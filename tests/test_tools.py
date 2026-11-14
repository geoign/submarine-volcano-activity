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
    # whole numbers keep their zeros: a bearing of 290 is not 29
    assert build_db.num(290, 0) == "290"
    assert build_db.num(100.0, 0) == "100"
    assert build_db.num(10, 0) == "10"
    assert build_db.num(360, 0) == "360"
    assert build_db.num(100) == "100"
    assert build_db.num(10.50) == "10.5"
    assert build_db.num(0.0, 0) == "0"


def test_obs_days_reads_the_day_of_each_observation():
    ids = "GVP243070-A_20240615T2201_S2B GVP243070-A-LS_20240617T2144_L9"
    assert build_db.obs_days(ids) == {"20240615", "20240617"}
    assert build_db.obs_days("") == set()


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
    status = {e["episode_id"]: e["review_status"] for e in eps}
    assert status == {"a": "ai-reviewed", "b": "ai-reviewed", "c": "ai-reviewed", "d": "human-reviewed",
                      "e": "human-reviewed", "f": "human-reviewed"}
    assert eps[3]["reviewed_at"] == "2026-11-14"


def test_the_authors_review_is_the_last_word():
    volcanoes = {"V1": {"_usual": True}}
    eps = [dict(episode_id="a", volcano_id="V1", cls="possible", basis="ai_review", cause="", owner_ja="",
                prior_reports="", known_ref=""),
           dict(episode_id="b", volcano_id="V1", cls="likely", basis="ai_review", cause="", owner_ja="",
                prior_reports="", known_ref=""),
           dict(episode_id="c", volcano_id="V1", cls="known", basis="catalogue", cause="", owner_ja="",
                prior_reports="", known_ref="GVP Confirmed Eruption 2020-01-01..2020-02-01")]
    cur = {"overrides": {"a": {"episode_id": "a", "class": "recurrent", "basis": "lead_review"}},
           "human": {"a": {"episode_id": "a", "verdict": "likely", "cause": "", "comment": "火口からの変色水", "reviewed_at": "2026-11-20"},
                     "b": {"episode_id": "b", "verdict": "nonvolcanic", "cause": "", "comment": "", "reviewed_at": "2026-11-21"}}}
    build_db.classify(eps, volcanoes, cur)
    a, b, c = eps
    assert (a["cls"], a["basis"], a["review_status"], a["reviewed_at"]) == ("likely", "owner", "human-reviewed", "2026-11-20")
    assert a["owner_ja"] == "2026-11-20: 火口からの変色水"
    assert (b["cls"], b["cause"], b["review_status"]) == ("nonvolcanic", "other", "human-reviewed")
    assert b["_owner_en"] == "2026-11-21: reviewed from the images (not volcanic)"
    assert (c["cls"], c["review_status"], c["reviewed_at"]) == ("known", "automatic", "")


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


def test_day_span_reads_days_months_years_and_ranges():
    from datetime import date
    assert build_db.day_span("2021-08-13") == (date(2021, 8, 13).toordinal(),) * 2
    assert build_db.day_span("2024-02") == (date(2024, 2, 1).toordinal(), date(2024, 2, 29).toordinal())
    assert build_db.day_span("2013") == (date(2013, 1, 1).toordinal(), date(2013, 12, 31).toordinal())
    assert build_db.day_span("2026-07-06/2026-07-07") == (date(2026, 7, 6).toordinal(), date(2026, 7, 7).toordinal())
    assert build_db.day_span("") is None
    assert build_db.day_span("2021-13-01") is None


def _report(date, category="anomaly", zones="V-A", site="Here", phenomena="dw"):
    return dict(volcano_id="V", site_ja=site, site_en=site, zones=zones, date=date, category=category,
                phenomena=phenomena, retrieved="2026-11-14", url="https://example.org/page.htm", match="summit")


def test_coast_guard_reports_are_compared_by_zone_and_day():
    e = dict(volcano_id="V", zone_id="V-A-LS", tier="highres", start="2022-06-10", end="2022-06-17")
    rows = [_report("2022-06-01"),                                  # 9 days before, in the zone
            _report("2022-06-20", zones="V-B", site="There"),       # another zone of the volcano
            _report("2022-06-30", "none"),                          # a visit that saw nothing
            _report("2022-07-02"),                                  # 15 days after: too late
            _report("2022", "none"),                                # a year says nothing about a day
            _report("2022-06-15", "not_visible")]
    here, away, quiet = build_db.jcg_split(e, rows)
    assert [r["date"] for r in here] == ["2022-06-01"]
    assert [r["site_en"] for r in away] == ["There"]
    assert [r["date"] for r in quiet] == ["2022-06-30"]
    # a low-resolution zone holds every site of the volcano
    wide = dict(e, zone_id="W-V", tier="lowres")
    assert len(build_db.jcg_split(wide, rows)[0]) == 2


def test_prior_reports_say_what_the_coast_guard_database_has():
    eps = [dict(volcano_id="V", zone_id="V-A", tier="highres", start="2022-06-10", end="2022-06-17", prior_reports=""),
           dict(volcano_id="V", zone_id="V-A", tier="highres", start="2019-01-01", end="2019-01-01", prior_reports="GVP: read"),
           dict(volcano_id="X", zone_id="X-A", tier="highres", start="2022-06-10", end="2022-06-17", prior_reports="")]
    rows = [_report("2022-06-01", phenomena="dw+fl"), _report("2022-06-01", phenomena="dw+fl"),
            _report("2022-06-20", zones="", site="There"), _report("2022-06-01", "none", site="Here too"),
            _report("2022-06-25", "none"), _report("2022-06-25", "none", site="Here too")]
    assert build_db.jcg_prior(eps, rows) == 2
    head = ("Japan Coast Guard, database of submarine volcanoes (https://example.org/page.htm; used on 2026-11-14; "
            "digest made and edited by this database): ")
    # the same record twice is said once; two sites seen on one day are one other day
    assert eps[0]["prior_reports"] == (head + "reported on 2022-06-01 (discoloured water, floating matter at Here); "
                                       "nothing unusual on 1 other day(s); "
                                       "outside this zone, 1 record(s) of something seen at There")
    # no record near the episode: say how far the records used reach, not that nobody looked
    assert eps[1]["prior_reports"] == ("GVP: read; " + head + "no record for this zone within 14 days of the episode "
                                       "(the records of Here and Here too used here run from 2022-06-01 to 2022-06-25)")
    assert eps[2]["prior_reports"] == ""      # no page for this volcano: nothing was read, nothing is said
    lone = [dict(volcano_id="V", zone_id="V-B", tier="highres", start="2022-06-10", end="2022-06-17", prior_reports="")]
    build_db.jcg_prior(lone, rows)
    assert lone[0]["prior_reports"].endswith("the source has no table for a feature in this zone; "
                                             "outside this zone, 3 record(s) of something seen at Here and There")


def test_a_row_the_coast_guard_has_twice_is_kept_once():
    import import_jcg
    r = dict(volcano_id="V", site_ja="S", date="2023-10-04", time="12:00", text_ja="変色水を認めた。")
    assert import_jcg.unique([r, dict(r), dict(r, time="13:00")]) == [r, dict(r, time="13:00")]


def test_a_welling_up_of_discoloured_water_is_not_bubbles():
    import parse_jcg
    assert parse_jcg.categorise("東海徳場付近に、円型の濃厚な黄白色の変色水の湧出を認めた。") == ("anomaly", "dw")
    assert parse_jcg.categorise("少量の変色水若しくはガスとみられる青白色の変色域を認めた。") == ("anomaly", "dw")
    assert parse_jcg.categorise("海水面に気泡を認めた。") == ("anomaly", "bubbles")


def test_a_yearly_row_of_the_coast_guard_becomes_its_days():
    import import_jcg
    r = dict(date="2013", category="none", time="", text_ja="2013年3月25日，7月1日 変色水を認めず，特異事象なし．")
    assert [x["date"] for x in import_jcg.split_year(r)] == ["2013-03-25", "2013-07-01"]
    assert import_jcg.split_year(dict(r, category="anomaly")) == [dict(r, category="anomaly")]
    assert import_jcg.split_year(dict(r, date="2013-03-25"))[0]["date"] == "2013-03-25"
