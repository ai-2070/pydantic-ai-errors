"""
Converts Pydantic errors into structured diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import ValidationError

from .source_map import JsonPath, JsonSourceMap, SourceSpan


class DiagnosticSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Diagnostic:
    """A structured diagnostic message."""

    code: str
    severity: DiagnosticSeverity
    message: str
    path: JsonPath
    span: SourceSpan | None
    help: str | None
    expected: str | None
    received: str | None


def _format_path(path: JsonPath) -> str:
    """Format a JSON path as a dotted string."""
    if not path:
        return "root"
    parts: list[str] = []
    for i, p in enumerate(path):
        if isinstance(p, int):
            parts.append(f"[{p}]")
        elif i == 0:
            parts.append(str(p))
        else:
            parts.append(f".{p}")
    return "".join(parts)


def _generate_error_code(index: int) -> str:
    """Generate an error code like PYD001."""
    return f"PYD{index + 1:03d}"


def _describe_value(value: Any) -> str:
    """Describe a value for error messages."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"boolean {str(value).lower()}"
    if isinstance(value, str):
        return f'string "{value}"'
    if isinstance(value, int):
        return f"integer {value}"
    if isinstance(value, float):
        return f"number {value}"
    if isinstance(value, list):
        return f"array with {len(value)} elements"
    if isinstance(value, dict):
        return "object"
    return str(value)


def _get_value_at_path(data: Any, path: JsonPath) -> Any:
    """Get the value at a given path in the data."""
    current = data
    for segment in path:
        if isinstance(current, dict) and isinstance(segment, str):
            current = current.get(segment)
        elif isinstance(current, list) and isinstance(segment, int):
            if 0 <= segment < len(current):
                current = current[segment]
            else:
                return None
        else:
            return None
    return current


def _generate_help(error_type: str, ctx: dict[str, Any] | None, received_value: Any) -> str | None:
    """Generate a helpful suggestion based on the error type."""
    ctx = ctx or {}

    if error_type == "string_type":
        if isinstance(received_value, int | float):
            return f"convert the number {received_value} to a string"
        return "provide a string value"

    if error_type == "int_type":
        if isinstance(received_value, str):
            try:
                parsed = int(received_value)
                return f'convert the string "{received_value}" to an integer ({parsed})'
            except ValueError:
                return f'convert the string "{received_value}" to an integer'
        return "provide an integer value"

    if error_type == "float_type":
        if isinstance(received_value, str):
            try:
                parsed = float(received_value)
                return f'convert the string "{received_value}" to a number ({parsed})'
            except ValueError:
                return f'convert the string "{received_value}" to a number'
        return "provide a number value"

    if error_type == "string_too_short":
        min_length = ctx.get("min_length", 1)
        return (
            f"provide a string with at least {min_length} character{'s' if min_length != 1 else ''}"
        )

    if error_type == "string_too_long":
        max_length = ctx.get("max_length", 0)
        return (
            f"provide a string with at most {max_length} character{'s' if max_length != 1 else ''}"
        )

    if error_type in ("greater_than", "greater_than_equal"):
        limit = ctx.get("gt") or ctx.get("ge")
        op = ">=" if error_type == "greater_than_equal" else ">"
        return f"provide a number {op} {limit}"

    if error_type in ("less_than", "less_than_equal"):
        limit = ctx.get("lt") or ctx.get("le")
        op = "<=" if error_type == "less_than_equal" else "<"
        return f"provide a number {op} {limit}"

    if error_type == "value_error":
        if "email" in str(ctx.get("error", "")).lower():
            return "provide a valid email address (e.g., user@example.com)"
        if "url" in str(ctx.get("error", "")).lower():
            return "provide a valid URL (e.g., https://example.com)"

    if error_type == "enum":
        expected = ctx.get("expected", "")
        return f"use one of the allowed values: {expected}"

    if error_type == "literal_error":
        expected = ctx.get("expected", "")
        return f"use the expected value: {expected}"

    if error_type == "missing":
        return "provide the required field"

    if error_type == "extra_forbidden":
        return "remove this unrecognized field"

    return None


def _format_expected(error_type: str, ctx: dict[str, Any] | None) -> str | None:
    """Format the expected value/type for display."""
    ctx = ctx or {}

    if error_type == "string_type":
        return "string"

    if error_type == "int_type":
        return "integer"

    if error_type == "float_type":
        return "number"

    if error_type == "bool_type":
        return "boolean"

    if error_type == "string_too_short":
        min_length = ctx.get("min_length", 1)
        return f"a string (min {min_length} chars)"

    if error_type == "string_too_long":
        max_length = ctx.get("max_length", 0)
        return f"a string (max {max_length} chars)"

    if error_type in ("greater_than", "greater_than_equal"):
        limit = ctx.get("gt") or ctx.get("ge")
        op = "≥" if error_type == "greater_than_equal" else ">"
        return f"a number {op} {limit}"

    if error_type in ("less_than", "less_than_equal"):
        limit = ctx.get("lt") or ctx.get("le")
        op = "≤" if error_type == "less_than_equal" else "<"
        return f"a number {op} {limit}"

    if error_type == "enum":
        return ctx.get("expected", "enum value")

    if error_type == "literal_error":
        return ctx.get("expected", "literal value")

    if error_type == "missing":
        return "required field"

    return None


def _generate_message(error_type: str, path: JsonPath, ctx: dict[str, Any] | None) -> str:
    """Generate a human-readable error message."""
    path_str = _format_path(path)
    ctx = ctx or {}

    if error_type in ("string_type", "int_type", "float_type", "bool_type"):
        return f"type mismatch for field `{path_str}`"

    if error_type in ("string_too_short", "string_too_long"):
        return f"invalid value for field `{path_str}`"

    if error_type in ("greater_than", "greater_than_equal", "less_than", "less_than_equal"):
        return f"invalid value for field `{path_str}`"

    if error_type == "enum":
        return f"invalid enum value for field `{path_str}`"

    if error_type == "literal_error":
        return f"invalid literal for field `{path_str}`"

    if error_type == "missing":
        return f"missing required field `{path_str}`"

    if error_type == "extra_forbidden":
        return f"unrecognized field `{path_str}`"

    if error_type == "value_error":
        if "email" in str(ctx.get("error", "")).lower():
            return f"invalid email for field `{path_str}`"
        if "url" in str(ctx.get("error", "")).lower():
            return f"invalid URL for field `{path_str}`"

    return f"validation error for field `{path_str}`"


def pydantic_error_to_diagnostics(
    error: ValidationError,
    source_map: JsonSourceMap,
    input_data: Any,
) -> list[Diagnostic]:
    """Convert a Pydantic ValidationError to a list of diagnostics."""
    diagnostics: list[Diagnostic] = []

    for i, err in enumerate(error.errors()):
        # Convert path to tuple
        path: JsonPath = tuple(err["loc"])
        span = source_map.get(path)

        # Get the actual value at this path
        received_value = _get_value_at_path(input_data, path)

        error_type = err["type"]
        ctx = err.get("ctx")

        diagnostics.append(
            Diagnostic(
                code=_generate_error_code(i),
                severity=DiagnosticSeverity.ERROR,
                message=_generate_message(error_type, path, ctx),
                path=path,
                span=span,
                help=_generate_help(error_type, ctx, received_value),
                expected=_format_expected(error_type, ctx),
                received=_describe_value(received_value),
            )
        )

    return diagnostics
