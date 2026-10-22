#!/usr/bin/env python
"""load_index.py — upsert a book's printed chant index (Index alphabeticus) into chant_indices.

NON-DESTRUCTIVE by design. The old upload_gr_index.py did DELETE + INSERT and wiped every curated
gregobase link; this never deletes and never overwrites chant_uuid / match_status.

Input: one JSON file per index page, produced by an index-page-parser agent (see
.claude/agents/index-page-parser.md), or a directory of them:
    {"book": "LIBER_HYMNARIUS", "index_page": "612",
     "rows": [{"id": 1, "section_type": "hymnus", "mode": 4, "incipit": "A Patre Unigenite",
               "page": "43", "author_origin": null, "notes": null}, ...],
     "questions": []}
`id` is the entry's ordinal in the whole index (stable across pages); (book, id, page) is unique.
A non-1..8 mode (D, E, 4*) is mode null + notes 'printed mode: x'.
Optional per row: `day_code` / `hour_code` / `place_code` (indices keyed by liturgical sigla, OCO);
`page` null (no page in this book, e.g. OCO's hymns, or a broken index link — say why in notes);
`chant_uuid` + `match_status` when the BOOK ITSELF links the chant (OCO's gregobase hyperlinks):
written only into a row whose chant_uuid is still NULL, so curated links are never overwritten.

    python tools/load_index.py --book X FILE_OR_DIR [--dry-run]

Refuses a file with open `questions`. Validates every target page exists in `books` (FK).
"""
import argparse
import glob
import json
import os
import sys

from sqlalchemy import text

from _db import PP_ROOT, engine
from index_util import SECTION_TO_OFFICE_PART

FIELDS = ["section_type", "mode", "incipit", "author_origin", "notes", "day_code", "hour_code", "place_code"]


def files(path):
    path = path if os.path.isabs(path) else os.path.join(PP_ROOT, path)
    return sorted(glob.glob(os.path.join(path, "*.json"))) if os.path.isdir(path) else [path]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("path")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows, errors = [], []
    for f in files(a.path):
        d = json.load(open(f, encoding="utf-8"))
        if d.get("book") != a.book:
            errors.append(f"{f}: book {d.get('book')!r} != {a.book}")
        if d.get("questions"):
            errors.append(f"{f}: has open questions — raise them in intake_queue, don't load")
        for r in d.get("rows", []):
            r["_file"] = os.path.basename(f)
            if r.get("section_type") not in SECTION_TO_OFFICE_PART:
                errors.append(f"{f}: id {r.get('id')}: unknown section_type {r.get('section_type')!r}")
            if r.get("mode") is not None and r["mode"] not in range(1, 9):
                errors.append(f"{f}: id {r.get('id')}: mode {r['mode']!r} — use null + notes 'printed mode: x'")
            rows.append(r)
    eng = engine(rw=not a.dry_run)
    with eng.connect() as c:
        have_pages = {p for (p,) in c.execute(text("SELECT printed_page_num FROM books WHERE book=:b"), {"b": a.book})}
        for r in rows:
            u = r.get("chant_uuid")
            if u is not None:
                if not u.startswith("gregobase:") or r.get("match_status") not in ("resolved", "resolved_with_difficulty"):
                    errors.append(f"{r['_file']}: id {r.get('id')}: chant_uuid {u!r} / match_status "
                                  f"{r.get('match_status')!r} — only book-supplied gregobase links")
                elif not c.execute(text("SELECT 1 FROM gregobase_chants WHERE id=:i"), {"i": int(u[10:])}).first():
                    errors.append(f"{r['_file']}: id {r.get('id')}: {u} not in gregobase_chants")
            if r.get("page") is None:
                continue
            if str(r.get("page")) not in have_pages:
                errors.append(f"{r['_file']}: id {r.get('id')}: page {r.get('page')!r} not in books — "
                              "check the index's page-number line alignment")
    if errors:
        print("\n".join(errors))
        sys.exit(1)

    ins = upd = same = 0
    with (eng.connect() if a.dry_run else eng.begin()) as c:
        for r in rows:
            key = {"b": a.book, "i": r["id"], "p": None if r.get("page") is None else str(r["page"])}
            old = c.execute(text("SELECT row_id, chant_uuid, " + ", ".join(FIELDS) + " FROM chant_indices "
                                 "WHERE book=:b AND id=:i AND page <=> :p"), key).first()
            new = {k: r.get(k) for k in FIELDS}
            link = {"chant_uuid": r["chant_uuid"], "match_status": r["match_status"]} if r.get("chant_uuid") else {}
            if old is None:
                ins += 1
                print(f"+ {r['id']:>4} p{key['p'] or '-':<5} {r['section_type']:<13} m{r.get('mode')}  {r['incipit']}"
                      + (f"  → {link['chant_uuid']}" if link else ""))
                if not a.dry_run:
                    cols = FIELDS + list(link)
                    c.execute(text("INSERT INTO chant_indices (book, id, page, " + ", ".join(cols) + ") "
                                   "VALUES (:b, :i, :p, " + ", ".join(f":{k}" for k in cols) + ")"),
                              {**key, **new, **link})
                continue
            diff = {k: v for k, v in new.items() if getattr(old, k) != v}
            if link and old.chant_uuid is None:
                diff.update(link)
            elif link and old.chant_uuid != link["chant_uuid"]:
                print(f"! row {old.row_id} id {r['id']}: kept {old.chant_uuid}; the book links {link['chant_uuid']}")
            if not diff:
                same += 1
                continue
            upd += 1
            print(f"~ row {old.row_id} id {r['id']}: " + ", ".join(f"{k}: {getattr(old, k, None)!r} → {v!r}" for k, v in diff.items()))
            if not a.dry_run:
                c.execute(text("UPDATE chant_indices SET " + ", ".join(f"{k}=:{k}" for k in diff) +
                               " WHERE row_id=:rid"), {**diff, "rid": old.row_id})
    print(json.dumps({"dry_run": a.dry_run, "insert": ins, "update": upd, "unchanged": same}))


if __name__ == "__main__":
    main()
