"""
pydantic-error-windows

Beautiful, AI-friendly Pydantic error formatting with Rust-style diagnostics.
"""

from ._internal.api import (
    PydanticValidationError,
    create_validator,
    format_pydantic_error,
    parse_json,
)
from ._internal.diagnostics import Diagnostic, DiagnosticSeverity, pydantic_error_to_diagnostics
from ._internal.renderer import RenderOptions, render_diagnostic, render_diagnostics
from ._internal.source_map import (
    JsonSourceMap,
    SourceLocation,
    SourceSpan,
    parse_json_with_source_map,
)

__all__ = [
    # Source map
    "JsonSourceMap",
    "SourceLocation",
    "SourceSpan",
    "parse_json_with_source_map",
    # Diagnostics
    "Diagnostic",
    "DiagnosticSeverity",
    "pydantic_error_to_diagnostics",
    # Renderer
    "render_diagnostic",
    "render_diagnostics",
    "RenderOptions",
    # API
    "parse_json",
    "format_pydantic_error",
    "create_validator",
    "PydanticValidationError",
]

__version__ = "1.0.0"
