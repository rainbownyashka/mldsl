# TODO (MLDSL Compiler)

Format: `id | task | priority | owner | needs_user_test | state | links`

- COMP-001 | Keep parser/output aligned with mod page-aware print expectations | P0 | agent | yes | in_progress | docs/CROSS_PROJECT_INDEX.md
- COMP-002 | Add donor-tier summary in compile output using shared id rules | P1 | agent | yes | open | donaterequire integration
- COMP-003 | Add strict schema validation for emitted plan.json | P1 | agent | no | open | tests/
- COMP-004 | Keep generated docs/aliases deterministic in CI | P1 | agent | no | in_progress | .github/workflows/ci.yml
- COMP-005 | Add docs scope guardrail to prevent mod/site doc drift | P1 | agent | no | done | tools/check_docs_scope.py
- COMP-006 | Lock plan/export compatibility test vectors for modern runtime-core adapters (1.16.5/1.20/1.21) | P0 | agent | yes | open | docs/CROSS_PROJECT_INDEX.md
- COMP-007 | Add regression test for action resolver fallback precedence (`sign1+sign2` must dominate `sign1` chest-based fallback) | P1 | agent | no | in_progress | mldsl_exportcode.py, tests/
- COMP-008 | Add regression test for empty sign diagnostics (`sign1/sign2/gui/menu` all empty -> explicit warning) | P1 | agent | no | in_progress | mldsl_exportcode.py, tests/
