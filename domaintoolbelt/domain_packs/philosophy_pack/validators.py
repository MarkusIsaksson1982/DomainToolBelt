from __future__ import annotations

import re
from typing import Any, Mapping

from domaintoolbelt.core.types import ValidationResult


_PHILOSOPHY_CITATION_RE = re.compile(
    r"^(Plato, Republic \d+[a-z]|Aristotle, NE \d+[a-z]|Descartes, Meditations II|Kant, CPR A\d+/B\d+|Hume, Enquiry 4\.1)$"
)


def validate_philosophy_output(tool_name: str, output: Any) -> ValidationResult:
    if not isinstance(output, Mapping):
        return ValidationResult(ok=False, issues=("Tool output must be a mapping.",))

    summary = str(output.get("summary", "")).strip()
    citations = output.get("citations", ())
    if not summary:
        return ValidationResult(ok=False, issues=("Tool output summary is empty.",))
    if not citations:
        return ValidationResult(ok=False, issues=("Tool output is missing citations.",))

    invalid = [
        str(citation)
        for citation in citations
        if not _PHILOSOPHY_CITATION_RE.match(str(citation))
    ]
    if invalid:
        return ValidationResult(
            ok=False,
            issues=(f"Tool output contains invalid philosophy citations: {', '.join(invalid)}",),
        )
    return ValidationResult(ok=True)
