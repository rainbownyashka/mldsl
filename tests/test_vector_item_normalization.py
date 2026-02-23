import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mldsl_compile  # noqa: E402


def _api_vector():
    return {
        "select": {
            "vybrat_igroka_po_umolchaniyu": {
                "aliases": ["vybrat_igroka_po_umolchaniyu"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по умолчанию",
                "menu": "Игрок по умолчанию",
                "params": [],
                "enums": [],
            },
            "vybrat_suschnost_po_umolchaniyu": {
                "aliases": ["vybrat_suschnost_po_umolchaniyu"],
                "sign1": "Выбрать обьект",
                "sign2": "Сущность по умолчанию",
                "menu": "Сущность по умолчанию",
                "params": [],
                "enums": [],
            },
        },
        "event": {
            "soobshchenie_chata": {
                "aliases": ["Событие чата"],
                "sign1": "Событие игрока",
                "sign2": "Событие чата",
                "menu": "Событие чата",
                "params": [],
                "enums": [],
            }
        },
        "var": {
            "unnamed_42": {
                "aliases": ["скалярное_произведение_векторов"],
                "sign1": "Присв. переменную",
                "sign2": "Скаляр. произв. векторо",
                "menu": "Скалярное произведение двух векторов",
                "params": [
                    {"name": "var", "slot": 10, "mode": "VARIABLE"},
                    {"name": "arg", "slot": 13, "mode": "VECTOR"},
                    {"name": "arg2", "slot": 16, "mode": "VECTOR"},
                ],
                "enums": [],
            }
        },
    }


def _api_location():
    return {
        "select": {
            "vybrat_igroka_po_umolchaniyu": {
                "aliases": ["vybrat_igroka_po_umolchaniyu"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по умолчанию",
                "menu": "Игрок по умолчанию",
                "params": [],
                "enums": [],
            },
            "vybrat_suschnost_po_umolchaniyu": {
                "aliases": ["vybrat_suschnost_po_umolchaniyu"],
                "sign1": "Выбрать обьект",
                "sign2": "Сущность по умолчанию",
                "menu": "Сущность по умолчанию",
                "params": [],
                "enums": [],
            },
        },
        "event": {
            "soobshchenie_chata": {
                "aliases": ["Событие чата"],
                "sign1": "Событие игрока",
                "sign2": "Событие чата",
                "menu": "Событие чата",
                "params": [],
                "enums": [],
            }
        },
        "var": {
            "set_loc_vals": {
                "aliases": ["установить_значения_в_местоположении"],
                "sign1": "Присв. переменную",
                "sign2": "Уст знач в мест",
                "menu": "Установить значения в местоположении",
                "params": [
                    {"name": "var", "slot": 10, "mode": "VARIABLE"},
                    {"name": "loc", "slot": 12, "mode": "LOCATION"},
                ],
                "enums": [],
            }
        },
    }


def test_vector_item_type_kw_normalized(tmp_path, monkeypatch):
    src = tmp_path / "a.mldsl"
    src.write_text(
        'event("Событие чата") {\n'
        '  var.скалярное_произведение_векторов('
        'var=test, '
        'arg=item(type=prismarine_shard, name="1 2 3"), '
        'arg2=item(type=prismarine_shard, name="4 5 6")'
        ")\n"
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mldsl_compile, "load_api", lambda: _api_vector())
    entries = mldsl_compile.compile_entries(src)
    action = next(e for e in entries if e.get("block") == "iron_block")
    args = str(action.get("args") or "")
    assert "slot(13)=item(prismarine_shard, name=\"1 2 3\")" in args
    assert "slot(16)=item(prismarine_shard, name=\"4 5 6\")" in args
    assert "type=prismarine_shard" not in args


def test_vector_named_args_aliases_supported(tmp_path, monkeypatch):
    src = tmp_path / "a.mldsl"
    src.write_text(
        'event("Событие чата") {\n'
        '  var.скалярное_произведение_векторов('
        'var=test, '
        'vector=item(type=prismarine_shard, name="1 2 3"), '
        'vector2=item(type=prismarine_shard, name="4 5 6")'
        ")\n"
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mldsl_compile, "load_api", lambda: _api_vector())
    entries = mldsl_compile.compile_entries(src)
    action = next(e for e in entries if e.get("block") == "iron_block")
    args = str(action.get("args") or "")
    assert "slot(13)=item(prismarine_shard, name=\"1 2 3\")" in args
    assert "slot(16)=item(prismarine_shard, name=\"4 5 6\")" in args


def test_location_loc_normalized_to_paper_item(tmp_path, monkeypatch):
    src = tmp_path / "a.mldsl"
    src.write_text(
        'event("Событие чата") {\n'
        '  var.установить_значения_в_местоположении(var=test, loc=loc("1 2 3 4 5"))\n'
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mldsl_compile, "load_api", lambda: _api_location())
    entries = mldsl_compile.compile_entries(src)
    action = next(e for e in entries if e.get("block") == "iron_block")
    args = str(action.get("args") or "")
    assert 'slot(12)=item(minecraft:paper, name="1 2 3 4 5")' in args
    assert "slot(12)=loc(" not in args


def test_location_bare_value_normalized_to_paper_item(tmp_path, monkeypatch):
    src = tmp_path / "a.mldsl"
    src.write_text(
        'event("Событие чата") {\n'
        '  var.установить_значения_в_местоположении(var=test, loc="1 2 3 4 5")\n'
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mldsl_compile, "load_api", lambda: _api_location())
    entries = mldsl_compile.compile_entries(src)
    action = next(e for e in entries if e.get("block") == "iron_block")
    args = str(action.get("args") or "")
    assert 'slot(12)=item(minecraft:paper, name="1 2 3 4 5")' in args
