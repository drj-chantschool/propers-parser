"""
Phase 1: Split GR and OCO into chapter PDFs.

GR:  Detect mostly-blank pages, OCR with Tesseract to get title, split there.
OCO: Use embedded level-1 ToC entries.

Output layout:
  graduale/1/1_<chapter-slug>.pdf
  oco/1/1_<chapter-slug>.pdf
  etc.
"""

import json
import re
import sys
import fitz          # pymupdf
import pytesseract
from pathlib import Path
from PIL import Image
import io

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

BASE = Path(__file__).parent


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def save_chapter(doc: fitz.Document, start: int, end: int, out_path: Path,
                 *, meta: dict | None = None) -> None:
    """Save pages [start, end) (0-indexed) to out_path.

    Skips writing the PDF if it already exists (non-destructive).
    Always writes meta.json if meta is provided.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        print(f"  Exists  {out_path.name} ({end - start} pages) — skipping PDF")
    else:
        out = fitz.open()
        out.insert_pdf(doc, from_page=start, to_page=end - 1)
        out.save(str(out_path))
        out.close()
        print(f"  Wrote   {out_path.name} ({end - start} pages)")
    if meta is not None:
        meta_path = out_path.parent / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"  Wrote   {meta_path.name}")


def ocr_page_title(page: fitz.Page) -> str:
    """Render top 55% of a page at 3x zoom and OCR; handles large spaced small-caps."""
    mat = fitz.Matrix(3, 3)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    w, h = img.size
    top = img.crop((0, 0, w, int(h * 0.55)))
    text = pytesseract.image_to_string(top, lang="lat", config="--psm 6")
    return text.strip()


def split_gr():
    pdf_path = BASE / "graduale" / "graduale romanum.pdf"
    doc = fitz.open(str(pdf_path))
    n = len(doc)
    print(f"GR: {n} pages")

    # Find chapter title pages: very sparse, high-alpha text, skipping front matter.
    # A minimum gap between chapters prevents sub-index pages from splitting a chapter.
    FRONT_MATTER_CUTOFF = 10  # ignore pages before this (0-indexed)
    SPARSE_THRESHOLD = 150    # fitz char count
    ALPHA_MIN = 0.90          # fraction of alpha/space chars
    MIN_CHAPTER_GAP = 10      # minimum pages between chapter starts

    def alpha_ratio(text):
        if not text:
            return 0.0
        return sum(1 for c in text if c.isalpha() or c.isspace()) / len(text)

    def extract_title_from_fitz(text: str) -> str:
        """Take leading uppercase lines as the chapter title, stop at mixed-case."""
        title_lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Accept lines that are mostly uppercase (title text)
            upper_chars = sum(1 for c in line if c.isalpha())
            if upper_chars == 0 or sum(1 for c in line if c.isupper()) / upper_chars >= 0.8:
                title_lines.append(line)
            else:
                break  # hit mixed-case subtitle, stop
        return " ".join(title_lines) if title_lines else text.splitlines()[0].strip()

    chapter_pages = []  # list of (0-indexed page, title)
    for i in range(FRONT_MATTER_CUTOFF, n):
        text = doc[i].get_text().strip()
        fitz_len = len(text)

        # Include both sparse-text pages and fully-image pages (fitz gets 0 chars)
        is_sparse_text = 0 < fitz_len < SPARSE_THRESHOLD and alpha_ratio(text) >= ALPHA_MIN
        is_image_page = fitz_len == 0

        if not (is_sparse_text or is_image_page):
            continue
        if chapter_pages and (i - chapter_pages[-1][0]) < MIN_CHAPTER_GAP:
            print(f"  Skipping p{i+1} (too close to previous chapter, likely sub-heading)")
            continue

        if is_sparse_text:
            title = extract_title_from_fitz(text)
        else:
            title = ""

        # For image pages or when fitz title extraction failed, use Tesseract
        if not re.search(r"[A-Za-z]{3,}", title):
            ocr = ocr_page_title(doc[i])
            # Keep only the leading uppercase lines (title proper)
            title = extract_title_from_fitz(ocr)
            if not re.search(r"[A-Za-z]{3,}", title):
                title = ocr.splitlines()[0].strip() if ocr else ""

        if re.search(r"[A-Za-z]{3,}", title):
            chapter_pages.append((i, title))
            print(f"  Found chapter at p{i+1}: {title!r}")

    if not chapter_pages:
        print("ERROR: No chapter pages found in GR", file=sys.stderr)
        return

    # Build (start, end, title) ranges
    ranges = []
    for idx, (page_idx, title) in enumerate(chapter_pages):
        start = page_idx
        end = chapter_pages[idx + 1][0] if idx + 1 < len(chapter_pages) else n
        ranges.append((start, end, title))

    out_root = BASE / "graduale"
    for chap_num, (start, end, title) in enumerate(ranges, 1):
        slug = slugify(title)
        out_path = out_root / str(chap_num) / f"{chap_num}_{slug}.pdf"
        print(f"  Chapter {chap_num}: {title!r} (p{start+1}–{end})")
        meta = {
            "title": title,
            "source_pdf": pdf_path.name,
            "page_offset": start + 1,   # 1-indexed page in graduale romanum.pdf
        }
        save_chapter(doc, start, end, out_path, meta=meta)

    doc.close()


def split_oco():
    pdf_path = BASE / "oco" / "oco.pdf"
    doc = fitz.open(str(pdf_path))
    n = len(doc)
    print(f"OCO: {n} pages")

    toc = doc.get_toc()
    l1 = [(title, page - 1) for level, title, page in toc if level == 1]  # 0-indexed

    if not l1:
        print("ERROR: No level-1 ToC entries found in OCO", file=sys.stderr)
        return

    out_root = BASE / "oco"
    for chap_num, (title, start) in enumerate(l1, 1):
        end = l1[chap_num][1] if chap_num < len(l1) else n
        slug = slugify(title)
        out_path = out_root / str(chap_num) / f"{chap_num}_{slug}.pdf"
        print(f"  Chapter {chap_num}: {title!r} (p{start+1}–{end})")
        meta = {
            "title": title,
            "source_pdf": pdf_path.name,
            "page_offset": start + 1,   # 1-indexed page in oco.pdf
        }
        save_chapter(doc, start, end, out_path, meta=meta)

    doc.close()


if __name__ == "__main__":
    print("=== OCO ===")
    split_oco()
    print()
    print("=== GR ===")
    split_gr()
