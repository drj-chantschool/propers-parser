"""
Phase 2: Split each GR chapter into section PDFs.

Output layout (within the chapter folder):
  graduale/1/1_tempus-adventus/0_tempus-adventus.pdf
  graduale/1/2_tempus-nativitatis/0_tempus-nativitatis.pdf
  ...

Section boundaries are given as (0-indexed page, title) pairs.
Pages before the first section boundary are prepended to section 1.
"""

import json
import re
import fitz
from pathlib import Path

BASE = Path(__file__).parent


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def save_section(doc: fitz.Document, start: int, end: int, out_path: Path) -> None:
    """Save pages [start, end) (0-indexed) to out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = fitz.open()
    out.insert_pdf(doc, from_page=start, to_page=end - 1)
    out.set_pagelayout("SinglePage")
    out.save(str(out_path))
    out.close()
    print(f"  Wrote {out_path.relative_to(BASE)} ({end - start} pages)")


# ---------------------------------------------------------------------------
# Chapter 1 — Proprium de Tempore
# Sections identified by manual inspection of 1_proprium-de-tempore.pdf.
# Page numbers are 1-indexed (as shown in the PDF viewer); converted to
# 0-indexed internally.
# ---------------------------------------------------------------------------

GR_CHAPTER_1_SECTIONS = [
    (2,   "TEMPUS ADVENTUS"),
    (25,  "TEMPUS NATIVITATIS"),
    (43,  "IN EPIPHANIA DOMINI"),
    (49,  "TEMPUS QUADRAGESIMAE"),
    (172, "TEMPUS PASCHALE"),
    (222, "IN ASCENSIONE DOMINI"),
    (244, "TEMPUS PER ANNUM"),
    (358, "SOLLEMNITATES DOMINI"),
]


def split_chapter(pdf_path: Path, sections: list, chap_num: int) -> None:
    doc = fitz.open(str(pdf_path))
    n = len(doc)
    print(f"Splitting {pdf_path.name} ({n} pages) into {len(sections)} sections")

    # Convert 1-indexed page numbers to 0-indexed
    boundaries = [(page - 1, title) for page, title in sections]

    out_root = pdf_path.parent

    for sec_num, (page_idx, title) in enumerate(boundaries, 1):
        start = page_idx
        # If this is section 1, include any front-matter pages before it
        if sec_num == 1:
            start = 0
        end = boundaries[sec_num][0] if sec_num < len(boundaries) else n

        slug = slugify(title)
        section_dir = out_root / f"{sec_num}_{slug}"
        out_path = section_dir / f"0_{slug}.pdf"

        print(f"  Section {sec_num}: {title!r} (p{start+1}–{end})")
        save_section(doc, start, end, out_path)

        meta = {
            "title": title,
            "source_pdf": pdf_path.name,
            "page_offset": start + 1,   # 1-indexed page in source PDF
        }
        (section_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    doc.close()


if __name__ == "__main__":
    chap1_pdf = BASE / "graduale" / "1" / "1_proprium-de-tempore.pdf"
    split_chapter(chap1_pdf, GR_CHAPTER_1_SECTIONS, chap_num=1)
