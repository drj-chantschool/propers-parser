# OCO — index-rows stage: instructions for the `index-row-resolver` agent

You resolve ONE `chant_indices` row of the Ordo Cantus Officii (book `OCO`, unit `r<row_id>`) and
write ONE verdict file. Follow `.claude/agents/index-row-resolver.md`; this file overrides it where
they differ. **No DB writes.** Do NOT delete `propers-parser/_tmp`.

## What a unit is here

In OCO the index IS the assignment list. Each row's codes (`day_code` | `hour_code` | `place_code`,
legend OCO pp1210–1213) say where the chant is sung. The director turns them into
`lit_part_sources` rows deterministically (`oco/oco_sigla.py`, `oco/load_oco_lps.py`). Your job is:
1. **identity**: which gregobase chant, or which chant_group, the engraving is;
2. **assignment**, only when `show_row.py` prints `LPS TARGETS: <reason>` (the codes can't name the
   day, e.g. "2 saints on 3/2"): read the page and say which epoch slug(s) it is.

## Start here

```
..\.venv\Scripts\python.exe oco\show_row.py <row_id>        (PYTHONUTF8=1)
..\.venv\Scripts\python.exe tools\render_page.py --book OCO <page>
```
`show_row.py` prints the row and siblings, the LPS targets, the TOC heading in force, the engraving's
full text (OCO prints it in white above each staff, plus a visible ref line such as
`cf. Ier 31,10; CAO 1428; ARII 3`), and every gregobase candidate whose text matches or whose
cantusid equals the CAO number, with its chant_group, sources (`7:327` = AM 1934 p327; 6 = ARII
2009, 24 = PM 1981, 56 = Liber Responsorialis, 9 = AR 1912, 48 = Liber antiphonarius 1960) and the
opening of its gabc.

## Identity rules

- Compare the engraving (render the page) with each candidate's gabc: opening neumes and one
  cadence, and the end of the text (OCO often prints the SHORT form: 'Ad te de luce vigilo, Deus.'
  vs a gabc continuing 'ut videam…'). Mode must agree.
- Several candidates in DIFFERENT groups are common: gregobase splits versions of one antiphon across
  groups. Pick the one whose melody matches the engraving; prefer an edition the ref line cites.
- **`group` verdict** (allowed for OCO, user ruling 2026-10-20): the text matches and every candidate
  in ONE chant_group fits the engraving equally (differences only in edition details), so no single
  edition is better. Give `chant_group_id`, no `chant_uuid`.
- `link`: one chant fits clearly better (melody, text form, cited edition).
- `unmatched`: no gregobase chant is this chant (same text + different melody = unmatched). Say
  what is closest.
- `ambiguous`: two different melodies fit equally → `question` with options, one recommended.
- `- cum alleluia`, `... all.`, `TP` variants and numbered settings (`Ecce Agnus Dei 1` / `2`) are
  DIFFERENT chants: match the one this row's engraving prints (siblings help).

## Cross-check every assignment against the TOC

`show_row.py` prints the TOC heading in force on the page. The slug(s) you accept or give must agree
with it when the engraving is the row's own (the PDF named dest, e.g. `A[6P6,L,B ante Asc]`, starts
with the row's day code). Engravings that belong to another day/common are legitimate (the index
reuses them) — then the codes decide, not the page. A disagreement you can't explain → `question`.

- **Easter week 6, Thu–Sat (`6P5`, `6P6`, `6P7`) is ambiguous by code alone.** Before Ascension
  (Ascension moved to Sunday) = `PASC-AD_ASC-06-d`, pp336–339 (TOC: Feria V/VI/Sabbato before 'In
  Ascensione Domini'); after Ascension (Thursday) = `PASC-POST_ASC-06-d`, p350 (TOC 'Post Ascensionem
  Domini → Hebdomada VI Paschae'). The place qualifier `ante Asc` / `post Asc` decides; a row with neither
  must be decided from the page/TOC in `assignment`, never guessed. (`2-7P6`/`2-7P7` psalm antiphons go
  on both.)
- Multi-saint dates: the mapper already places a row whose page lies in exactly one of the date's TOC
  sections ('Die 3: S. Blasii' / 'Vel: S. Ansgarii'). Otherwise give `assignment` from the page.

## The index link can point to the wrong engraving (user, intake #14)

The PDF link often goes to the FIRST engraving of a text (e.g. a psalter-week Vespers page) even when the
row's own day/hour has its own engraving elsewhere (e.g. the complementary psalmody pp698-700, a
feast's own page). If the TOC heading in force on the linked page doesn't fit the row's codes, search for
an engraving of the same text under the right heading (`show_row.py` + the TOC; the white text layer is
searchable). If you find it, identify THAT engraving and give `index_fix` {"column": "page", "from": "<old>",
"to": "<new>", "why": "…"}. Same text, different melody → different chant.

## B1/B2/B3 and M1/M2/M3 (user, intake #12/#16/#22)

They are ALTERNATIVE Benedictus / Magnificat antiphons (option 1/2/3, fixed by the code) for an office
on a date with several saints. YOU give the epoch: read the page/TOC and the rubrics, and give
`assignment.slugs` (one or more of the date's saints, e.g. `["st-blaise"]` or `["st-blaise","st-anskar"]`).
A trailing `TP` = Paschaltide (the mapper adds the option_txt). `TpA` is not settled: say what the page
shows in `evidence`, no assignment. If the row is ALREADY identified (`show_row.py` prints a
chant_uuid/chant_group_id with a status), check that identity and write verdict **`assign`** (identity
untouched, only `assignment`); if the identity looks wrong, `question` instead.

## Pages are PRINTED pages

The master PDF is v.6, which lacks printed p974: from p975 on, PDF page = printed − 1. All tools
(`show_row.py`, `render_page.py`) take printed pages; never open the PDF by page index yourself (use
`oco/oco_pages.py`). The white text layer can be wrong: on p184 it belongs to another antiphon than the
engraving ('Amen dico vobis, quia nemo' engraved, 'Amen amen dico vobis: Non Moyses' in the hidden text).
Trust the engraving.

## Rows without a page (`page` NULL)

The PDF link was broken. Vigil-canticle sets (`hour_code` Ol, `place_code` C/CV, codes like `41Ded`)
are engraved in the Appendix "Antiphonae ad cantica vigiliarum", pp1179–1200; the p1230 'Alleluia'
rows are Paschal-weekday psalter antiphons. Find the engraving, give `index_fix`
`{"column": "page", "from": null, "to": "<p>", "why": "…"}`, and still resolve the chant.

## Verdict file — `oco/index/resolve/r<row_id>.json`

```json
{"row_id": 6128, "verdict": "link | group | unmatched | ambiguous | index_error | assign",
 "chant_uuid": "gregobase:9785", "chant_group_id": null,
 "evidence": "p587 L.1 'Ad te de luce vigilo, Deus.' m7 short form; 9785 (AM p327) same neumes c3 e g h i i … ends 'Deus' ≠ 11116 (continues 'ut videam')",
 "rejected": [{"chant_uuid": "gregobase:11116", "why": "long form"}],
 "assignment": null,
 "index_fix": null,
 "question": null}
```
`assignment` (only when LPS TARGETS gave a reason): `{"slugs": ["st-blaise"], "wkday": null,
"option_txt": null, "rank_codes": null, "evidence": "p726 heading 'Die 3: S. Blasii'; slug from
proper_of_saints month 2 day 3"}`. Slugs must exist (`SELECT slug FROM lit_epoch WHERE slug=…`);
never invent one — if none fits, put it in `question`.

## Report (≤ 8 lines)
`OUTPUT: <path>`, verdict, chant_uuid / chant_group_id, the decisive evidence, the assignment if
any, anything for the director, and "no DB write performed".

## Stage `conflicts` (queue `oco/queues/conflicts.json`) — a different job

The row's identity is already set. `show_row.py` prints `HELD CONFLICT:` — another chant already holds
option 1 of the same slot (mostly hymns: two Office-of-Readings hymns for one weekday, a second melody
"… 2", two hymns at one feast's Lauds). Hymns have no page: render the `PAGES citing this hymn` and read
the rubric that introduces this hymn next to the other one.

- **Obvious** (the page prints a rubric that makes it an alternative: "Quando Officium lectionis dicitur
  noctu / diu", "Alia melodia", "Vel:", "ad libitum") → verdict `option`, `option_txt` = that rubric in
  the book's words (Latin, short). It loads as the slot's next option.
- **Not obvious** (no rubric, or the two hymns seem to be for different hours/days than the codes say)
  → verdict `hold` with a `question` (options, one recommended). Nothing loads; the user decides.
- **Index-only second melody** (user, intake #26): the hymn index has two rows for this slot, same hymn
  text, LHym N and another LHym number, but the page names only one → verdict `option`, `option_txt`
  `Alia melodia (LHym <this row's N>)`. Not a `hold`.

```json
{"row_id": 5682, "verdict": "option | hold", "option_txt": "Quando Officium lectionis dicitur diu",
 "evidence": "p613: two hymns under Ad Officium lectionis, second headed 'Quando … diu' …",
 "question": null}
```
