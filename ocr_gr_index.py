"""
ocr_gr_index.py: Full Tesseract OCR pass over all GR index pages.
Produces gr_chant_index_ocr.csv alongside the existing fitz-derived CSV.
"""

import re
import csv
import io
import fitz
import pytesseract
from PIL import Image
from pathlib import Path

OUTPUT_CSV = Path(__file__).parent / "gr_chant_index_ocr.csv"
INDEX_PDF = Path(__file__).parent / "graduale" / "8" / "8_indices.pdf"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

IMAGE_PAGES = range(0, 2)
FITZ_PAGES = range(2, 14)


_EXT_TRANS_DICT = {
    "I": "1",
    "l": "1",
    "O": "0",
    "o": "0",
    "r": "1",
    "J": "0",
    "!": "1",
    "$": "5",
    "S": "5",
    "s": "5",
    "z": "2",
    "i": "1",
}
_EXT_TRANS = str.maketrans(
    "".join(_EXT_TRANS_DICT.keys()), "".join(_EXT_TRANS_DICT.values())
)

SECTION_HEADERS = {
    "introitus": "introitus",
    "gradualia": "graduale",
    "versus alleluiatici": "alleluia",
    "tractus et cantica": "tractus",
    "tractus": "tractus",
    "offertoria": "offertorium",
    "communiones": "communio",
    "antiphon": "antiphona",
    "hymni": "hymnus",
    "psalmi": "psalmus",
    "cantica": "canticum",
    "responsoria": "responsorium",
    "varia": "varia",
    "cantus in ordine": "ordinarium",
}
STOP_SECTIONS = {"ordinarium"}

_IS_MODE = re.compile(r"^[1-8IiS$]{1,2}$")
_IS_PAGE = re.compile(r"^[IlOorJ!$Sszi\d]{2,5}$")


def fix_page(raw: str) -> str | None:
    c = raw.translate(_EXT_TRANS).rstrip(".,;:'")
    if not re.fullmatch(r"\d{1,5}", c) or int(c) <= 0:
        return None
    return c if re.fullmatch(r"\d{1,4}", c) and int(c) > 0 else None


def fix_all_pages(raw: str) -> list[str]:
    c = raw.translate(_EXT_TRANS).rstrip(".,;:'")
    results = []
    for p in re.split(r"[,;]", c):
        pg = fix_page(p.strip())
        if pg and pg not in results:
            results.append(pg)
    return results


def norm_mode(w: str) -> str:
    w = w.translate(_EXT_TRANS)
    return "1" if w in {"I", "i"} else w


def match_section(line: str) -> str | None:
    t = re.sub(r"[^\x00-\x7f]", "", line.strip().lower()).strip()
    t = re.sub(r"^[|.\s]+", "", t)  # strip leading OCR noise (| . etc)
    return next((v for k, v in SECTION_HEADERS.items() if t.startswith(k)), None)


def ocr_column(img: Image.Image) -> list[str]:
    text = pytesseract.image_to_string(img, lang="lat", config="--psm 6")
    return [l for l in text.splitlines() if l.strip()]


def parse_line(line: str) -> tuple[str, str, list[str]] | None:
    """
    Parse one OCR line as (mode, incipit, pages).
    Splits on whitespace, strips dot-leader noise, takes:
      - first token as mode (if it looks like 1-8/I)
      - last token as page (if it looks like a number)
      - everything between as incipit
    Returns None if the line doesn't look like an entry.
    """
    # Strip leading/trailing noise chars
    line = re.sub(r"^[|.\s]+", "", line).rstrip(" |.")
    # Collapse dot-leaders to single space
    line = re.sub(r"[\s.·]{2,}", " ", line).strip()

    tokens = line.split()
    if len(tokens) < 3:
        return None

    # First token must look like a mode digit
    if not _IS_MODE.match(tokens[0]):
        return None

    mode = norm_mode(tokens[0])

    # Greedily consume page numbers from the right end of the token list.
    # Stop as soon as a token starts with a letter (incipit territory).
    middle = tokens[1:]
    pages: list[str] = []
    while middle:
        candidate = fix_all_pages(middle[-1])
        if candidate and not middle[-1][0].isalpha():
            for p in candidate:
                if p not in pages:
                    pages.append(p)
            middle = middle[:-1]
        else:
            break

    if not pages:
        return None

    # Incipit is whatever remains, must start with a letter
    if not middle or not middle[0][0].isalpha():
        return None
    inc = " ".join(middle).strip().rstrip(".,; ")

    return mode, inc, pages


def parse_ocr_lines(all_lines: list[str]) -> list[dict]:
    records = []
    current_type = None
    done = False

    for line in all_lines:
        if done:
            break
        stripped = line.strip()

        sec = match_section(stripped)
        if sec:
            if sec in STOP_SECTIONS:
                done = True
            else:
                current_type = sec
            continue

        if current_type is None:
            continue

        parsed = parse_line(stripped)
        if not parsed:
            continue

        mode, inc, pages = parsed
        for p in pages:
            records.append(
                {"chant_type": current_type, "mode": mode, "incipit": inc, "page": p}
            )

    return records


def main():
    doc = fitz.open(str(INDEX_PDF))
    all_lines: list[str] = []

    for pg_idx in list(IMAGE_PAGES) + list(FITZ_PAGES):
        mat = fitz.Matrix(3, 3)
        pix = doc[pg_idx].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        w, h = img.size
        top = int(h * 0.05)
        # The printed column rule sits at ~w/2; give it 8px clearance on each side
        rule = w // 2
        for half in [img.crop((0, top, rule - 8, h)), img.crop((rule + 8, top, w, h))]:
            all_lines.extend(ocr_column(half))
        print(f"  OCR'd page {pg_idx}")

    doc.close()

    print(f"\nParsing {len(all_lines)} OCR lines...")
    records = parse_ocr_lines(all_lines)
    print(f"Found {len(records)} entries")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["chant_type", "mode", "incipit", "page"])
        writer.writeheader()
        writer.writerows(records)

    print(f"Written to {OUTPUT_CSV}")
    from collections import Counter

    by_type = Counter(r["chant_type"] for r in records)
    for t, n in sorted(by_type.items()):
        print(f"  {t:<15} {n}")


if __name__ == "__main__":
    main()
