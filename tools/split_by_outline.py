#!/usr/bin/env python
"""split_by_outline.py — split a PDF into a tree of mini-PDFs that mirrors its bookmark outline.

For books whose PDF carries an outline (OCO, GM). Scans with no outline go through
detect_subsections.py → reviewed subsections.json → split_sections.py / split_subsections.py.

    python tools/split_by_outline.py --src oco/oco.pdf --out oco/oco_split [--toc-json oco/toc.json] [--dry-run]

Each outline leaf becomes a file and each node with children a directory. A node's own pages
before its first child become "00 - <title> (intro).pdf". Every mini-PDF also carries ONE extra
trailing page (the first page of what follows): sections end mid-page, and splits that stop at the
next heading's page silently drop the tail above it (the GR split bug; GM "buffer page").
Printed page labels are copied from the source onto every piece, so printed numbers survive.

Writes <out>/_manifest.tsv, and with --toc-json the standard book TOC file:
    {"source": ..., "entries": [[level, title, printed_page, pdf_page], ...]}
(the same shape as lhymn/lhymn_toc.json; review it before anything depends on it).
"""
import argparse
import json
import os
import re

import fitz

from _db import PP_ROOT

BAD = re.compile(r'[\\/:*?"<>|]')


def clean(title):
    title = re.sub(r"\s+", " ", BAD.sub("-", title)).strip().rstrip(". ")
    return title[:120]


def resolve(p):
    return p if os.path.isabs(p) else os.path.join(PP_ROOT, p)


def label_ranges(src, first, last):
    """Page-label rules for pages first..last (0-indexed) of src, one range per contiguous run."""
    rules, prev, start = [], None, 0
    for i in range(first, last + 1):
        lab = src[i].get_label()
        n = int(lab) if lab.isdigit() else None
        if n is None or prev is None or n != prev + 1:
            if n is None:
                rules.append({"startpage": i - first, "prefix": lab, "style": ""})
            else:
                rules.append({"startpage": i - first, "prefix": "", "style": "D", "firstpagenum": n})
        prev = n
    return rules


def units_for(toc, total):
    """[(dir_parts, filename, start0)] from fitz get_toc() rows [level, title, page1]."""
    out, stack = [], []          # stack of (level, dirname)
    counters = {}
    for i, (lvl, title, page) in enumerate(toc):
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        parent = tuple(d for _, d in stack)
        counters[parent] = counters.get(parent, 0) + 1
        name = f"{counters[parent]:02d} - {clean(title)}"
        has_kids = i + 1 < len(toc) and toc[i + 1][0] > lvl
        start = max(page - 1, 0)
        if has_kids:
            if start < toc[i + 1][2] - 1:
                out.append((parent + (name,), f"00 - {clean(title)} (intro).pdf", start))
            stack.append((lvl, name))
        else:
            out.append((parent, f"{name}.pdf", start))
    if out and out[0][2] > 0:
        out.insert(0, ((), "00 - Front Matter.pdf", 0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--toc-json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    src = fitz.open(resolve(a.src))
    toc = src.get_toc()
    if not toc:
        raise SystemExit("no outline in this PDF — use detect_subsections.py + split_sections.py instead")
    total = src.page_count
    units = units_for(toc, total)
    out_root = resolve(a.out)
    manifest = []
    for i, (parts, fname, start) in enumerate(units):
        nxt = units[i + 1][2] if i + 1 < len(units) else total - 1
        end = min(max(nxt, start), total - 1)        # include the boundary page
        rel = os.path.join(*parts, fname) if parts else fname
        manifest.append((rel, start + 1, end + 1, src[start].get_label(), src[end].get_label()))
        if a.dry_run:
            continue
        path = os.path.join(out_root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        piece = fitz.open()
        piece.insert_pdf(src, from_page=start, to_page=end)
        piece.set_page_labels(label_ranges(src, start, end))
        piece.save(path, garbage=3, deflate=True)
    for rel, s, e, ls, le in manifest:
        print(f"pdf {s:>4}-{e:<4} printed {ls:>5}-{le:<5} {rel}")
    if not a.dry_run:
        with open(os.path.join(out_root, "_manifest.tsv"), "w", encoding="utf-8") as f:
            f.write("path\tpdf_first\tpdf_last\tprinted_first\tprinted_last\n")
            for row in manifest:
                f.write("\t".join(map(str, row)) + "\n")
    if a.toc_json:
        entries = [[lvl, title, src[max(p - 1, 0)].get_label() or None, p] for lvl, title, p in toc]
        with open(resolve(a.toc_json), "w", encoding="utf-8") as f:
            json.dump({"source": f"bookmark outline of {os.path.basename(a.src)} (unreviewed)",
                       "entries": entries}, f, indent=1, ensure_ascii=False)
    print(f"{'would write' if a.dry_run else 'wrote'} {len(units)} PDFs under {out_root}")


if __name__ == "__main__":
    main()
