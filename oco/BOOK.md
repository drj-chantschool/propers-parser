# Ordo Cantus Officii — editio cum cantu v.6 (A.D. MMXXV) — intake profile

| | |
|---|---|
| Book code | `OCO` (assignments of OCO 2015; pages are the v.6 sung edition — `p_sources.notes`) |
| Master PDF | `oco/oco.pdf` — "Ordo Cantus Officii, editio cum cantu, v.6, A.D. MMXXV" (PDF dated 2025-07-23; colophon still "Mecklingae Suevorum, die 22 Sept. 2023"). 1319 PDF pages = printed 1–1320 minus 974, outline (694 entries), text layer, link annotations, no PDF page labels. Replaced v.4 (A.D. MMXXIII) on 2026-10-20 |
| Printed-page rule | v.6: printed = PDF page for 1–973; the blank verso printed 974 is not in the PDF, so PDF 974–1319 = printed 975–1320 (every running head checked). `oco/oco_pages.py` converts; `oco/page_mapping_v6.json` → `seed_books.py --mapping`. Every DB page is PRINTED. No printed contents page; pp1–2 title + blank, body from p3 |
| gregobase source | none for this edition. Engravings cite AM→7, ARII→6, PM→24, RM→56, AR→9 and CAO (= `cantusid`); see `oco/resolve_oco_index.py` |
| Assignment authority | `OCO` |
| Text layer | yes. Each engraving's full text is printed in WHITE just above the staff, then a visible ref line (`cf. Ier 31,10; CAO 1428; ARII 3`). Music font extracts as noise |
| Unit model | **printed page** (one spec per page: every engraving that begins on it + every cue printed on it). The page is the authority for LPS; the index and the PDF's named destinations are a finding aid and a deterministic first pass the producer verifies — user, 2026-10-23 (supersedes "index row", 2026-10-20) |
| TOC | `oco/toc.json` (outline + 2 fixes, user OK 2026-10-20) → `book_toc` 694 rows |
| Index | `oco/parse_oco_index.py` → `oco/index/i<page>.json` → `chant_indices` (3,422 rows); report `oco/index_parse_report.txt` |
| Contract README | `oco/specs/README.md` (page contract) |
| Agent instructions | `oco/PRODUCER.md` (agent `content-producer`). `oco/RESOLVER.md` = the retired index-rows stage |
| First pass / loader | `oco/page_draft.py <page>` (named destinations + cue links → `oco/oco_sigla.py` proposals) / `oco/load_oco_page.py --spec … [--dry-run / --verify]`, `--legacy-report`. Identity helpers `oco/show_row.py`, `oco/candidates.py`. Retired index-pass loader: `oco/load_oco_lps.py` (don't run it any more: it would re-add rows the pages replaced) |

## Status (2026-10-23)

| Phase | State | Evidence |
|---|---|---|
| 0 Register | ✓ | `p_sources` (notes set 2026-10-20), `p_assignment_authority` |
| 1 Page images | ✓ 2026-10-20 (v.6) | 1319 `books` rows, printed 1–1320 without 974 (v.6 images; v.4 seeded 2026-10-19) |
| 2 Structure | ✓ 2026-10-20 | `book_toc` book='OCO' 694 rows; 625 leaf headings |
| 3 Index parsed | ✓ 2026-10-20 | 3,422 rows: antiphona 2,779 · hymnus 353 · responsorium breve 212 · invitatorium 78 |
| 4 Identity | ◐ | 1,115 resolved · 583 resolved_with_difficulty (chant) · 244 resolved_with_difficulty (group) · **1,480 queued** |
| 5 Epochs | ◐ | mapper places 3,276/3,422 rows (`oco/sigla_coverage.txt`; B1/M2-type rows get their epoch from the agent, intake #22); TOC cross-check `oco/oco_toc.py --check`: 1,750 own-engraving rows, 0 real disagreements; calendar fixes: Elizabeth of Portugal UNIVERSAL 4/7 + US 5/7 (#20), Paul of the Cross UNIVERSAL 19/10 + US 20/10 (#21) |
| 6 Content (LPS) | ◐ | stage `pages` started 2026-10-23: 1,206 pages in 4 lanes. Legacy index-pass rows: 2,203 (notes 'OCO index #…' + 11 Lent xrefs), adopted or replaced page by page (`load_oco_page.py --legacy-report`) |
| 7 Questions | ◐ | #12–28, #32 done; open #33 (identity), #34 (Marian antiphons), #35 (Alleluia rubric rows); #29–31 withdrawn 2026-10-23 (index-code disagreements: the page decides) |
| 8 Sweep | ✗ | end of `pages`: review `--legacy-report` (legacy rows no page adopted). **After the Commons lane (975–1161) is loaded** (intake #38): for each Common / sub-Common with a page-owned `VESPERS1.antM`, add a `VESPERS.antM` row, same chant, `rank_code` MEMORIAL, next free `option_num`, `option_txt` 'Ad libitum', `printed_page_num` 975, notes `OCO sweep #38: p975 'Si de Communi, antiphonae ad Magnificat, quae pro I Vesperis indicantur, possunt adhiberi ad libitum ad Vesperas' (In memoriis)` (not 'OCO p…': a page reload would prune it; it shows in `--legacy-report`, expected). Answer said MEMORIAL; if OPTIONAL_MEMORIAL / PROPER_MEMORIAL rows would be needed for it to apply to optional memorials, ask first |

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
| pages | `oco/queues/pages.json` (log `oco/INTAKE_LOG.md`), 1,206 printed pages, 4 strict lanes, batch 4, wait 30 | `content-producer` + `oco/PRODUCER.md` | `oco/specs/p<NNNN>.json` | `oco/load_oco_page.py --spec … --dry-run` (exit 0 / 3 questions / 4 blocked_dep / 1 error) | `--spec …` then `--verify` → VERIFY PASS |

Retired 2026-10-23 (queues kept as the record, not in this table so nothing picks them up):
`oco/queues/conflicts.json` (23 loaded, 6 held) and `oco/queues/index-rows.json` (44 loaded, 5 held, 1,460
never worked). Their held rows are pages now (the page decides).

Brief extra: "The previous page in your lane is {prev}: its spec, if present, is `oco/specs/p{prev:04}.json`;
read its `context_out` first. Start with `oco/page_draft.py <page>`: it is a proposal from the index codes;
the page decides."

## Director instructions

- **Lanes:** A psalter 548–700 → Appendix 1177–1209 → Sanctorale Aug–Dec 829–973; B Temporale 3–257
  (Advent → Holy Saturday); C Communia + Officium defunctorum 975–1176 → Sanctorale Jan–Jul 701–828; D Temporale
  258–547 (Easter Sunday first — the octave pages cite it — then Paschaltide, per annum, solemnities). Rebuilt after batch 1. Commons first in lane C so Sanctorale cues find their
  target identities; until then those pages exit 4 (`blocked_dep`), expected.
- **Pre-flight** per unit: run `oco/page_draft.py <page> --quiet` and render the page; pass both paths.
- **Review** on top of /book-batch step 5: every drop cap beginning on the page has a row and nothing
  continued from the previous page does; every cue line (hymn, `Ut in hebd.`, `Vel:`, `de Communi`,
  `ut ad …`, a `vel` inside a cue) has a row; slot/day/option per row match the page's heading, hour label,
  siglum and rubric (not just the draft); `ADOPTS`/`REPLACES legacy` lines make sense (a replacement means
  the page prints a different chant there); each identity was checked against the engraving (neumes, mode,
  termination), not only accepted from `index_id`.
- **Index disagrees with the page** (wrong day/hour code, wrong link page): the page wins, a `flags` line,
  no question, no `chant_indices` edit (user, #27).
- **Load by dry-run exit code:** 0 → load, `--verify`, `Q finish <p> loaded --summary '<last JSON line>'`
  (`no_rows` for `continuation_only` / `no_chant`); 3 → raise each question, `Q finish <p> held --question <id>`;
  4 → `Q finish <p> blocked_dep --note "<cited pages>"`, retried in step 3 once the cited page is loaded;
  1 → fix if certain, else `error` + log.
- `inherits` entries (`Omnia ut in …`): first time, raise one question (topic_key `oco-omnia-inherits`), then
  merge later pages into it; the page loads without them.
- **Allowed without asking:** a missing sub-epoch for a printed subject condition (`lit_epoch` kind as its
  parent, title = the printed heading, notes 'OCO sub-epoch (user 2026-10-23: structure before option_txt)',
  plus the `lit_epoch_tree` row; log it); a placeholder local chant (`chants` row `chant_uuid='local:<uuid>'`, `elements='[]'`) for a chant absent from gregobase (LH ruling
  2026-10-16; add it to the log); a missing saint epoch is a question, not allowed.
- Never run `oco/load_oco_lps.py` (retired): it re-adds index-code rows. Never re-run `parse_oco_index.py` +
  `load_index.py` in a way that drops links (the index is still the finding aid).

## Known decisions for this book

- 2026-10-23 (#38) Communia preamble p975: Commons' I Vespers Magnificat antiphons are ad-lib options at Vespers
  in memorials only (`rank_codes` MEMORIAL, not Feasts/Solemnities); one sweep after the Commons lane (phase 8).
- 2026-10-23 **page sweep** (user): the page is the authority for LPS, the index a finding aid with a deterministic
  first pass (named destinations + cue links → mapper proposals, `oco/page_draft.py`) that the producer verifies
  on the page. Reasons: the index misses cross-references and isn't accurate (#25, #27, #29–31: codes contradict
  the body; #32: a printed `vel` hymn the index never lists). Stages `index-rows` and `conflicts` retired; legacy
  index-pass rows are adopted/replaced by page loads.
- 2026-10-23 structure before `option_txt` (user): "any time option text can be modeled by our data structure, do
  that. They should go in sub-epochs." Subject qualifiers → sub-Commons (mapper SUBJECT_EPOCHS for the
  unambiguous ones); the loader moves a legacy parent-Common row into the sub-epoch (`adopt-move`). 16 legacy rows
  carry such qualifiers; they move as their pages load. T.P./Q./per annum inside an office stay option_txt
  (global T.P. logic, earlier user ruling).

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
