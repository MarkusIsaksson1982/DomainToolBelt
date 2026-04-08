from __future__ import annotations

import re
from typing import Any, Mapping

from domaintoolbelt.core.types import RetryStrategy, ToolResult, ValidationResult
from domaintoolbelt.rag.citations import extract_citations


class ValidationHub:
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
        candidate_tools: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        config = pack.config.validation
        max_retries = config.max_retries
        retry_strategy = config.retry_strategy
        payload = dict(arguments or {})
        available_tools = [tool_name]
        available_tools.extend(name for name in candidate_tools if name and name != tool_name)

        last_error = "Validation failed."
        current_tool = tool_name

        for attempt in range(max_retries + 1):
            if retry_strategy == RetryStrategy.RETOOL and attempt < len(available_tools):
                current_tool = available_tools[attempt]

            raw_output = await pack.run_tool(current_tool, instruction, payload)
            structured = self._coerce_tool_result(raw_output)
            citations = structured.citations or extract_citations(structured.content)

            tool_result: ValidationResult = pack.validate_step(current_tool, structured.content)
            fidelity_issues = self._check_fidelity(pack, structured.content, citations)

            combined_issues = list(structured.issues) + list(tool_result.issues) + fidelity_issues
            if tool_result.ok and not combined_issues:
                return {
                    "tool_name": current_tool,
                    "output": structured.content,
                    "citations": citations,
                    "issues": (),
                    "metadata": dict(structured.metadata),
                    "attempts": attempt + 1,
                }

            last_error = "; ".join(combined_issues) or "Validation failed."
            payload["retry_constraints"] = last_error
            instruction = (
                f"{instruction}\n\n"
                f"# Retry constraints\n"
                f"Fix only these issues and preserve grounded content: {last_error}"
            )

            if retry_strategy == RetryStrategy.ABORT:
                break

        raise ValueError(f"{current_tool} failed validation after retries: {last_error}")

    def audit_final(self, pack: Any, synthesis: str, citations: tuple[str, ...] = ()) -> ValidationResult:
        output_citations = extract_citations(synthesis)
        effective_citations = output_citations or citations
        issues = self._check_fidelity(pack, synthesis, effective_citations)
        pack_result = pack.fidelity_audit(synthesis, effective_citations)
        combined = tuple(issues) + tuple(pack_result.issues)
        return ValidationResult(ok=not combined, issues=combined)

    @staticmethod
    def _coerce_tool_result(output: Any) -> ToolResult:
        if isinstance(output, ToolResult):
            return output
        if isinstance(output, Mapping):
            citations = output.get("citations", ())
            issues = output.get("issues", ())
            metadata = output.get("metadata", {})
            return ToolResult(
                content=output,
                citations=tuple(str(item) for item in citations) if isinstance(citations, (list, tuple)) else (),
                issues=tuple(str(item) for item in issues) if isinstance(issues, (list, tuple)) else (),
                metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
            )
        return ToolResult(content=output)

    @staticmethod
    def _flatten_output(output: Any) -> str:
        if isinstance(output, str):
            return output
        if isinstance(output, Mapping):
            return " ".join(ValidationHub._flatten_output(value) for value in output.values())
        if isinstance(output, (list, tuple, set)):
            return " ".join(ValidationHub._flatten_output(value) for value in output)
        return str(output)
