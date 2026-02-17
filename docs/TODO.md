# TODO (MLDSL Compiler)

Format: `id | task | priority | owner | needs_user_test | state | links`

- COMP-001 | Keep parser/output aligned with mod page-aware print expectations | P0 | agent | yes | in_progress | docs/CROSS_PROJECT_INDEX.md
- COMP-002 | Add donor-tier summary in compile output using shared id rules | P1 | agent | yes | open | donaterequire integration
- COMP-003 | Add strict schema validation for emitted plan.json | P1 | agent | no | open | tests/
- COMP-004 | Keep generated docs/aliases deterministic in CI | P1 | agent | no | in_progress | .github/workflows/ci.yml
- COMP-005 | Add docs scope guardrail to prevent mod/site doc drift | P1 | agent | no | done | tools/check_docs_scope.py
- COMP-006 | Lock plan/export compatibility test vectors for modern runtime-core adapters (1.16.5/1.20/1.21) | P0 | agent | yes | open | docs/CROSS_PROJECT_INDEX.md
- COMP-007 | Add regression test for action resolver fallback precedence (`sign1+sign2` must dominate `sign1` chest-based fallback) | P1 | agent | no | done | tests/test_exportcode_contract.py
- COMP-008 | Add regression test for empty sign diagnostics (`sign1/sign2/gui/menu` all empty -> explicit warning) | P1 | agent | no | done | tests/test_exportcode_contract.py
- COMP-009 | Clarify chest-autopick warning by logging alias transition (`from module.alias -> to module.alias`) + regression test | P1 | agent | no | done | mldsl_exportcode.py, tests/test_exportcode_contract.py
- COMP-010 | Preserve variable tokens in export arg reconstruction (`TEXT`/`APPLE`/mixed modes), avoid forced stringification | P0 | agent | no | done | mldsl_exportcode.py, tests/test_exportcode_contract.py
- COMP-011 | Preserve special apple location tokens (`LOC_NAME`) as raw args (no text quoting/book coercion) | P0 | agent | no | done | mldsl_exportcode.py, tests/test_exportcode_contract.py
- COMP-012 | Normalize APPLE constants to `apple.<TOKEN>` while preserving already-prefixed values | P0 | agent | no | done | mldsl_exportcode.py, tests/test_exportcode_contract.py
- COMP-013 | Align `select.ifplayer/ifmob/ifentity` selector resolution with `if_player` naming and remove mob/entity ambiguity in same-leaf selectors | P0 | agent | no | done | mldsl_compile.py
- COMP-014 | Render `Выбрать объект` as `select.*` in exportcode translator (with `ifplayer/ifmob/ifentity` domain mapping) | P0 | agent | no | done | mldsl_exportcode.py, tests/test_exportcode_contract.py
- COMP-015 | Make `mldsl exportcode` default api_aliases path independent from current working directory | P0 | agent | no | done | mldsl_cli.py
- COMP-016 | Export world events (`Событие мира`/gold block) as `event(...)` instead of fallback `row(...)` | P0 | agent | no | done | mldsl_exportcode.py, tests/test_exportcode_contract.py
- COMP-017 | Ignore technical `minecraft:air` placeholders during exportcode row call rendering | P0 | agent | no | done | mldsl_exportcode.py, tests/test_exportcode_contract.py
- COMP-018 | Add assignment sugar (`+=`, `-=`, `*=`, `/=`) in compiler | P0 | agent | no | done | mldsl_compile.py
- COMP-019 | Treat bare identifiers in TEXT params as variable refs by default (`var(...)`) | P0 | agent | yes | done | mldsl_compile.py
- COMP-020 | Compatibility shim for `if_value.переменная_существует(var)` -> mirror to `var2` | P1 | agent | yes | done | mldsl_compile.py
- COMP-021 | Deduplicate mirrored params in api_aliases for `Если переменная | Переменная существует` (remove synthetic `var2`) | P0 | agent | yes | done | tools/build_api_aliases.py
- COMP-022 | Stabilize fallback arg-slot detection in `extract_regallactions_args.py` using row-aligned bounds + nearest-lower-first fallback | P0 | agent | yes | done | extract_regallactions_args.py
- COMP-023 | Deduplicate mirrored params in api_aliases for conditional-object `Переменная существует` (`Игрок/Моб/Сущность по условию`) | P0 | agent | yes | done | tools/build_api_aliases.py
- COMP-024 | Canonicalize conditional select actions in api_aliases to `select.ifplayer_* / ifmob_* / ifentity_*` with legacy alias bridge | P0 | agent | yes | done | tools/build_api_aliases.py
- COMP-025 | Add `meta.paramSource` (`raw|normalized`) to api_aliases specs and show source in helper hover footer | P1 | agent | yes | done | tools/build_api_aliases.py, local.mldsl-helper extension.js
- COMP-026 | Add regression tests for var-exists dedup across `if_value` + `select.if*` and negative control | P0 | agent | no | done | tests/test_api_aliases_dedup.py
- COMP-027 | Add compiler regression tests for select-sugar bridge (`select.if_player.*`) and assignment sugar (`+= -= *= /=`) | P1 | agent | no | open | mldsl_compile.py, tests/
