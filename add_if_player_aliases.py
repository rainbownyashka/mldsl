"""
Скрипт для добавления правильных алиасов для if_player функций
"""
import json
from pathlib import Path

from mldsl_paths import api_aliases_path as _api_aliases_path, ensure_dirs, lang_tokens_path as _lang_tokens_path

def add_if_player_aliases():
    ensure_dirs()
    # Загружаем LangTokens.json
    lang_tokens_path = _lang_tokens_path()
    with open(lang_tokens_path, "r", encoding="utf-8") as f:
        lang_data = json.load(f)
    
    # Загружаем api_aliases.json
    api_aliases_path = _api_aliases_path()
    if not api_aliases_path.exists():
        raise FileNotFoundError(
            f"Не найден `api_aliases.json`: {api_aliases_path}\n"
            "Сначала запусти: python tools/build_api_aliases.py"
        )
    with open(api_aliases_path, "r", encoding="utf-8") as f:
        api_data = json.load(f)
    
    # Получаем функции IF_PLAYER из LangTokens.json
    if_player_funcs = lang_data.get('IF_PLAYER', [])
    if_game_funcs = lang_data.get('IF_GAME', [])
    
    print(f"Найдено {len(if_player_funcs)} функций IF_PLAYER в LangTokens.json")
    print(f"Найдено {len(if_game_funcs)} функций IF_GAME в LangTokens.json")
    
    # Создаем маппинг customName -> имя функции
    custom_name_to_func = {}
    for func in if_player_funcs:
        name = func.get('name', '')
        custom_name = func.get('customName', '')
        if name and custom_name:
            custom_name_to_func[custom_name.lower()] = name
            print(f"  IF_PLAYER: {custom_name} -> {name}")
    
    for func in if_game_funcs:
        name = func.get('name', '')
        custom_name = func.get('customName', '')
        if name and custom_name:
            custom_name_to_func[custom_name.lower()] = name
            print(f"  IF_GAME: {custom_name} -> {name}")
    
    # Проверяем модули в api_aliases.json
    if_player_module = api_data.get('if_player', {})
    if_game_module = api_data.get('if_game', {})
    print(f"\nФункций в модуле if_player: {len(if_player_module)}")
    print(f"Функций в модуле if_game: {len(if_game_module)}")
    
    # Создаем новый модуль if_player с правильными именами
    new_if_player_module = {}
    
    # Список функций if_player, которые нужно добавить
    if_player_functions_to_add = [
        "IsSprinting", "IsSneaking", "HasItem", "GamemodeEquals",
        "PlayerNameEquals", "PlayerMessageEquals", "HoldingItem",
        "HavePermissions", "InteractionType", "HandUsedEquals"
    ]
    
    # Для каждой функции if_player создаем запись
    for func_name in if_player_functions_to_add:
        func_lower = func_name.lower()
        if func_lower in custom_name_to_func:
            # Создаем базовую структуру
            new_if_player_module[func_lower] = {
                "id": f"if_player_{func_lower}_placeholder",
                "sign1": "Если игрок",
                "sign2": func_name,
                "gui": func_name,
                "menu": func_name,
                "aliases": [func_lower, func_name],
                "description": f"Проверка игрока: {func_name}",
                "descriptionRaw": f"§7Проверка игрока: {func_name}",
                "params": [],
                "enums": []
            }
            print(f"Добавлена функция if_player: {func_name}")
        else:
            print(f"Функция if_player {func_name} не найдена в LangTokens.json")
    
    # Создаем новый модуль if_game с правильными именами
    new_if_game_module = {}
    
    # Список функций if_game, которые нужно добавить
    if_game_functions_to_add = [
        "BlockEquals", "ContainerHasItem", "SignContains"
    ]
    
    # Для каждой функции if_game создаем запись
    for func_name in if_game_functions_to_add:
        func_lower = func_name.lower()
        if func_lower in custom_name_to_func:
            # Создаем базовую структуру
            new_if_game_module[func_lower] = {
                "id": f"if_game_{func_lower}_placeholder",
                "sign1": "Если игра",
                "sign2": func_name,
                "gui": func_name,
                "menu": func_name,
                "aliases": [func_lower, func_name],
                "description": f"Проверка игры: {func_name}",
                "descriptionRaw": f"§7Проверка игры: {func_name}",
                "params": [],
                "enums": []
            }
            print(f"Добавлена функция if_game: {func_name}")
        else:
            print(f"Функция if_game {func_name} не найдена в LangTokens.json")
    
    # Обновляем api_aliases.json
    api_data['if_player'] = new_if_player_module
    api_data['if_game'] = new_if_game_module
    
    # Сохраняем обновленный файл
    with open(api_aliases_path, 'w', encoding='utf-8') as f:
        json.dump(api_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nОбновлено api_aliases.json")
    print(f"Добавлено функций if_player: {len(new_if_player_module)}")
    print(f"Добавлено функций if_game: {len(new_if_game_module)}")

if __name__ == "__main__":
    add_if_player_aliases()
