from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

_COLOR_RE = re.compile(r"(§.|&.)", re.U)


def strip_colors(s: str) -> str:
    return _COLOR_RE.sub("", s or "")


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
        return any("\u0400" <= ch <= "\u04FF" for ch in (x or ""))

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


def _norm_enum_label(s: str) -> str:
    s = _norm_key(s)
    s = s.replace(" ", "")
    return s


def _extract_enum_label(item: Dict[str, Any]) -> Optional[str]:
    if item.get("isEnum") and isinstance(item.get("enumOptions"), list):
        opts = [strip_colors(str(x or "")).strip() for x in (item.get("enumOptions") or [])]
        idx = item.get("enumSelectedIndex")
        if isinstance(idx, int) and 0 <= idx < len(opts):
            return opts[idx]

    lore = item.get("lore") or []
    if not lore:
        lore = _extract_lore_from_snbt(str(item.get("nbt") or "")) or []
    if isinstance(lore, list):
        for line in lore:
            clean = strip_colors(str(line or "")).strip()
            if "●" in clean or clean.startswith("●"):
                return clean.replace("●", "").replace("○", "").strip()
    return None


def _extract_lore_from_snbt(nbt: str) -> List[str]:
    """
    Best-effort parser for 1.12 ItemStack SNBT produced by `tag.toString()`.
    We only need display.Lore, which is usually stored as: Lore:["...","..."].
    """
    s = nbt or ""
    key = "Lore:["
    i = s.find(key)
    if i < 0:
        return []
    j = i + len(key)
    in_str = False
    esc = False
    depth = 0
    out = ""
    for k in range(j, len(s)):
        ch = s[k]
        if esc:
            esc = False
            out += ch
            continue
        if ch == "\\":
            esc = True
            out += ch
            continue
        if ch == '"':
            in_str = not in_str
            out += ch
            continue
        if not in_str:
            if ch == "[":
                depth += 1
            elif ch == "]":
                if depth == 0:
                    break
                depth -= 1
        out += ch
    # Extract all "...".
    vals: List[str] = []
    for m in re.finditer(r'"((?:\\\\.|[^"\\\\])*)"', out):
        raw = m.group(1)
        vals.append(raw.replace("\\\\", "\\").replace('\\"', '"'))
    return vals


def _item_to_arg_value(mode: str, item: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    warns: List[str] = []
    m = (mode or "").upper().strip()
    name = strip_colors(str(item.get("displayName") or "")).strip()
    lore = item.get("lore") or []
    if not lore:
        lore = _extract_lore_from_snbt(str(item.get("nbt") or "")) or []
    lore_clean = [strip_colors(str(x or "")).strip() for x in lore] if isinstance(lore, list) else []

    if m == "ANY":
        # Infer from item id (server convention).
        rid = (item.get("id") or "").lower().strip()
        inferred = ""
        if rid.endswith("book") or rid == "minecraft:book":
            inferred = "TEXT"
        elif rid.endswith("slime_ball") or rid == "minecraft:slime_ball":
            inferred = "NUMBER"
        elif rid.endswith("magma_cream") or rid == "minecraft:magma_cream":
            inferred = "VARIABLE"
        elif rid.endswith("paper") or rid == "minecraft:paper":
            inferred = "LOCATION"
        elif rid.endswith("item_frame") or rid == "minecraft:item_frame":
            inferred = "ARRAY"
        elif rid:
            inferred = "ITEM"
        else:
            warns.append("ANY: не удалось определить тип по id предмета")
            return None, warns
        v, ws = _item_to_arg_value(inferred, item)
        warns.extend(ws)
        return v, warns

    if m == "TEXT":
        if not name and lore_clean:
            name = lore_clean[0]
        if not name:
            warns.append("TEXT: пустое имя предмета")
            return _json_str(""), warns
        return _json_str(name), warns

    if m == "NUMBER":
        if not name:
            warns.append("NUMBER: пустое имя предмета")
            return "0", warns
        return name, warns

    if m == "VARIABLE":
        if not name:
            warns.append("VARIABLE: пустое имя предмета")
            return None, warns
        is_save = any("сохран" in ln.lower() for ln in lore_clean)
        if is_save:
            return f"var_save({name})", warns
        return name, warns

    if m == "ARRAY":
        if not name:
            warns.append("ARRAY: пустое имя предмета")
            return None, warns
        if name.endswith("⎘"):
            base = name[:-1].rstrip()
            return f"arr_save({base})", warns
        return name, warns

    if m == "LOCATION":
        if not name:
            warns.append("LOCATION: пустое имя предмета")
            return None, warns
        return name, warns

    if m == "ITEM":
        rid = (item.get("id") or "").strip()
        count = item.get("count")
        parts: List[str] = []
        if rid:
            parts.append(_json_str(rid))
        else:
            warns.append("ITEM: пустой id предмета")
            parts.append(_json_str("minecraft:stone"))
        if isinstance(count, int) and count > 1:
            parts.append(f"count={count}")
        if name:
            parts.append(f"name={_json_str(item.get('displayName') or '')}")
        return f"item({', '.join(parts)})", warns

    warns.append(f"неизвестный режим аргумента: {mode!r}")
    return None, warns


def _render_call_from_block(
    idx: Dict[str, List[Tuple[str, str, Dict[str, Any]]]],
    block: Dict[str, Any],
) -> Tuple[str, List[str]]:
    warns: List[str] = []
    sign = block.get("sign") or ["", "", "", ""]
    sign1 = (sign[0] if len(sign) > 0 else "") or ""
    sign2 = (sign[1] if len(sign) > 1 else "") or ""
    gui = str(block.get("gui") or "").strip()
    menu = str(block.get("menu") or "").strip()

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
    if not candidates and s2n:
        candidates = idx.get(f"menu:{s2n}", [])

    if not candidates:
        return (
            f"# UNKNOWN: {sign1} || {sign2} (block={block.get('block')})",
            [f"нет совпадения в api_aliases для sign1/sign2/gui/menu: {sign1!r} / {sign2!r} / {gui!r} / {menu!r}"],
        )

    module, alias, meta = candidates[0]
    params = meta.get("params") or []
    enums = meta.get("enums") or []

    if not params and not enums:
        return f"{module}.{alias}()", warns

    if not block.get("hasChest"):
        warns.append("у блока нет сундука параметров (hasChest=false) — аргументы восстановить нельзя")
        return f"{module}.{alias}()", warns

    items = block.get("chestItems") or []
    if not isinstance(items, list) or not items:
        warns.append("сундук параметров пустой/не экспортирован (chestItems пуст) — аргументы восстановить нельзя")
        return f"{module}.{alias}()", warns

    items_by_slot: Dict[int, Dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        slot = it.get("slot")
        if isinstance(slot, int):
            items_by_slot[slot] = it

    params_by_slot: Dict[int, Dict[str, Any]] = {}
    for p in params:
        if not isinstance(p, dict):
            continue
        slot = p.get("slot")
        if isinstance(slot, int):
            params_by_slot[slot] = p

    enums_by_slot: Dict[int, Dict[str, Any]] = {}
    for e in enums:
        if not isinstance(e, dict):
            continue
        slot = e.get("slot")
        if isinstance(slot, int):
            enums_by_slot[slot] = e

    out_kv: List[Tuple[str, str]] = []

    for slot, e in sorted(enums_by_slot.items(), key=lambda x: x[0]):
        ename = str(e.get("name") or "").strip()
        if not ename:
            continue
        it = items_by_slot.get(slot)
        if not it:
            warns.append(f"enum {ename}: слот {slot} пуст")
            continue
        picked = _extract_enum_label(it)
        if not picked:
            warns.append(f"enum {ename}: не удалось определить выбранный вариант")
            continue
        opts = e.get("options") or {}
        if not isinstance(opts, dict) or not opts:
            warns.append(f"enum {ename}: нет списка options в api_aliases")
            continue
        norm_map = {_norm_enum_label(k): k for k in opts.keys()}
        key = norm_map.get(_norm_enum_label(picked))
        if not key:
            warns.append(f"enum {ename}: значение {picked!r} не найдено в options")
            continue
        out_kv.append((ename, _json_str(key)))

    for slot, p in sorted(params_by_slot.items(), key=lambda x: x[0]):
        pname = str(p.get("name") or "").strip()
        pmode = str(p.get("mode") or "").strip()
        if not pname:
            continue
        it = items_by_slot.get(slot)
        if not it:
            continue
        v, ws = _item_to_arg_value(pmode, it)
        warns.extend([f"{pname}: {w}" for w in ws])
        if v is None:
            warns.append(f"{pname}: не удалось восстановить значение (slot={slot})")
            continue
        out_kv.append((pname, v))

    if not out_kv:
        warns.append("аргументы не восстановлены (ни один слот не распознан)")
        return f"{module}.{alias}()", warns

    args_s = ", ".join(f"{k}={v}" for k, v in out_kv)
    return f"{module}.{alias}({args_s})", warns


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

            if _norm_key(sign2) == "иначе" or _norm_key(sign1) == "иначе":
                lines.append(pad + "else")
                continue

            call, warns = _render_call_from_block(idx, b)
            for w in warns:
                lines.append(pad + f"# WARN: {w}")
            lines.append(pad + call)

        lines.append("}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
