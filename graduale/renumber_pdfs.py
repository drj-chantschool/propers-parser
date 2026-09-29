#!/usr/bin/env python3
"""
Apply printed page labels to all PDFs in the graduale directory tree.

Offset formula
--------------
For level-1 section PDFs (e.g. 1_proprium-de-tempore.pdf):
    meta.json has source_pdf == "graduale romanum.pdf"
    graduale_0based_offset = page_offset - 1

For all deeper PDFs (directory 0_*.pdf and leaf *.meta.json files):
    chapter_page_offset  — 1-indexed page in the CHAPTER PDF (proprium, communia, …)
                           where this section starts. Written by split_subsections.py.
    For level-2 section PDFs produced by split_sections.py (no chapter_page_offset),
    page_offset itself equals the chapter page (it is 1-indexed in the chapter PDF).

    level1_dir is the immediate child of GRADUALE_DIR that contains this PDF.
    level1.page_offset = 1-indexed page in graduale romanum.pdf where the chapter starts.

    graduale_0based_offset = level1.page_offset + chapter_page - 2

    where chapter_page = chapter_page_offset (if present) else page_offset.

Saves are done as a full rewrite (via a .tmp.pdf) so that any prior incremental
page-label updates are cleanly superseded.
"""
import json
import os
import sys
from pathlib import Path
import fitz

GRADUALE_DIR = Path(r"C:\Users\johna\liturgio\propers-parser\graduale")
GRADUALE_PDF_NAME = "graduale romanum.pdf"

with open(GRADUALE_DIR / "page_mapping.json") as f:
    _raw = json.load(f)
PAGE_MAPPING: dict[int, int] = {int(k): int(v) for k, v in _raw["mapping"].items()}

_level1_offset_cache: dict[str, int] = {}


def level1_graduale_offset(dir_path: Path) -> int:
    """
    Return the level-1 ancestor's page_offset - 1 (0-based graduale index of the
    chapter PDF's first page). Cached.
    """
    level1 = GRADUALE_DIR / dir_path.relative_to(GRADUALE_DIR).parts[0]
    key = str(level1)
    if key not in _level1_offset_cache:
        with open(level1 / "meta.json") as f:
            meta = json.load(f)
        # page_offset here is 1-indexed graduale page where this chapter starts
        _level1_offset_cache[key] = meta["page_offset"] - 1
    return _level1_offset_cache[key]


def load_meta_for_pdf(pdf_path: Path) -> dict:
    """Load the meta dict for pdf_path: sibling *.meta.json first, then dir meta.json."""
    leaf = pdf_path.with_suffix(".meta.json")
    if leaf.exists():
        with open(leaf) as f:
            return json.load(f)
    d = pdf_path.parent / "meta.json"
    if d.exists():
        with open(d) as f:
            return json.load(f)
    raise FileNotFoundError(f"No meta found for {pdf_path.name} in {pdf_path.parent}")


def get_pdf_graduale_offset(pdf_path: Path) -> int:
    """
    Return the 0-based offset such that
        PDF page P (1-based)  →  graduale page (offset + P) (1-based)
        →  printed page = PAGE_MAPPING[offset + P]
    """
    meta = load_meta_for_pdf(pdf_path)
    source = meta["source_pdf"]
    page_offset: int = meta["page_offset"]

    # Level-1: meta.json directly references graduale romanum.pdf
    if source == GRADUALE_PDF_NAME:
        return page_offset - 1

    # Deeper: compute from level-1 chapter offset + chapter_page
    # chapter_page_offset (written by split_subsections.py): 1-indexed page in the
    # chapter PDF (proprium / communia / …) where this section/leaf starts.
    # For level-2 sections produced by split_sections.py, page_offset itself
    # already equals the 1-indexed chapter page (no chapter_page_offset field).
    chapter_page = meta.get("chapter_page_offset", page_offset)
    # level1 offset: 0-based position of chapter page 1 in graduale
    l1_off = level1_graduale_offset(pdf_path.parent)
    # chapter page C → graduale page = (l1_off + 1) + C - 1 = l1_off + C
    return l1_off + chapter_page - 1


def make_label_ranges(labels: list[int]) -> list[dict]:
    ranges = []
    prev = None
    for i, label in enumerate(labels):
        if prev is None or label != prev + 1:
            ranges.append({"startpage": i, "style": "D", "firstpagenum": label, "prefix": ""})
        prev = label
    return ranges


def apply_labels(pdf_path: Path, graduale_offset: int) -> None:
    doc = fitz.open(str(pdf_path))
    n = doc.page_count
    if n == 0:
        doc.close()
        return

    labels = [PAGE_MAPPING.get(graduale_offset + p + 1, graduale_offset + p + 1) for p in range(n)]
    doc.set_page_labels(make_label_ranges(labels))

    # Full rewrite via temp file so old incremental label data is gone
    tmp = pdf_path.with_suffix(".tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    doc.close()
    tmp.replace(pdf_path)

    span = f"{labels[0]}–{labels[-1]}" if n > 1 else str(labels[0])
    print(f"    {pdf_path.name:60s} {n:4d}pp  printed {span}")


def process_graduale_romanum() -> None:
    pdf_path = GRADUALE_DIR / GRADUALE_PDF_NAME
    print(f"\n[root] {GRADUALE_PDF_NAME}")
    doc = fitz.open(str(pdf_path))
    n = doc.page_count
    labels = [PAGE_MAPPING.get(p + 1, p + 1) for p in range(n)]
    doc.set_page_labels(make_label_ranges(labels))
    tmp = pdf_path.with_suffix(".tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    doc.close()
    tmp.replace(pdf_path)
    print(f"    {n}pp  printed {labels[0]}–{labels[-1]}")


def process_subdirectories() -> None:
    for root, dirs, files in os.walk(GRADUALE_DIR):
        root_path = Path(root)
        if root_path == GRADUALE_DIR:
            continue

        pdf_files = sorted(f for f in files if f.lower().endswith(".pdf"))
        if not pdf_files:
            continue

        print(f"\n[{root_path.relative_to(GRADUALE_DIR)}]")
        for pdf_file in pdf_files:
            pdf_path = root_path / pdf_file
            try:
                offset = get_pdf_graduale_offset(pdf_path)
                apply_labels(pdf_path, offset)
            except FileNotFoundError as e:
                print(f"    (skip {pdf_file} — {e})")
            except Exception as e:
                print(f"    ERROR {pdf_file}: {e}", file=sys.stderr)


if __name__ == "__main__":
    process_graduale_romanum()
    process_subdirectories()
    print("\nDone.")
