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

ALLACTIONS_PATH = Path(__file__).resolve().parents[1] / "allactions.txt"
text = ALLACTIONS_PATH.read_text(encoding="utf-8", errors="replace")

# Ищем все вхождения "Если игрок"
import re
pattern = re.compile(r"\[\(([^]]+)\)\s+([^]]+)\]")
matches = list(pattern.finditer(text))

print(f"Всего совпадений: {len(matches)}")

# Ищем "Если игрок"
for match in matches:
    item_id = match.group(1).strip()
    label = match.group(2).strip()
    label_clean = strip_colors(label).strip()
    if "Если игрок" in label_clean:
        print(f"Найдено: '{label_clean}' -> '{item_id}'")
        print(f"  Нормализованный ключ: '{norm_key(label_clean)}'")
        break

# Покажем несколько примеров
print("\nПервые 5 записей:")
for i, match in enumerate(matches[:5]):
    item_id = match.group(1).strip()
    label = match.group(2).strip()
    label_clean = strip_colors(label).strip()
    print(f"  {i+1}. '{label_clean}' -> '{item_id}'")
    print(f"     Нормализованный: '{norm_key(label_clean)}'")
