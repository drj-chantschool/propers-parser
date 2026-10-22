# <Book title> — intake profile

<!-- Lives at propers-parser/<book_dir>/BOOK.md. /book-intake creates it and keeps the Status table
current; /book-batch reads the Stages table on every (cold) firing. Keep it short and factual: it is
state, not a diary — the diary is the stage's log file. -->

| | |
|---|---|
| Book code | `<CODE>` (`p_sources.source_code`; also `books.book`, `chant_indices.book`, `lit_part_sources.book`) |
| Master PDF | `propers-parser/<book_dir>/<file>.pdf` |
| Printed-page rule | e.g. "PDF labels stamped"; or "pdf = printed + 13; roman front matter iv–xvi" |
| gregobase source | `gregobase_sources.id` = N (`<title year>`), or 0 = none |
| Assignment authority | `p_assignment_authority` code, or "none (index/reference only)" |
| Text layer | yes / no (scan) / garbled |
| Unit model | page (LH-style lanes) / subsection (GR/GM-style resolver) |
| Contract README | `propers-parser/<book_dir>/specs/README.md` |
| Producer instructions | `propers-parser/<book_dir>/PRODUCER.md` (agent `content-producer`) |
| Loader | `propers-parser/<book_dir>/load_<x>.py` (`--dry-run` / real / `--verify`) |

## Status

| Phase | State | Evidence (re-check with) |
|---|---|---|
| 0 Register | ✗ | `SELECT * FROM p_sources WHERE source_code='<CODE>'` |
| 1 Page images | ✗ | `SELECT COUNT(*) FROM books WHERE book='<CODE>'` vs PDF page count |
| 2 Structure | ✗ | `<book_dir>/toc.json` reviewed; N level-1 headings |
| 3 Index parsed | ✗ | `SELECT COUNT(*) FROM chant_indices WHERE book='<CODE>'` vs printed entry count |
| 4 Index resolved | ✗ | `SELECT match_status, COUNT(*) FROM chant_indices WHERE book='<CODE>' GROUP BY 1` |
| 5 Epochs | ✗ | every unit's slug exists in `lit_epoch` |
| 6 Content | ✗ | `work_queue.py --queue <book_dir>/queues/content.json status` |
| 7 Questions | — | `tools/intake.py list --book <CODE> --status open` |
| 8 Sweep | ✗ | denominators, duplicates, placeholders |

## Stages (read by /book-batch)

<!-- Keep rows in phase order: with no stage given, /book-batch works the first row whose queue
still has pending units. -->

| Stage | Queue | Producer agent | Output | Validate | Load + verify |
|---|---|---|---|---|---|
| index-pages | `<book_dir>/queues/index-pages.json` | `index-page-parser` | `<book_dir>/index/i<page>.json` | `tools/load_index.py --book <CODE> <file> --dry-run` | same without `--dry-run`; re-run dry-run → all unchanged |
| index-rows | `<book_dir>/queues/index-rows.json` | `index-row-resolver` | `<book_dir>/index/resolve/r<row_id>.json` | director re-checks the evidence against the page | `tools/apply_index_verdict.py <file> --commit` then `--verify` |
| content | `<book_dir>/queues/content.json` | `content-producer` + `PRODUCER.md` | `<book_dir>/specs/<unit>.json` | `<loader> --spec … --dry-run` | `<loader> --spec …` then `--verify` → VERIFY PASS |

Brief extras per stage (quirks every producer must hear):
- index-pages: …
- content: …

## Director instructions
<!-- Everything a director needs that is specific to this book: how to resolve a unit (slug, span,
boundary), preconditions, modeling rules to enforce, known false-positive warnings, review and load
specifics, actions allowed without asking. Shared files (.claude/) must not carry these. -->

## Known decisions for this book
<!-- one line each, with the date and where the full ruling lives (contract README "User rulings",
intake_queue #N, a memory file). -->
