import json
import re
from pathlib import Path

from mldsl_paths import default_minecraft_export_path, ensure_dirs, out_dir, aliases_json_path

EXPORT_PATH = default_minecraft_export_path()
ALIASES_PATH = aliases_json_path()
OUT_PATH = out_dir() / "regallactions_args.json"

GLASS_ID = "minecraft:stained_glass_pane"

# Input item ids used by the server UIs (by glass meta / color marker).
INPUT_ITEM_BY_MODE: dict[str, list[str]] = {
    "TEXT": ["minecraft:book"],
    "NUMBER": ["minecraft:slime_ball"],
    "VARIABLE": ["minecraft:magma_cream"],
    "ARRAY": ["minecraft:item_frame"],
    "LOCATION": ["minecraft:paper"],
}


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


def determine_mode_v2(items: dict, glass_slot: int, glass_meta: int, glass_name: str) -> str | None:
    """
    Determine argument input mode primarily by colored-glass meta.

    NOTE: Glass display names in regallactions_export.txt are sometimes garbled by encoding,
    so this function intentionally avoids depending on them unless unavoidable (meta=5).
    """
    if glass_meta == 0:
        return "ANY"
    if glass_meta == 3:
        return "TEXT"
    if glass_meta == 14:
        return "NUMBER"
    if glass_meta == 1:
        return "VARIABLE"
    # Yellow glass pane is used as an "item input" marker in many GUIs.
    if glass_meta == 4:
        return "ITEM"
    if glass_meta == 5:
        # Meta=5 is ambiguous: it can mean ARRAY or LOCATION. Prefer detection by a
        # (readable) glass name, then fall back to neighbor input items if present.
        name_clean = strip_colors(glass_name).lower()
        if ("местополож" in name_clean) or ("location" in name_clean):
            return "LOCATION"
        max_row = (max(items.keys()) // 9) if items else 5
        for s in neighbor_slots(glass_slot, max_row):
            it = items.get(s)
            if not it:
                continue
            if it.get("id") == "minecraft:paper":
                return "LOCATION"
            if it.get("id") == "minecraft:item_frame":
                return "ARRAY"
        return "ARRAY"
    # Some server GUIs use meta=13 panes as "block/item input" marker (instead of meta=4),
    # while the same meta is also used for non-arg "output" panes (e.g. "Выходной массив").
    # Disambiguate by the pane display name.
    if glass_meta == 13:
        name_clean = strip_colors(glass_name).lower()
        if any(x in name_clean for x in ["блок", "предмет", "item", "block"]):
            return "ITEM"
    return None


def neighbor_slots(slot: int, max_row: int):
    row = slot // 9
    col = slot % 9
    order = [
        (row + 1, col),  # down
        (row, col - 1),  # left
        (row, col + 1),  # right
        (row - 1, col),  # up
    ]
    for r, c in order:
        # AGENT_TAG: merged_pages_neighbors
        # Support merged multi-page exports where slots go beyond a single 6-row chest page.
        if 0 <= r <= max_row and 0 <= c < 9:
            yield r * 9 + c


def find_candidate_slot(items: dict, base_slot: int, reserved: set[int], max_row: int) -> int | None:
    best_empty = None
    for s in neighbor_slots(base_slot, max_row):
        if s in reserved:
            continue
        if s not in items:
            if best_empty is None:
                best_empty = s
            continue
        if items[s]["id"] == GLASS_ID:
            continue
    return best_empty


def find_candidate_slot_v2(items: dict, base_slot: int, reserved: set[int], mode: str, max_row: int) -> int | None:
    """
    Pick the slot the UI would edit/fill for this glass marker.

    Order (close to the in-mod logic):
    1) If a neighbor slot already contains the expected input item for this mode, use it (edit).
    2) Otherwise pick the first empty neighbor slot (new value).
    3) For ITEM mode only: if no empty slots exist, allow the first non-glass neighbor slot.

    We intentionally do NOT use generic "occupied non-glass" fallback for other modes, because
    it can accidentally bind enum items (e.g. rope) that live in the GUI layout.
    """
    expected_ids = INPUT_ITEM_BY_MODE.get(mode, [])
    if expected_ids:
        for s in neighbor_slots(base_slot, max_row):
            if s in reserved:
                continue
            it = items.get(s)
            if not it:
                continue
            if it.get("id") in expected_ids:
                return s

    for s in neighbor_slots(base_slot, max_row):
        if s in reserved:
            continue
        if s not in items:
            return s

    if mode == "ITEM":
        for s in neighbor_slots(base_slot, max_row):
            if s in reserved:
                continue
            it = items.get(s)
            if not it:
                continue
            if it.get("id") != GLASS_ID:
                return s

    return None


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
    max_row = (max(items.keys()) // 9) if items else 5
    reserved = set()
    for slot, item in sorted(items.items()):
        if item["id"] != GLASS_ID:
            continue
        if item["meta"] == 15:
            continue
        mode = determine_mode_v2(items, slot, item["meta"], item["name"])
        if mode is None:
            continue
        arg_slot = find_candidate_slot_v2(items, slot, reserved, mode, max_row)
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
    ensure_dirs()
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(
            "Не найден `regallactions_export.txt`.\n"
            f"Ожидаемый путь: {EXPORT_PATH}\n"
            "Положи экспорт в `.minecraft/regallactions_export.txt` или укажи `MLDSL_REGALLACTIONS_EXPORT`."
        )
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
