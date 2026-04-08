# DomainToolBelt

DomainToolBelt is a starter implementation of a domain-agnostic, fidelity-aware interpretation framework. It packages the core orchestration loop, safe tool selection, validation, checkpoints, resume support, grounding, memory, structured trace logging, a minimal MCP workflow surface, optional LLM provider adapters, and reference domain packs.

## What is initialized

- Typed core contracts in `domaintoolbelt/core/types.py`
- A workflow kernel with planning, guardrails, parallel-ready execution, checkpoints, validation, synthesis, grounding, and memory
- A pack contract in `domaintoolbelt/domain_packs/base.py`
- Reference `bible_pack`, `legal_pack`, and `philosophy_pack` implementations
- Dynamic pack discovery plus `_template_pack` for community contributions
- Optional prompt-backed planner, synthesizer, and tool reranking through `domaintoolbelt/llm/`
- Optional structured-output planning/synthesis with graceful fallback
- Structured trace logging plus checkpoint-based resume
- An MCP CLI entry point exposed as `domaintoolbelt-mcp`
- A CLI entry point exposed as `domaintoolbelt`
- A stdlib-only test suite

## Quickstart

```bash
python -m unittest discover -s tests -v
python -m domaintoolbelt.cli --query "What does Romans 8 say about adoption?"
python -m domaintoolbelt.cli --domain legal_pack --query "What does the GDPR say about access requests?"
python -m domaintoolbelt.cli --domain philosophy_pack --query "What do philosophers say about knowledge?"
python -m domaintoolbelt.cli --resume <session_id> --state-dir .domaintoolbelt
python -m domaintoolbelt.cli --query "What does Romans 8 say about adoption?" --trace --ui rich
python -m domaintoolbelt.mcp.cli --domain bible_pack
```

## Repository layout

```text
domaintoolbelt/
  core/
  llm/
  domain_packs/
    _template_pack/
    bible_pack/
    legal_pack/
    philosophy_pack/
  rag/
  observability/
  mcp/
  ui/tui/
tests/
```

## Notes

- The reference packs are intentionally lightweight and deterministic so the starter repo works without external model or vector-store dependencies.
- Optional LLM adapters live behind lazy imports; the default test path remains stdlib-only.
- Optional Rich/Textual dependencies are exposed through the `tui` extra.
- `PACK_SPEC.md` describes the contract for creating a new domain pack from `_template_pack`.
