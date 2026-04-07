from domaintoolbelt.core.types import FidelityMode, FidelityPolicy


BIBLE_FIDELITY_POLICY = FidelityPolicy(
    mode=FidelityMode.GROUNDED,
    require_citations=True,
    strict_verbatim_only=False,
    allow_unverified_paraphrase=False,
    allowed_source_scopes=("primary", "cross_reference"),
    forbidden_patterns=(r"\bmaybe\b", r"\bperhaps\b"),
    final_checks=("citations", "scope", "tradition"),
)
