import pytest

import mldsl_compile
from test_compile_select_and_sugar import _api_base


def _compile(tmp_path, monkeypatch, lines, api=None):
    path = tmp_path / "case_vfunc.mldsl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: (api or _api_base()))
    return mldsl_compile.compile_entries(path)


def test_vfunc_expands_to_same_entries_as_manual_block(tmp_path, monkeypatch):
    manual = [
        'event("Вход") {',
        "select.if_player.переменная_существует(var=%selected%apiversion)",
        "player.msg(text=universeV1)",
        "}",
    ]
    via_vfunc = [
        'vfunc basicselectvar(varname, mobid="universeV1")',
        "    select.if_player.переменная_существует(var=varname)",
        "    player.msg(text=mobid)",
        "",
        'event("Вход") {',
        '    basicselectvar(%selected%apiversion, "universeV1")',
        "}",
    ]
    assert _compile(tmp_path, monkeypatch, via_vfunc) == _compile(tmp_path, monkeypatch, manual)


def test_vfunc_uses_default_arg_when_missing(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'vfunc basicselectvar(varname, mobid="universeV1")',
            "    player.msg(text=mobid)",
            'event("Вход") {',
            "    basicselectvar(x)",
            "}",
        ],
    )
    assert entries[1]["args"] == 'slot(9)=text("universeV1")'


def test_vfunc_named_arg_override(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'vfunc basicselectvar(varname, mobid="universeV1")',
            "    player.msg(text=mobid)",
            'event("Вход") {',
            '    basicselectvar(x, mobid="x")',
            "}",
        ],
    )
    assert entries[1]["args"] == 'slot(9)=text("x")'


def test_vfunc_keeps_string_literals_untouched(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            "vfunc keep(varname)",
            '    player.msg(text="varname")',
            'event("Вход") {',
            "    keep(abc)",
            "}",
        ],
    )
    assert entries[1]["args"] == 'slot(9)=text("varname")'


def test_vfunc_unknown_arg_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="unknown argument"):
        _compile(
            tmp_path,
            monkeypatch,
            [
                "vfunc keep(varname)",
                "    player.msg(text=varname)",
                'event("Вход") {',
                "    keep(x, unknown=y)",
                "}",
            ],
        )


def test_vfunc_missing_required_arg_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="missing required argument"):
        _compile(
            tmp_path,
            monkeypatch,
            [
                "vfunc pair(a, b)",
                "    player.msg(text=a)",
                'event("Вход") {',
                "    pair(x)",
                "}",
            ],
        )


def test_vfunc_recursion_cycle_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="recursion cycle"):
        _compile(
            tmp_path,
            monkeypatch,
            [
                "vfunc loopme()",
                "    loopme()",
                'event("Вход") {',
                "    loopme()",
                "}",
            ],
        )


def test_vfunc_name_conflict_with_func_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="both func and vfunc"):
        _compile(
            tmp_path,
            monkeypatch,
            [
                "vfunc dup(x)",
                "    player.msg(text=x)",
                "func dup(x) {",
                "    player.msg(text=x)",
                "}",
                'event("Вход") {',
                "    dup(x)",
                "}",
            ],
        )


def test_vfunc_indented_body_preserved_for_nested_block(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            "vfunc wrapped(v)",
            "    if if_value.переменная_существует(var=v) {",
            '        player.msg(text="ok")',
            "    }",
            'event("Вход") {',
            "    wrapped(x)",
            "}",
        ],
    )
    assert any(e.get("block") == "skip" for e in entries)
