import json
import re
from pathlib import Path

from _bootstrap import ensure_repo_root_on_syspath

ensure_repo_root_on_syspath()

from mldsl_paths import (
    action_translations_by_id_path,
    action_translations_path,
    actions_catalog_path,
    api_aliases_path,
    ensure_dirs,
)

CATALOG_PATH = actions_catalog_path()
OUT_API = api_aliases_path()
TRANSLATIONS_PATH = action_translations_path()
TRANSLATIONS_BY_ID_PATH = action_translations_by_id_path()


_MOJIBAKE_MAP = {
        "à": "а",
        "á": "б",
        "â": "в",
        "ã": "г",
        "ä": "д",
        "å": "е",
        "¸": "ё",
        "æ": "ж",
        "ç": "з",
        "è": "и",
        "é": "й",
        "ê": "к",
        "ë": "л",
        "ì": "м",
        "í": "н",
        "î": "о",
        "ï": "п",
        "ð": "р",
        "ñ": "с",
        "ò": "т",
        "ó": "у",
        "ô": "ф",
        "õ": "х",
        "ö": "ц",
        "ø": "ш",
        "ù": "щ",
        "ú": "ъ",
        "û": "ы",
        "ü": "ь",
        "ý": "э",
        "þ": "ю",
        "ÿ": "я",
        "À": "А",
        "Á": "Б",
        "Â": "В",
        "Ã": "Г",
        "Ä": "Д",
        "Å": "Е",
        "¨": "Ё",
        "Æ": "Ж",
        "Ç": "З",
        "È": "И",
        "É": "Й",
        "Ê": "К",
        "Ë": "Л",
        "Ì": "М",
        "Í": "Н",
        "Î": "О",
        "Ï": "П",
        "Ð": "Р",
        "Ñ": "С",
        "Ò": "Т",
        "Ó": "У",
        "Ô": "Ф",
        "Õ": "Х",
        "Ö": "Ц",
        "×": "Ч",
        "Ø": "Ш",
        "Ù": "Щ",
        "Ú": "Ъ",
        "Û": "Ы",
        "Ü": "Ь",
        "Ý": "Э",
        "Þ": "Ю",
        "ß": "Я",
}
_MOJIBAKE_TRANS = str.maketrans(_MOJIBAKE_MAP)
_MOJIBAKE_CHARS = set(_MOJIBAKE_MAP.keys())


def _looks_like_mojibake(text: str) -> bool:
    if not text:
        return False
    if "÷" in text:
        return False
    if any("\u0400" <= ch <= "\u04FF" for ch in text):
        return False
    hit = sum(1 for ch in text if ch in _MOJIBAKE_CHARS)
    return hit >= 2


def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    if _looks_like_mojibake(text):
        text = text.translate(_MOJIBAKE_TRANS)
    return text


_TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

CYR_TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def translit(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(CYR_TRANSLIT.get(ch, _TRANSLIT.get(ch, ch)))
    return "".join(out)


def snake(text: str) -> str:
    t = strip_colors(text)
    t = translit(t)
    t = t.replace("(", " ").replace(")", " ")
    t = re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")
    if not t:
        return "unnamed"
    if t[0].isdigit():
        t = "a_" + t
    return t


def rus_ident(text: str) -> str:
    t = strip_colors(text)
    t = t.strip().lower()
    t = t.replace("(", " ").replace(")", " ")
    # keep cyrillic/latin/digits/underscore, replace everything else with _
    t = re.sub(r"[^\w\u0400-\u04FF]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t or "unnamed"


def module_for_sign1(sign1: str) -> str:
    s = strip_colors(sign1).strip().lower()
    # draft mapping; tweak later
    if "действие игрока" in s:
        return "player"
    if "игровое действие" in s:
        return "game"
    if "выбрать объект" in s or "выбрать обьект" in s:
        return "select"
    if "массив" in s:
        return "array"
    if "присв" in s or "установить переменную" in s or "переменную" == s:
        return "var"
    if s.startswith("если "):
        if "игра" in s:
            return "if_game"
        if "игрок" in s:
            return "if_player"
        if "существо" in s or "существ" in s or "моб" in s or "сущ" in s:
            return "if_entity"
        if "значение" in s or "значен" in s or "переменная" in s or "перемен" in s:
            return "if_value"
        return "if"
    return "misc"

def extract_description(action: dict) -> str:
    raw = action.get("subitem") or action.get("category") or ""
    raw = strip_colors(raw)
    raw = raw.replace("\\n", "\n")
    if " | " in raw:
        raw = raw.split(" | ", 1)[1]
    raw = raw.strip()
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw


def extract_description_raw(action: dict) -> str:
    raw = action.get("subitem") or action.get("category") or ""
    raw = raw.replace("\\n", "\n")
    if " | " in raw:
        raw = raw.split(" | ", 1)[1]
    raw = raw.strip()
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw


def guess_param_base(arg: dict) -> str:
    name = strip_colors(arg.get("glassName", "")).lower()
    mode = (arg.get("mode") or "").lower()
    if "динамическ" in name or "переменн" in name:
        return "var"
    if "текст" in name:
        return "text"
    if "числ" in name:
        return "num"
    if mode == "location":
        return "loc"
    if mode == "array":
        return "arr"
    if mode == "item":
        return "item"
    if mode == "any":
        return "value"
    return mode or "arg"


def extract_param_label(arg: dict) -> str:
    """
    Build a human-readable per-param label from GUI glass marker text.
    Examples:
      "Число* - Шанс выпадения шлема" -> "Шанс выпадения шлема"
      "Текст* - Имя сущности" -> "Имя сущности"
      "Местоположение(я)" -> "Местоположение(я)"
    """
    raw = strip_colors(arg.get("glassName", "")).strip()
    if not raw:
        return ""
    # Remove optional marker often used in these UIs.
    raw = raw.replace("*", "").strip()
    if " - " in raw:
        left, right = raw.split(" - ", 1)
        # Only treat known type-prefixes as structural markers.
        left_norm = left.strip().lower()
        if left_norm in {"число", "текст", "предмет", "массив", "местоположение", "местоположение(я)", "переменная"}:
            label = right.strip()
            return label or raw
    return raw


def build_params(action: dict) -> list[dict]:
    params = []
    used = {}
    for arg in action.get("args", []):
        base = guess_param_base(arg)
        used.setdefault(base, 0)
        used[base] += 1
        name = base if used[base] == 1 else f"{base}{used[base]}"
        params.append(
            {
                "name": name,
                "mode": arg.get("mode"),
                "slot": arg.get("argSlot"),
                # AGENT_TAG: param_label_from_glass
                # Preserve the user-facing meaning from regallactions merged chest pages.
                "label": extract_param_label(arg),
            }
        )
    return params


def build_params_fallback(sign1: str, sign2: str) -> list[dict] | None:
    """
    Some records in regallactions_export.txt can have broken chest snapshots (e.g. cached category menu
    instead of params chest). For a few high-value actions, provide a pragmatic fallback slot map so the
    DSL compiler can still generate useful /placeadvanced commands.
    """
    s1 = strip_colors(sign1).strip().lower()
    s2 = strip_colors(sign2).strip().lower()

    # Player action: "Сообщение" (Send message)
    # Common params chest layout matches other "text(ы)" actions: 8 text slots around the center.
    if s1 == "действие игрока" and s2 == "сообщение":
        slots = [27, 28, 29, 30, 32, 33, 34, 35]
        return [
            {
                "name": "text" if i == 0 else f"text{i+1}",
                "mode": "TEXT",
                "slot": slot,
                "label": "Текст сообщения",
            }
            for i, slot in enumerate(slots)
        ]

    # Game action: "Заполнить область" (Fill region with blocks)
    # In some exports, the chest snapshot is missing the yellow block/item input.
    # Provide a stable mapping matching the in-game GUI:
    # - value (ANY) at slot 13 (yellow glass marker)
    # - loc (LOCATION) at slot 19
    # - loc2 (LOCATION) at slot 25
    # - num (NUMBER) at slot 40 (mode/meta)
    if s1 == "игровое действие" and s2 == "заполнить область":
        return [
            {"name": "value", "mode": "ANY", "slot": 13, "label": "Значение/блок"},
            {"name": "loc", "mode": "LOCATION", "slot": 19, "label": "Первая точка области"},
            {"name": "loc2", "mode": "LOCATION", "slot": 25, "label": "Вторая точка области"},
            {"name": "num", "mode": "NUMBER", "slot": 40, "label": "Режим заполнения"},
        ]

    return None


def merge_params(primary: list[dict], extra: list[dict]) -> list[dict]:
    """
    Merge `extra` params into `primary` without duplicating by slot.
    Used when export snapshots missed some marker glass, but we still want stable slots.
    """
    out = list(primary or [])
    seen_slots = {p.get("slot") for p in out if isinstance(p, dict)}
    for p in extra or []:
        if not isinstance(p, dict):
            continue
        slot = p.get("slot")
        if slot in seen_slots:
            continue
        out.append(p)
        seen_slots.add(slot)
    return out


def select_scope_from_sign2(sign2: str) -> str | None:
    s2 = strip_colors(sign2).strip().lower()
    if "игрок" in s2 and "по условию" in s2:
        return "ifplayer"
    if "моб" in s2 and "по условию" in s2:
        return "ifmob"
    if "сущност" in s2 and "по условию" in s2:
        return "ifentity"
    return None


def normalize_label_key(label: str) -> str:
    s = strip_colors(label).lower().strip()
    s = re.sub(r"[\s_\\-]+", " ", s)
    return s


def canonical_base_for_mode(mode: str) -> str:
    m = strip_colors(mode).strip().upper()
    if m == "VARIABLE":
        return "var"
    if m == "TEXT":
        return "text"
    if m == "NUMBER":
        return "num"
    if m == "LOCATION":
        return "loc"
    if m == "ARRAY":
        return "arr"
    if m == "ITEM":
        return "item"
    if m == "ANY":
        return "value"
    return "arg"


def canonicalize_param_names(params: list[dict]) -> list[dict]:
    out = list(params or [])
    counters: dict[str, int] = {}
    for p in out:
        base = canonical_base_for_mode(str((p or {}).get("mode") or ""))
        counters[base] = counters.get(base, 0) + 1
        p["name"] = base if counters[base] == 1 else f"{base}{counters[base]}"
    return out


def normalize_semantic_params(context: dict, params: list[dict]) -> tuple[list[dict], bool]:
    """
    Generic semantic dedup:
    - group by (mode, normalized_label)
    - keep minimal slot in each duplicate semantic group
    - canonicalize param names by mode
    """
    out = [dict(p) for p in (params or []) if isinstance(p, dict)]
    changed = False

    # Special semantic guard: "Переменная существует" must keep only one VARIABLE input.
    s1 = strip_colors(str(context.get("sign1") or "")).strip().lower()
    s2 = strip_colors(str(context.get("sign2") or "")).strip().lower()
    gui = strip_colors(str(context.get("gui") or "")).strip().lower()
    menu = strip_colors(str(context.get("menu") or "")).strip().lower()
    scope = select_scope_from_sign2(s2)
    is_var_exists = (
        (s1 == "если переменная" and s2 == "переменная существует")
        or (
            scope is not None
            and (gui == "переменная существует" or menu == "переменная существует" or s2 == "переменная существует")
        )
    )
    if is_var_exists:
        vars_only = [p for p in out if str((p or {}).get("mode") or "").upper() == "VARIABLE"]
        if len(vars_only) > 1:
            vars_only = sorted(vars_only, key=lambda p: int((p or {}).get("slot") or 10**9))
            keep_slot = int((vars_only[0] or {}).get("slot") or 0)
            new_out = []
            for p in out:
                if str((p or {}).get("mode") or "").upper() != "VARIABLE":
                    new_out.append(p)
                    continue
                if int((p or {}).get("slot") or 0) == keep_slot:
                    p["name"] = "var"
                    new_out.append(p)
                else:
                    changed = True
            out = new_out

    # Keep stable canonical names while preserving legitimate multi-slot actions.
    canon = canonicalize_param_names(out)
    if canon != out:
        changed = True
    out = canon
    return out, changed


def normalize_params_for_action(
    module: str,
    sign1: str,
    sign2: str,
    gui: str,
    menu: str,
    params: list[dict],
) -> tuple[list[dict], bool]:
    """
    Normalize known duplicated parameter patterns from regallactions exports.
    Some actions occasionally expose mirrored GUI markers that map to the same semantic input.
    """
    context = {
        "module": module,
        "sign1": sign1,
        "sign2": sign2,
        "gui": gui,
        "menu": menu,
    }
    return normalize_semantic_params(context, params)


def guess_enum_name(enum_item: dict) -> str:
    n = strip_colors(enum_item.get("name", "")).lower()
    if "синхрон" in n or "асинхрон" in n:
        return "async"
    if "запуск" in n and "функц" in n:
        return "async"
    if "раздел" in n:
        return "separator"
    if "учитывать" in n and "пуст" in n:
        return "include_empty"
    return snake(enum_item.get("name", ""))[:32]


def englishish_alias(text: str) -> str:
    s = strip_colors(text).strip().lower()
    replacements = [
        ("сообщение", "message"),
        ("выдать", "give"),
        ("установить", "set"),
        ("присв", "set"),
        ("удалить", "remove"),
        ("телепорт", "teleport"),
        ("урон", "damage"),
        ("исцел", "heal"),
        ("предмет", "item"),
        ("инвентарь", "inventory"),
        ("брон", "armor"),
        ("функц", "function"),
    ]
    for a, b in replacements:
        s = s.replace(a, b)
    return snake(s)


def parse_item_display_name(raw: str) -> str:
    """
    catalog 'subitem' looks like:
      [minecraft:quartz_stairs meta=0] §cСравнить числа | §7...
    We need the clickable menu name: "Сравнить числа".
    """
    if not raw:
        return ""
    s = strip_colors(raw)
    if "]" in s:
        s = s.split("]", 1)[1]
    s = s.strip()
    if "|" in s:
        s = s.split("|", 1)[0].strip()
    return s


def strip_page_suffix(text: str) -> str:
    """
    Remove GUI page suffix like "(5 из 5)" to keep stable aliases.
    """
    s = strip_colors(text).strip()
    s = re.sub(r"\(\s*\d+\s+из\s+\d+\s*\)\s*$", "", s, flags=re.IGNORECASE).strip()
    return s


def menu_short_aliases(menu: str) -> set[str]:
    """
    For menu strings like "Заспавнить моба/сущность" add useful short aliases:
    - "заспавнить_моба"
    - "заспавнить_моба_сущность"
    """
    out: set[str] = set()
    base = strip_page_suffix(menu)
    if not base:
        return out
    out.add(rus_ident(base))
    out.add(englishish_alias(base))
    if "/" in base:
        left = base.split("/", 1)[0].strip()
        if left:
            out.add(rus_ident(left))
            out.add(englishish_alias(left))
    return {a for a in out if a}


def load_translations():
    merged = {}
    # Autogenerated by-id translations are a baseline; manual translations override them.
    for path in [TRANSLATIONS_BY_ID_PATH, TRANSLATIONS_PATH]:
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                merged.update(json.load(f))
        except Exception:
            continue
    return merged


def build_enums(action: dict) -> list[dict]:
    out = []
    for enum_item in action.get("enums", []):
        var = enum_item.get("variant") or {}
        options = var.get("options") or []
        out.append(
            {
                "name": guess_enum_name(enum_item),
                "slot": enum_item.get("slot"),
                "options": {strip_colors(o).strip(): i for i, o in enumerate(options)},
            }
        )
    return out


def build_api_from_catalog(catalog: list[dict], translations: dict | None = None) -> dict:
    api: dict[str, dict[str, dict]] = {}
    collisions: dict[str, int] = {}
    translations = translations or {}

    for action in catalog:
        signs = action.get("signs") or ["", "", "", ""]
        sign1 = strip_colors(signs[0]).strip()
        sign2 = strip_colors(signs[1]).strip()
        gui = strip_colors(action.get("gui", "")).strip()
        # Clickable GUI item name comes from the item display name (subitem), with a fallback to category.
        # Prefer this for canonical API naming: sign2 is often shortened ("Правый клик"), while
        # menu name is descriptive ("Игрок кликает правой кнопкой").
        menu = parse_item_display_name(action.get("subitem") or action.get("category") or "")
        action_id = action.get("id", "")
        module = module_for_sign1(sign1)
        scope = select_scope_from_sign2(sign2) if module == "select" else None
        var_operator_funcs = {
            "=": "set_value",
            "+": "set_sum",
            "-": "set_difference",
            "*": "set_product",
            "/": "set_quotient",
        }
        if module == "var" and sign2 in var_operator_funcs:
            func = var_operator_funcs[sign2]
        else:
            base = menu or sign2 or gui
            func = snake(base)
        legacy_func = snake(sign2 or gui)

        api.setdefault(module, {})
        canonical = translations.get(action_id) or translations.get(f"{module}.{func}") or {}
        name_override = canonical.get("name")
        alias_override = canonical.get("aliases") or []
        reserved_names = {
            "player",
            "event",
            "game",
            "var",
            "array",
            "misc",
            "if_player",
            "if_game",
            "if_value",
        }
        if isinstance(name_override, str) and name_override.strip().lower() in reserved_names:
            name_override = None
        final_name = name_override or func
        # Canonical naming for conditional select domain.
        if module == "select" and scope:
            final_name = f"{scope}_{func}"
        if final_name in api[module]:
            collisions.setdefault(f"{module}.{final_name}", 0)
            collisions[f"{module}.{final_name}"] += 1
            final_name = f"{final_name}_{collisions[f'{module}.{final_name}']}"
        # Include aliases from both:
        # - sign2/gui (what player sees on sign / in docs)
        # - menu (what player clicks in the GUI item list)
        menu_aliases = menu_short_aliases(menu)
        gui_clean = strip_page_suffix(gui)
        merged_params = merge_params(
            build_params(action) or [],
            build_params_fallback(sign1, sign2) or [],
        )
        normalized_params, params_changed = normalize_params_for_action(module, sign1, sign2, gui, menu, merged_params)
        extra_aliases = set()
        if name_override and name_override != final_name:
            extra_aliases.add(name_override)
        if module == "select" and scope:
            # Keep historical names bridge for completion compatibility.
            extra_aliases.add(func)
            extra_aliases.add(legacy_func)
        api[module][final_name] = {
            "id": action.get("id"),
            "sign1": sign1,
            "sign2": sign2,
            "gui": gui,
            "menu": menu,
            "aliases": sorted(
                {
                    final_name,
                    *alias_override,
                    legacy_func,
                    englishish_alias(sign2 or gui),
                    rus_ident(sign2 or gui),
                    rus_ident(gui_clean),
                    englishish_alias(gui_clean),
                    *[a for a in menu_aliases if a],
                    *[a for a in extra_aliases if a],
                }
            ),
            "description": extract_description(action),
            "descriptionRaw": extract_description_raw(action),
            "params": normalized_params,
            "enums": build_enums(action),
            "meta": {
                "paramSource": "normalized" if params_changed else "raw",
            },
        }

    return api


def validate_api_contract(api: dict) -> None:
    select_mod = api.get("select")
    if not isinstance(select_mod, dict) or not select_mod:
        raise ValueError(
            "api_aliases contract violation: module `select` must exist and be non-empty. "
            "Rebuild via `python tools/build_api_aliases.py` from fresh actions_catalog."
        )

    has_ifplayer = any(str(k).startswith("ifplayer_") for k in select_mod.keys())
    has_ifmob = any(str(k).startswith("ifmob_") for k in select_mod.keys())
    has_ifentity = any(str(k).startswith("ifentity_") for k in select_mod.keys())
    if not (has_ifplayer and has_ifmob and has_ifentity):
        raise ValueError(
            "api_aliases contract violation: canonical select domains are incomplete. "
            "Expected keys with prefixes `ifplayer_`, `ifmob_`, `ifentity_`."
        )

    bad_meta: list[str] = []
    for module, funcs in (api or {}).items():
        if not isinstance(funcs, dict):
            continue
        for fname, spec in funcs.items():
            if not isinstance(spec, dict):
                bad_meta.append(f"{module}.{fname}: missing spec object")
                continue
            meta = spec.get("meta")
            if not isinstance(meta, dict):
                bad_meta.append(f"{module}.{fname}: missing meta")
                continue
            src = meta.get("paramSource")
            if src not in {"raw", "normalized"}:
                bad_meta.append(f"{module}.{fname}: invalid meta.paramSource={src!r}")
    if bad_meta:
        sample = "; ".join(bad_meta[:8])
        more = "..." if len(bad_meta) > 8 else ""
        raise ValueError(
            "api_aliases contract violation: each action must carry meta.paramSource in {raw, normalized}. "
            f"Sample: {sample}{more}"
        )


def main():
    ensure_dirs()
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            "Не найден `actions_catalog.json`.\n"
            f"Путь: {CATALOG_PATH}\n"
            "\n"
            "Сначала запусти:\n"
            "  python tools/build_actions_catalog.py\n"
        )
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    translations = load_translations()
    api = build_api_from_catalog(catalog, translations)
    validate_api_contract(api)

    OUT_API.write_text(json.dumps(api, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_API} modules={len(api)}")


if __name__ == "__main__":
    main()
