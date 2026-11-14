"""Keep the English translations of the review notes (curation/notes_en.csv).

    python tools/notes.py pending [--all] [--out FILE]   notes of db/episodes.csv without English text
    python tools/notes.py merge FILE [FILE ...]          add translated rows (columns: key, note_en)

Notes are written in Japanese by the reviewers. A translation is stored once per text, keyed by
the first twelve hex digits of the SHA-1 of the Japanese text, so that build_db.py finds it again
whatever episode carries the note. `pending` lists the notes of episodes that are not dismissed
(with --all, every note) that have no translation yet, as a CSV to hand to a translator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "curation" / "notes_en.csv"


def key(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_store() -> dict[str, dict]:
    return {r["key"]: r for r in read(STORE)} if STORE.exists() else {}


def save_store(store: dict[str, dict]) -> None:
    STORE.parent.mkdir(exist_ok=True)
    with open(STORE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["key", "note_ja", "note_en"])
        for k in sorted(store):
            w.writerow([k, store[k].get("note_ja", ""), store[k].get("note_en", "")])


def notes_in_db(all_notes: bool) -> dict[str, dict]:
    volcano = {r["volcano_id"]: r["name"] for r in read(ROOT / "db" / "volcanoes.csv")}
    out = {}
    for e in read(ROOT / "db" / "episodes.csv"):
        if e["class"] == "nonvolcanic" and not all_notes:
            continue
        for col in ("note_ja", "owner_ja"):
            text = e[col].strip()
            if text:
                out.setdefault(key(text), dict(key=key(text), note_ja=text,
                                               context=f"{volcano[e['volcano_id']]} {e['start']}..{e['end']} ({e['tier']})"))
    return out


def pending(args) -> None:
    store = load_store()
    rows = [r for k, r in notes_in_db(args.all).items() if not store.get(k, {}).get("note_en")]
    out = open(args.out, "w", encoding="utf-8-sig", newline="") if args.out else sys.stdout
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["key", "context", "note_ja"])
    for r in rows:
        w.writerow([r["key"], r["context"], r["note_ja"]])
    print(f"{len(rows)} notes without an English text", file=sys.stderr)


def merge(args) -> None:
    store = load_store()
    known = notes_in_db(True)
    added = 0
    for path in args.files:
        for r in read(Path(path)):
            text = (r.get("note_en") or "").strip().replace("\r", " ").replace("\n", " ")
            if not text:
                continue
            k = r["key"]
            ja = r.get("note_ja") or known.get(k, {}).get("note_ja") or store.get(k, {}).get("note_ja", "")
            if ja and key(ja) != k:
                raise SystemExit(f"{path}: key {k} does not match its Japanese text")
            store[k] = dict(key=k, note_ja=ja, note_en=text)
            added += 1
    save_store(store)
    print(f"{added} rows merged; {len(store)} translations in {STORE.name}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pending")
    p.add_argument("--all", action="store_true", help="include the notes of dismissed episodes")
    p.add_argument("--out")
    p.set_defaults(fn=pending)
    m = sub.add_parser("merge")
    m.add_argument("files", nargs="+")
    m.set_defaults(fn=merge)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
