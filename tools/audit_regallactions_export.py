import json
import re
from pathlib import Path

from mldsl_paths import default_minecraft_export_path, ensure_dirs, export_audit_path

EXPORT = default_minecraft_export_path()
OUT_JSON = export_audit_path()

GLASS = "minecraft:stained_glass_pane"
ITEM_RE = re.compile(r"^item=slot\s+(\d+):\s+\[([^\s]+)\s+meta=(\d+)\]\s+(.*)$")


def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    return text


def read_text_utf8(path: Path) -> str:
    return path.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="replace")


def has_variant_lore(lore: str) -> bool:
    if not lore:
        return False
    for part in lore.split(" \\n "):
        if "●" in part or "○" in part:
            return True
    return False


def parse_records(text: str):
    records = []
    cur = None
    rec_no = None
    for line in text.splitlines():
        if line.startswith("# record "):
            if cur is not None:
                records.append((rec_no, cur))
            rec_no = int(line.split()[-1])
            cur = {"sign1": "", "sign2": "", "gui": "", "hasChest": False, "items": {}}
            continue
        if cur is None:
            continue
        if line.startswith("sign1="):
            cur["sign1"] = line[6:]
        elif line.startswith("sign2="):
            cur["sign2"] = line[6:]
        elif line.startswith("gui="):
            cur["gui"] = line[4:]
        elif line.startswith("hasChest="):
            cur["hasChest"] = line[9:].strip().lower() == "true"
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
            cur["items"][slot] = {"id": item_id, "meta": meta, "name": name, "lore": lore}
    if cur is not None:
        records.append((rec_no, cur))
    return records


def main():
    ensure_dirs()
    if not EXPORT.exists():
        raise SystemExit(
            "Не найден `regallactions_export.txt`.\n"
            f"Ожидаемый путь: {EXPORT}\n"
            "Положи экспорт в `.minecraft/regallactions_export.txt` или укажи `MLDSL_REGALLACTIONS_EXPORT`."
        )
    text = read_text_utf8(EXPORT)
    records = parse_records(text)
    out = {
        "recordsTotal": len(records),
        "brokenLikely": [],
        "noArgsButHasEnums": [],
        "stats": {"hasChestTrue": 0, "hasChestFalse": 0},
    }

    for no, r in records:
        if r["hasChest"]:
            out["stats"]["hasChestTrue"] += 1
        else:
            out["stats"]["hasChestFalse"] += 1

        items = r["items"]
        glass = [it for it in items.values() if it["id"] == GLASS]
        glass_nonblack = [it for it in glass if it["meta"] != 15]
        enum_items = [it for it in items.values() if it["id"] != GLASS and has_variant_lore(it.get("lore", ""))]

        if r["hasChest"] and not glass_nonblack and not enum_items:
            firstrow = [items.get(i) for i in range(0, 9)]
            ids = [it["id"] for it in firstrow if it]
            looks_menu = any(
                x in ids
                for x in [
                    "minecraft:beacon",
                    "minecraft:chest",
                    "minecraft:painting",
                    "minecraft:leather_boots",
                    "minecraft:apple",
                ]
            )
            out["brokenLikely"].append(
                {
                    "record": no,
                    "sign1": strip_colors(r["sign1"]).strip(),
                    "sign2": strip_colors(r["sign2"]).strip(),
                    "gui": strip_colors(r["gui"]).strip(),
                    "items": len(items),
                    "glass": len(glass),
                    "enumItems": len(enum_items),
                    "looksLikeMenuSnapshot": looks_menu,
                }
            )
        elif r["hasChest"] and not glass_nonblack and enum_items:
            out["noArgsButHasEnums"].append(
                {
                    "record": no,
                    "sign1": strip_colors(r["sign1"]).strip(),
                    "sign2": strip_colors(r["sign2"]).strip(),
                    "gui": strip_colors(r["gui"]).strip(),
                    "items": len(items),
                    "enumItems": len(enum_items),
                }
            )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"records={out['recordsTotal']}")
    print(f"brokenLikely={len(out['brokenLikely'])} wrote={OUT_JSON}")
    for e in out["brokenLikely"][:50]:
        tag = "menu-snapshot" if e["looksLikeMenuSnapshot"] else "no-args"
        print(f"#record {e['record']}: {e['sign1']} | {e['sign2']} | gui={e['gui']} [{tag}]")


if __name__ == "__main__":
    main()
