---
name: book-intake
description: Set up (or re-check) the whole intake of ANY liturgical chant book into liturgio — registration, page images, structure/TOC, index parsing, index→gregobase resolution, epoch prerequisites, content intake, question triage — and create the work queues that /book-batch then drains. Idempotent; re-run it to get a status table.
argument-hint: <BOOK_CODE> [path/to/book.pdf] [--phase N]
---

# Chant-book intake: setup and status

Book: **$ARGUMENTS**

You are the **director** of a book's intake. This command does not parse the book itself. It walks
the phases below in order, works out which are already done (from the DB and files, never from
memory), finishes the cheap deterministic steps itself, and for every phase that needs page-by-page
agent work it **creates a work queue** and tells the user the `/loop /book-batch <CODE> <stage>`
line that drains it. Re-running it on a book in progress just refreshes the status.

Read before you start: [LESSONS.md](LESSONS.md) (cross-book lessons, by phase) and
`.claude/agents/parser-director.md` (the golden rule, review discipline, load/verify contract).
Books already under way have a `BOOK.md` in their directory (`tools/_db.py:book_dir` maps the code:
`GRADUALE` → `graduale/`, `GREGORIAN_MISSAL` → `GM/`, `LIBER_HYMNARIUS` → `lhymn/`, `OCO` → `oco/`,
`OCM` → `OCM/`, any other → `<code-lowercase>/`). Read only the BOOK.md of the book you were given;
everything specific to that book is there, not here.

## Conventions

- All paths are relative to `C:\Users\johna\liturgio\propers-parser\`. Python is
  `..\.venv\Scripts\python.exe` with `PYTHONUTF8=1`. Below, `T` = `python tools/` and
  `Q <stage>` = `python tools/work_queue.py --queue <book_dir>/queues/<stage>.json`.
- `<book_dir>` = the row above, or `propers-parser/<code-lowercase>/` for a new book
  (`tools/_db.py:book_dir`). Everything for one book lives there: master PDF, `BOOK.md`, `toc.json`,
  `queues/`, `index/`, `specs/`, its loader, its log.
- **`<book_dir>/BOOK.md` is the book's state file** (template: [BOOK_TEMPLATE.md](BOOK_TEMPLATE.md)).
  Create it in phase 0, update its Status table at the end of every phase you touch, and fill its
  Stages table when you create a queue. `/book-batch` firings start cold and read only that file.
- Reads: `T q.py "<SQL>"`. Writes: `jcost` (see `tools/_db.py`). Local MySQL only — DO is a
  read-only copy refreshed by `scripts/sync_to_do.py`.
- Questions you can't settle: `T intake.py raise <file.json>` (shape in `tools/intake.py`), never a
  guess, never a chat-only question when the answer must outlive this session. Questions about how
  the *pipeline* should be set up (unit model, a new table) are for the user directly — ask them.
- Schema or API changes → dated entry at the top of `../maintenance.md` (CLAUDE.md). Data loads don't.

## Phase 0 — Register the book

1. `SELECT * FROM p_sources WHERE source_code='<CODE>'`. Missing → propose `source_code`,
   `display_name`, `sort_order`, a one-line `notes` (edition, publisher, year) and confirm with the
   user before inserting: everything else FKs to it.
2. If the book *assigns* chants to liturgical acts (a gradual, antiphonal, hymnal — not a mere
   reference), check `p_assignment_authority` for the code too, and `p_translation_source` if it
   carries a vernacular.
3. Find its gregobase edition: `SELECT id, title, year FROM gregobase_sources` → record the id (or 0).
   `SELECT COUNT(*) FROM gregobase_chant_sources WHERE source=<id>` tells you how much of the book
   gregobase already has, which decides how much phase 4 can do deterministically.
4. Create `<book_dir>/`, move the master PDF in (gitignored), write `BOOK.md` from the template.

## Phase 1 — Page images (`books`)

1. Inspect the PDF: page count, outline (`fitz get_toc()`), text layer (`get_text()` on a body page),
   existing page labels. Scans of spreads must be split and duplicate scans dropped first
   (LESSONS §1); record what you did in a `<book_dir>/page_offsets.json` like `lhymn/`'s.
2. Establish printed page numbers. Best: stamp PDF page labels (copy `graduale/renumber_pdfs.py`'s
   range-building approach). Scans with irregular plates: `T pdf_page_mapper.py <pdf> <offsets> <mapping>`
   (interactive, divide and conquer). Simple offsets: `--offset N`.
3. `T seed_books.py --book <CODE> --pdf <pdf> (--labels|--mapping F|--offset N) --dry-run`, check the
   printed numbers at the start, a chapter break and the end, then run it for real. It refuses repeated
   printed numbers. Verify: `SELECT COUNT(*) FROM books WHERE book='<CODE>'`.
4. Spot-check with `T render_page.py --book <CODE> <p>` and Read the PNG: the printed number in the
   image must equal `<p>`.

## Phase 2 — Structure: TOC, sections, units

1. **TOC.** The book's printed contents page is the authority. Produce `<book_dir>/toc.json`
   (`{"source", "pdf_page_rule", "entries": [[level, title, printed_page], …]}`, as
   `lhymn/lhymn_toc.json`):
   - PDF with an outline: `T split_by_outline.py --src <pdf> --out <book_dir>/split --toc-json <book_dir>/toc.json`
     (also writes per-section PDFs, each with its boundary page and printed labels).
   - Scan without one: Read the contents page(s) (`render_page.py`) and transcribe; or for body
     headings `T detect_subsections.py <section.pdf>` → review `subsections_raw.json` into
     `subsections.json` → `T split_sections.py <chapter_dir>` / `T split_subsections.py <section_dir>`.
   Review toc.json against the printed contents yourself and get the user's OK on anything you changed
   (LH needed two rulings). Then load it: `T load_toc.py --book <CODE> <book_dir>/toc.json`
   (`book_toc`, PK (book, idx); every printed page must already be in `books`).
2. **Denominator.** Count the units the content phase will produce (Masses / Offices / hymns per
   heading) and record it in BOOK.md. It is the completion check in phase 8.
3. **Unit model** — decide with the user, record in BOOK.md:
   - **page** (LH): one producer per printed page; the page assigns only chants that BEGIN on it;
     lanes run in page order so each page's predecessor is finished and its `context_out` carries the
     governing headings. Best when headings run continuously across pages (Office books, hymnals).
   - **subsection** (GR/GM): one producer per Mass/feast/week, briefed with a resolver's anchor block
     (heading page/Y → boundary page/Y). Best when each unit is a self-contained formulary.

## Phase 3 — Index parsing → `chant_indices`

Skip if the book has no alphabetical chant index (say so in BOOK.md; phase 4 then works from the
content specs instead).

1. Locate the index pages from toc.json. Sample two pages yourself to learn the layout: column
   order, section headings (each heading becomes `section_type`, normalised to the Latin keys in
   `tools/index_util.py:SECTION_TO_OFFICE_PART`; a new kind of heading means a new key — ask), how
   the mode is printed, what `*`, `†` or italics mean (record MEANINGS in `notes`), where the page
   number sits relative to its entry (LH: one line low).
2. Create the queue — strict single lane, so each page knows where the previous one stopped (the
   `id` ordinal runs across pages and an entry can wrap over a page break):
   ```
   Q index-pages init --book <CODE> --stage index-pages --pages "<first>-<last>" --batch-size 3 --wait 20 --log <book_dir>/INTAKE_LOG.md
   ```
3. Fill BOOK.md's Stages row for `index-pages` (agent `index-page-parser`, output
   `<book_dir>/index/i<page>.json`, the layout notes from step 1 as "brief extras").
4. Hand off: `/loop /book-batch <CODE> index-pages`. The director loads each page with
   `T load_index.py --book <CODE> <file>` (non-destructive upsert; refuses unknown section types,
   bad modes, pages missing from `books`).
5. When the queue is DONE: `SELECT COUNT(*), MAX(id) FROM chant_indices WHERE book='<CODE>'` must
   equal the last printed entry number; verify ~10 random rows against their target pages (the
   line-low page-number trap), and fix through the loader.

## Phase 4 — Index resolution → `chant_indices.chant_uuid`

1. Deterministic pass: `T resolve_index.py --book <CODE> --source <gregobase id>` (dry-run), read
   the ✓ lines for anything odd, then `--commit --units-file <book_dir>/queues/index-rows.units`.
   It only links the unambiguous case and leaves rows already carrying a status alone.
2. Queue the rest — independent units, so unordered; pacing per LESSONS §4:
   ```
   Q index-rows init --book <CODE> --stage index-rows --units-file <book_dir>/queues/index-rows.units --unordered --batch-size 5 --wait 30 --log <book_dir>/INTAKE_LOG.md
   ```
   Fill the Stages row (agent `index-row-resolver`). Hand off: `/loop /book-batch <CODE> index-rows`.
3. The director applies each reviewed verdict with `T apply_index_verdict.py <file> --commit`
   (`--verify` after): a link → `match_status='resolved_with_difficulty'`; no edition in gregobase →
   `unmatched` (a placeholder local chant (`chants` row `chant_uuid='local:<uuid>'`, `elements='[]'`) only when content intake needs one); two or more
   defensible picks → `ambiguous` + the verdict's question raised with `T intake.py raise`; an
   index misprint → `--apply-index-fix` after you've looked. Curated rows are never overwritten.
   Ungrouped gregobase chants are reported, not linked around.

## Phase 5 — Epoch prerequisites (`lit_epoch`, ranks, jurisdictions)

For every unit in toc.json, find the `lit_epoch.slug` it will load against (temporale weeks/days,
saints via `proper_of_saints`, commons `kind='common'`, vigils, rites). Build a table of
heading → slug → exists?, put it in `<book_dir>/epoch_map.md` (or the contract README), and:
- existing slug: done (cross-check printed rank markers against `rank_code`, never fill from a blank);
- missing slug for a known pattern (an OSB saint, a vigil leaf) the book's rulings already allow:
  create it, log it;
- anything else: an intake question (`category='structural'`). Never invent a slug to make a load pass.

## Phase 6 — Content intake (the propers / assignments themselves)

1. **Contract + loader.** A new book needs `<book_dir>/specs/README.md` (JSON shape, part codes, the
   page/subsection rule, validation, "Known quirks", "User rulings") and a loader with `--dry-run`,
   real load, and `--verify` that upserts by slot and never overwrites a curated `chant_uuid`. Start
   from the nearest existing pair — `lhymn/load_lh_page.py` + `lhymn/specs/README.md` (Office, page
   model, index-first identity with ⚠ CHECK lines) or `graduale/load_graduale_propers.py` +
   `graduale/specs/README.md` (Mass, subsection model, bboxes). Writing these is your job, with the user
   reviewing; a new `service_part` or column is a schema change (maintenance.md).
2. **Producer instructions.** The producer agent is the shared `content-producer`; everything about
   this book goes in `<book_dir>/PRODUCER.md` (what a unit is, how to read the page, field rules, what
   "complete" means, the validate command, the report). Start from the nearest existing book's
   PRODUCER.md and replace its specifics; never put book rules in `.claude/`.
3. **Pilot.** Produce, review and load 3–5 representative units by hand (one of each unit kind) before
   queueing the rest. Fold every surprise into the README.
4. **Queue.**
   - page model: `Q content init --book <CODE> --stage content --pages "<lane A ranges>" --lane A …`
     then `Q content add --pages "<lane B ranges>" --lane B` …; `--skip "<a-b>:<why>"` for pages that
     are only cross-reference targets or indices. Lanes: independent runs of pages, with any range
     that others cite (Commons) first in its lane. Batch 3, wait 20.
   - subsection model: write `<book_dir>/queues/content.units` (`unit<TAB>lane<TAB>after,…` — e.g. a
     Sanctorale day `after` the Common it cites), then `init --units-file …`. Batch 2–3 for heavy units.
   Fill the Stages row, then hand off: `/loop /book-batch <CODE> content`.

## Phase 7 — Questions

Every pipeline raises into `intake_queue`; the user answers at `/intake` in liturgio-api. Make sure
`/loop 30m /intake-triage` is running (or offer to start it) while any queue of this book is active:
it claims answered rows, carries them out, releases the held units and folds standing rules into the
contract README.

## Phase 8 — Completion sweep (when every queue reports DONE)

- Units: loaded count vs the phase-2 denominator; list the gap by heading.
- Rows: per unit, row count vs spec; no duplicate slots (`uq_lps_slot` is the backstop); engraved rows
  have NULL `ref_page_num`, xrefs set.
- Index: every `chant_indices` row has a status; `ambiguous`/`unmatched` listed for the user.
- Placeholders: every `local:` chant with an empty gabc, listed for transcription.
- Open questions: `T intake.py list --book <CODE> --status open`.
- Final BOOK.md status table and a log line `🏁 INTAKE COMPLETE`.

## Report (end of every run)

The BOOK.md Status table, what you did this run, the queues you created with their `/loop` lines,
and — first — anything waiting on the user (a registration to confirm, a unit-model choice, a TOC
correction, open questions).
