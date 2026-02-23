from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import extract_regallactions_args as mod
from extract_regallactions_args import _find_concat_magic_slots, extract_args


def _mk_glass(meta: int = 1, name: str = "Переменная"):
    return {
        "id": "minecraft:stained_glass_pane",
        "meta": meta,
        "name": name,
        "lore": "",
    }


def _mk_record(sign2: str, items: dict[int, dict]):
    return {
        "path": "",
        "category": "",
        "subitem": "",
        "gui": "",
        "signs": ["", sign2, "", ""],
        "hasChest": True,
        "items": items,
    }


def test_concat_magic_detects_lane_and_expands_empty_below_slots(monkeypatch):
    items = {}
    # Row 1: 4 glass + one non-glass gap + 4 glass.
    for slot in (9, 10, 11, 12, 14, 15, 16, 17):
        items[slot] = _mk_glass()
    items[13] = {"id": "minecraft:stick", "meta": 0, "name": "", "lore": ""}
    # For this pattern lane occupies all 9 columns, so force test bounds explicitly.
    monkeypatch.setattr(mod, "infer_slot_bounds", lambda _items: (9, 44))

    record = _mk_record("Объединить тексты", items)
    args = extract_args(record)
    by_glass = {}
    for a in args:
        by_glass.setdefault(a["glassSlot"], []).append(a["argSlot"])

    assert sorted(by_glass[9]) == [18, 27, 36]
    assert sorted(by_glass[10]) == [19, 28, 37]
    assert sorted(by_glass[11]) == [20, 29, 38]
    assert sorted(by_glass[12]) == [21, 30, 39]
    assert sorted(by_glass[13]) == [22, 31, 40]
    assert sorted(by_glass[14]) == [23, 32, 41]
    assert sorted(by_glass[15]) == [24, 33, 42]
    assert sorted(by_glass[16]) == [25, 34, 43]
    assert sorted(by_glass[17]) == [26, 35, 44]


def test_concat_magic_rejects_non_empty_slots_below_lane():
    items = {}
    for slot in (9, 10, 11, 12, 14, 15, 16, 17):
        items[slot] = _mk_glass()
    items[13] = {"id": "minecraft:stick", "meta": 0, "name": "", "lore": ""}
    items[18] = {"id": "minecraft:stick", "meta": 0, "name": "", "lore": ""}
    record = _mk_record("Объединить текст", items)
    got = _find_concat_magic_slots(record, items, 9, 44)
    assert got == {}


def test_concat_magic_accepts_equal_sign_action_label(monkeypatch):
    items = {}
    for slot in (9, 10, 11, 12, 14, 15, 16, 17):
        items[slot] = _mk_glass(meta=3, name="Текст(ы)")
    items[13] = {"id": "minecraft:stick", "meta": 0, "name": "", "lore": ""}
    monkeypatch.setattr(mod, "infer_slot_bounds", lambda _items: (9, 44))

    record = _mk_record("=", items)
    args = extract_args(record)
    assert len(args) == 27
    assert any(a["glassSlot"] == 13 and a["argSlot"] == 22 for a in args)


def test_concat_magic_accepts_gap_on_slot4_pattern_3_plus_5(monkeypatch):
    items = {}
    # one-based row slots: 1..3 marker, 4 gap, 5..9 marker
    for slot in (9, 10, 11, 13, 14, 15, 16, 17):
        items[slot] = _mk_glass(meta=3, name="Текст(ы)")
    items[12] = {"id": "minecraft:stick", "meta": 0, "name": "", "lore": ""}
    monkeypatch.setattr(mod, "infer_slot_bounds", lambda _items: (9, 44))

    record = _mk_record("=", items)
    args = extract_args(record)
    assert len(args) == 27
    # gap column (slot 12) must participate in expansion
    assert any(a["glassSlot"] == 12 and a["argSlot"] == 21 for a in args)


def test_concat_magic_accepts_gap_on_slot6_pattern_5_plus_3(monkeypatch):
    items = {}
    # one-based row slots: 1..5 marker, 6 gap, 7..9 marker
    for slot in (9, 10, 11, 12, 13, 15, 16, 17):
        items[slot] = _mk_glass(meta=3, name="Текст(ы)")
    items[14] = {"id": "minecraft:stick", "meta": 0, "name": "", "lore": ""}
    monkeypatch.setattr(mod, "infer_slot_bounds", lambda _items: (9, 44))

    record = _mk_record("=", items)
    args = extract_args(record)
    assert len(args) == 27
    # gap column (slot 14) must participate in expansion
    assert any(a["glassSlot"] == 14 and a["argSlot"] == 23 for a in args)


def test_concat_magic_accepts_double_gap_with_center_glass_pattern(monkeypatch):
    items = {}
    # one-based row: 1..3 glass, 4 any, 5 glass, 6 any, 7..9 glass -> total 7 glasses
    for slot in (9, 10, 11, 13, 15, 16, 17):
        items[slot] = _mk_glass(meta=3, name="Текст(ы)")
    items[12] = {"id": "minecraft:stick", "meta": 0, "name": "", "lore": ""}
    items[14] = {"id": "minecraft:apple", "meta": 0, "name": "", "lore": ""}
    monkeypatch.setattr(mod, "infer_slot_bounds", lambda _items: (9, 44))

    record = _mk_record("=", items)
    args = extract_args(record)
    assert len(args) == 27
    assert any(a["glassSlot"] == 12 and a["argSlot"] == 21 for a in args)
    assert any(a["glassSlot"] == 13 and a["argSlot"] == 22 for a in args)
    assert any(a["glassSlot"] == 14 and a["argSlot"] == 23 for a in args)


def test_multiply_repeated_number_lane_expands_to_28_number_slots():
    items = {
        3: _mk_glass(meta=1, name="Динамическая переменная"),
        5: _mk_glass(meta=14, name="Число*"),
    }
    lane_lore = "Положите ниже ⇩ число(а)"
    for slot in range(18, 27):
        items[slot] = _mk_glass(meta=14, name="Число(а)")
        items[slot]["lore"] = lane_lore

    record = _mk_record("*", items)
    args = extract_args(record)
    number_args = [a for a in args if a["mode"] == "NUMBER"]

    # 1 base number + (9 columns * 3 rows) repeated-number slots.
    assert len(number_args) == 28
    got_slots = sorted(a["argSlot"] for a in number_args)
    assert 14 in got_slots
    assert all(s in got_slots for s in range(27, 54))


def test_repeated_lane_registers_arg_slots_in_row_major_order():
    items = {
        3: _mk_glass(meta=1, name="Динамическая переменная"),
        5: _mk_glass(meta=14, name="Число*"),
    }
    lane_lore = "Положите ниже ⇩ число(а)"
    for slot in range(18, 27):
        items[slot] = _mk_glass(meta=14, name="Число(а)")
        items[slot]["lore"] = lane_lore

    record = _mk_record("*", items)
    args = extract_args(record)
    repeated_only = [a["argSlot"] for a in args if a["mode"] == "NUMBER" and a["argSlot"] >= 27]
    assert repeated_only == list(range(27, 54))


def test_item_lane_uses_other_valid_row_when_lower_row_is_blocked():
    items = {}
    for slot in range(0, 9):
        items[slot] = _mk_glass(meta=4, name="Предмет(ы)")
    for slot in range(36, 45):
        items[slot] = _mk_glass(meta=4, name="Предмет(ы)")
    # Lower row has occupied neighbors and must not be chosen as lane source.
    items[45] = _mk_glass(meta=15, name="")
    items[46] = _mk_glass(meta=15, name="")
    items[47] = _mk_glass(meta=15, name="")
    items[48] = _mk_glass(meta=3, name="Текст*")
    items[50] = _mk_glass(meta=3, name="Текст*")
    items[53] = {"id": "minecraft:chest", "meta": 0, "name": "Тип инвентаря", "lore": ""}

    record = _mk_record("Открыть меню", items)
    args = extract_args(record)
    item_args = [a for a in args if a["mode"] == "ITEM"]

    assert len(item_args) == 27
    got_slots = sorted(a["argSlot"] for a in item_args)
    assert got_slots == list(range(9, 36))
