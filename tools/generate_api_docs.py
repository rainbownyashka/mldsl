import json
import os
from pathlib import Path

API_PATH = Path(r"C:\Users\ASUS\Documents\mlctmodified\out\api_aliases.json")
OUT_DIR = Path(r"C:\Users\ASUS\Documents\mlctmodified\out\docs")


def md_escape(text: str) -> str:
    return (text or "").replace("`", "\\`")


def first_line(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    return t.splitlines()[0].strip()


def fmt_sig(module_name: str, func_name: str, params: list[dict]) -> str:
    def fmt_param(p: dict) -> str:
        n = p.get("name") or ""
        m = p.get("mode") or ""
        s = p.get("slot")
        if m and s is not None:
            return f"{n}: {m} (slot {s})"
        if m:
            return f"{n}: {m}"
        return n

    return f"{module_name}.{func_name}(" + ", ".join(fmt_param(p) for p in params) + ")"


def write_mldsl_guide(out_dir: Path):
    guide = r"""
# MLDSL Guide (generated)

This is a short "how the compiler thinks" guide for people and for AI agents generating `.mldsl`.
The action catalog comes from `out/api_aliases.json`.

## Build pipeline

- `python tools/build_all.py`
  - Builds `out/actions_catalog.json`
  - Builds `out/api_aliases.json`
  - Generates docs into `out/docs`

## Basic syntax

### Events

```
event(join) {
    player.message("Hello!")
}
```

### Functions

Supported keywords: `func`, `function`, `def`, `функция`.
Both `func hello {}` and `func(hello) {}` are accepted.

```
func hello {
    player.message("Hi")
}
```

### Cycles / loops

```
loop mycycle every 5 {
    player.message("tick")
}
```

### Calling actions

API calls are `module.func(args...)`. Arguments can be positional or `key=value`
depending on the function’s `params` (see per-function docs).

```
player.message("text1", "text2")
if_player.сообщение_равно("!ping") {
    player.message("pong")
}
```

### Calling a function by name

```
hello()
call(hello)             # sync by default
call(hello, async=true) # async/sync is enum inside the GUI
```

### Variables and assignment

Variable names may contain placeholders, e.g. `%selected%counter`.

- Normal variable: `var(name)`
- Saved variable: `var_save(name)`

Assignment sugar compiles into variable actions (`var.set_value`, etc):

```
a = 1
save a = 1
a ~ 1               # shorthand for save a = 1
%selected%counter = %selected%counter + 1
```

Numeric expressions are limited to `+ - * /` with constants and names (no nested calls).
If an expression needs multiple server actions, compiler prints a warning about extra actions.

### `if` conditions

Examples:

```
if %selected%counter < 2 {
    player.message("low")
}

ifexists(%player%flag) {
    player.message("exists")
}

iftext "a" in "abc" {
    player.message("ok")
}
```

### Enums (switchers)

Some actions have enum switchers (lore bullets) and are represented in docs as `enums`.
You can usually pass the enum by name (generated enum name from docs) as `key=value`
and the compiler converts it to `clicks(slot,n)=0`.

## Output model (what compiler produces)

The compiler produces a linear plan of entries like:

```
{ "block": "diamond_block", "name": "вход", "args": "no" }
{ "block": "cobblestone", "name": "Отправить сообщение||Сообщение", "args": "slot(9)=text(hi)" }
{ "block": "newline" }
```

This plan is executed by the mod using the existing `/placeadvanced` mechanism.

## Important limitations (server constraints)

- `/placeadvanced` has a command length limit (~240 chars).
- Some bulk calls are chunked by the compiler (18 names per action).
""".strip() + "\n"

    (out_dir / "MLDSL_GUIDE.md").write_text(guide, encoding="utf-8")

def copy_quickstarts(out_dir: Path) -> list[str]:
    copied = []
    out_root = out_dir.parent
    candidates = [
        (out_root / "language_quickstart.md", out_dir / "QUICKSTART.md"),
        (out_root / "language_quickstart_ru.md", out_dir / "QUICKSTART_RU.md"),
        (out_root / "language_quickstart_rus.md", out_dir / "QUICKSTART_RU.md"),
        (out_root / "language_quickstart_ru-RU.md", out_dir / "QUICKSTART_RU.md"),
    ]
    for src, dst in candidates:
        if not src.exists():
            continue
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(dst.name)
    return sorted(set(copied))


def main():
    api = json.loads(API_PATH.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    quickstarts = copy_quickstarts(OUT_DIR)
    write_mldsl_guide(OUT_DIR)

    has_ru_guide = (OUT_DIR / "MLDSL_GUIDE_RU.md").exists()
    has_ru_quickstart = "QUICKSTART_RU.md" in quickstarts

    index_lines = ["# MLDSL API", ""]
    index_lines.append("## Quickstart")
    index_lines.append("")
    index_lines.append("- English: `QUICKSTART.md`")
    if has_ru_quickstart:
        index_lines.append("- Русский: `QUICKSTART_RU.md`")
    else:
        index_lines.append("- Русский: (not found) — add `out/language_quickstart_ru.md` to generate it")
    index_lines.append("")

    index_lines.append("## Guides")
    index_lines.append("")
    index_lines.append("- English: `MLDSL_GUIDE.md`")
    if has_ru_guide:
        index_lines.append("- Русский: `MLDSL_GUIDE_RU.md`")
    else:
        index_lines.append("- Русский: (not found)")
    index_lines.append("")

    index_lines.append("## Full API")
    index_lines.append("")
    index_lines.append("- `ALL_FUNCTIONS.md`")
    index_lines.append("")
    all_lines = [
        "# MLDSL API (All Functions)",
        "",
        "Autogenerated from `out/api_aliases.json`.",
        "",
    ]

    for module_name in sorted(api.keys()):
        mod_dir = OUT_DIR / module_name
        mod_dir.mkdir(parents=True, exist_ok=True)
        index_lines.append(f"## `{module_name}`")
        index_lines.append("")

        funcs = api[module_name]
        for func_name in sorted(funcs.keys()):
            spec = funcs[func_name]
            params = spec.get("params") or []
            enums = spec.get("enums") or []
            aliases = spec.get("aliases") or []
            description = (spec.get("description") or "").strip()
            description_raw = (spec.get("descriptionRaw") or "").strip()

            doc_path = mod_dir / f"{func_name}.md"
            sig = fmt_sig(module_name, func_name, params)
            lines = [f"# `{sig}`", ""]
            if aliases:
                lines.append("- `aliases`: " + ", ".join(f"`{md_escape(a)}`" for a in aliases))
            lines.append(f"- `sign1`: `{md_escape(spec.get('sign1',''))}`")
            lines.append(f"- `sign2`: `{md_escape(spec.get('sign2',''))}`")
            if spec.get("gui"):
                lines.append(f"- `gui`: `{md_escape(spec.get('gui',''))}`")
            lines.append(f"- `id`: `{md_escape(spec.get('id',''))}`")
            lines.append("")

            if description:
                lines.append("## Description")
                lines.append("```")
                lines.append(description)
                lines.append("```")
                lines.append("")
            if description_raw and description_raw != description:
                lines.append("## DescriptionRaw")
                lines.append("```")
                lines.append(description_raw)
                lines.append("```")
                lines.append("")

            if params:
                lines.append("## Params")
                for p in params:
                    lines.append(f"- `{p.get('name','')}`: `{p.get('mode','')}` slot `{p.get('slot')}`")
                lines.append("")

            if enums:
                lines.append("## Enums")
                for e in enums:
                    lines.append(f"- `{e.get('name')}`: slot `{e.get('slot')}`")
                    opts = e.get("options") or {}
                    for k, v in opts.items():
                        lines.append(f"  - `{md_escape(k)}` -> clicks `{v}`")
                lines.append("")

            doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            rel = os.path.relpath(doc_path, OUT_DIR)
            rel_md = rel.replace("\\", "/")
            index_lines.append(f"- `{module_name}.{func_name}` -> `{rel_md}`")

            all_lines.append(f"## `{module_name}.{func_name}`")
            all_lines.append("")
            all_lines.append(f"- `signature`: `{sig}`")
            all_lines.append(f"- `doc`: `{rel_md}`")
            if spec.get("gui"):
                all_lines.append(f"- `gui`: `{md_escape(spec.get('gui',''))}`")
            all_lines.append(f"- `sign1`: `{md_escape(spec.get('sign1',''))}`")
            all_lines.append(f"- `sign2`: `{md_escape(spec.get('sign2',''))}`")
            if aliases:
                all_lines.append("- `aliases`: " + ", ".join(f"`{md_escape(a)}`" for a in aliases))
            summary = first_line(description) or first_line(description_raw)
            if summary:
                all_lines.append(f"- `summary`: {md_escape(summary)}")
            all_lines.append("")

        index_lines.append("")

    (OUT_DIR / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    (OUT_DIR / "ALL_FUNCTIONS.md").write_text("\n".join(all_lines) + "\n", encoding="utf-8")
    print(f"wrote docs to {OUT_DIR}")


if __name__ == "__main__":
    main()
