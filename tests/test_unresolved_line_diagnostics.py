import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mldsl_compile  # noqa: E402
from tests.test_compile_select_and_sugar import _api_base  # noqa: E402


def _compile_text(tmp_path, monkeypatch, text: str):
    src = tmp_path / "case_unknown.mldsl"
    src.write_text(text, encoding="utf-8")
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: _api_base())
    return mldsl_compile.compile_entries(src)


def test_unresolved_line_warns_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MLDSL_STRICT_UNKNOWN", raising=False)
    monkeypatch.setenv("MLDSL_WARN_UNKNOWN", "1")
    entries = _compile_text(
        tmp_path,
        monkeypatch,
        'event("Событие чата") {\n'
        "  aervaeR()\n"
        "}\n",
    )
    err = capsys.readouterr().err
    assert "нераспознанная строка" in err
    assert "aervaeR()" in err
    assert entries and entries[0].get("block")


def test_unresolved_line_strict_mode_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("MLDSL_STRICT_UNKNOWN", "1")
    monkeypatch.setenv("MLDSL_WARN_UNKNOWN", "1")
    with pytest.raises(ValueError, match="нераспознанная строка"):
        _compile_text(
            tmp_path,
            monkeypatch,
            'event("Событие чата") {\n'
            "  aervaeR()\n"
            "}\n",
        )


def test_unknown_function_with_named_args_warns(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MLDSL_STRICT_UNKNOWN", raising=False)
    monkeypatch.setenv("MLDSL_WARN_UNKNOWN", "1")
    _compile_text(
        tmp_path,
        monkeypatch,
        'event("Событие чата") {\n'
        '  aervaeR(num="@#2")\n'
        "}\n",
    )
    err = capsys.readouterr().err
    assert "нераспознанная строка" in err
    assert 'aervaeR(num="@#2")' in err
