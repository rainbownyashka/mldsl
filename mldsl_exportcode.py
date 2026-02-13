from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

_COLOR_RE = re.compile(r"(?:§.|&.|В§.)", re.U)
_CONDITION_BLOCKS = {
    "minecraft:planks",
    "minecraft:red_nether_brick",
    "minecraft:brick_block",
    "minecraft:obsidian",
}


def strip_colors(s: str) -> str:
    return _COLOR_RE.sub("", s or "")


def _norm_key(s: str) -> str:
    s = strip_colors(s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _text_variants(s: str) -> List[str]:
    out: List[str] = []
    if not isinstance(s, str):
        return out
    out.append(s)
    # cp1251 bytes interpreted as latin1 text (e.g. "Êðåàòèâ")
    try:
        out.append(s.encode("latin1").decode("cp1251"))
    except Exception:
        pass
    # utf-8 bytes interpreted as cp1251 text
    try:
        out.append(s.encode("cp1251").decode("utf-8"))
    except Exception:
        pass
    dedup: List[str] = []
    seen = set()
    for v in out:
        if v not in seen:
            seen.add(v)
            dedup.append(v)
    return dedup


def _norm_key_variants(s: str) -> List[str]:
    vals: List[str] = []
    seen = set()
    for raw in _text_variants(s):
        k = _norm_key(raw)
        if k and k not in seen:
            seen.add(k)
            vals.append(k)
    return vals


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

    ident_re = re.compile(r"^[A-Za-z_\u0400-\u04FF][A-Za-z0-9_\u0400-\u04FF]*$")
    ident = [a for a in clean if ident_re.match(a)]

    ru = [a for a in ident if has_cyrillic(a)]
    if ru:
        return sorted(ru, key=lambda x: (len(x), x))[0]

    snake = [a for a in ident if "_" in a and re.match(r"^[a-zA-Z0-9_]+$", a)]
    if snake:
        return sorted(snake, key=lambda x: (len(x), x))[0]

    if ident:
        return sorted(ident, key=lambda x: (len(x), x))[0]

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
            sign1v = _norm_key_variants(str(meta.get("sign1", "")))
            sign2v = _norm_key_variants(str(meta.get("sign2", "")))
            guiv = _norm_key_variants(str(meta.get("gui", "")))
            menuv = _norm_key_variants(str(meta.get("menu", "")))
            val = (module_name, alias, meta)

            for sign1 in sign1v:
                add(f"s1:{sign1}", val)
            for gui in guiv:
                add(f"gui:{gui}", val)
            for menu in menuv:
                add(f"menu:{menu}", val)
            for sign1 in sign1v:
                for sign2 in sign2v:
                    add(f"s12:{sign1}|{sign2}", val)
            for sign1 in sign1v:
                for gui in guiv:
                    add(f"s1gui:{sign1}|{gui}", val)
            for sign1 in sign1v:
                for menu in menuv:
                    add(f"s1menu:{sign1}|{menu}", val)

    return out


def _norm_enum_label(s: str) -> str:
    s = _norm_key(s)
    s = s.replace("ё", "е")
    s = re.sub(r"[^a-zа-я0-9]+", "", s, flags=re.I)
    return s


def _enum_text_variants(s: str) -> List[str]:
    out: List[str] = []
    if not isinstance(s, str):
        return out
    out.append(s)
    # cp1251 bytes interpreted as latin1 text (e.g. "Êðåàòèâ")
    try:
        out.append(s.encode("latin1").decode("cp1251"))
    except Exception:
        pass
    # utf-8 bytes interpreted as cp1251 text
    try:
        out.append(s.encode("cp1251").decode("utf-8"))
    except Exception:
        pass
    # dedupe preserving order
    dedup: List[str] = []
    seen = set()
    for v in out:
        if v not in seen:
            seen.add(v)
            dedup.append(v)
    return dedup


def _enum_norm_variants(s: str) -> List[str]:
    vals: List[str] = []
    seen = set()
    for raw in _enum_text_variants(s):
        n = _norm_enum_label(raw)
        if n and n not in seen:
            seen.add(n)
            vals.append(n)
    return vals


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
            raw = str(line or "")
            clean = strip_colors(raw).strip()
            selected_markers = ("●", "•", "в—Џ")
            unselected_markers = ("○", "в—‹")
            selected_by_marker = any(m in clean for m in selected_markers)
            selected_by_color = any(code in raw.lower() for code in ("§a", "&a", "в§a"))
            if selected_by_marker or selected_by_color:
                out = clean
                for m in selected_markers + unselected_markers:
                    out = out.replace(m, "")
                out = out.strip(" -:\t")
                if out:
                    return out
    return None


def _match_enum_option_key(opts: Dict[str, Any], picked: str) -> Optional[str]:
    if not isinstance(opts, dict) or not opts:
        return None
    picked_norms = _enum_norm_variants(picked)
    if not picked_norms:
        return None

    for raw_key in opts.keys():
        key = str(raw_key)
        key_norms = _enum_norm_variants(key)
        if any(pn == kn for pn in picked_norms for kn in key_norms):
            return key

    candidates: List[Tuple[int, str]] = []
    for raw_key in opts.keys():
        key = str(raw_key)
        key_norms = _enum_norm_variants(key)
        if not key_norms:
            continue
        best: Optional[int] = None
        for pn in picked_norms:
            for kn in key_norms:
                if pn in kn or kn in pn:
                    score = abs(len(kn) - len(pn))
                    best = score if best is None else min(best, score)
        if best is not None:
            candidates.append((best, key))
    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][1]
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


def _extract_display_name_from_snbt(nbt: str) -> str:
    """Best-effort extraction of display.Name from SNBT item text."""
    s = str(nbt or "")
    if not s:
        return ""
    # Prefer display section if present, then read first Name:"...".
    m_display = re.search(r"display:\{(.*?)\}", s, flags=re.DOTALL)
    part = m_display.group(1) if m_display else s
    m_name = re.search(r'Name:"((?:\\\\.|[^"\\\\])*)"', part)
    if not m_name:
        return ""
    raw = m_name.group(1)
    return raw.replace("\\\\", "\\").replace('\\"', '"')


def _item_to_arg_value(mode: str, item: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    warns: List[str] = []
    m = (mode or "").upper().strip()
    raw_name = str(item.get("displayName") or "")
    if not raw_name:
        raw_name = _extract_display_name_from_snbt(str(item.get("nbt") or ""))
    name = strip_colors(raw_name).strip()
    lore = item.get("lore") or []
    if not lore:
        lore = _extract_lore_from_snbt(str(item.get("nbt") or "")) or []
    lore_clean = [strip_colors(str(x or "")).strip() for x in lore] if isinstance(lore, list) else []
    rid = (item.get("id") or "").lower().strip()

    def _is_variable_like_name(v: str) -> bool:
        t = (v or "").strip()
        if not t:
            return False
        if re.match(r"^(var|var_save|arr|arr_save)\(.+\)$", t, flags=re.IGNORECASE):
            return True
        if "%" in t and re.search(r"%[^%]+%", t):
            return True
        return False

    def _variable_passthrough() -> Optional[str]:
        if not name:
            return None
        if _is_variable_like_name(name):
            return name
        if rid.endswith("magma_cream") or rid == "minecraft:magma_cream":
            is_save = any("сохран" in ln.lower() for ln in lore_clean)
            return f"var_save({name})" if is_save else name
        return None

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
        # Do not coerce variable tokens into string text.
        var_v = _variable_passthrough()
        if var_v is not None:
            return var_v, warns
        if not name:
            # Some exportcode books encode text as formatting-only display names,
            # e.g. "§r§a" (green) or "§r§f" (white). In that case stripping colors
            # yields empty text, so keep MC formatting payload (without reset).
            fmt_only = re.sub(r"§r", "", raw_name).strip()
            if fmt_only:
                return _json_str(fmt_only), warns
        if not name and lore_clean:
            # Fallback for legacy exports where text is not in display name.
            name = lore_clean[0]
        if not name:
            warns.append("TEXT: пустое имя предмета")
            return _json_str(""), warns
        return _json_str(name), warns

    if m == "NUMBER":
        var_v = _variable_passthrough()
        if var_v is not None:
            return var_v, warns
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
        var_v = _variable_passthrough()
        if var_v is not None:
            return var_v, warns
        if not name:
            warns.append("LOCATION: пустое имя предмета")
            return None, warns
        return name, warns

    if m == "APPLE":
        # Legacy mode in some exports.
        # Do not stringify variable tokens; map bare apple constants to `apple.<TOKEN>`.
        var_v = _variable_passthrough()
        if var_v is not None:
            return var_v, warns
        if not name:
            warns.append("APPLE: пустое имя предмета")
            return "", warns
        if name.lower().startswith("apple."):
            return name, warns
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            return f"apple.{name}", warns
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




def _normalize_export_item(it: Dict[str, Any]) -> Dict[str, Any]:
    """Support both old and new export item formats."""
    if not isinstance(it, dict):
        return {}
    out = dict(it)
    if not out.get("id"):
        out["id"] = out.get("registry") or ""
    if not out.get("displayName"):
        out["displayName"] = out.get("display") or out.get("displayClean") or ""
    if "count" not in out:
        out["count"] = 1
    return out


def _is_placeholder_item(it: Dict[str, Any]) -> bool:
    rid = str((it or {}).get("id") or "").lower().strip()
    if rid == "minecraft:stained_glass_pane":
        return True
    return False


def _render_call_from_block(
    idx: Dict[str, List[Tuple[str, str, Dict[str, Any]]]],
    block: Dict[str, Any],
) -> Tuple[str, List[str]]:
    warns: List[str] = []
    sign = block.get("sign") or ["", "", "", ""]
    sign1 = (sign[0] if len(sign) > 0 else "") or ""
    sign2 = (sign[1] if len(sign) > 1 else "") or ""
    sign3 = (sign[2] if len(sign) > 2 else "") or ""
    gui = str(block.get("gui") or "").strip()
    menu = str(block.get("menu") or "").strip()

    s1v = _norm_key_variants(sign1)
    s2v = _norm_key_variants(sign2)
    s3v = _norm_key_variants(sign3)
    guiv = _norm_key_variants(gui)
    menuv = _norm_key_variants(menu)
    s1n = s1v[0] if s1v else ""
    s2n = s2v[0] if s2v else ""
    s3n = s3v[0] if s3v else ""

    # Hard guard: completely empty sign/gui/menu is invalid input and should
    # surface explicit diagnostics, not generic alias mismatch.
    if not s1v and not s2v and not guiv and not menuv:
        return (
            f"# UNKNOWN: {sign1} || {sign2} (block={block.get('block')})",
            [
                "пустая табличка: sign1/sign2/gui/menu пустые после нормализации; "
                "пересканируй таблички в моде и повтори export/publish"
            ],
        )

    # Special-case: old export may encode "Вызвать функцию" directly in sign lines
    # and miss api_aliases mapping. Normalize line 3 mode after stripping colors.
    if any("вызвать функцию" in x for x in s1v):
        fn_name = strip_colors(sign2).strip()
        if fn_name:
            mode = s3n.replace("ё", "е")
            if "асинхронно" in mode:
                return f"call({_json_str(fn_name)}, async=true)", warns
            # Empty and "Синхронно" both treated as sync by default.
            return f"call({_json_str(fn_name)})", warns

    def _placeholder_call_for_empty_sign() -> Optional[str]:
        # Support printer-compatible "empty sign action/condition":
        # keep block position in code flow, but do not require action name.
        # This compiles via pseudo noaction handlers in mldsl_compile.py.
        if s2n:
            return None
        s1c = s1n.replace(" ", "")
        if "событиеигрока" in s1c:
            return "event(\"Вход игрока\")"
        if "событиеигры" in s1c:
            return "event(\"Старт игры\")"
        if "еслиигрок" in s1c:
            return "if_player.noaction()"
        if "еслиигра" in s1c:
            return "if_game.noaction()"
        if "еслиперем" in s1c or "еслизнач" in s1c:
            return "if_value.noaction()"
        if "действиеигрока" in s1c:
            return "player.noaction()"
        if "действиеигры" in s1c:
            return "game.noaction()"
        return None

    candidates: List[Tuple[str, str, Dict[str, Any]]] = []
    if s1v and s2v:
        seen = set()
        for a in s1v:
            for b in s2v:
                for cand in idx.get(f"s12:{a}|{b}", []):
                    key = (cand[0], cand[1], id(cand[2]))
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(cand)
    if not candidates and guiv:
        seen = set()
        for g in guiv:
            for cand in idx.get(f"gui:{g}", []):
                key = (cand[0], cand[1], id(cand[2]))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(cand)
    if not candidates and menuv:
        seen = set()
        for m in menuv:
            for cand in idx.get(f"menu:{m}", []):
                key = (cand[0], cand[1], id(cand[2]))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(cand)
    if not candidates and s2v:
        seen = set()
        for s2k in s2v:
            for cand in idx.get(f"menu:{s2k}", []):
                key = (cand[0], cand[1], id(cand[2]))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(cand)
    if not candidates and s1n:
        seen = set()
        for cand in idx.get(f"s1:{s1n}", []):
            key = (cand[0], cand[1], id(cand[2]))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(cand)

    if not candidates:
        ph = _placeholder_call_for_empty_sign()
        if ph:
            return ph, ["пустая табличка: применен noaction-плейсхолдер"]
        return (
            f"# UNKNOWN: {sign1} || {sign2} (block={block.get('block')})",
            [f"нет совпадения в api_aliases для sign1/sign2/gui/menu: {sign1!r} / {sign2!r} / {gui!r} / {menu!r}"],
        )

    chest = block.get("chest")
    has_chest = bool(block.get("hasChest"))
    if not has_chest and isinstance(chest, dict):
        # New exportcode format may omit hasChest but contain chest object.
        has_chest = True

    items = block.get("chestItems") or []
    if (not isinstance(items, list) or not items) and isinstance(chest, dict):
        items = chest.get("slots") or []

    items_by_slot: Dict[int, Dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        norm_it = _normalize_export_item(it)
        slot = norm_it.get("slot")
        if isinstance(slot, int):
            items_by_slot[slot] = norm_it

    candidate_pool: List[Tuple[str, str, Dict[str, Any]]] = list(candidates)

    primary_set = set((m, a, id(meta0)) for (m, a, meta0) in candidates)

    def _score_candidate(cand: Tuple[str, str, Dict[str, Any]]) -> int:
        _, _, meta0 = cand
        score = 0
        if (cand[0], cand[1], id(cand[2])) in primary_set:
            score += 60
        elif s1n:
            # Same sign1 fallback is allowed, but should not dominate exact sign2 match
            score += 10

        for e in (meta0.get("enums") or []):
            if not isinstance(e, dict):
                continue
            slot = e.get("slot")
            if not isinstance(slot, int):
                continue
            it = items_by_slot.get(slot)
            if not it:
                continue
            picked = _extract_enum_label(it)
            if not picked:
                if _is_placeholder_item(it):
                    continue
                continue
            opts = e.get("options") or {}
            if _match_enum_option_key(opts, picked):
                score += 35
            else:
                score -= 90
        for p in (meta0.get("params") or []):
            if not isinstance(p, dict):
                continue
            slot = p.get("slot")
            if not isinstance(slot, int) or slot not in items_by_slot:
                continue
            it = items_by_slot.get(slot)
            if not isinstance(it, dict):
                continue
            if _is_placeholder_item(it):
                continue
            v, ws = _item_to_arg_value(str(p.get("mode") or ""), it)
            if v is not None and not ws:
                score += 12
            elif v is not None:
                score += 4
            else:
                score -= 6
        return score

    best = candidates[0]
    best_score = _score_candidate(best)
    for cand in candidate_pool[1:]:
        sc = _score_candidate(cand)
        if sc > best_score:
            best = cand
            best_score = sc

    module, alias, meta = best
    if not has_chest:
        warns.append("у блока нет сундука параметров (hasChest=false) — аргументы восстановить нельзя")
        return f"{module}.{alias}()", warns
    if not isinstance(items, list) or not items:
        warns.append("сундук параметров пустой/не детектирован (chestItems/slots пусты) — аргументы восстановить нельзя")
        return f"{module}.{alias}()", warns

    params = meta.get("params") or []
    enums = meta.get("enums") or []
    primary_module, primary_alias, primary_meta = candidates[0]
    if (module, alias) != (primary_module, primary_alias):
        warns.append(
            "автоподбор действия по сундуку: "
            f"from={primary_module}.{primary_alias} ('{primary_meta.get('sign1','')} | {primary_meta.get('sign2','')}') "
            f"-> to={module}.{alias} ('{meta.get('sign1','')} | {meta.get('sign2','')}')"
        )

    if not params and not enums:
        return f"{module}.{alias}()", warns

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
        key = _match_enum_option_key(opts, picked)
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

    # Diagnostic for multipage GUIs: if export has real items not described in api_aliases,
    # surface them explicitly so users see why args/enums were dropped.
    mapped_slots = set(params_by_slot.keys()) | set(enums_by_slot.keys())
    unresolved: List[Tuple[int, Dict[str, Any]]] = []
    for slot, it in sorted(items_by_slot.items(), key=lambda x: x[0]):
        if slot in mapped_slots:
            continue
        if _is_placeholder_item(it):
            continue
        unresolved.append((slot, it))

    if unresolved:
        hi = sum(1 for slot, _ in unresolved if slot >= 54)
        warns.append(
            f"api_aliases не покрывает часть слотов: mapped={len(mapped_slots)} unresolved={len(unresolved)} unresolvedPage2plus={hi}"
        )
        if hi > 0 and "1 из 5" in str(meta.get("gui") or ""):
            warns.append(
                "похоже используется схема GUI '1 из N' из api_aliases; слоты 2+ страниц не описаны и не будут конвертированы в аргументы"
            )
        enum_like: List[str] = []
        for slot, it in unresolved:
            picked = _extract_enum_label(it)
            if not picked:
                continue
            title = strip_colors(str(it.get("displayName") or "")).strip()
            enum_like.append(f"slot={slot} title={title!r} value={picked!r}")
            if len(enum_like) >= 8:
                break
        if enum_like:
            warns.append("нераспознанные enum-слоты: " + "; ".join(enum_like))

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
        name = s2.strip() or s1.strip()
        if not name:
            return "event() {"
        return f"event({_json_str(name)}) {{"
    if block == "minecraft:lapis_block":
        name = s2.strip() or s1.strip()
        if not name:
            name = f"func_noaction_{row_index}"
        return f"func({name}) {{"
    if block == "minecraft:emerald_block":
        name = s2.strip() or s1.strip()
        if not name:
            name = f"loop_noaction_{row_index}"
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
        blocks_src = row.get("blocks") or []
        blocks: List[Dict[str, Any]] = [b for b in blocks_src if isinstance(b, dict)]
        # Deterministic order: process raw exported blocks from right to left (X desc).
        blocks.sort(
            key=lambda b: int(((b.get("pos") or {}).get("x") if isinstance(b.get("pos"), dict) else -10**9)),
            reverse=True,
        )

        if not blocks:
            continue
        lines.append(_row_header(blocks[0], ri))
        indent = 1
        # Strict K+ iterator by geometry:
        # entryX(p) = x0 - 2*p, sideX(p)=entryX-1.
        # side piston facing +x opens "{", facing -x closes "}".
        by_x: Dict[int, List[Dict[str, Any]]] = {}
        x_vals: List[int] = []
        for b in blocks[1:]:
            p = b.get("pos") if isinstance(b.get("pos"), dict) else {}
            x = p.get("x") if isinstance(p, dict) else None
            if isinstance(x, int):
                by_x.setdefault(x, []).append(b)
                x_vals.append(x)
        p0 = blocks[0].get("pos") if isinstance(blocks[0].get("pos"), dict) else {}
        x0 = p0.get("x") if isinstance(p0, dict) else None

        if not isinstance(x0, int) or not x_vals:
            raise ValueError(
                f"row[{ri}] has no valid geometry for strict parser: "
                f"x0={x0!r}, parsed_x_count={len(x_vals)}"
            )

        min_x = min(x_vals)
        # Enough steps to cover all seen blocks + small tail.
        max_steps = max(0, ((x0 - min_x) // 2) + 4)
        for p in range(1, max_steps + 1):
                entry_x = x0 - 2 * p
                side_x = entry_x - 1
                entry_list = by_x.get(entry_x, [])
                side_list = by_x.get(side_x, [])
                entry_block: Optional[Dict[str, Any]] = None
                for cand in entry_list:
                    bid = str(cand.get("block") or "")
                    if bid not in ("minecraft:piston", "minecraft:sticky_piston"):
                        entry_block = cand
                        break
                side_piston: Optional[Dict[str, Any]] = None
                for cand in side_list:
                    bid = str(cand.get("block") or "")
                    if bid in ("minecraft:piston", "minecraft:sticky_piston"):
                        side_piston = cand
                        break

                # 1) Emit entry action/condition (if any) for this step.
                if entry_block is not None:
                    sign = entry_block.get("sign") or ["", "", "", ""]
                    sign1 = (sign[0] if len(sign) > 0 else "") or ""
                    sign2 = (sign[1] if len(sign) > 1 else "") or ""
                    pad = "    " * indent
                    if "иначе" in _norm_key_variants(sign2) or "иначе" in _norm_key_variants(sign1):
                        lines.append(pad + "else")
                    else:
                        call, warns = _render_call_from_block(idx, entry_block)
                        for w in warns:
                            lines.append(pad + f"# WARN: {w}")
                        lines.append(pad + call)

                # 2) Emit brace token from side piston for this step.
                if side_piston is not None:
                    facing = str(side_piston.get("facing") or "").lower()
                    # Strict rule from K+ layout:
                    # side piston at -1X, facing west -> opens "{"
                    # side piston at -1X, facing east -> closes "}"
                    if facing == "west":
                        lines.append(("    " * indent) + "{")
                        indent += 1
                    elif facing == "east":
                        if indent > 1:
                            indent -= 1
                            lines.append(("    " * indent) + "}")

        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


