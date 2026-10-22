# Ordo Cantus Officii — editio cum cantu v.6 (A.D. MMXXV) — intake profile

| | |
|---|---|
| Book code | `OCO` (assignments of OCO 2015; pages are the v.6 sung edition — `p_sources.notes`) |
| Master PDF | `oco/oco.pdf` — "Ordo Cantus Officii, editio cum cantu, v.6, A.D. MMXXV" (PDF dated 2025-07-23; colophon still "Mecklingae Suevorum, die 22 Sept. 2023"). 1319 PDF pages = printed 1–1320 minus 974, outline (694 entries), text layer, link annotations, no PDF page labels. Replaced v.4 (A.D. MMXXIII) on 2026-10-20 |
| Printed-page rule | v.6: printed = PDF page for 1–973; the blank verso printed 974 is not in the PDF, so PDF 974–1319 = printed 975–1320 (every running head checked). `oco/oco_pages.py` converts; `oco/page_mapping_v6.json` → `seed_books.py --mapping`. Every DB page is PRINTED. No printed contents page; pp1–2 title + blank, body from p3 |
| gregobase source | none for this edition. Engravings cite AM→7, ARII→6, PM→24, RM→56, AR→9 and CAO (= `cantusid`); see `oco/resolve_oco_index.py` |
| Assignment authority | `OCO` |
| Text layer | yes. Each engraving's full text is printed in WHITE just above the staff, then a visible ref line (`cf. Ier 31,10; CAO 1428; ARII 3`). Music font extracts as noise |
| Unit model | **index row** (one `chant_indices` row = identity + its LPS rows) — user, 2026-10-20 (supersedes "page") |
| TOC | `oco/toc.json` (outline + 2 fixes, user OK 2026-10-20) → `book_toc` 694 rows |
| Index | `oco/parse_oco_index.py` → `oco/index/i<page>.json` → `chant_indices` (3,422 rows); report `oco/index_parse_report.txt` |
| Contract README | `oco/specs/README.md` |
| Agent instructions | `oco/RESOLVER.md` (agent `index-row-resolver`) |
| Mapper / loader | `oco/oco_sigla.py` / `oco/load_oco_lps.py` (`--dry-run` / real / `--verify`) |

## Status (2026-10-20)

| Phase | State | Evidence |
|---|---|---|
| 0 Register | ✓ | `p_sources` (notes set 2026-10-20), `p_assignment_authority` |
| 1 Page images | ✓ 2026-10-20 (v.6) | 1319 `books` rows, printed 1–1320 without 974 (v.6 images; v.4 seeded 2026-10-19) |
| 2 Structure | ✓ 2026-10-20 | `book_toc` book='OCO' 694 rows; 625 leaf headings |
| 3 Index parsed | ✓ 2026-10-20 | 3,422 rows: antiphona 2,779 · hymnus 353 · responsorium breve 212 · invitatorium 78 |
| 4 Identity | ◐ | 1,115 resolved · 583 resolved_with_difficulty (chant) · 244 resolved_with_difficulty (group) · **1,480 queued** |
| 5 Epochs | ◐ | mapper places 3,276/3,422 rows (`oco/sigla_coverage.txt`; B1/M2-type rows get their epoch from the agent, intake #22); TOC cross-check `oco/oco_toc.py --check`: 1,750 own-engraving rows, 0 real disagreements; calendar fixes: Elizabeth of Portugal UNIVERSAL 4/7 + US 5/7 (#20), Paul of the Cross UNIVERSAL 19/10 + US 20/10 (#21) |
| 6 Content (LPS) | ◐ | 2,114 `lit_part_sources` rows (book OCO); 30 conflicts held → stage `conflicts`; 146 ad-lib waiting for a primary |
| 7 Questions | ◐ | #12–22 done; open: #23 (Lent III–V Year-A sets → option_txt?) |
| 8 Sweep | ✗ | |

## Structure notes

- Parts (v.6 printed): I Proprium de tempore 3–547 · II Psalterium 548–700 (Completorium 684, Psalmodia
  complementaris 698) · III Proprium de sanctis 701–973 · IV Communia 975–1161 · V Officium
  defunctorum 1162–1176 · VI Appendix 1177–1209 · VII Indices 1210–1316 (Sigla 1210–1213, Hymni
  1214, Invitatoria 1225, Antiphonae 1228, Responsoria brevia 1310). 1317–1320 blank/colophon.
- Leaf headings: Tempore 357, Sanctis 212, Psalterium 30, Communia 16, Appendix 4, Defunctorum 1.
- Page layout: hour in the left margin (I Vesp., Off. lect., Laudes, Hor. med., Vesp., Compl.), part
  siglum (H hymn, Ɽ br., B/M canticle antiphon, psalm antiphons 1–3, Inv.), mode + engraving, ref
  line above. Hymns are "Name (LHym N)" cross-references (LH page N; LH is loaded). Inheritance
  rubrics: "Ut in hebd. I.", "de Communi pastorum", "de die 4 augusti", "ut supra ad Vesperas",
  TQ:/TP:/Vel: alternatives. Underlined margin numbers (e.g. "166" on p695) are links — meaning TBD.
- Body links: 458 internal (named dests), 391 gregobase URIs (mostly hymns) — usable by producers.

## Index facts (phase 3)

- Every index entry is a link. Antiphon/responsory/invitatory links go to the page where the chant
  is ENGRAVED (its named dest names that first assignment, e.g. `A[6Q7,L,2]`, so it may differ from
  the row's own day/hour/place). Hymn links are gregobase URIs → `chant_uuid`, `page` NULL, `LHym N`
  in notes.
- `day_code` / `hour_code` / `place_code` hold the printed sigla verbatim (incl. odd ones: `Sab` and
  `M2` in the Officium column).
- `- cum alleluia` rows and ditto rows (incipit not reprinted) take the previous incipit; notes say so.
- 48 rows have `page` NULL: 7 empty GoTo links (p1230 'Alleluia' Paschal-weekday entries), 41 named
  dests that resolve to the blank last page (notes give the dest name).
- 69 rows whose link target page does not contain the incipit text verbatim (abbreviations "a. d.",
  typos "In prasepio", Marian antiphons without a white text line) — page kept (book's own link);
  listed in `oco/index_parse_report.txt`.

## Stages (read by /book-batch)

| Stage | Queue | Producer agent | Output | Validate | Load + verify |
|---|---|---|---|---|---|
| conflicts | `oco/queues/conflicts.json` (log `oco/INTAKE_LOG.md`), 29 units (the rows of `oco/lps_conflicts.txt`), unordered, batch 5, wait 30 | `index-row-resolver` + `oco/RESOLVER.md` § Stage `conflicts` | `oco/index/resolve/c<row_id>.json` | director reads the cited page | `option` → `oco/apply_oco_verdict.py <file> --commit`; `hold` → `tools/intake.py raise` the question (user decides) |
| index-rows | `oco/queues/index-rows.json` (log `oco/INTAKE_LOG.md`), 1,480 units + 30 identified B1/M2-type rows for verdict `assign` (intake #22), unordered single lane in priority order, batch 5, wait 30 | `index-row-resolver` + `oco/RESOLVER.md` | `oco/index/resolve/r<row_id>.json` | director re-checks against the page (`oco/show_row.py <row_id>`, `tools/render_page.py --book OCO <p>`) | `oco/apply_oco_verdict.py <file> --commit [--apply-index-fix]` (identity → override → LPS → verify) |

Brief extras per stage:
- conflicts: "Read `oco/RESOLVER.md` § Stage `conflicts`. Identity is set; decide only whether the page
  makes this hymn a further option (`option` + rubric) or not obviously (`hold` + question)."
- index-rows: "Read and follow `oco/RESOLVER.md` (overrides the generic agent file). Start with
  `oco/show_row.py <row_id>`. A `group` verdict is allowed. If LPS TARGETS prints a reason, give the
  `assignment`. Rows with page NULL: find the engraving, `index_fix` the page."

## Director instructions

- index-rows: after the batch's verdicts are applied, run `oco/load_oco_lps.py` once (whole book): it
  picks up ad-lib options whose primary has just arrived; it must report 0 new conflicts beyond
  `oco/lps_conflicts.txt` (a new one → review, raise if it needs a ruling).
- An `ambiguous` verdict: apply (status only) and raise its `question` with `tools/intake.py raise`.
- A unit whose verdict needs an `index_fix` of the page: check the page yourself, then `--apply-index-fix`.

- Index rows: never re-run `parse_oco_index.py` + `load_index.py` in a way that drops links; the
  loader is an upsert and never overwrites `chant_uuid`.
- Resolver: `oco/resolve_oco_index.py [--commit] [--units-file …]` only touches rows with NULL
  status; its report is overwritten each run.

## Known decisions for this book

- 2026-10-19 printed page = PDF page (seeded with `--identity`).
- 2026-10-20 toc.json from the outline with Feria II 50→49, Feria III 51→50 (Dec 17–23 antiphons): user OK.
- 2026-10-20 keep code `OCO`; `p_sources.notes` names the editio cum cantu (now v.6).
- 2026-10-20 v.6 replaced v.4 (user). Re-checked: the 3,422 index rows are identical (same order, incipits,
  codes, hymn links) → ids, identities, overrides and queues carry over; only pages moved (v.6 adds Lent III–V
  rubrics 'si quavis die legatur evangelium de Samaritana …' → reflow pp172–219; Sanctis starts at 701).
  Re-derived from v.6: books images, book_toc (231 entries moved; Feria II/III outline fix still needed),
  chant_indices.page (1,018 rows; the 9 manual page fixes re-found in v.6 + #2431 newly broken link → 1097),
  lit_part_sources.printed_page_num (515 rows), index files. One text change: 'manducait' → 'manducavit'
  (#2354). v.6 defect: p184's hidden text/ref line belong to 'Amen amen dico vobis: Non Moyses' while the
  engraving is 'Amen dico vobis, quia nemo propheta' (#548/#549).
- 2026-10-20 index: link targets are the page; the day/hour/place codes get their own columns (user).
- 2026-10-20 unit model: page, LH-style (user) — superseded the same day: one combined pass per index
  row (identity + LPS from the codes), queue priority psalter+Compline → Defunctorum → seasons → commons →
  sanctorale → rest (user).
- 2026-10-20 group-only matches stored in `chant_group_id` (user); Office parts added, hora media = MIDDAY (user).
- 2026-10-20 6P5 = `PASC-AD_ASC-06-5` (exists). Easter week 6 Thu–Sat: `ante Asc` → PASC-AD_ASC-06-d,
  `post Asc` → PASC-POST_ASC-06-d (no option_txt); unqualified → agent decides from the page/TOC (user:
  "make sure the agent knows that one's ambiguous"). `2-7P6/7` load on both.
- 2026-10-20 held conflicts: the agent reads the page; obvious → further option with the printed rubric,
  else intake question (user). Unexplained codes → intake, one question per code (user).
- 2026-10-20 psalter rank tones (`1.3H mem.`, `2.4H fest.`, `… soll.`) are per annum only → `lit_epoch_slug='OT-OT'`
  + rank_code + wknum_mod_2, like LH's OT-OT "in memoriis" rows; plain psalter codes stay epoch-less (user).
  The 40 rows loaded epoch-less were re-keyed in place.
- 2026-10-20 the TOC is evidence for the mapper (user): `oco/oco_toc.py` (saints per date in book order,
  page spans) + `--check` cross-check.
