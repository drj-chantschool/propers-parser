#!/usr/bin/env python
"""load_toc.py — load a book's reviewed toc.json into book_toc (any book).

    python tools/load_toc.py --book LIBER_HYMNARIUS lhymn/lhymn_toc.json [--dry-run] [--prune]

toc.json is the standard book TOC file (lhymn/lhymn_toc.json; tools/split_by_outline.py --toc-json):
    {"source": "...", "entries": [[level, title, printed_page(, pdf_page)(, y)], ...]}
Entries are numbered idx = 0, 1, 2 … in file order. Rows are upserted by (book, idx); a changed
heading at the same idx is updated and printed. --prune deletes this book's rows with an idx past
the end of the file (needed after removing headings). Every printed page must exist in `books`
(FK fk_bt_book_page), so seed the page images first (book-intake phase 1).

Never point this at book='GRADUALE' with a file: its 156 rows came from the OCR pipeline (with y
positions no toc.json carries), and their idx order is what the GR spans were cut from.
"""
import argparse
import json
import os
import sys

from sqlalchemy import text

from _db import PP_ROOT, engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("toc_json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true")
    a = ap.parse_args()
    if a.book == "GRADUALE":
        sys.exit("refusing: GRADUALE's book_toc rows are maintained by the OCR pipeline (see docstring)")
    path = a.toc_json if os.path.isabs(a.toc_json) else os.path.join(PP_ROOT, a.toc_json)
    entries = json.load(open(path, encoding="utf-8"))["entries"]
    rows = []
    for i, e in enumerate(entries):
        level, title, page = e[0], e[1], str(e[2])
        y = e[4] if len(e) > 4 else None
        rows.append({"book": a.book, "idx": i, "level": level, "text": title, "printed_page": page, "y": y})

    eng = engine(rw=not a.dry_run)
    with (eng.connect() if a.dry_run else eng.begin()) as c:
        pages = {p for (p,) in c.execute(text("SELECT printed_page_num FROM books WHERE book=:b"), {"b": a.book})}
        missing = [r for r in rows if r["printed_page"] not in pages]
        if missing:
            sys.exit("pages not in books: " + ", ".join(f"idx {r['idx']} {r['text']!r} p{r['printed_page']}"
                                                       for r in missing[:10]))
        have = {r.idx: r for r in c.execute(text("SELECT idx, level, text, printed_page, y FROM book_toc "
                                                 "WHERE book=:b"), {"b": a.book})}
        ins = upd = same = 0
        for r in rows:
            old = have.get(r["idx"])
            if old and (old.level, old.text, old.printed_page, old.y) == (r["level"], r["text"], r["printed_page"], r["y"]):
                same += 1
                continue
            if old:
                upd += 1
                print(f"~ idx {r['idx']}: {old.level} {old.text!r} p{old.printed_page} → {r['level']} {r['text']!r} p{r['printed_page']}")
            else:
                ins += 1
            if not a.dry_run:
                c.execute(text("INSERT INTO book_toc (book, idx, level, text, printed_page, y) "
                               "VALUES (:book, :idx, :level, :text, :printed_page, :y) AS new "
                               "ON DUPLICATE KEY UPDATE level=new.level, text=new.text, "
                               "printed_page=new.printed_page, y=new.y"), r)
        extra = [i for i in have if i >= len(rows)]
        if extra and a.prune and not a.dry_run:
            c.execute(text("DELETE FROM book_toc WHERE book=:b AND idx >= :n"), {"b": a.book, "n": len(rows)})
    print(json.dumps({"book": a.book, "dry_run": a.dry_run, "insert": ins, "update": upd, "unchanged": same,
                      "beyond_file": len(extra), "pruned": bool(extra and a.prune and not a.dry_run)}))


if __name__ == "__main__":
    main()
