import json
import re
from pathlib import Path

from mldsl_paths import action_aliases_path, actions_catalog_path, ensure_dirs

CATALOG_PATH = actions_catalog_path()
ALIASES_OUT = action_aliases_path()


def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
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


def translit(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(_TRANSLIT.get(ch, ch))
    return "".join(out)


def slug(text: str) -> str:
    t = strip_colors(text)
    t = translit(t)
    t = t.replace("(", " ").replace(")", " ")
    t = re.sub(r"[^a-z0-9]+", "_", t.lower())
    t = t.strip("_")
    if not t:
        return "unnamed"
    if t[0].isdigit():
        t = "a_" + t
    return t


def short_id(action_id: str) -> str:
    return action_id.split("|", 1)[0][:8] if action_id else "unknown"


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
    if mode == "any":
        return "value"
    return mode or "arg"


def build_params(action: dict) -> list[dict]:
    params = []
    used = {}
    for arg in action.get("args", []):
        base = guess_param_base(arg)
        used.setdefault(base, 0)
        used[base] += 1
        name = base if used[base] == 1 and base not in ("text",) else f"{base}{used[base]}"
        params.append(
            {
                "name": name,
                "mode": arg.get("mode"),
                "slot": arg.get("argSlot"),
                "glass": {
                    "name": arg.get("glassName"),
                    "meta": arg.get("glassMeta"),
                },
            }
        )
    return params


def guess_enum_name(enum_item: dict) -> str:
    n = strip_colors(enum_item.get("name", "")).lower()
    if "раздел" in n:
        return "separator"
    if "учитывать" in n and "пуст" in n:
        return "include_empty"
    return slug(enum_item.get("name", ""))[:32]


def build_enums(action: dict) -> list[dict]:
    out = []
    for enum_item in action.get("enums", []):
        var = enum_item.get("variant") or {}
        options = var.get("options") or []
        values = {}
        for idx, opt in enumerate(options):
            values[opt] = idx
        out.append(
            {
                "name": guess_enum_name(enum_item),
                "slot": enum_item.get("slot"),
                "options": values,
            }
        )
    return out


def main():
    ensure_dirs()
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            "Не найден `actions_catalog.json`.\n"
            f"Путь: {CATALOG_PATH}\n"
            "Сначала запусти: python tools/build_actions_catalog.py"
        )
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    aliases: dict[str, dict[str, dict]] = {}
    seen_call = set()
    for action in catalog:
        signs = action.get("signs") or ["", "", "", ""]
        group = strip_colors(signs[0]).strip() or "Unknown"
        title = strip_colors(signs[1]).strip() or strip_colors(action.get("gui", "")).strip() or "UnknownAction"
        group_key = slug(group)
        call = slug(title)

        # avoid collisions globally
        if call in seen_call:
            call = f"{call}_{short_id(action.get('id',''))}"
        seen_call.add(call)

        aliases.setdefault(group_key, {})
        aliases[group_key][call] = {
            "id": action.get("id"),
            "sign1": group,
            "sign2": title,
            "gui": strip_colors(action.get("gui", "")).strip(),
            "params": build_params(action),
            "enums": build_enums(action),
        }

    ALIASES_OUT.write_text(json.dumps(aliases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {ALIASES_OUT} groups={len(aliases)} actions={sum(len(v) for v in aliases.values())}")


if __name__ == "__main__":
    main()
