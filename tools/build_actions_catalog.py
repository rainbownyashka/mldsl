import json
from pathlib import Path
import importlib.util

from _bootstrap import ensure_repo_root_on_syspath

ensure_repo_root_on_syspath()

from mldsl_paths import (
    action_aliases_path,
    actions_catalog_path,
    aliases_json_path,
    default_minecraft_export_path,
    ensure_dirs,
    language_quickstart_path,
)


EXPORT_PATH = default_minecraft_export_path()
ALIASES_PATH = aliases_json_path()
OUT_CATALOG = actions_catalog_path()
OUT_ALIASES = action_aliases_path()
OUT_DOCS = language_quickstart_path()

TOOLS_PATH = Path(__file__).resolve().parent / "extract_regallactions_args.py"

def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("extract_regallactions_args", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def read_export_lines(path: Path) -> list[str]:
    data = path.read_bytes().replace(b"\x00", b"")
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()

def build_action_id(mod, record: dict, aliases: dict) -> str:
    key = mod.build_key(record, aliases)
    return key

def main():
    ensure_dirs()
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(
            "Не найден `regallactions_export.txt`.\n"
            f"Ожидаемый путь: {EXPORT_PATH}\n"
            "\n"
            "Скопируй экспорт в `.minecraft/regallactions_export.txt` или укажи путь через:\n"
            "  MLDSL_REGALLACTIONS_EXPORT=<путь>\n"
        )
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
