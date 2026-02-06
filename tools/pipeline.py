from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
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
            "Node.js/npm not found in PATH. Install Node.js or use --skip-vsix. "
            "In GitHub Actions use actions/setup-node."
        )
    return f"required command not found: {name}"


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    if not cmd:
        raise SystemExit("internal error: empty command")
    resolved = [*cmd]
    resolved[0] = _resolve_executable(resolved[0])
    where = f" (cwd={cwd})" if cwd else ""
    print(f"+{' '}{' '.join(resolved)}{where}")
    try:
        subprocess.check_call(resolved, cwd=str(cwd) if cwd else None)
    except FileNotFoundError:
        raise SystemExit(_missing_cmd_hint(cmd[0]))


def py_compile_scripts(repo: Path) -> None:
    scripts = [
        repo / "mldsl_cli.py",
        repo / "mldsl_compile.py",
        repo / "packaging" / "prepare_installer_payload.py",
        repo / "tools" / "build_all.py",
        repo / "tools" / "exportcode_to_mldsl.py",
        repo / "tools" / "_premium" / "ai_coder.py",
    ]
    for p in scripts:
        if not p.exists():
            raise SystemExit(f"missing required script: {p}")
    run([sys.executable, "-m", "py_compile", *[str(p) for p in scripts]])


def build_out(repo: Path) -> None:
    run([sys.executable, str(repo / "mldsl_cli.py"), "build-all"])


def smoke_candidates(repo: Path) -> list[Path]:
    candidates = [
        repo / "gmstick.mldsl",
        repo / "test2.mldsl",
        repo / "test.mldsl",
    ]
    return [p for p in candidates if p.exists()]


def smoke_compile(repo: Path, *, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = smoke_candidates(repo)
    if not candidates:
        raise SystemExit("no smoke .mldsl found (expected gmstick.mldsl/test2.mldsl/test.mldsl)")

    errors: list[str] = []
    for src in candidates:
        plan = out_dir / f"smoke.{src.stem}.plan.json"
        try:
            run([sys.executable, str(repo / "mldsl_cli.py"), "compile", str(src), "--plan", str(plan)])
        except subprocess.CalledProcessError as e:
            errors.append(f"{src.name}: compile failed (exit={e.returncode})")
            continue
        if not plan.exists():
            errors.append(f"{src.name}: plan not created")
            continue
        data = json.loads(plan.read_text(encoding="utf-8"))
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            errors.append(f"{src.name}: invalid plan format")
            continue
        print(f"[ok] smoke compile: {src.name} -> entries={len(entries)}")
        return

    raise SystemExit("smoke compile failed for all candidates:\n- " + "\n- ".join(errors))


def build_vsix(repo: Path, *, out_dir: Path) -> Path:
    ext_dir = repo / "tools" / "mldsl-vscode"
    if not ext_dir.exists():
        raise SystemExit(f"extension dir not found: {ext_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    vsix = out_dir / "mldsl-helper.vsix"
    run(["npm", "ci"], cwd=ext_dir)
    run(
        [
            "npx",
            "--yes",
            "@vscode/vsce",
            "package",
            "--no-dependencies",
            "-o",
            str(vsix),
        ],
        cwd=ext_dir,
    )
    if not vsix.exists():
        raise SystemExit(f"vsix was not created: {vsix}")
    print(f"[ok] vsix: {vsix}")
    return vsix


def has_iscc() -> bool:
    if shutil.which("iscc"):
        return True
    fallback = Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe"
    return fallback.exists()


def resolve_iscc() -> str:
    from_path = shutil.which("iscc")
    if from_path:
        return from_path
    fallback = Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe"
    if fallback.exists():
        return str(fallback)
    return "iscc"


def build_release(repo: Path, *, app_version: str, allow_missing_iscc: bool) -> None:
    run([sys.executable, str(repo / "packaging" / "prepare_installer_payload.py"), "--use-seed"])

    if not has_iscc():
        msg = "Inno Setup compiler `iscc` not found in PATH."
        if allow_missing_iscc:
            print(f"[warn] {msg} Skipping installer step (--allow-missing-iscc).")
            return
        raise SystemExit(msg)

    run(
        [
            resolve_iscc(),
            str(repo / "installer" / "MLDSL.iss"),
            f"/DAppVersion={app_version}",
        ]
    )
    print("[ok] installer built")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MLDSL one-command pipeline")
    p.add_argument(
        "mode",
        choices=["fast", "dev", "release", "all"],
        help="fast=validate+build out+smoke, dev=fast+vsix, release=dev+payload+installer",
    )
    p.add_argument(
        "--app-version",
        default="0.0.0-local",
        help="Installer AppVersion for release mode",
    )
    p.add_argument(
        "--allow-missing-iscc",
        action="store_true",
        help="Do not fail release mode if Inno Setup is missing",
    )
    p.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip smoke compile step",
    )
    p.add_argument(
        "--skip-vsix",
        action="store_true",
        help="Skip VSIX build (useful on machines without Node.js)",
    )
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    repo = Path(__file__).resolve().parents[1]
    t0 = time.time()
    out_dir = repo / "dist" / "pipeline"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[pipeline] mode={args.mode}")

    py_compile_scripts(repo)
    build_out(repo)
    if not args.skip_smoke:
        smoke_compile(repo, out_dir=out_dir)

    if args.mode in {"dev", "release", "all"} and not args.skip_vsix:
        build_vsix(repo, out_dir=out_dir)

    if args.mode in {"release", "all"}:
        build_release(
            repo,
            app_version=args.app_version,
            allow_missing_iscc=args.allow_missing_iscc,
        )

    dt = time.time() - t0
    print(f"[pipeline] done in {dt:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
