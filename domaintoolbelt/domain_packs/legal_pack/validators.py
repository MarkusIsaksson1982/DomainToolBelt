from __future__ import annotations

import re
from typing import Any, Mapping

from domaintoolbelt.core.types import ValidationResult


_LEGAL_CITATION_RE = re.compile(r"^(GDPR Art\. \d+|GDPR Recital \d+)$")


def validate_legal_output(tool_name: str, output: Any) -> ValidationResult:
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
        if not _LEGAL_CITATION_RE.match(str(citation))
    ]
    if invalid:
        return ValidationResult(
            ok=False,
            issues=(f"Tool output contains invalid legal citations: {', '.join(invalid)}",),
        )
    return ValidationResult(ok=True)
