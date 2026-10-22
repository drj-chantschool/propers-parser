"""q.py — run read-only SQL against local liturgio and print tab-separated results.

    python tools/q.py "SELECT ..." ["SELECT ..." ...]

Uses liturgio_ro. Never SELECT * FROM books (image blobs: 1 GB+).
"""
import sys

from sqlalchemy import text

from _db import engine

with engine().connect() as c:
    for q in sys.argv[1:]:
        print("##", q[:200])
        r = c.execute(text(q))
        if r.returns_rows:
            print("\t".join(r.keys()))
            for row in r:
                print("\t".join(str(x) for x in row))
