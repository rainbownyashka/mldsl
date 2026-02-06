from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), f"(cwd={cwd})" if cwd else "")
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def resolve_iscc() -> str | None:
    from_path = shutil.which("iscc")
    if from_path:
        return from_path
    fallback = Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe"
    if fallback.exists():
        return str(fallback)
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build MLDSL DEV installer with local BetterCode jars bundled")
    p.add_argument("--app-version", default="0.1.17-dev", help="Installer AppVersion")
    p.add_argument(
        "--mods-from",
        default=r"k:\mymod",
        help="Path to local BetterCode repo with built jars",
    )
    p.add_argument(
        "--skip-vsix",
        action="store_true",
        help="Skip VSIX packaging (faster local build)",
    )
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    repo = Path(__file__).resolve().parents[1]
    mods_from = Path(args.mods_from).resolve()
    if not mods_from.exists():
        raise SystemExit(f"--mods-from not found: {mods_from}")

    prep_cmd = [sys.executable, str(repo / "packaging" / "prepare_installer_payload.py"), "--use-seed", "--mods-from", str(mods_from)]
    if args.skip_vsix:
        prep_cmd.append("--no-vsix")
    run(prep_cmd)

    iscc = resolve_iscc()
    if not iscc:
        raise SystemExit(
            "ISCC not found. Install Inno Setup or add ISCC.exe to PATH.\n"
            "Expected fallback: %LOCALAPPDATA%\\Programs\\Inno Setup 6\\ISCC.exe"
        )

    run(
        [
            iscc,
            str(repo / "installer" / "MLDSL.iss"),
            f"/DAppVersion={args.app_version}",
            "/DDevInstaller=1",
        ]
    )
    print("[ok] dev installer built in dist/release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

