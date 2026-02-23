import json
import re
from pathlib import Path

from mldsl_paths import default_minecraft_export_path, ensure_dirs, out_dir, aliases_json_path

EXPORT_PATH = default_minecraft_export_path()
ALIASES_PATH = aliases_json_path()
OUT_PATH = out_dir() / "regallactions_args.json"

GLASS_ID = "minecraft:stained_glass_pane"
ROW_SIZE = 9


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


def round_down_to_row(slot: int) -> int:
    return (slot // ROW_SIZE) * ROW_SIZE


def round_up_to_row_max(slot: int) -> int:
    return ((slot // ROW_SIZE) + 1) * ROW_SIZE - 1


def infer_slot_bounds(items: dict[int, dict]) -> tuple[int, int]:
    if not items:
        return 0, ROW_SIZE - 1
    min_slot = min(items.keys())
    max_slot = max(items.keys())
    return round_down_to_row(min_slot), round_up_to_row_max(max_slot)


def is_usable_empty_slot(items: dict, slot: int, reserved: set[int]) -> bool:
    if slot in reserved:
        return False
    if slot in items:
        return False
    return True


def find_fallback_slot(items: dict, base_slot: int, reserved: set[int], min_slot: int, max_slot: int) -> int | None:
    # Directional policy: choose one side by nearest bound and scan only that side.
    # Near min bound -> search down only. Near max bound -> search up only.
    dist_min = abs(base_slot - min_slot)
    dist_max = abs(max_slot - base_slot)
    if dist_min <= dist_max:
        for s in range(base_slot - 1, min_slot - 1, -1):
            if is_usable_empty_slot(items, s, reserved):
                return s
    else:
        for s in range(base_slot + 1, max_slot + 1):
            if is_usable_empty_slot(items, s, reserved):
                return s
    return None


def find_candidate_slot(items: dict, base_slot: int, reserved: set[int], min_slot: int, max_slot: int) -> int | None:
    best_empty = None
    for s in neighbor_slots(base_slot):
        if s < min_slot or s > max_slot:
            continue
        if s in reserved:
            continue
        if s not in items:
            if best_empty is None:
                best_empty = s
            continue
        if items[s]["id"] == GLASS_ID:
            continue
    if best_empty is not None:
        return best_empty
    return find_fallback_slot(items, base_slot, reserved, min_slot, max_slot)


def _looks_like_concat_texts_action(record: dict) -> bool:
    signs = record.get("signs") or ["", "", "", ""]
    candidates = [
        signs[0] if len(signs) > 0 else "",
        signs[1] if len(signs) > 1 else "",
        signs[2] if len(signs) > 2 else "",
        record.get("gui", ""),
        record.get("subitem", ""),
    ]
    norms = [normalize(x) for x in candidates if x]

    # Text-level hints: tolerate aliases/drift (including short "=" action labels).
    for n in norms:
        if not n:
            continue
        if n == "=":
            return True
        if ("объедин" in n and "текст" in n) or ("concat" in n and "text" in n):
            return True

    # Structural fallback: action has concat-like pane layout markers.
    items = record.get("items") or {}
    text_markers = 0
    variable_markers = 0
    for it in items.values():
        if it.get("id") != GLASS_ID:
            continue
        meta = int(it.get("meta", 0))
        if meta == 15:
            continue
        mode = determine_mode(meta, str(it.get("name", "")))
        if mode == "TEXT":
            text_markers += 1
        elif mode == "VARIABLE":
            variable_markers += 1
    return text_markers >= 8 and variable_markers >= 1


def _glass_runs_in_row(items: dict[int, dict], row: int) -> list[tuple[int, int]]:
    cols = []
    for col in range(ROW_SIZE):
        slot = row * ROW_SIZE + col
        it = items.get(slot)
        is_glass = False
        if it and it.get("id") == GLASS_ID and int(it.get("meta", 0)) != 15:
            mode = determine_mode(int(it.get("meta", 0)), str(it.get("name", "")))
            is_glass = mode is not None
        cols.append(is_glass)
    runs = []
    i = 0
    while i < ROW_SIZE:
        if not cols[i]:
            i += 1
            continue
        j = i
        while j + 1 < ROW_SIZE and cols[j + 1]:
            j += 1
        runs.append((i, j))
        i = j + 1
    return runs


def _is_marker_glass_item(item: dict | None) -> bool:
    return bool(item and item.get("id") == GLASS_ID and int(item.get("meta", 0)) != 15)


def _find_nearest_lane_marker(items: dict[int, dict], row: int, col: int, lane_cols: list[int]) -> dict | None:
    best = None
    best_dist = None
    for c in lane_cols:
        if c == col:
            continue
        s = row * ROW_SIZE + c
        it = items.get(s)
        if not _is_marker_glass_item(it):
            continue
        mode = determine_mode(int(it.get("meta", 0)), str(it.get("name", "")))
        if mode is None:
            continue
        d = abs(c - col)
        if best is None or d < best_dist:
            best = it
            best_dist = d
    return best


def _find_concat_magic_slots(record: dict, items: dict[int, dict], min_slot: int, max_slot: int) -> dict[int, dict]:
    """
    Prototype rule for "Объединить тексты":
    - detect a row with >=4 non-gray glass in a run, optional one non-glass gap,
      then another >=4 non-gray glass run;
    - if each detected glass has >=3 empty slots vertically below (or more until bounds),
      treat all those empty below-slots as argument slots for that glass.
    """
    if not _looks_like_concat_texts_action(record):
        return {}
    if min_slot > max_slot:
        return {}
    min_row = min_slot // ROW_SIZE
    max_row = max_slot // ROW_SIZE
    out: dict[int, dict] = {}

    max_inventory_slot = (6 * ROW_SIZE) - 1
    for row in range(min_row, max_row + 1):
        runs = _glass_runs_in_row(items, row)
        if len(runs) < 2:
            continue

        picked_lane_cols = None
        for i in range(len(runs) - 1):
            a0, a1 = runs[i]
            b0, b1 = runs[i + 1]
            len_a = a1 - a0 + 1
            len_b = b1 - b0 + 1
            gap = b0 - a1 - 1
            total_markers = len_a + len_b
            if len_a >= 3 and len_b >= 3 and gap == 1 and total_markers >= 7:
                picked_lane_cols = list(range(a0, b1 + 1))
                break

        # Pattern with two gaps around a center marker run:
        # 3+ gap +1+ gap +3 (or stronger variants), e.g. col 4 and 6 are any item,
        # col 5 is marker glass.
        if picked_lane_cols is None and len(runs) >= 3:
            for i in range(len(runs) - 2):
                a0, a1 = runs[i]
                b0, b1 = runs[i + 1]
                c0, c1 = runs[i + 2]
                len_a = a1 - a0 + 1
                len_b = b1 - b0 + 1
                len_c = c1 - c0 + 1
                gap_ab = b0 - a1 - 1
                gap_bc = c0 - b1 - 1
                total_markers = len_a + len_b + len_c
                if len_a >= 3 and len_b >= 1 and len_c >= 3 and gap_ab == 1 and gap_bc == 1 and total_markers >= 7:
                    picked_lane_cols = list(range(a0, c1 + 1))
                    break

        if picked_lane_cols is None:
            continue
        lane_cols = picked_lane_cols

        local: dict[int, dict] = {}
        valid = True
        # Regallactions export can omit fully empty bottom rows; for concat lane we still
        # need at least 3 downward slots, so extend virtual scan range up to chest bounds.
        local_max_slot = min(max_inventory_slot, max(max_slot, row * ROW_SIZE + (ROW_SIZE - 1) + (3 * ROW_SIZE)))
        for col in lane_cols:
            lane_slot = row * ROW_SIZE + col
            empties = []
            s = lane_slot + ROW_SIZE
            while s <= local_max_slot:
                if s in items:
                    # For concat-text lane, slots below marker glass must stay empty.
                    valid = False
                    break
                empties.append(s)
                s += ROW_SIZE
            if not valid:
                break
            if len(empties) < 3:
                valid = False
                break

            src = items.get(lane_slot)
            if not _is_marker_glass_item(src):
                src = _find_nearest_lane_marker(items, row, col, lane_cols)
            if src is None:
                valid = False
                break
            src_meta = int(src.get("meta", 0))
            src_name = str(src.get("name", ""))
            src_mode = determine_mode(src_meta, src_name)
            if src_mode is None:
                valid = False
                break

            local[lane_slot] = {
                "argSlots": empties,
                "glassMeta": src_meta,
                "glassName": strip_colors(src_name).strip(),
                "mode": src_mode,
                "keyNorm": "" if src_meta == 0 else normalize(src_name),
            }
        if valid:
            out.update(local)
            break
    return out


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


def _find_repeated_lane_magic_slots(
    items: dict[int, dict],
    min_slot: int,
    max_slot: int,
    mode: str,
    min_total_markers: int = 7,
    min_consecutive_markers: int = 3,
    required_empty_rows: int = 3,
) -> dict[int, dict]:
    if min_slot > max_slot:
        return {}

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
        # once lane markers are recognized, inspect every column in lane span
        # (including enum/non-glass columns) and register only successful columns.
        lane_start = marker_cols[0]
        lane_end = marker_cols[-1]
        local: dict[int, dict] = {}
        lane_valid = True
        for col in range(lane_start, lane_end + 1):
            lane_slot = row * ROW_SIZE + col
            src = items.get(lane_slot)
            if not _is_repeated_marker(src, mode):
                src = _find_nearest_lane_marker(items, row, col, marker_cols)
            if src is None:
                lane_valid = False
                break
            arg_slots = []
            s = lane_slot + ROW_SIZE
            for _ in range(required_empty_rows):
                if s > max_inventory_slot or s in items:
                    lane_valid = False
                    break
                arg_slots.append(s)
                s += ROW_SIZE
            if not lane_valid:
                break
            src_name = strip_colors(str(src.get("name", ""))).strip()
            src_meta = int(src.get("meta", 0))
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


def _find_repeated_number_magic_slots(record: dict, items: dict[int, dict], min_slot: int, max_slot: int) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, min_slot, max_slot, mode="NUMBER")


def _find_repeated_text_magic_slots(record: dict, items: dict[int, dict], min_slot: int, max_slot: int) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, min_slot, max_slot, mode="TEXT")


def _find_repeated_item_magic_slots(record: dict, items: dict[int, dict], min_slot: int, max_slot: int) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, min_slot, max_slot, mode="ITEM")


def _find_repeated_location_magic_slots(record: dict, items: dict[int, dict], min_slot: int, max_slot: int) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, min_slot, max_slot, mode="LOCATION")


def _find_repeated_array_magic_slots(record: dict, items: dict[int, dict], min_slot: int, max_slot: int) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, min_slot, max_slot, mode="ARRAY")


def _find_repeated_any_magic_slots(record: dict, items: dict[int, dict], min_slot: int, max_slot: int) -> dict[int, dict]:
    return _find_repeated_lane_magic_slots(items, min_slot, max_slot, mode="ANY")


def parse_variant_info(lore: str) -> dict | None:
    if not lore:
        return None
    lines = [strip_colors(x).strip() for x in lore.split(" \\n ")]
    options = []
    selected = None
    for line in lines:
        if "●" in line or "○" in line:
            if "●" in line:
                bullet = "●"
                is_selected = True
            else:
                bullet = "○"
                is_selected = False
            text = line.split(bullet, 1)[1].strip()
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
    min_slot, max_slot = infer_slot_bounds(items)
    reserved = set()
    concat_magic = _find_concat_magic_slots(record, items, min_slot, max_slot)
    number_lane_magic = _find_repeated_number_magic_slots(record, items, min_slot, max_slot)
    text_lane_magic = _find_repeated_text_magic_slots(record, items, min_slot, max_slot)
    item_lane_magic = _find_repeated_item_magic_slots(record, items, min_slot, max_slot)
    location_lane_magic = _find_repeated_location_magic_slots(record, items, min_slot, max_slot)
    array_lane_magic = _find_repeated_array_magic_slots(record, items, min_slot, max_slot)
    any_lane_magic = _find_repeated_any_magic_slots(record, items, min_slot, max_slot)
    repeated_lane_maps = [
        number_lane_magic,
        text_lane_magic,
        item_lane_magic,
        location_lane_magic,
        array_lane_magic,
        any_lane_magic,
    ]
    lane_slots = set(concat_magic.keys())
    for lane_map in repeated_lane_maps:
        lane_slots.update(lane_map.keys())
    for slot, item in sorted(items.items()):
        if item["id"] != GLASS_ID:
            continue
        if item["meta"] == 15:
            continue
        mode = determine_mode(item["meta"], item["name"])
        if mode is None:
            continue
        if item_lane_magic and _is_repeated_marker(item, "ITEM") and slot not in item_lane_magic:
            continue
        if text_lane_magic and _is_repeated_marker(item, "TEXT") and slot not in text_lane_magic:
            continue
        if number_lane_magic and _is_repeated_marker(item, "NUMBER") and slot not in number_lane_magic:
            continue
        if location_lane_magic and _is_repeated_marker(item, "LOCATION") and slot not in location_lane_magic:
            continue
        if array_lane_magic and _is_repeated_marker(item, "ARRAY") and slot not in array_lane_magic:
            continue
        if any_lane_magic and _is_repeated_marker(item, "ANY") and slot not in any_lane_magic:
            continue
        # Lane layouts are emitted in one strict row-major pass later.
        if slot in lane_slots:
            continue
        magic_spec = (
            concat_magic.get(slot)
            or number_lane_magic.get(slot)
            or text_lane_magic.get(slot)
            or item_lane_magic.get(slot)
            or location_lane_magic.get(slot)
            or array_lane_magic.get(slot)
            or any_lane_magic.get(slot)
        )
        if magic_spec:
            candidate_slots = magic_spec["argSlots"]
            glass_meta = int(magic_spec["glassMeta"])
            glass_name = magic_spec["glassName"]
            key_norm = magic_spec["keyNorm"]
            mode = magic_spec["mode"]
        else:
            arg_slot = find_candidate_slot(items, slot, reserved, min_slot, max_slot)
            if arg_slot is None:
                continue
            candidate_slots = [arg_slot]
            glass_meta = int(item["meta"])
            glass_name = strip_colors(item["name"]).strip()
            key_norm = "" if item["meta"] == 0 else normalize(item["name"])

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

    _emit_lane_map_row_major(concat_magic)
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
