from __future__ import annotations

import re
from typing import Any, Mapping

from domaintoolbelt.core.types import ValidationResult
from domaintoolbelt.rag.citations import extract_citations


class ValidationHub:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def _check_fidelity(
        self,
        pack: Any,
        output: Any,
        citations: tuple[str, ...],
    ) -> list[str]:
        policy = pack.config.fidelity
        issues: list[str] = []
        flattened = self._flatten_output(output)

        if policy.require_citations and not citations:
            issues.append("Missing citations required by the Domain Pack.")

        if not policy.allow_unverified_paraphrase:
            if re.search(r"\b(i think|maybe|perhaps|probably)\b", flattened, flags=re.IGNORECASE):
                issues.append("Unverified paraphrase/speculation detected.")

        for pattern in policy.forbidden_patterns:
            if re.search(pattern, flattened, flags=re.IGNORECASE):
                issues.append(f"Forbidden pattern matched: {pattern}")

        return issues

    async def run_with_validation(
        self,
        pack: Any,
        tool_name: str,
        instruction: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error = "Validation failed."
        payload = arguments or {}

        for _attempt in range(self.max_retries + 1):
            output = await pack.run_tool(tool_name, instruction, payload)
            citations = extract_citations(output)

            tool_result: ValidationResult = pack.validate_step(tool_name, output)
            fidelity_issues = self._check_fidelity(pack, output, citations)

            if tool_result.ok and not fidelity_issues:
                return {
                    "tool_name": tool_name,
                    "output": output,
                    "citations": citations,
                    "issues": (),
                }

            issues = list(tool_result.issues) + fidelity_issues
            last_error = "; ".join(issues)
            payload = dict(payload)
            payload["retry_constraints"] = last_error
            instruction = (
                f"{instruction}\n\n"
                f"# Retry constraints\n"
                f"Fix only these issues and preserve grounded content: {last_error}"
            )

        raise ValueError(f"{tool_name} failed validation after retries: {last_error}")

    def audit_final(self, pack: Any, synthesis: str, citations: tuple[str, ...] = ()) -> ValidationResult:
        output_citations = extract_citations(synthesis)
        issues = self._check_fidelity(pack, synthesis, output_citations)
        pack_result = pack.fidelity_audit(synthesis, output_citations or citations)
        combined = tuple(issues) + tuple(pack_result.issues)
        return ValidationResult(ok=not combined, issues=combined)

    @staticmethod
    def _flatten_output(output: Any) -> str:
        if isinstance(output, str):
            return output
        if isinstance(output, Mapping):
            return " ".join(ValidationHub._flatten_output(value) for value in output.values())
        if isinstance(output, (list, tuple, set)):
            return " ".join(ValidationHub._flatten_output(value) for value in output)
        return str(output)
