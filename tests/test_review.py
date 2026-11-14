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
