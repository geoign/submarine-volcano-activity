"""A review of the hindcast counts for the alert days it was given on; '>' in the catalogue is continuing."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_db  # noqa: E402

EP_COLS = ["episode", "zone_id", "start", "end", "n_alert", "n_usable", "n_l3", "reasons", "max_dw_km2",
           "max_fl_km2", "max_nl_km2", "colour", "median_dist_km", "sensors", "peak_obs", "known",
           "prior_episode", "obs_ids"]


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def _ep(eid: str, days: list[str], known: str = "", prior: str = "") -> dict:
    zone = eid.rsplit("_", 1)[0]
    return dict(episode=eid, zone_id=zone, start=days[0], end=days[-1], n_alert=len(days), n_usable=len(days),
                n_l3=0, reasons="dw", known=known, prior_episode=prior, peak_obs=f"{zone}_{days[0]}T0100_S2A",
                obs_ids=" ".join(f"{zone}_{d}T0100_S2A" for d in days))


def test_a_review_counts_for_the_days_it_was_given_on(tmp_path, monkeypatch):
    mon, web = tmp_path / "mon", tmp_path / "web"
    eps = [
        _ep("Z-A_20200101", ["20200101", "20200105"]),                       # as triaged
        _ep("Z-A_20200301", ["20200310"]),                                    # same id, other passes
        _ep("Z-A_20200501", ["20200501", "20200520"]),                        # grew
        _ep("Z-A_20200701", ["20200701"], prior="Y-A_20200620"),              # carried, the triage names X
        _ep("Z-A_20200901", ["20200901"], known="GVP Confirmed Eruption 2020-08-01..2020-09-30"),
    ]
    _write(mon / "data/retro2/review/episodes.csv", EP_COLS, eps)
    tri_cols = ["episode", "call", "cause", "interest", "note", "source", "prior_episode"]
    _write(mon / build_db.HINDCAST_REPORT / "triage.csv", tri_cols, [
        dict(episode="Z-A_20200101", call="dismiss", cause="cloud", note="a", source="this run"),
        dict(episode="Z-A_20200301", call="dismiss", cause="cloud", note="b", source="this run"),
        dict(episode="Z-A_20200501", call="look", interest="3", note="c", source="this run"),
        dict(episode="Z-A_20200701", call="dismiss", cause="glint", note="d", source="earlier run",
             prior_episode="X-A_20200701"),
        dict(episode="Z-A_20200901", call="look", interest="3", note="e", source="this run"),
    ])
    _write(mon / build_db.HINDCAST_REPORT / "look.csv", ["episode", "owner_verdict"], [])
    _write(mon / "data/retro/review/episodes.csv", ["episode", "obs_ids"], [
        # The triage's earlier episode X shares no day with Z-A_20200701; the one the rebuilt list
        # names (Y) does: the verdict was given on X's passes.
        dict(episode="X-A_20200701", obs_ids="X-A_20200620T0100_S2A"),
        dict(episode="Y-A_20200620", obs_ids="Y-A_20200701T0100_S2A"),
    ])
    _write(web / "curation/hindcast2_triaged_days.csv", ["episode", "alert_days"], [
        dict(episode="Z-A_20200101", alert_days="20200101;20200105"),
        dict(episode="Z-A_20200301", alert_days="20200301"),
        dict(episode="Z-A_20200501", alert_days="20200501"),
        dict(episode="Z-A_20200901", alert_days="20200901"),
    ])
    monkeypatch.setattr(build_db, "ROOT", web)
    rows = {r["episode_id"]: r for r in build_db.hindcast_episodes(mon, {"Z-A": "Z"})}
    assert (rows["Z-A_20200101"]["cls"], rows["Z-A_20200101"]["basis"]) == ("nonvolcanic", "ai_review")
    assert (rows["Z-A_20200301"]["cls"], rows["Z-A_20200301"]["note_ja"]) == ("unreviewed", "")
    assert (rows["Z-A_20200501"]["cls"], rows["Z-A_20200501"]["basis"]) == ("likely", "ai_review_partial")
    assert rows["Z-A_20200701"]["cls"] == "unreviewed"
    # A catalogue match decides the class; the review's interest and note stay.
    known = rows["Z-A_20200901"]
    assert (known["cls"], known["basis"], known["interest"], known["note_ja"]) == ("known", "catalogue", "3", "e")


def test_a_continuing_eruption_is_shown_as_continuing():
    eps = [dict(volcano_id="V", known_ref="GVP Uncertain Eruption 2020-03-16..ongoing")]
    periods = [dict(volcano_id="V", source="GVP", kind="Uncertain Eruption", start="2020-03-16",
                    end="2024-04-24", continuing="yes")]
    build_db.exact_known_refs(eps, periods)
    assert eps[0]["known_ref"] == "GVP Uncertain Eruption 2020-03-16..continuing"
