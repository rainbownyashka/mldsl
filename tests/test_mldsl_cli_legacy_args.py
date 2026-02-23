from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mldsl_cli


def test_legacy_single_input_is_rewritten_to_compile():
    got = mldsl_cli._normalize_legacy_cli_argv(["script.mldsl"])
    assert got == ["compile", "script.mldsl"]


def test_legacy_plan_before_input_is_rewritten_to_compile():
    got = mldsl_cli._normalize_legacy_cli_argv(["--plan", "C:\\tmp\\plan.json", "script.mldsl"])
    assert got == ["compile", "script.mldsl", "--plan", "C:\\tmp\\plan.json"]


def test_modern_subcommand_is_kept():
    got = mldsl_cli._normalize_legacy_cli_argv(["compile", "script.mldsl", "--plan", "plan.json"])
    assert got == ["compile", "script.mldsl", "--plan", "plan.json"]
