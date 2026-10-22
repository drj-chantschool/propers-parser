# Liber Hymnarius — producer instructions

For the `content-producer` agent working on book `LIBER_HYMNARIUS`. Read with the generic rules in
`.claude/agents/content-producer.md`; where they differ, this file wins.

## What you produce

ONE spec for ONE printed page: `lhymn/specs/p<NNNN>.json` (4-digit zero pad), recording which chants
BEGIN on the page and which liturgical act (epoch, day, hour, part, rank) each is assigned to,
engraved chants and cross-references alike. Validate with `lhymn/load_lh_page.py`.

**Contract:** `lhymn/specs/README.md`, in full — the page rule (a page assigns only the chants that
BEGIN on it), the JSON format, the services table, the epoch map, Commons and `common_refs`, Known
quirks, User rulings. Your brief gives the page and the previous page in your lane.

## Step 1: see the page

```
cd C:\Users\johna\liturgio\propers-parser
python tools\render_page.py --book LIBER_HYMNARIUS <page> <previous_page> <next_page>
```
Read each PNG: the scan has no text layer. For small print (rubrics, `p. 146` citations, the mode in
the left margin such as `H.IV`, `Ant.E`) add `--zoom top` / `--zoom bottom`.

**Establish context first.** The headings that govern the top of your page (section, day, hour,
rubric) are often printed earlier. Read the previous page's spec `context_out`; if it is missing or
doesn't settle it, read earlier page images back to the last section/day/hour heading. Running heads
help (left page: section; right page: subsection).

## Step 2: inventory the page, top to bottom

- **A chant continuing from an earlier page** (no drop-cap; starts mid-text or with a stanza number
  such as `2.`): goes in `continues`, never a row — with any psalm cue / `Ad libitum` line at the top
  that the previous page's chant owns.
- **A chant beginning here** (big drop-cap, mode in the left margin): one row. A hymn's notated
  stanza plus its text stanzas, doxology and Amen are one chant.
- **A cross-reference** (`Ad libitum dici potest hymnus Dies aetasque, p. 183.`,
  `Vel ℟. Missus est, p. 517`, `Ps. Veníte, p. 146.`): an `xref` row with `ref_page`.
- **Headings and rubrics** (`AD LAUDES`, `In dominica`, `In feriis`, `I. Quando Officium lectionis
  dicitur noctu…`) set epoch, service, wkday and options for the rows that follow; record the rubric
  verbatim in each governed row's `rubric`.
- **Sanctorale:** `De Communi …` lines become `common_refs`; proper chants are rows on the saint's slug.

Check against the index (it lists the page each chant begins on):
```sql
SELECT row_id, section_type, mode, incipit, page, chant_uuid, match_status
FROM chant_indices WHERE book='LIBER_HYMNARIUS' AND page IN (:p, :p_minus_1, :p_plus_1)
```
An index row with no drop-cap you can see = you missed something, or the index is a page off (use
`index_row_id`). A drop-cap with no index row is normal for invitatories/responsories; gregobase
source 15 may still have it (the loader checks both).

## Step 3: write the spec

Always fill `context_in`, `context_out` (section › day › hour › last rubric, and whether a chant
runs onto the next page), `continues`, `flags`, `questions`. Watch for:
- **Office of Readings hymn by time of day:** "I. … noctu vel summo mane" vs "II. … interdiu" are
  options 1 and 2 of `OFFREAD.hymn` (`option_txt` = the rubric).
- **"In Officio dominicali et feriali, a I Vesperis dominicae … usque ad …"** is section-wide: a plain
  AD VESPERAS under it → both `VESPERS1` and `VESPERS` rows.
- **The invitatory psalm cue** goes with its antiphon even when printed overleaf: an
  `INVITATORY.invps` xref row with the antiphon's exact epoch/wkday/rank fields.
- **Same incipit, different chant:** dominica vs feriis invitatories share words, not mode. Always
  give `mode`.
- **Run-overs:** a chant that starts on your page is YOURS to its final double bar; read the next page,
  and any `vel` / `Ad libitum` / psalm-cue line after it is a row in YOUR spec.

## Step 3b: trust the index, but verify every chant

The index is the loader's first source of identity and is not guaranteed correct: page numbers print
about a line low and can be a page off; a linked `chant_uuid` can be a different edition or melody
(p517 *Missus est*); `resolved_with_difficulty` / `reviewed` mean "best of a bad pool"; same incipit
≠ same chant (Paschal second settings); the index has misprints.

Every row's dry-run line `✓? gregobase:N = '<incipit>' m<mode> <office-part>, LH p<pages>; text
'<opening words>'` must match the page: opening words (not just the first word), mode, office-part
(hymn `hy`, invitatory `an`, responsory `re`), and the LH page when gregobase ties one. Each
`⚠ CHECK` must be resolved before the page can load:
1. a better candidate (another index row via `index_row_id`, or a gregobase chant tied to this
   source-15 page via `chant_uuid` + a flag) → switch and re-run;
2. you checked the page and the chant is right (e.g. a different mode convention) →
   `"verified_despite": ["<distinctive part of the warning>"]` and explain in `flags`;
3. otherwise → `questions`, quoting the warning. Never acknowledge a warning you haven't resolved.

## Validate

```
set PYTHONUTF8=1
C:\Users\johna\liturgio\.venv\Scripts\python.exe C:\Users\johna\liturgio\propers-parser\lhymn\load_lh_page.py --spec C:\Users\johna\liturgio\propers-parser\lhymn\specs\p<NNNN>.json --dry-run
```
Iterate to `DRY-RUN OK` (exit 0), or exit 3 with genuine `questions`. `⚠ slot already holds a
DIFFERENT chant` = your epoch/day/option fields collide with an existing row: re-check, flag if sure.

## Report (≤ 15 lines)

1. `SPEC: <path>` and `PAGE_KIND: …`
2. The final dry-run's last JSON line, verbatim.
3. One line per row: `service.part  epoch  day-fields  engraved|xref→pN  incipit → chant_uuid`
4. `QUESTIONS:` (verbatim or "none") and `FLAGS:` (or "none").
5. "no DB write performed".
