#!/usr/bin/env python
"""seed_books.py — seed `books` with one book's page images (dpi=200 PNG blobs), any book.

`books(book, printed_page_num)` is the FK target of chant_indices, graduale_toc and
lit_part_sources, and `bbox` values live in its dpi=200 pixel space — so the DPI is fixed
by convention and recorded in `notes`. `book` must already exist in `p_sources`.

The printed page number for each PDF page comes from, in order of preference:
  --labels       the PDF's own page labels (stamp them first; see tools/chunk_pdf.py and
                 graduale/renumber_pdfs.py — printed labels are the project convention)
  --mapping F    a JSON file {pdf_page: printed} or {"mapping": {...}} (pdf_page_mapper.py output)
  --offset N     printed = pdf_page - N; pages 1..N take their PDF label, else are skipped
  --identity     printed = pdf_page (only for a book whose PDF has no front matter)

    python tools/seed_books.py --book LIBER_HYMNARIUS --pdf lhymn/Liber_Hymnarius_1983_paged.pdf --labels --dry-run
    python tools/seed_books.py --book X --pdf x/x.pdf --offset 13 --pages 1-50

Upserts one row at a time (mysql-connector's executemany rewrite can't bind
ON DUPLICATE KEY UPDATE ... VALUES()), so re-runs are idempotent.
"""
import argparse
import json
import os

import fitz
from sqlalchemy import text

from _db import PP_ROOT, engine

UPSERT = text("INSERT INTO books (book, printed_page_num, image_blob, notes) VALUES (:b, :p, :img, :n) "
              "ON DUPLICATE KEY UPDATE image_blob = VALUES(image_blob), notes = VALUES(notes)")


def resolve(path):
    return path if os.path.isabs(path) else os.path.join(PP_ROOT, path)


def printed_numbers(doc, a):
    n = doc.page_count
    if a.mapping:
        raw = json.load(open(resolve(a.mapping), encoding="utf-8"))
        raw = raw.get("mapping", raw)
        return {i: (str(raw[str(i)]) if raw.get(str(i)) is not None else None) for i in range(1, n + 1)}
    if a.identity:
        return {i: str(i) for i in range(1, n + 1)}
    if a.offset is not None:
        return {i: (str(i - a.offset) if i > a.offset else (doc[i - 1].get_label() or None))
                for i in range(1, n + 1)}
    return {i: (doc[i - 1].get_label() or None) for i in range(1, n + 1)}   # --labels (default)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, help="p_sources.source_code, e.g. LIBER_HYMNARIUS")
    ap.add_argument("--pdf", required=True, help="path (absolute or relative to propers-parser/)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--labels", action="store_true", help="use PDF page labels (default)")
    g.add_argument("--mapping")
    g.add_argument("--offset", type=int)
    g.add_argument("--identity", action="store_true")
    ap.add_argument("--pages", help="inclusive PDF page range A-B (default all)")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    pdf = resolve(a.pdf)
    doc = fitz.open(pdf)
    nums = printed_numbers(doc, a)
    lo, hi = (map(int, a.pages.split("-"))) if a.pages else (1, doc.page_count)
    dupes = [p for p in set(nums.values()) if p and list(nums.values()).count(p) > 1]
    if dupes:
        raise SystemExit(f"printed page numbers repeat ({sorted(dupes)[:10]}…) — fix the labels/mapping first")

    eng = None if a.dry_run else engine(rw=True)
    if eng:
        with eng.connect() as c:
            if not c.execute(text("SELECT 1 FROM p_sources WHERE source_code=:b"), {"b": a.book}).first():
                raise SystemExit(f"{a.book} is not in p_sources — register the book first (book-intake phase 0)")
    seeded = skipped = 0
    for i in range(lo, hi + 1):
        p = nums.get(i)
        if not p:
            skipped += 1
            continue
        png = doc[i - 1].get_pixmap(dpi=a.dpi).tobytes("png")
        note = f"pymupdf dpi={a.dpi}; {os.path.basename(pdf)} pdf_page={i}"
        if a.dry_run:
            print(f"pdf {i:>4} -> printed {p:>6}  {len(png) // 1024} KB")
        else:
            with eng.begin() as c:
                c.execute(UPSERT, dict(b=a.book, p=p, img=png, n=note))
        seeded += 1
        if not a.dry_run and seeded % 25 == 0:
            print(f"seeded {seeded} (pdf {i})", flush=True)
    print(f"{'would seed' if a.dry_run else 'seeded'} {seeded} pages, skipped {skipped} with no printed number")


if __name__ == "__main__":
    main()
