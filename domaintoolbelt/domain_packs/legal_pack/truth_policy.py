from domaintoolbelt.core.types import FidelityMode, FidelityPolicy


LEGAL_FIDELITY_POLICY = FidelityPolicy(
    mode=FidelityMode.STRICT,
    require_citations=True,
    strict_verbatim_only=True,
    allow_unverified_paraphrase=False,
    allowed_source_scopes=("statute", "regulation"),
    forbidden_patterns=(r"\bi think\b", r"\bprobably\b", r"\bshould\b"),
    final_checks=("citations", "scope", "jurisdiction"),
)
