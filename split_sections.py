"""
Phase 2: Split a chapter PDF into section PDFs, one subdirectory per
top-level (level-0) heading.

Output layout (within the chapter directory):
  graduale/<N>/1_<slug>/0_<slug>.pdf
  graduale/<N>/1_<slug>/meta.json
  graduale/<N>/2_<slug>/0_<slug>.pdf
  ...

Each 0_<slug>.pdf gets a PDF page-label range so its pages keep displaying
their original page number from the chapter PDF -- page 1 of
2_februarius/0_februarius.pdf shows as page 8, its true page in
3_proprium-de-sanctis.pdf, instead of restarting at 1.

Section boundaries are the level==0 entries of a subsections JSON file
(produced by detect_subsections.py + review) living in the chapter
directory. Any pages before the first boundary are prepended to section 1.

Usage:
  python split_sections.py <chapter_dir> [--subsections subsections_ai.json]
  python split_sections.py graduale/3
"""

import argparse
import json
import re
import sys
from pathlib import Path

import fitz


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def find_chapter_pdf(chapter_dir: Path) -> Path:
    candidates = [
        p for p in chapter_dir.glob("*.pdf")
        if re.match(r"^\d+_", p.name) and not p.name.startswith("0_")
    ]
    if len(candidates) != 1:
        candidates = list(chapter_dir.glob("*.pdf"))
    if len(candidates) != 1:
        print(f"ERROR: expected exactly one chapter pdf in {chapter_dir}, found {candidates}")
        sys.exit(1)
    return candidates[0]


def split_chapter(chapter_dir: Path, subsections_name: str) -> None:
    subsections_path = chapter_dir / subsections_name
    entries = json.loads(subsections_path.read_text(encoding="utf-8"))
    sections = [e for e in entries if e.get("level") == 0]
    sections.sort(key=lambda e: (e["page"], e.get("y", 0)))
    if not sections:
        print(f"ERROR: no level-0 entries found in {subsections_path}")
        sys.exit(1)

    chapter_pdf = find_chapter_pdf(chapter_dir)
    doc = fitz.open(str(chapter_pdf))
    n = doc.page_count

    print(f"Splitting {chapter_pdf.name} ({n} pages) into {len(sections)} sections")
    for idx, s in enumerate(sections):
        # Prepend any front matter before the first heading to section 1.
        start = s["page"] if idx > 0 else 1
        end = sections[idx + 1]["page"] - 1 if idx + 1 < len(sections) else n
        slug = slugify(s["text"])
        num = idx + 1

        section_dir = chapter_dir / f"{num}_{slug}"
        section_dir.mkdir(exist_ok=True)
        out_path = section_dir / f"0_{slug}.pdf"

        out = fitz.open()
        out.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
        out.set_pagelayout("SinglePage")
        # Page 0 of this split displays as `start`, incrementing from there,
        # so labels match the original page numbers in chapter_pdf exactly.
        out.set_page_labels([{"startpage": 0, "prefix": "", "style": "D", "firstpagenum": start}])
        out.save(str(out_path))
        out.close()

        meta = {
            "title": s["text"],
            "source_pdf": chapter_pdf.name,
            "page_offset": start,  # 1-indexed page in source PDF
        }
        (section_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        print(f"  {num:2d}. {s['text']:<24} p{start}-{end}  ({end - start + 1}pp)  -> {section_dir.name}/0_{slug}.pdf")

    doc.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter_dir", type=Path)
    parser.add_argument("--subsections", default="subsections.json")
    args = parser.parse_args()

    if not args.chapter_dir.is_dir():
        print(f"ERROR: {args.chapter_dir} is not a directory")
        sys.exit(1)

    split_chapter(args.chapter_dir, args.subsections)
