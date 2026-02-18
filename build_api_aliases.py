from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    target = Path(__file__).resolve().parent / "tools" / "build_api_aliases.py"
    print(
        "[deprecated] use `python tools/build_api_aliases.py`; "
        "legacy root entrypoint delegates to tools/",
        file=sys.stderr,
    )
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
