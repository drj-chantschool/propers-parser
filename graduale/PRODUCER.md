# Graduale Romanum — producer instructions

For the `content-producer` agent working on book `GRADUALE`. Read with the generic rules in
`.claude/agents/content-producer.md`; where they differ, this file wins.

## What you produce

ONE subsection spec (an OT week, a feast, a Lenten day, a votive/ritual Mass…) at
`graduale/specs/<name>.json`, dry-run clean against `graduale/load_graduale_propers.py`, which
matches chants to gregobase, computes bboxes and writes rows.

**Contract:** `graduale/specs/README.md` — JSON format, the `band` field (PDF points),
engraved-vs-cross-reference, the whole-week per-annum structure, the wkday/slug/cycle rules,
alternates, validation. **Examples:** `graduale/specs/ot-ot-13.json` (a full OT week — engraved
Mass + year-cycle options + a ferial) or `ot-ot-20.json`.

**Checkpoint:** write the spec as soon as you've identified the engraved default Mass (just its
chants, each with a rough band), then refine.

## Book facts

- PDF `graduale/graduale romanum.pdf` (PyMuPDF `fitz`); chapter/section splits under `graduale/<n>/`.
  The chant-body text layer is garbled (neume syllables interleave) and can crash `charmap`
  without `PYTHONUTF8=1`; headings and citations are usable.
- Printed == pdf page up to ~p378; past that, unnumbered plates shift it (printed 402 = pdf 400).
  Render by PRINTED page with `tools/render_page.py --book GRADUALE <p>`; for fitz block geometry
  map via `graduale/page_mapping.json`. The loader stores `printed_page_num` and derives the pdf page.
- Native Read rejects PDFs over ~4 pages / 450 KB as "password-protected" (a size limit):
  `tools/chunk_pdf.py`, or read page PNGs.

## Workflow

1. **Span.** Your brief gives it (heading page/Y → boundary page/Y not to cross). To check it:
   `book_toc WHERE book='GRADUALE'` (columns `text`, `printed_page` VARCHAR, `idx`, `y`, `level`) —
   consecutive headings give the span, e.g. `HEBDOMADA DECIMA TERTIA`=297 → `DECIMA QUARTA`=300 ⇒
   week 13 is p297–299, with trailing options possibly on p300 above the next heading. Split PDFs
   such as `graduale/1/7_tempus-per-annum/<N>_hebdomada-….pdf` extract whole pages, so text-layer
   y-coordinates match the main PDF — but splits end one page early; read the boundary page too.
   Sanctorale days are not in `book_toc`: their headings are `graduale/3/subsections_ai.json`
   (level 1 = `Die N <mensis>` / `Eodem die`, level 2 = title, `page` 1-indexed into
   `3_proprium-de-sanctis.pdf`).
2. **Chant checklist** from the GR index:
   `SELECT page, section_type, mode, incipit, chant_uuid, match_status FROM chant_indices
   WHERE book='GRADUALE' AND CAST(page AS UNSIGNED) BETWEEN :a AND :b ORDER BY CAST(page AS UNSIGNED)`.
   `section_type`→`service_part`: introitus→`in`, graduale→`gr`, alleluia→`al`, tractus→`tr`,
   offertorium→`of`, communio→`co`, sequentia→`seq`. No index row for a part on its page ⇒ that
   part is a cross-reference there, not an engraving.
3. **Whole-week structure (per annum).** Delimit the week by the **spelled-out** `HEBDOMADA <N>`
   heading (not the roman-numeral running header). A week = the engraved default Sunday Mass
   (in/gr/al/of/co), then a trailing block of options that spills onto the next page(s):
   - **Year-cycle Sunday options** `Dom. anno A/B/C: <incipit>, <page>` → a cross-reference of the
     cited part with `cycle_sun` (1=A, 2=B, 3=C). Several may share one line (and one bbox).
   - **Ferial options** `Feria N: …` / `Anno I/II, feria N: …` → a cross-reference with `wkday`
     (Feria II=2 … Sabbato=7) and, for `Anno I/II`, `cycle_wkday` (1/2).
   - **`In feriis: …`** — depends on whether the WEEK HAS A SUNDAY (not on engraved-vs-cited):
     normal weeks → it OVERRIDES the Sunday on weekdays: ONE row with a `"wkdays"` list (ferias 2–7
     except any with their own proper). **Weeks 1 & 34** (no Sunday: Dominica I is the Baptism, the
     last Sunday is Christ the King) → it IS the week default: no `wkday`/`wkdays`.
   - Continuation shorthand: `Feria 2: Loquebar, 528. - 3: In te, 296. - 6: Caro mea, 378.` = three
     rows; `Dom. anno A: Surrexit, 202. - C: Simon Ioannis, 574.` = anno A and C.
   - `vel:` / `Vel ad libitum:` / `Ad libitum:` → an additional row of the preceding item's part
     and day fields plus `"option_txt"` (the printed marker). A `vel:` inside the Sunday communion's
     psalm line binds the Sunday default.
   - Each option's PART comes from the cited chant on its TARGET page (index row there).
   - An option at the TOP of the next page (above its heading) belongs to the week just ended.
   - Example of rubric scope: p311 (week 17) `Anno I, feria 6:` governs only the introit
     `Exsultate Deo`; the graduale `In Deo speravit` below it is the Sunday default.
   - **Complete** = the week-default set (week slug, no wkday/cycle) has `in`, `gr`, `al` (or `tr`),
     `of`, `co`.
4. **Engraved vs cross-reference.** Engraved: `engraved:true`, `mode`, `band` boxes the engraving.
   Cross-reference: `engraved:false`, `target_page` (cited printed page), `band` boxes the citation
   LINE, `mode` omitted. `cum ps. NNN*` after a citation is a psalm-tone plan: not a chant, not a
   target page — `target_page` is the number before it; record the plan in `notes`.
   - The right-margin rank marker (`Mem.` / `Fest.` / `Sol.`) is NOT a chant and not `option_txt`;
     report it verbatim with its page (read it off the PNG — OCR mangles it).
   - An all-cross-reference Mass (five `IN./GR./AL./OF./CO.` lines) is normal for memorials; still
     expect the full set and band each citation line.
5. **Bands.** `band` = `[ytop_pt, ybot_pt]` in PDF points from `page.get_text("dict")` block
   extents; `compute_bbox` unions blocks whose vertical CENTER falls in the band. Give merged OCR
   blocks the same band rather than subdividing. Confirm on the dpi=200 render. (A bbox only has to
   show the right page region was parsed.)
6. **Slug / wkday / cycle.** Top-level `lit_epoch_slug` = the **week** slug (`OT-OT-14`); the
   loader derives per-chant slugs: default Mass → no fields; Sunday option → `cycle_sun` (loader
   makes `…-1`, wkday 1); ferial → `wkday` (+ `cycle_wkday`). A single-day feast/Sunday spec uses
   that day slug and sets spec-level `wkday` iff the GR prints Dominica/Feria/Sabbato. Never invent
   a slug: the brief gives it.
7. **Incipits** as printed but **without diacritics** (the loader folds i/j, u/v, punctuation and a
   bare `V` verse marker, but not accents: `Lætámini` misses the index silently). If a target-page
   index incipit is an OCR typo, cite normally — the loader resolves a page's single chant of that
   part (`ℹ index incipit mismatch`); report it so the director can fix the index row.

## Paschaltide, Lent, late Advent (when your unit is one)

- **Paschaltide:** no Gradual; two Alleluias. The first = `al1` (Gradual's slot, week default);
  the second = `al`. "In feriis omittitur AL. <incipit>" ⇒ that `al` gets `wkday:1` (Sunday only).
- **Lenten ferias** print only In/Gr/Of/Co (no Tract/Alleluia); the loader's missing-al/tr
  COMPLETENESS warning is a known false positive there — confirm and say so.
- **Dec 17–24:** ADV-II+wkday ferias vs the dated `ADV-II-00-seq` days; your brief says which.

## Validate

```
set PYTHONUTF8=1
C:\Users\johna\liturgio\.venv\Scripts\python.exe C:\Users\johna\liturgio\propers-parser\graduale\load_graduale_propers.py --spec-file C:\Users\johna\liturgio\propers-parser\graduale\specs\<name>.json --dry-run
```
Clean = every chant `-> gregobase:<id>` (ideally `via index`), a sane non-empty bbox, no
`LookupError`/`ValueError`. `⚠ REVIEW` (multi-candidate split), `ℹ index incipit mismatch`,
`ℹ version-split` are not errors — report them. `⚠ COMPLETENESS` is: fix it or explain it.

## Report

The spec path, the final dry-run output, the printed span you used (and how you bounded it), the
engraved / xref / year-cycle / ferial breakdown, your slug/wkday decisions, any rank marker seen, all
REVIEW/mismatch/version-split lines, and "no DB write performed".
