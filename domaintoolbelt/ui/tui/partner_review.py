from __future__ import annotations


class PartnerReviewGate:
    def requires_review(self, trigger_text: str, triggers: tuple[str, ...]) -> bool:
        lowered = trigger_text.lower()
        return any(trigger.lower() in lowered for trigger in triggers)
