from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

repo_root_path = Path(__file__).resolve().parents[1]
if str(repo_root_path) not in sys.path:
    sys.path.insert(0, str(repo_root_path))

from mldsl_paths import (
    action_aliases_path,
    actions_catalog_path,
    api_aliases_path,
    apples_txt_path,
    default_minecraft_export_path,
    docs_dir,
    gamevalues_path,
    language_quickstart_path,
    out_dir,
)


@dataclass(frozen=True)
class Step:
    name: str
    script: str
    inputs: tuple[Path, ...]
    outputs: tuple[Path, ...]


def run(args: list[str]) -> None:
    print("+", " ".join(args))
    subprocess.check_call(args)


def _safe_max_mtime(paths: tuple[Path, ...]) -> float:
    newest = 0.0
    for path in paths:
        if not path.exists():
            continue
        newest = max(newest, path.stat().st_mtime)
    return newest


def _safe_min_mtime(paths: tuple[Path, ...]) -> float:
    existing = [p.stat().st_mtime for p in paths if p.exists()]
    if not existing:
        return 0.0
    return min(existing)


def _all_outputs_exist(paths: tuple[Path, ...]) -> bool:
    return all(path.exists() for path in paths)


def _stamps_dir() -> Path:
    return out_dir() / ".build_stamps"


def _stamp_path(step_name: str) -> Path:
    return _stamps_dir() / f"{step_name}.stamp"


def _should_run(step: Step, force: bool) -> tuple[bool, str]:
    stamp = _stamp_path(step.name)
    if force:
        return True, "force"

    if not _all_outputs_exist(step.outputs):
        return True, "missing output"

    if not stamp.exists():
        return True, "missing stamp"

    newest_input = _safe_max_mtime(step.inputs)
    oldest_output = _safe_min_mtime(step.outputs)
    stamp_mtime = stamp.stat().st_mtime

    # Rebuild if inputs are newer than outputs or than last successful stamp.
    if newest_input > oldest_output:
        return True, "inputs newer than outputs"
    if newest_input > stamp_mtime:
        return True, "inputs newer than stamp"
    return False, "up-to-date"


def _touch_stamp(step_name: str) -> None:
    _stamps_dir().mkdir(parents=True, exist_ok=True)
    stamp = _stamp_path(step_name)
    stamp.touch()
    now = time.time()
    os.utime(stamp, (now, now))


def _steps(repo_root: Path) -> list[Step]:
    tools = repo_root / "tools"
    export_path = default_minecraft_export_path()
    apples_path = apples_txt_path() or Path("<missing-apples.txt>")
    docs_readme = docs_dir() / "README.md"

    return [
        Step(
            name="actions_catalog",
            script="build_actions_catalog.py",
            inputs=(
                tools / "build_actions_catalog.py",
                tools / "extract_regallactions_args.py",
                export_path,
                repo_root / "src" / "assets" / "Aliases.json",
            ),
            outputs=(
                actions_catalog_path(),
                action_aliases_path(),
                language_quickstart_path(),
            ),
        ),
        Step(
            name="api_aliases",
            script="build_api_aliases.py",
            inputs=(
                tools / "build_api_aliases.py",
                actions_catalog_path(),
                repo_root / "tools" / "action_translations.json",
                repo_root / "tools" / "action_translations_by_id.json",
            ),
            outputs=(api_aliases_path(),),
        ),
        Step(
            name="gamevalues",
            script="build_gamevalues.py",
            inputs=(
                tools / "build_gamevalues.py",
                apples_path,
            ),
            outputs=(gamevalues_path(),),
        ),
        Step(
            name="api_docs",
            script="generate_api_docs.py",
            inputs=(
                tools / "generate_api_docs.py",
                api_aliases_path(),
                actions_catalog_path(),
            ),
            outputs=(
                docs_readme,
                docs_dir() / "ALL_FUNCTIONS.md",
                docs_dir() / "MLDSL_GUIDE.md",
            ),
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Incremental MLDSL build pipeline")
    parser.add_argument("--force", action="store_true", help="Rebuild all steps")
    parser.add_argument("--verbose", action="store_true", help="Print skip reasons")
    args = parser.parse_args()

    repo_root = repo_root_path
    python = sys.executable
    executed = 0
    skipped = 0

    for step in _steps(repo_root):
        should_run, reason = _should_run(step, force=args.force)
        script_path = repo_root / "tools" / step.script
        if should_run:
            print(f"[RUN ] {step.name}: {reason}")
            run([python, str(script_path)])
            _touch_stamp(step.name)
            executed += 1
        else:
            if args.verbose:
                print(f"[SKIP] {step.name}: {reason}")
            else:
                print(f"[SKIP] {step.name}")
            skipped += 1

    print(f"[DONE] executed={executed} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
