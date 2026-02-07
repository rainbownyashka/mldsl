# Architecture

## Scope
MLDSL toolchain converts and compiles K+ code artifacts:
- `exportcode_*.json` -> `.mldsl`
- `.mldsl` -> `plan.json`

## Components
- `mldsl_cli.py`: public CLI entrypoint (`build-all`, `compile`, `paths`, `exportcode`).
- `mldsl_exportcode.py`: JSON export translator, including noaction placeholders and brace reconstruction.
- `mldsl_compile.py`: DSL compiler to plan entries.
- `build_api_aliases.py` / `out/api_aliases.json`: action/signature catalog.
- `tools/pipeline.py`: deterministic local/CI pipeline entrypoint.

## Contract invariants
- Export rows are processed by geometry order (x desc, strict step pattern).
- Side piston brace semantics must stay deterministic:
- `west` => open block
- `east` => close block
- Empty sign support is explicit and compile-safe:
- `event()`
- `player.noaction()`
- `if_player.noaction()`

## Data contracts
- Export JSON v2 is baseline format.
- Chest slot indices can be absolute (across pages).
- Compiler should accept noaction pseudo-calls as structural nodes.

## Quality gates
- CI runs `tools/pipeline.py fast --skip-smoke --skip-vsix`.
- Unit tests under `tests/` must pass.
- Required docs must exist.
