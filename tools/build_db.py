"""Build the public tables under db/ from the stores of the monitoring system.

    python tools/build_db.py [--monitor <checkout of the monitoring system>] [--work <folder>]

Both default to the entries `monitor` and `work` of local.toml (not committed; see README).

The monitoring system (not part of this repository) keeps its observations in SQLite stores and
its reviews in CSV tables. This tool reads them, never writes to them, and produces:

    db/volcanoes.csv, db/zones.csv        the targets and their monitoring zones
    db/episodes.csv                       one row per episode with its public class and notes
    db/passes/<volcano_id>.csv            every high-resolution pass, alert or not
    db/lowres/<volcano_id>.csv            daily low-resolution screening (sea visible days)
    db/known_periods.csv                  eruption periods the episodes were matched against
    db/records/*.csv                      ring waves and airborne bands
    db/index.json, db/meta.json           what the map page needs, and the build stamp
    <work>/lists/ql_*.txt                 quicklooks to publish (for tools/sync_images.py)

High-resolution passes before CUT come from the second hindcast (data/retro2), later ones from
the monitor's own store (data/). Episodes of the monitor's store are rebuilt on every run by the
monitor's own script, into <work>/monitor_review, so that they follow its current rules.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safeio import write_csv, write_text  # noqa: E402
from vocab import CAUSES, CLASS_EN, CLASS_JA, CLASSES, COVERAGE, DEPTH_CLASS, VERDICT_CLASS, ZONE_TYPE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db"
CURATION = ROOT / "curation"
CUT = "2025-11-12T00:00:00Z"
IMAGE_BASE = "https://gis.ikgm.net/submvolc"
HINDCAST_REPORT = "reports/hindcast2-20261114"
SAT = {"sentinel-2a": "S2A", "sentinel-2b": "S2B", "sentinel-2c": "S2C", "sentinel-2d": "S2D",
       "landsat-8": "L8", "landsat-9": "L9"}
RANK = {c: i for i, c in enumerate(CLASSES)}
# Figures of the reports that are not published: they overlay bathymetry that is not yet public.
WITHHELD_FIGURES = {"hindcast1/fig28_fonuafoou_10m_study.jpg"}
# Working documents of the monitoring system that notes refer to, and where their content is here.
PUBLIC_COPIES = {"docs/AIRBORNE_BANDS.md": "db/records/airborne_bands.csv",
                 "docs/RING_WAVES.md": "db/records/ring_waves.csv"}
REEF_ZONES = {"Curacoa", "Hankow Reef"}
REEF_JA = "礁と海岸。毎回同じ場所に出るので、1 件ずつの確認からは外した (2 回目の遡及調査の報告)。"
USUAL_EN = ("The low-resolution review filed this as the usual appearance of the zone. At this volcano the usual "
            "appearance is volcanic discoloured water, so the episode is listed as possibly volcanic, like the "
            "high-resolution episodes of the same period.")
USUAL_JA = ("低解像度の判定では、区域のいつもの姿とされました。この火山のいつもの姿は火山性の変色水なので、"
            "同じ時期の高解像度のエピソードと同じく「火山性の可能性あり」としています。")
DIGEST_EN = ("Low-resolution passes (VIIRS, MODIS, OLCI) of the reviewed episodes, cut out 30 km square around the zone "
             "centre (yellow cross). One row per episode; pink outline: discoloured water, orange outline: bright "
             "floating matter. Above each frame: date, satellite, area of discoloured water and of bright matter in "
             "km2, distance from the centre.")
DIGEST_JA = ("判定した低解像度のエピソードの通過 (VIIRS、MODIS、OLCI) を、区域の中心 (黄色の十字) のまわり 30 km 四方で"
             "切り出して並べた図です。1 行が 1 エピソードで、桃色の輪郭が変色水、橙色の輪郭が明るい浮遊物です。"
             "各コマの上の文字は、日付、衛星、変色水の面積と明るい浮遊物の面積 (km2)、中心からの距離です。")


# ----------------------------------------------------------------------------- helpers

def local_settings() -> dict:
    """Paths of this PC: local.toml beside the repository's README, never committed."""
    path = ROOT / "local.toml"
    if not path.exists():
        return {}
    import tomllib
    return tomllib.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))




def ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def num(v, digits: int = 3):
    """A number for a CSV cell: rounded, without trailing zeros; empty for nothing."""
    if v is None or v == "":
        return ""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    if x != x:  # NaN
        return ""
    s = f"{x:.{digits}f}"
    if "." in s:  # only zeros of the fraction go; "290" must stay "290"
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def note_key(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


def site_of(zone_id: str) -> str:
    """The zone a Landsat twin zone belongs to."""
    return zone_id[:-3] if zone_id.endswith("-LS") else zone_id


def obs_days(obs_ids: str) -> set[str]:
    """The days (YYYYMMDD) of a list of observation ids."""
    return {m.group(1) for m in re.finditer(r"_(\d{8})T\d{4}_", obs_ids or "")}


def md_table(path: Path, first_header: str) -> list[dict]:
    """The rows of the markdown table whose header starts with `first_header`."""
    rows, cols = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            if cols:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cols is None:
            if cells[0] == first_header:
                cols = cells
            continue
        if set(cells[0]) <= set("-: "):
            continue
        rows.append(dict(zip(cols, cells)))
    return rows


# ----------------------------------------------------------------------------- curation

def load_curation() -> dict:
    cur = {"overrides": {}, "notes_en": {}, "names_ja": {}, "summaries": {}, "figures": [], "human": {}}
    p = CURATION / "human_review.csv"
    if p.exists():
        for r in read_csv(p):
            if r.get("verdict") not in CLASSES or r["verdict"] == "unreviewed":
                raise SystemExit(f"curation/human_review.csv: verdict {r.get('verdict')!r} for {r.get('episode_id')}")
            cur["human"][r["episode_id"]] = r
    p = CURATION / "overrides.csv"
    if p.exists():
        for r in read_csv(p):
            cur["overrides"][r["episode_id"]] = r
    p = CURATION / "notes_en.csv"
    if p.exists():
        for r in read_csv(p):
            if r.get("note_en", "").strip():
                cur["notes_en"][r["key"]] = r["note_en"].strip()
    p = CURATION / "names_ja.csv"
    if p.exists():
        for r in read_csv(p):
            if r.get("name_ja", "").strip():
                cur["names_ja"][r["volcano_id"]] = r["name_ja"].strip()
    p = CURATION / "volcano_summaries.csv"
    if p.exists():
        for r in read_csv(p):
            cur["summaries"][r["volcano_id"]] = r
    p = CURATION / "figures.csv"
    if p.exists():
        cur["figures"] = read_csv(p)
    return cur


# ----------------------------------------------------------------------------- targets

def load_targets(mon: Path, cur: dict):
    wide = read_csv(mon / "aoi/wide_zones.csv")
    zones = read_csv(mon / "aoi/zones.csv")
    targets = {r["id"]: r for r in read_csv(mon / "aoi/source/submarine_volcano_monitor_targets.csv")}
    volcanoes, zone_rows = {}, []
    for r in wide:
        t = targets.get(r["target_id"], {})
        gvp = r["gvp_number"].split(".")[0] if r["gvp_number"] else ""
        volcanoes[r["target_id"]] = dict(
            volcano_id=r["target_id"], gvp_number=gvp, name=r["volcano"],
            name_ja=cur["names_ja"].get(r["target_id"], ""), country=re.sub(r"\s*:\s*", ": ", r["country"]).strip(),
            lat=num(r["lat"], 4), lon=num(r["lon"], 4),
            depth_class=DEPTH_CLASS.get(t.get("depth_class", ""), "unknown"),
            coverage=COVERAGE.get(t.get("coverage", ""), "lowres_only"),
            tiers="highres+lowres" if r["tier"] == "hires+wide" else "lowres",
            baseline_class=r["baseline_class"], n_zones=0,
            # The owner's list of places where the same ordinary thing shows on every clear pass
            # ("常時" in the source table). Fukutoku-Oka-no-Ba is judged by its own history as
            # well, but for frequent volcanic discoloured water, so it is not in this list.
            _usual=t.get("discoloration_baseline", "").startswith("常時"))
        zone_rows.append(dict(
            zone_id=r["wide_id"], volcano_id=r["target_id"], tier="lowres", name=r["volcano"], kind="whole volcano",
            lat=num(r["lat"], 4), lon=num(r["lon"], 4), radius_km=num(r["radius_km"], 1), sensors="lowres"))
    zone_volcano = {}
    for z in zones:
        if z["target_id"] not in volcanoes:
            raise SystemExit(f"zone {z['zone_id']} belongs to {z['target_id']}, which is not in wide_zones.csv")
        volcanoes[z["target_id"]]["n_zones"] += 1
        zone_volcano[z["zone_id"]] = z["target_id"]
        kind = ZONE_TYPE.get(z["zone_type_ja"])
        if kind is None:
            raise SystemExit(f"zone type without a translation: {z['zone_type_ja']!r} (tools/vocab.py)")
        zone_rows.append(dict(
            zone_id=z["zone_id"], volcano_id=z["target_id"], tier="highres", name=z["zone_name"], kind=kind,
            lat=num(z["lat"], 4), lon=num(z["lon"], 4), radius_km=num(z["radius_km"], 1), sensors=z["coverage"]))
    zone_rows.sort(key=lambda r: (r["volcano_id"], r["tier"], r["zone_id"]))
    return volcanoes, zone_rows, zone_volcano


# ----------------------------------------------------------------------------- passes

def load_passes(db_path: Path, store: str, where: str, zone_volcano: dict):
    """Observations of one store as rows for db/passes, grouped by volcano."""
    out = defaultdict(list)
    root = db_path.parent
    con = ro(db_path)
    q = ("select obs_id, zone_id, datetime, platform, obs_class, clear_frac, level, features, quicklook_path "
         f"from observations where status='ok' and {where}")
    for obs_id, zone_id, dt, platform, cls, clear, level, feat, ql in con.execute(q):
        vid = zone_volcano.get(site_of(zone_id))
        if vid is None:
            continue
        sat = SAT.get(platform or "", "")
        t = dt[:16]
        expect = f"{zone_id}_{t[:4]}{t[5:7]}{t[8:10]}T{t[11:13]}{t[14:16]}_{sat}"
        if obs_id != expect:
            raise SystemExit(f"observation id does not follow zone_time_satellite: {obs_id} vs {expect}")
        lv, _, reasons = (level or "").partition(":")
        row = dict(obs_id=obs_id, zone_id=zone_id, time=t, sat=sat, cls=cls or "", clear=num(clear, 2),
                   level=lv, reasons=reasons, store=store, episode_id="", img=0)
        if cls in ("A", "B"):
            f = json.loads(feat) if feat else {}
            row.update(dw_km2=num(f.get("dw_km2")), colour=f.get("dw_colour") or "",
                       dist_km=num(f.get("dw_dist_km"), 2) if f.get("dw_km2") else "",
                       bearing=num(f.get("dw_bearing"), 0) if f.get("dw_km2") else "",
                       fl_km2=num(f.get("fl_km2")), nl_km2=num(f.get("nl_km2")),
                       th_px=num(f.get("th_px"), 0), ap_km2=num(f.get("ap_km2")))
            if ql and (root / ql).exists():
                row["img"] = 1
                row["ql"] = ql.replace("\\", "/")
        out[vid].append(row)
    con.close()
    return out


# ----------------------------------------------------------------------------- episodes

def hindcast_episodes(mon: Path, zone_volcano: dict) -> list[dict]:
    eps = read_csv(mon / "data/retro2/review/episodes.csv")
    triage = {r["episode"]: r for r in read_csv(mon / HINDCAST_REPORT / "triage.csv")}
    owner = {r["episode"]: r.get("owner_verdict", "") for r in read_csv(mon / HINDCAST_REPORT / "look.csv")}
    first = mon / "data/retro/review/episodes.csv"
    earlier = {r["episode"]: obs_days(r["obs_ids"]) for r in read_csv(first)} if first.exists() else {}
    rows = []
    n_void = 0
    for e in eps:
        t = triage.get(e["episode"], {})
        cls, basis, cause, interest, note = "unreviewed", "", "", "", ""
        # The second hindcast took over the review of the first for every episode that overlaps one
        # of the first within 21 days. Where the two share no alert day, the review was of other
        # passes: the episode is not reviewed.
        carried = t.get("source") == "earlier run"
        mine, theirs = obs_days(e["obs_ids"]), earlier.get(e.get("prior_episode", ""), set())
        if carried and not e["known"] and not (mine & theirs):
            n_void += 1
            t = {}
        # "ai_review_partial": the review saw some of this episode's alert passes, not all of them.
        how = "ai_review_partial" if carried and not mine <= theirs else "ai_review"
        if e["known"]:
            cls, basis = "known", "catalogue"
        elif t.get("call") == "dismiss":
            cls, basis, cause, interest = "nonvolcanic", how, t.get("cause", ""), "0"
        elif t.get("call") == "look":
            interest = str(int(float(t.get("interest") or 0)))
            cls, basis = {"3": "likely", "2": "possible"}.get(interest, "undetermined"), how
        note = (t.get("note") or "").strip()
        rows.append(_episode_row(e, "hindcast2", zone_volcano, cls, basis, cause, interest, note,
                                 owner.get(e["episode"], "")))
    print(f"  hindcast: {n_void} carried reviews set aside (no alert day in common with the reviewed episode)")
    return rows


def monitor_episodes(mon: Path, work: Path, zone_volcano: dict, refresh: bool) -> list[dict]:
    out = work / "monitor_review"
    prev = mon / "data/review/triage_merged.csv"
    if refresh:
        env = dict(os.environ, PYTHONUTF8="1")
        env.pop("SUBMVOLC_PROFILE", None)
        cmd = [sys.executable, "scripts/retro_episodes.py", "--out", str(out), "--previous", str(prev), "--show", "0"]
        res = subprocess.run(cmd, cwd=mon, env=env, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            raise SystemExit("the monitor's retro_episodes.py failed:\n" + res.stderr[-2000:])
    eps = [e for e in read_csv(out / "episodes.csv") if e["start"] >= CUT[:10]]
    notes = {r["episode"]: (r.get("note") or "").strip() for r in read_csv(prev)}
    old = mon / "data/review/episodes.csv"
    earlier = {r["episode"]: obs_days(r["obs_ids"]) for r in read_csv(old)} if old.exists() else {}
    con = ro(mon / "data/state.sqlite")
    verdicts = {}
    for obs_id, verdict, evidence, causes in con.execute(
            "select obs_id, verdict, evidence, causes from verdicts order by created_at"):
        try:
            first = (json.loads(causes or "[]") or [""])[0]
        except ValueError:
            first = ""
        verdicts[obs_id] = (verdict, (evidence or "").strip(), first if first in CAUSES else "")
    con.close()
    rows = []
    for e in eps:
        cls, basis, cause, interest, note = "unreviewed", "", "", "", ""
        mine, theirs = obs_days(e["obs_ids"]), earlier.get(e["prior_episode"], set())
        shared = mine & theirs
        how = "ai_review" if mine <= theirs else "ai_review_partial"
        if not shared:
            pass  # the triage it would inherit looked at other passes
        elif e["prior_call"] == "dismiss":
            cls, basis, cause, interest = "nonvolcanic", how, e["prior_cause"], "0"
        elif e["prior_call"] == "look":
            interest = str(int(float(e["prior_interest"] or 0)))
            cls, basis = {"3": "likely", "2": "possible"}.get(interest, "undetermined"), how
        if shared:
            note = notes.get(e["prior_episode"], "")
        # A verdict recorded for a pass of the episode outweighs the triage of the episode.
        best = None
        for o in e["obs_ids"].split():
            if o in verdicts:
                c = VERDICT_CLASS.get(verdicts[o][0])
                if c and (best is None or RANK[c] < RANK[best[0]]):
                    best = (c, verdicts[o][1], verdicts[o][2])
        explicit = False
        # A verdict of "likely" or "possible" always stands: it was given to a pass on purpose. A
        # dismissal of one pass does not undo a flag on the whole episode.
        if best and (best[0] in ("likely", "possible") or cls in ("unreviewed", "undetermined") or RANK[best[0]] < RANK[cls]):
            cls, basis, explicit = best[0], "ai_review", True
            if best[1]:
                note = best[1]
            if cls == "nonvolcanic":
                cause = best[2] or cause or "other"
        if e["known"]:
            cls, basis = "known", "catalogue"
        row = _episode_row(e, "monitor", zone_volcano, cls, basis, cause, interest, note, "")
        row["_explicit"] = explicit
        rows.append(row)
    return rows


def _episode_row(e, source, zone_volcano, cls, basis, cause, interest, note, owner) -> dict:
    return dict(
        episode_id=e["episode"], volcano_id=zone_volcano[e["zone_id"]], zone_id=e["zone_id"], tier="highres",
        source=source, start=e["start"], end=e["end"], n_detect=e["n_alert"], n_seen=e["n_usable"], n_l3=e["n_l3"],
        phenomena=e["reasons"], max_dw_km2=num(e["max_dw_km2"]), max_fl_km2=num(e["max_fl_km2"]),
        max_nl_km2=num(e["max_nl_km2"]), colour=e["colour"], median_dist_km=num(e["median_dist_km"], 2),
        sensors=e.get("sensors") or "Sentinel-2", peak=e["peak_obs"], cls=cls, basis=basis, cause=cause,
        interest=interest, known_ref=e["known"], prior_reports="", note_ja=note, owner_ja=owner,
        _obs=e["obs_ids"].split())


def lowres_episodes(mon: Path, volcanoes: dict) -> list[dict]:
    ranked = {r["episode"]: r for r in read_csv(mon / HINDCAST_REPORT / "wide_episodes_ranked.csv")}
    rows = []
    reviewed = set()
    for r in read_csv(mon / HINDCAST_REPORT / "wide_lead_review.csv"):
        k = ranked[r["episode"]]
        reviewed.add(r["episode"])
        interest = str(int(float(r["interest"] or 0)))
        if r["call"] == "look":
            cls, cause = {"3": "likely", "2": "possible"}.get(interest, "undetermined"), ""
        elif r["cause"] == "persistent":
            cls, cause = "recurrent", ""
        else:
            cls, cause = "nonvolcanic", r["cause"]
        row = _lowres_row(k, cls, "ai_review", cause, interest, r["note"].strip(), sheet=True)
        if cls == "recurrent" and k["target_id"] in volcanoes and not volcanoes[k["target_id"]]["_usual"]:
            # The review filed it as the zone's usual appearance; at a volcano that is not on the
            # owner's list of usual features the usual appearance is volcanic discoloured water.
            row.update(cls="possible", basis="rule", curation_en=USUAL_EN, curation_ja=USUAL_JA)
        rows.append(row)
    for eid, k in ranked.items():
        # Alerts inside a documented eruption period count only where the water was at the vent.
        if eid in reviewed or int(k["near_days"] or 0) < 2:
            continue
        # "..ongoing" is the monitor's reading of a catalogue entry without an end date. For an
        # eruption that began years before the episode that is no match (McDonald Islands 2001).
        m = re.match(r"GVP .*? (\d{4})-\d\d-\d\d\.\.ongoing", k["known"])
        stale = bool(m) and int(k["start"][:4]) - int(m.group(1)) > 2
        if k["known"] and not stale:
            rows.append(_lowres_row(k, "known", "catalogue", "", "", "", sheet=False))
        elif k["volcano"] in REEF_ZONES:
            # Left out of the one-by-one review as reef zones (report of the second hindcast).
            rows.append(dict(_lowres_row(dict(k, known=""), "nonvolcanic", "lead_review", "reef_or_shoal", "0", REEF_JA,
                                         sheet=False), _bulk=True))
        else:
            rows.append(_lowres_row(dict(k, known=""), "unreviewed", "", "", "", "", sheet=False))
    return [r for r in rows if r["volcano_id"] in volcanoes]


def _lowres_row(k, cls, basis, cause, interest, note, sheet) -> dict:
    # "bright" of the survey answers to cloud that kept its reflectance; it is not floating matter.
    kinds = {"dw": "dw", "bright": "", "dw+bright": "dw"}
    return dict(
        episode_id=k["episode"], volcano_id=k["target_id"], zone_id=k["wide_id"], tier="lowres",
        source="olci_survey", start=k["start"], end=k["end"], n_detect=k["near_days"], n_seen=k["days_seen"],
        n_l3=k["n_l3"], phenomena=kinds.get(k["kind"], k["kind"]), max_dw_km2=num(k["near_peak_km2"]),
        max_fl_km2="", max_nl_km2="", colour="", median_dist_km=num(k["min_dist_km"], 1), sensors="OLCI",
        peak=k["peak_day"], cls=cls, basis=basis, cause=cause, interest=interest, known_ref=k["known"],
        prior_reports="", note_ja=note, owner_ja="", _obs=[], _sheet=sheet)


def classify(episodes: list[dict], volcanoes: dict, cur: dict) -> None:
    """Rules that follow the owner's decisions, then the curated overrides."""
    for e in episodes:
        usual = volcanoes[e["volcano_id"]]["_usual"]
        if usual and e["cls"] in ("likely", "possible", "undetermined") and not e.get("_explicit"):
            # Places with a usual feature: the recurring pale water is on record, not an alert.
            e["cls"], e["basis"] = "recurrent", "rule"
        o = e["owner_ja"]
        if o:
            e["basis"] = "owner"
            if "帯" in o:
                e["cls"] = "airborne"
            elif "異常なし" in o:
                e["cls"], e["cause"] = "nonvolcanic", e["cause"] or "other"
            elif "異常ではない" in o:
                e["cls"] = "recurrent"
            else:
                print(f"  warning: the owner's verdict of {e['episode_id']} was not understood: {o[:40]}")
        ov = cur["overrides"].get(e["episode_id"])
        if ov:
            if ov.get("class"):
                if ov["class"] not in CLASSES:
                    raise SystemExit(f"curation/overrides.csv: unknown class {ov['class']!r} for {e['episode_id']}")
                e["cls"] = ov["class"]
                e["basis"] = ov.get("basis") or "curated"
            if ov.get("cause"):
                e["cause"] = ov["cause"]
            if ov.get("prior_reports"):
                e["prior_reports"] = ov["prior_reports"]
            if ov.get("known_ref"):
                e["known_ref"] = ov["known_ref"]
            if ov.get("owner_ja"):
                e["owner_ja"] = ov["owner_ja"]
            e["curation_ja"] = ov.get("reason_ja", "")
            e["curation_en"] = ov.get("reason_en", "")
        h = cur.get("human", {}).get(e["episode_id"])
        if h:
            # The author's review in the form (tools/build_review.py) is the last word.
            if h["verdict"] == "known" and not e.get("known_ref"):
                raise SystemExit(f"curation/human_review.csv: {e['episode_id']} is judged 'known', but the episode "
                                 "matches no eruption period (the review form does not offer that class for it)")
            day = (h.get("reviewed_at") or "")[:10]
            e["cls"], e["basis"] = h["verdict"], "owner"
            e["cause"] = (h.get("cause") or e["cause"] or "other") if h["verdict"] == "nonvolcanic" else ""
            comment = (h.get("comment") or "").strip()
            e["owner_ja"] = f"{day}: {comment}" if comment else f"{day}: 画像を確認 ({CLASS_JA[h['verdict']]})"
            e["_owner_en"] = "" if comment else f"{day}: reviewed from the images ({CLASS_EN[h['verdict']]})"
            e["_reviewed_at"] = day
        if e["cls"] != "nonvolcanic" and e["cause"] and e["cls"] != "recurrent":
            e["cause"] = ""
        # Who looked: the author, an AI-assisted review, or nobody (screening, a date match, or a
        # decision taken for a whole zone without looking at its episodes).
        if e["basis"] == "owner":
            e["review_status"] = "human-reviewed"
            m = re.match(r"(\d{4}-\d\d-\d\d)", e.get("owner_ja") or "")
            e["reviewed_at"] = e.get("_reviewed_at") or (m.group(1) if m else "")
        elif e["basis"] in ("ai_review", "ai_review_partial", "lead_review", "rule") and not e.get("_bulk"):
            e["review_status"], e["reviewed_at"] = "ai-reviewed", ""
        else:
            e["review_status"], e["reviewed_at"] = "automatic", ""
    gone = set(cur.get("human", {})) - {e["episode_id"] for e in episodes}
    if gone:
        print(f"  warning: {len(gone)} human review(s) name an episode that is not in the tables, e.g. {sorted(gone)[:3]}")
    unknown = set(cur["overrides"]) - {e["episode_id"] for e in episodes}
    if unknown:
        print(f"  warning: {len(unknown)} override(s) name an episode that is not in the tables, e.g. {sorted(unknown)[:3]}")


# ----------------------------------------------------------------------------- reference tables

def known_periods(mon: Path, volcanoes: dict, first_year: int = 2013) -> list[dict]:
    by_gvp = {v["gvp_number"]: vid for vid, v in volcanoes.items() if v["gvp_number"]}
    files = sorted(mon.glob("aoi/source/WFS_*/Smithsonian_VOTW_Holocene_Eruptions.csv"))
    rows = []

    def date(y, m, d):
        if not y:
            return ""
        y, m, d = int(float(y)), int(float(m or 0)), int(float(d or 0))
        return f"{y:04d}" + (f"-{m:02d}" if m > 0 else "") + (f"-{d:02d}" if m > 0 and d > 0 else "")

    # The second table of the same download says which eruptions were continuing at that time.
    continuing = set()
    for f in sorted(mon.glob("aoi/source/WFS_*/E3WebApp_Eruptions1960.csv"))[-1:]:
        for r in read_csv(f):
            if r.get("ContinuingEruption") == "True":
                continuing.add((r["VolcanoNumber"], r["StartDate"]))
    if files:
        for r in read_csv(files[-1]):
            vid = by_gvp.get(r["Volcano_Number"].split(".")[0])
            if not vid or not r["StartDateYear"]:
                continue
            last = float(r["EndDateYear"] or r["StartDateYear"])
            if last < first_year:
                continue
            start = date(r["StartDateYear"], r["StartDateMonth"], r["StartDateDay"])
            rows.append(dict(
                volcano_id=vid, source="GVP", kind=r["Activity_Type"], start=start,
                end=date(r["EndDateYear"], r["EndDateMonth"], r["EndDateDay"]),
                continuing="yes" if (r["Volcano_Number"].split(".")[0], start.replace("-", "")) in continuing else "",
                area=r["ActivityArea"], note=""))
    ev = mon / "config/events.toml"
    if ev.exists():
        import tomllib
        for e in tomllib.loads(ev.read_text(encoding="utf-8")).get("event", []):
            if e["target_id"] in volcanoes:
                rows.append(dict(volcano_id=e["target_id"], source="monitor", kind="Event period",
                                 start=e["start"], end=e["end"], continuing="", area="", note=e.get("note", "")))
    rows.sort(key=lambda r: (r["volcano_id"], r["start"]))
    return rows


def exact_known_refs(episodes: list[dict], periods: list[dict]) -> int:
    """Write the eruption an episode was matched to with the dates the catalogue has.

    The monitor reads the catalogue with every day cut at 28 (so that any month holds it) and
    prints a missing cell as "(nan)"; its reference to an eruption of 2023-01-31 reads 2023-01-28.
    """
    by = defaultdict(list)
    for p in periods:
        if p["source"] == "GVP":
            by[p["volcano_id"]].append(p)
    day = lambda d: datetime.strptime(d, "%Y-%m-%d").toordinal()  # noqa: E731
    changed = 0
    for e in episodes:
        ref = (e["known_ref"] or "").replace(" (nan)", "").replace("events.toml ", "Own event list ")
        m = re.match(r"GVP (Confirmed Eruption|Uncertain Eruption) (\d{4}-\d\d-\d\d)\.\.(\S+)(.*)", ref)
        if m:
            kind, start, _, rest = m.groups()
            for p in by.get(e["volcano_id"], []):
                full = len(p["start"]) == 10
                if p["kind"] == kind and (abs(day(p["start"]) - day(start)) <= 3 if full else start.startswith(p["start"])):
                    end = p["end"] or ("continuing" if p["continuing"] else "end not given")
                    ref = f"GVP {kind} {p['start']}..{end}{rest}"
                    break
        if ref != e["known_ref"]:
            e["known_ref"] = ref
            changed += 1
    return changed


JCG_URL = "https://www1.kaiho.mlit.go.jp/kaiikiDB/"
JCG_WINDOW = 14     # days either side of an episode within which an observation counts as "at the time"
JCG_PHENOMENA = {"dw": "discoloured water", "fl": "floating matter", "steam": "steam", "plume": "plume",
                 "eruption": "eruption", "island": "new island", "bubbles": "bubbles", "thermal": "thermal anomaly",
                 "other": "other activity"}


def day_span(date: str) -> tuple[int, int] | None:
    """First and last day (ordinal) of a date that may be a day, a month, a year or a range a/b."""
    lo, _, hi = date.partition("/")

    def edge(d: str, last: bool) -> int:
        p = [int(x) for x in d.split("-")]
        y = p[0]
        m = p[1] if len(p) > 1 else (12 if last else 1)
        dd = p[2] if len(p) > 2 else (monthrange(y, m)[1] if last else 1)
        return datetime(y, m, dd).toordinal()
    try:
        return edge(lo, False), edge(hi or lo, True)
    except (ValueError, IndexError):
        return None


def jcg_observations(volcanoes: dict) -> list[dict]:
    """Observations of the Japan Coast Guard's database of submarine volcanoes, as curated."""
    path = CURATION / "jcg_observations.csv"
    if not path.exists():
        return []
    rows = []
    for r in read_csv(path):
        if r["volcano_id"] in volcanoes and day_span(r["date"]):
            rows.append(dict(r, url=JCG_URL + r["jcg_page"]))
    rows.sort(key=lambda r: (r["volcano_id"], r["date"], r["site_ja"]))
    return rows


def jcg_near(e: dict, rows: list[dict], window: int = JCG_WINDOW):
    """The observations at the volcano within `window` days of an episode, each with whether its site lies
    in the zone of the episode. A low-resolution zone (30 km) holds every site of its volcano. An
    observation dated to more than a month says nothing about a day and is left out."""
    s = datetime.strptime(e["start"][:10], "%Y-%m-%d").toordinal() - window
    t = datetime.strptime(e["end"][:10], "%Y-%m-%d").toordinal() + window
    zone = site_of(e["zone_id"])
    for r in rows:
        span = day_span(r["date"])
        if span and span[1] - span[0] <= 31 and span[0] <= t and span[1] >= s:
            yield r, e["tier"] == "lowres" or zone in r.get("zones", "").split()


def jcg_split(e: dict, rows: list[dict], window: int = JCG_WINDOW) -> tuple[list, list, list]:
    """Of the observations near an episode: activity in its zone, activity elsewhere at the volcano,
    visits to its zone that found nothing."""
    here, away, quiet = [], [], []
    for r, inside in jcg_near(e, rows, window):
        if r["category"] == "anomaly":
            (here if inside else away).append(r)
        elif r["category"] == "none" and inside:
            quiet.append(r)
    return here, away, quiet


def jcg_prior(episodes: list[dict], rows: list[dict]) -> int:
    """Say in prior_reports what the Coast Guard's database has within JCG_WINDOW days of each episode.

    The text is this database's digest of the source: it names the pages and says that it was edited.
    It says "reported", not "activity": the source records what was seen and does not always take it
    for volcanic."""
    by = defaultdict(list)
    for r in rows:
        by[r["volcano_id"]].append(r)

    def item(r):
        what = ", ".join(JCG_PHENOMENA.get(p, p) for p in r["phenomena"].split("+") if p) or "a phenomenon"
        return f"{r['date']} ({what} at {r['site_en'] or r['site_ja']})"

    def some(items, more):
        items = list(dict.fromkeys(items))
        return ", ".join(items[:6]) + (f" and {len(items) - 6} more {more}" if len(items) > 6 else "")

    def names(rs):
        return " and ".join(sorted({r["site_en"] or r["site_ja"] for r in rs}))
    n = 0
    for e in episodes:
        mine = by.get(e["volcano_id"])
        if not mine:
            continue
        here, away, quiet = jcg_split(e, mine)
        zone = site_of(e["zone_id"])
        tables = [r for r in mine if e["tier"] == "lowres" or zone in r.get("zones", "").split()]
        parts = []
        if here:
            parts.append("reported on " + some([item(r) for r in here], "records"))
            other = {r["date"] for r in quiet} - {r["date"] for r in here}
            if other:
                parts.append(f"nothing unusual on {len(other)} other day(s)")
        elif quiet:
            parts.append("nothing unusual reported on " + some([r["date"] for r in quiet], "days"))
        elif tables:
            days = sorted(r["date"][:10] for r in tables)
            parts.append(f"no record for this zone within {JCG_WINDOW} days of the episode "
                         f"(the records of {names(tables)} used here run from {days[0]} to {days[-1]})")
        else:
            parts.append("the source has no table for a feature in this zone")
        if away:
            parts.append(f"outside this zone, {len(away)} record(s) of something seen at {names(away)}")
        pages = " and ".join(dict.fromkeys(r.get("url", "") for r in mine))
        read = max(r.get("retrieved", "") for r in mine)
        text = (f"Japan Coast Guard, database of submarine volcanoes ({pages}; used on {read}; "
                "digest made and edited by this database): " + "; ".join(parts))
        e["prior_reports"] = f"{e['prior_reports']}; {text}" if e["prior_reports"] else text
        n += 1
    return n


def lowres_days(mon: Path, volcanoes: dict):
    out = defaultdict(list)
    have = set()
    con = ro(mon / "data/wide_survey/wide.sqlite")
    for wid, date, n, cls, level, dw, bright, dw2 in con.execute(
            "select wide_id, date, n_passes, best_class, level, dw_masked_km2, bright_masked_km2, dw_two_pass_km2 "
            "from zone_days where best_class in ('A','B') order by wide_id, date"):
        vid = wid[2:]
        if vid in volcanoes:
            out[vid].append(dict(date=date, src="olci", n_passes=n, cls=cls, level=level, dw_km2=num(dw, 2),
                                 bright_km2=num(bright, 2), dw_two_pass_km2=num(dw2, 2)))
            have.add((vid, date))
    con.close()
    # The monitor's own low-resolution tier (VIIRS) fills the days the survey has no row for.
    mw = mon / "data/wide/wide.sqlite"
    if mw.exists():
        con = ro(mw)
        for wid, date, n, cls, level, dw, bright, dw2 in con.execute(
                "select wide_id, date, n_passes, best_class, level, dw_masked_km2, bright_masked_km2, dw_two_pass_km2 "
                "from zone_days where best_class in ('A','B') order by wide_id, date"):
            vid = wid[2:]
            if vid in volcanoes and (vid, date) not in have:
                out[vid].append(dict(date=date, src="viirs", n_passes=n, cls=cls, level=level, dw_km2=num(dw, 2),
                                     bright_km2=num(bright, 2), dw_two_pass_km2=num(dw2, 2)))
        con.close()
    for rows in out.values():
        rows.sort(key=lambda r: r["date"])
    return out


# ----------------------------------------------------------------------------- main

EPISODE_COLUMNS = [
    "episode_id", "volcano_id", "zone_id", "tier", "source", "start", "end", "n_detect", "n_seen", "n_l3",
    "phenomena", "max_dw_km2", "max_fl_km2", "max_nl_km2", "colour", "median_dist_km", "sensors", "peak",
    "class", "review_status", "reviewed_at", "basis", "cause", "interest", "known_ref", "prior_reports", "image",
    "note_en", "note_ja", "owner_en", "owner_ja", "curation_en", "curation_ja"]
PASS_COLUMNS = ["zone_id", "time", "sat", "cls", "clear", "level", "reasons", "dw_km2", "colour", "dist_km",
                "bearing", "fl_km2", "nl_km2", "th_px", "ap_km2", "episode_id", "img"]
LOWRES_COLUMNS = ["date", "src", "n_passes", "cls", "level", "dw_km2", "bright_km2", "dw_two_pass_km2"]
VOLCANO_COLUMNS = [
    "volcano_id", "gvp_number", "name", "name_ja", "country", "lat", "lon", "depth_class", "coverage", "tiers",
    "baseline_class", "n_zones", "first_pass", "last_pass", "n_passes", "n_usable", "lowres_days",
    "n_known", "n_likely", "n_possible", "n_recurrent", "n_airborne", "n_undetermined", "n_nonvolcanic",
    "n_unreviewed", "n_human_reviewed", "top_class", "last_activity", "summary_en", "summary_ja"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    local = local_settings()
    ap.add_argument("--monitor", default=local.get("monitor"), required="monitor" not in local,
                    help="checkout of the monitoring system (or `monitor` in local.toml)")
    ap.add_argument("--work", default=local.get("work", str(ROOT / "build")),
                    help="folder for lists and the rebuilt episode table (or `work` in local.toml)")
    ap.add_argument("--no-refresh", action="store_true", help="use <work>/monitor_review as it is")
    args = ap.parse_args()
    mon, work = Path(args.monitor), Path(args.work)
    cur = load_curation()

    volcanoes, zone_rows, zone_volcano = load_targets(mon, cur)
    print(f"{len(volcanoes)} volcanoes, {len(zone_rows)} zones")

    passes = load_passes(mon / "data/retro2/state.sqlite", "hindcast2", f"datetime < '{CUT}'", zone_volcano)
    for vid, rows in load_passes(mon / "data/state.sqlite", "monitor", f"datetime >= '{CUT}'", zone_volcano).items():
        passes[vid].extend(rows)

    episodes = hindcast_episodes(mon, zone_volcano)
    n_h = len(episodes)
    episodes += monitor_episodes(mon, work, zone_volcano, refresh=not args.no_refresh)
    n_m = len(episodes) - n_h
    low = lowres_episodes(mon, volcanoes)
    episodes += low
    classify(episodes, volcanoes, cur)
    periods = known_periods(mon, volcanoes)
    jcg = jcg_observations(volcanoes)
    n_jcg = jcg_prior(episodes, jcg)
    if jcg:
        print(f"Japan Coast Guard: {len(jcg)} observations at {len({r['volcano_id'] for r in jcg})} volcanoes, "
              f"{n_jcg} episodes compared")
    n_ref = exact_known_refs(episodes, periods)
    print(f"episodes: hindcast {n_h}, monitor {n_m}, low resolution {len(low)}; {n_ref} catalogue references rewritten")

    days = lowres_days(mon, volcanoes)
    for e in episodes:
        if e["tier"] == "lowres":
            e["n_seen"] = sum(1 for d in days.get(e["volcano_id"], []) if e["start"] <= d["date"] <= e["end"])

    # Notes: English from the curated translations, keyed by the Japanese text.
    missing = Counter()
    for e in episodes:
        e["class"] = e["cls"]
        for col in ("note_ja", "owner_ja", "curation_ja", "curation_en"):
            for private, public in PUBLIC_COPIES.items():
                if private in (e.get(col) or ""):
                    e[col] = e[col].replace(private, public)
        for src, dst in (("note_ja", "note_en"), ("owner_ja", "owner_en")):
            text = e.get(src, "")
            e[dst] = cur["notes_en"].get(note_key(text), "") if text else ""
            if dst == "owner_en" and not e[dst] and e.get("_owner_en"):
                e[dst] = e["_owner_en"]          # a review without a comment needs no translator
            if text and not e[dst] and e["cls"] != "nonvolcanic":
                missing[src] += 1
        e["image"] = f"wide/sheet/{e['episode_id']}.jpg" if e.get("_sheet") else ""
    if missing:
        print(f"  notes without an English text (not dismissed): {dict(missing)}")

    # Passes carry the id of their episode.
    obs_episode = {o: e["episode_id"] for e in episodes for o in e.get("_obs", [])}
    n_pass = n_img = 0
    lists = defaultdict(list)
    stats = {}
    for vid in volcanoes:
        rows = sorted(passes.get(vid, []), key=lambda r: (r["time"], r["zone_id"]))
        for r in rows:
            r["episode_id"] = obs_episode.get(r["obs_id"], "")
            if r["img"]:
                lists[r["store"]].append(r["ql"][len("quicklooks/"):])
        usable = [r for r in rows if r["cls"] in ("A", "B")]
        stats[vid] = dict(first_pass=rows[0]["time"][:10] if rows else "", last_pass=rows[-1]["time"][:10] if rows else "",
                          n_passes=len(rows), n_usable=len(usable))
        n_pass += len(rows)
        n_img += sum(r["img"] for r in rows)
        path = DB / "passes" / f"{vid}.csv"
        if rows:
            write_csv(path, PASS_COLUMNS, rows)
        elif path.exists():
            path.unlink()
    stray = sorted(set(obs_episode) - {r["obs_id"] for rows in passes.values() for r in rows})
    if stray:
        print(f"  warning: {len(stray)} alert passes of the episode lists are not in the pass tables, e.g. {stray[:3]}")
    print(f"passes: {n_pass} ({n_img} with a quicklook)")

    n_days = 0
    for vid in volcanoes:
        rows = days.get(vid, [])
        stats[vid]["lowres_days"] = len(rows)
        n_days += len(rows)
        if rows:
            write_csv(DB / "lowres" / f"{vid}.csv", LOWRES_COLUMNS, rows)
    print(f"low-resolution days with the sea visible: {n_days}")

    episodes.sort(key=lambda e: (e["volcano_id"], e["start"], e["tier"], e["episode_id"]))
    write_csv(DB / "episodes.csv", EPISODE_COLUMNS, episodes)
    by_volcano = defaultdict(list)
    for e in episodes:
        by_volcano[e["volcano_id"]].append(e)

    write_csv(DB / "known_periods.csv", ["volcano_id", "source", "kind", "start", "end", "continuing", "area", "note"], periods)

    vol_rows = []
    for vid, v in volcanoes.items():
        eps = by_volcano.get(vid, [])
        counts = Counter(e["cls"] for e in eps)
        active = [e for e in eps if e["cls"] in ("known", "likely", "possible")]
        top = min((e["cls"] for e in eps), key=lambda c: RANK[c], default="")
        s = cur["summaries"].get(vid, {})
        v.update(stats[vid], top_class=top, last_activity=max((e["end"] for e in active), default=""),
                 n_human_reviewed=sum(1 for e in eps if e["review_status"] == "human-reviewed"),
                 summary_en=s.get("summary_en", ""), summary_ja=s.get("summary_ja", ""),
                 **{f"n_{c}": counts.get(c, 0) for c in CLASSES})
        vol_rows.append(v)
    vol_rows.sort(key=lambda v: v["name"].lower())
    write_csv(DB / "volcanoes.csv", VOLCANO_COLUMNS, vol_rows)
    write_csv(DB / "zones.csv", ["zone_id", "volcano_id", "tier", "name", "kind", "lat", "lon", "radius_km", "sensors"],
              zone_rows)

    # Records kept by the monitor as markdown tables.
    ring = md_table(mon / "docs/RING_WAVES.md", "Pass (UTC)")
    for r in ring:
        for k in r:
            r[k] = re.sub(r"\s*\(`[^`]*`\)", "", r[k]).replace("`", "")
    write_csv(DB / "records/ring_waves.csv",
              ["pass_utc", "zone_id", "volcano", "centre", "reach", "spacing", "sea", "with_it", "noted"],
              [dict(zip(["pass_utc", "zone_id", "volcano", "centre", "reach", "spacing", "sea", "with_it", "noted"],
                        r.values())) for r in ring])
    bands = md_table(mon / "docs/AIRBORNE_BANDS.md", "Day")
    write_csv(DB / "records/airborne_bands.csv",
              ["day", "utc", "zone_id", "sensor", "area_km2", "length_km", "from_jadid", "level", "store"],
              [dict(zip(["day", "utc", "zone_id", "sensor", "area_km2", "length_km", "from_jadid", "level", "store"],
                        r.values())) for r in bands])
    write_csv(DB / "jcg_observations.csv",
              ["volcano_id", "site_ja", "site_en", "match", "zones", "date", "time", "observer", "category", "phenomena",
               "text_ja", "summary_en", "url", "retrieved"], jcg)
    figs = [dict(volcano_id=f["volcano_id"], file="fig/" + f["file"].lstrip("/"), caption_en=f.get("caption_en", ""),
                 caption_ja=f.get("caption_ja", "")) for f in cur["figures"]
            if f["volcano_id"] in volcanoes and f["file"].lstrip("/") not in WITHHELD_FIGURES]
    for d in sorted((mon / "data/wide_refine/review/digest").glob("W-*.jpg")):
        vid = d.stem[2:]
        if vid in volcanoes and any(e["tier"] == "lowres" and e.get("_sheet") for e in by_volcano.get(vid, [])):
            figs.append(dict(volcano_id=vid, file=f"wide/digest/{d.name}", caption_en=DIGEST_EN, caption_ja=DIGEST_JA))
    write_csv(DB / "figures.csv", ["volcano_id", "file", "caption_en", "caption_ja"], figs)

    # What the map page reads in one request.
    index = dict(
        classes=CLASSES,
        volcanoes=[dict(
            id=v["volcano_id"], name=v["name"], name_ja=v["name_ja"], country=v["country"],
            lat=float(v["lat"]), lon=float(v["lon"]), gvp=v["gvp_number"], tiers=v["tiers"],
            baseline=v["baseline_class"], depth=v["depth_class"], top=v["top_class"], last=v["last_activity"],
            usable=v["n_usable"], lowres_days=v["lowres_days"],
            counts=[v[f"n_{c}"] for c in CLASSES],
            episodes=[[e["start"], e["end"], RANK[e["cls"]], 0 if e["tier"] == "highres" else 1, e["phenomena"],
                       1 if e["review_status"] == "human-reviewed" else 0]
                      for e in by_volcano.get(v["volcano_id"], []) if e["cls"] != "nonvolcanic"],
        ) for v in vol_rows])
    write_text(DB / "index.json", json.dumps(index, ensure_ascii=False, separators=(",", ":")))

    head = subprocess.run(["git", "-C", str(mon), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    last_pass = max((s["last_pass"] for s in stats.values() if s["last_pass"]), default="")
    meta = dict(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), monitor_commit=head.stdout.strip(),
        image_base=IMAGE_BASE, cut=CUT, first_pass=min((s["first_pass"] for s in stats.values() if s["first_pass"]), default=""),
        last_pass=last_pass, volcanoes=len(vol_rows), zones=len(zone_rows), passes=n_pass, quicklooks=n_img,
        lowres_days=n_days, episodes=len(episodes),
        episodes_by_class={c: sum(1 for e in episodes if e["cls"] == c) for c in CLASSES},
        episodes_by_source=dict(Counter(e["source"] for e in episodes)),
        episodes_by_review_status=dict(Counter(e["review_status"] for e in episodes)),
        ring_wave_records=len(ring), airborne_band_records=len(bands), jcg_observations=len(jcg))
    write_text(DB / "meta.json", json.dumps(meta, indent=1))

    (work / "lists").mkdir(parents=True, exist_ok=True)
    for store, name in (("hindcast2", "ql_retro2.txt"), ("monitor", "ql_monitor.txt")):
        write_text(work / "lists" / name, "\n".join(sorted(lists[store])) + "\n")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
