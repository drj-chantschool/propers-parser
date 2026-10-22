# Cross-book lessons (GR, GM, LH intakes, 2026-04 → 2026-10)

Distilled from the Graduale Romanum, Gregorian Missal and Liber Hymnarius runs, so that a new book
starts with them instead of rediscovering them. Each line names the memory or file that has the
full story. Rules for one book live in that book's BOOK.md / PRODUCER.md / specs README, not here.

## Everywhere

- **Golden rule.** Every mark on the page ends up modeled: as a row, in `continues`/`notes`/`flags`,
  or as an `intake_queue` question. Never a silent drop, never a guess. A question blocks one unit; a
  wrong guess pollutes the DB. (`.claude/agents/parser-director.md`)
- **A clean dry-run proves resolvability, not correctness.** A mis-scoped rubric, a wrong cycle, the
  wrong saint, the wrong edition all dry-run clean. Review needs a semantic pass: coverage of every
  printed rubric, structural completeness, chant identity against the page. (prefer-sonnet-subagents)
- **Already loaded ≠ already correct.** Loader checks are spec-relative; rows from earlier pipelines
  must be re-read against the page. (gr-preexisting-specs-need-rereading)
- **Pages are PRINTED page labels everywhere** — specs, loaders, `books.printed_page_num`, reports.
  `printed_page_num` is a VARCHAR: `BETWEEN '619' AND '626'` matches `'62'`; CAST or list pages.
- **A new edition of the master PDF: re-verify printed = PDF on EVERY running head, not a sample.**
  OCO v.6 dropped one blank verso (printed 974), shifting 346 pages by one; links/outline are PDF pages.
  Re-parse to a scratch dir and diff row-by-row before writing; `books` stores images, so reseed, and
  `render_page.py` shows the stored image, not the PDF — re-check pages only after the reseed.
- Canonical venv only (`C:\Users\johna\liturgio\.venv`), `PYTHONUTF8=1` on every command (the
  resolvers print ✓ and crash cp1252 without it). Local MySQL is the write target; DO is a read-only
  copy. Schema/API changes get a `maintenance.md` entry; plain data loads don't.
- `fitz` cannot write `/tmp`; scratch goes to `propers-parser/_tmp/`, which is **director-owned**.
  Producers are told to clean scratch, so every brief says "do NOT delete `_tmp`".
- Run `work_queue.py finish … --summary '<json>'` from Bash, not PowerShell 5.1 (it strips the inner
  quotes). (lh-page-intake-pipeline)

## Phase 1 — PDF and page images

- The Read tool's "PDF is password-protected" error is a **size** limit (~>4 pages / >450 KB), not
  encryption. `tools/chunk_pdf.py` cuts any PDF into readable chunks and keeps printed labels.
  (gr-pdf-read-size-threshold)
- Scans of two-page spreads must be split left/right, and duplicate scans removed, before anything
  is numbered (LH: 320 spreads → 640 pages, one duplicated spread dropped; `lhymn/page_offsets.json`).
- Stamp printed page labels on the master PDF first; every split/chunk then inherits them. Splitters
  that don't carry labels caused a whole chapter to be cited on chapter-page numbers.
  (gr-split-printed-page-labels)
- `books.image_blob` holds the dpi=200 page PNG; `bbox` lives in that pixel space, so never change
  the DPI. **Never `SELECT *` from `books`** (1.1 GB). `tools/render_page.py` is the fastest way to
  answer "does the book actually print X here?" (books-table-page-images)

## Phase 2 — Structure (TOC, sections, units)

- The book's own printed TOC (Index generalis) is the authority for structure; font size is not.
  Rubrics such as "Ad libitum…" / "Tempore paschali:" are options, not subsections. (gr-toc-rubric-vs-subsection)
- Auto-detected heading text is untrusted: an OCR'd `Eadem die` typo hid a whole Mass and silently
  stretched its neighbour. Grep for the anchors and cross-check the count. (gr-subsections-heading-text-untrusted)
- **Count the level-1 headings first** — it is the only honest denominator for "is anything
  missing?" and turns the completion check into arithmetic. (gr-sanctorale-batch-workflow)
- Splits must include the boundary page: a section's tail sits above the next heading on that page.
  (gr-split-drops-boundary-page; GM's "buffer page")
- Spans reported by a resolver can under-report a multi-page unit; brief from the boundary
  page/Y and probe one page past. (gr-resolver-span-under-reports)
- Out-of-sequence material exists (GR addendum Masses at month end; LH Paschal second settings);
  "Die N…, saint, page." pointer lines are navigation and emit no row. (gr-addendum-mass-and-pointer-line)

## Phase 3 — Index parsing (`chant_indices`)

- **Check a born-digital PDF for link annotations and hidden text before planning agent work.** OCO's
  index entries were all hyperlinks (target page, or a gregobase URI) and every engraving carried its
  full text in white plus a source line (CAO / AM / ARII + page): parsing and ~57% of resolution became
  deterministic, with no agents. (`oco/parse_oco_index.py`, `oco/resolve_oco_*.py`)
- Text-only matching needs a lyric check, not an incipit prefix: a short incipit matched different chants
  ('Quaerite Dominum' et vivet / dum inveniri). Gregobase also splits versions of one chant across groups.

- **Never DELETE + reload an index table.** `upload_gr_index.py` did, and would have wiped all
  curated links; `tools/load_index.py` upserts and never touches `chant_uuid`/`match_status`.
  (upload-gr-index-is-destructive)
- Printed index page numbers can sit **a line below** their entry; agents misaligned them. Verify
  a sample of rows against their target pages. (lh-index-alphabeticus)
- Keep the printed incipit (normalised æ→ae) and record the index's own conventions as MEANINGS:
  author/origin in `author_origin`, an `*` as `notes='Proprium monasticum O.S.B.'`, a non-1..8 mode
  as `mode NULL` + `notes='printed mode: E'`. Not a new column per book. (lh-index-alphabeticus)
- An OCR/typo'd index incipit breaks cross-reference resolution silently on single-candidate
  pages: fix the index row; the spec keeps the printed spelling. (gr-index-ocr-typo-xref)
- Glossed index forms ("Laetamini (sine alleluia)") and printed ellipses ("Responsum… et cum")
  defeat the prefix rule — probe with a one-chant dry-run. (gr-index-incipit-prefix-rule,
  gregobase-ellipsis-incipit-trap)
- Roman numerals mean three things (mode in the margin, option marker centred, a book citation);
  "Antiphona ad introitum N" is a MODE. Alleluia index rows key to the VERSE page.
  (gr-roman-numeral-three-meanings, gr-alleluia-index-verse-page)

## Phase 4 — Index resolution (gregobase links)

- Deterministic first: one chant tied by the book's own gregobase source to the index page (±1),
  office-part + numeric mode + incipit prefix agree, grouped, and no second index row with the same
  incipit on that page. That rule is 232/232 against the curated LH links (`tools/resolve_index.py`).
- The rest: one row per Sonnet agent, batches of 5, steady 30-min gap (5- and 15-min gaps hit the
  session limit). ~50–65k tokens per agent. (agent-fanout-pacing)
- Agent/Claude judgments get `match_status='resolved_with_difficulty'` (the review queue), never
  `resolved`. `reviewed` can mean "best of a bad pool"; it is not proof. (judgment-links-flag-for-review,
  gr-match-status-reviewed-not-proof)
- Same incipit ≠ same chant: compare engraved neumes (opening + a cadence), not text, not mode, not
  GABC-to-GABC. Same melody + different words = unmatched. (gr-same-incipit-different-chant)
- Gregobase suffixes (`(In feriis)`, `(Adv.)`, sine/cum alleluia) split one incipit into several
  chants; two index rows hitting the same chant is a red flag. (gregobase-sine-cum-alleluia-variants)
- ~100 imported gregobase chants are ungrouped and unreachable by matchers, so a worse (even
  English) edition wins with a clean result. Hold, don't load-then-fix. (gregobase-ungrouped-import-tail)
- A chant truly absent from gregobase gets a blank placeholder `local_chants` row (draft, empty
  gabc) and `local:<uuid>`; keep the placeholder list for the user to transcribe. (lh-page-intake-pipeline)
- Fixing an index link later does not touch rows already loaded from it: repoint the
  `lit_part_sources` rows (and any GM twin). (gr-curated-index-fix-doesnt-reload)

## Phase 5 — Epochs, ranks, jurisdictions

- Never invent a `lit_epoch` slug; a missing one is a modeling question. `lit_epoch` is keyed on
  `slug` (there is no `lit_epoch_slug` column). (gm-step0-slug-validation)
- A date-only resolver can return OK on the WRONG saint (general vs national calendar): read the
  printed title every time. (gr-sanctorale-resolver-wrong-saint)
- Commons are `kind='common'` part-menus, vigils are their own `kind='mass'` leaf, movable feasts
  are temporale nodes with a placeholder date, non-universal propers carry `jurisdiction`.
  (gr-commons-kind-common, gr-vigil-mass-leaf, movable-feast-modeling, gr-osb-appendix-jurisdiction)
- A printed rank marker (Mem./Fest./Sol.) maps to `rank_code`; its ABSENCE is not evidence (All
  Saints prints none). Ranks are usually preloaded — the marker is a cross-check. (gr-sanctorale-rank-markers)

## Phase 6 — Content intake (producers → specs → loader)

- Producers are page-local. Every January near-miss was a same-page collision a producer could not
  see. The director pre-flights the index rows of every cited page into the brief, names the
  neighbouring unit's trap, and probes doubtful incipits. (gr-sanctorale-batch-workflow)
- Highest-leverage recon: put every distinct citation of the batch into ONE probe spec with real
  pages/bands and dry-run it once before spawning. Render the batch's page images up front and hand
  producers the paths. (gr-sanctorale-batch-workflow)
- Brief producers with block geometry; give merged OCR blocks the same band. (gr-brief-block-geometry)
- Know whether your book's loader folds accents before writing incipits from the page: a
  page-accurate accented incipit can miss the index silently. (gr-spec-incipit-no-diacritics)
- Checkpoint the spec to disk early; session limits kill unsaved work. Size waves to
  the unit: 2 for heavy multi-page units, 3 for single pages. (prefer-sonnet-subagents)
- Page model (LH): a page assigns only the chants that BEGIN on it; lanes keep each page's
  predecessor finished so its `context_out` carries headings across the page break; run-overs belong
  to the page they start on. Subsection model (GR/GM): a resolver prints the anchor block.
- A rubric governs only the one chant it introduces; alternates (`vel:`, `Or:`, a bare em-dash line)
  are distinct chants; continuation shorthand packs several rows into one line; a missing part is a
  parse error, not an editorial omission. (gr-em-dash-alternate, parser-director)
- Engraved-vs-xref and cycle/day assignment are independent axes. (gm-cycle-label-vs-gr-slot)
- Inheritance rubrics ("Omnia sicut…, praeter…", "Cantus ut supra") print zero or partial chants:
  grep `ut supra`/`praeter` at recon and ask. (gr-cantus-ut-supra-construct)
- Resume pointers come from the DB with EXACT slug match, never `LIKE 'slug%'` (`thomas` looked
  loaded because `thomas-aquinas` was). (gr-sanctorale-batch-workflow)
- When the same producer mistake shows up twice, add a one-line rule to the contract README's
  "Known quirks"; that is how later producers learn.

## Phase 7 — Questions and rulings

- Questions go to `intake_queue` (answered at `/intake` with the page in view), not to chat or log
  lines. Reuse `topic_key`; give pages, chants, options (one `recommended`) and context so an agent
  with no memory can act. Held units name the question; answering releases them. (intake-queue)
- `is_standing_rule=1` answers go into the contract README's "User rulings" as well as the case.
- Don't re-litigate recorded rulings (see each contract README and the book's memory file).
