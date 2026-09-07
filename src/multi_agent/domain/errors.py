from __future__ import annotations

from typing import Any

from pydantic import ValidationError


class ContractError(ValueError):
    """Stable boundary error used before values enter repositories."""

    def __init__(self, code: str, field_path: str, message: str):
        super().__init__(f"{code} at {field_path}: {message}")
        self.code = code
        self.field_path = field_path
        self.message = message


def format_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Return validation errors without requiring callers to parse text."""

    formatted: list[dict[str, Any]] = []
    for error in exc.errors():
        path = ".".join(str(part) for part in error.get("loc", ())) or "$"
        formatted.append(
            {
                "code": str(error.get("type", "validation_error")),
                "field_path": path,
                "message": str(error.get("msg", "")),
            }
        )
    return formatted
