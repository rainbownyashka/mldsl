from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

from mldsl_paths import ensure_dirs, out_dir, repo_root


def _cmd_build_all(_args: argparse.Namespace) -> int:
    ensure_dirs()
    target = str(repo_root() / "tools" / "build_all.py")
    # Isolate argv so inner argparse does not receive outer `mldsl_cli` args.
    prev_argv = sys.argv[:]
    try:
        sys.argv = [target]
        runpy.run_path(target, run_name="__main__")
    finally:
        sys.argv = prev_argv
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    ensure_dirs()
    from mldsl_compile import compile_commands, compile_entries

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Файл не найден: {src}")

    if args.plan:
        plan_path = Path(args.plan).expanduser()
        if not plan_path.is_absolute():
            plan_path = Path.cwd() / plan_path
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        entries = compile_entries(src)
        plan_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.print_plan:
            print(plan_path.read_text(encoding="utf-8"))
        else:
            print(f"OK: wrote {plan_path}")
        return 0

    for cmd in compile_commands(src):
        print(cmd)
    return 0


def _cmd_paths(_args: argparse.Namespace) -> int:
    from mldsl_paths import (
        actions_catalog_path,
        api_aliases_path,
        data_root,
        default_minecraft_export_path,
        docs_dir,
        gamevalues_path,
        inputs_dir,
        logs_dir,
    )

    ensure_dirs()
    print(f"data_root={data_root()}")
    print(f"out_dir={out_dir()}")
    print(f"docs_dir={docs_dir()}")
    print(f"logs_dir={logs_dir()}")
    print(f"inputs_dir={inputs_dir()}")
    print(f"api_aliases={api_aliases_path()}")
    print(f"actions_catalog={actions_catalog_path()}")
    print(f"gamevalues={gamevalues_path()}")
    print(f"regallactions_export={default_minecraft_export_path()}")
    return 0


def _cmd_exportcode(args: argparse.Namespace) -> int:
    ensure_dirs()
    from mldsl_exportcode import exportcode_to_mldsl

    export_path = Path(args.export_json).expanduser().resolve()
    if not export_path.exists():
        raise FileNotFoundError(f"Файл exportcode не найден: {export_path}")

    api_path = Path(args.api).expanduser()
    if not api_path.is_absolute():
        api_path = Path.cwd() / api_path
    if not api_path.exists():
        raise FileNotFoundError(f"api_aliases.json не найден: {api_path}")

    export_obj = json.loads(export_path.read_text(encoding="utf-8"))
    api_obj = json.loads(api_path.read_text(encoding="utf-8"))
    text = exportcode_to_mldsl(export_obj, api_obj)

    out_path = Path(args.out).expanduser() if args.out else export_path.with_suffix(".mldsl")
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"OK: wrote {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mldsl", description="MLDSL compiler/build tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_build = sub.add_parser("build-all", help="Generate out/ (catalog, api_aliases, gamevalues, docs)")
    sp_build.set_defaults(func=_cmd_build_all)

    sp_compile = sub.add_parser("compile", help="Compile .mldsl to /placeadvanced commands or plan.json")
    sp_compile.add_argument("input", help="Path to .mldsl file")
    sp_compile.add_argument("--plan", help="Write JSON plan to this path (instead of printing commands)")
    sp_compile.add_argument("--print-plan", action="store_true", help="Print plan.json after writing")
    sp_compile.set_defaults(func=_cmd_compile)

    sp_paths = sub.add_parser("paths", help="Print resolved paths (data_root/out/docs/etc)")
    sp_paths.set_defaults(func=_cmd_paths)

    sp_export = sub.add_parser("exportcode", help="Convert exportcode_*.json (from BetterCode) to .mldsl")
    sp_export.add_argument("export_json", help="Path to exportcode_*.json")
    sp_export.add_argument(
        "--api",
        default="out/api_aliases.json",
        help="Path to api_aliases.json (default: out/api_aliases.json)",
    )
    sp_export.add_argument("-o", "--out", default=None, help="Output .mldsl path (default: <export>.mldsl)")
    sp_export.set_defaults(func=_cmd_exportcode)

    ns = p.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
