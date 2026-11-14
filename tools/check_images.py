"""Check that quicklooks named by the pass tables answer from the image store.

    python tools/check_images.py [N]

Draws N passes with an image at random from db/passes/ (default 20), builds the address of each
quicklook by the rule of docs/DATA.md, and asks the image store for its header. Exits with
status 1 when one does not answer with an image.
"""

from __future__ import annotations

import csv
import json
import random
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db"


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    meta = json.loads((DB / "meta.json").read_text(encoding="utf-8"))
    rng = random.Random()
    files = sorted((DB / "passes").glob("*.csv"))
    urls = []
    while len(urls) < n:
        with open(rng.choice(files), encoding="utf-8", newline="") as f:
            rows = [p for p in csv.DictReader(f) if p["img"] == "1"]
        if rows:
            p = rng.choice(rows)
            stamp = p["time"].replace("-", "").replace(":", "")
            urls.append(f"{meta['image_base']}/ql/{p['zone_id']}/{p['zone_id']}_{stamp}_{p['sat']}.jpg")
    bad = 0
    for url in urls:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "db-check"})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
                    bad += 1
                    print("FAIL", url, r.status, r.headers.get("Content-Type"))
        except Exception as exc:  # noqa: BLE001
            bad += 1
            print("FAIL", url, exc)
    print(f"images: {n - bad} of {n} sampled quicklooks answer")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
