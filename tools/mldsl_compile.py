"""
Wrapper for the active MLDSL compiler.

The real implementation lives at repo root: `mldsl_compile.py`.
We keep this file because VS Code extension and docs auto-detect `tools/mldsl_compile.py`.
"""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    root = repo_root / "mldsl_compile.py"
    runpy.run_path(str(root), run_name="__main__")


if __name__ == "__main__":
    main()
