import json
from pathlib import Path

from mldsl_paths import (
    action_translations_path,
    action_translations_template_path,
    api_aliases_path,
    ensure_dirs,
)

API_PATH = api_aliases_path()
OUT_PATH = action_translations_template_path()


def main():
    ensure_dirs()
    if not API_PATH.exists():
        raise FileNotFoundError(
            "Не найден `api_aliases.json`.\n"
            f"Путь: {API_PATH}\n"
            "Сначала запусти: python tools/build_api_aliases.py"
        )
    data = json.loads(API_PATH.read_text(encoding="utf-8"))
    template = {}
    for module, funcs in data.items():
        for name, spec in funcs.items():
            key = f"{module}.{name}"
            template[key] = {
                "name": name,
                "sign1": spec.get("sign1"),
                "sign2": spec.get("sign2"),
                "gui": spec.get("gui"),
                "description": spec.get("description"),
                "aliases": spec.get("aliases", []),
            }

    existing = action_translations_path()
    if existing.exists():
        user = json.loads(existing.read_text(encoding="utf-8"))
        for key, custom in user.items():
            if key in template:
                template[key].update(custom)
    OUT_PATH.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"dumped template to {OUT_PATH}")


if __name__ == "__main__":
    main()
