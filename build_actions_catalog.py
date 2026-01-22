import json
from pathlib import Path
import importlib.util

EXPORT_PATH = Path(r"C:\Users\ASUS\AppData\Roaming\.minecraft\regallactions_export.txt")
ALIASES_PATH = Path(r"C:\Users\ASUS\Documents\mlctmodified\src\assets\Aliases.json")
OUT_CATALOG = Path(r"C:\Users\ASUS\Documents\mlctmodified\out\actions_catalog.json")
OUT_ALIASES = Path(r"C:\Users\ASUS\Documents\mlctmodified\out\action_aliases.json")
OUT_DOCS = Path(r"C:\Users\ASUS\Documents\mlctmodified\out\language_quickstart.md")


TOOLS_PATH = Path(r"C:\Users\ASUS\Documents\mlctmodified\tools\extract_regallactions_args.py")

def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("extract_regallactions_args", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def read_export_lines(path: Path) -> list[str]:
    data = path.read_bytes()
    # Export is sometimes UTF-16 (lots of NUL bytes). Decode properly so §-colors and RU names
    # stay intact (affects completion + docs).
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        text = data.decode("utf-16", errors="replace")
    else:
        nul_ratio = (data.count(b"\x00") / max(1, len(data)))
        if nul_ratio > 0.05:
            text = data.decode("utf-16-le", errors="replace")
        else:
            text = data.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

def build_action_id(mod, record: dict, aliases: dict) -> str:
    key = mod.build_key(record, aliases)
    return key

def main():
    mod = load_module(TOOLS_PATH)
    aliases = mod.load_aliases(ALIASES_PATH)
    lines = read_export_lines(EXPORT_PATH)

    records = []
    chunk = []
    for line in lines:
        if line.startswith("# record"):
            if chunk:
                records.append(mod.parse_record_lines(chunk))
                chunk = []
        elif line.startswith("records="):
            continue
        else:
            chunk.append(line)
    if chunk:
        records.append(mod.parse_record_lines(chunk))

    catalog = []
    alias_suggestions = {}
    for record in records:
        action_id = build_action_id(mod, record, aliases)
        args = mod.extract_args(record)
        enums = mod.extract_enums(record)
        action = {
            "id": action_id,
            "path": record["path"],
            "category": record["category"],
            "subitem": record["subitem"],
            "gui": record["gui"],
            "signs": record["signs"],
            "args": args,
            "enums": enums,
        }
        catalog.append(action)

        # simple alias stub by sign1/sign2
        sign1 = record["signs"][0] if record["signs"] else ""
        sign2 = record["signs"][1] if len(record["signs"]) > 1 else ""
        if sign2:
            alias_suggestions.setdefault(sign1, {})
            alias_suggestions[sign1].setdefault(sign2, "")

    OUT_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    OUT_CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_ALIASES.write_text(json.dumps(alias_suggestions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_DOCS.write_text(
        """
# MLCT DSL (draft)

## Events
```
event(join) {
    message(text("Hello", player))
}
```

## Assignment
```
score = num(5)
name = text(player, " joined")
```

## Action args
- Action and arg aliases live in `out/action_aliases.json`.
- GUI slots are mapped from `out/actions_catalog.json`.

## Enum switches
- Enum items are detected by lore lines with filled/empty bullets.
- Use `clicks(slot,n)` in `/placeadvanced`.

## /placeadvanced example
```
/placeadvanced diamond_block "vhod" no iron_block "Obedinit texty" "slot(13)=var_save(setswa),slot(27)=TEXT1,slot(28)=TEXT2,clicks(22,2)=0"
```
""".strip() + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
