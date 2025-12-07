"""
Tracks source locations in JSON for error reporting.
Maps JSON paths to their line/column positions in the source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceLocation:
    """A position in the source text."""

    line: int
    column: int
    offset: int


@dataclass(frozen=True)
class SourceSpan:
    """A span of text in the source, tracking both the full span and value span."""

    start: SourceLocation
    end: SourceLocation
    value_start: SourceLocation
    value_end: SourceLocation


JsonPath = tuple[str | int, ...]


class JsonSourceMap:
    """Maps JSON paths to their source locations."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.lines = source.split("\n")
        self._locations: dict[JsonPath, SourceSpan] = {}

    def set(self, path: JsonPath, span: SourceSpan) -> None:
        """Store the source span for a path."""
        self._locations[path] = span

    def get(self, path: JsonPath) -> SourceSpan | None:
        """Get the source span for a path."""
        return self._locations.get(path)

    def get_line_content(self, line_number: int) -> str:
        """Get the content of a specific line (1-indexed)."""
        if 1 <= line_number <= len(self.lines):
            return self.lines[line_number - 1]
        return ""

    def get_context_lines(self, line_number: int, before: int, after: int) -> list[tuple[int, str]]:
        """Get context lines around a given line number."""
        start_line = max(1, line_number - before)
        end_line = min(len(self.lines), line_number + after)
        return [(i, self.lines[i - 1]) for i in range(start_line, end_line + 1)]


class _JsonParser:
    """JSON parser that tracks source locations."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.source_map = JsonSourceMap(source)

    def _current_location(self) -> SourceLocation:
        return SourceLocation(line=self.line, column=self.column, offset=self.pos)

    def _char_at(self, pos: int) -> str:
        if pos < len(self.source):
            return self.source[pos]
        return ""

    def _current_char(self) -> str:
        return self._char_at(self.pos)

    def _advance(self, count: int = 1) -> None:
        for _ in range(count):
            if self.pos < len(self.source):
                if self.source[self.pos] == "\n":
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.pos += 1

    def _skip_whitespace(self) -> None:
        while self.pos < len(self.source) and self._current_char() in " \t\n\r":
            self._advance()

    def _parse_string(self) -> str:
        if self._current_char() != '"':
            raise ValueError(f"Expected '\"' at position {self.pos}")
        self._advance()  # skip opening quote

        result: list[str] = []
        while self.pos < len(self.source) and self._current_char() != '"':
            if self._current_char() == "\\":
                self._advance()
                escape_char = self._current_char()
                if escape_char == "n":
                    result.append("\n")
                elif escape_char == "r":
                    result.append("\r")
                elif escape_char == "t":
                    result.append("\t")
                elif escape_char == "\\":
                    result.append("\\")
                elif escape_char == '"':
                    result.append('"')
                elif escape_char == "u":
                    self._advance()
                    hex_str = self.source[self.pos : self.pos + 4]
                    result.append(chr(int(hex_str, 16)))
                    self._advance(3)
                else:
                    result.append(escape_char)
            else:
                result.append(self._current_char())
            self._advance()
        self._advance()  # skip closing quote
        return "".join(result)

    def _parse_number(self) -> int | float:
        start = self.pos
        if self._current_char() == "-":
            self._advance()

        while self.pos < len(self.source) and self._current_char().isdigit():
            self._advance()

        is_float = False
        if self._current_char() == ".":
            is_float = True
            self._advance()
            while self.pos < len(self.source) and self._current_char().isdigit():
                self._advance()

        if self._current_char() in "eE":
            is_float = True
            self._advance()
            if self._current_char() in "+-":
                self._advance()
            while self.pos < len(self.source) and self._current_char().isdigit():
                self._advance()

        num_str = self.source[start : self.pos]
        return float(num_str) if is_float else int(num_str)

    def _parse_value(self, path: JsonPath) -> Any:
        self._skip_whitespace()

        start = self._current_location()
        value_start = self._current_location()
        value: Any
        char = self._current_char()

        if char == '"':
            value = self._parse_string()
        elif char == "-" or char.isdigit():
            value = self._parse_number()
        elif char == "{":
            value = self._parse_object(path)
        elif char == "[":
            value = self._parse_array(path)
        elif self.source[self.pos : self.pos + 4] == "true":
            value = True
            self._advance(4)
        elif self.source[self.pos : self.pos + 5] == "false":
            value = False
            self._advance(5)
        elif self.source[self.pos : self.pos + 4] == "null":
            value = None
            self._advance(4)
        else:
            raise ValueError(
                f"Unexpected character '{char}' at line {self.line}, column {self.column}"
            )

        value_end = self._current_location()
        end = self._current_location()

        self.source_map.set(
            path,
            SourceSpan(start=start, end=end, value_start=value_start, value_end=value_end),
        )

        return value

    def _parse_object(self, path: JsonPath) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        self._advance()  # skip {
        self._skip_whitespace()

        if self._current_char() == "}":
            self._advance()
            return obj

        while True:
            self._skip_whitespace()
            key = self._parse_string()
            self._skip_whitespace()

            if self._current_char() != ":":
                raise ValueError(f"Expected ':' at position {self.pos}")
            self._advance()  # skip :

            obj[key] = self._parse_value((*path, key))

            self._skip_whitespace()
            if self._current_char() == "}":
                self._advance()
                break
            if self._current_char() != ",":
                raise ValueError(f"Expected ',' or '}}' at position {self.pos}")
            self._advance()  # skip ,

        return obj

    def _parse_array(self, path: JsonPath) -> list[Any]:
        arr: list[Any] = []
        self._advance()  # skip [
        self._skip_whitespace()

        if self._current_char() == "]":
            self._advance()
            return arr

        index = 0
        while True:
            arr.append(self._parse_value((*path, index)))
            index += 1

            self._skip_whitespace()
            if self._current_char() == "]":
                self._advance()
                break
            if self._current_char() != ",":
                raise ValueError(f"Expected ',' or ']' at position {self.pos}")
            self._advance()  # skip ,

        return arr

    def parse(self) -> Any:
        return self._parse_value(())


def parse_json_with_source_map(source: str) -> tuple[Any, JsonSourceMap]:
    """Parse JSON and return both the data and a source map for error locations."""
    parser = _JsonParser(source)
    data = parser.parse()
    return data, parser.source_map
