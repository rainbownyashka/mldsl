import pytest

import mldsl_compile
from test_compile_select_and_sugar import _api_base


def _compile(tmp_path, monkeypatch, lines, api=None):
    path = tmp_path / "case_not_negated.mldsl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: (api or _api_base()))
    return mldsl_compile.compile_entries(path)


def test_not_if_player_action_sets_negated_flag(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "NOT if_value.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Переменная существует"
    assert entries[1].get("negated") is True


def test_not_select_ifplayer_action_sets_negated_flag(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "не select.ifplayer.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Игрок по условию"
    assert entries[1].get("negated") is True


def test_without_not_flag_is_absent(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "if_value.переменная_существует(var=x)", "}"],
    )
    assert "negated" not in entries[1]


def test_not_on_non_conditional_action_fails_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="NOT недопустим для неусловного действия"):
        _compile(
            tmp_path,
            monkeypatch,
            ['event("Вход") {', "NOT player.msg(text=\"x\")", "}"],
        )
