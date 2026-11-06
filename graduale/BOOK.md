# Graduale Romanum (1974) — intake profile

Book-specific instructions for directors working on `GRADUALE`. Producers read `PRODUCER.md`.

| | |
|---|---|
| Book code | `GRADUALE` |
| Master PDF | `graduale/graduale romanum.pdf` (906 pages; printed labels stamped; outline written by `build_gr_toc.py`). Pre-2026-10-22 copy: `graduale romanum.pdf.pre-addenda.bak` |
| Printed-page rule | **Page labels.** Every GR PDF (master + all 200 splits) is stamped with printed page numbers; look pages up by label (`doc.get_page_numbers("<p>")`), never by pdf index. `page_mapping.json` retired 2026-10-22 (archived in `APPLIED/`; labels reproduce it exactly) |
| gregobase source | 4 (Graduale Romanum 1974) |
| Assignment authority | `GRADUALE` |
| Text layer | yes, but the chant body is garbled; headings/citations usable; read page images |
| Unit model | subsection (one Mass / week / feast per producer) |
| Contract README | `graduale/specs/README.md` |
| Producer instructions | `graduale/PRODUCER.md` (agent `content-producer`) |
| Loader | `graduale/load_graduale_propers.py --spec-file … [--dry-run|--verify]` |

## Status (2026-10-19)

| Phase | State | Evidence |
|---|---|---|
| 0 Register | ✓ | `p_sources`, `p_assignment_authority` |
| 1 Page images | ✓ | 906 `books` rows (dpi=200) |
| 2 Structure | ✓ | chapters 1–8 split under `graduale/<n>/`; `book_toc` book='GRADUALE' (156 rows, chapter 1); `3/subsections_ai.json` (Sanctorale) |
| 3 Index parsed | ✓ | 842 `chant_indices` rows (`gr_index_entry` retired 2026-10-19; archived locally as `gr_index_entry_bak_2026_10_19` with its index-page geometry) |
| 4 Index resolved | ✓ | 792 resolved, 48 reviewed, 2 resolved_with_difficulty; new rows → `tools/resolve_index.py --book GRADUALE --source 4` |
| 5 Epochs | ✓ for loaded chapters | Commons seeded by `seed_commons_epochs.py` |
| 6 Content | ◐ | Temporale (OT 1–34, Lent 0–5, Easter 2–6 …) and all 189 Sanctorale Masses loaded; 397 specs. Open: chapter 4 (Missae rituales, ad diversa, votivae), chapter 6 (Cantus in Ordine Missae), `pasc-post-asc-07` (8 ferial rows never loaded: VERIFY FAIL 39/45), and 3 specs that no longer dry-run (`com-bmv`, `nat-bapt`: incipit/index mismatch; `de-spiritu-sancto`: a notes field > 500 chars) |
| 7 Questions | — | `tools/intake.py list --book GRADUALE` |
| 8 Sweep | ✗ | |

## Addenda (printed 919–921) — added 2026-10-22

A later printing's "Addenda in Graduale Romano" plus "Addenda in Missis propriis O.S.B.", scanned
separately (CamScanner, **no text layer**: read the page images / `books` rows 919–921) and appended
in place of a stray CCWatershed web ad (the old `books` 919 row was that ad; now replaced). The same
day the front CCWatershed inserts were dropped (copyright primer, editions list, Ordinary-Form ad),
the cover photo cropped (label `0`), and the scanned spread split into Imprimatur (4) and Decree (5);
front labels are now 0, 1, 3, 4, 5, 7… (p2/p6 are blank versos not in the scan). Outline entries come from `ADDENDA_HEADINGS` in `build_gr_toc.py`. Queued as units in
`queues/content.json` (11 Masses). Director notes per unit:
- **Every chant is a page cross-reference** (`IN. Adorate Deum, 264.`); nothing is engraved here.
  `printed_page_num` = the addenda page, `ref_page_num` = the cited page. Resolve each via
  `chant_indices` on the cited page as usual.
- `NAT-EPI-00-0-vigil` (5 Jan, vespertine vigil Mass of the Epiphany) and `PASC-ASC-06-5-vigil`
  (Hebd. VI Paschae, Feria IV, vespertine vigil of the Ascension) — both temporal vigil leaves already
  exist with 0 rows. Ascension vigil: `IN. Omnes gentes, 297 (cum alleluia, p. 825)`; `OF. … 231, vel
  Ascendit Deus, 237` (two options); `CO. Psallite Domino (annis A et B), 238` / `Pater cum essem (anno C), 243`.
- `st-maximilian-kolbe` (919–920) cites exactly the five chants already loaded from p596
  (447/125/511/224/470) — confirm and expect `no_rows`.
- `teresa-benedicta-of-the-cross` prints `(In Europa: Festum)`: RULED 2026-10-22 and already applied —
  `proper_of_saints` UNIVERSAL = OPTIONAL_MEMORIAL (also `lit_epoch.rank_code`) + an `EU` row = FEAST
  (the Cyril & Methodius pattern). The chants load as usual (UNIVERSAL); don't raise the rank.
- `john-paul-ii` runs 920→921; `andrew-dung-lac` heads p921.
- OSB entries (epochs created 2026-11-05, intake_queue #39; both tagged `C.S.`, see the `gr-osb-appendix-jurisdiction` memory; `jurisdiction: OSB`):
  `pontons-rochefort-martyrs-osb` (18 Aug, BB. Martyrum Benedictinorum Pontonum Rupifortium) and
  `omnium-sanctorum-osb` (8 Nov, Omnium Sanctorum O.S.P.N. Benedicti, Mem.) are now real epochs
  (rank NULL/UNDETERMINED and MEMORIAL); produce the specs as usual.

## Stages (read by /book-batch)

| Stage | Queue | Producer agent | Output | Validate | Load + verify |
|---|---|---|---|---|---|
| content | `graduale/queues/content.json` (created 2026-10-22 with the Addenda units; `Q add` remaining spec slugs via `/book-intake GRADUALE`) | `content-producer` + `graduale/PRODUCER.md` | `graduale/specs/<slug>.json` | `load_graduale_propers.py --spec-file … --dry-run` | same without `--dry-run`, then `--verify` → VERIFY PASS |

## Director instructions

### Before spawning: anchors
The step-0 resolver (`resolve_gr_subsection.py`) was retired on 2026-10-19 once everything it
covered was loaded. For a unit, resolve by hand and put it in the brief:
- **Slug:** look it up in `lit_epoch` (keyed on `slug`) — never invent one; a missing slug is a
  question. A date-only match can return the WRONG saint (general vs US calendar): match by the
  printed title.
- **Span:** heading page/Y → the next heading's page/Y (the boundary NOT to cross), from `book_toc`
  (chapter 1), `graduale/<n>/subsections*.json`, or the page itself. Spans derived from TOCs can
  under-report a multi-page Mass: query `chant_indices` one page past the end. Name what sits just
  above and below the unit so the producer excludes its neighbours.
- **Pre-flight** (the step that made the Sanctorale clean): read the page yourself; query
  `chant_indices` for every cited target page and write into the brief, per chant, the expected
  `chant_uuid` and every collision on that page — two rows of the same part (sometimes the same
  mode too), one incipit cited to two pages as two parts, a page another unit cites as a different
  part. Put every doubtful citation (ellipsis, glossed index form) in one throwaway probe spec in
  `_tmp` and dry-run it before briefing. Fix an index typo it exposes before briefing.
- **Already loaded?** `SELECT COUNT(*) FROM lit_part_sources WHERE lit_epoch_slug = '<slug>' AND
  book='GRADUALE'` — EXACT match, never `LIKE 'slug%'` (`thomas` vs `thomas-aquinas`). Loaded ≠
  correct: re-read pages for slugs loaded by earlier pipelines.

### Modeling rules you enforce (the producer's half is in PRODUCER.md)
- **Paschaltide:** `al1` (part_id 20, the Gradual's slot) = first Alleluia, week default; `al` =
  second; "In feriis omittitur AL." ⇒ that `al` is `wkday:1`. COMPLETENESS waives `gr` there and
  `al1` satisfies the Alleluia slot. A `PASC-AD_ASC-NN` week's Sunday is its `-1` slug (Divine Mercy
  was reslugged from `PASC-OCT-02-1`); confirm the `-1` exists before loading an Easter week.
- **Weeks 1 & 34** have no Sunday: `In feriis` is the week default.
- **Rank markers** (`Mem.`/`Fest.`/`Sol.`) map to `lit_epoch.rank_code` / `proper_of_saints.rank_code`
  (`p_lit_rank`); producers report them, you decide. Absence is not evidence (All Saints prints none);
  ranks are usually preloaded — the marker is a cross-check.
- **Lenten ferias** print no Tract/Alleluia: that COMPLETENESS warning is a false positive.
- **Settled — don't re-raise:** the p532 Sanctorale chapter rubrics (modeled on the `SAINTS`
  epoch); T.P. variants sharing a `chant_group` with their non-T.P. form (global logic; don't split).
- "Ut supra" / "praeter" inheritance rubrics are still UNRULED: grep for them at recon and ask.

### Review and load
- Re-run the dry-run yourself. Require every chant `-> gregobase:<id>` (ideally `via index`) and a
  sane bbox. `⚠ COMPLETENESS` is a blocker. Confirm each option's part against the target page's
  `chant_indices` row; no index row for a part on a page ⇒ cross-reference. Engraved rows have NULL
  `ref_page_num`, xrefs set — the classic error on a mixed Mass. Read the spec's `notes` prose too
  (a factual error there is stored provenance no check can see).
- Load, then `--verify` per spec → `VERIFY PASS` (asserts ROW COUNT, IDEMPOTENT, REF_PAGE_NUM;
  dedup and verify are scoped by `book='GRADUALE'`). ⚠ ROW COUNT compares against the base-slug
  family, so a spec sharing its base slug with another loaded spec over-counts — read the table.
- Loaders never overwrite a `chant_uuid`. After curating a `chant_indices` row, repoint the loaded
  `lit_part_sources` rows (and any GREGORIAN_MISSAL twin) by hand; if the chant_group changed, the
  spec goes non-idempotent until you do.

## Known decisions
`graduale/specs/README.md` ("User rulings"), the `gr-*` memories, and per-month Sanctorale rulings in
`graduale/3/<month>/DECISIONS.md`.
