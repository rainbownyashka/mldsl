import json
import re
from pathlib import Path

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


def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    # Fix common mojibake where cp1251 bytes were decoded as latin-1 (àáâ...)
    text = text.translate(
        str.maketrans(
            {
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
        )
    )
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
    if "выбрать объект" in s:
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


def guess_param_base_v2(arg: dict) -> str:
    """
    Prefer using the extracted `mode` instead of brittle glass-name heuristics.

    Glass names in the export can be garbled depending on encoding, while `mode`
    is derived from the glass meta + GUI layout.
    """
    name = strip_colors(arg.get("glassName", "")).lower()
    mode = (arg.get("mode") or "").lower()

    if "блок" in name:
        return "block"
    if "предмет" in name:
        return "item"

    if mode == "variable":
        return "var"
    if mode == "text":
        return "text"
    if mode == "number":
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


def build_params(action: dict) -> list[dict]:
    params = []
    used = {}
    for arg in action.get("args", []):
        base = guess_param_base_v2(arg)
        used.setdefault(base, 0)
        used[base] += 1
        name = base if used[base] == 1 else f"{base}{used[base]}"
        params.append({"name": name, "mode": arg.get("mode"), "slot": arg.get("argSlot")})
    return params


def merge_params(primary: list[dict] | None, extra: list[dict] | None, *, overwrite: bool = False) -> list[dict]:
    """
    Merge two param lists by param `name`.
    - If overwrite=False: keep primary's slot/mode for existing names; only append new names from extra.
    - If overwrite=True: replace existing names in primary with extra's slot/mode; append new names.
    """
    if not primary:
        return list(extra or [])
    if not extra:
        return list(primary)

    out = list(primary)
    idx_by_name: dict[str, int] = {}
    for i, p in enumerate(out):
        n = p.get("name")
        if isinstance(n, str) and n:
            idx_by_name.setdefault(n, i)

    for p in extra:
        n = p.get("name")
        if not isinstance(n, str) or not n:
            continue
        if n in idx_by_name:
            if overwrite:
                out[idx_by_name[n]] = p
            continue
        idx_by_name[n] = len(out)
        out.append(p)

    return out


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
            {"name": "text" if i == 0 else f"text{i+1}", "mode": "TEXT", "slot": slot}
            for i, slot in enumerate(slots)
        ]

    # Game action: "Заполнить область" (Fill region with blocks).
    # Some snapshots export too many LOCATION slots; provide a stable mapping for the core arguments.
    if englishish_alias(sign2) in {"zapolnit_oblast", "zapolnit_oblast_blokami"}:
        return [
            {"name": "value", "mode": "ANY", "slot": 13},
            {"name": "block", "mode": "ITEM", "slot": 13},
            {"name": "loc", "mode": "LOCATION", "slot": 19},
            {"name": "loc2", "mode": "LOCATION", "slot": 25},
            {"name": "num", "mode": "NUMBER", "slot": 40},
        ]

    # Game action: "Поставить блок(и)" (Place blocks at locations).
    # Export sometimes misses the ITEM slot for the block itself; add it.
    if englishish_alias(sign2) in {"postavit_blok", "postavit_blok_i"}:
        return [
            {"name": "var", "mode": "VARIABLE", "slot": 1},
            {"name": "value", "mode": "ANY", "slot": 4},
            {"name": "block", "mode": "ITEM", "slot": 4},
            {"name": "num", "mode": "NUMBER", "slot": 7},
            {"name": "loc", "mode": "LOCATION", "slot": 18},
            {"name": "loc2", "mode": "LOCATION", "slot": 19},
            {"name": "loc3", "mode": "LOCATION", "slot": 20},
            {"name": "loc4", "mode": "LOCATION", "slot": 21},
            {"name": "loc5", "mode": "LOCATION", "slot": 22},
            {"name": "loc6", "mode": "LOCATION", "slot": 23},
            {"name": "loc7", "mode": "LOCATION", "slot": 24},
            {"name": "loc8", "mode": "LOCATION", "slot": 25},
            {"name": "loc9", "mode": "LOCATION", "slot": 26},
        ]

    return None


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
    api: dict[str, dict[str, dict]] = {}
    collisions: dict[str, int] = {}
    translations = load_translations()

    for action in catalog:
        signs = action.get("signs") or ["", "", "", ""]
        sign1 = strip_colors(signs[0]).strip()
        sign2 = strip_colors(signs[1]).strip()
        gui = strip_colors(action.get("gui", "")).strip()
        # Clickable GUI item name comes from the item display name (subitem), with a fallback to category.
        # We also prefer this "menu" name for canonical API naming because sign2 is often shortened
        # ("Правый клик") while the GUI item title is more descriptive ("Игрок кликает правой кнопкой").
        menu = parse_item_display_name(action.get("subitem") or action.get("category") or "")
        action_id = action.get("id", "")
        module = module_for_sign1(sign1)
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
        if final_name in api[module]:
            collisions.setdefault(f"{module}.{final_name}", 0)
            collisions[f"{module}.{final_name}"] += 1
            final_name = f"{final_name}_{collisions[f'{module}.{final_name}']}"
        # Include aliases from both:
        # - sign2/gui (what player sees on sign / in docs)
        # - menu (what player clicks in the GUI item list)
        menu_aliases = {englishish_alias(menu), rus_ident(menu)}
        # Params must come from the exported params-chest snapshot only (glass markers),
        # otherwise we mask bad parsing with hard-coded fallbacks.
        merged_params = build_params(action)
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
                    rus_ident(gui),
                    *[a for a in menu_aliases if a],
                }
            ),
            "description": extract_description(action),
            "descriptionRaw": extract_description_raw(action),
            "params": merged_params,
            "enums": build_enums(action),
        }

    OUT_API.write_text(json.dumps(api, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_API} modules={len(api)}")


if __name__ == "__main__":
    main()
