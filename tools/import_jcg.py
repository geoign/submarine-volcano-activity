"""Bring the extracted records of the Japan Coast Guard's volcano database into curation/.

    python tools/import_jcg.py [--from <folder>] [--retrieved YYYY-MM-DD]
    python tools/import_jcg.py [--from <folder>] --pending <file>

The Coast Guard's database of submarine volcanoes (海域火山データベース,
https://www1.kaiho.mlit.go.jp/kaiikiDB/list-2.htm) has a page per volcano with dated
observations. tools/parse_jcg.py extracts them into a folder outside this repository (default
`<work>/jcg`, with `work` from local.toml):

    jcg_records.csv    one row per observation since 2013: date, time, observer, category, text
    jcg_summaries.csv  optional: English summaries (text_ja, summary_en) of texts that report activity

This tool joins them with curation/jcg_sites.csv (which feature of which page belongs to which
volcano here, whether it is the volcano itself or a place nearby, and which monitoring zones it
lies in) into curation/jcg_observations.csv. A text that jcg_summaries.csv does not have keeps
the English summary it has in the present curation/jcg_observations.csv, so an update needs
summaries only for new texts: `--pending <file>` writes those texts (text_ja, summary_en empty)
and changes nothing else. Fill in the second column, save the file as jcg_summaries.csv in the
source folder and run the import again.
tools/build_db.py publishes that table as db/jcg_observations.csv and compares it with the
episodes (`prior_reports`).

A few rows of the source sum up the visits of a year ("2013年3月25日，7月1日 ... 特異事象なし").
Such a row becomes one row for each day its text names, with the same text.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_db import ROOT, local_settings  # noqa: E402
from safeio import write_csv  # noqa: E402

COLUMNS = ["volcano_id", "jcg_page", "site_ja", "site_en", "match", "zones", "date", "time", "observer", "category",
           "phenomena", "text_ja", "summary_en", "retrieved"]
CATEGORIES = {"anomaly", "none", "not_visible", "other"}
YEAR = re.compile(r"\d{4}")
DAY = re.compile(r"(\d{1,2})月(\d{1,2})日")


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_year(r: dict) -> list[dict]:
    """A row that sums up a year's visits without anything seen: one row for each day named in its text."""
    if not YEAR.fullmatch(r["date"]) or r["category"] != "none":
        return [r]
    days = sorted({f"{r['date']}-{int(m):02d}-{int(d):02d}" for m, d in DAY.findall(r["text_ja"])})
    return [dict(r, date=d, time="") for d in days] or [r]


def unique(rows: list[dict]) -> list[dict]:
    """Without the rows the source has twice (same site, day, time and text)."""
    seen, out = set(), []
    for r in rows:
        key = (r["volcano_id"], r["site_ja"], r["date"], r["time"], r["text_ja"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def load_summaries(summaries: Path, previous: Path) -> dict:
    """text_ja -> summary_en: from the summaries file when it exists, else from the previous table."""
    out = {}
    if Path(previous).exists():
        out.update({r["text_ja"]: r["summary_en"].strip() for r in read(previous) if r["summary_en"].strip()})
    if Path(summaries).exists():
        out.update({r["text_ja"]: r["summary_en"].strip() for r in read(summaries) if r["summary_en"].strip()})
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    local = local_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", default=str(Path(local.get("work", ROOT / "build")) / "jcg"))
    ap.add_argument("--retrieved", default=date.today().isoformat(), help="day the pages were fetched")
    ap.add_argument("--pending", help="write the texts that report activity and lack a summary to this file")
    args = ap.parse_args()
    src = Path(args.src)
    out = ROOT / "curation" / "jcg_observations.csv"
    sites = {(s["volcano_id"], s["site_ja"]): s for s in read(ROOT / "curation" / "jcg_sites.csv")}
    summaries = load_summaries(src / "jcg_summaries.csv", out)
    if args.pending:
        texts = dict.fromkeys(r["text_ja"] for r in read(src / "jcg_records.csv")
                              if r["category"] == "anomaly" and r["text_ja"] not in summaries)
        n = write_csv(Path(args.pending), ["text_ja", "summary_en"], ({"text_ja": t} for t in texts))
        print(f"{args.pending}: {n} texts that report activity without an English summary")
        return
    rows, missing, unknown, split = [], 0, set(), 0
    for raw in read(src / "jcg_records.csv"):
        if raw["category"] not in CATEGORIES:
            raise SystemExit(f"unknown category {raw['category']!r} on {raw['date']} ({raw['jcg_site']})")
        site = sites.get((raw["volcano_id"], raw["jcg_site"]))
        if not site:
            unknown.add((raw["volcano_id"], raw["jcg_site"]))
            continue
        parts = split_year(raw)
        split += len(parts) > 1
        for r in parts:
            en = summaries.get(r["text_ja"], "") if r["category"] == "anomaly" else ""
            missing += r["category"] == "anomaly" and not en
            rows.append(dict(
                volcano_id=r["volcano_id"], jcg_page=r["jcg_page"], site_ja=r["jcg_site"], site_en=site["site_en"],
                match=site["match"], zones=site["zones"], date=r["date"], time=r["time"], observer=r["observer"],
                category=r["category"], phenomena=r["phenomena"], text_ja=r["text_ja"], summary_en=en,
                retrieved=args.retrieved))
    if unknown:
        raise SystemExit(f"sites that curation/jcg_sites.csv does not have: {sorted(unknown)}")
    rows.sort(key=lambda r: (r["volcano_id"], r["date"], r["site_ja"], r["time"]))
    twice = len(rows)
    rows = unique(rows)
    n = write_csv(out, COLUMNS, rows)
    print(f"curation/jcg_observations.csv: {n} observations at {len({r['volcano_id'] for r in rows})} volcanoes "
          f"({split} yearly rows of the source split into days, {twice - n} repeated rows left out); "
          f"{missing} reports of activity without an English summary")


if __name__ == "__main__":
    main()
