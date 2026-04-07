from __future__ import annotations

from typing import Any, Mapping

from domaintoolbelt.core.types import ValidationResult


def validate_bible_output(tool_name: str, output: Any) -> ValidationResult:
    if not isinstance(output, Mapping):
        return ValidationResult(ok=False, issues=("Tool output must be a mapping.",))

    summary = str(output.get("summary", "")).strip()
    citations = output.get("citations", ())
    if not summary:
        return ValidationResult(ok=False, issues=("Tool output summary is empty.",))
    if not citations:
        return ValidationResult(ok=False, issues=("Tool output is missing citations.",))
    return ValidationResult(ok=True)
