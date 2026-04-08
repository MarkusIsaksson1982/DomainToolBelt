from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PartnerReviewDecision:
    required: bool
    reason: str = ""


class PartnerReviewGate:
    def requires_review(self, trigger_text: str, triggers: tuple[str, ...]) -> bool:
        lowered = trigger_text.lower()
        return any(trigger.lower() in lowered for trigger in triggers)

    def review_decision(self, trigger_text: str, triggers: tuple[str, ...]) -> PartnerReviewDecision:
        if self.requires_review(trigger_text, triggers):
            return PartnerReviewDecision(
                required=True,
                reason="One of the configured partner review triggers matched the latest output.",
            )
        return PartnerReviewDecision(required=False)
