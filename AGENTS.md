# AGENTS (MLDSL Compiler Repo)

## Repo role
- Project: `C:\Users\ASUS\Documents\mlctmodified`
- Role: MLDSL compiler, exporter, CLI tooling, packaging

## Forbidden scope
- No detailed mod runtime docs (belongs to `k:\mymod`).
- No detailed site deploy/backend docs (belongs to `mldsl-hub`).

## Workflow rule
- Read `docs/STATUS.md` and `docs/TODO.md` before edits.
- Update both after meaningful changes.

## Engineering policy (compiler vs runtime)
- Keep printer/scanner runtime as simple and cross-version portable as possible (`k:\mymod` side).
- Prefer moving logic/validation/bug-fixes into compiler (`mlctmodified`) when feasible.
- Goal: runtime should reliably execute plans, compiler should carry complexity and test coverage.

## Parser reliability rules
- Never detect assignment by naive `line contains '='` logic.
- Assignment sugar is valid only when operator is top-level (outside quotes, call args, and bracket scopes).
- Dynamic assignment fallback (`%var(...)` in LHS) must use the same top-level-operator guard as regular assignment.
- Any parser bug report must be locked with a regression test first, then fixed in compiler logic (no runtime workaround).
