import json
import re
from pathlib import Path

from mldsl_paths import default_minecraft_export_path, ensure_dirs, out_dir, aliases_json_path

EXPORT_PATH = default_minecraft_export_path()
ALIASES_PATH = aliases_json_path()
OUT_PATH = out_dir() / "regallactions_args.json"

GLASS_ID = "minecraft:stained_glass_pane"
ROW_SIZE = 9

# Input item ids used by the server UIs (by glass meta / color marker).
INPUT_ITEM_BY_MODE: dict[str, list[str]] = {
    "TEXT": ["minecraft:book"],
    "NUMBER": ["minecraft:slime_ball"],
    "VARIABLE": ["minecraft:magma_cream"],
    "ARRAY": ["minecraft:item_frame"],
    "LOCATION": ["minecraft:paper"],
    "VECTOR": [],
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
    if name_clean.startswith("вектор") or name_clean.startswith("vector"):
        return "VECTOR"
    if "блок" in name_clean:
        return "BLOCK"
    if glass_meta == 9:
        return "VECTOR"
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
    name_clean = strip_colors(glass_name).lower()
    if name_clean.startswith("вектор") or name_clean.startswith("vector"):
        return "VECTOR"
    if "блок" in name_clean:
        return "BLOCK"
    if glass_meta == 9:
        return "VECTOR"
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
        if any(x in name_clean for x in ["блок", "предмет", "item", "block"]):
            return "ITEM"
    return None


def neighbor_slots(slot: int, max_row: int):
    row = slot // ROW_SIZE
    col = slot % ROW_SIZE
    order = [
        (row + 1, col),  # down
        (row, col - 1),  # left
        (row, col + 1),  # right
        (row - 1, col),  # up
    ]
    for r, c in order:
        # AGENT_TAG: merged_pages_neighbors
        # Support merged multi-page exports where slots go beyond a single 6-row chest page.
        if 0 <= r <= max_row and 0 <= c < ROW_SIZE:
            yield r * ROW_SIZE + c


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

    if mode in {"ITEM", "BLOCK"}:
        for s in neighbor_slots(base_slot, max_row):
            if s in reserved:
                continue
            it = items.get(s)
            if not it:
                continue
            if it.get("id") != GLASS_ID:
                return s

    return None


_REPEATED_TOKENS: dict[str, tuple[str, ...]] = {
    "NUMBER": ("число(а)", "числа"),
    "TEXT": ("текст(ы)", "тексты"),
    "ITEM": ("предмет(ы)", "предметы"),
    "LOCATION": ("местоположение(я)", "местоположения", "местополож"),
    "ARRAY": ("массив(ы)", "массивы"),
    "VECTOR": ("вектор(ы)", "векторы", "вектор"),
    "ANY": ("значение(я)", "значения"),
}


def _is_repeated_marker(item: dict | None, mode: str) -> bool:
    if not item or item.get("id") != GLASS_ID:
        return False
    item_mode = determine_mode(int(item.get("meta", 0)), str(item.get("name", "")))
    if item_mode != mode:
        return False
    name_n = normalize(str(item.get("name", "")))
    lore_raw = str(item.get("lore", ""))
    lore_n = normalize(lore_raw)
    has_plural_hint = any(t in name_n for t in _REPEATED_TOKENS.get(mode, ()))
    has_arrow_hint = ("ниже" in lore_n) or ("выше" in lore_n) or ("⇩" in lore_raw) or ("⇧" in lore_raw)
    return has_plural_hint or has_arrow_hint


def _find_nearest_repeated_marker(
    items: dict[int, dict],
    row: int,
    col: int,
    marker_cols: list[int],
    mode: str,
) -> dict | None:
    best = None
    best_dist = None
    for c in marker_cols:
        s = row * ROW_SIZE + c
        it = items.get(s)
        if not _is_repeated_marker(it, mode):
            continue
        dist = abs(c - col)
        if best is None or dist < best_dist:
            best = it
            best_dist = dist
    return best


def _find_repeated_lane_magic_slots(
    items: dict[int, dict],
    mode: str,
    min_total_markers: int = 7,
    min_consecutive_markers: int = 3,
    required_empty_rows: int = 3,
) -> dict[int, dict]:
    if not items:
        return {}
    min_slot = min(items.keys())
    max_slot = max(items.keys())
    min_row = min_slot // ROW_SIZE
    max_row = max_slot // ROW_SIZE
    max_inventory_slot = (6 * ROW_SIZE) - 1
    candidates: list[tuple[int, int, int, int, dict[int, dict]]] = []

    for row in range(min_row, max_row + 1):
        marker_cols = []
        for col in range(ROW_SIZE):
            slot = row * ROW_SIZE + col
            if _is_repeated_marker(items.get(slot), mode):
                marker_cols.append(col)
        if len(marker_cols) < min_total_markers:
            continue

        has_consecutive = False
        i = 0
        while i < len(marker_cols):
            a = marker_cols[i]
            b = a
            while i + 1 < len(marker_cols) and marker_cols[i + 1] == b + 1:
                i += 1
                b = marker_cols[i]
            if (b - a + 1) >= min_consecutive_markers:
                has_consecutive = True
                break
            i += 1
        if not has_consecutive:
            continue

        # Current repeated-lane parser:
        # once a lane is recognized by marker glasses, inspect every column in lane span
        # (including enum/non-glass columns) and register each successful column.
        lane_start = marker_cols[0]
        lane_end = marker_cols[-1]
        local: dict[int, dict] = {}
        lane_valid = True
        for col in range(lane_start, lane_end + 1):
            lane_slot = row * ROW_SIZE + col
            src = items.get(lane_slot)
            if not _is_repeated_marker(src, mode):
                src = _find_nearest_repeated_marker(items, row, col, marker_cols, mode)
            if src is None:
                lane_valid = False
                break
            s = lane_slot + ROW_SIZE
            arg_slots = []
            for _ in range(required_empty_rows):
                if s > max_inventory_slot or s in items:
                    lane_valid = False
                    break
                arg_slots.append(s)
                s += ROW_SIZE
            if not lane_valid:
                break
            src_meta = int(src.get("meta", 0))
            src_name = strip_colors(str(src.get("name", ""))).strip()
            local[lane_slot] = {
                "argSlots": arg_slots,
                "glassMeta": src_meta,
                "glassName": src_name,
                "mode": mode,
                "keyNorm": "" if src_meta == 0 else normalize(src_name),
            }
        if lane_valid and local:
            candidates.append((len(local), len(marker_cols), -row, lane_start, local))

    if not candidates:
        return {}
    candidates.sort(reverse=True)
    return candidates[0][4]


def _find_repeated_number_magic_slots(items: dict[int, dict]) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, mode="NUMBER")


def _find_repeated_text_magic_slots(items: dict[int, dict]) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, mode="TEXT")


def _find_repeated_item_magic_slots(items: dict[int, dict]) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, mode="ITEM")


def _find_repeated_location_magic_slots(items: dict[int, dict]) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, mode="LOCATION")


def _find_repeated_array_magic_slots(items: dict[int, dict]) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, mode="ARRAY")


def _find_repeated_any_magic_slots(items: dict[int, dict]) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, mode="ANY")


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
    repeated_number_magic = _find_repeated_number_magic_slots(items)
    repeated_text_magic = _find_repeated_text_magic_slots(items)
    repeated_item_magic = _find_repeated_item_magic_slots(items)
    repeated_location_magic = _find_repeated_location_magic_slots(items)
    repeated_array_magic = _find_repeated_array_magic_slots(items)
    repeated_any_magic = _find_repeated_any_magic_slots(items)
    repeated_lane_maps = [
        repeated_number_magic,
        repeated_text_magic,
        repeated_item_magic,
        repeated_location_magic,
        repeated_array_magic,
        repeated_any_magic,
    ]
    lane_slots = set()
    for lane_map in repeated_lane_maps:
        lane_slots.update(lane_map.keys())
    for slot, item in sorted(items.items()):
        if item["id"] != GLASS_ID:
            continue
        if item["meta"] == 15:
            continue
        mode = determine_mode_v2(items, slot, item["meta"], item["name"])
        if mode is None:
            continue
        if repeated_item_magic and _is_repeated_marker(item, "ITEM") and slot not in repeated_item_magic:
            continue
        if repeated_text_magic and _is_repeated_marker(item, "TEXT") and slot not in repeated_text_magic:
            continue
        if repeated_number_magic and _is_repeated_marker(item, "NUMBER") and slot not in repeated_number_magic:
            continue
        if repeated_location_magic and _is_repeated_marker(item, "LOCATION") and slot not in repeated_location_magic:
            continue
        if repeated_array_magic and _is_repeated_marker(item, "ARRAY") and slot not in repeated_array_magic:
            continue
        if repeated_any_magic and _is_repeated_marker(item, "ANY") and slot not in repeated_any_magic:
            continue
        # Lane layouts are emitted in one strict row-major pass later.
        if slot in lane_slots:
            continue

        magic_spec = (
            repeated_number_magic.get(slot)
            or repeated_text_magic.get(slot)
            or repeated_item_magic.get(slot)
            or repeated_location_magic.get(slot)
            or repeated_array_magic.get(slot)
            or repeated_any_magic.get(slot)
        )
        if magic_spec:
            candidate_slots = magic_spec["argSlots"]
            glass_meta = int(magic_spec["glassMeta"])
            glass_name = magic_spec["glassName"]
            key_norm = magic_spec["keyNorm"]
            mode = magic_spec["mode"]
        else:
            arg_slot = find_candidate_slot_v2(items, slot, reserved, mode, max_row)
            if arg_slot is None:
                continue
            candidate_slots = [arg_slot]
            glass_meta = int(item["meta"])
            glass_name = strip_colors(item["name"]).strip()
            key_norm = "" if glass_meta == 0 else normalize(item["name"])
        glass_meta_filter = None if glass_meta == 0 else glass_meta
        for arg_slot in candidate_slots:
            if arg_slot in reserved:
                continue
            reserved.add(arg_slot)
            arg_has_item = arg_slot in items
            variant = None
            if arg_has_item:
                variant = parse_variant_info(items[arg_slot].get("lore", ""))
            args.append({
                "glassSlot": slot,
                "glassMeta": glass_meta,
                "glassMetaFilter": glass_meta_filter,
                "glassName": glass_name,
                "keyNorm": key_norm,
                "mode": mode,
                "argSlot": arg_slot,
                "argHasItem": arg_has_item,
                "variant": variant,
            })

    # Emit lane arguments in strict row-major order:
    # first row across all lane columns, then second row, then third row.
    def _emit_lane_map_row_major(lane_map: dict[int, dict]):
        if not lane_map:
            return
        ordered_lane_slots = sorted(lane_map.keys())
        max_depth = max((len(spec.get("argSlots") or []) for spec in lane_map.values()), default=0)
        for depth in range(max_depth):
            for lane_slot in ordered_lane_slots:
                lane_spec = lane_map.get(lane_slot) or {}
                lane_arg_slots = lane_spec.get("argSlots") or []
                if depth >= len(lane_arg_slots):
                    continue
                arg_slot = lane_arg_slots[depth]
                if arg_slot in reserved:
                    continue
                reserved.add(arg_slot)
                glass_meta = int(lane_spec.get("glassMeta", 0))
                glass_meta_filter = None if glass_meta == 0 else glass_meta
                arg_has_item = arg_slot in items
                variant = None
                if arg_has_item:
                    variant = parse_variant_info(items[arg_slot].get("lore", ""))
                args.append({
                    "glassSlot": lane_slot,
                    "glassMeta": glass_meta,
                    "glassMetaFilter": glass_meta_filter,
                    "glassName": lane_spec.get("glassName", ""),
                    "keyNorm": lane_spec.get("keyNorm", ""),
                    "mode": lane_spec.get("mode"),
                    "argSlot": arg_slot,
                    "argHasItem": arg_has_item,
                    "variant": variant,
                })

    for lane_map in repeated_lane_maps:
        _emit_lane_map_row_major(lane_map)
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
