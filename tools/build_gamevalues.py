import json
import re
import shutil
import os
from pathlib import Path

from _bootstrap import ensure_repo_root_on_syspath

ensure_repo_root_on_syspath()

from mldsl_paths import (
    apples_txt_path,
    default_minecraft_dir,
    ensure_dirs,
    gamevalues_path,
)

APPLIES_PATH = apples_txt_path()
OUT_PATH = gamevalues_path()
MC_OUT_PATH = default_minecraft_dir() / "bettercode_gamevalues.json"


def strip_mc_colors(s: str) -> str:
    if s is None:
        return ""
    # Fix occasional 0x15 -> §
    s = s.replace("\u0015", "\u00a7")
    # remove §x formatting
    s = re.sub(r"\u00a7.", "", s)
    # remove control chars
    s = re.sub(r"[\x00-\x1f]", "", s)
    return s


def norm_key(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", strip_mc_colors(s).lower()).strip()


def extract_json_objects(text: str) -> list[dict]:
    objs: list[dict] = []
    # Brace-matching that ignores braces inside JSON string literals (nbt contains {...} inside quotes).
    depth = 0
    start = None
    in_str = False
    str_ch = ""
    esc = False
    for i, ch in enumerate(text):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch in ("\"", "'"):
            if in_str and ch == str_ch:
                in_str = False
                str_ch = ""
            elif not in_str:
                in_str = True
                str_ch = ch
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    blob = text[start : i + 1]
                    start = None
                    try:
                        objs.append(json.loads(blob))
                    except Exception:
                        pass
    return objs


def main() -> int:
    ensure_dirs()
    if APPLIES_PATH is None:
        raise SystemExit(
            "Не найден файл `apples.txt` (список игровых значений).\n"
            "Положи его в одно из мест:\n"
            "- `apples.txt` рядом с репозиторием\n"
            f"- или `{OUT_PATH.parent.parent / 'inputs' / 'apples.txt'}`\n"
            "- или `~/Documents/apples.txt`\n"
            "\n"
            "Либо укажи путь через `MLDSL_APPLES_TXT=<путь>`.\n"
        )
    if not APPLIES_PATH.exists():
        raise SystemExit(f"Не найден файл: {APPLIES_PATH}")

    raw = APPLIES_PATH.read_text(encoding="utf-8", errors="replace")

    # If apples.txt was already cleaned into a single JSON payload, load it directly.
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None

    if isinstance(parsed, dict) and isinstance(parsed.get("values"), list):
        by_loc: dict[str, dict] = {}
        by_key: dict[str, str] = {}
        for it in parsed.get("values") or []:
            if not isinstance(it, dict):
                continue
            loc = str(it.get("locName") or "").strip()
            if not loc:
                continue
            display = strip_mc_colors(it.get("display") or "")
            by_loc[loc] = {
                "locName": loc,
                "display": display,
                "id": it.get("id") or "",
                "meta": int(it.get("meta") or 0),
                "lore": strip_mc_colors(it.get("lore") or ""),
            }
            if display:
                k = norm_key(display)
                if k and k not in by_key:
                    by_key[k] = loc

        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "count": len(by_loc), "byLocName": by_loc, "byKey": by_key}
        OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {OUT_PATH} values={len(by_loc)} (from cleaned apples.txt)")
        if MC_OUT_PATH.parent.exists():
            MC_OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Wrote {MC_OUT_PATH}")
        return 0

    objs = extract_json_objects(raw)

    by_loc: dict[str, dict] = {}
    by_key: dict[str, str] = {}

    for o in objs:
        slots = o.get("slots") if isinstance(o, dict) else None
        if not isinstance(slots, list):
            continue
        for it in slots:
            if not isinstance(it, dict):
                continue
            nbt = it.get("nbt") or ""
            m = re.search(r'LocName:\"([A-Z0-9_]+)\"', nbt)
            if not m:
                # also accept JSON form (just in case)
                m = re.search(r'\"LocName\"\\s*:\\s*\"([A-Z0-9_]+)\"', nbt)
            if not m:
                continue
            loc = m.group(1)
            display = strip_mc_colors(it.get("display") or it.get("displayName") or "")
            lore = strip_mc_colors(it.get("lore") or "")
            item_id = it.get("id") or ""
            meta = int(it.get("meta") or 0)
            by_loc[loc] = {
                "locName": loc,
                "display": display,
                "id": item_id,
                "meta": meta,
                "lore": lore,
            }
            if display:
                k = norm_key(display)
                if k and k not in by_key:
                    by_key[k] = loc

    # Fallback: apples.txt can contain truncated JSON (chat copy) but still has NBT snippets.
    # Extract LocName + Name directly from raw text.
    for m in re.finditer(r'LocName:\\\"([A-Z0-9_]+)\\\"', raw):
        loc = m.group(1)
        if loc in by_loc:
            continue
        window = raw[m.start() : m.start() + 600]
        name_m = re.search(r'Name:\\\"([^\\\\\"]+)\\\"', window)
        display = strip_mc_colors(name_m.group(1)) if name_m else ""
        id_m = re.search(r'id:\\\"([a-z0-9_]+:[a-z0-9_]+)\\\"', window)
        item_id = id_m.group(1) if id_m else ""
        by_loc[loc] = {
            "locName": loc,
            "display": display,
            "id": item_id,
            "meta": 0,
            "lore": "",
        }
        if display:
            k = norm_key(display)
            if k and k not in by_key:
                by_key[k] = loc

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "count": len(by_loc),
        "byLocName": by_loc,
        "byKey": by_key,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH} values={len(by_loc)}")
    if MC_OUT_PATH.parent.exists():
        MC_OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {MC_OUT_PATH}")

    # Optional: rewrite apples.txt into a clean JSON file (backup original once).
    # Enabled by env var CLEAN_APPLES=1 to keep build pipeline stable by default.
    if str(os.environ.get("CLEAN_APPLES", "")).strip() == "1":
        bak = APPLIES_PATH.with_suffix(".txt.bak")
        if APPLIES_PATH.exists() and not bak.exists():
            shutil.copyfile(str(APPLIES_PATH), str(bak))
            print(f"Backup: {bak}")
        cleaned = {
            "version": 1,
            "count": len(by_loc),
            "values": list(by_loc.values()),
        }
        APPLIES_PATH.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Rewrote {APPLIES_PATH} (clean JSON)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
