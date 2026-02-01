import json
from pathlib import Path

from mldsl_paths import actions_catalog_path, api_aliases_path, ensure_dirs

CATALOG_PATH = actions_catalog_path()
API_PATH = api_aliases_path()

def main():
    ensure_dirs()
    if not CATALOG_PATH.exists() or not API_PATH.exists():
        raise FileNotFoundError(
            "Не найдены входные файлы json (нужно сгенерировать `out/`).\n"
            f"actions_catalog: {CATALOG_PATH}\n"
            f"api_aliases: {API_PATH}\n"
            "Запусти: python tools/build_all.py"
        )

    print("Загрузка данных...")
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        catalog = json.load(f)
        # Создаем словарь для быстрого поиска по ID действия
        catalog_map = {item['id']: item for item in catalog if 'id' in item}

    with open(API_PATH, 'r', encoding='utf-8') as f:
        api = json.load(f)

    updated_count = 0

    print("Обогащение API данными о стеклах...")
    
    for module, functions in api.items():
        for func_key, func_data in functions.items():
            action_id = func_data.get('id')
            
            # Ищем оригинал в каталоге
            if action_id and action_id in catalog_map:
                original_args = catalog_map[action_id].get('args', [])
                current_params = func_data.get('params', [])
                
                # Пытаемся сопоставить параметры
                # Обычно порядок совпадает, но лучше проверять слоты
                
                # Создаем карту слотов из каталога
                slot_to_glass = {
                    arg['argSlot']: {
                        "glassName": arg.get('glassName', 'Аргумент'),
                        "glassMeta": arg.get('glassMeta', 0),
                        "mode": arg.get('mode', 'ANY')
                    }
                    for arg in original_args if 'argSlot' in arg
                }

                # Обновляем параметры в API
                for param in current_params:
                    slot = param.get('slot')
                    if slot in slot_to_glass:
                        glass_info = slot_to_glass[slot]
                        param['glassName'] = glass_info['glassName']
                        param['glassMeta'] = glass_info['glassMeta']
                        # Если режим был ANY, уточним его из каталога
                        if param.get('mode') == 'ANY':
                            param['mode'] = glass_info['mode']
                
                updated_count += 1

    # Сохраняем обновленный API
    with open(API_PATH, 'w', encoding='utf-8') as f:
        json.dump(api, f, ensure_ascii=False, indent=2)

    print(f"Готово! Обновлено записей: {updated_count}")
    print("Теперь в api_aliases.json есть информация о цветных стеклах.")

if __name__ == "__main__":
    main()
