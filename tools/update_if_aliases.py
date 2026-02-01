"""
Скрипт для обновления алиасов if_player и if_game с правильными параметрами
"""
import json
from pathlib import Path

from mldsl_paths import api_aliases_path as _api_aliases_path, ensure_dirs, lang_tokens_path as _lang_tokens_path

def strip_colors(text: str) -> str:
    import re
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    return text

def update_if_aliases():
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
    
    # Функция для преобразования параметров
    def convert_params(args_dict):
        params = []
        slot_counter = 9  # Начинаем с слота 9
        for param_name, param_info in args_dict.items():
            param_type = param_info.get('type', 'value')
            mode = param_type.upper()
            if mode == 'VALUE':
                mode = 'TEXT'  # По умолчанию TEXT для value
            
            param = {
                "name": param_name,
                "mode": mode,
                "slot": slot_counter
            }
            
            # Обработка listed параметров
            if param_info.get('listed'):
                max_items = param_info.get('max', 1)
                for i in range(max_items):
                    param_copy = param.copy()
                    param_copy["name"] = f"{param_name}{i+1}" if i > 0 else param_name
                    param_copy["slot"] = slot_counter + i
                    params.append(param_copy)
                slot_counter += max_items
            else:
                params.append(param)
                slot_counter += 1
        
        return params
    
    # Обновляем if_player
    if_player_funcs = lang_data.get('IF_PLAYER', [])
    new_if_player_module = {}
    
    for func in if_player_funcs:
        name = func.get('name', '')
        custom_name = func.get('customName', '')
        if name and custom_name:
            func_lower = custom_name.lower()
            args = func.get('args', {})
            
            # Преобразуем параметры
            params = convert_params(args)
            
            new_if_player_module[func_lower] = {
                "id": f"if_player_{func_lower}",
                "sign1": "Если игрок",
                "sign2": custom_name,
                "gui": custom_name,
                "menu": custom_name,
                "aliases": [func_lower, custom_name],
                "description": f"Проверка игрока: {custom_name}",
                "descriptionRaw": f"§7Проверка игрока: {custom_name}",
                "params": params,
                "enums": []
            }
            print(f"Добавлена функция if_player: {custom_name} с {len(params)} параметрами")
    
    # Обновляем if_game
    if_game_funcs = lang_data.get('IF_GAME', [])
    new_if_game_module = {}
    
    for func in if_game_funcs:
        name = func.get('name', '')
        custom_name = func.get('customName', '')
        if name and custom_name:
            func_lower = custom_name.lower()
            args = func.get('args', {})
            
            # Преобразуем параметры
            params = convert_params(args)
            
            new_if_game_module[func_lower] = {
                "id": f"if_game_{func_lower}",
                "sign1": "Если игра",
                "sign2": custom_name,
                "gui": custom_name,
                "menu": custom_name,
                "aliases": [func_lower, custom_name],
                "description": f"Проверка игры: {custom_name}",
                "descriptionRaw": f"§7Проверка игры: {custom_name}",
                "params": params,
                "enums": []
            }
            print(f"Добавлена функция if_game: {custom_name} с {len(params)} параметрами")
    
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
    update_if_aliases()
