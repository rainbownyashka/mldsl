from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--use-seed",
        action="store_true",
        help="Use committed seed/out snapshot (for CI / releases). Skips tools/build_all.py.",
    )
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    repo = Path(__file__).resolve().parents[1]
    payload = repo / "dist" / "payload"
    app_dir = payload / "app"
    assets_dir = payload / "assets"
    seed_out_dir = payload / "seed_out"

    payload.mkdir(parents=True, exist_ok=True)

    python = sys.executable

    # 1) Prepare out/ that will be shipped with the installer.
    #    - Dev/local mode: regenerate %LOCALAPPDATA%\MLDSL\out using your local exports.
    #    - CI/release mode: use committed seed/out snapshot (no hidden fallback).
    if args.use_seed:
        seed_out = repo / "seed" / "out"
        if not seed_out.exists():
            raise SystemExit(f"--use-seed was set but seed/out was not found: {seed_out}")
    else:
        run([python, str(repo / "tools" / "build_all.py")])

    # 2) Build mldsl.exe (Nuitka standalone).
    dist_dir = repo / "dist"
    if dist_dir.exists():
        # keep payload, remove old nuitka outputs
        for p in dist_dir.iterdir():
            if p.name == "payload":
                continue
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    run(
        [
            python,
            "-m",
            "nuitka",
            str(repo / "mldsl_cli.py"),
            "--standalone",
            "--assume-yes-for-downloads",
            "--output-dir=dist",
            "--output-filename=mldsl.exe",
        ]
    )

    nuitka_dist = repo / "dist" / "mldsl_cli.dist"
    if not nuitka_dist.exists():
        raise SystemExit(f"Nuitka output not found: {nuitka_dist}")

    copy_tree(nuitka_dist, app_dir)

    # 3) Copy read-only assets needed by the compiler.
    assets_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "allactions.txt", assets_dir / "allactions.txt")
    shutil.copy2(repo / "src" / "assets" / "Aliases.json", assets_dir / "Aliases.json")
    shutil.copy2(repo / "src" / "assets" / "LangTokens.json", assets_dir / "LangTokens.json")

    # 4) Seed out/ into the payload (installer copies it into %LOCALAPPDATA%\MLDSL\out).
    #    This makes mldsl.exe work immediately after install.
    if args.use_seed:
        copy_tree(repo / "seed" / "out", seed_out_dir)
    else:
        local_out = Path.home() / "AppData" / "Local" / "MLDSL" / "out"
        if not local_out.exists():
            raise SystemExit(f"Expected generated out/ at: {local_out}")
        copy_tree(local_out, seed_out_dir)

    print("")
    print("OK: prepared payload at:", payload)
    print("- app:", app_dir)
    print("- assets:", assets_dir)
    print("- seed_out:", seed_out_dir)
    print("")
    print("Optional: build VSIX and place at dist/payload/mldsl-helper.vsix for auto-install.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
