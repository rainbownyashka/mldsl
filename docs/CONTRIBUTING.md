# Contributing

## Rules
- Keep behavior explicit; no silent fallback paths.
- Any parser/compiler behavior change requires tests.
- Keep user-facing RU output readable (UTF-8).

## Local checks
```powershell
python tools/pipeline.py fast --skip-smoke --skip-vsix
python -m unittest discover -s tests -p "test_*.py" -v
```

## Change checklist
- Update docs when behavior/contract changes.
- Add regression test for every fixed bug in export/compile flow.
- Keep CLI contracts backward-compatible unless explicitly versioned.
