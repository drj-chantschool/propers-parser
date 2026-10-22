#!/usr/bin/env python
"""Split any PDF into smaller, Read-tool-sized chunks.

The native Read tool rejects large GR/GM PDFs as "password-protected" above a size
threshold (fitz reports is_encrypted=False; a 5-page/390KB split reads fine, a
9-page/530KB one does not). Chunking to <=4 pages keeps every piece readable.

Works on any source PDF (GR, GM, LH, ...) and, unlike graduale/renumber_pdfs.py,
carries the parent's printed page labels (page.get_label())
over onto each chunk so downstream tooling that keys off printed page numbers
keeps working.

    python tools/chunk_pdf.py --src graduale/3/1_ianuarius/0_ianuarius.pdf --size 3 \
        --outdir _tmp/ianuarius
"""
import argparse
import os
import sys

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # propers-parser/
REPO_ROOT = os.path.dirname(ROOT)


def resolve_src(path):
    """Resolve --src as absolute, or relative to cwd / propers-parser/ / repo root."""
    if os.path.isabs(path):
        return path if os.path.exists(path) else None
    for base in (os.getcwd(), ROOT, REPO_ROOT):
        candidate = os.path.join(base, path)
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None


def positive_int_upto_10(value):
    n = int(value)
    if not (1 <= n <= 10):
        raise argparse.ArgumentTypeError("--size must be between 1 and 10")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="path to source PDF (absolute, "
                     "or relative to cwd / propers-parser/ / repo root)")
    ap.add_argument("--size", type=positive_int_upto_10, default=4,
                     help="pages per chunk, 1-10 (default 4)")
    ap.add_argument("--outdir", default=None,
                     help="default: propers-parser/_tmp/<src-stem>/")
    ap.add_argument("--name", default=None,
                     help="output filename prefix (default: src stem)")
    ap.add_argument("--from", dest="first", default=None,
                     help="printed page label to start at (default: first page)")
    ap.add_argument("--to", dest="last", default=None,
                     help="printed page label to end at (default: last page)")
    args = ap.parse_args()

    if bool(args.first) != bool(args.last):
        print("ERROR: --from and --to must be given together", file=sys.stderr)
        return 2

    src_path = resolve_src(args.src)
    if not src_path:
        print(f"ERROR: source PDF not found: {args.src!r}", file=sys.stderr)
        return 2

    stem = os.path.splitext(os.path.basename(src_path))[0]
    outdir = args.outdir or os.path.join(ROOT, "_tmp", stem)
    os.makedirs(outdir, exist_ok=True)
    name = args.name or stem

    src = fitz.open(src_path)
    labels = [src[i].get_label() for i in range(src.page_count)]

    if args.first:
        try:
            a = labels.index(args.first)
            b = labels.index(args.last)
        except ValueError as exc:
            print(f"ERROR: printed page not in {src_path}: {exc}", file=sys.stderr)
            return 2
    else:
        a, b = 0, src.page_count - 1

    made = []
    for start in range(a, b + 1, args.size):
        end = min(start + args.size - 1, b)

        chunk_labels = labels[start:end + 1]
        use_labels = all(chunk_labels)
        first_num = None
        if use_labels:
            try:
                first_num = int(labels[start])
            except ValueError:
                use_labels = False

        out = fitz.open()
        out.insert_pdf(src, from_page=start, to_page=end)

        if use_labels:
            out.set_page_labels([{
                "startpage": 0, "prefix": "", "style": "D",
                "firstpagenum": first_num,
            }])
            tag_first, tag_last = labels[start], labels[end]
        else:
            # No usable printed label on this page range -- fall back to
            # naming by 1-indexed source page number and say so.
            tag_first, tag_last = f"p{start + 1}", f"p{end + 1}"
            print(f"NOTE: pages {start + 1}-{end + 1} of {src_path} have no "
                  f"(usable) printed label; falling back to source page numbers")

        path = os.path.join(outdir, f"{name}_{tag_first}-{tag_last}.pdf")
        out.save(path)
        kb = os.path.getsize(path) // 1024
        made.append(path)
        flag = "  ⚠ may be too large to Read" if kb > 450 else ""
        print(f"{path}  ({end - start + 1}pp, {kb}KB){flag}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
