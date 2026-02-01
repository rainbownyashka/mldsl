import json
import re
from pathlib import Path

from mldsl_paths import actions_catalog_path, api_aliases_path, ensure_dirs, lang_tokens_path

LANG_TOKENS_PATH = lang_tokens_path()
CATALOG_PATH = actions_catalog_path()
API_OUT_PATH = api_aliases_path()

# Расширенный словарь для перевода имен, которые трудно перевести транслитом
# (Английский ключ, который ты хочешь -> Точный текст на русском в игре)
TRANSLATION_DICT = {
    # IF PLAYER
    "Летает": "is_flying",
    "Бежит": "is_sprinting",
    "Приседает": "is_sneaking",
    "На элитрах": "is_gliding",
    "Планирует": "is_gliding", # Вариант
    "На земле": "is_grounded",
    "Плавает": "is_swimming",
    "Блокирует": "is_blocking",
    "Горит": "is_burning",
    "Имеет предмет": "has_item",
    "Держит предмет": "holding_item",
    "Игровой режим": "gamemode",
    "Имя равно": "name_equals",
    "Стоит на блоке": "standing_on",
    "Рядом": "is_near",
    "В регионе": "in_region",
    "Эффект зелья": "potion_effect",
    "Имеет права": "has_permission",
    "Тип взаимодействия": "interaction_type",
    
    # IF GAME
    "Блок равен": "block_equals",
    "Контейнер имеет": "container_has",
    "Табличка содерж.": "sign_contains",
    "День": "is_day",
    "Дождь": "is_raining",
    "Гроза": "is_thundering",
    
    # ACTIONS
    "Сообщение": "message",
    "Выдать предмет": "give_item",
    "Установить переменную": "set_var",
    "Телепортация": "teleport",
    "Телепорт": "teleport"
}

def strip_colors(text: str) -> str:
    text = re.sub(r"\u00a7.", "", text).strip()
    return text

def to_snake_case(text: str) -> str:
    # Русское название -> snake_case (транслит)
    ru_map = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", 
        " ": "_"
    }
    text = strip_colors(text).lower()
    text = re.sub(r"[\s\-]+", "_", text) # Пробелы в _
    text = re.sub(r"[^a-zа-я0-9_]", "", text) # Убрать спецсимволы
    
    out = []
    for char in text:
        out.append(ru_map.get(char, char))
    return "".join(out)

def get_english_key(gui_name: str) -> str:
    """Пытается найти красивое английское имя, иначе транслит"""
    clean_gui = strip_colors(gui_name)
    
    # 1. Проверяем словарь
    if clean_gui in TRANSLATION_DICT:
        return TRANSLATION_DICT[clean_gui]
    
    # 2. Если нет, делаем транслит (stoit_na_bloke)
    return to_snake_case(clean_gui)

def main():
    ensure_dirs()
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            "Не найден `actions_catalog.json`.\n"
            f"Путь: {CATALOG_PATH}\n"
            "Сначала запусти: python tools/build_actions_catalog.py"
        )

    # Загружаем файлы
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        catalog = json.load(f)
    
    # Пытаемся сохранить старые данные API, если есть
    if API_OUT_PATH.exists():
        with open(API_OUT_PATH, 'r', encoding='utf-8') as f:
            api_data = json.load(f)
    else:
        api_data = {}

    api_data.setdefault('if_player', {})
    api_data.setdefault('if_game', {})
    
    # Счетчики
    stats = {"player": 0, "game": 0}

    # Проходим по каталогу (источник правды о именах блоков)
    for action in catalog:
        signs = action.get('signs', ["", "", "", ""])
        sign1 = strip_colors(signs[0]).lower()
        sign2 = strip_colors(signs[1])
        
        # Если sign2 пусто, берем из GUI/Subitem (как в прошлом скрипте)
        if not sign2:
            sign2 = strip_colors(action.get('gui', ''))
            if not sign2 and 'subitem' in action:
                parts = action['subitem'].split('|')
                if len(parts) > 0:
                    raw = parts[0]
                    if ']' in raw: raw = raw.split(']')[1]
                    sign2 = strip_colors(raw).strip()

        if not sign1 or not sign2:
            continue

        target_module = None
        if "если игрок" in sign1:
            target_module = 'if_player'
            stats['player'] += 1
        elif "если игра" in sign1:
            target_module = 'if_game'
            stats['game'] += 1
        
        if target_module:
            # 1. Генерируем Основной Ключ (Английский)
            # Например: "Летает" -> "is_flying"
            main_key = get_english_key(sign2)
            
            # 2. Генерируем Алиасы
            aliases = set()
            aliases.add(main_key) # is_flying
            aliases.add(main_key.replace("_", "")) # isflying
            
            # Добавляем русские алиасы (для удобства)
            ru_snake = to_snake_case(sign2) # letaet (транслит)
            aliases.add(ru_snake)
            
            # Добавляем чистый русский snake_case (летает)
            ru_clean = re.sub(r"\u00a7.", "", sign2).strip().lower().replace(" ", "_")
            ru_clean = re.sub(r"[^а-яa-z0-9_]", "", ru_clean)
            aliases.add(ru_clean)

            # Формируем запись
            entry = {
                "id": action.get('id', 'unknown'),
                "sign1": signs[0],
                "sign2": sign2,      # <-- ВАЖНО: Точное русское имя для компилятора
                "gui": sign2,
                "menu": sign2,
                "aliases": sorted(list(aliases)),
                "description": f"Check: {sign2}",
                "params": action.get('args', []), # Используем аргументы из каталога
                "enums": action.get('enums', [])
            }

            # Сохраняем под основным ключом
            api_data[target_module][main_key] = entry
            
            # Сохраняем под слитным ключом (isflying), чтобы старый код работал
            api_data[target_module][main_key.replace("_", "")] = entry

    with open(API_OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(api_data, f, ensure_ascii=False, indent=2)

    print(f"Готово! Обработано IF_PLAYER: {stats['player']}, IF_GAME: {stats['game']}")
    print(f"Теперь 'if_player.is_flying' и 'if_player.isflying' создадут блок '{TRANSLATION_DICT.get('Летает', 'Летает')}'")

if __name__ == "__main__":
    main()
