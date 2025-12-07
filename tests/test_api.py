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
