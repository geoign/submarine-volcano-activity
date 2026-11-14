"""Tests of the builder of the local review form (tools/build_review.py)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_review  # noqa: E402


def test_steady_follows_the_baseline_or_many_active_episodes():
    assert build_review.steady("persistent", 0)
    assert build_review.steady("frequent", 0)
    assert not build_review.steady("quiet", 0)
    assert not build_review.steady("quiet", 9)
    assert build_review.steady("quiet", 10)
    assert build_review.steady("quiet", 25)
    assert not build_review.steady("", 3)
    assert build_review.steady("", 10)


def test_a_withdrawn_review_stays_out_until_a_newer_one():
    from build_db import live_reviews
    rows = [dict(episode_id="A", verdict="likely", reviewed_at="2026-11-14T21:33:33+09:00"),
            dict(episode_id="B", verdict="possible", reviewed_at="2026-11-14T21:34:51+09:00")]
    assert set(live_reviews(rows, [])) == {"A", "B"}
    gone = [dict(episode_id="A", withdrawn_at="2026-11-14T23:40:00+09:00")]
    assert set(live_reviews(rows, gone)) == {"B"}
    again = rows + [dict(episode_id="A", verdict="possible", reviewed_at="2026-11-15T09:00:00+09:00")]
    assert live_reviews(again, gone)["A"]["verdict"] == "possible"
