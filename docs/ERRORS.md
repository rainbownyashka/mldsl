# Errors and Diagnostics

## Translator (`mldsl exportcode`)
- `# UNKNOWN: ...`
- Meaning: action/signature not resolved via api aliases.
- Action: check `out/api_aliases.json` and source sign lines.

- `пустая табличка: применен noaction-плейсхолдер`
- Meaning: structural node kept intentionally with `noaction`.

## Compiler (`mldsl compile`)
- `неизвестное событие: ...`
- Meaning: event token is not in event catalog and not empty-form event.

- `argument cmd: invalid choice ...`
- Meaning: wrong CLI shape; must use subcommand (`compile`, `exportcode`, ...).

## Encoding
- Any mojibake in output is a blocker regression.
- All repo files and runtime IO must be UTF-8.
