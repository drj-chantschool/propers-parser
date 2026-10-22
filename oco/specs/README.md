# OCO contract — index rows → `chant_indices` identity + `lit_part_sources`

OCO's alphabetical indices (pp1214–1316) are the assignment list: every entry names a chant, the page
where it is engraved (PDF link) and where it is sung (day | hour | place sigla, legend pp1210–1213).
A unit is ONE `chant_indices` row. Content is not parsed page by page.

## Pipeline

| step | tool | writes |
|---|---|---|
| parse index | `oco/parse_oco_index.py` → `tools/load_index.py --book OCO oco/index` | `chant_indices` (codes in `day_code`/`hour_code`/`place_code`) |
| identity, cited editions | `oco/resolve_oco_index.py --commit` | `chant_uuid`, `resolved` |
| identity, any edition by full text | `oco/resolve_oco_text.py` (+ commit step in INTAKE_LOG) | one chant → `chant_uuid`; one group → `chant_group_id`; both `resolved_with_difficulty` |
| identity, the rest | queue `index-rows`, agent `index-row-resolver` + `oco/RESOLVER.md` | verdict file; director: `oco/apply_oco_verdict.py <file> --commit` |
| assignment | `oco/oco_sigla.py` (mapper), `oco/load_oco_lps.py` (loader, `--dry-run`/`--verify`) | `lit_part_sources` book/authority `OCO` |

## LPS row conventions (follow the LH contract, `lhymn/specs/README.md`)

- `book='OCO'`, `assignment_authority_code='OCO'`, `jurisdiction='UNIVERSAL'`, `review_status='draft'`,
  `printed_page_num` = engraving page; hymns: `printed_page_num` NULL, `ref_book='LIBER_HYMNARIUS'`,
  `ref_page_num` = LHym page. `notes` = `OCO index #<id>: <day> | <hour> | <place>`.
- Identity: `chant_uuid`, or `chant_group_id` with `chant_uuid` NULL (group match, user ruling 2026-10-20).
- Hours: 1V→VESPERS1, 2V/V→VESPERS, L→LAUDS, Ol→OFFREAD, T/S/N→TERCE/SEXT/NONE `ant` (places 1-3 → `ant1-3`), Hm→MIDDAY,
  C→COMPLINE; `L-V`, `Ol V`, `1-2V` → one row per hour. Places 1–3→ant1–3, B→antB, M→antM, Nunc→antN,
  Ma1–4 (C)→antMar, CV/C at Ol→VIGILIAE.antcv. Short responsories → `<hour>.resp`.
- Cycle letters: a/b/c → `cycle_sun` 1/2/3 (`Mbc` → two rows); I/II → `cycle_wkday`.
- Psalter: null epoch + `wkday`; 1.3/2.4 → `wknum_mod_2` 1/0; week k → `wknum_mod_4` k%4; `H0` =
  Saturday-night Compline (after I Vespers of Sunday) → `wkday 7`.
- Rank suffixes: mem. → MEMORIAL+OPTIONAL_MEMORIAL, fest. → FEAST+FEAST_OF_THE_LORD, soll. → SOLEMNITY,
  one row each; `fer TpA` → OT-OT + WEEKDAY.
- Easter week 6 Thu–Sat: `ante Asc` → `PASC-AD_ASC-06-d`, `post Asc` → `PASC-POST_ASC-06-d`, no option_txt;
  no qualifier → not mapped (agent decides from the page). `2-7P6/7` → both slugs.
- Multi-saint dates: the TOC (`oco/oco_toc.py`) picks the saint whose section holds the page; B1/M2-style
  places are options n of an office whose epoch the agent gives (intake #12/#16/#22; the n-th-saint reading
  is kept off behind `NTH_SAINT_RULE`).
- Advent IV and the 17–23 Dec weekday sets → `ADV-II` + `wkday` (GR precedent).
- Options: a printed qualifier (TP, TQ, TpA, ante/post Asc, pro pluribus, pro una martyre, pro ecclesiis
  minoribus, Ad libitum n …) → `option_txt`, `option_num` = next free in the slot. No qualifier → option 1.
- Hourless `ad lib n` (antiphons ad libitum pro canticis evangelicis) → LAUDS.antB + VESPERS1.antM +
  VESPERS.antM. `Sab` hour → COM-BMV-SAB LAUDS.antB option.

## Loader guards

- Two DIFFERENT chants claiming option 1 of one slot → CONFLICT, not loaded (`oco/lps_conflicts.txt`).
- An `Ad libitum` option waits until its slot has an option-1 primary (an ad-lib alone in a more specific
  slot would hide the primary in the day query). Re-run `oco/load_oco_lps.py` after each batch to pick up
  the ones whose primary has arrived.
- Codes the mapper can't place (multi-saint dates the TOC can't split, odd places) are skipped; an agent verdict's
  `assignment` → `oco/index/lps_overrides.json` supplies the slugs.

## User rulings

- 2026-10-20 (intake_queue #18) hour column `M` = the hour is missing and `M` is the place (Magnificat):
  read as `V | M<place>` (checked on the pages: 13/4 Martin I p763 'M … TP: Ecce quomodo computati';
  13D p424 II Vesp. 'vel, ad lib. Quisquis enim'). Engravings may sit in a Common (PlM/UnM ad lib pages).

- 2026-10-20 (intake_queue #12, #16, #22) `B1/B2/B3`, `M1/M2/M3` = ALTERNATIVE antiphons for one office →
  LAUDS.antB / VESPERS.antM with `option_num` = n (fixed by the code, not the next free). Trailing `TP` =
  Paschaltide (option_txt). `TpA` on them: unsettled, not loaded. The epoch (which saint(s) of the date) is
  given by the agent from the page (`assignment`); 30 already-identified rows were added to index-rows with
  verdict `assign`.

- 2026-10-20 (intake_queue #15) `TP | V | Ma5/Ma5b/Ma5c` = Regina caeli after Compline in Paschaltide (hour V
  is a misprint for C) → PASC `COMPLINE.antMar`: Ma5 solemn (p695) option 1, Ma5b '[simpl.]' mode 6 (p696)
  'Tonus simplex (modus 6)', Ma5c '[simpl.]' mode 1 (p697) 'Tonus simplex (modus 1)'. Index pages for b/c fixed.

- 2026-10-20 (intake_queue #14) `H | T/S/N | 1-3` (complementary psalmody, every day) → `TERCE/SEXT/NONE.ant1-3`
  (new parts), null epoch, no wkday. Feasts and solemnities mostly have their own single T/S/N antiphon
  (`.ant`). The index link can point to the WRONG engraving: six of these nine linked to an earlier
  psalter-week engraving of the same text (fixed to pp698-700 in v.6; 699-701 in v.4); always confirm the engraving belongs to
  the row's own day/hour (TOC + rubric) and `index_fix` the page if not.

- 2026-10-20 (intake_queue #13, #17) `5Q1 L B*` and `5Q1 2V M*` = Benedictus antiphon for when the Lazarus gospel (Jn 11) is read
  → LAUDS.antB, `option_txt` 'cum Evangelio de Lazaro', NOT cycle_sun 1: "any parish might use the A Gospel
  in any year". (intake_queue #23) The same for every Year-A ('a') antiphon of the 3Q1/4Q1/5Q1 Sundays
  (B, M, T/S/N): the book says "Quae antiphonae etiam aliis annis adhibendae sunt, si legatur evangelium
  de …" (v.6 pp178/194/211) → no cycle_sun, option_txt 'cum Evangelio de Samaritana / de caeco nato / de
  Lazaro' (`LENT_A_GOSPEL`). General rule: where the book explains that another Gospel may be read, leave
  cycle_sun blank. (intake_queue #24) The weekday rubrics 'Infra hebdomadam, si quavis die legatur evangelium de …'
  (pp183/199/215-216) load as options on that week's weekdays: `LENT_XREFS` in `oco/load_oco_lps.py` (6 entries:
  Aqua / Mulier venient dies, Rabbi / A saeculo, Lazarus amicus / Domine si hic), chant = the Sunday index row's,
  Lauds Mon-Sat, Vespers Mon-Fri (Saturday evening is I Vespers of Sunday), printed_page_num = rubric page,
  ref_book OCO + ref_page_num = engraving; held until the weekday has its own option-1 antiphon.

- 2026-10-20 held conflicts: agent reads the page; an obvious printed rubric → next option with that
  `option_txt`, otherwise an intake question. Unexplained codes → intake, one per code (#12–19).
- 2026-10-21 (intake_queue #26) index-only second melody: the hymn index lists two rows for one slot (same
  hymn, same day/hour code, LHym N and N+1) but the feast page names only one → the other loads as the slot's
  next option, `option_txt` 'Alia melodia (LHym <its own N>)'. The page simply doesn't repeat the second melody
  (Eia mater 15/9 L: LHym 436 option 1, LHym 437 option 2). Applies to every such pair (e.g. 'Stabat mater 2').
- 2026-10-20 Easter week 6 Thu–Sat is ambiguous without `ante/post Asc`: never guess.

- 2026-10-20 index link target = the page; day/hour/place codes stored as printed in their own columns.
- 2026-10-20 group-only matches are stored (`chant_group_id`), not forced to an edition.
- 2026-10-20 Office hours get antiphon/short-responsory parts; hora media is its own `MIDDAY` service.
- 2026-10-20 one combined pass per index row (identity + LPS); queue priority: psalter + Compline, Office of
  the Dead, seasons in order, commons, sanctorale, rest.

## Known quirks

- Master PDF is v.6 (A.D. MMXXV): printed p974 (a blank) is missing, so PDF = printed − 1 from p975.
  Every stored page is printed; convert with `oco/oco_pages.py`. v.6 p184: hidden text/ref line of another
  antiphon (the engraving is 'Amen dico vobis, quia nemo').

- 48 index links are broken (41 vigil-canticle sets → Appendix pp1179–1200; 7 p1230 'Alleluia').
- Gregobase splits versions of one antiphon across several chant_groups; text alone often can't choose.
- Index typo `2h3` (= 2H3) is folded by the mapper.
- A `link`/`group` verdict that also carries an `index_fix`: `apply_oco_verdict.py --apply-index-fix` does NOT write
  the page (`tools/apply_index_verdict.py` applies `index_fix` only for verdict `index_error`). Director: write the
  page (+ a `notes` line) by hand and check it. Missed for r6191 in batch 2; fixed 2026-10-22.
- A gregobase chant_group often mixes melodic variants (single note vs clivis/pes on one syllable, a different
  final cadence, a different psalm-tone termination, e.g. 8c `h h f h i h` vs `h h g h f e`). Before a `group` verdict,
  compare EVERY syllable and the Euouae of each member with the engraving; if one member matches and another doesn't,
  it is a `link`. Producers gave `group` wrongly twice in batch 4 (r6351 → 10713, r6382 → 11082); 2026-10-22.
