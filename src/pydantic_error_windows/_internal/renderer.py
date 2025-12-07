"""
Renders diagnostics in a beautiful Rust-style format.
"""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import Diagnostic, DiagnosticSeverity
from .source_map import JsonSourceMap


@dataclass
class RenderOptions:
    """Options for rendering diagnostics."""

    colors: bool = True
    filename: str = "input.json"
    context_lines: int = 4


@dataclass
class _Colors:
    """ANSI color codes."""

    red: str = ""
    cyan: str = ""
    yellow: str = ""
    blue: str = ""
    bold: str = ""
    reset: str = ""


_NO_COLORS = _Colors()
_ANSI_COLORS = _Colors(
    red="\033[31m",
    cyan="\033[36m",
    yellow="\033[33m",
    blue="\033[34m",
    bold="\033[1m",
    reset="\033[0m",
)


def _colorize(text: str, *codes: str) -> str:
    """Apply color codes to text."""
    if not codes or not codes[0]:
        return text
    return "".join(codes) + text + _ANSI_COLORS.reset


def render_diagnostic(
    diagnostic: Diagnostic,
    source_map: JsonSourceMap,
    options: RenderOptions | None = None,
) -> str:
    """Render a single diagnostic as a formatted string."""
    options = options or RenderOptions()
    c = _ANSI_COLORS if options.colors else _NO_COLORS

    lines: list[str] = []

    # Header: error[PYD001]: message
    severity_color = c.red if diagnostic.severity == DiagnosticSeverity.ERROR else c.yellow
    header = _colorize(
        _colorize(f"{diagnostic.severity.value}[{diagnostic.code}]", c.bold),
        severity_color,
    )
    lines.append(f"{header}: {_colorize(diagnostic.message, c.bold)}")

    if diagnostic.span:
        value_start = diagnostic.span.value_start
        value_end = diagnostic.span.value_end

        # Location pointer: --> filename:line:column
        arrow = _colorize("-->", c.blue)
        lines.append(f"  {arrow} {options.filename}:{value_start.line}:{value_start.column}")

        # Get context lines
        error_line = value_start.line
        all_lines = source_map.get_context_lines(
            error_line, options.context_lines, options.context_lines
        )

        # Calculate gutter width
        max_line_num = all_lines[-1][0] if all_lines else error_line
        gutter_width = len(str(max_line_num))

        # Empty gutter line
        pipe = _colorize("|", c.blue)
        lines.append(f"{' ' * (gutter_width + 1)}{pipe}")

        # Render each context line
        for line_number, content in all_lines:
            line_num_str = str(line_number).rjust(gutter_width)
            lines.append(f"{_colorize(line_num_str, c.blue)} {pipe} {content}")

            # If this is the error line, add the underline
            if line_number == error_line:
                start_col = value_start.column - 1

                if value_start.line == value_end.line:
                    underline_length = max(1, value_end.column - value_start.column)
                else:
                    underline_length = max(1, len(content) - start_col)

                # Build annotation message
                annotation_msg = ""
                if diagnostic.expected and diagnostic.received:
                    annotation_msg = f"expected {diagnostic.expected}, found {diagnostic.received}"
                elif diagnostic.expected:
                    annotation_msg = f"expected {diagnostic.expected}"

                padding = " " * start_col
                underline = "^" * underline_length
                lines.append(
                    f"{' ' * (gutter_width + 1)}{pipe} {padding}"
                    f"{_colorize(underline, c.red)} {_colorize(annotation_msg, c.red)}"
                )

        # Closing gutter
        lines.append(f"{' ' * (gutter_width + 1)}{pipe}")

    # Help message
    if diagnostic.help:
        gutter_width = len(str(len(source_map.lines))) if diagnostic.span else 1
        eq = _colorize("=", c.blue)
        help_label = _colorize("help", c.cyan)
        lines.append(f"{' ' * (gutter_width + 1)}{eq} {help_label}: {diagnostic.help}")

    return "\n".join(lines)


def render_diagnostics(
    diagnostics: list[Diagnostic],
    source_map: JsonSourceMap,
    options: RenderOptions | None = None,
) -> str:
    """Render multiple diagnostics as a formatted string."""
    return "\n\n".join(render_diagnostic(d, source_map, options) for d in diagnostics)
