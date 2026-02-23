import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mldsl_cli  # noqa: E402


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def test_required_tier_king_wins_over_gamer(tmp_path, monkeypatch):
    api_path = tmp_path / "api_aliases.json"
    catalog_path = tmp_path / "actions_catalog.json"
    rank_path = tmp_path / "donaterequire.txt"

    _write_json(
        api_path,
        {
            "player": {
                "message": {
                    "aliases": ["soobshchenie"],
                    "sign1": "A",
                    "sign2": "B",
                    "gui": "G1",
                },
                "damage": {
                    "aliases": ["uron"],
                    "sign1": "C",
                    "sign2": "D",
                    "gui": "G2",
                },
            }
        },
    )
    _write_json(
        catalog_path,
        [
            {"signs": ["A", "B"], "gui": "G1"},  # id 0
            {"signs": ["X", "Y"], "gui": "Gx"},  # id 1
            {"signs": ["C", "D"], "gui": "G2"},  # id 2
        ],
    )
    rank_path.write_text(
        "gamer can\n0\n\nking can\n2\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mldsl_cli, "api_aliases_path", lambda: api_path)
    monkeypatch.setattr(mldsl_cli, "actions_catalog_path", lambda: catalog_path)
    monkeypatch.setattr(mldsl_cli, "repo_root", lambda: tmp_path)

    tier, level, matched, detected = mldsl_cli._compute_required_tier_for_source(
        'player.message(text="x")\nplayer.damage(num=1)\n'
    )
    assert tier == "king"
    assert level == mldsl_cli.TIER_LEVEL["king"]
    assert matched == [0, 2]
    assert detected == ["player.damage", "player.message"]


def test_required_tier_player_when_no_matches(tmp_path, monkeypatch):
    api_path = tmp_path / "api_aliases.json"
    catalog_path = tmp_path / "actions_catalog.json"
    rank_path = tmp_path / "donaterequire.txt"

    _write_json(api_path, {"player": {}})
    _write_json(catalog_path, [])
    rank_path.write_text("gamer can\n1\n", encoding="utf-8")

    monkeypatch.setattr(mldsl_cli, "api_aliases_path", lambda: api_path)
    monkeypatch.setattr(mldsl_cli, "actions_catalog_path", lambda: catalog_path)
    monkeypatch.setattr(mldsl_cli, "repo_root", lambda: tmp_path)

    tier, level, matched, detected = mldsl_cli._compute_required_tier_for_source("player.unknown()")
    assert tier == "player"
    assert level == 0
    assert matched == []
    assert detected == []
