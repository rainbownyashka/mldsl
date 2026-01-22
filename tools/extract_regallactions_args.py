import json
import re
from pathlib import Path

EXPORT_PATH = Path(r"C:\Users\ASUS\AppData\Roaming\.minecraft\regallactions_export.txt")
ALIASES_PATH = Path(r"C:\Users\ASUS\Documents\mlctmodified\src\assets\Aliases.json")
OUT_PATH = Path(r"C:\Users\ASUS\Documents\regallactions_args.json")

GLASS_ID = "minecraft:stained_glass_pane"


def read_text_utf8(path: Path) -> str:
    data = path.read_bytes().replace(b"\x00", b"")
    return data.decode("utf-8", errors="replace")


def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    return text


def normalize(text: str) -> str:
    text = strip_colors(text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def load_aliases(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("sign1", {})


def apply_alias(line: str, aliases: dict) -> str:
    if not line:
        return ""
    raw = strip_colors(line).strip()
    if raw in aliases:
        return aliases[raw]
    return raw


ITEM_RE = re.compile(r"^item=slot\s+(\d+):\s+\[([^\s]+)\s+meta=(\d+)\]\s+(.*)$")


def parse_record_lines(lines):
    record = {
        "path": "",
        "category": "",
        "subitem": "",
        "gui": "",
        "signs": ["", "", "", ""],
        "hasChest": False,
        "items": {},
    }
    for line in lines:
        if line.startswith("path="):
            record["path"] = line[len("path="):]
        elif line.startswith("category="):
            record["category"] = line[len("category="):]
        elif line.startswith("subitem="):
            record["subitem"] = line[len("subitem="):]
        elif line.startswith("gui="):
            record["gui"] = line[len("gui="):]
        elif line.startswith("sign1="):
            record["signs"][0] = line[len("sign1="):]
        elif line.startswith("sign2="):
            record["signs"][1] = line[len("sign2="):]
        elif line.startswith("sign3="):
            record["signs"][2] = line[len("sign3="):]
        elif line.startswith("sign4="):
            record["signs"][3] = line[len("sign4="):]
        elif line.startswith("hasChest="):
            record["hasChest"] = line[len("hasChest="):].strip().lower() == "true"
        elif line.startswith("item="):
            m = ITEM_RE.match(line)
            if not m:
                continue
            slot = int(m.group(1))
            item_id = m.group(2).strip()
            meta = int(m.group(3))
            rest = m.group(4)
            parts = rest.split(" | ", 1)
            name = parts[0].strip()
            lore = parts[1].strip() if len(parts) > 1 else ""
            record["items"][slot] = {
                "id": item_id,
                "meta": meta,
                "name": name,
                "lore": lore,
            }
    return record


def determine_mode(glass_meta: int, glass_name: str) -> str | None:
    name_clean = strip_colors(glass_name).lower()
    if glass_meta == 0:
        return "ANY"
    if glass_meta == 3 and name_clean.startswith("текст"):
        return "TEXT"
    if glass_meta == 14:
        return "NUMBER"
    if glass_meta == 1:
        return "VARIABLE"
    # Yellow glass pane is used as "item input" marker in many GUIs.
    if glass_meta == 4:
        return "ITEM"
    if glass_meta == 5:
        if "местополож" in name_clean:
            return "LOCATION"
        return "ARRAY"
    return None


def neighbor_slots(slot: int):
    row = slot // 9
    col = slot % 9
    order = [
        (row + 1, col),  # down
        (row, col - 1),  # left
        (row, col + 1),  # right
        (row - 1, col),  # up
    ]
    for r, c in order:
        if 0 <= r < 6 and 0 <= c < 9:
            yield r * 9 + c


def find_candidate_slot(items: dict, base_slot: int, reserved: set[int]) -> int | None:
    best_empty = None
    for s in neighbor_slots(base_slot):
        if s in reserved:
            continue
        if s not in items:
            if best_empty is None:
                best_empty = s
            continue
        if items[s]["id"] == GLASS_ID:
            continue
    return best_empty


def parse_variant_info(lore: str) -> dict | None:
    if not lore:
        return None
    lines = [strip_colors(x).strip() for x in lore.split(" \\n ")]
    options = []
    selected = None
    for line in lines:
        # Server UIs use ○ / ● bullets, but some exports may corrupt them to '?' / TAB.
        if ("●" in line) or ("○" in line) or ("?" in line) or ("\t" in line):
            if ("●" in line) or ("?" in line):
                bullet = "●" if "●" in line else "?"
                is_selected = True
            else:
                bullet = "○" if "○" in line else "\t"
                is_selected = False
            text = line.split(bullet, 1)[1].strip()
            if text:
                options.append(text)
                if is_selected and selected is None:
                    selected = len(options) - 1
    if not options:
        return None
    if selected is None:
        selected = 0
    return {
        "options": options,
        "selectedIndex": selected,
        "clicks": selected,
    }


def build_key(record: dict, aliases: dict) -> str:
    signs = [apply_alias(s, aliases) for s in record["signs"]]
    parts = [
        normalize(record["path"]),
        normalize(record["category"]),
        normalize(record["subitem"]),
        normalize(record["gui"]),
        normalize(signs[0]),
        normalize(signs[1]),
        normalize(signs[2]),
        normalize(signs[3]),
    ]
    return "|".join(parts)


def extract_args(record: dict):
    args = []
    items = record["items"]
    reserved = set()
    for slot, item in sorted(items.items()):
        if item["id"] != GLASS_ID:
            continue
        if item["meta"] == 15:
            continue
        mode = determine_mode(item["meta"], item["name"])
        if mode is None:
            continue
        arg_slot = find_candidate_slot(items, slot, reserved)
        if arg_slot is None:
            continue
        reserved.add(arg_slot)
        arg_has_item = arg_slot in items
        variant = None
        if arg_has_item:
            variant = parse_variant_info(items[arg_slot].get("lore", ""))
        glass_meta_filter = None if item["meta"] == 0 else item["meta"]
        args.append({
            "glassSlot": slot,
            "glassMeta": item["meta"],
            "glassMetaFilter": glass_meta_filter,
            "glassName": strip_colors(item["name"]).strip(),
            "keyNorm": "" if item["meta"] == 0 else normalize(item["name"]),
            "mode": mode,
            "argSlot": arg_slot,
            "argHasItem": arg_has_item,
            "variant": variant,
        })
    return args


def extract_enums(record: dict):
    enums = []
    items = record["items"]
    for slot, item in sorted(items.items()):
        if item["id"] == GLASS_ID:
            continue
        variant = parse_variant_info(item.get("lore", ""))
        if variant is None:
            continue
        enums.append({
            "slot": slot,
            "id": item["id"],
            "meta": item["meta"],
            "name": strip_colors(item["name"]).strip(),
            "variant": variant,
        })
    return enums


def main():
    text = read_text_utf8(EXPORT_PATH)
    aliases = load_aliases(ALIASES_PATH)
    records = []
    chunk = []
    for line in text.splitlines():
        if line.startswith("# record"):
            if chunk:
                records.append(parse_record_lines(chunk))
                chunk = []
        elif line.startswith("records="):
            continue
        else:
            chunk.append(line)
    if chunk:
        records.append(parse_record_lines(chunk))

    out = []
    for record in records:
        args = extract_args(record)
        enums = extract_enums(record)
        key = build_key(record, aliases)
        out.append({
            "key": key,
            "path": record["path"],
            "category": record["category"],
            "subitem": record["subitem"],
            "gui": record["gui"],
            "signs": record["signs"],
            "args": args,
            "enums": enums,
        })

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"records={len(out)} out={OUT_PATH}")


if __name__ == "__main__":
    main()
