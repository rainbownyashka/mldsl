# TODO (MLDSL Compiler)

Format: `id | task | priority | owner | needs_user_test | state | links`

- COMP-001 | Keep parser/output aligned with mod page-aware print expectations | P0 | agent | yes | in_progress | docs/CROSS_PROJECT_INDEX.md
- COMP-002 | Add donor-tier summary in compile output using shared id rules | P1 | agent | yes | open | donaterequire integration
- COMP-003 | Add strict schema validation for emitted plan.json | P1 | agent | no | open | tests/
- COMP-004 | Keep generated docs/aliases deterministic in CI | P1 | agent | no | in_progress | .github/workflows/ci.yml
- COMP-005 | Add docs scope guardrail to prevent mod/site doc drift | P1 | agent | no | done | tools/check_docs_scope.py
