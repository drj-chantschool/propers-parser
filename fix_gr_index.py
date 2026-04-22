"""
fix_gr_index.py: Post-process gr_chant_index_fitz_output.csv into gr_chant_index.csv.

Fixes applied:
1. Discard garbage entries (incipit < 2 chars)
2. Recover page numbers absorbed into the incipit (extended OCR char map)
3. Expand comma-separated multi-page entries into separate rows
4. Targeted OCR for remaining entries with no page number
5. Fix bad pages (000, 00 -> OCR)
6. Strip trailing dot-leader artifacts from incipits
"""

import re
import csv
import io
import fitz
import pytesseract
from PIL import Image
from pathlib import Path

INPUT_CSV  = Path(__file__).parent / "gr_chant_index_fitz_output.csv"
OUTPUT_CSV = Path(__file__).parent / "gr_chant_index.csv"
INDEX_PDF  = Path(__file__).parent / "graduale" / "8" / "8_indices.pdf"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Extended char map: adds i→1, S/s→5, z→2 on top of the original set
# "IlOorJ!$Sszi" (12) → "110000115521" (12)
_EXT_TRANS = str.maketrans("IlOorJ!$Sszi", "110000115521")


def try_fix_page(raw: str) -> str | None:
    c = raw.translate(_EXT_TRANS).rstrip(".,;:'")
    if "," in c:
        c = c.split(",")[0]
    return c if re.fullmatch(r"\d{1,4}", c) and int(c) > 0 else None


def fix_all_pages(raw: str) -> list[str]:
    """Return all valid page numbers from a possibly comma-separated string."""
    c = raw.translate(_EXT_TRANS).rstrip(".,;:'")
    return [
        p.strip()
        for p in re.split(r"[,;]", c)
        if re.fullmatch(r"\d{1,4}", p.strip()) and int(p.strip()) > 0
    ]


def clean_incipit(inc: str) -> str:
    """Strip trailing dot-leader runs and soft-hyphens."""
    inc = inc.replace("\xad", "")          # soft hyphen
    inc = re.sub(r"[\s.·]{3,}$", "", inc)  # trailing leader dots
    inc = re.sub(r"\s+", " ", inc)
    return inc.strip().rstrip(".,;")


def recover_page_from_incipit(inc: str) -> tuple[str, str | None]:
    """
    Try to split a trailing OCR page number out of an incipit.
    Returns (cleaned_incipit, page) or (inc, None).
    """
    # Match a trailing token that looks like a page number
    m = re.search(r"[\s.]+([IlOorJ!$SszbZi\d]{2,5})\s*$", inc)
    if m:
        pg = try_fix_page(m.group(1))
        if pg:
            return inc[: m.start()].strip().rstrip(".,;"), pg
    return inc, None


# ---------------------------------------------------------------------------
# Targeted OCR helpers
# ---------------------------------------------------------------------------

def _ocr_rect(page: fitz.Page, rect: fitz.Rect, zoom: int = 3) -> str:
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=rect, colorspace=fitz.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="lat", config="--psm 7").strip()


def _extract_trailing_number(text: str) -> str | None:
    """Pull the rightmost digit sequence that looks like a page number."""
    # Remove obvious non-number noise then look for last number
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = text.split()
    for tok in reversed(tokens):
        pg = try_fix_page(tok)
        if pg:
            return pg
    return None


def find_page_number_by_ocr(doc: fitz.Document, incipit: str,
                             pg_range=range(2, 14)) -> str | None:
    """
    For a given incipit, locate the entry via fitz text search, then OCR only
    the page-number x-zone (right portion of whichever column the entry is in),
    scanning 2-3 line-heights to catch numbers on the same or next line.
    """
    words = [w for w in incipit.split() if len(w) > 2 and w[0].isalpha()]
    if not words:
        return None
    search_word = words[0]

    PAGE_W = 396  # typical index page width in pts

    for pg_idx in pg_range:
        page = doc[pg_idx]
        hits = page.search_for(search_word, quads=False)
        if not hits:
            continue
        for rect in hits:
            entry_x = rect.x0
            # Determine which column and where its page-number zone is
            if entry_x < 180:
                # Left column: page numbers appear around x=120-180
                num_x0, num_x1 = 110, 182
            else:
                # Right column: page numbers appear around x=290-380
                num_x0, num_x1 = 280, PAGE_W

            # Scan 3 line-heights downward (page number may be on next line)
            scan = fitz.Rect(num_x0, rect.y0 - 2, num_x1, rect.y1 + 30)
            text = _ocr_rect(page, scan, zoom=4)
            pg = _extract_trailing_number(text)
            if pg and int(pg) > 15:  # exclude mode numbers 1-8 and index page nums
                return pg
    return None


def find_page_number_by_ocr_image_pages(doc: fitz.Document, incipit: str,
                                        pg_range=range(0, 2)) -> str | None:
    """
    For image-only pages: render the whole page at 3x and OCR column halves,
    then search line-by-line for the incipit and extract the page number.
    """
    words = [w for w in incipit.split() if len(w) > 2 and w[0].isalpha()]
    if not words:
        return None
    search_word = words[0].lower()

    for pg_idx in pg_range:
        mat = fitz.Matrix(3, 3)
        pix = doc[pg_idx].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        w, h = img.size
        for half in [img.crop((0, 0, w // 2, h)), img.crop((w // 2, 0, w, h))]:
            text = pytesseract.image_to_string(half, lang="lat", config="--psm 6")
            for line in text.splitlines():
                if search_word in line.lower():
                    pg = _extract_trailing_number(line)
                    if pg:
                        return pg
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rows = list(csv.DictReader(open(INPUT_CSV, encoding="utf-8")))
    doc  = fitz.open(str(INDEX_PDF))

    out_rows: list[dict] = []
    fixed = skipped = expanded = ocr_found = ocr_failed = 0
    last_ocr_page: str | None = None  # dedup: discard if OCR returns same page twice running

    # Known merged-entry splits: incipit → list of (mode, incipit) tuples
    MERGED_ENTRIES = {
        "Unus militum Veni, Domine": [("7", "Unus militum"), ("1", "Veni, Domine")],
    }

    for row in rows:
        inc  = clean_incipit(row["incipit"])
        mode = row["mode"]
        ctype = row["chant_type"]
        pg   = row["page"]

        # 1. Discard garbage
        if len(inc) < 2 or inc in {"i", ".", "-"}:
            skipped += 1
            continue

        # 2. Expand known merged entries (two chants run together by the parser)
        if inc in MERGED_ENTRIES:
            for m, i in MERGED_ENTRIES[inc]:
                out_rows.append({"chant_type": ctype, "mode": m, "incipit": i, "page": ""})
            expanded += len(MERGED_ENTRIES[inc]) - 1
            continue

        # 3. Extract multi-page from incipit (e.g. "Tu es Petrus ·550,577")
        multi_m = re.search(r"[·.]?\s*(\d{2,4})[,;]\s*(\d{2,4})\s*$", inc)
        if multi_m:
            inc = inc[:multi_m.start()].strip().rstrip(".,;·")
            pages = [multi_m.group(1), multi_m.group(2)]
            for p in pages:
                out_rows.append({"chant_type": ctype, "mode": mode, "incipit": inc, "page": p})
            expanded += 1
            fixed += 1
            continue

        # 4. Bad zero pages
        if pg in {"000", "00", "0"}:
            pg = None

        # 5. If no page, try to recover from incipit
        if not pg:
            inc, pg = recover_page_from_incipit(inc)

        # 6. If still no page, try OCR
        if not pg:
            candidate = (find_page_number_by_ocr(doc, inc)
                         or find_page_number_by_ocr_image_pages(doc, inc))
            # Discard if same as last OCR result (raster artifact repeated across entries)
            if candidate and candidate != last_ocr_page:
                pg = candidate
                last_ocr_page = pg
                ocr_found += 1
                print(f"  OCR found page {pg} for: {ctype} {inc!r}")
            else:
                if candidate:
                    print(f"  OCR DEDUP ({candidate}) for: {ctype} {inc!r}")
                else:
                    print(f"  OCR FAILED for: {ctype} {inc!r}")
                ocr_failed += 1
                last_ocr_page = None
        else:
            last_ocr_page = None  # reset when we have a real page

        # 7. Check for multi-page in original page field (e.g. "270,369")
        if row["page"] and "," in row["page"]:
            pages = fix_all_pages(row["page"])
            if len(pages) > 1:
                for p in pages:
                    out_rows.append({"chant_type": ctype, "mode": mode,
                                     "incipit": inc, "page": p})
                expanded += len(pages) - 1
                fixed += 1
                continue

        # Also check the recovered page field
        if pg and "," in pg:
            pages = fix_all_pages(pg)
            if len(pages) > 1:
                for p in pages:
                    out_rows.append({"chant_type": ctype, "mode": mode,
                                     "incipit": inc, "page": p})
                expanded += len(pages) - 1
                fixed += 1
                continue

        # Validate final page
        if pg:
            pg = try_fix_page(pg) or pg  # normalize through trans table

        out_rows.append({"chant_type": ctype, "mode": mode,
                          "incipit": inc, "page": pg or ""})
        if pg != row["page"]:
            fixed += 1

    doc.close()

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["chant_type", "mode", "incipit", "page"])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"\nDone: {len(out_rows)} rows written")
    print(f"  Skipped garbage: {skipped}")
    print(f"  Fixed (char map / incipit): {fixed}")
    print(f"  Expanded multi-page: {expanded}")
    print(f"  OCR rescued: {ocr_found}")
    print(f"  OCR failed (page left blank): {ocr_failed}")

    from collections import Counter
    by_type = Counter(r["chant_type"] for r in out_rows)
    for t, n in sorted(by_type.items()):
        print(f"  {t:<15} {n}")


if __name__ == "__main__":
    main()
