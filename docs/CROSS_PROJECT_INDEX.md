# CROSS_PROJECT_INDEX

## Project
- Name: MLDSL Compiler
- Path: `C:\Users\ASUS\Documents\mlctmodified`
- Role: compile/translate/export MLDSL artifacts
- Last verified: 2026-02-11

## Depends on
- Mod repo (`k:\mymod`) for runtime consumer behavior of `plan.json`.
- Site repo (`mldsl-hub`) for publish/display expectations around compiled modules.

## Inbound contracts
- Mod reports parser/runtime constraints for plan compatibility.
- Site defines metadata expectations for published modules.

## Outbound contracts
- Stable `plan.json` schema and deterministic compile behavior.
- Export conversion compatibility for mod-generated exportcode JSON.

## External dependency links
- External dependency: `k:\mymod` / `docs/AGENT_RUNBOOK.md`
- External dependency: `C:\Users\ASUS\Documents\mldsl-hub` / `docs/AGENT_RUNBOOK.md`
