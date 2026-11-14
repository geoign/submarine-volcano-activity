"""Tests of the build helpers and of the built tables.

    python -m pytest tests

The table tests read db/ as it is committed; they do not need the monitoring system.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_db  # noqa: E402
import check_db  # noqa: E402
import notes  # noqa: E402
from vocab import CLASSES  # noqa: E402


def test_num_formats_cells():
    assert build_db.num(None) == ""
    assert build_db.num("") == ""
    assert build_db.num(float("nan")) == ""
    assert build_db.num(0) == "0"
    assert build_db.num(1.5) == "1.5"
    assert build_db.num(17.7441) == "17.744"
    assert build_db.num(-0.0001) == "0"
    assert build_db.num(352.0, 0) == "352"


def test_site_of_strips_the_landsat_twin():
    assert build_db.site_of("GVP243070-A-LS") == "GVP243070-A"
    assert build_db.site_of("GVP243070-A") == "GVP243070-A"
    assert build_db.site_of("IR-Omuro_Hole-A-LS") == "IR-Omuro_Hole-A"


def test_note_key_is_shared_by_both_tools():
    text = "  区域の中心に緑の変色水。 "
    assert build_db.note_key(text) == notes.key(text)
    assert len(build_db.note_key(text)) == 12


def test_md_table_reads_the_named_table(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("intro\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n| Day | UTC |\n|---|---|\n| 2016-02-02 | 07:32 |\n| 2016-03-12 | 07:27 |\n\ntail\n",
                  encoding="utf-8")
    rows = build_db.md_table(md, "Day")
    assert rows == [{"Day": "2016-02-02", "UTC": "07:32"}, {"Day": "2016-03-12", "UTC": "07:27"}]


def test_classify_applies_rule_owner_and_override():
    volcanoes = {"V1": {"_usual": True}, "V2": {"_usual": False}}

    def ep(eid, vid, cls, owner="", explicit=False):
        return dict(episode_id=eid, volcano_id=vid, cls=cls, basis="ai_review", cause="", owner_ja=owner,
                    prior_reports="", known_ref="", _explicit=explicit)

    eps = [ep("a", "V1", "possible"), ep("b", "V1", "possible", explicit=True), ep("c", "V2", "likely"),
           ep("d", "V2", "likely", owner="2026-11-14: 異常なし (自然色の図を見ての判定)"),
           ep("e", "V2", "possible", owner="2026-11-14: 帯は大気中の現象"), ep("f", "V2", "undetermined")]
    cur = {"overrides": {"f": {"episode_id": "f", "class": "likely", "basis": "owner", "prior_reports": "read"}}}
    build_db.classify(eps, volcanoes, cur)
    got = {e["episode_id"]: (e["cls"], e["basis"]) for e in eps}
    assert got["a"] == ("recurrent", "rule")
    assert got["b"] == ("possible", "ai_review")
    assert got["c"] == ("likely", "ai_review")
    assert got["d"] == ("nonvolcanic", "owner")
    assert got["e"] == ("airborne", "owner")
    assert got["f"] == ("likely", "owner")
    assert eps[5]["prior_reports"] == "read"
    assert eps[3]["cause"] == "other"


def test_built_tables_are_consistent():
    check_db.errors.clear()
    check_db.check_tables()
    assert check_db.errors == []


def test_nothing_private_is_about_to_be_committed():
    check_db.errors.clear()
    check_db.check_leaks()
    assert check_db.errors == []


def test_index_matches_the_episode_table():
    index = json.loads((ROOT / "db" / "index.json").read_text(encoding="utf-8"))
    with open(ROOT / "db" / "episodes.csv", encoding="utf-8", newline="") as f:
        episodes = [e for e in csv.DictReader(f) if e["class"] != "nonvolcanic"]
    assert sum(len(v["episodes"]) for v in index["volcanoes"]) == len(episodes)
    assert index["classes"] == CLASSES
    for v in index["volcanoes"]:
        assert -90 <= v["lat"] <= 90 and -180 <= v["lon"] <= 180
