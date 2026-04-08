from domaintoolbelt.core.types import FidelityMode, FidelityPolicy


PHILOSOPHY_FIDELITY_POLICY = FidelityPolicy(
    mode=FidelityMode.GROUNDED,
    require_citations=True,
    strict_verbatim_only=False,
    allow_unverified_paraphrase=False,
    allowed_source_scopes=("primary", "commentary"),
    forbidden_patterns=(r"\bi think\b", r"\bobviously\b", r"\bclearly\b"),
    final_checks=("citations", "scope", "tradition"),
)
