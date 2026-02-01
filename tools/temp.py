import json
import re
from pathlib import Path

from mldsl_paths import actions_catalog_path, api_aliases_path

CATALOG_PATH = actions_catalog_path()
API_OUT_PATH = api_aliases_path()

# СИСТЕМНЫЕ СВЯЗКИ (Поиск по имени предмета)
CORE_LOGIC = {
    "player": {"message": "Отправить сообщение", "teleport": "Телепортация", "give_item": "Выдать предметы"},
    "var": {
        "set_value": "Установить (=)", "set_sum": "Установить (+)", "set_difference": "Установить (-)",
        "set_product": "Установить (*)", "set_quotient": "Установить (÷)", "set_remainder": "Установить (%)"
    },
    "if_value": {"number_2": "Сравнить числа", "text": "Текст равняется", "var": "Переменная существует"},
    "game": {"call_function": "Вызвать функцию", "start_loops": "Запустить цикл", "stop_loops": "Остановить цикл"}
}

# ИМЕНА ПАРАМЕТРОВ (Накладываются на найденные слоты)
PARAM_NAMES = {
    "var.set_value": ["var", "value"],
    "var.set_sum": ["var", "num", "num2", "num3", "num4", "num5", "num6", "num7", "num8", "num9", "num10"],
    "var.set_product": ["var", "num", "num2", "num3", "num4", "num5", "num6", "num7", "num8", "num9", "num10"],
    "var.set_difference": ["var", "num", "num2"],
    "var.set_quotient": ["var", "num", "num2"],
    "var.set_remainder": ["var", "num", "num2"],
    "if_value.number_2": ["num", "num2", "num3"],
    "player.message": ["text", "text2", "text3", "text4", "text5", "text6", "text7", "text8"],
    "player.give_item": ["item", "item2", "item3", "item4", "item5", "item6"]
}

def strip_colors(text: str) -> str:
    if not text: return ""
    return re.sub(r"\u00a7.", "", text).replace("●", "").replace("○", "").strip()

def extract_real_name(subitem):
    """Вытаскивает 'Проверить режим игры' из строки subitem"""
    if not subitem: return ""
    s = subitem
    if "]" in s: s = s.split("]" ,1)[1]
    if "|" in s: s = s.split("|", 1)[0]
    return strip_colors(s)

def to_code_name(text: str) -> str:
    t = strip_colors(text).lower()
    if t in ["+", "-", "*", "/", "%", "=", "+=", "-=", "*=", "/="]: return t
    t = re.sub(r"[\s\-]+", "_", t)
    t = re.sub(r"[^a-zа-я0-9_]", "", t)
    return re.sub(r"_+", "_", t).strip("_")

def translit(text: str) -> str:
    ru_map = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"}
    return "".join(ru_map.get(c, c) for c in text)

def get_arg_mode(meta, name):
    name = name.lower()
    if meta == 4: return "ITEM"
    if meta == 14: return "NUMBER"
    if meta in [3, 11]: return "TEXT"
    if meta == 1: return "VARIABLE"
    if meta == 5: return "LOCATION"
    if "текст" in name: return "TEXT"
    if "числ" in name: return "NUMBER"
    return "ANY"

def find_neighbor_slot(items_dict, base_slot, reserved):
    """Ищет слот-аргумент: Вниз, Влево, Вправо, Вверх"""
    row = base_slot // 9
    col = base_slot % 9
    offsets = [(1, 0), (0, -1), (0, 1), (-1, 0)]
    for r_off, c_off in offsets:
        r, c = row + r_off, col + c_off
        if 0 <= r < 6 and 0 <= c < 9:
            s = r * 9 + c
            if s in reserved: continue
            if str(s) not in items_dict: return s # Пустой слот
            if items_dict[str(s)].get('id') == "minecraft:stained_glass_pane": continue # Стекло
            return s # Занятый слот (например предмет)
    return None

def parse_action_params(action):
    items = action.get('items', {})
    if not items: return [] # Если items нет, берем пустой список (или можно args)

    glass_panes = []
    for slot_str, item in items.items():
        if item.get('id') == "minecraft:stained_glass_pane" and item.get('meta') != 15:
            glass_panes.append((int(slot_str), item))
    
    # Сортируем стекла по порядку (0, 1, 2...)
    glass_panes.sort(key=lambda x: x[0])

    params = []
    reserved = set()

    for glass_slot, item in glass_panes:
        target_slot = find_neighbor_slot(items, glass_slot, reserved)
        
        # Фолбек: если это Message/GiveItem и соседа нет, берем само стекло
        menu_name = extract_real_name(action.get('subitem', ''))
        if target_slot is None and (menu_name in ["Отправить сообщение", "Выдать предметы"]):
            target_slot = glass_slot
            
        if target_slot is not None:
            reserved.add(target_slot)
            params.append({
                "name": to_code_name(item.get('name', 'arg')),
                "mode": get_arg_mode(item.get('meta'), item.get('name')),
                "slot": target_slot
            })
    return params

def main():
    if not CATALOG_PATH.exists(): return print("Нет каталога")
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f: catalog = json.load(f)

    api = {"player":{}, "game":{}, "if_player":{}, "if_game":{}, "if_value":{}, "var":{}, "select":{}, "misc":{}}

    print("Генерация полного API (обычные + системные)...")

    # 1. ОБРАБАТЫВАЕМ ВЕСЬ КАТАЛОГ
    for action in catalog:
        s1 = strip_colors(action.get('signs', [""])[0]).lower()
        s2 = strip_colors(action.get('signs', ["", ""])[1])
        menu_name = extract_real_name(action.get('subitem', '')) or s2
        
        module = "misc"
        if "если игрок" in s1: module = "if_player"
        elif "если игра" in s1: module = "if_game"
        elif "значение" in s1 or "переменная" in s1: module = "if_value"
        elif "действие игрока" in s1: module = "player"
        elif "игровое действие" in s1: module = "game"
        elif "присв" in s1 or "перемен" in s1: module = "var"

        # Генерируем ключ на основе SIGN2 (короткое имя), чтобы было удобно писать код
        # (Например: rezhim_igroka, а не proverit_rezhim_igry)
        key = to_code_name(s2)
        if not key: key = to_code_name(menu_name)
        if not key: continue

        # Парсим слоты (честно)
        params = parse_action_params(action)
        
        # Если честный парсинг вернул пустоту (например items не было), пробуем взять args из каталога
        if not params and action.get('args'):
            params = []
            for arg in action.get('args'):
                params.append({"name": to_code_name(arg.get('glassName', 'arg')), "mode": arg.get('mode', 'ANY'), "slot": arg.get('argSlot')})

        entry = {
            "id": action.get('id'), "sign1": action.get('signs', [""])[0], "sign2": s2,
            "gui": menu_name, "menu": menu_name, # ДЛЯ ПРИНТЕРА
            "params": params, "aliases": [key, translit(key)], "enums": action.get('enums', [])
        }
        api[module][key] = entry
        
        # Доп. алиас для транслита
        if translit(key) != key:
            api[module][translit(key)] = entry

    # 2. НАКЛАДЫВАЕМ СИСТЕМНЫЕ ИМЕНА (Поиск по menu_name)
    print("Привязка системных алиасов...")
    for mod_name, funcs in CORE_LOGIC.items():
        for tech_key, real_gui in funcs.items():
            # Ищем в уже созданном API
            found = False
            for k, entry in api[mod_name].items():
                if entry['gui'] == real_gui:
                    api[mod_name][tech_key] = entry
                    entry['aliases'].append(tech_key)
                    
                    # Переименовываем параметры
                    full_tech = f"{mod_name}.{tech_key}"
                    sys_names = PARAM_NAMES.get(full_tech, [])
                    for i, p in enumerate(entry['params']):
                        if i < len(sys_names): p['name'] = sys_names[i]
                    
                    print(f"  [OK] {full_tech} -> '{real_gui}'")
                    found = True
                    break
            if not found:
                print(f"  [FAIL] {mod_name}.{tech_key} не найден (искал '{real_gui}')")

    with open(API_OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(api, f, ensure_ascii=False, indent=2)
    print("\nAPI готов.")

if __name__ == "__main__": main()
