# STATUS (MLDSL Compiler)

## Current release baseline
- CLI: `mldsl_cli.py` active entrypoint
- Build pipeline: `tools/pipeline.py`

## Verified features
- exportcode -> mldsl conversion path
- mldsl -> plan compile path
- compile-time required donate tier summary:
  - `mldsl compile` now computes minimum required tier from `donaterequire.txt` using alias->action-id mapping (`api_aliases.json` + `actions_catalog.json`),
  - emits stderr warning after compile: `[warn] required donate tier: <tier> (matched actions: N)`,
  - warning now also shows up to 5 matched action names from source (`detected: module.action, ...`),
  - if multiple tiers are matched, highest tier wins (e.g. `gamer + king` => `king`), no matches => `player`.
- vector/item runtime compatibility normalization:
  - compiler now rewrites `item(type=..., ...)` to positional form `item(..., ...)` for `VECTOR/ITEM/BLOCK` arguments,
  - avoids runtime printer cases where `type=` payload in vector slots was ignored and item was not placed into action slot.
- numeric unary-minus lowering fix:
  - constant negative literals in numeric expressions (e.g. `-1.483046211`) now compile directly to `num(-...)` via `var.set_value`,
  - compiler no longer emits redundant `set_product(..., num(-1))` for pure numeric unary-minus constants.
- numeric constant-folding in expression lowering:
  - pure numeric subexpressions are now folded before emission (e.g. `-(1+2)` -> `num(-3)`, `-(-3.5)` -> `num(3.5)`),
  - avoids temporary vars and intermediate arithmetic actions when result is compile-time constant.
- inline block normalization for parser robustness:
  - compiler now expands one-line scoped blocks (`if ... { a = 1 b += 2 }`) into multiline-equivalent statements before parse,
  - compact inline bodies are split reliably (semicolon-aware + assignment/call boundary fallback),
  - semantics now match explicit multiline blocks for conditional scopes.
- LOCATION runtime compatibility normalization:
  - compiler now rewrites `LOCATION` payloads into runtime-safe paper items:
    - `loc("x y z yaw pitch")` -> `item(minecraft:paper, name="x y z yaw pitch")`,
    - bare location literals in `LOCATION` params are normalized the same way,
  - explicit `item(type=..., ...)` in `LOCATION` now also normalizes to positional `item(..., ...)`.
- dynamic placeholder assignment target support:
  - assignment sugar now supports placeholder-based variable names in LHS, e.g.
    `__mn_row_%var(__mn_z)% += __mn_pix`,
  - such assignments are no longer silently dropped and compile into `var.set_*` actions.
- VSCode helper compiler selection priority fix:
  - when `mldsl.compilerPath` is explicitly set, extension now always uses that path first (py or exe),
  - prevents accidental fallback to installed `mldsl.exe` that previously overrode dev `mldsl_cli.py`.
- VSCode helper Python CLI invocation fix:
  - for `mldsl_cli.py`, extension now calls subcommand form `compile <file> [--plan ...]` (not legacy positional form),
  - fixes runtime error `invalid choice: '<plan-path>'` in `Compile To plan`.
- CLI legacy invocation compatibility:
  - `mldsl_cli.py` now accepts old extension arg order and rewrites it into modern subcommand mode,
  - supported legacy forms include `mldsl_cli.py --plan <plan> <input.mldsl>` and `mldsl_cli.py <input.mldsl>`,
  - prevents hard failures when editor still invokes pre-subcommand format.
- VSCode helper publish flow Python invocation fix:
  - `MLDSL: Publish Module` now also calls Python compiler in subcommand form
    `python mldsl_cli.py compile <file> --plan <plan.json>`,
  - removes legacy arg order bug that called CLI without `compile` and failed with argparse invalid choice.
- unresolved-line diagnostics hardening:
  - compiler now emits explicit unresolved-line warnings (`[warn] line N: нераспознанная строка ...`) when source lines are not parsed into actions,
  - strict mode is available via env `MLDSL_STRICT_UNKNOWN=1` and CLI flag `mldsl compile --strict-unknown` (fail-fast `ValueError`),
  - unknown call-like sugar is now gated by known function signatures to prevent silent acceptance of garbage calls.
- assignment parser hardening for `=` inside call text:
  - fixed false assignment detection when `=` appears inside quoted call arguments (e.g. `player.message("sum=...")`),
  - dynamic assignment fallback no longer triggers unless `=` is top-level,
  - prevents lines like `player.message("...pred=%var(x)%")` from being miscompiled into `var.set_value`.
- builtin interception guard for canonical calls:
  - `compile_builtin` now explicitly skips lines matching canonical `module.func(...)`,
  - prevents sugar parser from pre-empting normal action-call parsing and creating false assignment actions.
- assignment `loc(...)` runtime normalization:
  - in assignment sugar (`x = ...`), RHS `loc("...")` now normalizes to
    `item(minecraft:paper, name="...")` before `var.set_value`,
  - aligns assignment path with LOCATION-arg path and avoids runtime printing of literal `loc(...)` text.
- vector keyword alias support:
  - compiler now accepts `vector`, `vector2`, ... (also `vec`, `vektor`, `вектор`) for `VECTOR` params,
  - aliases are mapped to action param names from `api_aliases` (including legacy `arg/arg2` catalogs),
  - keeps backward compatibility with existing `arg/arg2` scripts while allowing clearer vector-style calls.
- VARIABLE item-wrapper compatibility:
  - compiler now accepts `item(...)` in `VARIABLE`-typed params with explicit stderr warning,
  - payload is passed through (with `item(type=...)` normalization) instead of hard-failing,
  - removes compile aborts for runtime patterns that intentionally place item payload into variable slots.
- strict named-key validation for action calls:
  - compiler now fails fast on unknown named keys (param/enum typos) instead of silently ignoring them,
  - error includes known params and enum names for the target action.
- ampersand formatting normalization:
  - unescaped `&` is normalized to `§` in text/item/location payloads where applicable,
  - escaped `\\&` is preserved as literal `&`.
- VSCode helper integrated MC `&` color preview:
  - main extension (`tools/mldsl-vscode/extension.js`) now includes in-editor `&` formatting preview for `mldsl`,
  - preview is scoped to quoted string segments and auto-stops at closing quote (no color bleed into tail text),
  - refresh triggers on visible editors, active editor switch, and document changes.
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
- exportcode select-alias disambiguation hardening:
  - translator alias picker now skips generic/category aliases (`deystviya`, `переменная`, `сущность_по_условию`, etc.) when choosing emitted call names,
  - scoped rendering for `Выбрать объект` now applies to both `misc` and canonical `select` modules, including no-arg actions,
  - fixes compile-time ambiguities in translated scripts (e.g. `select.действия()`, `select.сущность_по_условию(...)`, unscoped `select.сравнить_число_облегчённо(...)`).
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
- regallactions repeated-number lane expansion:
  - extractor now detects `Число(а)` marker lanes (>=3 consecutive NUMBER panes, >=7 markers total in row, with "ниже ⇩" hint)
    and expands argument slots into virtual 3+ empty rows below marker columns,
  - fixes `Установить (*)`/`Установить (+)`/`Установить (-)`/`Установить (÷)` losing multi-number inputs
    (restored up to 28 numeric operands in `api_aliases`).
- regallactions repeated-text lane expansion:
  - extractor now detects `Текст(ы)` marker lanes (>=7 markers in row, supports both "ниже ⇩" and "выше ⇧" lore variants)
    and expands virtual repeated TEXT slots into lower rows for `текст содержит`-style actions,
  - restored multi-text parameter extraction for `if_value.текст_содержит` and `select.if*.текст_содержит`
    (current source layout yields 22 TEXT params: base `text` + 21 repeated slots).
- regallactions repeated-item lane fallback selection:
  - extractor now detects `Предмет(ы)` marker lanes and validates 3 required empty rows under each lane column,
  - if one candidate marker row is blocked, parser now checks other rows/runs instead of using broken nearest-neighbor fallback,
  - fixed `Открыть меню` extraction to stable 27 item slots (`9..35`) plus title text slot (`49`).
- generalized repeated-lane parser for multi-slot glass markers:
  - lane expansion now uses unified mode-aware detector for `NUMBER`, `TEXT`, `ITEM`, `LOCATION`, `ARRAY`, `ANY`,
  - chooses best valid marker row by marker density and validates 3 empty rows per marker column,
  - prevents mixing broken lower marker rows with fallback slots and significantly increases recovered multi-slot args on 3+ marker test set.
- repeated-lane span-column expansion (including enum columns):
  - after lane recognition, extractor now inspects every column between first and last marker (not only marker columns),
  - for non-marker lane columns (including enum/item slots), extractor borrows nearest marker metadata and registers arg slots only when vertical empties are valid,
  - synthetic repeated-lane columns are added into args output, improving extraction for wide UIs with enum columns embedded inside repeated lanes.
- repeated-lane all-or-nothing empty-column validation:
  - repeated-lane extraction now commits lane columns only when vertical empties are valid under every lane column in the recognized span,
  - if any column in the span is blocked, lane expansion is rejected for that lane (no partial per-column registration).
- new argument mode `BLOCK` in action extractor:
  - glass markers whose display name contains `блок` (case-insensitive) are now parsed as mode `BLOCK`,
  - compiler wrapping supports `BLOCK` by emitting `item(...)` payloads for runtime compatibility.
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
- fill-region arg coercion fix:
  - compiler no longer force-wraps `Заполнить область` value into `item(...)` for ANY slot,
  - emitted plan keeps `slot(13)=var(...)`/raw mode-driven payloads and avoids `invalid item()` runtime side-effects.
- NUMBER placeholder guardrails:
  - `%selected%var`-style values in NUMBER slots are now recognized as variable tokens (`var(...)`),
  - placeholder arithmetic strings with `%...%` (e.g. `%selected%idx+1`) now fail fast with explicit guidance instead of unsafe `num(...)` wrapping.
- ANY slot variable auto-detection:
  - `%selected%var` and bare identifier tokens in `ANY` params are now auto-wrapped as `var(...)`,
  - keeps explicit wrappers as highest priority and reduces accidental raw-token emission.
- call-arg formula lowering:
  - numeric expressions inside call args for `NUMBER/TEXT/ANY` are now lowered into intermediate var actions
    before the target action call (e.g. `text2=%player%money + 5` -> `set_sum(...)` + `text2=var(tmp)`),
  - supports both spaced and compact forms (`a + 5` and `a+5`).
- item/block variable safety:
  - `ITEM/BLOCK` params no longer auto-coerce variable-like tokens into `item(var(...))`,
  - variable-like values are passed as `var(...)`, while concrete ids still become `item(...)`.
- assignment wrapper semantics fix:
  - assignment RHS wrapper calls (`item(...)`, `loc(...)`, `text(...)`, `num(...)`, etc.) are now treated as plain values,
  - they no longer trigger function-return sugar via `__mldsl_args/__mldsl_ret`.
- engineering workflow policy recorded:
  - compiler is the preferred place for smart logic and validation,
  - runtime printer/scanner should remain simple and cross-version portable.
- repeated-lane argument order hardening:
  - lane args are now emitted in strict row-major order after full all-column validation,
  - registration order is now stable by slot progression (`row1 cols -> row2 cols -> row3 cols`) to match server slot-order semantics.
- loop-control text quoting fix:
  - `game.start_loops(...)` / `game.stop_loops(...)` now normalize quoted TEXT literals to plain `text(...)` payloads without embedded quote chars,
  - prevents cycle-name items like `'mldsl_mnist_loop'` caused by preserved literal quotes.
- return flow-control note:
  - in current runtime semantics, `return` does not hard-stop remaining emitted actions in a function row by itself,
  - robust scripts must guard remaining body explicitly (e.g. `if_value(done < 1) { ... }`) instead of relying on early-return short-circuit.
- autosplit trampoline post-pass:
  - compiler now applies a final entries-level compaction pass that removes auto-generated helper funcs with body `call(__autosplit_row_*)` only,
  - call sites are rewritten to the final target helper, then redundant helper definitions are removed and newlines normalized.
- autosplit payload-budget correction:
  - autosplit split-point selection and loop thresholds now consistently use payload budget (`MAX_ACTIONS_PER_ROW - 1`) to account for row header slot,
  - prevents accidental `func` continuation rows that contained only `call(__autosplit_row_N)` because a 43-action payload spilled at emit stage.
- extracted-helper autosplit stabilization:
  - extracted nested helpers are no longer hard-failed when body exceeds payload budget,
  - compiler now applies the same call-chain autosplit strategy to extracted helpers (including nested extraction when needed).
- global TEXT literal quote normalization:
  - quoted TEXT literals are now emitted as `text(payload)` without embedded quote chars for all actions (not only loop-control),
  - quoted identifiers keep literal semantics (`"abc"` -> `text(abc)`, not `var(abc)`).
- autosplit temporary debug instrumentation:
  - compiler now supports opt-in verbose autosplit diagnostics via env `MLDSL_AUTOSPLIT_DEBUG=1`,
  - debug stream reports split-loop iterations, candidate counts, extracted helper sizes, and allocated `__autosplit_row_*` names.
- compile deep debug instrumentation (temporary):
  - compiler now supports stage/line-level tracing via env `MLDSL_COMPILE_DEEP_DEBUG=1`,
  - includes pipeline stage counters, per-line parse progress, flush-block start/end stats, and post-pass entry counts.
  - autosplit runaway guard added (`MLDSL_AUTOSPLIT_MAX_ITERS`, default `50000`) to fail fast on infinite split loops.
- autosplit no-progress loop fix:
  - fixed pathological extraction loop where nested-scope extraction could pick a 1-action body and rewrite without reducing action count,
  - extraction now requires at least 2 body actions and verifies strict progress (`len(actions_left)` must decrease),
  - compiler now fails fast with explicit `extraction made no progress` instead of spending 30s+ in helper-name churn.
- new parser mode `VECTOR`:
  - extractor now recognizes vector glass markers by either color `meta=9` or display name starting with `вектор`/`vector` (case-insensitive),
  - mode propagates into `actions_catalog` and `api_aliases` params as `VECTOR`,
  - vector-heavy actions (`скалярное/векторное/адамарово произведение`, `сумма/разница векторов`, etc.) now expose vector slots explicitly instead of fallback modes.
- VSCode helper select-domain completion fix:
  - extension `select` module alias now targets canonical `select` (not legacy `misc`),
  - `select.ifplayer.*`, `select.ifmob.*`, `select.ifentity.*` completion now resolves from `api_aliases.select`,
  - legacy `misc` remains as fallback only when `select` section is absent.
- VSCode helper compact completion detail for `select.*`:
  - completion right-side detail no longer shows long canonical alias variants (e.g. `ifplayer_sravnit_*`),
  - `select` entries now show compact signature (`select.(params)`) to reduce visual clutter.
- VSCode helper select completion detail simplification:
  - `select.*` completion detail no longer renders parameter lists on the right side,
  - right-side detail now shows only compact action context (`select` + menu label when available).
- VSCode helper api path root-selection fix:
  - when `mldsl.apiAliasesPath` is empty but `mldsl.compilerPath` is configured, helper now resolves
    `out/api_aliases.json` from compiler root first (repo dev root / legacy `tools/mldsl_compile.py` wrapper / CLI exe dir),
  - `%LOCALAPPDATA%\\MLDSL\\out\\api_aliases.json` is now a lower-priority fallback, preventing false production API pickup
    while editing scripts outside the compiler repo workspace.
- VSCode helper completion detail canonicalization:
  - right-side completion detail for action suggestions now shows only canonical function id (`funcName`),
  - removes duplicated module/signature/alias noise in completion list (e.g. `player.<...>` details).
- `multiselect` compile-time expansion (MVP):
  - added `multiselect ifplayer|ifmob|ifentity <counterVar> <threshold>` precompile block,
  - each weighted condition line supports `+ - * /` and `+= -= *= /=` suffixes,
  - expansion uses canonical `select.*` + `var.set_*` actions and appends final `сравнить_число_легко >= threshold`.
  - multiline condition calls inside `multiselect` are normalized before expansion
    (e.g. `select.ifplayer.держит(` with args on next lines).
  - weighted ops now target real var action signatures (`var` + `num`) to avoid incomplete `+/-/*//` plan args.
  - plan smoke-check practice: after compile-sugar changes, verify emitted `plan.json` slots against live API aliases.
- regallactions concat-text lane parser prototype:
  - `extract_regallactions_args.py` now supports `Объединить текст(ы)` lane pattern:
    `>=4` marker glasses + optional single gap + `>=4` marker glasses,
  - when each lane column has at least 3 empty slots below, those below-slots are expanded as arg slots,
  - optional single gap column now participates in vertical arg expansion (same as marker glass columns),
  - lane scan now tolerates omitted empty bottom rows in export by using virtual chest-bottom bounds for this action,
  - if any below-slot in lane is occupied, magic expansion is rejected fail-fast for that action (fallback parser path remains).
- concat-lane candidate filters generalized:
  - concat parser is no longer tied only to exact `sign2` value; it now checks multiple record text fields (`signs/gui/subitem`)
    with tolerant patterns (`объедин*текст*`, `concat*text*`, `=`),
  - includes structural fallback marker check (`TEXT` panes + `VARIABLE` pane) for alias/drift resilience.
- concat-lane shape rules widened:
  - lane matcher now accepts runs `>=3` (was `>=4`) with exactly one gap and total marker panes `>=8`,
  - supports `3+gap+5`, `4+gap+4`, `5+gap+3` patterns (gap at 4/5/6 positions in 1-based row terms),
  - marker panes now require recognized argument mode (`determine_mode(...) != None`) to avoid non-arg glass noise.
- concat-lane threshold relaxation:
  - minimum total marker panes in lane reduced from `8` to `7` for tolerant detection on sparse action layouts,
  - regression compare over current 494-record export showed no additional affected actions vs threshold `8` baseline.
- concat-lane double-gap support:
  - lane matcher now also supports `3+gap+1+gap+3` shape (e.g. slots 1-3,5,7-9 are marker panes; 4 and 6 are any items),
  - both gap columns are included into vertical arg expansion when lane validity checks pass.
  - full-catalog compare over current 494-record export showed no additional action count deltas vs previous matcher.
- parser regression coverage for concat-text lane:
  - added `tests/test_extract_regallactions_args_concat.py` for positive lane expansion and occupied-slot rejection.
- conditional negation (`NOT/не`) contract in compiler:
  - compiler now accepts `NOT`/`не` prefix for conditional action calls and emits `negated=true` in `plan.json` entries,
  - fail-fast validation added for non-conditional usage (`NOT player.*` and similar are rejected with explicit error),
  - added regression coverage in `tests/test_not_negation_plan_flag.py`.
- `if_value.<условие> { ... }` block-form parser fix:
  - compiler now recognizes block-form `if_value.*` conditions (previously only action-form `if_value.*(...)` worked reliably),
  - fixes missing `obsidian` condition rows and accidental unconditional execution of nested actions in emitted `plan.json`,
  - added regression coverage in `tests/test_compile_select_and_sugar.py` (`test_if_value_block_form_compiles_as_condition_scope`).
- dev/prod `data_root` split in path resolver:
  - `mldsl_paths.data_root()` now defaults to repo root in source checkout mode (dev),
  - production default remains `%LOCALAPPDATA%\\MLDSL` (with existing portable override behavior),
  - prevents accidental use of stale `%LOCALAPPDATA%\\MLDSL\\out\\api_aliases.json` during local development.
  - added regression coverage in `tests/test_mldsl_paths_data_root.py`.
- NUMBER-slot variable sugar in compiler:
  - bare identifiers in `NUMBER` params are now emitted as `var(...)` instead of `num(...)`,
  - fixes cases like `if_value.сравнить_число_легко(__set_z1, __set_z2, ...)` where runtime treated args as constants.
  - regression coverage added in `tests/test_compile_select_and_sugar.py` (`test_number_param_bare_identifier_wraps_to_var`).
- multiline-call normalization limit reserve:
  - added optional `MLDSL_NORMALIZED_CALL_LIMIT` guard for normalized multiline calls,
  - limit check now reserves one character budget for closing `}` (`limit-1`),
  - regression coverage added in `tests/test_compile_select_and_sugar.py` (`test_multiline_call_limit_reserves_closing_brace`).
- plan row auto-split action-budget fix:
  - compiler now enforces `43` actions per row budget during `plan.json` emission,
  - for long `event(...)` blocks, auto-split is emitted as call-chain equivalent:
    - event chunk: `42 actions + call(__autosplit_row_N)`,
    - continuation chunk(s): auto-generated `func __autosplit_row_N { ... }` in `plan` (`lapis_block` headers),
  - auto-generated helper func names are collision-safe against existing `func`/`vfunc` names,
  - closing scope `}` marker (`skip`) remains a normal action and participates in chunk budget.
  - regression coverage added in `tests/test_compile_select_and_sugar.py` (`test_row_limit_43_uses_call_and_helper_func`).
- compile-time warning for row auto-split:
  - compiler now emits existing-style stderr warning (`[warn] ...`) when a row is auto-split by `43`-action budget,
  - for event call-chain split, warning includes created helper call target (`call(__autosplit_row_N)`),
  - regression coverage added in `tests/test_compile_select_and_sugar.py` (`test_row_limit_autosplit_prints_warning_to_stderr`).
- semantics-first safe split policy for auto-row functions:
  - event auto-split now uses only safe top-level split points (no split inside open `{}` scopes),
  - when split point has active non-default selection, compiler inserts default single-target select before `call(...)`
    and prepends original selection in generated helper function,
  - if no safe top-level split point exists, compiler falls back to in-event `newline` split
    (preserves source action order and avoids compile abort on deeply nested scopes),
  - fallback is explicit via warning (`has no safe top-level split point; fallback to in-event newline split`).
  - regression coverage added in `tests/test_compile_select_and_sugar.py`
    (`test_row_limit_nested_single_if_fallback_to_newline_split`).
- continuation-row header enforcement:
  - when row wrap occurs (including fallback-wrapped helper funcs), compiler now injects a leading header block
    on each continuation row (`diamond_block`/`lapis_block`/`emerald_block` according to current scope),
  - removes invalid rows starting directly with action blocks after `newline`,
  - regression coverage added in `tests/test_compile_select_and_sugar.py`
    (`test_row_wrap_continuation_rows_keep_leading_header`).
- test harness isolation hardening:
  - fixed cross-test import contamination in `tests/test_api_aliases_dedup.py`
    (temporary `tools/` path injection is now reverted after module load),
  - added `pytest.ini` with `testpaths = tests` so default runs do not collect `archive/` legacy scripts as tests,
  - full suite now passes with default command: `python -m pytest -q`.
- row budget accounting fix for continuation headers:
  - row split counter now includes leading header block (`diamond/lapis/emerald`) in the same 43-slot budget,
  - continuation rows reset occupied counter to `1` after injected header instead of `0`,
  - fixes overflow where compiler emitted `43 actions + 1 header` (44 total) and runtime ran out of row space.
- fallback newline split nested-closure budget fix:
  - fallback row wrapping now tracks open `if` depth per emitted action and reserves row slots for runtime implicit closing pistons on newline boundaries,
  - prevents hidden overflow where compiler emitted `43` visible actions but runtime auto-appended closers (`}`) and exceeded physical row capacity,
  - verified on user case: `__set_cursor_x = __set_min_x` moved out of overflow row (split now happens earlier).
- strict autosplit scope-safety enforcement:
  - compiler no longer performs fallback row splitting inside open scopes (`if { ... }`) when safe top-level split points are absent,
  - instead it fails fast with explicit error:
    `cannot split inside open scopes... Refactor by extracting inner block into a helper func/vfunc`,
  - this prevents semantic drift where `skip`/server-implicit brace handling could move closures across physical rows.
- smart nested-scope extraction for autosplit:
  - when no safe top-level split point exists, compiler now attempts scope-preserving rewrite:
    extracts nested `if` body into auto-generated helper function and inserts `call(helper)` inside that same `if` scope,
  - braces stay semantically local to opener row (`skip` behavior preserved), while row budget is reduced without unsafe cross-row closure carry,
  - verified on current user script: compiler emits `__autosplit_row_1 -> call(__autosplit_row_2)` and final `plan.json` rows stay within max `43`.
- synthetic array stack index fix:
  - internal compiler-generated array calls now use canonical param name `num` (not `number`) for:
    `array.vstavit_v_massiv`, `array.get_array`, `array.remove_array`,
  - restores index slots in emitted plan (`slot(13)` / `slot(15)`) for stack-based call/return plumbing (`__mldsl_args` / `__mldsl_ret`),
  - removes intermittent "missing array index" symptom in compiled `plan.json`.

## Known regressions
- Catalog drift risk when source exports are stale.
- Runtime assumptions may diverge if mod changes plan parser semantics.

## Last user-tested
- 2026-02-11: integrated workflow with mod export/compile path used in practice.
- 2026-02-12: mod-side modern runtime-core migration started (`fabric1165/fabric120/fabric121/forge1165` bootstrap targets).

## Notes
- Compiler-only SoT.
- Keep export/plan semantics stable while modern mod adapters are replacing bootstrap `UNIMPLEMENTED_PLATFORM_OPERATION` paths with full publish/parser/printer logic.
