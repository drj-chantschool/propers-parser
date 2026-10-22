# Graduale subsection specs — producer contract

This directory holds **agent-produced JSON specs**, one per liturgical subsection (a
day/Mass). A spec is the *input* to the deterministic backend
[`load_graduale_propers.py`](../load_graduale_propers.py), which matches each chant to
gregobase (`chant_uuid`), computes its `bbox`, enforces idempotency, and writes
`lit_part_sources` rows. **The agent produces the spec; the loader does the writes.**

## What the agent decides (and the loader does not)

For one subsection the agent answers two questions the loader cannot:

1. **Which chants are on which body pages** — the identity/part/mode/incipit checklist.
   This comes from the parsed back-of-book index, **not** from reading the engraving:
   ```sql
   SELECT page, section_type, mode, incipit, chant_uuid, match_status
   FROM chant_indices
   WHERE book = 'GRADUALE' AND CAST(page AS UNSIGNED) BETWEEN :start AND :end
   ORDER BY CAST(page AS UNSIGNED);
   ```
   (`chant_indices` replaced `gr_index_entry` on 2026-10-19; `page` is a VARCHAR printed label
   with an FK to `books`, so always CAST for ranges.)
   `section_type` → `service_part`: introitus→`in`, graduale→`gr`, alleluia→`al`,
   tractus→`tr`, offertorium→`of`, communio→`co`, sequentia→`seq`.

2. **Where each chant starts on its body page** — its vertical band, for ordering and
   `bbox`. The index gives identity but **not** body-page position. Get the start-y from
   the **text layer** (`page.get_text("dict")` block boxes, in PDF points) by finding the
   block that carries the chant's part-label / drop-cap / incipit, and **confirm by
   vision** on the rendered PNG (render at dpi=200 via fitz; on Windows fitz must save to
   a real Windows path, not `/tmp`). Set `PYTHONUTF8=1` — the chant-body text layer is
   garbled (neume syllables interleave) and printing it can crash with `charmap`.

The day/Mass heading immediately above a chant (in reading order) is its `lit_epoch`; a
heading can fall mid-page, so order chants against headings by y-position.

### ⚠ Per-annum sections are whole WEEKS, not single Sundays

Outside Lent/Holy Week (i.e. the `Tempus per annum` / Ordinary-Time and the Sunday-cycle
sections), each GR section is a whole **week** formulary, headed by a spelled-out
`HEBDOMADA < N>` (e.g. `HEBDOMADA VIGESIMA` = week 20) — NOT the roman-numeral running
header at the very top of each page (`HEBDOMADA XX`), which only names the page. Use the
spelled-out heading to delimit a week, and the `lit_epoch_slug` is the **week** slug
(`OT-OT-20`), not a Sunday day-slug (`OT-OT-20-1`).

> **Finding the span without scanning:** the `book_toc` table (`book='GRADUALE'`) has one row
> per heading with `text`, `printed_page`, `level`, `y` — query consecutive `HEBDOMADA …` rows to get
> a week's printed page span directly (e.g. DECIMA TERTIA=297 → DECIMA QUARTA=300 ⇒ OT-13 is
> p297–299, with trailing options possibly on p300 before the next heading). Pre-split
> per-subsection PDFs also exist under `graduale/1/7_tempus-per-annum/<N>_hebdomada-….pdf`
> (with `.meta.json` offsets) — handy for reading one week in isolation; they extract whole
> pages so text-layer y-coordinates match the main PDF.

**Slug per chant (the loader derives it).** Keep the spec's top-level `lit_epoch_slug` as the
**week** slug (`OT-OT-13`); the loader assigns each chant the right `lit_epoch` from its
day-specificity:
- the engraved **week-default** Mass (printed first, no day qualifier) → the week slug
  (`OT-OT-13`);
- a **Sunday-specific** year-cycle option (`Dom. anno A/B/C`, i.e. has `cycle_sun`) →
  `OT-OT-13-1` (Sunday = day 1);
- a **ferial** option (`Feria N` / `Anno I/II feria N`, i.e. has a per-chant `wkday`) →
  `OT-OT-13-N`.

Only a **per-chant** `wkday`/`cycle_sun` promotes the slug, so a day-slug spec (a Lenten
feria, Pentecost — where `wkday` is set once at the spec level) is unaffected: every chant
stays at the base slug. `wkday` mirrors the slug's day suffix: a Sunday-specific option gets
`wkday=1` (it carries a `Dom.` label), a ferial keeps its `Feria N` weekday, and the
week-default Mass stays `wkday` NULL.

A week's section is: the engraved Sunday Mass (in/gr/al/of/co), THEN a trailing block of
options that **runs past the communion and spills onto the next page(s)**, before the next
week's spelled-out heading:
- **Year-cycle Sunday options** — `Dom. anno A: …  - B: …  - C: …` lines, one per part
  that varies by year (often the alleluia, sometimes the gradual or the communion). Emit
  each as a cross-reference of the cited part with `cycle_sun` (1/2/3). Several can sit on
  one line (e.g. `anno A: Domus mea, 402. - B: Qui manducat, 383.` → two `co` rows).
- **Ferial options** — `Feria N: …` and `Anno II, feria N: …` lines (weekday Masses of
  that week). Emit each as a cross-reference of the cited part, carrying a per-chant
  `"wkday"` (Feria II=2 … Sabbato=7 — these lines DO print a weekday, so wkday is set even
  though the Sunday Mass leaves it null) and, when an `Anno I`/`Anno II` is named, a
  `"cycle_wkday"` (Anno I=1, Anno II=2; a plain `Feria N` with no Anno → omit/null = both
  years). A ferial line names only the part(s) that differ from the Sunday — emit just
  those. (`wkday`/`cycle_wkday` are per-chant overrides; chants without them inherit the
  subsection-level `wkday`.)
- **`In feriis: …`** — a ferial default. Which model applies depends on **whether the week has
  a liturgical Sunday** — NOT on engraved-vs-cross-reference (default-vs-override is orthogonal
  to engraved-vs-cited: an engraved chant can be a weekday/year override, e.g. `Mense septimo`
  engraved for Anno II feria 2; a cross-reference can be the Sunday default, e.g. an `of`/`co`
  the GR cites to another page):
  - **Normal weeks (have a Sunday)** — `In feriis` is a weekday OVERRIDE of the Sunday default.
    Emit ONE row with a `"wkdays"` LIST (the loader expands it): ferias 2–7 EXCEPT any feria
    with its own printed proper (a `Sabbato:` line ⇒ `"wkdays": [2,3,4,5,6]` and Sabbato its
    own `"wkday": 7`).
  - **Weeks 1 and 34 — NO Sunday** (perhaps the only two): Dominica I per annum is displaced by
    the **Baptism of the Lord**, and the last Sunday is always **Christ the King** — so these
    weeks have no per-annum Sunday, and their `In feriis` Mass **IS the week default**. Emit
    each such chant with NO `wkday`/`wkdays` (it sits once at the week slug); emit only the real
    `Feria N:` / `Ad libitum:` overrides as day rows.

⚠ **Continuation shorthand — parse EVERY segment.** These option blocks pack several items
onto one line and ELIDE the repeated word: `Feria 2: Loquebar, 528. - 3: In te, 296.
- 6: Caro mea, 378.` means feria **2** Loquebar, feria **3** In te, feria **6** Caro mea —
three rows. Likewise `Dom. anno A: Surrexit, 202. - C: Simon Ioannis, 574.` is anno A AND
anno C. A bare leading `- N :` or `N :` continues the SAME part's list at feria N (or anno
N). Read the whole wrapped block and emit a row for every `<n>: <incipit>, <page>` segment —
missing the tail segments is the classic error (the whole point of the review queue is to
catch it).

Because these option lines trail AFTER the engraved Sunday chants, they routinely appear at
the **top of the following page**, above that page's first spelled-out heading. Do NOT scope
a week by its engraved-chant pages alone: scan from the week's heading all the way to the
NEXT week's spelled-out heading (which may be mid-way down a later page), and capture every
`anno`/`Feria`/`In feriis` line (and every continuation segment) in that span.

⚠ **A printed rubric governs only the ONE chant that immediately follows it.** Chants of the
same genre are often grouped, so an engraved ferial chant can sit BETWEEN two Sunday-default
chants. E.g. on p311 (week 17) the rubric `Anno I, feria 6:` labels ONLY the introit
`Exsultate Deo`; the graduale `In Deo speravit` engraved just below it is the **Sunday
default**, not a feria-6 chant. Do NOT extend a `Feria N` / `Anno I` rubric over the chants
that follow the one it labels.

⚠ **A completely missing part is a parsing error, not an editorial omission.** The WEEK
DEFAULT Mass (per-annum sections are for whole WEEKS, not Sundays — the engraved set at the
week slug with no `wkday`/`cycle`) should have a FULL set — `in`, `gr`, `al` (or `tr`), `of`,
`co`. If after parsing the week default is missing one (e.g. no default graduale), you almost
certainly mis-scoped a rubric onto a week-default chant (see above); re-examine the page and
fix it. Highlight any genuine gap in review — never rationalize it as "the Graduale just
omits it."

### `wkday` — set it iff the Graduale labels the weekday

`wkday` is **always the calendar weekday**, and you set it **if and only if the Graduale
page itself specifies one** — i.e. the Mass is printed under a `Feria N` / `Dominica` /
`Sabbato` heading. Map the printed Latin label to Sun=1:

| GR heading | Dominica | Feria II | Feria III | Feria IV | Feria V | Feria VI | Sabbato |
|---|---|---|---|---|---|---|---|
| `wkday` | 1 | 2 | 3 | 4 | 5 | 6 | 7 |

If the GR gives no weekday (a date-based or title Mass — e.g. Christmas "AD MISSAM IN DIE"),
`wkday` is **null**. Do NOT derive `wkday` from the slug's trailing number: that is `seq`
(sequence within the structure), which usually equals the weekday but not always (e.g. the
O antiphons have a fixed seq but a year-varying weekday). Read the weekday off the GR page,
not the slug. (Easter-octave Friday prints "FERIA VI" → `wkday` 6.)

## The `band` field

`band` is `[ytop_pt, ybot_pt]` in **PDF points** (the text layer's native unit, ~72/inch)
— NOT dpi=200 pixels. Pick the window so it encloses **only** that chant's blocks: top
just above its part-label/drop-cap, bottom just above the next chant's start (or just
above the page footer for the last chant on a page). The loader unions every text block
whose vertical centre falls in the band and scales the result into the dpi=200 pixel
space that `books`/`bbox` use, so a band that accidentally includes the running header or
footer page-number will corrupt the bbox. Verify the computed bbox with `--dry-run`.

## Engraved vs cross-reference chants

On Lenten ferias most chants are **cross-references** — the page does not engrave the
music, it cites another page: `GR. Propitius esto, 288.` Both kinds get a row.

| | Engraved | Cross-reference |
|---|---|---|
| `engraved` | `true` | `false` |
| `mode` | required (read from part-label) | **omit** — resolved from the target page's index |
| `target_page` | omit | required (the cited page, e.g. 288) |
| `page` | the engraving's page | the **citing** page (where the citation is printed) |
| `band` | boxes the engraving | boxes the **citation line** (for review) |
| `text_src` | the citation, or null | usually `null` (none prints at a reference) |

**Identity comes from the curated index first.** A one-time pass (the retired `resolve_gr_index.py`) has already
resolved the whole back-of-book index to gregobase (`chant_indices.chant_uuid`, book `GRADUALE`,
under the edition policy + human review), so the loader reads that pre-resolved id for
each chant — on its own `page` if engraved, on the cited `target_page` if a
cross-reference — and only live-matches (below) when no usable curated id exists (no index
row, an unresolved/ambiguous row, or an ungrouped chant). The dry-run tags each row
`via index` or `via live`.

For a cross-reference the loader (when it must live-match) looks up the index entry on
`target_page`, filtered by `service_part`, to get the chant's `mode`, then matches
gregobase exactly as for an engraved chant. So a citation needs only `service_part` + `incipit` + `target_page`; the
`band` exists purely so a reviewer can render the citation line and confirm it was read
right (`printed_page_num` stays the citing page; the loader also stores `target_page` in the
row's `ref_page_num` so the cited page is recorded — NULL for engraved chants).

> **Pages are PRINTED page numbers.** A spec's `page`/`target_page` and the stored
> `printed_page_num`/`ref_page_num` are the numbers *printed on the page* (what the GR's
> own index and citations use) — the scanner-independent source of truth. The per-scan PDF
> page index (and its dpi=200 image) is derived from `books(book, printed_page_num)`; the
> loader maps printed→pdf (`printed_to_pdf`) before computing a `bbox`. In this scan the two
> coincide below ~p378 but diverge after (unnumbered plates shift later pages by +2), so use
> the printed number everywhere and let `books` resolve the image.

⚠ **Shared lines:** several citations often sit on one text line/block
(`GR. … 288. OF. … 293. CO. … 357.`). The loader boxes whole blocks, so those rows will
share one bbox spanning the line — expected, not a bug; `part_id` distinguishes them.

⚠ **Ambiguity:** if the target page's index has two entries of the same part matching the
incipit with different modes, the loader **raises** rather than guess. Disambiguate the
incipit (more words) or check the target page is right.

## Output JSON format

```json
{
  "subsection": "pasc-oct-fri",
  "label": "Easter Octave — Friday (Feria VI infra octavam Paschae)",
  "lit_epoch_slug": "<FK into lit_epoch>",
  "wkday": 6,
  "chants": [
    {
      "page": 220,
      "service_part": "in",
      "mode": 4,
      "incipit": "Eduxit eos",
      "text_src": "Ps. ...",
      "band": [ytop_pt, ybot_pt],
      "engraved": true
    },
    {
      "page": 91,
      "service_part": "gr",
      "incipit": "Propitius esto",
      "target_page": 288,
      "band": [ytop_pt, ybot_pt],
      "engraved": false
    }
  ]
}
```

- `incipit` drives the gregobase match — give it exactly as printed (the loader compares
  on letters+digits only and folds classical/medieval Latin `i↔j` and `u↔v`, so spacing,
  punctuation, OCR artifacts, and `Iacta`/`Jacta`-style orthography are all tolerated —
  but the words must be right). One-word stubs are dangerous; include enough words to
  disambiguate. (You need not normalize I/J or U/V yourself; the loader does. When that
  fold makes one chant match two un-collapsed gregobase groups with the *same* incipit,
  the loader takes the canonical/lowest group; it still refuses genuinely different
  same-prefix chants.)
  - **Verse markers:** the back-of-book index writes a gradual/alleluia as
    `Haec dies V Benedictus` — that bare `V` is the verse marker (V./℣.), not part of the
    incipit. `condense()` now strips a standalone `V`/`℣`/`℟` token, so either form matches;
    still, prefer the clean `"Haec dies Benedictus"` (and omit a leading `V.`/`℣.` on
    alleluia verses) for readability.
- `text_src` = the scripture citation printed top-right, or `null` if none is printed.
- `engraved`: `true` for chants with music on the page, `false` for a cross-reference
  (see the table above). Both are emitted and loaded.
  - **Octave-gradual hybrid (watch case):** during the Easter octave the gradual prints
    the *refrain* abbreviated with a cite (`Haec dies … etc. 196.`) but engraves that day's
    proper *verse* in full on the current page. That is **engraved here**, NOT a
    cross-reference: the verse is on this page, and the target-page index entry is a
    *different* verse (p196 = Confitemini, not Benedictus), so an xref would mis-resolve.
    Decide engraved-vs-xref by what is actually engraved on the page, by vision.

## The `office_part` override — when a chant's KIND differs from its slot

`service_part` is the liturgical SLOT a chant fills (`in`/`gr`/`al`/`tr`/`of`/`co`/…) — it
governs where the row is stored. It is a **different vocabulary** from the chant's actual
KIND (gregobase's `office-part` column / `chant_indices.section_type`) — usually they
coincide, but not always: a hymn can be sung *pro GR.* (`service_part:'gr'`, but it IS a
hymn), a responsory can stand in for a Gradual (same), an introit can gregobase-catalog as
a plain antiphon. When they diverge, set the optional per-chant `"office_part"` field to
**whatever the book's own heading/subheading says this chant IS** (e.g. `"hy"`, `"re"`) —
that's the only thing `office_part` is for. It is passed straight through to the matcher
with **no allow-list**: any gregobase office-part code is valid, not just the handful of
Mass-service-part codes this loader writes. Omit it when the KIND coincides with the slot
(the norm).

**Before reaching for `office_part`, check whether the correctly-tagged edition is simply
ungrouped.** A `LookupError` on a chant that gregobase clearly has under the *expected*
`office-part` (matching its `service_part`) is usually NOT a KIND mismatch — it's that
gregobase's own row for that edition has no `chant_group_id` (`SELECT chant_group_id FROM
gregobase_chant_group_map WHERE gregobase_id=<id>` returns nothing), so it's invisible to
`v_chant_item` and unusable as a `chant_uuid`. That's a one-line DB fix (group it with the
chant's other editions — same incipit/mode, different `version`), not a spec workaround; do
NOT paper over it by overriding `office_part` to reach a *different*, worse-edition entry
that happens to already be grouped. Report the ungrouped id and its expected group in your
handback rather than silently dropping the chant or forcing a lesser edition.

## `"unmatched": true` — a chant gregobase does not have

Rare, and **never** a way out of a failed match. Some music the Graduale engraves simply is not
in the corpus in any edition — e.g. the three responsorial psalms composed for the 1974 *Ordo
Exsequiarum* (GR pp. 681–683), which gregobase carries in no form. Such a chant is declared
explicitly and is written with `chant_uuid` NULL:

```json
{
  "page": 683, "service_part": "st1ps3", "mode": null,
  "incipit": "Misericordias Domini", "band": [40, 290], "engraved": true,
  "unmatched": true,
  "original_text": "℣. 1 Misericórdias Dómini ℟. In ætérnum cantábo. …",
  "notes": "Psalmus 88. GR prints no mode. Not gregobase rb 4015, which sets the whole phrase as one melismatic refrain rather than the GR's ℣./℟. split."
}
```

- **`original_text` is required** and must be non-empty: with no `chant_uuid` there is nothing
  else to say what the row records, and the loader's idempotency keys on it (slot + `option_txt`
  + `original_text`). Give the text as printed.
- **Only for `engraved` chants.** An unmatched *cross-reference* means the `target_page` or
  incipit is wrong — the target page engraves the chant, so it resolves there.
- `original_text` is **rejected** on a normal (matched) chant; that text comes via `chant_uuid`.
- Say in `notes` *why* nothing matched, naming the near-misses you rejected and how they differ
  (different form, different response, different melody). That is what stops the next reader
  re-doing the search — and stops anyone "fixing" it by pointing at a wrong chant.

⚠ **A `LookupError` is not grounds for this flag.** It almost always means the spec is wrong (bad
incipit/part/`target_page`) or the correct edition is simply **ungrouped** — see the
`office_part` section above. Prove the chant is absent from the corpus before declaring it:
search `gregobase_chants_texts.text_decode` (the plain-text table), **not** `gabc`, whose neume
codes interleave the words and make a `LIKE` on Latin silently return nothing. If you are not
certain, hand the chant back as a question instead of flagging it.

## Alternates and ambiguous matches (multiple rows per slot)

`lit_part_sources` has no natural unique key (only `text_id`), and the loader's dedup key
includes `chant_uuid`, so a single part on a day can legitimately become several rows:

- **Alternates (`Vel:` / `Ad libitum:` / `or:`):** when the GR prints an alternate chant
  (`Vel: Reminiscere, 81.`), emit it as an ADDITIONAL chant of the same `service_part`,
  carrying `"option_txt"` set to the printed marker (`"Vel:"`, `"Ad libitum:"`, `"vel:"`, …).
  The primary keeps `option_txt` unset/null **because the page prints no marker before it** —
  that's a fact about this specific pattern, not a general rule (see next bullet). Emit one
  such row per alternate the GR gives — they coexist (distinct `chant_uuid`). An alternate is
  usually a cross-reference (`engraved:false`, with `target_page`).
  **Binding:** a `vel:` line binds the **immediately-preceding item** — copy that item's day
  fields (`wkday`/`cycle_sun`/`cycle_wkday`) onto the alternate. E.g. `… Feria 6: Domus mea,
  402. vel: Amen dico… 368.` → the `vel` is Feria 6's (`wkday=6`). A `vel:` embedded in the
  Sunday communion's psalm line binds the Sunday default (week slug, no wkday).
- **Gospel-conditional groups (`Quando legitur Evangelium de …:`):** distinct from Vel:/Ad
  libitum — here EVERY member of the group, including the one printed first/closest to the
  base chant, can carry its own rubric (e.g. Lent 3 Sunday's communio: "Quando legitur
  Evangelium de Samaritana:" precedes the FIRST-listed option, not just the later ones).
  Do NOT reuse the Vel:-pattern assumption that "the first option has no `option_txt`" here —
  that assumption does not generalize. Check the page immediately above **each** member of the
  group for a rubric line and copy it verbatim into that member's `option_txt`, even for
  `option_num=1`. Only leave `option_txt` unset for a member that the page genuinely prints
  with no preceding rubric.
  **Length:** varchar(512), enforced at spec-read time. That is deliberately roomy enough for a
  full printed rubric (`Feria 5, in regionibus ubi sollemnitas Ascensionis in dominicam
  sequentem transfertur: Missa de dominica VI Paschae, 229, praeter:`), so copy what the page
  prints verbatim rather than truncating it. `option_txt` is for the BOOK's words; an editorial
  comment of your own goes in `notes`.
- **`notes` — an editorial note on one chant (optional, varchar 500).** Free text written to
  `lit_part_sources.notes`. Use it for something a reader of the row would otherwise question:
  a deliberate departure from what the page prints (and why), a rubric too long for
  `option_txt`, or a slot assignment the page leaves genuinely ambiguous. It records a
  judgement — it is NOT a substitute for asking about an anomaly, and never a place to bury a
  chant you could not model. On re-load a spec's note overwrites the stored one, but a spec
  with no note never blanks out an existing one, so a human's note on a row is safe.
  E.g. `pasc-ad-asc-06.json`: the Graduale prints the communio `Spiritus Sanctus docébit vos`
  under `Dom. anno C`, but per the Ordo Cantus Missae that rubric is an error in this edition,
  so the row is loaded as the week default with the reasoning in `notes`.
- **Year-cycle propers (`cycle_sun`):** some Sundays (mostly OT) print year-specific
  options, e.g. `Dom. anno A: Ostende, 31. — anno C: Beata gens, 333.` Emit each as an
  ADDITIONAL row of that part (usually a cross-reference) with `"cycle_sun"`: `1`=anno A,
  `2`=anno B, `3`=anno C. The in-place engraved/default chant gets **no** `cycle_sun`
  (null — do not assert anno B). Decide the PART from the cited chant on the target page,
  not a guess: a `Dom. anno …` line that cites graduale entries is a graduale option even
  if it sits near the Alleluia (verify via `chant_indices` on the target page).
- **Edition preference:** gregobase stores each chant in many versions (Solesmes,
  Vatican, Dominican, Palmer & Burgess, seasonal `(T.P.)` variants, …) often in separate
  un-collapsed `chant_group`s. The loader picks the edition by a fixed policy —
  **Solesmes 1974 > Solesmes 1961 > generic 'Solesmes' > Vatican > other-year Solesmes >
  everything else** (see `version_rank`) — so you do not pick a version; the loader does. When the chosen chant also exists in
  other groups at worse editions it prints `ℹ version-split: … consider merging` so those
  groups can be merged at the source. Cross-references match on the **target page's**
  full index incipit, not the abbreviated citation stub, so a short citation
  (`Beatus vir, 475`) cannot mis-match a different chant (`Beatus vir cujus`).
- **Ambiguous gregobase match (the review queue):** if an incipit resolves to more than one
  un-collapsed gregobase `chant_group` (e.g. `adjuvandum` cg 731 vs `adiuvandum` cg 18154),
  the loader does NOT pick one — it writes **one row per candidate group** and prints
  `⚠ REVIEW: 1 of N candidate groups`. These are a review queue: a human keeps the correct
  row and deletes the rest (and ideally folds the duplicate `chant_group`s at the source).
  You don't author these — the loader produces them — but expect extra rows on a clean
  dry-run when a chant is genuinely split in gregobase, and call them out in your report.

## Validate before handing back

The spec is correct only if the loader accepts it. Run a **dry-run** and confirm every
chant matched gregobase and produced a sane bbox:

```
C:\Users\johna\liturgio\.venv\Scripts\python.exe \
  propers-parser/graduale/load_graduale_propers.py --spec-file propers-parser/graduale/specs/<name>.json --dry-run
```

A `LookupError` (no gregobase/index match at all) or an empty-band `ValueError` usually
means the spec is wrong — fix the incipit/part/mode/target_page or the band and re-run
until the dry-run is clean. But before assuming that: check whether the chant's own
correctly-tagged gregobase edition is simply ungrouped (see the `office_part` section
above) — that's a DB gap to report, not a spec bug to work around. (A `⚠ REVIEW` line is
NOT an error — it is the multi-candidate review case above; the dry-run is still clean.)
Do **not** run a real write; the human runs the tiny-then-full write after review.
