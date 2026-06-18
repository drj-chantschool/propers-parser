"""
Parse the GR INDEX ALPHABETICUS CANTUUM into a CSV.
Output columns: chant_type, mode, incipit, page

Reading order: for each page, left column top-to-bottom, then right column
top-to-bottom. One shared section state flows through the entire stream.
Section changes happen at in-column headings only (page-top headers ignored).
"""

import re
import csv
import io
import fitz
import pytesseract
from PIL import Image
from pathlib import Path

GR_PDF = Path(__file__).parent / "graduale" / "graduale romanum.pdf"
OUTPUT_CSV = Path(__file__).parent / "gr_chant_index.csv"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Chapter 8 (INDICES) starts at PDF page 880 (1-indexed) = index 879 (0-indexed)
IMAGE_PAGES = range(879, 881)
FITZ_PAGES  = range(881, 893)
COLUMN_SPLIT_X = 180
LINE_TOL = 4

SECTION_HEADERS = {
    "introitus":           "introitus",
    "gradualia":           "graduale",
    "versus alleluiatici": "alleluia",
    "tractus et cantica":  "tractus",
    "tractus":             "tractus",
    "offertoria":          "offertorium",
    "communiones":         "communio",
    "cornrnuniones":       "communio",
    "antiphon":            "antiphona",
    "hymni":               "hymnus",
    "psalmi":              "psalmus",
    "cantica":             "canticum",
    "responsoria":         "responsorium",
    "varia":               "varia",
    "cantus in ordine":    "ordinarium",
}

STOP_SECTIONS = {"ordinarium"}
STOP_WORDS    = set()

_PAGE_TRANS = str.maketrans("IlOorJ!$", "11000011")


def fix_page(raw: str) -> str | None:
    c = raw.translate(_PAGE_TRANS).rstrip(".,;:'")
    if "," in c:
        c = c.split(",")[0]
    return c if re.fullmatch(r"\d{1,4}", c) else None

def is_page(w): return fix_page(w) is not None
def is_mode(w): return w in {"1","2","3","4","5","6","7","8","I"}
def norm_mode(w): return "1" if w == "I" else w

def match_section(text: str) -> str | None:
    t = re.sub(r"[^\x00-\x7f]", "", text.strip().lower()).strip()
    return next((v for k, v in SECTION_HEADERS.items() if t.startswith(k)), None)

def is_stop_word(text: str) -> bool:
    t = re.sub(r"[^\x00-\x7f]", "", text.strip().lower()).strip()
    return t in STOP_WORDS

def group_by_y(spans):
    lines = {}
    for s in spans:
        y = s[1]
        b = next((k for k in lines if abs(k - y) <= LINE_TOL), None)
        if b is None: b = round(y); lines[b] = []
        lines[b].append(s)
    return lines

def parse_tokens(tokens):
    entries, mode, parts = [], None, []
    def flush(pg):
        nonlocal mode, parts
        inc = " ".join(parts).strip().rstrip(".,; ")
        if inc or mode: entries.append((mode, inc, pg))
        mode, parts = None, []
    for tok in tokens:
        if is_mode(tok) and not parts:
            if mode is not None: flush(None)
            mode = norm_mode(tok)
        elif is_page(tok) and not (parts and fix_page(tok) in {"1","11","111"}):
            # Guard: Roman numerals I/II/III (→ 1/11/111) mid-incipit are version
            # disambiguators (e.g. "Asperges me I"), not page numbers.
            flush(fix_page(tok))
        elif tok not in {",", ";", "'", "·"}:
            parts.append(tok)
    flush(None)
    return entries


class Stream:
    def __init__(self):
        self.records = []
        self.current_type = None
        self._pmode = None
        self._pinc  = None
        self.done = False

    def feed(self, tokens: list[str]):
        if self.done: return
        full = " ".join(tokens)

        if is_stop_word(full):
            self.done = True
            return

        sec = match_section(full)
        if sec:
            if sec in STOP_SECTIONS:
                self.flush()
                self.done = True
            else:
                self.flush()
                self.current_type = sec
            return

        if self.current_type is None:
            return

        for mode, inc, pg in parse_tokens(tokens):
            if self._pinc is not None and mode is None:
                # continuation line — append to pending incipit
                inc  = (self._pinc + " " + inc).strip()
                mode = self._pmode
                self._pmode = self._pinc = None
            elif self._pinc is not None and mode is not None:
                # new entry starts before previous one got a page — emit it pageless
                if self._pinc:
                    self.records.append({
                        "chant_type": self.current_type,
                        "mode": self._pmode,
                        "incipit": self._pinc,
                        "page": None,
                    })
                self._pmode = self._pinc = None

            if pg:
                if inc:
                    self.records.append({
                        "chant_type": self.current_type,
                        "mode": mode,
                        "incipit": inc,
                        "page": pg,
                    })
                self._pmode = self._pinc = None
            else:
                self._pmode = mode
                self._pinc  = inc

    def flush(self):
        """Emit any trailing pending entry (no page number found)."""
        if self._pinc:
            self.records.append({
                "chant_type": self.current_type,
                "mode": self._pmode,
                "incipit": self._pinc,
                "page": None,
            })
        self._pmode = self._pinc = None

    def feed_spans(self, spans):
        """Feed sorted (x,y,text) spans as logical lines."""
        for y_key, line_spans in sorted(group_by_y(spans).items()):
            tokens = [t for s in sorted(line_spans, key=lambda s: s[0])
                        for t in s[2].split()]
            self.feed(tokens)
            if self.done: break


def get_fitz_col_spans(doc, pg_idx):
    """Return (left_spans, right_spans) as (x, y, text) lists, skipping page header."""
    page = doc[pg_idx]
    d = page.get_text("dict")
    left, right = [], []
    for block in d["blocks"]:
        if block["type"] != 0: continue
        for line in block["lines"]:
            for span in line["spans"]:
                txt = span["text"].strip()
                if not txt: continue
                x, y = span["bbox"][0], span["bbox"][1]
                if y < 20: continue   # skip page number / running header
                (left if x < COLUMN_SPLIT_X else right).append((x, y, txt))
    return left, right


_ENTRY_RE = re.compile(
    r"^([1-8I])[\s.]+?"
    r"([A-Za-zÀ-ÿ].{2,}?)"
    r"[\s.·,\-]*"
    r"(\d{2,4}(?:,\d+)?)"
    r"[\s.]*$"
)

def ocr_half(doc, pg_idx, left):
    mat = fitz.Matrix(2, 2)
    pix = doc[pg_idx].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    w, h = img.size
    top = int(h * 0.05)
    half = img.crop((0, top, w//2, h) if left else (w//2, top, w, h))
    return pytesseract.image_to_string(half, lang="lat", config="--psm 6").splitlines()

def feed_ocr_lines(lines, stream):
    for raw in lines:
        line = raw.strip()
        if not line or len(line) < 3: continue
        if is_stop_word(line):
            stream.done = True; return
        sec = match_section(line)
        if sec:
            if sec in STOP_SECTIONS: stream.done = True; return
            stream.current_type = sec; continue
        if stream.current_type is None: continue
        m = _ENTRY_RE.match(line)
        if m:
            mode = norm_mode(m.group(1))
            inc  = m.group(2).strip().rstrip(".,; ")
            page = fix_page(m.group(3).split(",")[0])
            if inc and page:
                stream.records.append({
                    "chant_type": stream.current_type,
                    "mode": mode, "incipit": inc, "page": page,
                })


def parse_index():
    doc = fitz.open(str(GR_PDF))
    stream = Stream()

    # Image pages: left column then right column
    for pg_idx in IMAGE_PAGES:
        if stream.done: break
        feed_ocr_lines(ocr_half(doc, pg_idx, left=True),  stream)
        feed_ocr_lines(ocr_half(doc, pg_idx, left=False), stream)

    # Fitz pages: left column then right column per page
    for pg_idx in FITZ_PAGES:
        if stream.done: break
        left_spans, right_spans = get_fitz_col_spans(doc, pg_idx)
        stream.feed_spans(left_spans)
        if stream.done: break
        stream.feed_spans(right_spans)

    stream.flush()
    doc.close()
    return stream.records


def main():
    print("Parsing GR index...")
    records = parse_index()
    print(f"Found {len(records)} entries")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["chant_type","mode","incipit","page"])
        writer.writeheader()
        writer.writerows(records)

    print(f"Written to {OUTPUT_CSV}")

    from collections import Counter
    by_type = Counter(r["chant_type"] for r in records)
    for t, n in sorted(by_type.items()):
        print(f"  {t:<15} {n}")


if __name__ == "__main__":
    main()
