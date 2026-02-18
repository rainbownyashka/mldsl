import json
import os
import shutil
import subprocess
import sys
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

def _load_tools_build_api_aliases():
    path = ROOT / "tools" / "build_api_aliases.py"
    bootstrap = str(ROOT / "tools")
    had_bootstrap = bootstrap in sys.path
    if not had_bootstrap:
        sys.path.insert(0, bootstrap)
    try:
        spec = importlib.util.spec_from_file_location("tools_build_api_aliases_contract", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        return mod
    finally:
        if not had_bootstrap and bootstrap in sys.path:
            sys.path.remove(bootstrap)


def _load_fixture():
    p = ROOT / "tests" / "fixtures" / "actions_catalog_var_exists.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _copy_seed_out(dst_out: Path) -> None:
    seed_out = ROOT / "seed" / "out"
    (dst_out / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed_out / "actions_catalog.json", dst_out / "actions_catalog.json")
    shutil.copy2(seed_out / "action_aliases.json", dst_out / "action_aliases.json")
    shutil.copy2(seed_out / "language_quickstart.md", dst_out / "language_quickstart.md")
    shutil.copy2(seed_out / "gamevalues.json", dst_out / "gamevalues.json")
    shutil.copy2(seed_out / "docs" / "README.md", dst_out / "docs" / "README.md")
    shutil.copy2(seed_out / "docs" / "ALL_FUNCTIONS.md", dst_out / "docs" / "ALL_FUNCTIONS.md")
    shutil.copy2(seed_out / "docs" / "MLDSL_GUIDE.md", dst_out / "docs" / "MLDSL_GUIDE.md")


def _touch_stamp(stamps_dir: Path, name: str) -> None:
    stamps_dir.mkdir(parents=True, exist_ok=True)
    (stamps_dir / f"{name}.stamp").touch()


def test_api_aliases_contract_has_select_and_param_source():
    mod = _load_tools_build_api_aliases()
    api = mod.build_api_from_catalog(_load_fixture(), {})
    mod.validate_api_contract(api)
    assert isinstance(api.get("select"), dict) and api["select"]
    assert any(k.startswith("ifplayer_") for k in api["select"])
    assert any(k.startswith("ifmob_") for k in api["select"])
    assert any(k.startswith("ifentity_") for k in api["select"])


def test_build_all_and_direct_builder_produce_same_api_aliases(tmp_path):
    data_root = tmp_path / "mldsl_data"
    out_dir = data_root / "out"
    _copy_seed_out(out_dir)
    _touch_stamp(out_dir / ".build_stamps", "actions_catalog")
    _touch_stamp(out_dir / ".build_stamps", "gamevalues")
    _touch_stamp(out_dir / ".build_stamps", "api_docs")

    env = os.environ.copy()
    env["MLDSL_DATA_DIR"] = str(data_root)
    py = ROOT / ".venv" / "Scripts" / "python.exe"

    # Force api_aliases regeneration through canonical CLI pipeline.
    api_path = out_dir / "api_aliases.json"
    if api_path.exists():
        api_path.unlink()
    subprocess.check_call([str(py), "mldsl_cli.py", "build-all"], cwd=str(ROOT), env=env)
    via_cli = api_path.read_text(encoding="utf-8")

    # Direct generator must produce byte-identical result in the same data root.
    subprocess.check_call([str(py), "tools/build_api_aliases.py"], cwd=str(ROOT), env=env)
    via_direct = api_path.read_text(encoding="utf-8")
    assert via_cli == via_direct
