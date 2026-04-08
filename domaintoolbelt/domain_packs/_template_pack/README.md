# Template Pack

Copy this directory to create a new community pack.

Required pieces:
- `config.py` with a `DomainConfig`
- async tool implementations
- `validate_step` and `fidelity_audit`
- prompt files for planning, selection, and synthesis

Recommended steps:
1. Replace the placeholder fidelity policy with domain rules.
2. Mark authoritative tools explicitly.
3. Keep the first version deterministic so the stdlib test path stays easy to run.
