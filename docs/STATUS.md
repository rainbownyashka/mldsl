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
- compiler regression coverage for select and sugar:
  - added `tests/test_compile_select_and_sugar.py` to lock `select.if_*` bridge behavior
    (including fail-fast ambiguity) and assignment/text sugar (`+=`, `-=`, `*=`, `/=`, TEXT var/literal split),
  - includes compatibility check for `if_value.переменная_существует(var=...)` var2 mirror behavior.
- select module compatibility hardening in compiler:
  - module aliases now resolve `select` to `select` (instead of legacy `misc`) by default,
  - fallback bridge is preserved (`select -> misc`) for older alias catalogs without `select` section,
  - default selection actions and selector leaf lookup now use `api["select"]` first with legacy fallback.
- seed input preservation for long-to-rebuild sources:
  - added `seed/inputs/regallactions_export.txt` and `seed/inputs/apples.txt` to keep critical raw sources in-repo,
  - path resolver now uses `seed/inputs/regallactions_export.txt` as fallback for default export source,
  - `apples_txt_path()` now checks `seed/inputs/apples.txt` before user-local docs path.
- translator architecture stabilization (generator SoT + contract checks):
  - root `build_api_aliases.py` is now a thin deprecated wrapper that delegates to `tools/build_api_aliases.py`,
  - `tools/build_api_aliases.py` now enforces contract invariants before writing output:
    - non-empty `select` module,
    - canonical select domains (`ifplayer_*`, `ifmob_*`, `ifentity_*`),
    - mandatory `meta.paramSource` in every action spec (`raw|normalized`),
  - added pipeline contract tests:
    - `tests/test_build_pipeline_contract.py` validates generator invariants and consistency
      between `mldsl build-all` and direct `tools/build_api_aliases.py` output.
- `vfunc` compile-time expansion (MVP):
  - compiler now supports top-level virtual functions:
    - `vfunc name(arg1, arg2="default")` + call as `name(...)` inside blocks,
  - calls are expanded into plain MLDSL lines before normal parse/compile stages,
  - fail-fast checks added for:
    - unknown/missing arguments,
    - recursion cycles / excessive expansion depth,
    - `func`/`vfunc` name conflicts.
  - coverage added in `tests/test_vfunc_expansion.py`.
- select compile-path regression fix after generator architecture stabilization:
  - select actions are now compiled through canonical `select` module in selection sugar path
    (instead of hardcoded `misc`),
  - added compatibility alias bridge for `select.if_*.сравнить_число_легко` ->
    `сравнить_число_облегчённо`,
  - fixes runtime compile error `Unknown action: misc.unnamed_*` in mixed canonical/legacy catalogs.
- call parsing hardening for compile stability:
  - multiline `module.func(...)` calls are now normalized before parse, so multiline argument formatting
    no longer degrades into unrelated assignment actions,
  - named args with empty value (e.g. `var=`) are now omitted from emitted args,
    so `plan.json` does not receive broken empty slots.
- VSCode helper select-domain completion fix:
  - extension `select` module alias now targets canonical `select` (not legacy `misc`),
  - `select.ifplayer.*`, `select.ifmob.*`, `select.ifentity.*` completion now resolves from `api_aliases.select`,
  - legacy `misc` remains as fallback only when `select` section is absent.

## Known regressions
- Catalog drift risk when source exports are stale.
- Runtime assumptions may diverge if mod changes plan parser semantics.

## Last user-tested
- 2026-02-11: integrated workflow with mod export/compile path used in practice.
- 2026-02-12: mod-side modern runtime-core migration started (`fabric1165/fabric120/fabric121/forge1165` bootstrap targets).

## Notes
- Compiler-only SoT.
- Keep export/plan semantics stable while modern mod adapters are replacing bootstrap `UNIMPLEMENTED_PLATFORM_OPERATION` paths with full publish/parser/printer logic.
