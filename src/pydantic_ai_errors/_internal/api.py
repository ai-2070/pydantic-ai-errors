"""
High-level API for parsing and validating JSON with beautiful error output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from .diagnostics import Diagnostic, pydantic_error_to_diagnostics
from .renderer import RenderOptions, render_diagnostics
from .source_map import JsonPath, parse_json_with_source_map

T = TypeVar("T", bound=BaseModel)


@dataclass
class ValidationSuccess(Generic[T]):
    """Successful validation result."""

    data: T
    success: Literal[True] = True


@dataclass
class ValidationFailure:
    """Failed validation result."""

    formatted: str
    diagnostics: list[Diagnostic]
    success: Literal[False] = False


ValidationResult = ValidationSuccess[T] | ValidationFailure


class PydanticValidationError(Exception):
    """Exception raised when validation fails and throw=True."""

    diagnostics: list[Diagnostic]

    def __init__(self, formatted: str, diagnostics: list[Diagnostic]) -> None:
        super().__init__(formatted)
        self.diagnostics = diagnostics


def parse_json(
    json_string: str,
    model: type[T],
    *,
    filename: str = "",
    colors: bool = True,
    context_lines: int = 4,
    throw: bool = False,
    compact: bool = False,
    custom_messages: dict[JsonPath, str] | None = None,
) -> ValidationResult[T]:
    """
    Parse and validate JSON against a Pydantic model.

    Returns a ValidationSuccess with the parsed data on success,
    or a ValidationFailure with formatted errors on failure.

    Args:
        json_string: The JSON string to parse and validate.
        model: The Pydantic model class to validate against.
        filename: The filename to display in error messages.
        colors: Whether to use ANSI colors in output.
        context_lines: Number of context lines to show around errors.
        throw: If True, raise PydanticValidationError instead of returning failure.
        compact: If True, show all errors in a single error window.
        custom_messages: Dict mapping field paths to custom error messages.
            Keys are tuples like ("user", "name") or ("items", 0, "price").

    Returns:
        ValidationSuccess or ValidationFailure.

    Raises:
        PydanticValidationError: If validation fails and throw=True.
    """
    # Parse JSON with source mapping
    data, source_map = parse_json_with_source_map(json_string)

    # Validate against model
    try:
        parsed = model.model_validate(data)
        return ValidationSuccess(parsed)
    except ValidationError as e:
        # Convert to diagnostics
        diagnostics = pydantic_error_to_diagnostics(e, source_map, data)

        # Render formatted output
        options = RenderOptions(
            colors=colors,
            filename=filename,
            context_lines=context_lines,
            compact=compact,
            custom_messages=custom_messages or {},
        )
        formatted = render_diagnostics(diagnostics, source_map, options)

        if throw:
            raise PydanticValidationError(formatted, diagnostics) from e

        return ValidationFailure(formatted, diagnostics)


def format_pydantic_error(
    error: ValidationError,
    json_string: str,
    *,
    filename: str = "",
    colors: bool = True,
    context_lines: int = 4,
    compact: bool = False,
    custom_messages: dict[JsonPath, str] | None = None,
) -> str:
    """
    Format an existing Pydantic ValidationError with source context.

    Args:
        error: The Pydantic ValidationError to format.
        json_string: The original JSON string (for source locations).
        filename: The filename to display in error messages.
        colors: Whether to use ANSI colors in output.
        context_lines: Number of context lines to show around errors.
        compact: If True, show all errors in a single error window.
        custom_messages: Dict mapping field paths to custom error messages.
            Keys are tuples like ("user", "name") or ("items", 0, "price").

    Returns:
        Formatted error string.
    """
    data, source_map = parse_json_with_source_map(json_string)
    diagnostics = pydantic_error_to_diagnostics(error, source_map, data)
    options = RenderOptions(
        colors=colors,
        filename=filename,
        context_lines=context_lines,
        compact=compact,
        custom_messages=custom_messages or {},
    )
    return render_diagnostics(diagnostics, source_map, options)


def create_validator(
    model: type[T],
    *,
    filename: str = "",
    colors: bool = True,
    context_lines: int = 4,
    compact: bool = False,
    custom_messages: dict[JsonPath, str] | None = None,
) -> Callable[[str], ValidationResult[T]]:
    """
    Create a reusable validator function for a Pydantic model.

    Args:
        model: The Pydantic model class to validate against.
        filename: Default filename to display in error messages.
        colors: Default for whether to use ANSI colors.
        context_lines: Default number of context lines to show.
        compact: If True, show all errors in a single error window.
        custom_messages: Dict mapping field paths to custom error messages.
            Keys are tuples like ("user", "name") or ("items", 0, "price").

    Returns:
        A validator function that takes a JSON string and returns ValidationResult.
    """

    def validator(json_string: str) -> ValidationResult[T]:
        return parse_json(
            json_string,
            model,
            filename=filename,
            colors=colors,
            context_lines=context_lines,
            compact=compact,
            custom_messages=custom_messages,
        )

    return validator
