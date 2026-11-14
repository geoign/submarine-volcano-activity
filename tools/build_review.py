"""Build the local review form: review/index.html with the episodes to look at, most important first.

    python tools/build_review.py

The form is for the author of the database. It lists every episode that has archived images
(the quicklooks of its passes, or the review sheet of a low-resolution episode), shows them with
the passes before and after, and takes a verdict. An episode the author has judged carries the
status "human-reviewed" in the published tables.

The form is a set of static files opened from disk: tools/review_form/ is copied to review/ and
the data is written beside it as review/data.js (review/ is not committed). The verdicts are
saved by the form into curation/human_review.csv, which tools/build_db.py reads.

Importance (the order of the list) is a number made of
  - the class the episode has now: likely 100, possible 80, unreviewed 70, known 65,
    airborne 55, undetermined 50, recurrent 30, nonvolcanic 0;
  - the interest the first-pass review gave (3 points each step);
  - the alert passes (1.5 each, up to 8) and those of level L3 (2 each, up to 5);
  - the area of discoloured water (6 x log10(1 + km2), up to 15);
  - floating matter or new land (5), hot pixels (2).
When the Japan Coast Guard's database records something seen at the volcano itself, in the zone and
within 14 days of an episode that is not counted as a documented eruption or likely volcanic, the
class counts 75 at least and 20 is added: a visit that saw something beside a review that did not
is the first thing to look at. Records of a neighbouring island do not count for this.
It only orders the work; it is not published.

The form can leave out volcanoes where activity is seen almost all the time (Lateiki, Home Reef,
Fukutoku-Oka-no-Ba...), so that the author can work on the rest. Each volcano of data.js carries
its baseline class (`base`), the number of its episodes in the form (`n`), those of class known,
likely, possible or recurrent (`act`), and `steady`, see steady(): whether it is left out when the
filter is on. That only sets the default of a filter of the form; the author changes the set in
the form (kept in the browser), and none of it is published.

Keys of the form: 1 to 7 verdict, A agree with the class, Enter save and next, J/K or arrows up/down
next/previous episode, arrows left/right pass, C comment, D date of the pass into the comment
(Alt+D inside it), G grid of all passes, H enhancement of the images, and Q W E R T Y U I O P Z X V
the causes of a "nonvolcanic" verdict (in the order of vocab.CAUSES).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_db import jcg_near, jcg_split, live_reviews  # noqa: E402
from safeio import copy, write_text  # noqa: E402
from vocab import CAUSES, CLASSES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db"
OUT = ROOT / "review"
FORM = Path(__file__).resolve().parent / "review_form"
SITE = "https://geoign.github.io/submarine-volcano-activity/"
WEIGHT = {"likely": 100, "possible": 80, "unreviewed": 70, "known": 65, "airborne": 55, "undetermined": 50,
          "recurrent": 30, "nonvolcanic": 0}
CONTEXT = 2          # usable passes shown before the first and after the last alert
QUIET_INSIDE = 10    # at most this many passes without an alert from inside the episode
ACTIVE = ("known", "likely", "possible", "recurrent")   # the classes counted as activity for steady()
STEADY_ACT = 10      # this many such episodes in the form make a volcano "steady" whatever its baseline


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def f(v) -> float:
    try:
        return float(v or 0)
    except ValueError:
        return 0.0


def importance(e: dict, seen_by_jcg: bool = False) -> float:
    ph = e["phenomena"].split("+")
    score = WEIGHT[e["class"]]
    if seen_by_jcg and e["class"] not in ("known", "likely"):
        score = max(score, 75) + 20
    score += 3 * f(e["interest"]) + 1.5 * min(f(e["n_detect"]), 8) + 2 * min(f(e["n_l3"]), 5)
    score += min(6 * math.log10(1 + f(e["max_dw_km2"])), 15)
    score += 5 * ("fl" in ph or "nl" in ph) + 2 * ("th" in ph)
    return round(score, 1)


def steady(base: str, act: int) -> bool:
    """Whether the form leaves the volcano out by default when "almost always active" is filtered.

    True for a baseline class of "persistent" or "frequent", or for STEADY_ACT or more episodes of
    an active class in the form. Only the default of a filter of the form; not published.
    """
    return base in ("persistent", "frequent") or act >= STEADY_ACT


def site_of(zone: str) -> str:
    return zone[:-3] if zone.endswith("-LS") else zone


def pass_row(p: dict, role: str) -> list:
    return [p["zone_id"], p["time"], p["sat"], p["level"], p["reasons"], p["dw_km2"], p["colour"], p["dist_km"],
            p["bearing"], p["fl_km2"], p["nl_km2"], p["th_px"], p["ap_km2"], role]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    meta = json.loads((DB / "meta.json").read_text(encoding="utf-8"))
    volcanoes = {v["volcano_id"]: v for v in read(DB / "volcanoes.csv")}
    episodes = read(DB / "episodes.csv")
    withdrawn = read(ROOT / "curation" / "review_withdrawn.csv")
    reviews = live_reviews(read(ROOT / "curation" / "human_review.csv"), withdrawn)
    periods = defaultdict(list)
    for k in read(DB / "known_periods.csv"):
        periods[k["volcano_id"]].append(k)
    reports = defaultdict(list)
    for r in read(DB / "jcg_observations.csv"):
        reports[r["volcano_id"]].append(r)

    by_volcano = defaultdict(list)
    for e in episodes:
        by_volcano[e["volcano_id"]].append(e)

    out, skipped = [], 0
    for vid, eps in by_volcano.items():
        passes = [p for p in read(DB / "passes" / f"{vid}.csv") if p["img"] == "1"]
        by_site = defaultdict(list)
        for p in passes:
            by_site[site_of(p["zone_id"])].append(p)
        for e in eps:
            rows = []
            if e["tier"] == "highres":
                site = by_site.get(e["zone_id"], [])
                alerts = [i for i, p in enumerate(site) if p["episode_id"] == e["episode_id"]]
                if not alerts:
                    skipped += 1
                    continue
                first, last = alerts[0], alerts[-1]
                inside = [i for i in range(first, last + 1) if i not in set(alerts)]
                if len(inside) > QUIET_INSIDE:
                    step = len(inside) / QUIET_INSIDE
                    inside = [inside[int(k * step)] for k in range(QUIET_INSIDE)]
                keep = {i: "a" for i in alerts}
                keep.update({i: "q" for i in inside})
                keep.update({i: "b" for i in range(max(0, first - CONTEXT), first)})
                keep.update({i: "c" for i in range(last + 1, min(len(site), last + 1 + CONTEXT))})
                rows = [pass_row(site[i], keep[i]) for i in sorted(keep)]
            elif not e["image"]:
                skipped += 1          # a low-resolution episode without a review sheet has nothing to look at
                continue
            near = [[r["date"], r["category"], r["site_ja"], r["text_ja"], int(inside)]
                    for r, inside in jcg_near(e, reports.get(vid, []), 30)]
            seen = any(r["match"] == "summit" for r in jcg_split(e, reports.get(vid, []))[0])
            known = [f"{k['source']} {k['kind']} {k['start']}..{k['end'] or ''}" for k in periods.get(vid, [])
                     if (k["end"] or "9999") >= e["start"][:4] and k["start"][:4] <= e["end"][:4]]
            out.append(dict(
                id=e["episode_id"], v=vid, z=e["zone_id"], tier=e["tier"], src=e["source"], s=e["start"], e=e["end"],
                nd=e["n_detect"], ns=e["n_seen"], l3=e["n_l3"], ph=e["phenomena"], dw=e["max_dw_km2"],
                fl=e["max_fl_km2"], nl=e["max_nl_km2"], col=e["colour"], dist=e["median_dist_km"], sens=e["sensors"],
                peak=e["peak"], cls=e["class"], basis=e["basis"], cause=e["cause"], interest=e["interest"],
                known=e["known_ref"], prior=e["prior_reports"], image=e["image"], note_ja=e["note_ja"],
                note_en=e["note_en"], owner_ja=e["owner_ja"], cur_ja=e["curation_ja"],
                status=e.get("review_status", ""), imp=importance(e, seen), passes=rows, jcg=near, jh=int(seen),
                periods=known))
    out.sort(key=lambda r: (-r["imp"], r["s"]))
    n_eps, n_act = defaultdict(int), defaultdict(int)
    for r in out:
        n_eps[r["v"]] += 1
        n_act[r["v"]] += r["cls"] in ACTIVE
    data = dict(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), db_generated=meta["generated"],
        image_base=meta["image_base"], site=SITE, classes=[c for c in CLASSES if c != "unreviewed"], causes=CAUSES,
        volcanoes={k: dict(name=v["name"], name_ja=v["name_ja"], country=v["country"], gvp=v["gvp_number"],
                           base=v.get("baseline_class", ""), n=n_eps[k], act=n_act[k],
                           steady=steady(v.get("baseline_class", ""), n_act[k]))
                   for k, v in volcanoes.items()},
        episodes=out,
        # Withdrawals made outside the form: the form drops an older copy of the review that its storage holds.
        withdrawn={w["episode_id"]: w["withdrawn_at"] for w in withdrawn},
        reviews={k: dict(verdict=r["verdict"], cause=r.get("cause", ""), comment=r.get("comment", ""),
                         reviewed_at=r.get("reviewed_at", "")) for k, r in reviews.items()})
    OUT.mkdir(exist_ok=True)
    for src in FORM.iterdir():
        copy(src, OUT / src.name)
    text = "window.REVIEW_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    write_text(OUT / "data.js", text)
    by_class = defaultdict(int)
    for r in out:
        by_class[r["cls"]] += 1
    print(f"review/index.html: {len(out)} episodes with images ({skipped} without), "
          f"{len(reviews)} already reviewed, data.js {len(text) / 1e6:.1f} MB")
    print("by class:", dict(by_class))
    left = [k for k, v in data["volcanoes"].items() if v["steady"] and v["n"]]
    print(f"almost always active (left out by default when the filter is on): {len(left)} volcanoes, "
          f"{sum(n_eps[k] for k in left)} episodes")
    print("something seen at the volcano in the Coast Guard's database at the time:", sum(r["jh"] for r in out), "episodes")


if __name__ == "__main__":
    main()
