"""Extract the activity records of the Japan Coast Guard's pages of submarine volcanoes.

    python tools/parse_jcg.py [--pages <folder>] [--out <folder>] [--fetch]
    python tools/parse_jcg.py dump <page>     print every row of every table of a saved page
    python tools/parse_jcg.py check           per named table: rows of 2013 or later in the HTML
                                              (counted independently) against rows written

The Coast Guard's database of submarine volcanoes (海域火山データベース,
https://www1.kaiho.mlit.go.jp/kaiikiDB/list-2.htm) has a page per volcano with one or more tables
of dated observations ("活動記録"). This tool reads the saved pages (default `<work>/jcg/pages`,
with `work` from local.toml) and writes `<out>/jcg_records.csv` (default `<work>/jcg`): one row per
observation since 2013 of the tables named in curation/jcg_sites.csv, with a category

    anomaly      the text says something was seen (phenomena: dw, fl, steam, plume, eruption,
                 island, bubbles, thermal, joined with +)
    none         nothing unusual was seen
    not_visible  weather or darkness kept the observers from seeing
    other        anything else

set by the keyword rules below, or by hand in curation/jcg_categories.csv (text_ja -> category,
phenomena, reason) where the rules go wrong. tools/import_jcg.py takes the table from there.

With --fetch the list page, the pages named in curation/jcg_sites.csv and the terms of use are
downloaded first into the pages folder: one plain request at a time, 3 seconds apart. The download
stops at the first HTTP error, and at a volcano page without a record table (the site changed).
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_db import ROOT, local_settings  # noqa: E402
from safeio import write_csv, write_text  # noqa: E402

BASE = "https://www1.kaiho.mlit.go.jp/kaiikiDB/"
LIST_PAGE = "list-2.htm"
TERMS = ("../../copyright.html", "copyright.html")  # link of the list page, name of the saved file
USER_AGENT = "python-urllib"
WAIT = 3.0
FIRST_YEAR = 2013
FIELDS = ["volcano_id", "jcg_page", "jcg_site", "match", "date", "time", "observer", "category", "phenomena",
          "text_ja"]
SITES = ROOT / "curation" / "jcg_sites.csv"
CATEGORIES = ROOT / "curation" / "jcg_categories.csv"

# ---- reading a page ----------------------------------------------------------------------------

H2_RE = re.compile(r'<h2 id="(activity[^"]*)"[^>]*>(.*?)</h2>', re.S)
BOX_RE = re.compile(r'<div class="actbox"\s*>', re.S)
TD_RE = re.compile(r'<div class="act_td"[^>]*>(.*?)</div>', re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def clean(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t.replace("　", " ")).strip()


def site_name(h2_inner: str) -> str:
    t = clean(h2_inner)
    t = re.sub(r"活動記録$", "", t).strip()
    return t.strip("「」 ")


def sections_of(text: str):
    """Yield (site, rows) for every record table of a page; a row is the list of its cleaned cells."""
    s = COMMENT_RE.sub("", text)
    for m in H2_RE.finditer(s):
        start = m.end()
        nxt = s.find("<h2", start)
        body = s[start: nxt if nxt != -1 else len(s)]
        boxes = list(BOX_RE.finditer(body))
        rows = []
        for j, b in enumerate(boxes):
            chunk = body[b.end(): boxes[j + 1].start() if j + 1 < len(boxes) else len(body)]
            rows.append([clean(x) for x in TD_RE.findall(chunk)])
        yield site_name(m.group(2)), rows


def read_page(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def sections(path: Path):
    return sections_of(read_page(path))


ZEN = str.maketrans("０１２３４５６７８９／～－", "0123456789/~-")


def parse_date(raw: str):
    """Return (date, year): date normalised (YYYY, YYYY-MM, YYYY-MM-DD or a range a/b), None if not parsed."""
    t = raw.translate(ZEN)
    # two full dates in one cell (separated by a line break on the page): keep both as a range
    parts = re.findall(r"\d{4}/\s*\d{1,2}/\s*\d{1,2}", t)
    if len(parts) >= 2 and re.fullmatch(r"(\s*\d{4}/\s*\d{1,2}/\s*\d{1,2}\s*)+", t):
        ds = [parse_date(p)[0] for p in parts]
        return ds[0] + "/" + ds[-1], int(parts[0][:4])
    t = t.replace(" ", "")
    m = re.fullmatch(r"(\d{4})年?", t)
    if m:
        return m.group(1), int(m.group(1))
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", t)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}", y
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})[-~](\d{1,2})", t)
    if m:
        y, mo, d1, d2 = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d1:02d}/{y:04d}-{mo:02d}-{d2:02d}", y
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})[-~](\d{1,2})/(\d{1,2})", t)
    if m:
        y, mo, d1, mo2, d2 = map(int, m.groups())
        y2 = y + 1 if mo2 < mo else y  # a range over the new year: 2020/12/30-1/2
        return f"{y:04d}-{mo:02d}-{d1:02d}/{y2:04d}-{mo2:02d}-{d2:02d}", y
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})[-~](\d{4})/(\d{1,2})/(\d{1,2})", t)
    if m:
        y, mo, d1, y2, mo2, d2 = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d1:02d}/{y2:04d}-{mo2:02d}-{d2:02d}", y
    m = re.fullmatch(r"(\d{4})/(\d{1,2})", t)
    if m:
        y, mo = map(int, m.groups())
        return f"{y:04d}-{mo:02d}", y
    m = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", t)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}", y
    m = re.fullmatch(r"(\d{4})年(\d{1,2})月", t)
    if m:
        y, mo = map(int, m.groups())
        return f"{y:04d}-{mo:02d}", y
    m = re.match(r"(\d{4})", t)
    return None, (int(m.group(1)) if m else None)


# ---- category rules ----------------------------------------------------------------------------

NOT_VISIBLE = re.compile(r"天候が悪く|悪天候|雲|視認できな|視認不能|確認できなかった|視界不良|降雨|夜間|天候不良|見えな|観測できな|視程")
NONE_RE = re.compile(r"特異事象(を|は|が)?(認められ|認めず|確認され|見られ|なし|無し)|目立つような噴火痕は見当たらなかった|変色水を認めず|噴火や浮遊物は認められなかった|特異事象なし|異常(は)?(認められ|なし)|変化(は)?(認められ|なし)|変色水(域)?(等)?(は|の)?(認められなかった|確認されなかった|なし)|噴気(等)?(は)?(認められなかった)")

PHEN = [
    ("dw", re.compile(r"変色")),
    ("fl", re.compile(r"軽石|浮遊物|浮流物|漂流物|浮遊|浮流")),
    ("steam", re.compile(r"噴気|白煙|水蒸気|湯気")),
    ("plume", re.compile(r"噴煙")),
    ("eruption", re.compile(r"噴火|噴出物|爆発|火柱|噴石|溶岩")),
    ("island", re.compile(r"新島|陸地|陸化|新たな島|島が出現")),
    ("bubbles", re.compile(r"気泡|湧出|ガス")),
    ("thermal", re.compile(r"熱|高温|温度")),
]
NEG_TAIL = re.compile(r"(は|も)?(認められなかった|確認されなかった|確認できなかった|見られなかった|なかった|無かった|なし|無し|認めず|認められず|見当たらな|視認されな|確認できず|判別できな|不明)")
POSITIVE = re.compile(r"認めた|確認した|認められた|確認された|観測した|見られた|していた|あった|が分布|噴出|広がって|伸びて")
# place names that contain a phenomenon word
NAME_RE = re.compile(r"噴火浅根(西ノ瀬)?")


def phenomena_of(text: str) -> list[str]:
    """Phenomena that the text says were seen (a mention in a negated clause is dropped)."""
    out = []
    text = NAME_RE.sub("〇", text)
    # clauses: split on the Japanese full stop and on "but"
    clauses = re.split(r"[。．.]|が、", text)
    for key, rx in PHEN:
        for c in clauses:
            if not rx.search(c):
                continue
            if NEG_TAIL.search(c) and not POSITIVE.search(c):
                continue
            out.append(key)
            break
    return out


def categorise(text: str, overrides: dict | None = None) -> tuple[str, str]:
    """(category, phenomena) of a text; a text of the hand-set table takes its category from there."""
    if overrides and text in overrides:
        return overrides[text]
    ph = phenomena_of(text)
    if ph:
        return "anomaly", "+".join(ph)
    if NONE_RE.search(text):
        return "none", ""
    if NOT_VISIBLE.search(text):
        return "not_visible", ""
    return "other", ""


# ---- tables ------------------------------------------------------------------------------------

def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_categories(path: Path) -> dict:
    if not Path(path).exists():
        return {}
    return {r["text_ja"]: (r["category"], r["phenomena"]) for r in read_csv(path)}


def page_files(folder: Path) -> list[Path]:
    return sorted(p for p in Path(folder).iterdir() if p.suffix in (".htm", ".html"))


def records(folder: Path, sites: list[dict], overrides: dict) -> tuple[list[dict], list[tuple]]:
    """Rows of the tables named in the site table, and (page, site, rows since 2013) of the others."""
    folder = Path(folder)
    tables = {}
    for name in sorted({s["jcg_page"] for s in sites}):
        path = folder / name
        if not path.exists():
            raise SystemExit(f"{name} (named in curation/jcg_sites.csv) is not in {folder}")
        for site, rows in sections(path):
            tables.setdefault((name, site), []).extend(rows)
    out = []
    for s in sites:
        key = (s["jcg_page"], s["site_ja"])
        if key not in tables:
            raise SystemExit(f"no record table {s['site_ja']} in {s['jcg_page']}")
        for r in tables[key]:
            if len(r) < 3:
                raise SystemExit(f"short row in {s['jcg_page']} {s['site_ja']}: {r}")
            day, year = parse_date(r[0])
            if year is None or year < FIRST_YEAR:
                continue
            if day is None:
                raise SystemExit(f"unparsed date {r[0]!r} in {s['jcg_page']}")
            cat, ph = categorise(r[2], overrides)
            out.append({
                "volcano_id": s["volcano_id"], "jcg_page": s["jcg_page"], "jcg_site": s["site_ja"],
                "match": s["match"], "date": day, "time": r[1], "observer": r[3] if len(r) > 3 else "",
                "category": cat, "phenomena": ph, "text_ja": r[2],
            })
    out.sort(key=lambda x: (x["volcano_id"], x["jcg_page"], x["jcg_site"], x["date"], x["time"]))
    named = {(s["jcg_page"], s["site_ja"]) for s in sites}
    others = []
    for path in page_files(folder):
        for site, rows in sections(path):
            if (path.name, site) in named:
                continue
            n = sum(1 for r in rows if r and (parse_date(r[0])[1] or 0) >= FIRST_YEAR)
            others.append((path.name, site, n))
    return out, others


def check(folder: Path, sites: list[dict], overrides: dict) -> int:
    """Count the rows of 2013 or later in the HTML by a plain search and compare; returns mismatches."""
    recs, _ = records(folder, sites, overrides)
    n_out = {}
    for r in recs:
        k = (r["jcg_page"], r["jcg_site"], r["volcano_id"])
        n_out[k] = n_out.get(k, 0) + 1
    bad = 0
    for s in sites:
        raw = COMMENT_RE.sub("", read_page(Path(folder) / s["jcg_page"]))
        n_html = 0
        for h in H2_RE.finditer(raw):
            if site_name(h.group(2)) != s["site_ja"]:
                continue
            nxt = raw.find("<h2", h.end())
            body = raw[h.end(): nxt if nxt != -1 else len(raw)]
            years = re.findall(r'<div class="actbox"\s*>\s*<div class="act_td"[^>]*>\s*[^<\d]*(\d{4})', body)
            n_html += sum(int(y) >= FIRST_YEAR for y in years)
        k = (s["jcg_page"], s["site_ja"], s["volcano_id"])
        flag = "" if n_html == n_out.get(k, 0) else "  <-- MISMATCH"
        bad += bool(flag)
        print(f"{s['jcg_page']:15s} {s['site_ja']:12s} {s['volcano_id']:28s} html={n_html:4d} "
              f"out={n_out.get(k, 0):4d}{flag}")
    return bad


# ---- download ----------------------------------------------------------------------------------

def fetch_plan(sites: list[dict], base: str = BASE) -> list[tuple[str, str, bool]]:
    """(url, file name, must hold a record table) for the list page, the named pages and the terms."""
    plan = [(urljoin(base, LIST_PAGE), LIST_PAGE, False)]
    for name in dict.fromkeys(s["jcg_page"] for s in sites):
        plan.append((urljoin(base, name), name, True))
    plan.append((urljoin(urljoin(base, LIST_PAGE), TERMS[0]), TERMS[1], False))
    return plan


def get(url: str, opener=urllib.request.urlopen) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(req, timeout=60) as r:
        data = r.read()
        charset = r.headers.get_content_charset() if getattr(r, "headers", None) is not None else None
    return data.decode(charset or "utf-8")


def download(plan, folder: Path, opener=urllib.request.urlopen, wait: float = WAIT, sleep=time.sleep) -> int:
    """Fetch the plan one page at a time into folder; stop at an HTTP error or a page without its table."""
    folder = Path(folder)
    for i, (url, name, needs_table) in enumerate(plan):
        if i:
            sleep(wait)
        try:
            text = get(url, opener)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{url}: HTTP {e.code}; stopped after {i} page(s)")
        if needs_table and not any(rows for _, rows in sections_of(text)):
            raise SystemExit(f"{url}: no record table (has the page changed?); stopped after {i} page(s)")
        write_text(folder / name, text)
        print(f"{name}: {len(text)} characters")
    return len(plan)


# ---- main --------------------------------------------------------------------------------------

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    work = Path(local_settings().get("work", ROOT / "build")) / "jcg"
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", choices=["write", "dump", "check"], default="write")
    ap.add_argument("page", nargs="?", help="page file name for dump")
    ap.add_argument("--pages", default=str(work / "pages"), help="folder of the saved pages")
    ap.add_argument("--out", default=str(work), help="folder for jcg_records.csv")
    ap.add_argument("--fetch", action="store_true", help="download the pages first")
    args = ap.parse_args()
    pages = Path(args.pages)
    sites = read_csv(SITES)
    overrides = read_categories(CATEGORIES)
    if args.mode == "dump":
        if not args.page:
            ap.error("dump needs a page")
        for site, rows in sections(pages / args.page):
            print("##", site, len(rows))
            for r in rows:
                print(" | ".join(r))
        return
    if args.fetch:
        download(fetch_plan(sites), pages)
    if args.mode == "check":
        raise SystemExit(1 if check(pages, sites, overrides) else 0)
    recs, others = records(pages, sites, overrides)
    n = write_csv(Path(args.out) / "jcg_records.csv", FIELDS, recs)
    used = {r["text_ja"] for r in recs}
    print(f"jcg_records.csv: {n} records of {len({(s['jcg_page'], s['site_ja']) for s in sites})} tables; "
          f"{sum(c == 'anomaly' for c in (r['category'] for r in recs))} report activity; "
          f"{len(used & overrides.keys())} of {len(overrides)} hand-set categories used")
    if others:
        print(f"{len(others)} tables not in curation/jcg_sites.csv (page, site, rows since {FIRST_YEAR}): "
              + "; ".join(f"{p} {s} {n}" for p, s, n in others))


if __name__ == "__main__":
    main()
