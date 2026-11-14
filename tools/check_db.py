"""Check the built tables under db/ and the files that will be published.

    python tools/check_db.py [--images N]

Exits with status 1 when a check fails. The checks:

- every table parses, has its columns, and uses only the documented vocabularies;
- ids join: episodes and zones point to volcanoes, alert passes to episodes;
- counts agree between meta.json, index.json and the tables;
- nothing that is to be committed holds a local path, a user name, or anything shaped like a key;
- with --images N, N quicklook URLs drawn at random answer with an image (network).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vocab import BASES, CAUSES, CLASSES, PHENOMENA  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db"
LEAKS = [
    (re.compile(r"[A-Za-z]:\\Users\\", re.I), "Windows user folder"),
    (re.compile(r"/c/Users/|C:/Users/", re.I), "Windows user folder"),
    (re.compile(r"OneDrive", re.I), "local folder name"),
    (re.compile(r"\b[A-Z]:[\\/][A-Za-z_]"), "drive path of this PC"),
    (re.compile(r"\bcloudflare\d*:"), "name of an rclone remote"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "GitHub token"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"), "API key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"[\w.+-]+@(?!users\.noreply\.github\.com)[\w-]+\.[\w.-]+"), "e-mail address"),
]
ALLOWED_MAIL = {"f.ikegami@gmail.com", "noreply@anthropic.com"}
TEXT = {".py", ".js", ".css", ".html", ".md", ".csv", ".json", ".cff", ".txt", ".svg", ".toml", ".yml", ".yaml", ""}

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)
    print("FAIL", msg)


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def check_tables() -> None:
    meta = json.loads((DB / "meta.json").read_text(encoding="utf-8"))
    index = json.loads((DB / "index.json").read_text(encoding="utf-8"))
    volcanoes = read(DB / "volcanoes.csv")
    zones = read(DB / "zones.csv")
    episodes = read(DB / "episodes.csv")
    vids = {v["volcano_id"] for v in volcanoes}
    zids = {z["zone_id"] for z in zones}
    if len(vids) != len(volcanoes):
        fail("volcanoes.csv: duplicate volcano_id")
    if meta["volcanoes"] != len(volcanoes) or len(index["volcanoes"]) != len(volcanoes):
        fail("volcano counts differ between meta.json, index.json and volcanoes.csv")
    if meta["episodes"] != len(episodes):
        fail(f"meta.json says {meta['episodes']} episodes, episodes.csv has {len(episodes)}")
    if index["classes"] != CLASSES:
        fail("index.json: class list differs from tools/vocab.py")
    for z in zones:
        if z["volcano_id"] not in vids:
            fail(f"zones.csv: {z['zone_id']} points to an unknown volcano")
    ids = Counter(e["episode_id"] for e in episodes)
    for eid, n in ids.items():
        if n > 1:
            fail(f"episodes.csv: {eid} appears {n} times")
    by_class = Counter()
    for e in episodes:
        by_class[e["class"]] += 1
        if e["volcano_id"] not in vids:
            fail(f"{e['episode_id']}: unknown volcano {e['volcano_id']}")
        if e["zone_id"] not in zids:
            fail(f"{e['episode_id']}: unknown zone {e['zone_id']}")
        if e["class"] not in CLASSES:
            fail(f"{e['episode_id']}: unknown class {e['class']!r}")
        if e["cause"] and e["cause"] not in CAUSES:
            fail(f"{e['episode_id']}: unknown cause {e['cause']!r}")
        if e["basis"] not in BASES:
            fail(f"{e['episode_id']}: unknown basis {e['basis']!r}")
        if (e["class"] == "unreviewed") != (e["basis"] == ""):
            fail(f"{e['episode_id']}: class {e['class']} with basis {e['basis']!r}")
        if e["class"] == "nonvolcanic" and not e["cause"]:
            fail(f"{e['episode_id']}: dismissed without a cause")
        if any(p not in PHENOMENA for p in e["phenomena"].split("+") if p):
            fail(f"{e['episode_id']}: unknown phenomenon in {e['phenomena']!r}")
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", e["start"]) or not re.fullmatch(r"\d{4}-\d\d-\d\d", e["end"]) or e["end"] < e["start"]:
            fail(f"{e['episode_id']}: bad dates {e['start']}..{e['end']}")
        if e["class"] == "known" and not e["known_ref"]:
            fail(f"{e['episode_id']}: class known without a reference")
    overrides = ROOT / "curation" / "overrides.csv"
    if overrides.exists():
        gone = [r["episode_id"] for r in read(overrides) if r["episode_id"] not in ids]
        if gone:
            fail(f"curation/overrides.csv names {len(gone)} episode(s) that are not in the tables, e.g. {gone[:3]}")
    for e in episodes:
        if e["tier"] == "lowres" and "fl" in e["phenomena"].split("+"):
            fail(f"{e['episode_id']}: low-resolution episode with floating matter")
    if dict(by_class) != {c: n for c, n in meta["episodes_by_class"].items() if n}:
        fail("meta.json: episodes_by_class differs from episodes.csv")
    for v in volcanoes:
        mine = Counter(e["class"] for e in episodes if e["volcano_id"] == v["volcano_id"])
        if any(int(v[f"n_{c}"]) != mine.get(c, 0) for c in CLASSES):
            fail(f"volcanoes.csv: class counts of {v['volcano_id']} differ from episodes.csv")

    n_pass = n_img = 0
    alert_ids = set()
    high = {e["episode_id"] for e in episodes if e["tier"] == "highres"}
    for path in sorted((DB / "passes").glob("*.csv")):
        if path.stem not in vids:
            fail(f"passes/{path.name}: no such volcano")
        last = ""
        for p in read(path):
            n_pass += 1
            n_img += p["img"] == "1"
            if p["time"] < last:
                fail(f"passes/{path.name}: not in order of time at {p['time']}")
                break
            last = p["time"]
            if p["bearing"] and not 0 <= float(p["bearing"]) <= 360:
                fail(f"passes/{path.name}: bearing {p['bearing']} at {p['time']}")
                break
            if p["cls"] not in ("A", "B", "C") or p["level"] not in ("L0", "L1", "L2", "L3"):
                fail(f"passes/{path.name}: bad class or level at {p['time']}")
                break
            if p["episode_id"]:
                alert_ids.add(p["episode_id"])
                if p["episode_id"] not in high:
                    fail(f"passes/{path.name}: {p['time']} points to an unknown episode {p['episode_id']}")
                    break
    if n_pass != meta["passes"] or n_img != meta["quicklooks"]:
        fail(f"pass tables hold {n_pass} passes and {n_img} quicklooks, meta.json says {meta['passes']} and {meta['quicklooks']}")
    orphan = high - alert_ids
    if orphan:
        fail(f"{len(orphan)} high-resolution episodes have no pass in the pass tables, e.g. {sorted(orphan)[:3]}")
    n_days = sum(len(read(p)) for p in (DB / "lowres").glob("*.csv"))
    if n_days != meta["lowres_days"]:
        fail(f"lowres tables hold {n_days} days, meta.json says {meta['lowres_days']}")
    print(f"tables: {len(volcanoes)} volcanoes, {len(zones)} zones, {len(episodes)} episodes, {n_pass} passes, {n_days} low-resolution days")
    print("episodes by class:", dict(by_class))


def tracked_files() -> list[Path]:
    """Files git would commit: tracked ones and untracked ones that are not ignored."""
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, text=True, encoding="utf-8")
    return [ROOT / line for line in out.stdout.splitlines() if line]


def check_leaks() -> None:
    n = 0
    for path in tracked_files():
        if path.suffix.lower() not in TEXT or not path.is_file() or "vendor" in path.parts:
            continue
        n += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, what in LEAKS:
            for m in pattern.finditer(text):
                if what == "e-mail address" and (m.group(0) in ALLOWED_MAIL or m.group(0).endswith((".jpg", ".png", ".csv"))):
                    continue
                if what == "local account name" and path.name == "check_db.py":
                    continue
                if what in ("Windows user folder", "local folder name", "drive path of this PC", "name of an rclone remote") and path.name == "check_db.py":
                    continue
                fail(f"{path.relative_to(ROOT)}: {what}: {m.group(0)[:40]}")
                break
    print(f"leak scan: {n} text files")


def check_images(n: int) -> None:
    meta = json.loads((DB / "meta.json").read_text(encoding="utf-8"))
    rng = random.Random(20261114)
    files = sorted((DB / "passes").glob("*.csv"))
    urls = []
    while len(urls) < n:
        rows = [p for p in read(rng.choice(files)) if p["img"] == "1"]
        if rows:
            p = rng.choice(rows)
            stamp = p["time"].replace("-", "").replace(":", "")
            urls.append(f"{meta['image_base']}/ql/{p['zone_id']}/{p['zone_id']}_{stamp}_{p['sat']}.jpg")
    bad = 0
    for url in urls:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "submvolc-db-check"})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
                    bad += 1
                    fail(f"{url}: {r.status} {r.headers.get('Content-Type')}")
        except Exception as exc:  # noqa: BLE001
            bad += 1
            fail(f"{url}: {exc}")
    print(f"images: {n - bad} of {n} sampled quicklooks answer")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=int, default=0, help="number of quicklook URLs to request")
    args = ap.parse_args()
    check_tables()
    check_leaks()
    if args.images:
        check_images(args.images)
    print("OK" if not errors else f"{len(errors)} check(s) failed")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
