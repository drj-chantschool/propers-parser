# Writing Graduale subsection contents to `lit_part_sources` — dry-run learnings

Living document. Goal: work out the most efficient, reliable procedure for turning a
*subsection* of the Graduale Romanum (one liturgical day/occasion) into a set of
`lit_part_sources` rows (one per proper chant). This is exploratory — no DB writes yet.

Status: **Cycle 1 complete + corrected per user direction (2026-06-18).** See "Cycle 1 findings"
and then **"Cycle 1 follow-up"** near the bottom — the follow-up supersedes several things above
(schema, cross-ref handling, the books decision). Read the follow-up as the current truth.

> ## ⚠ SCHEMA CORRECTION (2026-06-18, from `maintenance.md`)
> `lit_part_sources` **no longer has `season`, `subseason`, `wknum`** — they were dropped and
> replaced by **`lit_epoch_slug`** (FK → `lit_epoch.slug`). Only **`wkday`** remains of the old
> set. So the liturgical assignment of a row is now: **`lit_epoch_slug` (+ `wkday` when the slug
> is a week/subseason node)**. Everywhere below that says "set season/subseason/wknum/wkday,"
> read instead "set `lit_epoch_slug` (+ `wkday`)". The mapping for the 4 test subsections and the
> rules are in the follow-up section.

---

## Target table: `lit_part_sources`

One row per proper chant of a Mass. Columns and where each value comes from:

| Column | Source / how to derive | Notes |
|---|---|---|
| `text_id` | auto-increment | don't set |
| `lit_epoch_slug` | heading stack → matching `lit_epoch.slug` (FK) | **replaces season/subseason/wknum.** e.g. day `TQ-LENT-02-1`, week `OT-OT-19`, mass `NAT-DAY-00-0-day`. See follow-up for the mapping rules. |
| `wkday` | day-of-week number, set alongside a day-level slug, or to disambiguate a week/subseason slug | Dominica=1 … Sabbato=7. NULL for OT Sundays (week-node slug) and for Christmas Mass slugs. |
| ~~`season`/`subseason`/`wknum`~~ | **DROPPED 2026-06-18** | do not set — columns no longer exist |
| `cycle_sun` | anno A/B/C or I/II marker | usually null |
| `cycle_wkday` | week-parity marker | usually null |
| `service_part` | chant kind label above drop-cap → `service_part.part_code` | **REQUIRED**. in/gr/tr/al/of/co/seq/tr2/gr2 (see table below) |
| `original_text` | the chant incipit/full Latin text | from the page — vision OCR (text layer is garbled) |
| `vernacular_text` | English translation | NOT in GR; left null for GRADUALE rows (existing GR rows have it null) |
| `text_src` | scripture citation printed top-right of the chant | e.g. "Is. 9, 6; Ps. 97", "Zach. 9, 9" — in text layer, fairly clean |
| `original_lang` | 'la' | default |
| `vernacular_lang` | null for GR | |
| `assignment_authority_code` | 'GRADUALE' | → `p_assignment_authority` |
| `translation_source_code` | null for GR | |
| `status` | 'draft' | default |
| `book` | book code, e.g. 'GR' — **FK to `books(book, pdf_page_num)`** | ⚠ `books` table is EMPTY; FK will fail until a `books` row exists |
| `pdf_page_num` | page in source PDF | part of the FK |
| `bbox` | "x,y,w,h" or start-y of the chant on the page | from heading/element y |
| `month`, `day_of_month`, `feast_title`, `common_of` | for sanctoral / fixed-date feasts | mostly null for de tempore |

### ⚠ Blocking constraint → DECISION (2026-06-18): populate `books` first
`lit_part_sources.book` + `pdf_page_num` is a **foreign key into `books`**, and `books`
is currently **empty** (0 rows). **Decision (user): populate `books` first**, seeding it with the
**page images from the Graduale Romanum** (one row per page: `book='GR'`-style key, `pdf_page_num`,
`printed_page_num`, `image_path`/`image_blob`). This makes `book`/`pdf_page_num` settable on every
`lit_part_sources` row AND makes `bbox` meaningful (a region within the stored page image).
The earlier "leave NULL / use `page_num`" fallback (what the 2 existing GRADUALE rows do) is now
the *deprecated* path — we are doing it properly. **`bbox` coordinate space = the page-image pixel
space**, which is the same space `gr_index_entry.bbox_*` already uses (x≈91–983, y≈108–1496), so
index bboxes can be carried straight across.

### Existing data baseline
- 833 rows: 831 `MISSAL` (ICEL English, no page provenance), **2 `GRADUALE`**.
- Existing `service_part` values used: only `in`, `co`, `of`. Graduale work will add `gr`, `al`, `tr`.
- All existing rows: `book/pdf_page_num/bbox` all NULL.

---

## Reference codes (from DB)

**`service_part`** (part_code → name, MASS proper parts):
`in`=Introit, `gr`=Gradual, `tr`=Tract, `al`=Alleluia, `tr2`=Tract-after-Alleluia,
`gr2`=Gradual-after-Tract (Palm Sunday), `seq`=Sequence, `of`=Offertory, `co`=Communion.

**`p_liturgical_seasons`**: ADV, NAT, TQ, PASC, OT, FOL.

**`p_liturgical_subseasons`** (season, code): ADV/I, ADV/II; NAT/DAY, NAT/OCT, NAT/PO,
NAT/IO, NAT/EPI, NAT/BAPT; TQ/LENT, TQ/HOLYWEEK; PASC/OCT, PASC/AD_ASC, PASC/ASC,
PASC/POST_ASC, PASC/PENT; OT/OT, OT/FOL.

**`p_assignment_authority`**: GRADUALE, MISSAL, OCM, OCO, LOTH1, LOTH2, CUSTOM.

---

## Source files & page convention

- Subsection index: `propers-parser/graduale/1/all_subsections.json` (155 entries; 146 with level≥0).
  Each entry: `section_num, section, subsection, level, text, pdf_page, printed_page, y`.
- **`pdf_page` (1-based) indexes the FULL book `propers-parser/graduale/graduale romanum.pdf`**
  (906 pages), NOT the chapter PDF. Verified: full-book page 47 = printed 47 = Christmas
  "AD MISSAM IN DIE". The chapter PDF `1/1_proprium-de-tempore.pdf` page 47 is a different
  page — do NOT use it for page lookup.
- `y` is the vertical start of the heading on its page; subsections can start mid-page.
- A subsection's content spans from its `(pdf_page, y)` to the next subsection's start.

### Render recipe (PyMuPDF, canonical venv)
Interpreter: `C:\Users\johna\liturgio\.venv\Scripts\python.exe`
```python
import fitz
doc = fitz.open(r'propers-parser/graduale/graduale romanum.pdf')
doc[pdf_page-1].get_pixmap(dpi=95).save('out.png')   # 0-based index
```
Then Read the PNG to view it (vision). `get_text()` also works but is **garbled**: neume
syllables are interleaved with the incipit. The text layer IS useful for the running
header (page no. + heading), the scripture citation, and the part-label/mode — but the
incipit itself is best read by vision.

### Anatomy of one chant on the page (from the Christmas render)
- A **label line** giving part + mode: e.g. `Antiphona ad introitum VII`, `CO. IV`,
  `OF. VIII`, `Gr.`, `AL.` — part kind + Roman-numeral mode.
- A **scripture citation** top-right: e.g. `Is. 9, 6; Ps. 97`.
- A **drop-cap + incipit**: large initial then the first words ("PUER natus est nobis...").
- For Introit/Communion often a **`Psalmus NN*`** line + `(Differentia : g)` after.

---

## DB access (read-only for this exercise)
`keyring.get_password('liturgio-mysql','liturgio_ro')`, then
`mysql+mysqlconnector://liturgio_ro:<pw>@localhost:3306/liturgio`. **No writes.**

---

## Cycle 1 — the four subsections under test
1. **NAT/IN NATIVITATE DOMINI/AD MISSAM IN DIE** — full-book pp. 47–50 (heading p47 y347.2).
2. **TQ/HEBDOMADA SECUNDA QUADRAGESIMAE** (a whole-week container) — pp. 88–95.
3. **PASC/INFRA OCTAVAM PASCHAE/FERIA SEXTA** — pp. 211–213 (heading p211 y182.9).
4. **OT/HEBDOMADA DECIMA NONA (XIX)** — pp. 319–322 (heading p319 y363).

---

## Cycle 1 findings (synthesized from 4 independent subagents + DB verification)

All four agents succeeded, read the chants by vision, and converged. The page convention,
render recipe, and reference codes in this doc all held up. Concrete results:

### A. The page-number / `books` FK question — RESOLVED (for now)
The **2 existing GRADUALE rows** (`text_id` 108, 109) set `book=NULL`, `pdf_page_num=NULL`,
`bbox=NULL`, and record the page in the **legacy `page_num`** column (526, 362).
→ **Recommended pattern: follow the existing GRADUALE rows — leave `book`/`pdf_page_num`/`bbox`
NULL and put the GR printed page in `page_num`.** Populating `books` (one row per page) is the
"proper" long-term fix and would let `bbox` be meaningful, but it is NOT required to write rows
now and is out of scope for a first pass. Do not invent a `book` key blindly — it will fail the FK.

### B. No uniqueness guard — IMPORTANT
`lit_part_sources` has only `PRIMARY (text_id)` plus the two FK indexes (`fk_lps_book`,
`fk_lps_epoch`). **There is NO unique constraint** on
(season, subseason, wknum, wkday, service_part, authority). So GRADUALE rows coexist with the
existing MISSAL rows (which carry *different*, Missal-recension texts for the same day) with no
DB-level dedup. De-duplication / "don't re-insert" logic must live in the loader.
(Also note an `fk_lps_epoch` FK on a `lit_epoch_slug` column that wasn't in the earlier
`SHOW CREATE` dump — verify the current column list before writing.)

### C. `wkday` is context-dependent — REFERENCE TABLE (confirmed against existing rows)
| Context | wknum | wkday encoding |
|---|---|---|
| **Christmas (NAT/DAY)** | 0 | the four Masses: Vigil=0, Midnight=1, Aurora=2, **Day=3**. So "AD MISSAM IN DIE" = wknum 0, **wkday 3** (matches existing "Puer natus est" / "Viderunt omnes" rows). |
| **Lent ferial week (TQ/LENT)** | week no. | Dominica=1, Feria II=2, Feria III=3, Feria IV=4, Feria V=5, Feria VI=6, Sabbato=7. |
| **Easter octave (PASC/OCT)** | 1 | Sunday=1 → Feria VI = **wkday 6** (confirmed by the matching Friday Introit row). |
| **Ordinary Time (OT/OT)** | week no. | **All existing OT rows have wkday=NULL** → identify the Sunday Mass by `wknum` alone; set **wkday=NULL**. |

General rule: ferial-week subsections (Lent, etc.) → Dominica=1…Sabbato=7; OT Sundays →
wkday NULL; Christmas → special Mass-of-day encoding. Always cross-check against an existing
row for the same season before committing.

### D. Whole-week container subsections (#2 Lent wk2, #4 OT wk19) — RESOLVED
The level-0 week heading is a **pure container and gets no row of its own**. Each *day* under it
(Dominica + Feria II…Sabbato) becomes its own group of rows, distinguished by `wkday`. For OT,
"HEBDOMADA XIX" in the GR is effectively just the **Sunday Mass** (5 chants); ferial OT Masses
aren't engraved per-day in the GR. Lent week 2 yielded ~30 rows across 7 days.

### E. Cross-reference chants are the DOMINANT case for ferias — KEY FINDING
On Lenten ferias, **~20 of ~30 chants are page cross-references** ("GR. Propitius esto, 288.")
rather than engraved music. Likewise some Graduals/Alleluias in Easter/OT ("Haec dies, etc. 196",
anno A/C Graduals). **Do not drop them.** Recommended representation per cross-ref chant:
emit the row, `original_text` = the printed incipit, `text_src` = NULL (no citation printed at
the reference), `page_num` = the page where the *reference* appears, plus a note/flag of the
target page. A later "resolver" pass pulls full text + citation from the target page. A small
helper that resolves target pages in the same run would let xref rows be filled immediately.

### F. Text layer = labels/citations only; incipits need vision — CONFIRMED
`get_text()` is garbled for chant bodies (neume syllables interleave: "!acta", "Namibo"), but
**reliably yields the scripture citation (top-right), the part-label + mode, and the running
header**. Use it to cross-check `service_part`, mode, `text_src`, and the page; use **vision**
(rendered PNG) for `original_text`. Set `PYTHONUTF8=1` (or reconfigure stdout to utf-8) — one
agent hit a Windows `charmap` crash printing the garbled layer.

### G. `service_part` codes beyond in/co — NEW AT SCALE
The table today holds only `in`, `co`, and a single `of`. The Graduale pass introduces `gr`,
`al`, `tr`, `of`, `seq` en masse. Column is `varchar(4)` so all codes store fine; confirm
downstream consumers accept them. Per-Mass part sets observed:
- Christmas Day & festive Masses: in, gr, al, of, co (no Sequence printed on the day page itself).
- Lent Sunday: in, gr, **tr**, of, co (no al). Lent feria: in, gr, of, co (often mostly xrefs).
- Easter octave feria: in, gr, al, of, co. **Sequence is NOT reprinted per octave day** —
  "Victimae paschali laudes" is engraved once at Easter Sunday and repeated by rubric, so octave
  ferias yield **zero `seq` rows** (whether to synthesize one is an editorial decision).

### H. Other modeling notes
- **Alternate chants** ("Vel: Reminiscere, 81") → emit an additional row of the same
  `service_part` (mirrors existing data which has 2 `in` rows for that day).
- **Per-year anno A/B/C** (mostly OT, some festive) → `cycle_sun` (proposed 1=A, 2=B, 3=C; no
  existing precedent — all current rows NULL). In-place chant = default/year-B; A & C are usually
  cross-refs to other pages.
- **`bbox` format is still undefined** (`varchar(64)`, never populated). If we keep the NULL-book
  pattern (A), bbox stays NULL and this is moot for now. If we later seed `books`, pin the
  coordinate space/DPI convention first. Agents could extract per-chant boxes via
  `get_text("dict"/"blocks")` grouped between consecutive part-labels.

### I. Per-subsection row counts produced (dry run)
| Subsection | Rows | Notes |
|---|---|---|
| NAT / AD MISSAM IN DIE | 5 | all engraved; Alleluia has no printed citation |
| TQ / Hebdomada II Quadragesimae | ~30 | 7 days; ~20 are cross-refs; Sunday has a Tract + alt Introit |
| PASC / Infra Oct. / Feria VI | 5 | Gradual "Haec dies" abbreviated (→p196); single-verse Alleluia; no Sequence |
| OT / Hebdomada XIX | 5 (+2 xref anno A/C Graduals) | Sunday only; wkday NULL; anno A/C Graduals are xrefs |

---

## Refined procedure (draft, ready for Cycle 2 validation)
1. Read the subsection's start `(pdf_page, y)` and the next subsection's start from
   `all_subsections.json`; that's the page range (respect the start-y boundary — a subsection
   can begin mid-page, and the page-top is the previous Mass).
2. If the subsection is a **level-0 week container**, expand into its child day-subsections;
   each day is a row group keyed by `wkday`.
3. Render each page (dpi≈110) and view it; in parallel dump `get_text()` for citations,
   part-labels/modes, and the running header. (`PYTHONUTF8=1`.)
4. For each chant, in order: read part-label → `service_part`; read mode (roman numeral);
   read incipit by **vision** → `original_text`; read citation (top-right) → `text_src`.
   If the chant is a **cross-reference**, set `text_src=NULL`, keep the incipit, flag target page.
5. Derive `season`/`subseason`/`wknum`/`wkday`/`cycle_*` from the heading stack using the
   context table (C); cross-check one existing same-season row.
6. Set constants: `original_lang='la'`, vernacular_* NULL, `assignment_authority_code='GRADUALE'`,
   `status='draft'`; `book`/`pdf_page_num`/`bbox` NULL, GR printed page → `page_num` (pattern A).
7. Loader must handle de-dup itself (no DB unique constraint) and a later pass resolves
   cross-reference target pages.

### Open questions for Cycle 2 / the data owner
- Confirm pattern **A** (NULL book, use `page_num`) vs. seeding `books` — this is the one real
  policy fork before any write.
- Confirm `cycle_sun` integer coding (1=A/2=B/3=C?) and whether to materialize anno A/C
  cross-ref Graduals as their own rows.
- Confirm whether to synthesize a `seq` row for octave ferias by rubric, or leave none.
- Confirm the current full column list (the `lit_epoch_slug` FK suggests the schema moved since
  the `SHOW CREATE` captured above) and whether a `lit_epoch_slug` value is expected.
- Decide the de-dup key the loader should enforce.

---

## Cycle 1 follow-up — user direction (2026-06-18)

Responses to the Cycle-1 open questions, plus three new inputs (the parsed index, instructional
text, and the right-justified commentary). **This section is the current truth where it conflicts
with anything above.**

### 1. `books` → populate first (decided)
We will seed `books` with the GR **page images** before writing `lit_part_sources` rows, so
`book`/`pdf_page_num` are set and `bbox` is meaningful. See the updated blocker box above.

### 2. "No unique constraint" — what that means (explanation)
`lit_part_sources` has exactly one key: `PRIMARY (text_id)`, where `text_id` is an
auto-increment surrogate. There is **no UNIQUE index on the natural/business key** (the thing that
identifies a chant-slot: `lit_epoch_slug` + `wkday` + `service_part` + `assignment_authority_code`
[+ an option index for alternates]). Consequences:
- **Nothing stops duplicate inserts.** Re-running the loader would happily insert the same chant
  twice and the DB would not complain. **Idempotency is the loader's job** — it must check
  "does a row for this (slug, wkday, part, authority, option) already exist?" before inserting
  (or use an upsert keyed on those columns).
- **MISSAL and GRADUALE rows for the same day coexist on purpose** (different books, different
  texts). That's fine and intended; the authority code distinguishes them.
- Contrast: `lit_part_assignment` *does* have a real unique key (`uq_lit_part_assignment_v2`,
  9 cols incl. `option_num`, per maintenance.md). `lit_part_sources` does not — so we either add
  one or enforce dedup in code. **Open: decide and, ideally, add a unique index** on the natural
  key so the DB guards it.

### 3. Schema correction absorbed
Done — see the SCHEMA CORRECTION banner at top and the `lit_epoch_slug` row in the target table.
**Slug + wkday mapping for the 4 test subsections** (verified against existing rows):
| Subsection | `lit_epoch_slug` | `wkday` |
|---|---|---|
| Christmas AD MISSAM IN DIE | `NAT-DAY-00-0-day` (a `kind='mass'` node) | NULL |
| Lent wk2 — per day | `TQ-LENT-02-1` (Dom) … `TQ-LENT-02-7` (Sab) | 1 … 7 |
| Easter octave Friday | `PASC-OCT-01-6` | 6 |
| OT week 19 (Sunday) | `OT-OT-19` (the **week** node, not `-1`) | NULL |
Rule of thumb: use the most specific existing `lit_epoch` node. For Lent/Easter ferial days a
day node exists → use it and set `wkday` to the day number. For OT Sundays the existing convention
is the **week** node with `wkday` NULL. For Christmas, the four Masses are `kind='mass'` leaf nodes
under `NAT-DAY-00-0` with `wkday` NULL.

### 4. "Why a later resolver pass?" — answer: it's NOT needed (revised)
My Cycle-1 doc proposed deferring cross-reference resolution to a later pass. That was because,
*looking only at the page*, a cross-ref ("GR. Propitius esto, 288.") points to music engraved in a
different subsection. **But we don't need the page for that** — the parsed index resolves it
**inline** (see #5). So: resolve cross-references at parse time via an index lookup; no second
pass. The only thing genuinely deferrable is pulling the *full Latin text* of a referenced chant,
and even that is better sourced from the matched gregobase chant than from re-OCR.

### 5. Use the parsed index `gr_index_entry` (843 rows) — big simplification
The index is already in the DB and gives, **per page**: `section_type` (→ `service_part`), `mode`,
`incipit`, `bbox_x0..y1` (page-image pixel space), `col`. This means:
- **Which chants are engraved on a page is known up front** — query
  `SELECT * FROM gr_index_entry WHERE page BETWEEN <start> AND <end>`. Verified for our pages:
  e.g. p47 → introitus "Puer natus est" (mode 7, bbox), p48 → graduale "Viderunt omnes", etc.
- `section_type` → `service_part` map: introitus→`in`, graduale→`gr`, alleluia→`al`,
  tractus→`tr`, offertorium→`of`, communio→`co`, sequentia→`seq`, antiphona→(context), hymnus→…,
  psalmus→…. So **part-type, mode, incipit, and bbox come from the index, not vision.**
- **Cross-references resolve here too:** "Propitius esto, 288" → `gr_index_entry` row at page 288
  (graduale, mode 5, full incipit, bbox). Resolve by the cited page number (most reliable) or by
  incipit match.
- **Boundary still matters:** the index lists *every* chant on a page including the tail of the
  previous Mass (p47 also returns the Aurora Mass's communio "Exsulta filia Sion"). Filter by the
  subsection's start-`y` (compare against `bbox_y0`) to drop chants above the heading.

So the agent should be **handed the index slice for its page range** instead of identifying chants
by eye. Vision becomes a *verification* step (and a fallback when the index missed/garbled an
entry), not the primary extraction path. `original_text` (full antiphon, not just incipit) is best
taken from the **matched gregobase chant** (`gregobase_chants_texts` via
`gregobase_chant_group_map`), using the index incipit + mode + part as the match key.

### 6a. "New `service_part` codes" — what I meant (explanation)
Today `lit_part_sources` contains only `in` (Introit), `co` (Communion), and a single `of`
(Offertory) row — because the data loaded so far is Missal Introit/Communion antiphons. The
Graduale supplies the **full Mass-proper set**: `gr` (Gradual), `al` (Alleluia), `tr` (Tract),
`seq` (Sequence), plus `of` and the rare `gr2`/`tr2`. All are defined in the `service_part`
reference table and the column is `varchar(4)`, so storing them is fine. My flag was only: **this
GR pass will be the first to populate `gr`/`al`/`tr`/`seq` at volume**, so any downstream code or
query that implicitly assumed "only in/co/of exist" should be checked.

### 6b. Instructional / rubric text → flag as "instructional", keep as memory items
The GR body is peppered with **rubrics that are not chants**: e.g. "Cantus ut supra, die 4 martii",
"Progrediente processione, cantatur:", "Omittitur Kyrie eleison, cantatur Gloria in excelsis",
"AD MISSAM IN DIE", "T.P. Alleluia", "Vel:" alternates, "(Differentia : g)". **Do not try to model
these as chant rows and do not hard-group/discard them** (we'd lose context). Instead **flag each
as `instructional`** and preserve it as a **memory item** (small, human-readable notes), so the
rubric's meaning stays attached to the place it occurred. Keep the list small; revisit if it grows.
(This is a parsing-output category, distinct from `lit_part_sources` rows.)

### Aside — capture the right-justified "commentary" (scripture source) above each engraved chant
The 1974 GR prints, right-justified above each engraved chant, a **source citation** (e.g.
`Is. 9, 6; Ps. 97`, `Zach. 9, 9`, `Ex. 12, 14`). This is the `text_src` field. **It is new in the
1974 Graduale and absent from the older editions that most `gregobase_chants` derive from** — so it
is genuinely additive data worth extracting from the scan (the matched gregobase chant won't have
it). It is **not** in `gr_index_entry`; it must be read from the page — and it's reliably present in
the **text layer** (top-right of the chant block) as well as by vision. Capture it into `text_src`
for every engraved chant; for pure cross-reference chants no citation is printed at the reference
(pull it from the target page's engraved instance if needed).

### Revised procedure (v2) for Cycle 2
1. From `all_subsections.json` get the subsection's `(pdf_page, y)` and the next subsection's start
   → page range + start-y boundary. Expand level-0 week containers into their day children.
2. **Pull the index slice:** `gr_index_entry WHERE page BETWEEN start AND end`; drop entries whose
   `bbox_y0` is above the start-y on the first page (previous Mass's tail). This yields the ordered
   list of (service_part, mode, incipit, bbox, page) — engraved chants — with no vision.
3. For each engraved chant: match to gregobase (`gregobase_chant_group_map` via incipit+mode+part)
   → `original_text` (full Latin) and the `chant_group` linkage; read `text_src` (citation) from
   the page text layer (vision to verify).
4. Resolve any **cross-reference** chants named in the page rubrics via `gr_index_entry` (by cited
   page number, else incipit) — inline, no later pass.
5. Determine `lit_epoch_slug` (+ `wkday`) from the heading stack per the #3 mapping rules.
6. Set constants: `original_lang='la'`, vernacular_* NULL, `assignment_authority_code='GRADUALE'`,
   `status='draft'`; **`book`/`pdf_page_num` set** (books now seeded), `bbox` from the index entry.
7. Emit non-chant rubrics as `instructional` memory items (6b), not rows.
8. Loader enforces idempotency on the natural key (#2) — ideally back it with a UNIQUE index.

### Cycle 2 test — v2 procedure run end-to-end (dry run, Easter octave Friday)
Ran steps 1–6 programmatically on PASC / Infra Octavam / **Feria Sexta** (`PASC-OCT-01-6`, wkday 6).
Index slice (pp. 211–213) → 5 engraved chants; matched each to gregobase by incipit+`office-part`+
`mode`; pulled full `original_text` (`gregobase_chants_texts.text_decode`) + `chant_group_id`;
attached `text_src` citations; set slug/wkday/book/pdf_page_num/bbox. **4 of 5 matched cleanly**
(gr→cg 416, al→cg 627, of→cg 151, co→cg 1260, all with correct mode/part). Two refinements surfaced:

- **Index incipits carry OCR spacing artifacts.** The Introit's index incipit is `"Eduxiteos"`
  (missing space) vs gregobase `"Eduxit eos"` → prefix match failed. **Fix:** normalise whitespace
  on both sides before matching (strip/collapse spaces, compare condensed forms), and fall back to
  fuzzy match; flag low-confidence matches for review (per the plan's "fail, don't guess").
- **Chant order must come from `service_part.sort_order`, not `bbox_y0`.** On two-column pages the
  Alleluia (left col) sits physically above the Gradual (right col); sorting by raw y put `al`
  before `gr`. Order each Mass's rows by the canonical part order (in<gr<al<tr<seq<of<co) — or use
  column-aware reading order (`col` then `bbox_y0`) — not raw y.

Matching key confirmed: **incipit + `office-part` + `mode`** is necessary and sufficient — incipit
alone is ambiguous (e.g. "Haec dies" returns both a mode-2 Gradual and a mode-8 Alleluia). The
gregobase match yields full Latin text *and* `chant_group_id` (the join key the plan wants), so
`original_text` should come from the matched chant, not OCR; vision/text-layer is only needed for
`text_src` (the citation) and boundary checks.

### Still-open (smaller) questions
- `cycle_sun` integer coding (1=A/2=B/3=C?) and whether to materialize anno A/C cross-ref Graduals
  as their own rows (with `cycle_sun` set).
- Whether to synthesize a `seq` row for octave ferias by rubric (none is printed there).
- Add a UNIQUE index on the `lit_part_sources` natural key, or enforce dedup only in the loader?
- Antiphona/hymnus/psalmus `section_type`s → which `service_part` codes (office vs mass)?
