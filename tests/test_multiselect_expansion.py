import pytest

import mldsl_compile
from test_compile_select_and_sugar import _api_base


def _api_multiselect():
    api = _api_base()
    misc = api.setdefault("misc", {})
    misc.update(
        {
            "vse_igroki": {
                "aliases": ["allplayers", "все_игроки"],
                "sign1": "Выбрать объект",
                "sign2": "Все игроки",
                "menu": "Все игроки",
                "params": [],
                "enums": [],
            },
            "vse_moby": {
                "aliases": ["allmobs", "все_мобы"],
                "sign1": "Выбрать объект",
                "sign2": "Все мобы",
                "menu": "Все мобы",
                "params": [],
                "enums": [],
            },
            "vse_suschnosti": {
                "aliases": ["allentities", "все_сущности"],
                "sign1": "Выбрать объект",
                "sign2": "Все сущности",
                "menu": "Все сущности",
                "params": [],
                "enums": [],
            },
            "ifplayer_number": {
                "aliases": ["сравнить_число_легко", "сравнить_число_облегчённо"],
                "sign1": "Выбрать объект",
                "sign2": "Игрок по условию",
                "menu": "Сравнить числа (Облегчённая версия)",
                "params": [
                    {"name": "num", "slot": 10, "mode": "NUMBER"},
                    {"name": "num2", "slot": 16, "mode": "NUMBER"},
                ],
                "enums": [
                    {"name": "тип_проверки", "slot": 28, "options": {"≥ (Больше или равно)": 0}},
                ],
            },
            "ifmob_number": {
                "aliases": ["сравнить_число_легко", "сравнить_число_облегчённо"],
                "sign1": "Выбрать объект",
                "sign2": "Моб по условию",
                "menu": "Сравнить числа (Облегчённая версия)",
                "params": [
                    {"name": "num", "slot": 10, "mode": "NUMBER"},
                    {"name": "num2", "slot": 16, "mode": "NUMBER"},
                ],
                "enums": [
                    {"name": "тип_проверки", "slot": 28, "options": {"≥ (Больше или равно)": 0}},
                ],
            },
        }
    )
    return api


def _compile(tmp_path, monkeypatch, lines, api=None):
    path = tmp_path / "case_multiselect.mldsl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: (api or _api_multiselect()))
    return mldsl_compile.compile_entries(path)


def test_multiselect_expands_basic_ifplayer_block(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'event("Вход") {',
            "    multiselect ifplayer %selected%sel 1",
            '        select.ifplayer.держит(item=item("minecraft:stick"))+',
            "        select.ifplayer.переменная_существует(var=%selected%apiversion)-2",
            "}",
        ],
    )
    names = [e["name"] for e in entries]
    assert "Все игроки||Все игроки" in names
    assert "Держит предмет||Игрок по условию" in names
    assert "Переменная существует||Игрок по условию" in names
    assert "+||+" in names
    assert "-||-" in names
    assert "Сравнить числа (Облегчённая версия)||Игрок по условию" in names


def test_multiselect_supports_all_weight_ops_and_shortcuts(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'event("Вход") {',
            "    multiselect ifmob %selected%score 2",
            "        select.ifmob.переменная_существует(var=%selected%v)+",
            "        select.ifmob.переменная_существует(var=%selected%v)-3",
            "        select.ifmob.переменная_существует(var=%selected%v)*2",
            "        select.ifmob.переменная_существует(var=%selected%v)/=%selected%specvar",
            "}",
        ],
    )
    names = [e["name"] for e in entries]
    assert "+||+" in names
    assert "-||-" in names
    assert "*||*" in names
    assert "/||/" in names
    assert "Сравнить числа (Облегчённая версия)||Моб по условию" in names


def test_multiselect_scope_mismatch_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="scope mismatch"):
        _compile(
            tmp_path,
            monkeypatch,
            [
                'event("Вход") {',
                "    multiselect ifmob %selected%score 1",
                "        select.ifplayer.переменная_существует(var=x)+",
                "}",
            ],
        )
