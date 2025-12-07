"""Tests for JSON source map parsing."""

import pytest

from pydantic_ai_errors import parse_json_with_source_map


class TestParseJsonWithSourceMap:
    def test_parses_simple_object_and_tracks_locations(self) -> None:
        json = '{"name": "test"}'
        data, source_map = parse_json_with_source_map(json)

        assert data == {"name": "test"}

        name_span = source_map.get(("name",))
        assert name_span is not None
        assert name_span.value_start.column == 10

    def test_parses_nested_objects(self) -> None:
        json = """{
  "user": {
    "name": "alice"
  }
}"""
        data, source_map = parse_json_with_source_map(json)

        assert data == {"user": {"name": "alice"}}

        user_span = source_map.get(("user",))
        assert user_span is not None
        assert user_span.value_start.line == 2

        name_span = source_map.get(("user", "name"))
        assert name_span is not None
        assert name_span.value_start.line == 3

    def test_parses_arrays(self) -> None:
        json = '{"items": [1, 2, 3]}'
        data, source_map = parse_json_with_source_map(json)

        assert data == {"items": [1, 2, 3]}

        item0_span = source_map.get(("items", 0))
        assert item0_span is not None

        item2_span = source_map.get(("items", 2))
        assert item2_span is not None

    def test_parses_all_primitive_types(self) -> None:
        json = """{
  "string": "hello",
  "number": 42,
  "float": 3.14,
  "bool": true,
  "null": null
}"""
        data, _ = parse_json_with_source_map(json)

        assert data == {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
        }

    def test_handles_escape_sequences_in_strings(self) -> None:
        json = '{"text": "line1\\nline2\\ttab"}'
        data, _ = parse_json_with_source_map(json)

        assert data == {"text": "line1\nline2\ttab"}

    def test_tracks_correct_line_numbers(self) -> None:
        json = """{
  "a": 1,
  "b": 2,
  "c": 3
}"""
        _, source_map = parse_json_with_source_map(json)

        span_a = source_map.get(("a",))
        assert span_a is not None
        assert span_a.value_start.line == 2

        span_b = source_map.get(("b",))
        assert span_b is not None
        assert span_b.value_start.line == 3

        span_c = source_map.get(("c",))
        assert span_c is not None
        assert span_c.value_start.line == 4

    def test_provides_context_lines(self) -> None:
        json = """{
  "a": 1,
  "b": 2,
  "c": 3,
  "d": 4
}"""
        _, source_map = parse_json_with_source_map(json)

        context = source_map.get_context_lines(3, 1, 1)
        assert len(context) == 3
        assert context[0][0] == 2
        assert context[1][0] == 3
        assert context[2][0] == 4
