#!/usr/bin/env python
"""
seed_books_gm.py — Seed the MySQL `books` table with the Gregorian Missal pages.

WHAT THIS DOES
--------------
Renders each page of the Gregorian Missal PDF to a PNG (via PyMuPDF/fitz at a
fixed DPI) and stores the PNG bytes as a blob in the `books` table, one row per
page.  The `printed_page_num` key is the 1-based PDF page index (as a string),
since no separate printed-page-to-PDF mapping exists for this book.  If a
mapping JSON is later produced (same format as graduale/page_mapping.json), pass
it with --mapping to override the default identity mapping.

Table layout (books, PK = book + printed_page_num):
    book             varchar(40)  NOT NULL   -- 'GREGORIAN_MISSAL'
    printed_page_num varchar(16)  NOT NULL   -- str(pdf_page) unless --mapping supplied
    image_path       varchar(512)            -- left NULL (blob stored instead)
    image_blob       longblob                -- PNG bytes of the rendered page
    notes            varchar(500)            -- render provenance
    created_at       timestamp               -- DB default

Rows are upserted (INSERT … ON DUPLICATE KEY UPDATE) so re-runs are idempotent.

HOW TO RUN
----------
    PY=C:\\Users\\johna\\liturgio\\.venv\\Scripts\\python.exe

    # Dry-run a single page:
    $PY propers-parser\\seed_books_gm.py --dry-run --pages 1-1

    # Seed pages 1..50:
    $PY propers-parser\\seed_books_gm.py --pages 1-50

    # Seed everything:
    $PY propers-parser\\seed_books_gm.py

    # Use an explicit page mapping JSON (same format as graduale/page_mapping.json):
    $PY propers-parser\\seed_books_gm.py --mapping path\\to\\gm_page_mapping.json

Options:
    --pages A-B     Inclusive 1-based PDF page range (default: all 1..718).
    --dry-run       Render and report sizes, but do NOT write to the database.
    --book NAME     Value for the `book` column (default: 'GREGORIAN_MISSAL').
    --dpi N         Render DPI (default: 200).
    --mapping PATH  Optional JSON mapping file {mapping: {str(pdf_page): printed_page}}.
                    When omitted, printed_page_num = str(pdf_page).

DB credentials come from the keyring entry ('liturgio-mysql', 'jcost').
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(_HERE, "GM", "gregorian-missal.pdf")

DEFAULT_BOOK = "GREGORIAN_MISSAL"
DEFAULT_DPI = 200
TOTAL_PAGES = 718
BATCH_SIZE = 50
OVERSIZE_WARN_BYTES = 15 * 1024 * 1024

KEYRING_SERVICE = "liturgio-mysql"
KEYRING_USER = "jcost"
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "liturgio"

UPSERT_SQL = (
    "INSERT INTO books "
    "(book, printed_page_num, image_path, image_blob, notes) "
    "VALUES (:book, :printed_page_num, "
    ":image_path, :image_blob, :notes) "
    "ON DUPLICATE KEY UPDATE "
    "image_blob=VALUES(image_blob), "
    "notes=VALUES(notes)"
)


def parse_pages(spec):
    """Parse an inclusive 'A-B' (or single 'A') 1-based range string."""
    if spec is None:
        return 1, TOTAL_PAGES
    spec = spec.strip()
    if "-" in spec:
        lo_s, hi_s = spec.split("-", 1)
        lo, hi = int(lo_s), int(hi_s)
    else:
        lo = hi = int(spec)
    if lo < 1 or hi > TOTAL_PAGES or lo > hi:
        raise ValueError(
            f"--pages {spec!r} out of range; must be within 1..{TOTAL_PAGES} and lo<=hi"
        )
    return lo, hi


def load_mapping(path):
    """Load the pdf-page -> printed-page mapping dict (keys are strings)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data["mapping"]


def make_engine():
    """Build a SQLAlchemy engine using the keyring-stored DB password."""
    import keyring
    from sqlalchemy import create_engine

    pw = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if not pw:
        raise RuntimeError(
            f"No password found in keyring for ({KEYRING_SERVICE!r}, {KEYRING_USER!r})"
        )
    url = (
        f"mysql+mysqlconnector://{KEYRING_USER}:{pw}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    return create_engine(url)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed the MySQL `books` table with Gregorian Missal page images."
    )
    parser.add_argument(
        "--pages",
        default=None,
        help="Inclusive 1-based PDF page range 'A-B' (default: all 1..718).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and report, but do NOT write to the database.",
    )
    parser.add_argument(
        "--book",
        default=DEFAULT_BOOK,
        help=f"Value for the `book` column (default: {DEFAULT_BOOK!r}).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help=f"Render DPI (default: {DEFAULT_DPI}).",
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help=(
            "Optional JSON mapping file with key 'mapping': {str(pdf_page): printed_page}. "
            "When omitted, printed_page_num = str(pdf_page)."
        ),
    )
    args = parser.parse_args(argv)

    lo, hi = parse_pages(args.pages)

    mapping = None
    if args.mapping:
        mapping = load_mapping(args.mapping)
        notes = f"pymupdf dpi={args.dpi}; gregorian-missal.pdf; mapping={os.path.basename(args.mapping)}"
    else:
        notes = f"pymupdf dpi={args.dpi}; gregorian-missal.pdf; printed_page_num=pdf_page"

    print(f"PDF:      {PDF_PATH}")
    print(f"Mapping:  {args.mapping or '(none — using pdf page as printed_page_num)'}")
    print(f"Book:     {args.book!r}")
    print(f"DPI:      {args.dpi}")
    print(f"Pages:    {lo}..{hi} ({hi - lo + 1} page(s))")
    print(f"Mode:     {'DRY-RUN (no DB writes)' if args.dry_run else 'WRITE'}")
    print("-" * 60)

    import fitz  # PyMuPDF

    doc = fitz.open(PDF_PATH)
    if doc.page_count != TOTAL_PAGES:
        print(
            f"WARNING: PDF has {doc.page_count} pages, expected {TOTAL_PAGES}.",
            file=sys.stderr,
        )

    engine = None
    conn = None
    if not args.dry_run:
        engine = make_engine()
        conn = engine.connect()

    total_bytes = 0
    rows_intended = 0
    oversized = []
    batch = []

    try:
        from sqlalchemy import text as sa_text

        for pdf_page in range(lo, hi + 1):
            page = doc[pdf_page - 1]
            png_bytes = page.get_pixmap(dpi=args.dpi).tobytes("png")
            nbytes = len(png_bytes)
            total_bytes += nbytes
            rows_intended += 1

            if mapping is not None:
                printed = mapping.get(str(pdf_page))
                if printed is None:
                    print(
                        f"  NOTE: no printed-page mapping for pdf page {pdf_page}; skipping.",
                        file=sys.stderr,
                    )
                    continue
                printed_str = str(printed)
            else:
                printed_str = str(pdf_page)

            kb = nbytes / 1024.0
            flag = ""
            if nbytes > OVERSIZE_WARN_BYTES:
                flag = "  *** OVERSIZED (>15MB; check max_allowed_packet) ***"
                oversized.append((pdf_page, nbytes))
            print(
                f"page {pdf_page:>3}/{TOTAL_PAGES}  "
                f"printed_page={printed_str:<6}  blob={kb:8.1f} KB{flag}"
            )

            if not args.dry_run:
                batch.append(
                    {
                        "book": args.book,
                        "printed_page_num": printed_str,
                        "image_path": None,
                        "image_blob": png_bytes,
                        "notes": notes,
                    }
                )
                if len(batch) >= BATCH_SIZE:
                    for row in batch:
                        conn.execute(sa_text(UPSERT_SQL), row)
                    conn.commit()
                    print(f"  -- committed batch of {len(batch)} row(s)")
                    batch = []

        if not args.dry_run and batch:
            for row in batch:
                conn.execute(sa_text(UPSERT_SQL), row)
            conn.commit()
            print(f"  -- committed final batch of {len(batch)} row(s)")

    finally:
        doc.close()
        if conn is not None:
            conn.close()

    print("-" * 60)
    print(f"Rows intended:  {rows_intended}")
    print(f"Total blob size: {total_bytes / (1024 * 1024):.2f} MB")
    if oversized:
        print(f"OVERSIZED pages ({len(oversized)}): {[p for p, _ in oversized]}")
    if args.dry_run:
        print("DRY-RUN: no rows written.")
    elif engine is not None:
        from sqlalchemy import text as sa_text

        with engine.connect() as vconn:
            count = vconn.execute(
                sa_text("SELECT COUNT(*) FROM books WHERE book=:b"),
                {"b": args.book},
            ).scalar()
        print(
            f"Verification: SELECT COUNT(*) FROM books WHERE book={args.book!r} "
            f"-> {count}"
        )

    if engine is not None:
        engine.dispose()


if __name__ == "__main__":
    main()
