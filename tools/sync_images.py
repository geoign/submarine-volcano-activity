"""Copy the quicklooks of the usable passes to the image store (Cloudflare R2, gis.ikgm.net).

    python tools/sync_images.py [--monitor D:/SubMVolc_Monitor] [--work C:/tmp/submvolc_web]
                                [--remote cloudflare1:gis/submvolc] [--dry-run] [--extras]

build_db.py writes the lists of quicklooks that the pass tables point to into <work>/lists.
This tool hands them to rclone, which copies only what the store does not hold yet (it asks the
store for every listed file, so a run with nothing new costs one request per file; give --since
to look only at recent passes). Images are never deleted from the store.

    --since 2026-11-01   only passes on or after that day
    --extras             also the review sheets and digests of the low-resolution review and the
                         figures of the reports (rarely change)

Nothing here needs a key in this repository: rclone uses the remote configured on this PC.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CACHE = "Cache-Control: public, max-age=604800"
# Not published: figures that overlay bathymetry which is not yet public (see build_db.py).
WITHHELD = {"hindcast1/fig28_fonuafoou_10m_study.jpg"}


def rclone(args: list[str], dry: bool) -> int:
    cmd = ["rclone", *args, "--transfers", "32", "--checkers", "32", "--header-upload", CACHE,
           "--retries", "5", "--low-level-retries", "10", "--stats", "30s", "--stats-one-line", "-v"]
    if dry:
        cmd.append("--dry-run")
    print(" ".join(cmd[:6]), "...")
    return subprocess.run(cmd).returncode


def stage_extras(mon: Path, stage: Path) -> None:
    """Small files with names of their own: staged under one tree and copied as a whole."""
    for sub in ("wide/sheet", "wide/digest", "fig/hindcast1", "fig/hindcast2"):
        (stage / sub).mkdir(parents=True, exist_ok=True)
    for sheet in mon.glob("data/wide_refine/refine/*/sheet.jpg"):
        shutil.copy2(sheet, stage / "wide/sheet" / f"{sheet.parent.name}.jpg")
    for digest in mon.glob("data/wide_refine/review/digest/*.jpg"):
        shutil.copy2(digest, stage / "wide/digest" / digest.name)
    for tag, report in (("hindcast1", "hindcast-20261113"), ("hindcast2", "hindcast2-20261114")):
        for fig in (mon / "reports" / report / "fig").glob("*"):
            if fig.suffix.lower() in (".jpg", ".jpeg", ".png") and f"{tag}/{fig.name}" not in WITHHELD:
                shutil.copy2(fig, stage / "fig" / tag / fig.name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--monitor", default=os.environ.get("SUBMVOLC_MONITOR", "D:/SubMVolc_Monitor"))
    ap.add_argument("--work", default=os.environ.get("SUBMVOLC_WEB_WORK", "C:/tmp/submvolc_web"))
    ap.add_argument("--remote", default="cloudflare1:gis/submvolc")
    ap.add_argument("--since", help="only passes on or after this day (YYYY-MM-DD)")
    ap.add_argument("--extras", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    mon, work = Path(args.monitor), Path(args.work)
    status = 0
    for name, root in (("ql_monitor.txt", mon / "data/quicklooks"), ("ql_retro2.txt", mon / "data/retro2/quicklooks")):
        src = work / "lists" / name
        if not src.exists():
            raise SystemExit(f"{src} is missing: run tools/build_db.py first")
        lines = src.read_text(encoding="utf-8").split()
        if args.since:
            day = args.since.replace("-", "")
            lines = [p for p in lines if (m := re.search(r"_(\d{8})T\d{4}_", p)) and m.group(1) >= day]
        if not lines:
            print(f"{name}: nothing to send")
            continue
        part = work / "lists" / f"_send_{name}"
        part.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"{name}: {len(lines)} files")
        status |= rclone(["copy", str(root), f"{args.remote}/ql", "--files-from", str(part), "--no-traverse"], args.dry_run)
    if args.extras:
        stage = work / "stage"
        stage_extras(mon, stage)
        status |= rclone(["copy", str(stage), args.remote], args.dry_run)
    sys.exit(status)


if __name__ == "__main__":
    main()
