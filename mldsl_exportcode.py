from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


_COLOR_RE = re.compile(r"(§.|&.)", re.U)


def strip_colors(s: str) -> str:
    return _COLOR_RE.sub("", s or "")


def _norm(s: str) -> str:
    return strip_colors(s or "").strip().lower()


def _norm_key(s: str) -> str:
    s = strip_colors(s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _json_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _pick_preferred_alias(entry: Dict[str, Any]) -> Optional[str]:
    aliases = entry.get("aliases") or []
    if not aliases:
        return None

    def has_cyrillic(x: str) -> bool:
        return any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in x)

    clean = [a for a in aliases if isinstance(a, str) and a.strip()]
    if not clean:
        return None

    ru = [a for a in clean if has_cyrillic(a)]
    if ru:
        return sorted(ru, key=lambda x: (len(x), x))[0]

    snake = [a for a in clean if "_" in a and re.match(r"^[a-zA-Z0-9_]+$", a)]
    if snake:
        return sorted(snake, key=lambda x: (len(x), x))[0]

    return sorted(clean, key=lambda x: (len(x), x))[0]


def build_action_index(api: Dict[str, Any]) -> Dict[str, List[Tuple[str, str, Dict[str, Any]]]]:
    out: Dict[str, List[Tuple[str, str, Dict[str, Any]]]] = {}

    def add(key: str, val: Tuple[str, str, Dict[str, Any]]) -> None:
        if not key:
            return
        out.setdefault(key, []).append(val)

    for module_name, funcs in api.items():
        if not isinstance(funcs, dict):
            continue
        for func_key, meta in funcs.items():
            if not isinstance(meta, dict):
                continue

            alias = _pick_preferred_alias(meta) or func_key
            sign1 = _norm_key(meta.get("sign1", ""))
            sign2 = _norm_key(meta.get("sign2", ""))
            gui = _norm_key(meta.get("gui", ""))
            menu = _norm_key(meta.get("menu", ""))
            val = (module_name, alias, meta)

            if sign1 and sign2:
                add(f"s12:{sign1}|{sign2}", val)
            if gui:
                add(f"gui:{gui}", val)
            if menu:
                add(f"menu:{menu}", val)
            if sign1 and gui:
                add(f"s1gui:{sign1}|{gui}", val)
            if sign1 and menu:
                add(f"s1menu:{sign1}|{menu}", val)

    return out


def _render_call_from_block(
    idx: Dict[str, List[Tuple[str, str, Dict[str, Any]]]],
    block: Dict[str, Any],
) -> Tuple[str, List[str]]:
    warns: List[str] = []
    sign = block.get("sign") or ["", "", "", ""]
    sign1 = (sign[0] if len(sign) > 0 else "") or ""
    sign2 = (sign[1] if len(sign) > 1 else "") or ""
    gui = str(block.get("gui") or "").strip()
    menu = (sign[0] if len(sign) > 0 else "") or ""

    s1n = _norm_key(sign1)
    s2n = _norm_key(sign2)
    guin = _norm_key(gui)
    menun = _norm_key(menu)

    candidates: List[Tuple[str, str, Dict[str, Any]]] = []
    if s1n and s2n:
        candidates = idx.get(f"s12:{s1n}|{s2n}", [])
    if not candidates and guin:
        candidates = idx.get(f"gui:{guin}", [])
    if not candidates and menun:
        candidates = idx.get(f"menu:{menun}", [])
    if not candidates and s1n and guin:
        candidates = idx.get(f"s1gui:{s1n}|{guin}", [])
    if not candidates and s1n and menun:
        candidates = idx.get(f"s1menu:{s1n}|{menun}", [])

    if not candidates:
        return f"# UNKNOWN: {sign1} || {sign2} (block={block.get('block')})", ["no api match for block/sign"]

    module, alias, meta = candidates[0]

    # If chest snapshot is absent but API expects args, warn loudly and emit empty call.
    if meta.get("params") and not block.get("chestItems"):
        warns.append("нет снимка сундука параметров (chestItems): вызов сгенерирован без аргументов")
        return f"{module}.{alias}()", warns

    # Full arg reconstruction is handled by tools/exportcode_to_mldsl.py in dev mode.
    # For production CLI we keep it safe: if chestItems exist but we don't implement slot mapping here,
    # emit a visible warning.
    if block.get("chestItems"):
        warns.append("снимок сундука есть, но восстановление аргументов пока не включено в mldsl.exe")

    return f"{module}.{alias}()", warns


def _row_header(row0: Dict[str, Any], row_index: int) -> str:
    block = row0.get("block", "") or ""
    sign = row0.get("sign") or ["", "", "", ""]
    s1 = (sign[0] if len(sign) > 0 else "") or ""
    s2 = (sign[1] if len(sign) > 1 else "") or ""
    s3 = (sign[2] if len(sign) > 2 else "") or ""
    if block == "minecraft:diamond_block":
        name = s2.strip() or s1.strip() or f"event_{row_index}"
        return f"event({_json_str(name)}) {{"
    if block == "minecraft:lapis_block":
        name = s2.strip() or f"func_{row_index}"
        return f"func({name}) {{"
    if block == "minecraft:emerald_block":
        name = s2.strip() or f"loop_{row_index}"
        ticks = s3.strip()
        if ticks:
            return f"loop({name}, {ticks}) {{"
        return f"loop({name}, 20) {{"
    name = s2.strip() or s1.strip() or f"row_{row_index}"
    return f"row({_json_str(name)}) {{"


def exportcode_to_mldsl(export_obj: Dict[str, Any], api: Dict[str, Any]) -> str:
    idx = build_action_index(api)
    lines: List[str] = []
    rows = export_obj.get("rows") or []

    version = export_obj.get("version")
    if version is not None and int(version) < 2:
        lines.append("# WARN: exportcode version < 2; возможна неполная детекция enum/аргументов.")
        lines.append("")

    for ri, row in enumerate(rows):
        blocks = row.get("blocks") or []
        if not blocks:
            continue
        lines.append(_row_header(blocks[0], ri))
        indent = 1

        for b in blocks[1:]:
            block_id = b.get("block", "") or ""
            facing = (b.get("facing") or "").lower()
            sign = b.get("sign") or ["", "", "", ""]
            sign1 = (sign[0] if len(sign) > 0 else "") or ""
            sign2 = (sign[1] if len(sign) > 1 else "") or ""

            pad = "    " * indent

            if block_id in ("minecraft:piston", "minecraft:sticky_piston"):
                if facing == "west":
                    lines.append(pad + "{")
                    indent += 1
                    continue
                if facing == "east":
                    indent = max(1, indent - 1)
                    lines.append(("    " * indent) + "}")
                    continue
                lines.append(pad + f"# piston facing={facing!r}")
                continue

            if _norm(sign2) == "иначе" or _norm(sign1) == "иначе":
                lines.append(pad + "else")
                continue

            call, warns = _render_call_from_block(idx, b)
            for w in warns:
                lines.append(pad + f"# WARN: {w}")
            lines.append(pad + call)

        lines.append("}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"

