from __future__ import annotations

import re
from dataclasses import dataclass

from domaintoolbelt.core.types import FidelityMode, WorkflowContext


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


@dataclass
class GroundedClaim:
    claim_text: str
    source_id: str
    confidence: float
    is_grounded: bool
    grounding_error: str | None = None


@dataclass
class GroundingReport:
    claims: list[GroundedClaim]
    overall_confidence: float
    ungrounded_claims: list[str]

    @property
    def passed(self) -> bool:
        return not self.ungrounded_claims


class RAGGroundingLayer:
    def prepare_passages(self, ctx: WorkflowContext) -> list[dict[str, str]]:
        passages: list[dict[str, str]] = []
        for item in ctx.retrieved_context:
            passages.append(self._to_passage(item))
        for step in ctx.completed_steps:
            passages.append(self._to_passage(str(step.output)))
        return passages

    async def audit_synthesis(
        self,
        synthesis: str,
        retrieved_passages: list[dict[str, str]],
        fidelity_mode: FidelityMode,
        similarity_threshold: float = 0.2,
    ) -> GroundingReport:
        claims = self._extract_claims(synthesis)
        grounded_claims: list[GroundedClaim] = []

        for claim in claims:
            best_passage = None
            best_score = 0.0
            claim_tokens = _tokenize(claim)
            for passage in retrieved_passages:
                source_tokens = _tokenize(passage["text"])
                score = self._lexical_similarity(claim_tokens, source_tokens)
                if score > best_score:
                    best_score = score
                    best_passage = passage

            is_grounded = best_score >= similarity_threshold or fidelity_mode == FidelityMode.GUIDED
            if fidelity_mode == FidelityMode.STRICT and best_passage:
                is_grounded = self._verbatim_supported(claim, best_passage["text"])

            error = None
            if not is_grounded:
                error = f"Claim not sufficiently grounded (score={best_score:.2f})"

            grounded_claims.append(
                GroundedClaim(
                    claim_text=claim,
                    source_id=best_passage["id"] if best_passage else "",
                    confidence=best_score,
                    is_grounded=is_grounded,
                    grounding_error=error,
                )
            )

        ungrounded = [claim.claim_text for claim in grounded_claims if not claim.is_grounded]
        confidence = (
            sum(claim.confidence for claim in grounded_claims) / len(grounded_claims)
            if grounded_claims
            else 1.0
        )
        return GroundingReport(
            claims=grounded_claims,
            overall_confidence=confidence,
            ungrounded_claims=ungrounded,
        )

    @staticmethod
    def _extract_claims(synthesis: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"\[])|\n+", synthesis)
        claims = [part.strip() for part in parts if len(part.strip()) > 20]
        return claims or [synthesis.strip()]

    @staticmethod
    def _lexical_similarity(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    @staticmethod
    def _verbatim_supported(claim: str, source_text: str) -> bool:
        quoted = re.findall(r'"([^"]+)"', claim)
        if not quoted:
            return False
        return any(item in source_text for item in quoted)

    @staticmethod
    def _to_passage(text: str) -> dict[str, str]:
        match = re.search(r"\[([^\[\]]+)\]", text)
        source_id = match.group(1) if match else "context"
        return {"id": source_id, "text": text}
