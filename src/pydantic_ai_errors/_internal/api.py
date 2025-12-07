"""
High-level API for parsing and validating JSON with beautiful error output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .diagnostics import Diagnostic, pydantic_error_to_diagnostics
from .renderer import RenderOptions, render_diagnostics
from .source_map import parse_json_with_source_map

T = TypeVar("T", bound=BaseModel)


@dataclass
class ValidationSuccess(Generic[T]):
    """Successful validation result."""

    success: bool
    data: T

    def __init__(self, data: T) -> None:
        self.success = True
        self.data = data


@dataclass
class ValidationFailure:
    """Failed validation result."""

    success: bool
    formatted: str
    diagnostics: list[Diagnostic]

    def __init__(self, formatted: str, diagnostics: list[Diagnostic]) -> None:
        self.success = False
        self.formatted = formatted
        self.diagnostics = diagnostics


ValidationResult = ValidationSuccess[T] | ValidationFailure


class PydanticValidationError(Exception):
    """Exception raised when validation fails and throw=True."""

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
) -> str:
    """
    Format an existing Pydantic ValidationError with source context.

    Args:
        error: The Pydantic ValidationError to format.
        json_string: The original JSON string (for source locations).
        filename: The filename to display in error messages.
        colors: Whether to use ANSI colors in output.
        context_lines: Number of context lines to show around errors.

    Returns:
        Formatted error string.
    """
    data, source_map = parse_json_with_source_map(json_string)
    diagnostics = pydantic_error_to_diagnostics(error, source_map, data)
    options = RenderOptions(
        colors=colors,
        filename=filename,
        context_lines=context_lines,
    )
    return render_diagnostics(diagnostics, source_map, options)


def create_validator(
    model: type[T],
    *,
    filename: str = "",
    colors: bool = True,
    context_lines: int = 4,
) -> Callable[[str], ValidationResult[T]]:
    """
    Create a reusable validator function for a Pydantic model.

    Args:
        model: The Pydantic model class to validate against.
        filename: Default filename to display in error messages.
        colors: Default for whether to use ANSI colors.
        context_lines: Default number of context lines to show.

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
        )

    return validator
