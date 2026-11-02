# Liber Hymnarius (Solesmes 1983) — intake profile

Book-specific instructions for directors working on `LIBER_HYMNARIUS`. Producers read `PRODUCER.md`.

| | |
|---|---|
| Book code | `LIBER_HYMNARIUS` |
| Master PDF | `lhymn/Liber_Hymnarius_1983_paged.pdf` (spreads split, one duplicate spread removed: `page_offsets.json`) |
| Printed-page rule | pdf 1–13 = roman iv–xvi; pdf 14–638 = printed 1–625 (`tools/seed_books.py --offset 13`) |
| gregobase source | 15 (Liber Hymnarius 1983) |
| Assignment authority | `LIBER_HYMNARIUS` |
| Text layer | none (scan) — read page images |
| Unit model | page, three lanes (A tempore; B Commons → Sanctorale Jan–Aug; C Responsoria, OSB, Sanctorale Aug–Dec) |
| Contract README | `lhymn/specs/README.md` |
| Producer instructions | `lhymn/PRODUCER.md` (agent `content-producer`) |
| Loader | `lhymn/load_lh_page.py --spec … [--dry-run|--verify|--prune]` |
| TOC | `lhymn/lhymn_toc.json` (Index generalis, corrected by user ruling 2026-10-08) |

## Status (2026-10-19)

| Phase | State | Evidence |
|---|---|---|
| 0 Register | ✓ | `p_sources`, `p_assignment_authority` |
| 1 Page images | ✓ | 638 `books` rows |
| 2 Structure | ✓ | `lhymn_toc.json` → `book_toc` book='LIBER_HYMNARIUS' (79 rows, `tools/load_toc.py`) |
| 3 Index parsed | ✓ | 544 `chant_indices` rows (pp. 608–619) |
| 4 Index resolved | ✓ | 341 resolved, 7 reviewed, 147 resolved_with_difficulty, 3 ambiguous, 46 unmatched |
| 5 Epochs | ✓ | OSB saints created during intake |
| 6 Content | ✓ 2026-10-18 | queue `lhymn/queues/pages.json`: 450 loaded, 111 no_rows, 64 skipped |
| 7 Questions | ✓ | intake_queue #1–#9 done |
| 8 Sweep | ◐ | 12 placeholder `local_chants` await transcription (see `LH_INTAKE_LOG.md`, 🏁 line) |

## Stages (read by /book-batch)

| Stage | Queue | Producer agent | Output | Validate | Load + verify |
|---|---|---|---|---|---|
| pages | `lhymn/queues/pages.json` (log `lhymn/LH_INTAKE_LOG.md`) | `content-producer` + `lhymn/PRODUCER.md` | `lhymn/specs/p<NNNN>.json` | `lhymn/load_lh_page.py --spec … --dry-run` (exit 0 / 3 questions / 4 blocked_dep / 1 error) | `--spec …` then `--verify` → VERIFY PASS |

Run as `/loop /book-batch LIBER_HYMNARIUS pages`, 3 producers per batch (one per lane). The intake
completed 2026-10-18; the queue is kept as the record. To redo a page: `Q reset <p>`, fire one batch.

## Director instructions

- **Lanes:** A 1–130, 177–244 (Proprium de tempore, per annum); B 245–420 (Commons first, then
  Sanctorale Jan–Aug); C 487–607, 421–486 (Responsoria, OSB proper, Sanctorale Aug–Dec). Skipped:
  131–176 (Ps 94 tones, cross-reference targets only), 608–625 (indices).
- **Brief extra:** "The previous page in your lane is {prev}: its spec, if present, is
  `lhymn/specs/p{prev:04}.json`; read its `context_out` first."
- **Review** on top of /book-batch step 5: every drop-cap chant starting on the page has a row and
  nothing continued from the previous page does; hour heading, day rubric and option per row match
  the page; xref rows carry the printed `ref_page`; `continues` / `page_kind` plausible; epoch per the
  README map; psalter rows carry `wknum_mod_2/4` or `psalter_all_weeks`.
- **Identity:** read every `✓? gregobase:N …` line against the page. Each `⚠ CHECK` is resolved or a
  question; remove a producer's `verified_despite` you don't agree with. When the line shows `LH p-`
  or another LH page, compare the GABC's opening neumes and a cadence with the engraving (same hymn
  text, different melody: p96 vs p77).
- **Slot conflict with an earlier page's Common copy** ("slot already holds a DIFFERENT chant" from a
  `common_ref` on the saint's first page): add the slot to that page's `common_refs[].skip_slots`,
  reload that page with `L --spec … --prune` and verify, then load the current page (Agnes p340/p341).
- **Index wrong** (bad page, bad link): raise an `index_fix` question naming the `chant_indices` row;
  never edit `chant_indices` from the loop.
- **Load by dry-run exit code:** 0 → load, `--verify`, `Q finish <p> loaded --summary '<last JSON
  line>'` (`no_rows` for `continuation_only` / `no_chant`); 3 → raise each question, `Q finish <p> held
  --question <id>`; 4 (cited Common not fully loaded) → `Q finish <p> blocked_dep` — the OSB
  Sanctorale (from p541) waits on lane B's Commons, expected; dependency checks read the QUEUE status,
  so `Q finish` a newly loaded Common page before retrying its dependents; 1 → `error` + log.
- **Allowed without asking:** a missing OSB saint epoch (kind `saint`, child of `OSB-PROPRIUM`, plus a
  `proper_of_saints` row with jurisdiction `OSB`); a placeholder local chant (`chants` row `chant_uuid='local:<uuid>'`, `elements='[]'`) (version LH1983,
  draft) for a chant absent from gregobase — add it to the placeholder list in the log.

## Known decisions
`lhymn/specs/README.md` "User rulings"; memory `lh-page-intake-pipeline`.
