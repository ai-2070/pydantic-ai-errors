"""Tests for the main API."""

import pytest
from pydantic import BaseModel, Field

from pydantic_ai_errors import (
    PydanticValidationError,
    create_validator,
    format_pydantic_error,
    parse_json,
)


class SimpleModel(BaseModel):
    name: str
    age: int


class ConstrainedModel(BaseModel):
    name: str = Field(min_length=3)
    value: int = Field(ge=10)


class TestParseJson:
    def test_returns_success_for_valid_input(self) -> None:
        result = parse_json('{"name": "alice", "age": 25}', SimpleModel)

        assert result.success is True
        assert result.data.name == "alice"
        assert result.data.age == 25

    def test_returns_formatted_error_for_invalid_input(self) -> None:
        result = parse_json('{"name": "alice", "age": "old"}', SimpleModel)

        assert result.success is False
        assert "error[PYD001]" in result.formatted
        assert "age" in result.formatted
        assert len(result.diagnostics) == 1

    def test_respects_filename_option(self) -> None:
        result = parse_json('{"name": 123, "age": 25}', SimpleModel, filename="config.json")

        assert result.success is False
        assert "config.json" in result.formatted

    def test_can_disable_colors(self) -> None:
        result = parse_json('{"name": 123, "age": 25}', SimpleModel, colors=False)

        assert result.success is False
        assert "\033[" not in result.formatted

    def test_throws_when_throw_option_is_true(self) -> None:
        with pytest.raises(PydanticValidationError) as exc_info:
            parse_json('{"name": 123, "age": 25}', SimpleModel, throw=True)

        assert "error[PYD001]" in str(exc_info.value)

    def test_handles_constraint_errors(self) -> None:
        result = parse_json('{"name": "ab", "value": 5}', ConstrainedModel)

        assert result.success is False
        assert len(result.diagnostics) >= 2


class TestFormatPydanticError:
    def test_formats_existing_error(self) -> None:
        json = '{"name": "alice", "age": "old"}'

        # Create the error by attempting validation
        try:
            SimpleModel.model_validate_json(json)
            pytest.fail("Expected ValidationError")
        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                formatted = format_pydantic_error(e, json, colors=False)
                assert "error[PYD001]" in formatted
                assert "age" in formatted


class TestCreateValidator:
    def test_creates_reusable_validator(self) -> None:
        validate = create_validator(SimpleModel, filename="config.json")

        valid = validate('{"name": "alice", "age": 25}')
        assert valid.success is True

        invalid = validate('{"name": "alice", "age": "old"}')
        assert invalid.success is False
        assert "config.json" in invalid.formatted


class TestCompactMode:
    def test_compact_mode_shows_all_errors_in_one_window(self) -> None:
        result = parse_json(
            '{"name": "ab", "value": 5}',
            ConstrainedModel,
            compact=True,
            colors=False,
        )

        assert result.success is False
        # In compact mode, all errors should be listed at the top
        assert "error[PYD001]" in result.formatted
        assert "error[PYD002]" in result.formatted
        # Should only have one code window (one --> marker)
        assert result.formatted.count("-->") == 1

    def test_compact_mode_with_multiple_errors(self) -> None:
        json_input = """{
  "name": "",
  "value": 0
}"""
        result = parse_json(json_input, ConstrainedModel, compact=True, colors=False)

        assert result.success is False
        # Both errors should be shown
        assert "name" in result.formatted
        assert "value" in result.formatted
        # Help messages for both errors should appear
        assert "help:" in result.formatted

    def test_non_compact_mode_shows_separate_windows(self) -> None:
        result = parse_json(
            '{"name": "ab", "value": 5}',
            ConstrainedModel,
            compact=False,
            colors=False,
        )

        assert result.success is False
        # In non-compact mode, each error has its own window
        assert result.formatted.count("-->") == 2


class TestCustomMessages:
    def test_custom_message_overrides_default(self) -> None:
        result = parse_json(
            '{"name": 123, "age": 25}',
            SimpleModel,
            colors=False,
            custom_messages={("name",): "Please provide your full name as text"},
        )

        assert result.success is False
        assert "Please provide your full name as text" in result.formatted
        # Original message should not appear
        assert "type mismatch" not in result.formatted

    def test_custom_message_only_affects_specified_field(self) -> None:
        result = parse_json(
            '{"name": 123, "age": "old"}',
            SimpleModel,
            colors=False,
            custom_messages={("name",): "Custom name error"},
        )

        assert result.success is False
        assert "Custom name error" in result.formatted
        # Age should still use the default message (not overridden)
        assert "field `age`" in result.formatted
        assert "PYD002" in result.formatted

    def test_custom_message_with_nested_path(self) -> None:
        from pydantic import BaseModel

        class Address(BaseModel):
            city: str
            zip_code: int

        class Person(BaseModel):
            name: str
            address: Address

        result = parse_json(
            '{"name": "alice", "address": {"city": 123, "zip_code": "abc"}}',
            Person,
            colors=False,
            custom_messages={("address", "city"): "City must be a string"},
        )

        assert result.success is False
        assert "City must be a string" in result.formatted

    def test_custom_message_with_compact_mode(self) -> None:
        result = parse_json(
            '{"name": "ab", "value": 5}',
            ConstrainedModel,
            compact=True,
            colors=False,
            custom_messages={
                ("name",): "Name is too short",
                ("value",): "Value is below minimum",
            },
        )

        assert result.success is False
        assert "Name is too short" in result.formatted
        assert "Value is below minimum" in result.formatted

    def test_custom_message_in_create_validator(self) -> None:
        validate = create_validator(
            SimpleModel,
            filename="user.json",
            colors=False,
            custom_messages={("name",): "Invalid username"},
        )

        result = validate('{"name": 123, "age": 25}')
        assert result.success is False
        assert "Invalid username" in result.formatted

    def test_custom_message_in_format_pydantic_error(self) -> None:
        json = '{"name": 123, "age": 25}'

        try:
            SimpleModel.model_validate_json(json)
            pytest.fail("Expected ValidationError")
        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                formatted = format_pydantic_error(
                    e,
                    json,
                    colors=False,
                    custom_messages={("name",): "Name should be text"},
                )
                assert "Name should be text" in formatted
