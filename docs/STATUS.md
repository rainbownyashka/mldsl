# STATUS (MLDSL Compiler)

## Current release baseline
- CLI: `mldsl_cli.py` active entrypoint
- Build pipeline: `tools/pipeline.py`

## Verified features
- exportcode -> mldsl conversion path
- mldsl -> plan compile path
- build-all pipeline with generated docs/aliases
- exportcode action resolver safety fix:
  - `sign1`-only fallback is now used only when no `sign1+sign2/gui/menu` candidates were found,
  - prevents false remap like `Если игрок | Имеет право` -> `Если игрок | Режим игрока` from chest-score override.
- exportcode empty-sign diagnostics:
  - if `sign1/sign2/gui/menu` are all empty after normalization, resolver now emits explicit "пустая табличка" warning
    instead of generic `api_aliases` mismatch.
- exportcode chest-autopick diagnostics:
  - resolver now reports `from=<module.alias> -> to=<module.alias>` when chest scoring switches candidate,
    instead of ambiguous `sign1|sign2 -> sign1|sign2` logs.
- exportcode variable passthrough hardening:
  - variable-like values are no longer stringified in `TEXT`/`NUMBER`/`LOCATION` and legacy `APPLE` modes,
  - `magma_cream` variable markers stay variable tokens,
  - existing `var(...)`/`var_save(...)`/`arr(...)`/`arr_save(...)` expressions are preserved as-is.
  - legacy `APPLE` mode maps bare constants to `apple.<TOKEN>` (e.g. `LOC_NAME` -> `apple.LOC_NAME`) and keeps `apple.<...>` values as-is.
- select selector bridge hardening:
  - `select.ifplayer.<leaf>` now resolves through `if_player` aliases/menus (e.g. `держит`, `переменная_равна`),
  - `select.ifmob.<leaf>` and `select.ifentity.<leaf>` now resolve deterministically by strict `sign2` domain (`Моб по условию` vs `Сущность по условию`),
  - removes previous ambiguity/`unnamed_*` workaround requirement for common condition selectors.
- exportcode translator select rendering:
  - when source action is `Выбрать объект`, translator now emits `select.*` syntax instead of `misc.*`,
  - conditional domains are rendered as `select.ifplayer|ifmob|ifentity.<selector>(...)` based on sign2 (`* по условию`).
- exportcode CLI path resolution hardening:
  - `mldsl exportcode` now resolves default `api_aliases.json` via `mldsl_paths.api_aliases_path()`,
  - no longer depends on current working directory (`./out/api_aliases.json`) and avoids false "api_aliases.json not found" in repo/mod folders.
- world-event row header fix:
  - exportcode rows with `sign1~"Событие ..."` (including `minecraft:gold_block` / `Событие мира`) now emit `event(...)` header,
  - prevents wrong `row(...)` output and empty/invalid plan compilation for world-event modules.
- exportcode AIR-placeholder fix:
  - technical `minecraft:air` blocks inside row geometry are now skipped during call rendering,
  - prevents fake empty action lines (e.g. extra `if_player.сообщение_равно()`) caused by runtime AIR markers.
- assignment sugar expansion:
  - compiler now supports `+=`, `-=`, `*=`, `/=` in addition to `=`,
  - augmented forms are compiled as numeric expressions over current variable value.
- text-slot variable sugar:
  - bare identifiers in `TEXT` params are now treated as `var(...)`,
  - literal text should be quoted or wrapped as `text(...)`.
- `if_value.переменная_существует` compatibility sugar:
  - when only `var` is provided, compiler mirrors it into `var2`,
  - reduces false 2-arg friction for one-variable existence checks.
- api-aliases parameter dedup for variable-existence check:
  - `tools/build_api_aliases.py` now normalizes duplicated mirrored variable markers for
    `Если переменная | Переменная существует`,
  - generated `api_aliases.json` keeps a single canonical `var` param (slot 13) instead of synthetic `var2`.
- regallactions arg-slot fallback stabilization:
  - `extract_regallactions_args.py` now constrains neighbor-slot search to inferred row-aligned bounds from real slot data,
  - fallback now picks a single direction by nearest bound (`min` side -> down only, `max` side -> up only),
  - reduces off-page synthetic picks for sparse/partial chest snapshots.
- api-aliases dedup for conditional-object variable-exists actions:
  - `tools/build_api_aliases.py` now normalizes mirrored VARIABLE markers for
    `Игрок/Моб/Сущность по условию -> Переменная существует`,
  - generated `api_aliases.json` keeps a single canonical `var` param (slot 13) for these entries,
    so hover/completion no longer shows synthetic `var2` there.
- canonical `select.if_*` naming in api aliases:
  - `tools/build_api_aliases.py` now canonicalizes conditional object selectors into `select` module keys:
    `ifplayer_*`, `ifmob_*`, `ifentity_*`,
  - legacy aliases are preserved for completion compatibility (`player_*`/`unnamed_*` bridges in aliases),
  - prevents leakage of conditional `select` actions into `misc.*` for var-exists selectors.
- semantic param normalization source tagging:
  - `tools/build_api_aliases.py` now writes `meta.paramSource` for each action spec (`raw|normalized`),
  - `local.mldsl-helper` hover shows this source as a non-intrusive bottom line.
- regression test coverage for var-exists dedup:
  - added `tests/test_api_aliases_dedup.py` with fixture `tests/fixtures/actions_catalog_var_exists.json`,
  - covers `if_value` and `select.ifplayer/ifmob/ifentity` one-variable expectations + negative control.
- exportcode resolver/diagnostic regression coverage:
  - added contract tests in `tests/test_exportcode_contract.py` for strict resolver precedence
    (`sign1+sign2` must win over same-`sign1` fallback) and explicit empty-sign warning path,
  - validates behavior around chest-based action picking and unknown-sign diagnostics.
- premium ai-coder backend routing:
  - `tools/_premium/ai_coder.py` adds `cerebras:<model>` route through OpenAI-compatible XML tool loop,
  - Cerebras SDK import is now optional-safe and errors explicitly only when this backend is requested.

## Known regressions
- Catalog drift risk when source exports are stale.
- Runtime assumptions may diverge if mod changes plan parser semantics.

## Last user-tested
- 2026-02-11: integrated workflow with mod export/compile path used in practice.
- 2026-02-12: mod-side modern runtime-core migration started (`fabric1165/fabric120/fabric121/forge1165` bootstrap targets).

## Notes
- Compiler-only SoT.
- Keep export/plan semantics stable while modern mod adapters are replacing bootstrap `UNIMPLEMENTED_PLATFORM_OPERATION` paths with full publish/parser/printer logic.
