from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_repo_root_on_syspath

ensure_repo_root_on_syspath()

from mldsl_exportcode import exportcode_to_mldsl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export_json", type=Path, help="Path to exportcode_*.json")
    ap.add_argument("--api", type=Path, default=Path("out/api_aliases.json"), help="Path to api_aliases.json")
    ap.add_argument("-o", "--out", type=Path, default=None, help="Output .mldsl path")
    args = ap.parse_args()

    export_obj = json.loads(args.export_json.read_text(encoding="utf-8"))
    api_obj = json.loads(args.api.read_text(encoding="utf-8"))
    text = exportcode_to_mldsl(export_obj, api_obj)

    out_path = args.out or args.export_json.with_suffix(".mldsl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

