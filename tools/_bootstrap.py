from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_syspath() -> None:
    """
    Allows running tools/*.py directly (python tools/foo.py) while importing modules from repo root.
    """
    repo_root = Path(__file__).resolve().parents[1]
    p = str(repo_root)
    if p not in sys.path:
        sys.path.insert(0, p)

