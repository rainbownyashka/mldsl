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

## Known regressions
- Catalog drift risk when source exports are stale.
- Runtime assumptions may diverge if mod changes plan parser semantics.

## Last user-tested
- 2026-02-11: integrated workflow with mod export/compile path used in practice.
- 2026-02-12: mod-side modern runtime-core migration started (`fabric1165/fabric120/fabric121/forge1165` bootstrap targets).

## Notes
- Compiler-only SoT.
- Keep export/plan semantics stable while modern mod adapters are replacing bootstrap `UNIMPLEMENTED_PLATFORM_OPERATION` paths with full publish/parser/printer logic.
