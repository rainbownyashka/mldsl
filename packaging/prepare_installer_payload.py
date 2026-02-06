from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    candidates = [name]
    if sys.platform.startswith("win"):
        candidates = [name, f"{name}.cmd", f"{name}.exe", f"{name}.bat"]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return name


def _missing_cmd_hint(name: str) -> str:
    if name in {"npm", "npx"}:
        return (
            "Node.js/npm not found in PATH. "
            "For CI use actions/setup-node, for local install Node.js, "
            "or run with --no-vsix if you intentionally skip extension packaging."
        )
    return f"required command not found: {name}"


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    if not cmd:
        raise SystemExit("internal error: empty command")
    resolved = [*cmd]
    resolved[0] = _resolve_executable(resolved[0])
    prefix = f"+ (cwd={cwd}) " if cwd else "+ "
    print(prefix + " ".join(resolved))
    try:
        subprocess.check_call(resolved, cwd=str(cwd) if cwd else None)
    except FileNotFoundError:
        raise SystemExit(_missing_cmd_hint(cmd[0]))


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
    p.add_argument(
        "--no-vsix",
        action="store_true",
        help="Do not build VS Code extension VSIX into dist/payload (dev mode).",
    )
    p.add_argument(
        "--mods-from",
        default="",
        help=(
            "Optional local BetterCode repo path. If set, copies built mod jars into "
            "dist/payload/mods for offline/dev installer."
        ),
    )
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    repo = Path(__file__).resolve().parents[1]
    payload = repo / "dist" / "payload"
    app_dir = payload / "app"
    assets_dir = payload / "assets"
    seed_out_dir = payload / "seed_out"
    vsix_path = payload / "mldsl-helper.vsix"
    mods_dir = payload / "mods"

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

    # 5) Build VS Code extension VSIX (bundled into installer by default).
    if not args.no_vsix:
        ext_dir = repo / "tools" / "mldsl-vscode"
        if not ext_dir.exists():
            raise SystemExit(f"VS Code extension folder not found: {ext_dir}")
        run(["npm", "ci"], cwd=ext_dir)
        run(
            [
                "npx",
                "--yes",
                "@vscode/vsce",
                "package",
                "--no-dependencies",
                "-o",
                str(vsix_path),
            ],
            cwd=ext_dir,
        )
        if not vsix_path.exists():
            raise SystemExit(f"VSIX output not found: {vsix_path}")

    # 6) Optional local BetterCode jars for dev/offline installer.
    if args.mods_from:
        mods_src = Path(args.mods_from).resolve()
        if not mods_src.exists():
            raise SystemExit(f"--mods-from path not found: {mods_src}")
        candidates = [
            mods_src / "build" / "libs" / "bettercode-1.0.9.jar",
            mods_src / "modern" / "fabric120" / "build" / "libs" / "bettercode-fabric120-0.1.0-fabric120.jar",
            mods_src / "modern" / "fabric121" / "build" / "libs" / "bettercode-fabric121-0.1.0-fabric121.jar",
        ]
        found = [p for p in candidates if p.exists()]
        if not found:
            raise SystemExit(
                "No built BetterCode jars found under --mods-from. "
                "Build mod first (e.g. python tools/build_matrix.py all --task build)."
            )
        if mods_dir.exists():
            shutil.rmtree(mods_dir)
        mods_dir.mkdir(parents=True, exist_ok=True)
        for jar in found:
            shutil.copy2(jar, mods_dir / jar.name)

    print("")
    print("OK: prepared payload at:", payload)
    print("- app:", app_dir)
    print("- assets:", assets_dir)
    print("- seed_out:", seed_out_dir)
    if args.mods_from:
        print("- mods:", mods_dir)
    if not args.no_vsix:
        print("- vsix:", vsix_path)
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
