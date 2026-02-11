# Agent Runbook (MLDSL Compiler SoT)

This file is the source of truth for compiler/tooling in this repo only.

## Repo role
- Project: `C:\Users\ASUS\Documents\mlctmodified`
- Scope: parser/compiler/exporter/CLI/packaging

## Forbidden scope
- No detailed BetterCode mod operational docs.
- No detailed mldsl-hub deploy/backend docs.

## Core commands
Run from repo root:

```powershell
python .\mldsl_cli.py exportcode "<in.json>" -o "<out.mldsl>"
python .\mldsl_cli.py compile "<out.mldsl>" --plan "<out.plan.json>"
python .\mldsl_cli.py build-all
```

## Compiler pipeline SoT
- Input: `.mldsl` or `exportcode_*.json`
- Output: `.mldsl` and/or `plan.json`
- Aliases/docs source: generated `out/` assets

## Integration contract with mod (no mod build steps)
- Compiler guarantees valid `plan.json` structure consumed by `/mldsl run`.
- `noaction` placeholders remain compilable to structurally valid plan entries.
- Encoding contract: UTF-8 for all generated files.
- Breaking plan schema changes require explicit coordination update in cross-project index.

## External dependencies
- External dependency: mod repo `k:\mymod` / `docs/AGENT_RUNBOOK.md`
- External dependency: site repo `C:\Users\ASUS\Documents\mldsl-hub` / `docs/AGENT_RUNBOOK.md`
