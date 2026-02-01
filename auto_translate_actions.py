import json
import re
from pathlib import Path

from mldsl_paths import action_translations_by_id_path, actions_catalog_path, ensure_dirs

CATALOG_PATH = actions_catalog_path()
OUT_PATH = action_translations_by_id_path()


def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    return text


def snake(text: str) -> str:
    t = strip_colors(text).lower()
    t = t.replace("(", " ").replace(")", " ")
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    if not t:
        return "unnamed"
    if t[0].isdigit():
        t = "a_" + t
    return t


def module_for_sign1(sign1: str) -> str:
    s = strip_colors(sign1).strip().lower()
    if "действие игрока" in s:
        return "player"
    if "игровое действие" in s:
        return "game"
    if "выбрать объект" in s:
        return "select"
    if "массив" in s:
        return "array"
    if "присв" in s or "установить переменную" in s or s == "переменную":
        return "var"
    if s.startswith("если "):
        if "игра" in s:
            return "if_game"
        if "игрок" in s:
            return "if_player"
        if "существо" in s or "сущ" in s or "моб" in s:
            return "if_entity"
        if "значение" in s or "переменная" in s:
            return "if_value"
        return "if"
    return "misc"


def translate_name(sign2_or_gui: str) -> str:
    s = strip_colors(sign2_or_gui).strip().lower()

    # normalize common punctuation
    s = re.sub(r"[’'`]", "", s)
    s = s.replace("эндер сундук", "ender_chest")
    s = s.replace("эндер-сундук", "ender_chest")

    # phrase-level replacements (rough, but stable)
    phrases = [
        ("вызвать функцию", "call_function"),
        ("установить переменную", "set_var"),
        ("присв. переменную", "set_var"),
        ("присвоить переменную", "set_var"),
        ("очистить инвентарь", "clear_inventory"),
        ("удалить предметы", "remove_items"),
        ("выдать предметы", "give_items"),
        ("выдать предмет", "give_item"),
        ("надеть броню", "equip_armor"),
        ("отправить сообщение", "message"),
        ("сообщение", "message"),
        ("телепортировать", "teleport"),
        ("телепорт", "teleport"),
        ("установить предмет", "set_item"),
        ("установить предметы", "set_items"),
        ("поставить предмет", "place_item"),
        ("урон", "damage"),
        ("исцел", "heal"),
        ("объединить тексты", "concat_texts"),
        ("объединить текст", "concat_texts"),
    ]
    for a, b in phrases:
        if a in s:
            return b

    # word-level rough dictionary
    words = re.split(r"[\s_/]+", s)
    mapped = []
    dict_words = [
        ("выдать", "give"),
        ("дать", "give"),
        ("установ", "set"),
        ("присв", "set"),
        ("удал", "remove"),
        ("очист", "clear"),
        ("получ", "get"),
        ("добав", "add"),
        ("созда", "create"),
        ("сохран", "save"),
        ("загруз", "load"),
        ("отправ", "send"),
        ("сообщ", "message"),
        ("телепорт", "teleport"),
        ("урон", "damage"),
        ("исцел", "heal"),
        ("предмет", "item"),
        ("предметы", "items"),
        ("инвент", "inventory"),
        ("брон", "armor"),
        ("текст", "text"),
        ("тексты", "texts"),
        ("числ", "number"),
        ("перемен", "var"),
        ("массив", "array"),
        ("местополож", "location"),
        ("функц", "function"),
        ("игрок", "player"),
        ("существо", "entity"),
    ]
    stop = {"в", "на", "по", "для", "и", "или", "с", "со", "из", "к", "от", "до", "это", "все"}
    for w in words:
        w = re.sub(r"[^a-z0-9\u0400-\u04FF]+", "", w)
        if not w or w in stop:
            continue
        out = None
        for a, b in dict_words:
            if w.startswith(a):
                out = b
                break
        mapped.append(out or w)

    res = "_".join(mapped)
    res = re.sub(r"_+", "_", res).strip("_")
    return snake(res)


def main():
    ensure_dirs()
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            "Не найден `actions_catalog.json`.\n"
            f"Путь: {CATALOG_PATH}\n"
            "Сначала запусти: python tools/build_actions_catalog.py"
        )
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    out = {}
    used = {}
    for action in catalog:
        action_id = action.get("id")
        if not action_id:
            continue
        signs = action.get("signs") or ["", "", "", ""]
        sign1 = signs[0] if signs else ""
        sign2 = signs[1] if len(signs) > 1 else ""
        gui = action.get("gui", "") or ""
        module = module_for_sign1(sign1)
        base = translate_name(sign2 or gui)
        used.setdefault(module, {})
        used[module].setdefault(base, 0)
        used[module][base] += 1
        name = base if used[module][base] == 1 else f"{base}_{used[module][base]}"

        out[action_id] = {
            "name": name,
            "aliases": [
                strip_colors(sign2 or gui).strip(),
            ],
        }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH} actions={len(out)}")


if __name__ == "__main__":
    main()
