#!/usr/bin/env python
"""Cut a printed-page range out of a Graduale chapter PDF into Read-tool-sized chunks.

The native Read tool rejects the GR PDFs as "password-protected" above a size threshold
(fitz reports is_encrypted=False; a 5-page/390KB split reads fine, a 9-page/530KB one does
not).  Chunking to <=4 pages keeps every piece readable, so producers can Read the pages
directly instead of falling back to fitz + dpi=200 PNG renders.

Printed page labels are carried over from the parent PDF (renumber_pdfs.py does not do this).

    python chunk_gr_pages.py --chapter 2 --from 397 --to 402 --name ded
"""
import argparse
import os
import sys

import fitz

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--size", type=int, default=4, help="pages per chunk (default 4)")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    chapters = {
        "2": os.path.join(ROOT, "graduale", "2", "2_communia.pdf"),
    }
    src_path = chapters.get(args.chapter)
    if not src_path or not os.path.exists(src_path):
        print(f"ERROR: no chapter PDF for {args.chapter!r}", file=sys.stderr)
        return 2

    outdir = args.outdir or os.path.join(ROOT, "_tmp", f"ch{args.chapter}")
    os.makedirs(outdir, exist_ok=True)

    src = fitz.open(src_path)
    labels = [src[i].get_label() for i in range(src.page_count)]
    try:
        a = labels.index(str(args.first))
        b = labels.index(str(args.last))
    except ValueError as exc:
        print(f"ERROR: printed page not in {src_path}: {exc}", file=sys.stderr)
        return 2

    made = []
    for start in range(a, b + 1, args.size):
        end = min(start + args.size - 1, b)
        out = fitz.open()
        out.insert_pdf(src, from_page=start, to_page=end)
        out.set_page_labels([{
            "startpage": 0, "prefix": "", "style": "D",
            "firstpagenum": int(labels[start]),
        }])
        path = os.path.join(outdir, f"{args.name}_{labels[start]}-{labels[end]}.pdf")
        out.save(path)
        kb = os.path.getsize(path) // 1024
        made.append(path)
        flag = "  ⚠ may be too large to Read" if kb > 450 else ""
        print(f"{path}  ({end - start + 1}pp, {kb}KB){flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
