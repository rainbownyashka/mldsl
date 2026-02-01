import json
import re
from pathlib import Path

def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    return text

def norm_key(text: str) -> str:
    text = strip_colors(text).replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text

def load_allactions_map() -> dict:
    ALLACTIONS_PATH = Path(__file__).resolve().parents[1] / "allactions.txt"
    if not ALLACTIONS_PATH.exists():
        return {}
    text = ALLACTIONS_PATH.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(r"^\x28\x28([^\]]+)\x29\s+([^\]]+)\x29$", re.M)
    out = {}
    for item_id, label in pattern.findall(text):
        label = strip_colors(label).strip()
        out[norm_key(label)] = item_id.strip()
    return out

# Загружаем blocks
blocks = load_allactions_map()
print(f"Всего блоков: {len(blocks)}")

# Ищем "если игрок"
search_key = norm_key("Если игрок")
print(f"Ищем ключ: '{search_key}'")
if search_key in blocks:
    print(f"Найдено: blocks['{search_key}'] = '{blocks[search_key]}'")
else:
    print("Не найдено в blocks")
    # Покажем похожие ключи
    similar = [k for k in blocks.keys() if "игрок" in k or "если" in k]
    print(f"Похожие ключи ({len(similar)}):")
    for k in similar[:10]:
        print(f"  '{k}' -> '{blocks[k]}'")
