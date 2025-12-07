"""
Example usage of pydantic-ai-errors
"""

from pydantic import BaseModel, Field

from pydantic_ai_errors import parse_json


class Address(BaseModel):
    street: str = Field(min_length=5)
    zipcode: str = Field(min_length=5, max_length=5)


class User(BaseModel):
    name: str = Field(min_length=2)
    age: int = Field(ge=18)
    email: str = Field(min_length=5)
    address: Address


class Root(BaseModel):
    user: User


# Invalid JSON input
json_input = """{
  "user": {
    "name": "",
    "age": "sixteen",
    "email": "not-an-email",
    "address": {
      "street": "123",
      "zipcode": "12"
    }
  }
}"""


def main() -> None:
    print("Validating JSON input...\n")
    print("Input:")
    print(json_input)
    print("\n" + "=" * 60 + "\n")
    print("Validation errors:\n")

    result = parse_json(
        json_input,
        Root,
        filename="input.json",
        context_lines=4,
        colors=True,
    )

    if not result.success:
        print(result.formatted)


if __name__ == "__main__":
    main()
