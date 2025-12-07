"""
Example: Compact mode and custom error messages

This example demonstrates:
1. Compact mode - all errors shown in a single error window
2. Custom error messages - override default messages per field
"""

from pydantic import BaseModel, Field

from pydantic_ai_errors import ValidationFailure, parse_json


class User(BaseModel):
    name: str = Field(min_length=2)
    age: int = Field(ge=18)
    email: str = Field(min_length=5)


# Invalid JSON input with multiple errors
json_input = """{
  "name": "",
  "age": "sixteen",
  "email": "x"
}"""


def demo_compact_mode() -> None:
    """Demonstrate compact mode - all errors in one window."""
    print("=" * 60)
    print("COMPACT MODE")
    print("=" * 60)
    print("\nWith compact=True, all errors are shown in a single window:\n")

    result = parse_json(
        json_input,
        User,
        filename="user.json",
        compact=True,
        colors=True,
    )

    if isinstance(result, ValidationFailure):
        print(result.formatted)


def demo_non_compact_mode() -> None:
    """Demonstrate non-compact mode (default) - separate windows per error."""
    print("\n" + "=" * 60)
    print("NON-COMPACT MODE (default)")
    print("=" * 60)
    print("\nWith compact=False, each error has its own window:\n")

    result = parse_json(
        json_input,
        User,
        filename="user.json",
        compact=False,
        colors=True,
    )

    if isinstance(result, ValidationFailure):
        print(result.formatted)


def demo_custom_messages() -> None:
    """Demonstrate custom error messages."""
    print("\n" + "=" * 60)
    print("CUSTOM ERROR MESSAGES")
    print("=" * 60)
    print("\nCustom messages can be provided per field path:\n")

    result = parse_json(
        json_input,
        User,
        filename="user.json",
        compact=True,
        colors=True,
        custom_messages={
            ("name",): "Username must be at least 2 characters long",
            ("age",): "Please enter your age as a number (must be 18+)",
            ("email",): "A valid email address is required",
        },
    )

    if isinstance(result, ValidationFailure):
        print(result.formatted)


def main() -> None:
    print("Input JSON:")
    print(json_input)

    demo_compact_mode()
    demo_non_compact_mode()
    demo_custom_messages()


if __name__ == "__main__":
    main()
