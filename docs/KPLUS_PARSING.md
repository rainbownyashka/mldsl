# K+ Export -> MLDSL: Row/Brace Rules

This note fixes the source of ambiguity around row order and braces.

## Row geometry

- Row starts at event block `x0` (the first block in `rows[i].blocks`).
- Iterator step `p` uses:
  - `entryX = x0 - 2*p`
  - `sideX  = entryX + 1`
- `entryX` is the action/condition slot.
- `sideX` is the brace piston slot.

## Brace tokens (strict)

- Braces are emitted from **side piston only** (`sideX`), even if entry block is air.
- Piston facing:
  - `east` (`+x`) => open brace `{`
  - `west` (`-x`) => close brace `}`
- Entry block does not decide brace open/close by itself.

## Emission order per iterator step

1. Emit entry action/condition call (if any block at `entryX`).
2. Emit brace token from side piston at `sideX` (if present).

This order matches K+ visual code flow where side piston is a structural token near the entry slot.

## Conditions

- `if_*` is emitted as a regular call line.
- Scope is controlled by side pistons according to the rule above.

## Why this exists

Previous logic mixed braces from:
- block type (`if_*`) and
- piston heuristics/noise filtering.

That produced unstable scopes when side pistons were filtered or reordered.

