import pytest

import mldsl_compile
from test_compile_select_and_sugar import _api_base


def _compile(tmp_path, monkeypatch, lines, api=None):
    path = tmp_path / "case_call_parse.mldsl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: (api or _api_base()))
    return mldsl_compile.compile_entries(path)


def test_multiline_module_call_is_compiled_as_single_action(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'event("Вход") {',
            "    player.msg(",
            '        text="Привет"',
            "    )",
            "}",
        ],
    )
    assert len(entries) == 2
    assert entries[1]["name"] == "Сообщение||Сообщение"
    assert entries[1]["args"] == 'slot(9)=text("Привет")'


def test_empty_named_arg_fails_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="empty value for argument"):
        _compile(
            tmp_path,
            monkeypatch,
            [
                'event("Вход") {',
                "    if_value.переменная_существует(var=)",
                "}",
            ],
        )

