"""
Detect subsection headings within a section PDF.

Searches for "HEBDOMADA" (or other keywords) in body text (y >= 30)
on every page, returning page number (1-indexed), y-position, and heading text.

Running page headers (y < 30, small font) are excluded.

Usage:
  python detect_subsections.py <section_pdf>
  python detect_subsections.py graduale/1/7_tempus-per-annum/0_tempus-per-annum.pdf
"""

import sys
import re
import json
import fitz
from pathlib import Path

# Keywords that mark a subsection heading
HEADING_PATTERNS = [
    r"HEBDOMAD",          # weekly headings (Tempus per Annum, Advent, etc.)
    r"DOMINICA",          # Sunday headings
    r"FERIA",             # weekday headings
    r"SABBATO",           # Saturday headings (esp. Lent)
    r"IN VIGILIA",        # vigil headings
    r"IN NATIVITATE",
    r"AD MISSAM",
    r"IN ASCENSIONE",
    r"VIRGI",
    r"DOCTOR",
    r"EPISCOP",
    r"MARTY",
    r"PRESB",
    r"DOMINI",
    r"APOST",
#    r"COMMUNE",           # Common of Saints cross-references
#    r"PRO ",
#    r"IN ",
    r"S\.",
    r"SS\.",
    r"\b(?:IANUARI|FEBRUARI|MARTI|APRIL|MAI|IUNI|IULI|AUGUST|SEPTEMBR|OCTOBR|NOVEMBR|DECEMBR)",  # Latin month names (Sanctorale dates)
    r"DIE",
#    r"^\d{1,2}\.?\s",     # Arabic day-of-month numbers (Sanctorale dates)
    r"\b(?:PRIM|SECUND|TERTI|QUART|QUINT|SEXT|SEPTIM|OCTAV|NON|DECIM)[AOU]",  # Latin ordinals
]

HEADING_RE = re.compile("|".join(HEADING_PATTERNS), re.IGNORECASE)


def detect(pdf_path: Path) -> list[dict]:
    doc = fitz.open(str(pdf_path))
    results = []

    for i, page in enumerate(doc):
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                line_text = " ".join(s["text"] for s in line["spans"]).strip()
                y = line["bbox"][1]
                sz = max(s["size"] for s in line["spans"])

                # Skip running headers (very top, small font)
                if y < 30 and sz < 10:
                    continue

                if HEADING_RE.search(line_text):
                    if 'die' in line_text.lower():
                        level=1
                    elif 'S.' in line_text or 'SS.' in line_text:
                        level=2
                    else:
                        level=0
                    results.append({
                        "page": i + 1,   # 1-indexed
                        "y": round(y, 1),
                        "size": round(sz, 1),
                        "level": level,
                        "text": line_text,
                    })

    doc.close()
    return results


if __name__ == "__main__":
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not pdf_path or not pdf_path.exists():
        print(f"Usage: python {Path(__file__).name} <section_pdf>")
        sys.exit(1)

    hits = detect(pdf_path)

    print(f"{'Page':>5}  {'y':>6}  {'sz':>5}  Text")
    print("-" * 70)
    for h in hits:
        print(f"{h['page']:>5}  {h['y']:>6.1f}  {h['size']:>5.1f}  {h['text']}")

    out = pdf_path.with_name("subsections_raw.json")
    out.write_text(json.dumps(hits, indent=2))
    print(f"\nWrote {out}")
