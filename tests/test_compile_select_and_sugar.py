import pytest

import mldsl_compile


def _api_base():
    return {
        "misc": {
            "vybrat_igroka_po_umolchaniyu": {
                "aliases": ["выбрать_игрока_по_умолчанию"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по умолчанию",
                "menu": "Игрок по умолчанию",
                "params": [],
                "enums": [],
            },
            "vybrat_suschnost_po_umolchaniyu": {
                "aliases": ["выбрать_сущность_по_умолчанию"],
                "sign1": "Выбрать обьект",
                "sign2": "Сущность по умолчанию",
                "menu": "Сущность по умолчанию",
                "params": [],
                "enums": [],
            },
            "ifplayer_peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по условию",
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "ifmob_peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Выбрать обьект",
                "sign2": "Моб по условию",
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "ifentity_peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Выбрать обьект",
                "sign2": "Сущность по условию",
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "ifplayer_derzhit_predmet": {
                "aliases": ["держит_предмет"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по условию",
                "menu": "Держит предмет",
                "params": [{"name": "item", "slot": 9, "mode": "ITEM"}],
                "enums": [],
            },
        },
        "if_player": {
            "peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "derzhit_predmet": {
                "aliases": ["держит_предмет", "держит"],
                "menu": "Держит предмет",
                "params": [{"name": "item", "slot": 9, "mode": "ITEM"}],
                "enums": [],
            },
        },
        "if_value": {
            "peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Если переменная",
                "sign2": "Переменная существует",
                "params": [
                    {"name": "var", "slot": 13, "mode": "VARIABLE"},
                    {"name": "var2", "slot": 31, "mode": "VARIABLE"},
                ],
                "enums": [],
            }
        },
        "var": {
            "set_value": {
                "aliases": ["set_value"],
                "sign1": "Присв. переменную",
                "sign2": "=",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "value", "slot": 10, "mode": "ANY"},
                ],
                "enums": [],
            },
            "set_sum": {
                "aliases": ["set_sum"],
                "sign1": "Присв. переменную",
                "sign2": "+",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "values", "slot": 10, "mode": "ANY_ARRAY"},
                ],
                "enums": [],
            },
            "set_difference": {
                "aliases": ["set_difference"],
                "sign1": "Присв. переменную",
                "sign2": "-",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "value1", "slot": 10, "mode": "ANY"},
                    {"name": "value2", "slot": 11, "mode": "ANY"},
                ],
                "enums": [],
            },
            "set_product": {
                "aliases": ["set_product"],
                "sign1": "Присв. переменную",
                "sign2": "*",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "values", "slot": 10, "mode": "ANY_ARRAY"},
                ],
                "enums": [],
            },
            "set_quotient": {
                "aliases": ["set_quotient"],
                "sign1": "Присв. переменную",
                "sign2": "/",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "value1", "slot": 10, "mode": "ANY"},
                    {"name": "value2", "slot": 11, "mode": "ANY"},
                ],
                "enums": [],
            },
        },
        "player": {
            "msg": {
                "aliases": ["msg"],
                "sign1": "Действие игрока",
                "sign2": "Сообщение",
                "params": [{"name": "text", "slot": 9, "mode": "TEXT"}],
                "enums": [],
            }
        },
        "game": {},
        "if_game": {},
        "select": {},
    }


def _compile(tmp_path, monkeypatch, lines, api=None):
    path = tmp_path / "case.mldsl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: (api or _api_base()))
    return mldsl_compile.compile_entries(path)


def test_select_if_player_var_exists_success(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "select.if_player.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Игрок по условию"
    assert entries[1]["args"] == "slot(13)=var(x)"


def test_select_if_mob_var_exists_success(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "select.if_mob.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Моб по условию"
    assert entries[1]["args"] == "slot(13)=var(x)"


def test_select_if_entity_var_exists_success(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "select.if_entity.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Сущность по условию"
    assert entries[1]["args"] == "slot(13)=var(x)"


def test_select_bridge_leaf_map_derzhit(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'select.if_player.держит(item=item("minecraft:stick"))', "}"],
    )
    assert entries[1]["name"] == "Держит предмет||Игрок по условию"


def test_select_unknown_leaf_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="select: неизвестный селектор"):
        _compile(
            tmp_path,
            monkeypatch,
            ['event("Вход") {', "select.if_player.unknown_leaf(var=x)", "}"],
        )


def test_select_ambiguous_without_domain_hint_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="select: неоднозначно"):
        _compile(
            tmp_path,
            monkeypatch,
            ['event("Вход") {', "select.переменная_существует(var=x)", "}"],
        )


def test_assignment_sugars_compile(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "a += 1", "a -= 1", "a *= 2", "a /= 2", "}"],
    )
    names = [e["name"] for e in entries[1:]]
    assert "+||+" in names
    assert "-||-" in names
    assert "*||*" in names
    assert "/||/" in names


def test_assignment_non_numeric_rhs_raises(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="supports numeric expressions only"):
        _compile(
            tmp_path,
            monkeypatch,
            ['event("Вход") {', 'a += "txt"', "}"],
        )


def test_text_param_bare_identifier_wraps_to_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "player.msg(text=myVar)", "}"],
    )
    assert entries[1]["args"] == "slot(9)=var(myVar)"


def test_text_param_quoted_literal_keeps_text(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'player.msg(text="abc")', "}"],
    )
    assert entries[1]["args"] == 'slot(9)=text("abc")'


def test_if_value_var_exists_single_var_is_mirrored_to_var2(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "if_value.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["args"] == "slot(13)=var(x),slot(31)=var(x)"

