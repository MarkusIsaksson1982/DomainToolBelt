# DomainToolBelt

DomainToolBelt is a starter implementation of the v0.2 engineering spec for a domain-agnostic, fidelity-aware interpretation framework. It packages the core orchestration loop, safe tool selection, validation, checkpoints, grounding, memory, a minimal MCP adapter, and a reference `bible_pack`.

## What is initialized

- Typed core contracts in `domaintoolbelt/core/types.py`
- A workflow kernel with planning, guardrails, parallel-ready execution, checkpoints, validation, synthesis, grounding, and memory
- A pack contract in `domaintoolbelt/domain_packs/base.py`
- A reference `bible_pack` with prompts, local tools, validators, and a fidelity policy
- A CLI entry point exposed as `domaintoolbelt`
- A stdlib-only test suite

## Quickstart

```bash
python -m unittest discover -s tests -v
python -m domaintoolbelt.cli --query "What does Romans 8 say about adoption?"
```

## Repository layout

```text
domaintoolbelt/
  core/
  domain_packs/
    bible_pack/
  rag/
  mcp/
  ui/tui/
tests/
```

## Notes

- The reference `bible_pack` is intentionally lightweight and deterministic so the starter repo works without external model or vector-store dependencies.
- The prompt file pattern, fidelity policy boundary, and pack-owned validators follow the v0.2 spec and are ready to be swapped to real domain tooling.
