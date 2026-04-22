Goal: For each proper chant in the Graduale Romanum and Ordo Cantus Officii, identify the matching chant in the local `liturgio` database and record its liturgical assignment.

We do not need to OCR the whole chant; these exist in GABC format in gregobase (mirrored into `liturgio`). We extract enough from the scan to match each chant and to determine its place in the liturgical calendar from the surrounding headings.

### Output

Each chant found produces a row in `lit_part_assignment`:

| Column | Source |
|---|---|
| `chant_group_id` | Matched via `gregobase_chant_group_map` using OCR'd incipit |
| `part_id` | Derived from the part type (Introit, Gradual, etc.) via `service_part` |
| `season`, `subseason`, `wknum`, `wkday` | Parsed from heading hierarchy |
| `cycle_wk` / `cycle_sun` | Set when heading specifies anno I/II (wknum_mod_2) or a 4-week cycle (wknum_mod_4) |
| `notes` | Explanatory rubric preceding the chant (e.g. "POST II LECTIONEM"), if present |

The hierarchy fallback logic (specific day overrides generic week) is handled by the consuming engine, not this parser. The parser's job is simply to emit the most specific assignment the heading warrants — `wkday=null` when the heading is a week, `wkday=4` when it specifies Feria IV, etc.

Plan (preliminary):

OCR of headings is the linchpin of every split operation below. All chapter, section, and subsection boundaries are detected by recognising heading text in the scanned pages.

OCR approach: segment each page to isolate text regions (stripping the staff/neumes), then run standard OCR on the text-only regions. Fall back to LLM vision if segmentation proves unreliable.

**Source book differences:** The OCO has a ToC that can drive steps 1–3 directly, bypassing heading OCR for structural splitting. The GR has no usable ToC and requires full heading detection throughout. Steps 1–3 should have two implementation paths accordingly.

1. **Split the GR into its chapters** ✓ DONE (`split_chapters.py`)
    * GR split into 8 chapter PDFs under `graduale/`
    * OCO split into 7 chapter PDFs under `oco/`
    * Test: Manual verification passed
2. Split each chapter into sections
    * Advent, Lent, Easter, Ordinary Time, Feasts of the Lord, etc.
    * Test: Pages are sequential, first page has section heading, last page has next section's heading (manual review)
3. Split each section into subsections
    * Usually by week (except Lent and some others)
    * Wherever subsection headings are found, each extracted subsection needs to include both the start/end page
    * Test:
        * In the GR, Each subsection contains no more than a few pages (Rare exceptions like Palm Sunday)
        * In the OCO, everything up to here can be done by inspecting the ToC
4. Cut the widow/orphan off each extracted subsection
    * because subsection headings can be in the middle of a page
5. Within each subsection, for each part:
    a. OCR the label above the drop-cap (e.g. "Of. IV") to extract chant kind and mode
    b. OCR the incipit text (first few words of the chant, or the plain-text page reference)
    c. Match against `gregobase_chants` / `gregobase_chant_group_map` by incipit, using kind and mode as confirmation
    d. **On uncertain match: fail and log — do not guess.** Manual fallback for ~10% of cases is acceptable.
    e. Parse the surrounding heading stack to determine `season`, `subseason`, `wknum`, `wkday`, and any cycle modifier
    f. Capture any preceding rubric text (e.g. "POST II LECTIONEM") into `notes`
    g. Write a `lit_part_assignment` row
    * Per-day/per-year overrides are treated as subheadings — they narrow the heading stack, not a separate code path
    * Whether the chant is engraved or a plain-text page reference, the incipit is always readable as text

Directory structure:

book-title/
 | book-title.pdf
 | 1/
    | 1_<chapter_name>.pdf (after phase 1)
    | 1_advent/ (after phase 2)
        | 0_advent.pdf (after phase 2)
        | 1_hebd_1_adv.pdf (after phase 3)
        | 2_hebd_2_adv.pdf (after phase 3)
        .
        .
        .
    | 3_lent/ (after phase 2)
        | 0_lent.pdf (after phase 2)
        | 1_ash_wednesday.pdf (after phase 3)
        | 2_thurs_post_cinerum.pdf (after phase 3)
        | 3_fri_post_cinerum.pdf (after phase 3)
 | 2/
    | 2_<chapter_name>.pdf
    | 2_<section_name>/
        | ...
 | 3/

PDF names are examples, but more likely it will be x_{section_name_kebab}.pdf where x is a sequential integer.


## Caveats

* Heading detection accuracy gates everything downstream — misreading a chapter or section heading cascades
* Some sections have irregular subsection structure (e.g. Lent is by day, not week) — the splitter must not assume a uniform heading hierarchy
* The GR occasionally has headings mid-page; the widow/orphan trim (step 4) must handle this without losing content from adjacent subsections
* Rubric text like "POST II LECTIONEM" is typically not bolded — distinguishing it from chant incipits requires layout/font heuristics, not just heading detection
* `chant_group_id` is the join key (via `gregobase_chant_group_map`), not the raw `gregobase_id` — the match pipeline must resolve through that map


---

## GR Index Extraction — Progress Notes (as of 2026-04-11)

Rather than OCRing the body of the book, we are working from the *Index Alphabeticus Cantuum* at the back of the GR (PDF `graduale/8/8_indices.pdf`, pages 0–13). The index lists every chant with its mode, incipit, and page number — enough to do the gregobase match without touching the main book pages.

### Approach

The index has two kinds of pages:
- **Pages 0–1**: image-only scans (no text layer) → full Tesseract OCR
- **Pages 2–13**: PDF with embedded text layer → fitz `get_text("dict")`

Each page is two columns. The parser reads left column top-to-bottom, then right column, carrying a single section-type state across the entire stream. In-column bold section headers (e.g. "Introitus", "Gradualia") update the state; page-top running headers are ignored.

### Scripts

**`parse_gr_index.py`** — primary parser
- Uses fitz text layer for pages 2–13, Tesseract OCR (`--psm 6`, lang=`lat`) for pages 0–1
- `Stream` class maintains pending-entry state across lines (`_pinc`/`_pmode`) so entries split across lines are re-joined
- `parse_tokens()` handles Roman numeral disambiguators (I/II/III appearing mid-incipit as version suffixes, not page numbers)
- Outputs `gr_chant_index_fitz_output.csv` (842 entries at last run)
- Current counts: introitus 148, graduale 126, alleluia 164, tractus 25, offertorium 115, communio 163, antiphona 45, hymnus 13, psalmus 24, responsorium 15, varia 4

**`fix_gr_index.py`** — post-processor for the fitz output
- Input: `gr_chant_index_fitz_output.csv`; output: `gr_chant_index.csv`
- Extended OCR character substitution: `str.maketrans("IlOorJ!$Sszi", "110000115521")` (adds i→1, S/s→5, z→2)
- `recover_page_from_incipit()`: extracts trailing page numbers that the parser absorbed into the incipit string
- `clean_incipit()`: strips soft hyphens and trailing dot-leader runs
- Expands comma-separated multi-page entries to multiple rows
- `MERGED_ENTRIES` dict for chants the parser ran together (e.g. "Unus militum" + "Veni, Domine")
- `find_page_number_by_ocr()`: for entries still missing a page, uses fitz `search_for()` to locate the entry on the page, then OCRs only the page-number x-zone (right margin of that column), requiring the result to be > 15 to exclude mode numbers
- OCR dedup: discards a page number if it is identical to the previous OCR result (catches a raster artifact that returns the same number for consecutive entries)

**`ocr_gr_index.py`** — independent full Tesseract pass over all 14 index pages
- Crops each page into left/right halves with 8px clearance around the printed column rule at `w//2`, to avoid the rule being read as `1` by Tesseract
- `parse_line()`: expects each line to start with a mode digit and end with a page number; everything between is the incipit
- Outputs `gr_chant_index_ocr.csv` (752 entries at last run)
- Still has quality issues (see below)

### CSV Files

| File | Description | Status |
|---|---|---|
| `gr_chant_index_fitz_output.csv` | Raw fitz parse output | Saved; input to fix_gr_index.py |
| `gr_chant_index.csv` | Fitz output after fix_gr_index.py post-processing | ~843 rows, ~17 blank pages |
| `gr_chant_index_ocr.csv` | Pure Tesseract OCR output | 752 entries, still has errors |
| `gr_chant_index_ocr_john_manual_review.csv` | John's hand-corrected introits | 165 rows; ground truth for introits |

### Known Remaining Issues

**In `gr_chant_index_ocr.csv`:**
- **Leading `0` artifacts**: some page numbers read as e.g. "017" instead of "117", "0510" instead of "510". Likely OCR reading the page/gutter edge as "0". Root cause not fully resolved.
- **Trailing noise from physical book margin**: some page numbers end with characters from the printed book margin, e.g. "1ssS" for 155, "861i" for 861. These survive the column-rule clearance fix because they come from the outer margin of the scan, not the centre rule.
- **Page number swaps for similar incipits**: clusters where Tesseract assigns the right numbers but to the wrong entries (e.g. Dicit Dominus, Gaudeamus, Miserere, Sacerdotes clusters, Suscepimus pair). These require either the fitz layer or manual review to resolve.

**In `gr_chant_index.csv`:**
- ~17 entries still have a blank page number after all post-processing. These are predominantly entries whose page numbers are absent from the fitz text layer and where targeted OCR also failed.

### Next Steps for Index

1. Reconcile the two CSVs: use the fitz-derived index as the base (better incipit quality), fill blanks using OCR output where OCR confidence is higher. Flag remaining blanks for manual review.
2. Manual review of the ~17 blank-page entries (and any other low-confidence rows) against the physical PDF.
3. Once the index is clean, proceed to gregobase matching: incipit + mode/type → `gregobase_chants` → `gregobase_chant_group_map` → `chant_group_id`.


