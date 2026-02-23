from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import sys
from pathlib import Path

from mldsl_paths import actions_catalog_path, api_aliases_path, ensure_dirs, out_dir, repo_root

TIER_ORDER = ["player", "gamer", "skilled", "expert", "hero", "king", "legend"]
TIER_LEVEL = {name: idx for idx, name in enumerate(TIER_ORDER)}
TIER_ALIASES = {
    "игрок": "player",
    "player": "player",
    "геймер": "gamer",
    "gamer": "gamer",
    "skilled": "skilled",
    "expert": "expert",
    "hero": "hero",
    "king": "king",
    "legend": "legend",
}


def _norm_alias(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[§&][0-9a-fk-or]", "", s)
    s = re.sub(r"[\x00-\x1f]", "", s)
    s = re.sub(r"[“”\"'`]", "", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\wа-яё.]+", "_", s, flags=re.I)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _build_catalog_key(sign1: str, sign2: str, gui: str) -> str:
    return "|".join([_norm_alias(sign1), _norm_alias(sign2), _norm_alias(gui)])


def _normalize_tier_name(name: str) -> str | None:
    x = TIER_ALIASES.get((name or "").strip().lower(), (name or "").strip().lower())
    return x if x in TIER_LEVEL else None


def _parse_rank_rules_text(text: str) -> dict[int, int]:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    by_tier: dict[str, set[int]] = {t: set() for t in TIER_ORDER}
    current_tier: str | None = None
    for line in lines:
        m = re.match(r"^([a-zа-яё_]+)\s+can$", line, flags=re.I)
        if m:
            current_tier = _normalize_tier_name(m.group(1))
            continue
        if not current_tier:
            continue
        if not re.match(r"^\d{1,5}$", line):
            continue
        by_tier[current_tier].add(int(line))
    id_to_tier_level: dict[int, int] = {}
    for tier in TIER_ORDER:
        lvl = TIER_LEVEL[tier]
        for action_id in by_tier[tier]:
            prev = id_to_tier_level.get(action_id)
            if prev is None or lvl > prev:
                id_to_tier_level[action_id] = lvl
    return id_to_tier_level


def _extract_action_calls_from_code(code: str) -> set[str]:
    stripped_lines: list[str] = []
    for line in str(code or "").splitlines():
        in_quote = False
        quote_ch = ""
        cut_idx = -1
        i = 0
        while i < len(line):
            ch = line[i]
            if ch in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
                if not in_quote:
                    in_quote = True
                    quote_ch = ch
                elif quote_ch == ch:
                    in_quote = False
                    quote_ch = ""
            elif ch == "#" and not in_quote:
                cut_idx = i
                break
            i += 1
        stripped_lines.append(line[:cut_idx] if cut_idx >= 0 else line)
    s = "\n".join(stripped_lines)
    out: set[str] = set()
    rx = re.compile(r"([a-zа-яё_][a-zа-яё0-9_]*)\s*\.\s*([a-zа-яё_][a-zа-яё0-9_]*)\s*\(", flags=re.I)
    for m in rx.finditer(s):
        mod = _norm_alias(m.group(1))
        act = _norm_alias(m.group(2))
        if not mod or not act:
            continue
        out.add(f"{mod}.{act}")
        out.add(act)
    return out


def _build_alias_id_map(aliases_obj: dict, catalog_arr: list[dict]) -> dict[str, int]:
    catalog_by_key: dict[str, int] = {}
    for idx, row in enumerate(catalog_arr):
        if not isinstance(row, dict):
            continue
        signs = row.get("signs") if isinstance(row.get("signs"), list) else []
        key = _build_catalog_key(
            str(signs[0]) if len(signs) > 0 else "",
            str(signs[1]) if len(signs) > 1 else "",
            str(row.get("gui") or ""),
        )
        catalog_by_key.setdefault(key, idx)

    out: dict[str, int] = {}
    for mod_name, mod_items in (aliases_obj or {}).items():
        mod_norm = _norm_alias(str(mod_name or ""))
        if not isinstance(mod_items, dict):
            continue
        for act_name, act_obj in mod_items.items():
            if not isinstance(act_obj, dict):
                continue
            key = _build_catalog_key(
                str(act_obj.get("sign1") or ""),
                str(act_obj.get("sign2") or ""),
                str(act_obj.get("gui") or ""),
            )
            action_id = catalog_by_key.get(key)
            if action_id is None:
                continue
            aliases = act_obj.get("aliases") if isinstance(act_obj.get("aliases"), list) else []
            for raw_name in [act_name, *aliases]:
                n = _norm_alias(str(raw_name or ""))
                if not n:
                    continue
                out[n] = action_id
                if mod_norm:
                    out[f"{mod_norm}.{n}"] = action_id
    return out


def _compute_required_tier_for_source(code: str) -> tuple[str, int, list[int], list[str]]:
    rank_path = repo_root() / "donaterequire.txt"
    id_to_tier_level = _parse_rank_rules_text(rank_path.read_text(encoding="utf-8")) if rank_path.exists() else {}
    if not id_to_tier_level:
        return "player", 0, [], []

    alias_path = api_aliases_path()
    catalog_path = actions_catalog_path()
    if not alias_path.exists() or not catalog_path.exists():
        return "player", 0, [], []

    aliases_obj = json.loads(alias_path.read_text(encoding="utf-8"))
    catalog_arr = json.loads(catalog_path.read_text(encoding="utf-8"))
    alias_id_map = _build_alias_id_map(aliases_obj, catalog_arr if isinstance(catalog_arr, list) else [])
    if not alias_id_map:
        return "player", 0, [], []

    ids: set[int] = set()
    alias_to_id: dict[str, int] = {}
    for alias in _extract_action_calls_from_code(code):
        action_id = alias_id_map.get(alias)
        if action_id is not None:
            ids.add(action_id)
            if "." in alias:
                alias_to_id[alias] = action_id

    required_level = 0
    matched_ids: list[int] = []
    for action_id in ids:
        lvl = id_to_tier_level.get(action_id)
        if lvl is None:
            continue
        matched_ids.append(action_id)
        if lvl > required_level:
            required_level = lvl
    matched_ids.sort()
    matched_id_set = set(matched_ids)
    matched_names_sorted = sorted([name for name, aid in alias_to_id.items() if aid in matched_id_set])
    return TIER_ORDER[required_level], required_level, matched_ids, matched_names_sorted


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

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Файл не найден: {src}")
    src_text = src.read_text(encoding="utf-8")

    prev_strict_env = os.environ.get("MLDSL_STRICT_UNKNOWN")
    try:
        if getattr(args, "strict_unknown", False):
            os.environ["MLDSL_STRICT_UNKNOWN"] = "1"
        from mldsl_compile import compile_commands, compile_entries
        if args.plan:
            plan_path = Path(args.plan).expanduser()
            if not plan_path.is_absolute():
                plan_path = Path.cwd() / plan_path
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            entries = compile_entries(src)
            plan_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tier, _level, matched, matched_names = _compute_required_tier_for_source(src_text)
            preview = ", ".join(matched_names[:5]) if matched_names else "-"
            print(
                f"[warn] required donate tier: {tier} (matched actions: {len(matched)}; detected: {preview})",
                file=sys.stderr,
            )
            if args.print_plan:
                print(plan_path.read_text(encoding="utf-8"))
            else:
                print(f"OK: wrote {plan_path}")
            return 0

        for cmd in compile_commands(src):
            print(cmd)
        tier, _level, matched, matched_names = _compute_required_tier_for_source(src_text)
        preview = ", ".join(matched_names[:5]) if matched_names else "-"
        print(
            f"[warn] required donate tier: {tier} (matched actions: {len(matched)}; detected: {preview})",
            file=sys.stderr,
        )
        return 0
    finally:
        if prev_strict_env is None:
            os.environ.pop("MLDSL_STRICT_UNKNOWN", None)
        else:
            os.environ["MLDSL_STRICT_UNKNOWN"] = prev_strict_env


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

    if args.api:
        api_path = Path(args.api).expanduser()
        if not api_path.is_absolute():
            api_path = Path.cwd() / api_path
    else:
        api_path = api_aliases_path()
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


def _normalize_legacy_cli_argv(argv: list[str] | None) -> list[str]:
    """Accept legacy invocations and rewrite them into subcommand form.

    Supported legacy forms:
    - mldsl_cli.py <input.mldsl>
    - mldsl_cli.py --plan <plan.json> <input.mldsl>
    - mldsl_cli.py <input.mldsl> --plan <plan.json>
    """
    args = list(argv or [])
    if not args:
        return args
    known_cmds = {"build-all", "compile", "paths", "exportcode"}
    if args[0] in known_cmds:
        return args

    # Legacy compile mode: first token is file path or option list for compile.
    # Keep flags intact and move detected input into first positional after `compile`.
    input_path: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("-"):
            rest.append(tok)
            # preserve value for known value-taking options
            if tok in {"--plan", "-o", "--out", "--api"} and (i + 1) < len(args):
                rest.append(args[i + 1])
                i += 2
                continue
            i += 1
            continue
        if input_path is None:
            input_path = tok
        else:
            rest.append(tok)
        i += 1
    if not input_path:
        return args
    return ["compile", input_path, *rest]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mldsl", description="MLDSL compiler/build tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_build = sub.add_parser("build-all", help="Generate out/ (catalog, api_aliases, gamevalues, docs)")
    sp_build.set_defaults(func=_cmd_build_all)

    sp_compile = sub.add_parser("compile", help="Compile .mldsl to /placeadvanced commands or plan.json")
    sp_compile.add_argument("input", help="Path to .mldsl file")
    sp_compile.add_argument("--plan", help="Write JSON plan to this path (instead of printing commands)")
    sp_compile.add_argument("--print-plan", action="store_true", help="Print plan.json after writing")
    sp_compile.add_argument(
        "--strict-unknown",
        action="store_true",
        help="Fail on unresolved/unknown lines instead of warning",
    )
    sp_compile.set_defaults(func=_cmd_compile)

    sp_paths = sub.add_parser("paths", help="Print resolved paths (data_root/out/docs/etc)")
    sp_paths.set_defaults(func=_cmd_paths)

    sp_export = sub.add_parser("exportcode", help="Convert exportcode_*.json (from BetterCode) to .mldsl")
    sp_export.add_argument("export_json", help="Path to exportcode_*.json")
    sp_export.add_argument(
        "--api",
        default=None,
        help="Path to api_aliases.json (default: resolved MLDSL out/api_aliases.json)",
    )
    sp_export.add_argument("-o", "--out", default=None, help="Output .mldsl path (default: <export>.mldsl)")
    sp_export.set_defaults(func=_cmd_exportcode)

    eff_argv = list(sys.argv[1:] if argv is None else argv)
    ns = p.parse_args(_normalize_legacy_cli_argv(eff_argv))
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
