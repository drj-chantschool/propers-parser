# subsections_ai.json — cleanup notes (Proprium de Sanctis / book 3)

Source: `subsections_raw.json`, produced by `detect_subsections.py`'s regex-based
heading detector. That detector assigns `level` from text content alone
(`level=1` if the line contains "die"; `level=2` if it contains "S."/"SS.";
`level=0` otherwise), so it frequently misclassifies lines and splits a single
heading across multiple array entries. This pass reconstructs the intended
3-level structure — **0 = month, 1 = day ("Die N mensis" / "Eodem die" /
"Eadem die"), 2 = feast title** — and drops everything that isn't a heading
(chant incipits, psalm/scripture citations, cross-references to other days,
neume/solfège text fragments, OCR noise).

Result: 393 entries (12 months, 189 day headings, 192 title/mass-part
entries), down from 578 raw entries.

## Structural fixes

- **Merged split headings.** Many headings were split across 2–3 raw array
  entries because the mis-leveled continuation line didn't match the "S."/"SS."
  pattern (e.g. `"S. FRANCISCI DE SALES,"` + `"EPISCOPI ET ECCLESIÆ DOCTORIS"` →
  one title). Continuation lines are merged forward as long as they're
  mostly-uppercase and don't look like a new heading or a citation.
- **Reclassified titles that were tagged level 0.** The raw-file heuristic only
  promotes a line to level 2 if it contains "S."/"SS.", so titles that don't
  (Marian feasts, "IN ___ DOMINI" formulas) were left at level 0 and would have
  been dropped as noise. Any level-0 line immediately following a day heading
  that looks like a real heading (not a citation) is now treated as the title:
  `IN PRÆSENTATIONE DOMINI` (Feb 2), `IN ANNUNTIATIONE DOMINI` (Mar 25),
  `IN VISITATIONE B. MARIÆ VIRGINIS` (May 31), `B. MARIÆ VIRGINIS DE MONTE
  CARMELO` (Jul 16), `IN TRANSFIGURATIONE DOMINI` (Aug 6), `B. MARIÆ VIRGINIS`
  ×2 — Assumption Aug 15 and Immaculate Conception Dec 8, both set in a much
  larger point size (17.1 / 17.8 vs. the usual 7–11) — `B. MARIÆ VIRGINIS
  REGINÆ` (Aug 22), `IN NATIVITATE B. MARIÆ VIRGINIS` (Sep 8), `B. MARIÆ
  VIRGINIS PERDOLENTIS` (Sep 15), `B. MARIÆ VIRGINIS A ROSARIO` (Oct 7),
  `IN PRÆSENTATIONE B. MARIÆ VIRGINIS` (Nov 21).
- **"AD MISSAM" / "AD MISSAM IN VIGILIA" / "AD MISSAM IN DIE"** promoted to
  level 2 (sibling of the feast title) wherever they occurred, regardless of
  their raw level (0 or 1 depending on incidental wording). These mark a
  genuinely separate Mass formulary under the same calendar day (Nativity of
  John the Baptist Jun 24, SS. Peter & Paul Jun 29, Assumption Aug 15) and, for
  Candlemas (Feb 2), the point in the rite where the candle-blessing procession
  ends and the Mass proper begins.
- **Bare `"Die"` / `"S."` fragments** where the day-number or saint's name had
  been extracted as a separate array entry (e.g. `"Die"` + `"11 februarii"`,
  `"S."` + `"SEBASTIANI, MARTYRIS"`) were reassembled into one entry.
- **One movable-date heading**: `"Sabbato post dominicam II post Pentecosten"`
  (Immaculate Heart of Mary) doesn't match the "Die N mensis" pattern at all
  and was being dropped as noise; it's now recognized as a day-level heading
  like any `Die` entry. It's the only movable feast in this volume — everything
  else in the Sanctorale is a fixed calendar date.
- **One out-of-reading-order fragment (Sep 16, page 74).** The extractor
  emitted this feast's title fragments in the wrong order because of a
  two-column layout: `"SS. CORNELII,"` and `"MARTYRUM"` came out *before* the
  `Die 16 septembris` heading, and `"PAPÆ, ET CYPRIANI, EPISCOPI,"` (the middle
  clause) came out *after* it. Reassembled by hand into `"SS. CORNELII, PAPÆ,
  ET CYPRIANI, EPISCOPI, MARTYRUM"`, placed after the Die heading.

## Day-number OCR fixes

This edition's typesetting renders the digit "1" as a bare roman-numeral-style
"I" (and occasionally a lowercase "r") wherever it appears inside a two-digit
day number — e.g. `"Die I 7 martii"` → 17, `"Die 2I aprilis"` → 21, `"Die r
iunii"` → 1. This is completely mechanical and was fixed for all 30 affected
`Die` entries (verified each against its known feast — e.g. `Die 31 ianuarii`
= St. John Bosco, `Die 1 novembris` = All Saints). One month-name typo,
`"apriJis"` → `aprilis`, was fixed the same way. General body-text OCR
artifacts (the Æ ligature rendered as `£`, `il£`, `IJ£`, or lowercase-mixed
fragments like "MARGARITlE") were **left uncorrected** in feast titles,
matching the existing convention in `graduale/2/subsections.json` (which
likewise keeps a similar artifact, "misericordire" for "misericordiae",
uncorrected) — this index is a structural/navigational aid, not the
authoritative source text, and producer agents read the actual PDF page.

## Missing month headers (synthesized)

`MAIUS`, `SEPTEMBER`, `OCTOBER`, `NOVEMBER`, and `DECEMBER` never appear as
level-0 headings anywhere in the raw extraction — every one of these months'
first `Die` entry sits at the very top of a page with nothing above it. (The
other seven months — IANUARIUS, FEBRUARIUS, MARTIUS, APRILIS, IUNIUS, IULIUS,
AUGUSTUS — all have a normal, cleanly-extracted month header.) This looks like
a genuine gap in the source PDF's text layer for those five page transitions,
not a one-off mis-extraction. I synthesized a level-0 entry for each, marked
`"synthesized": true`, using the correct Latin nominative and the same page as
that month's first `Die`, with `y` estimated ~25pt above the first day heading
(matching the offset seen between real month headers and their first `Die`).
**If exact position matters, verify these five against the source PDF —
their `y` values are inferred, not extracted.**

## Known gaps (left incomplete, not fabricated)

A few titles are missing text that was never captured in the raw extraction at
all (no stray continuation line to merge — the gap is in the source, not an
artifact of my merge logic). Left as-is rather than guessing:

- **Sep 14** (`Die 14 septembris`, Exaltation of the Holy Cross) has no title
  entry at all between the Die heading and the next Introit citation.
- **Oct 16** (`Die 16 octobris`) title is a bare `"S."` — the saint's name
  (traditionally St. Hedwig) was never extracted. The same day's second feast
  (`Eadem die`, Margaret Mary Alacoque) has its full title.
- **Dec 12** (`Die 12 decembris`) title ends mid-phrase: `"S. IOANNÆ
  FRANCISCÆ DE CHANTAL,"` with a trailing comma and no continuation.
- **Sep 29** title `"SS. MICHAELIS, GABRIELIS ET RAPHAELIS,"` is missing its
  final word (presumably "ARCHANGELORUM") — same situation, no continuation
  line exists in the raw data to merge.

## Out-of-calendar-order entry (kept as found)

`Die 14 augusti` (St. Maximilian Kolbe, canonized 1982 — a late addition to
the calendar) appears on page 65, *after* `Die 29 augusti`, rather than in
chronological position between Aug 13 and Aug 15. This matches the actual
PDF layout (an addendum at the end of the August section) and was **not**
reordered. A separate line on page 58 — `"Die I4 aug., S. Maximiliani Marire
Kolbe, 596."`, a cross-reference sentence pointing to page 596 — was dropped
as body text rather than treated as a second `Die 14 augusti` heading.

## Dropped as noise (not headings)

- Chant/Mass-part citations: `CO.`, `AL.`, `GR.`, scripture references
  (`Ps.`, `Is.`, `Io.`, `Act.`, `Phil.`, etc.), and reused-chant cross-refs
  like `"Lex Domini irreprehensibilis, 86."` and `"Quinque prudentes
  virgines, 507."`.
- `"Cantus ut supra, die N mensis."` and similar same-day rubric notes that
  reference another date's chant (these are body text within a subsection,
  not new subsection headings).
- Neume/solfège text remnants (hyphenated syllable fragments like
  `"Domi-ne"`) and private-use/control-character OCR garbage.
- The two candle-procession rubrics for Candlemas, `"Progrediente
  processione, cantatur :"` and `"Ingrediente processione in ecclesiam,
  cantatur :"` — these label a single antiphon within the existing Mass
  rather than a distinct formulary, unlike the `AD MISSAM` markers, so they
  were treated as content rather than structure.
