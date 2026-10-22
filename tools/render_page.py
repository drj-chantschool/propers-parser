#!/usr/bin/env python
"""render_page.py — write page PNGs from books.image_blob for reading with the Read tool, any book.

    python tools/render_page.py --book LIBER_HYMNARIUS 4 5 [--out DIR] [--zoom top|bottom] [--full]

Pages are PRINTED page labels (books.printed_page_num), so there is no pdf-offset math.
Writes DIR/p<N>.png (default DIR = propers-parser/_tmp/pages/<BOOK>/), downscaled to 1100x1600
unless --full. --zoom top|bottom writes p<N>_top.png / p<N>_bottom.png: the upper or lower 55%
at full dpi-200 resolution, for small print (rubrics, page citations, mode letters).
"""
import argparse
import io
import os

from PIL import Image
from sqlalchemy import text

from _db import TMP, engine

ap = argparse.ArgumentParser()
ap.add_argument("pages", nargs="+")
ap.add_argument("--book", required=True)
ap.add_argument("--out")
ap.add_argument("--zoom", choices=["top", "bottom"])
ap.add_argument("--full", action="store_true", help="keep full dpi-200 resolution")
a = ap.parse_args()
out = a.out or os.path.join(TMP, "pages", a.book)
os.makedirs(out, exist_ok=True)
with engine().connect() as c:
    for p in a.pages:
        b = c.execute(text("SELECT image_blob FROM books WHERE book=:b AND printed_page_num=:p"),
                      {"b": a.book, "p": p}).scalar()
        if b is None:
            print(f"p{p}: no such {a.book} page")
            continue
        im = Image.open(io.BytesIO(b))
        if a.zoom:
            w, h = im.size
            im = im.crop((0, 0, w, int(h * .55)) if a.zoom == "top" else (0, int(h * .45), w, h))
            path = os.path.join(out, f"p{p}_{a.zoom}.png")
        else:
            if not a.full:
                im.thumbnail((1100, 1600))
            path = os.path.join(out, f"p{p}.png")
        im.save(path)
        print(os.path.abspath(path))
