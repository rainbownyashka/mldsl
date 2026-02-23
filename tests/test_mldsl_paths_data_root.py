from pathlib import Path

import mldsl_paths


def test_data_root_override_wins(monkeypatch, tmp_path):
    override = tmp_path / "override_data"
    monkeypatch.setenv("MLDSL_DATA_DIR", str(override))
    monkeypatch.setattr(mldsl_paths, "_portable_enabled", lambda: False)
    monkeypatch.setattr(mldsl_paths, "_is_dev_checkout", lambda: False)
    assert mldsl_paths.data_root() == override.resolve()


def test_data_root_portable_wins_over_dev(monkeypatch, tmp_path):
    monkeypatch.delenv("MLDSL_DATA_DIR", raising=False)
    monkeypatch.setattr(mldsl_paths, "_portable_enabled", lambda: True)
    monkeypatch.setattr(mldsl_paths, "_executable_dir", lambda: tmp_path / "bin")
    monkeypatch.setattr(mldsl_paths, "_is_dev_checkout", lambda: True)
    assert mldsl_paths.data_root() == (tmp_path / "bin" / "MLDSL").resolve()


def test_data_root_dev_checkout_defaults_to_repo(monkeypatch, tmp_path):
    monkeypatch.delenv("MLDSL_DATA_DIR", raising=False)
    monkeypatch.setattr(mldsl_paths, "_portable_enabled", lambda: False)
    monkeypatch.setattr(mldsl_paths, "_is_dev_checkout", lambda: True)
    monkeypatch.setattr(mldsl_paths, "repo_root", lambda: tmp_path / "repo")
    assert mldsl_paths.data_root() == (tmp_path / "repo").resolve()


def test_data_root_prod_defaults_to_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("MLDSL_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localapp"))
    monkeypatch.setattr(mldsl_paths, "_portable_enabled", lambda: False)
    monkeypatch.setattr(mldsl_paths, "_is_dev_checkout", lambda: False)
    assert mldsl_paths.data_root() == (tmp_path / "localapp" / "MLDSL").resolve()

