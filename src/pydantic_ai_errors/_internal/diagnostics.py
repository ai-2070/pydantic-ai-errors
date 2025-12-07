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


# Maps error types to (message_template, expected, help_text)
# Templates use {path} for field path and {ctx_*} for context values
_ERROR_TYPE_INFO: dict[str, tuple[str, str | None, str | None]] = {
    # String types
    "string_type": ("type mismatch for field `{path}`", "string", "provide a string value"),
    "string_too_short": (
        "invalid value for field `{path}`",
        "a string (min {min_length} chars)",
        "provide a string with at least {min_length} characters",
    ),
    "string_too_long": (
        "invalid value for field `{path}`",
        "a string (max {max_length} chars)",
        "provide a string with at most {max_length} characters",
    ),
    "string_pattern_mismatch": (
        "invalid format for field `{path}`",
        "string matching pattern",
        "provide a string matching the required pattern",
    ),
    "string_unicode": (
        "invalid unicode for field `{path}`",
        "valid unicode string",
        "provide a valid unicode string",
    ),
    "string_sub_type": (
        "invalid string subtype for field `{path}`",
        "valid string subtype",
        "provide a valid string value",
    ),
    # Integer types
    "int_type": ("type mismatch for field `{path}`", "integer", "provide an integer value"),
    "int_parsing": (
        "invalid integer for field `{path}`",
        "valid integer",
        "provide a valid integer value",
    ),
    "int_parsing_size": (
        "integer too large for field `{path}`",
        "integer within range",
        "provide a smaller integer value",
    ),
    "int_from_float": (
        "float not allowed for field `{path}`",
        "integer (not float)",
        "provide an integer without decimal places",
    ),
    # Float types
    "float_type": ("type mismatch for field `{path}`", "number", "provide a number value"),
    "float_parsing": (
        "invalid number for field `{path}`",
        "valid number",
        "provide a valid number",
    ),
    "finite_number": (
        "infinite number for field `{path}`",
        "finite number",
        "provide a finite number (not infinity or NaN)",
    ),
    # Decimal types
    "decimal_type": ("type mismatch for field `{path}`", "decimal", "provide a decimal value"),
    "decimal_parsing": (
        "invalid decimal for field `{path}`",
        "valid decimal",
        "provide a valid decimal number",
    ),
    "decimal_max_digits": (
        "too many digits for field `{path}`",
        "decimal with fewer digits",
        "reduce the number of digits",
    ),
    "decimal_max_places": (
        "too many decimal places for field `{path}`",
        "decimal with fewer places",
        "reduce the number of decimal places",
    ),
    "decimal_whole_digits": (
        "too many whole digits for field `{path}`",
        "decimal with fewer whole digits",
        "reduce the number of digits before the decimal point",
    ),
    # Boolean types
    "bool_type": ("type mismatch for field `{path}`", "boolean", "provide true or false"),
    "bool_parsing": (
        "invalid boolean for field `{path}`",
        "boolean",
        "provide a boolean value (true or false)",
    ),
    # None/null
    "none_required": (
        "null required for field `{path}`",
        "null",
        "provide null value",
    ),
    # Bytes types
    "bytes_type": ("type mismatch for field `{path}`", "bytes", "provide bytes or string value"),
    "bytes_too_short": (
        "bytes too short for field `{path}`",
        "longer bytes value",
        "provide more bytes",
    ),
    "bytes_too_long": (
        "bytes too long for field `{path}`",
        "shorter bytes value",
        "reduce the bytes length",
    ),
    # Date types
    "date_type": ("type mismatch for field `{path}`", "date", "provide a date value"),
    "date_parsing": (
        "invalid date for field `{path}`",
        "valid date",
        "provide a valid date (e.g., 2024-01-15)",
    ),
    "date_from_datetime_parsing": (
        "invalid date for field `{path}`",
        "valid date",
        "provide a valid date (e.g., 2024-01-15)",
    ),
    "date_from_datetime_inexact": (
        "datetime has time component for field `{path}`",
        "date without time",
        "provide a date without time component",
    ),
    "date_past": (
        "date must be in the past for field `{path}`",
        "past date",
        "provide a date in the past",
    ),
    "date_future": (
        "date must be in the future for field `{path}`",
        "future date",
        "provide a date in the future",
    ),
    # Time types
    "time_type": ("type mismatch for field `{path}`", "time", "provide a time value"),
    "time_parsing": (
        "invalid time for field `{path}`",
        "valid time",
        "provide a valid time (e.g., 10:30:00)",
    ),
    "time_delta_type": (
        "type mismatch for field `{path}`",
        "time duration",
        "provide a time duration value",
    ),
    "time_delta_parsing": (
        "invalid duration for field `{path}`",
        "valid duration",
        "provide a valid time duration",
    ),
    # Datetime types
    "datetime_type": ("type mismatch for field `{path}`", "datetime", "provide a datetime value"),
    "datetime_parsing": (
        "invalid datetime for field `{path}`",
        "valid datetime",
        "provide a valid datetime (e.g., 2024-01-15T10:30:00)",
    ),
    "datetime_from_date_parsing": (
        "invalid datetime for field `{path}`",
        "valid datetime",
        "provide a valid datetime (e.g., 2024-01-15T10:30:00)",
    ),
    "datetime_object_invalid": (
        "invalid datetime object for field `{path}`",
        "valid datetime",
        "provide a valid datetime value",
    ),
    "datetime_past": (
        "datetime must be in the past for field `{path}`",
        "past datetime",
        "provide a datetime in the past",
    ),
    "datetime_future": (
        "datetime must be in the future for field `{path}`",
        "future datetime",
        "provide a datetime in the future",
    ),
    # Timezone
    "timezone_naive": (
        "timezone-naive datetime required for field `{path}`",
        "datetime without timezone",
        "remove the timezone from the datetime",
    ),
    "timezone_aware": (
        "timezone-aware datetime required for field `{path}`",
        "datetime with timezone",
        "add a timezone to the datetime (e.g., +00:00 or Z)",
    ),
    "timezone_offset": (
        "invalid timezone offset for field `{path}`",
        "valid timezone offset",
        "provide a valid timezone offset",
    ),
    # UUID types
    "uuid_type": ("type mismatch for field `{path}`", "UUID", "provide a UUID value"),
    "uuid_parsing": (
        "invalid UUID for field `{path}`",
        "valid UUID",
        "provide a valid UUID (e.g., 550e8400-e29b-41d4-a716-446655440000)",
    ),
    "uuid_version": (
        "wrong UUID version for field `{path}`",
        "UUID with correct version",
        "provide a UUID with the required version",
    ),
    # URL types
    "url_type": ("type mismatch for field `{path}`", "URL", "provide a URL value"),
    "url_parsing": (
        "invalid URL for field `{path}`",
        "valid URL",
        "provide a valid URL (e.g., https://example.com)",
    ),
    "url_syntax": (
        "invalid URL syntax for field `{path}`",
        "valid URL",
        "fix the URL syntax",
    ),
    "url_too_long": (
        "URL too long for field `{path}`",
        "shorter URL",
        "provide a shorter URL",
    ),
    "url_scheme": (
        "invalid URL scheme for field `{path}`",
        "URL with valid scheme",
        "use a valid URL scheme (e.g., https://)",
    ),
    # Collection types
    "list_type": ("type mismatch for field `{path}`", "array", "provide a list/array value"),
    "tuple_type": (
        "type mismatch for field `{path}`",
        "tuple/array",
        "provide a tuple/array value",
    ),
    "set_type": (
        "type mismatch for field `{path}`",
        "array of unique values",
        "provide a set of unique values",
    ),
    "frozenset_type": (
        "type mismatch for field `{path}`",
        "array of unique values",
        "provide a set of unique values",
    ),
    "dict_type": (
        "type mismatch for field `{path}`",
        "object",
        "provide an object/dictionary value",
    ),
    "iteration_error": (
        "cannot iterate over field `{path}`",
        "iterable value",
        "provide an iterable value",
    ),
    # Numeric constraints
    "greater_than": (
        "invalid value for field `{path}`",
        "a number > {gt}",
        "provide a number > {gt}",
    ),
    "greater_than_equal": (
        "invalid value for field `{path}`",
        "a number >= {ge}",
        "provide a number >= {ge}",
    ),
    "less_than": (
        "invalid value for field `{path}`",
        "a number < {lt}",
        "provide a number < {lt}",
    ),
    "less_than_equal": (
        "invalid value for field `{path}`",
        "a number <= {le}",
        "provide a number <= {le}",
    ),
    "multiple_of": (
        "invalid value for field `{path}`",
        "a multiple of {multiple_of}",
        "provide a number that is a multiple of {multiple_of}",
    ),
    # Length constraints
    "too_short": (
        "value too short for field `{path}`",
        "at least {min_length} items",
        "provide at least {min_length} items",
    ),
    "too_long": (
        "value too long for field `{path}`",
        "at most {max_length} items",
        "provide at most {max_length} items",
    ),
    # Enum/Literal/Union
    "enum": (
        "invalid enum value for field `{path}`",
        "{expected}",
        "use one of the allowed values: {expected}",
    ),
    "literal_error": (
        "invalid literal for field `{path}`",
        "{expected}",
        "use the expected value: {expected}",
    ),
    "union_tag_invalid": (
        "invalid discriminator value for field `{path}`",
        "valid discriminator",
        "provide a valid discriminator value",
    ),
    "union_tag_not_found": (
        "missing discriminator for field `{path}`",
        "discriminator field",
        "include the discriminator field",
    ),
    # Missing/Extra fields
    "missing": (
        "missing required field `{path}`",
        "required field",
        "provide the required field",
    ),
    "extra_forbidden": (
        "unrecognized field `{path}`",
        None,
        "remove this unrecognized field",
    ),
    "frozen_field": (
        "cannot modify frozen field `{path}`",
        None,
        "this field cannot be modified",
    ),
    "frozen_instance": (
        "cannot modify frozen instance at `{path}`",
        None,
        "this instance cannot be modified",
    ),
    # Model/dataclass types
    "model_type": (
        "type mismatch for field `{path}`",
        "model object",
        "provide a valid model object",
    ),
    "model_attributes_type": (
        "type mismatch for field `{path}`",
        "object with attributes",
        "provide an object with the required attributes",
    ),
    "dataclass_type": (
        "type mismatch for field `{path}`",
        "dataclass instance",
        "provide a valid dataclass instance",
    ),
    "dataclass_exact_type": (
        "type mismatch for field `{path}`",
        "exact dataclass type",
        "provide the exact dataclass type required",
    ),
    # Callable
    "callable_type": (
        "type mismatch for field `{path}`",
        "callable",
        "provide a callable (function)",
    ),
    # JSON
    "json_invalid": (
        "invalid JSON for field `{path}`",
        "valid JSON",
        "provide valid JSON",
    ),
    "json_type": (
        "type mismatch for field `{path}`",
        "JSON value",
        "provide a valid JSON value",
    ),
    # Recursion
    "recursion_loop": (
        "circular reference detected at `{path}`",
        None,
        "remove the circular reference",
    ),
    # Assertions
    "assertion_error": (
        "assertion failed for field `{path}`",
        None,
        "ensure the value meets validation requirements",
    ),
    # Value error (generic)
    "value_error": (
        "validation error for field `{path}`",
        None,
        None,
    ),
    # Custom error
    "custom_error": (
        "validation error for field `{path}`",
        None,
        None,
    ),
    # Arguments (function validation)
    "arguments_type": (
        "invalid arguments at `{path}`",
        "valid arguments",
        "provide valid function arguments",
    ),
    "missing_argument": (
        "missing argument `{path}`",
        "required argument",
        "provide the missing argument",
    ),
    "unexpected_keyword_argument": (
        "unexpected keyword argument `{path}`",
        None,
        "remove the unexpected argument",
    ),
    "missing_keyword_only_argument": (
        "missing keyword-only argument `{path}`",
        "required keyword argument",
        "provide the required keyword argument",
    ),
    "unexpected_positional_argument": (
        "unexpected positional argument at `{path}`",
        None,
        "remove the unexpected positional argument",
    ),
    "missing_positional_only_argument": (
        "missing positional argument `{path}`",
        "required positional argument",
        "provide the required positional argument",
    ),
    "multiple_argument_values": (
        "multiple values for argument `{path}`",
        "single value",
        "provide only one value for this argument",
    ),
    # Get/Attribute
    "get_attribute_error": (
        "cannot access attribute `{path}`",
        None,
        "ensure the attribute exists",
    ),
    "is_instance_of": (
        "type mismatch for field `{path}`",
        "instance of required type",
        "provide an instance of the required type",
    ),
    "is_subclass_of": (
        "type mismatch for field `{path}`",
        "subclass of required type",
        "provide a subclass of the required type",
    ),
}


def _format_template(template: str | None, path_str: str, ctx: dict[str, Any]) -> str | None:
    """Format a template string with path and context values."""
    if template is None:
        return None
    try:
        return template.format(path=path_str, **ctx)
    except KeyError:
        # If context is missing keys, just use basic substitution
        return template.replace("{path}", path_str)


def _generate_help(error_type: str, ctx: dict[str, Any] | None, received_value: Any) -> str | None:
    """Generate a helpful suggestion based on the error type."""
    ctx = ctx or {}

    # Special handling for some types with dynamic help
    if error_type == "string_type":
        if isinstance(received_value, int | float):
            return f"convert the number {received_value} to a string"

    if error_type == "int_type":
        if isinstance(received_value, str):
            try:
                parsed = int(received_value)
                return f'convert the string "{received_value}" to an integer ({parsed})'
            except ValueError:
                return f'convert the string "{received_value}" to an integer'

    if error_type == "float_type":
        if isinstance(received_value, str):
            try:
                parsed = float(received_value)
                return f'convert the string "{received_value}" to a number ({parsed})'
            except ValueError:
                return f'convert the string "{received_value}" to a number'

    if error_type == "value_error":
        error_str = str(ctx.get("error", "")).lower()
        if "email" in error_str:
            return "provide a valid email address (e.g., user@example.com)"
        if "url" in error_str:
            return "provide a valid URL (e.g., https://example.com)"

    # Look up in the error type info table
    if error_type in _ERROR_TYPE_INFO:
        _, _, help_template = _ERROR_TYPE_INFO[error_type]
        return _format_template(help_template, "", ctx)

    return None


def _format_expected(error_type: str, ctx: dict[str, Any] | None) -> str | None:
    """Format the expected value/type for display."""
    ctx = ctx or {}

    if error_type in _ERROR_TYPE_INFO:
        _, expected_template, _ = _ERROR_TYPE_INFO[error_type]
        return _format_template(expected_template, "", ctx)

    return None


def _generate_message(error_type: str, path: JsonPath, ctx: dict[str, Any] | None) -> str:
    """Generate a human-readable error message."""
    path_str = _format_path(path)
    ctx = ctx or {}

    # Special handling for value_error with email/url detection
    if error_type == "value_error":
        error_str = str(ctx.get("error", "")).lower()
        if "email" in error_str:
            return f"invalid email for field `{path_str}`"
        if "url" in error_str:
            return f"invalid URL for field `{path_str}`"

    if error_type in _ERROR_TYPE_INFO:
        message_template, _, _ = _ERROR_TYPE_INFO[error_type]
        result = _format_template(message_template, path_str, ctx)
        if result:
            return result

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
