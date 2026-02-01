from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def _executable_dir() -> Path:
    # Works for python, pyinstaller onefile/onedir, nuitka, etc.
    return Path(getattr(sys, "_MEIPASS", Path(sys.argv[0]).resolve().parent)).resolve()


def _portable_enabled() -> bool:
    v = os.environ.get("MLDSL_PORTABLE", "").strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return (_executable_dir() / "portable.flag").exists()


def data_root() -> Path:
    """
    Directory for ALL mutable MLDSL data:
    - generated out/ (api_aliases.json, docs, etc.)
    - caches, logs, etc.

    Default: %LOCALAPPDATA%\\MLDSL
    Override: MLDSL_DATA_DIR
    Portable: MLDSL_PORTABLE=1 or portable.flag near exe -> <exe_dir>\\MLDSL
    """
    override = os.environ.get("MLDSL_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if _portable_enabled():
        return (_executable_dir() / "MLDSL").resolve()

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return (Path(local_app_data) / "MLDSL").resolve()

    return (Path.home() / ".mldsl").resolve()


def ensure_dirs() -> None:
    out_dir().mkdir(parents=True, exist_ok=True)
    docs_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    inputs_dir().mkdir(parents=True, exist_ok=True)
    (data_root() / "assets").mkdir(parents=True, exist_ok=True)


def out_dir() -> Path:
    return data_root() / "out"


def docs_dir() -> Path:
    return out_dir() / "docs"


def logs_dir() -> Path:
    return data_root() / "logs"


def inputs_dir() -> Path:
    return data_root() / "inputs"


def api_aliases_path() -> Path:
    return out_dir() / "api_aliases.json"


def actions_catalog_path() -> Path:
    return out_dir() / "actions_catalog.json"


def action_aliases_path() -> Path:
    return out_dir() / "action_aliases.json"


def language_quickstart_path() -> Path:
    return out_dir() / "language_quickstart.md"


def gamevalues_path() -> Path:
    return out_dir() / "gamevalues.json"


def export_audit_path() -> Path:
    return out_dir() / "export_audit.json"


def arg_parse_issues_path() -> Path:
    return out_dir() / "arg_parse_issues.json"


def action_translations_by_id_path() -> Path:
    return repo_root() / "tools" / "action_translations_by_id.json"


def action_translations_path() -> Path:
    return repo_root() / "tools" / "action_translations.json"


def action_translations_template_path() -> Path:
    return out_dir() / "action_translations_template.json"


def _first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def aliases_json_path() -> Path:
    candidates = [
        repo_root() / "src" / "assets" / "Aliases.json",  # dev repo
        _executable_dir() / "assets" / "Aliases.json",  # packaged
        data_root() / "assets" / "Aliases.json",  # user override
    ]
    p = _first_existing(candidates)
    if p:
        return p
    raise FileNotFoundError(
        "Не найден `Aliases.json`.\nОжидалось в одном из путей:\n" + "\n".join(f"- {c}" for c in candidates)
    )


def lang_tokens_path() -> Path:
    candidates = [
        repo_root() / "src" / "assets" / "LangTokens.json",
        _executable_dir() / "assets" / "LangTokens.json",
        data_root() / "assets" / "LangTokens.json",
    ]
    p = _first_existing(candidates)
    if p:
        return p
    raise FileNotFoundError(
        "Не найден `LangTokens.json`.\nОжидалось в одном из путей:\n" + "\n".join(f"- {c}" for c in candidates)
    )


def allactions_txt_path() -> Path:
    candidates = [
        repo_root() / "allactions.txt",
        _executable_dir() / "assets" / "allactions.txt",
        data_root() / "assets" / "allactions.txt",
    ]
    p = _first_existing(candidates)
    if p:
        return p
    raise FileNotFoundError(
        "Не найден `allactions.txt`.\nОжидалось в одном из путей:\n" + "\n".join(f"- {c}" for c in candidates)
    )


def default_minecraft_dir() -> Path:
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / ".minecraft"
    return Path.home() / ".minecraft"


def default_minecraft_export_path() -> Path:
    override = os.environ.get("MLDSL_REGALLACTIONS_EXPORT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return default_minecraft_dir() / "regallactions_export.txt"


def apples_txt_path() -> Path | None:
    override = os.environ.get("MLDSL_APPLES_TXT", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    candidates = [
        repo_root() / "apples.txt",
        inputs_dir() / "apples.txt",
        Path.home() / "Documents" / "apples.txt",
    ]
    return _first_existing(candidates)

