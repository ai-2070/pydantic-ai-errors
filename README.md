# Pydantic AI Errors

Beautiful, AI-friendly Pydantic error formatting with Rust-style diagnostics.

```
error[PYD001]: invalid value for field `user.name`
  --> input.json:3:13
  |
1 | {
2 |   "user": {
3 |     "name": "",
  |             ^^ expected a string (min 2 chars), found string ""
4 |     "age": "sixteen",
5 |     "email": "not-an-email",
  |
   = help: provide a string with at least 2 characters

error[PYD002]: type mismatch for field `user.age`
  --> input.json:4:12
  |
1 | {
2 |   "user": {
3 |     "name": "",
4 |     "age": "sixteen",
  |            ^^^^^^^^^ expected integer, found string "sixteen"
5 |     "email": "not-an-email",
  |
   = help: convert the string "sixteen" to an integer
```

## Features

- **Source location tracking** — Parses JSON while tracking line/column positions for each value
- **Rich diagnostics** — Converts Pydantic validation errors to structured diagnostics with full context
- **Rust-style output** — Beautiful error formatting inspired by the Rust compiler:
  - Error codes (`PYD001`, `PYD002`, etc.)
  - File location pointers (`--> input.json:3:12`)
  - Surrounding context lines with line numbers
  - Underlined error locations with `^^^`
  - Actionable help suggestions (`= help: ...`)
- **ANSI color support** — Colorized output for terminal display (can be disabled)
- **AI-friendly** — Structured output that's easy for LLMs to parse and act on

## Installation

### uv
```bash
uv add pydantic-ai-errors
```

### pip
```bash
pip install pydantic-ai-errors
```

Requires Pydantic v2.

## Usage

### Basic Usage

```python
from pydantic import BaseModel, Field
from pydantic_ai_errors import parse_json


class User(BaseModel):
    name: str = Field(min_length=2)
    age: int = Field(ge=18)
    email: str


json_input = '''{
  "name": "",
  "age": "sixteen",
  "email": "not-valid"
}'''

result = parse_json(json_input, User, filename="user.json")

if not result.success:
    print(result.formatted)
    # Also available: result.diagnostics for programmatic access
```

### Format Existing Pydantic Error

If you already have a `ValidationError` from a previous validation:

```python
from pydantic import BaseModel, ValidationError
from pydantic_ai_errors import format_pydantic_error


class Config(BaseModel):
    name: str


json_string = '{"name": 123}'

try:
    Config.model_validate_json(json_string)
except ValidationError as e:
    formatted = format_pydantic_error(e, json_string, filename="config.json")
    print(formatted)
```

### Create a Reusable Validator

```python
from pydantic import BaseModel, Field
from pydantic_ai_errors import create_validator


class Config(BaseModel):
    port: int = Field(ge=1, le=65535)
    host: str


validate_config = create_validator(Config, filename="config.json", colors=True)

result = validate_config(json_string)
if not result.success:
    print(result.formatted)
    exit(1)

# result.data is typed as Config
print(f"Server running on {result.data.host}:{result.data.port}")
```

## API

### `parse_json(json_string, model, **options)`

Parse and validate JSON against a Pydantic model.

**Parameters:**
- `json_string: str` — The JSON string to parse and validate
- `model: type[BaseModel]` — The Pydantic model to validate against
- `filename: str = "input.json"` — Filename to display in error locations
- `colors: bool = True` — Enable ANSI colors
- `context_lines: int = 4` — Number of context lines before/after error
- `throw: bool = False` — Raise exception instead of returning failure

**Returns:** `ValidationSuccess[T] | ValidationFailure`

### `format_pydantic_error(error, json_string, **options)`

Format an existing `ValidationError` with source context.

**Parameters:**
- `error: ValidationError` — The Pydantic error to format
- `json_string: str` — The original JSON string
- `filename: str = "input.json"` — Filename to display
- `colors: bool = True` — Enable ANSI colors
- `context_lines: int = 4` — Number of context lines

**Returns:** `str`

### `create_validator(model, **default_options)`

Create a reusable validator function.

**Returns:** `Callable[[str], ValidationResult[T]]`

### Diagnostic Type

For programmatic access to error details:

```python
@dataclass
class Diagnostic:
    code: str           # e.g., 'PYD001'
    severity: DiagnosticSeverity
    message: str        # e.g., 'type mismatch for field `user.age`'
    path: tuple[str | int, ...]  # e.g., ('user', 'age')
    span: SourceSpan | None      # Source location info
    help: str | None    # Actionable suggestion
    expected: str | None  # Expected type/value
    received: str | None  # Actual type/value
```

## Examples

Run the included example:

```bash
cd python
pip install -e ".[dev]"
python examples/01_basic.py
```

## License

Apache-2.0
