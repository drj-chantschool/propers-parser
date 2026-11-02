# Ordo Cantus Officii — producer instructions (stage `pages`)

For the `content-producer` agent on book `OCO`. Read with `.claude/agents/content-producer.md`; where they
differ, this file wins.

## The goal

`lit_part_sources` must say, for every liturgical act this book covers, which chant the book assigns,
**as the page prints it**. You own ONE printed page. The index (`chant_indices`) and the PDF's links are
there to help you find and identify chants; they are not the assignment. When the index codes disagree
with the page, the page wins: model the page and add a `flags` line. Don't ask about it and don't edit the
index.

## What you produce

ONE spec, `oco/specs/p<NNNN>.json` (4-digit pad), recording every engraving that begins on the page and
every cue printed on it. Contract: `oco/specs/README.md`, in full (page rule, fields, services, assignment
conventions, Identity, User rulings, Known quirks).

## Step 1: the draft and the page

```
cd C:\Users\johna\liturgio\propers-parser
set PYTHONUTF8=1
..\.venv\Scripts\python.exe oco\page_draft.py <page>
..\.venv\Scripts\python.exe tools\render_page.py --book OCO <page> <page+1>
```
Read the draft summary, then the PNG (add `--zoom top|bottom` for small print). The previous page's spec
`context_out` gives the headings in force at the top (day, hour, rubric); if it's missing, read earlier
pages back to the last heading, and use the draft's `TOC:` line.

## Step 2: check the draft against the page, mark by mark, top to bottom

For each item on the page:
- **Engraving that begins here** (drop cap + mode + staff): one row per act it is assigned to. The draft's
  proposal comes from the engraving's own destination code; confirm epoch, service, part, day fields and
  option from the page's heading, hour label, siglum and rubric. Fix whatever the page contradicts.
- **Engraving continued from the previous page**: `continues`, no row.
- **Cue line** (siglum + text, no staff): an `xref` row. Hymn `Name (LHym N)` → `ref_book` LIBER_HYMNARIUS,
  `ref_page` N, identity = the cue's gregobase link (the draft gives it). Linked cues (`Ut in hebd. I.`,
  `Vel: …`, `…, de Communi pastorum`) → `ref_book` OCO, `ref_page` = the link's target page. Unlinked cues
  (`Iste confessor ut ad Vesperas`, `ut supra`): find the cited engraving or cue yourself.
  A `vel` inside a cue line is a second row (option 2, or `option_num` null).
- **Rubric** (italic): sets options and conditions for the rows it governs, up to the next rubric or heading.
  Record it in `rubric`. A condition becomes structure whenever the data model can hold it: a subject ("pro
  pluribus", "pro una virgine") → the sub-epoch; year, rank, week, weekday → their fields (contract:
  "Structure before option_txt"). Only what no field or epoch expresses becomes `option_txt` (book's words, short).
- **Headings** (`Die 11: S. Martini Turonensis`, `Feria II`, `Pro cunctis diebus`, `Hebdomada II`): the epoch.
- **Whole-office references** (`Omnia ut in Officio Defunctorum.`): `inherits`, not rows.
- **Anything else** you can't place: `questions` (it blocks the page; that's fine).

The draft's NOTES list what it couldn't place. Resolve each one in the spec (a row, a flag, `continues`) or
explain it in `flags`. An index row that "links here but was not placed" is usually a reuse cued on another
page: flag it only if this page seems to print it.

## Step 3: identity, for every row

Read the contract's **Identity** section. For each engraved row:
1. If the row has an identity (`index_id` with a chant, or explicit), check it in the dry-run's `✓?` line and,
   unless the ref line cites that very edition, compare the gabc's opening neumes, one cadence and the Euouae
   with the engraving.
2. If it has none: `..\.venv\Scripts\python.exe oco\candidates.py "<engraving text>" --cao <N> --mode <m>`
   (and `oco\show_row.py <row_id>` when there is an index row). Pick by melody; `chant_group_id` only when
   every member fits equally; `allow_unresolved` + flag when nothing is this chant.
Write the decisive evidence in `notes` (e.g. `p587 8g; 9785 opening c3 e g h i i matches; 11116 long form`).

## Step 4: write and validate

Checkpoint the spec early (valid JSON at every save). Then:
```
..\.venv\Scripts\python.exe oco\load_oco_page.py --spec oco\specs\p<NNNN>.json --dry-run
```
Iterate to `DRY-RUN OK` (exit 0), or exit 3 with genuine `questions`, or exit 4 when a cited page isn't loaded
yet (say so; it is not your error). Read every `ADOPTS` / `REPLACES legacy` line: a replacement is right only
when the page really prints a different chant in that slot; otherwise your slot fields are wrong.

## Report (≤ 15 lines)

1. `SPEC: <path>` and `PAGE_KIND: …`
2. The final dry-run's last JSON line, verbatim.
3. One line per row: `service.part  epoch  day-fields  opt  engraved|xref→book pN  incipit → identity (how checked)`
4. What you changed from the draft and why (one line each).
5. `QUESTIONS:` (verbatim or "none") and `FLAGS:` (or "none").
6. "no DB write performed".
