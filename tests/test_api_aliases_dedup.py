import json
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load_build_api_from_catalog():
    mod_path = TOOLS / "build_api_aliases.py"
    had_tools = str(TOOLS) in sys.path
    if not had_tools:
        sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("tools_build_api_aliases_local", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module spec: {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod.build_api_from_catalog
    finally:
        if not had_tools and str(TOOLS) in sys.path:
            sys.path.remove(str(TOOLS))


def _load_fixture():
    p = ROOT / "tests" / "fixtures" / "actions_catalog_var_exists.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _params_for(api, module, key):
    spec = api[module][key]
    return [(p.get("name"), p.get("mode"), p.get("slot")) for p in spec.get("params", [])], spec


def test_var_exists_dedup_for_if_value_and_select_domains():
    build_api_from_catalog = _load_build_api_from_catalog()
    api = build_api_from_catalog(_load_fixture(), {})

    params_if_value, spec_if_value = _params_for(api, "if_value", "peremennaya_suschestvuet")
    assert params_if_value == [("var", "VARIABLE", 13)]
    assert (spec_if_value.get("meta") or {}).get("paramSource") == "normalized"

    params_ifplayer, spec_ifplayer = _params_for(api, "select", "ifplayer_peremennaya_suschestvuet")
    assert params_ifplayer == [("var", "VARIABLE", 13)]
    assert (spec_ifplayer.get("meta") or {}).get("paramSource") == "normalized"

    params_ifmob, spec_ifmob = _params_for(api, "select", "ifmob_peremennaya_suschestvuet")
    assert params_ifmob == [("var", "VARIABLE", 13)]
    assert (spec_ifmob.get("meta") or {}).get("paramSource") == "normalized"

    params_ifentity, spec_ifentity = _params_for(api, "select", "ifentity_peremennaya_suschestvuet")
    assert params_ifentity == [("var", "VARIABLE", 13)]
    assert (spec_ifentity.get("meta") or {}).get("paramSource") == "normalized"


def test_negative_control_distinct_variable_labels_are_kept():
    build_api_from_catalog = _load_build_api_from_catalog()
    api = build_api_from_catalog(_load_fixture(), {})
    spec = None
    for cand in api.get("if_value", {}).values():
        if (cand.get("sign1") == "Если переменная") and (cand.get("sign2") == "Значение равно"):
            spec = cand
            break
    assert spec is not None
    params = [(p.get("name"), p.get("mode"), p.get("slot")) for p in spec.get("params", [])]
    assert params == [("var", "VARIABLE", 13), ("var2", "VARIABLE", 31)]
    assert (spec.get("meta") or {}).get("paramSource") == "raw"
