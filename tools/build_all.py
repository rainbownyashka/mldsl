import subprocess
import sys
from pathlib import Path


def run(args: list[str]) -> None:
    print("+", " ".join(args))
    subprocess.check_call(args)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    python = sys.executable

    run([python, str(repo_root / "tools" / "build_actions_catalog.py")])
    run([python, str(repo_root / "tools" / "build_api_aliases.py")])
    run([python, str(repo_root / "tools" / "build_gamevalues.py")])
    run([python, str(repo_root / "tools" / "generate_api_docs.py")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
