from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Transpile .dslpy (python-like DSL) to .mldsl and compile to plan.json.")
    ap.add_argument("path", help="Path to .dslpy file")
    ap.add_argument("--print-mldsl", action="store_true", help="Print transpiled MLDSL to stdout")
    ap.add_argument("--print-plan", action="store_true", help="Print compiled plan JSON to stdout (like mldsl_compile.py)")
    args = ap.parse_args()

    src_path = Path(args.path)
    if not src_path.exists():
        print(f"ERROR: file not found: {src_path}", file=sys.stderr)
        return 2

    try:
        from tools._premium.dslpy_transpile import DslPyError, transpile  # type: ignore
    except Exception:
        # tools/ is not a package; load by path
        import importlib.util

        tp = (REPO_ROOT / "tools" / "_premium" / "dslpy_transpile.py").resolve()
        spec = importlib.util.spec_from_file_location("_mldsl_dslpy_transpile", str(tp))
        if not spec or not spec.loader:
            print("ERROR: cannot load dslpy transpiler", file=sys.stderr)
            return 2
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        DslPyError = getattr(mod, "DslPyError")
        transpile = getattr(mod, "transpile")

    try:
        src = src_path.read_text(encoding="utf-8", errors="replace")
        # Allow a tiny template directive (not valid python syntax):
        #   @import timer_start
        #   @template hold_rightclick
        directive_line = ""
        for ln in (src or "").lstrip("\ufeff").splitlines():
            stripped = ln.strip()
            if not stripped:
                continue
            directive_line = stripped
            break
        m = re.match(r"^@(import|template)\s+(.+?)\s*$", directive_line, flags=re.IGNORECASE)
        if m:
            raw_name = m.group(2).strip()
            raw_name = raw_name.split("#", 1)[0].strip().strip("\"'").replace("\\", "/")
            # tolerate junk after the template name (weak models): "@import timer_start 2"
            raw_name = raw_name.split()[0] if raw_name.split() else raw_name
            name = raw_name.split("/")[-1]
            safe = re.sub(r"[^0-9A-Za-z_.-]", "", name)
            ex_path = (REPO_ROOT / "examples" / f"{safe}.dslpy").resolve()
            if not ex_path.exists():
                print(f"ERROR: dslpy template not found: {raw_name} (looked for {ex_path})", file=sys.stderr)
                return 2
            src = ex_path.read_text(encoding="utf-8", errors="replace")
        mldsl_src = transpile(src)  # type: ignore[misc]
    except Exception as ex:
        if ex.__class__.__name__ == "DslPyError":
            print(f"ERROR: dslpy: {ex}", file=sys.stderr)
            return 2
        print(f"ERROR: dslpy: {type(ex).__name__}: {ex}", file=sys.stderr)
        return 2

    if args.print_mldsl:
        print(mldsl_src)
        if not args.print_plan:
            return 0

    tmp = src_path.with_suffix(".mldsl")
    tmp.write_text(mldsl_src, encoding="utf-8")

    cmd = [sys.executable, str(REPO_ROOT / "tools" / "mldsl_compile.py"), str(tmp)]
    if args.print_plan:
        cmd.append("--print-plan")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
