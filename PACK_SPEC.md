# Pack Spec

Each DomainToolBelt pack should provide:

- A `DomainConfig` with a unique `key`, fidelity policy, and tool definitions.
- Async tool implementations that return grounded content and citations.
- `validate_step` and `fidelity_audit` methods tuned to the domain.
- Prompt files for planning, tool selection, and final synthesis.
- `tradition_flags` or equivalent guardrail metadata that clarifies scope and interpretive boundaries.

Recommended layout:

```text
my_pack/
  __init__.py
  config.py
  mcp_tools.py
  truth_policy.py
  validators.py
  prompts/
    create_action_plan.md
    intent_disambiguation.md
    supervisor.md
    tool_instruction.md
    tool_selection.md
    write_final_answer.md
```

Minimum contract:

1. Expose a pack class that satisfies `domaintoolbelt.domain_packs.base.DomainPack`.
2. Keep at least one authoritative tool in `config.tools`.
3. Make citations explicit enough for `fidelity_audit` to enforce.
4. Add at least one test covering pack discovery or pack validation behavior.

Start from `domaintoolbelt/domain_packs/_template_pack/` and keep the first version deterministic before adding provider-backed behavior.

Humanities packs such as `philosophy_pack` should declare school or era metadata in `tradition_flags`, prefer `FidelityMode.GROUNDED`, and keep their first corpus public-domain and citation-heavy.
