# OCO page specs — contract (stage `pages`)

**The page is the authority; the index is a finding aid** (user, 2026-10-23). One JSON spec per
**printed page**, `oco/specs/pNNNN.json` (4-digit pad), records every assignment the page prints: which
chant is sung at which liturgical act. The product is `lit_part_sources`. `chant_indices` and the PDF's
links only help find and identify things. Where the index's day/hour/place codes disagree with the page,
the page wins: follow it, add a `flags` line. Don't raise a question about it and don't edit `chant_indices`
(user, intake #27: "do not waste any more time trying to re-code the index").

Backend: `oco/load_oco_page.py` (`--dry-run` / load / `--verify`). First pass: `oco/page_draft.py <page>`.

## The page rule

A page assigns:
1. every chant whose **engraving begins** on it (drop cap, mode, staff), to the act its headings give
   (day heading › hour label in the left margin › part siglum › rubric);
2. every **cue** printed on it, as an `xref` row: a hymn cue `Name (LHym N)`, `Name ut ad Vesperas`,
   `Ut in hebd. I.`, `Vel: Dum esset summus pontifex`, `Non enim vos estis, de Communi pastorum`,
   `Aqua ut supra pro anno A, ad Benedictus`. A cue line belongs to the page it is printed on, even when it
   closes the previous page's office (p932's top line `Vel: Dum esset summus pontifex` is St Leo's).

An engraving that continues from the previous page is `continues`, not a row. A page with only the tail
of a chant is `continuation_only`; title, blank, rubric-only pages are `no_chant`. Never add a row for
something this page doesn't print. An index row that reuses this page's engraving for another day gets
its row on the page that prints the cue for that day (or nowhere, if no page prints it — then it is an
index-only claim, see "Index-only rows").

## The deterministic first pass

`python oco/page_draft.py <page>` (read-only) writes `oco/drafts/pNNNN.json` and prints:
- **READING**: the page's text outside the staves in order: headings, hour labels, sigla with their cue,
  rubrics, margin numbers, ENGRAVING markers;
- **ENGRAVINGS**: per engraving its hidden full text (OCO prints it in white above the staff), ref line
  (`Ps 116,1; CAO 3586; PM 314`), siglum, mode, and its **own named destination** (`A[6Q7,Ol,1]` = the
  book's own label: day 6Q7, Off. lect., antiphon 1) with the index row of those codes;
- **PROPOSED ROWS**: the codes of each engraving's destination, each hymn cue's gregobase link and each
  cross-reference link's target, run through `oco/oco_sigla.py`. Identity comes from the index row when one
  is set;
- **NOTES**: what it could not place (an engraving without a destination, a cue with no index row, index
  rows that link here but fit nothing);
- **ALREADY LOADED**: rows now carrying `printed_page_num` = this page.

The draft is a proposal. **Every proposed row is checked against the page image**: slot, day, option,
rubric and identity. Unlinked cues (`Iste confessor ut ad Vesperas`) and `vel` alternatives inside a cue line
(`Salve dies (LHym 210) vel Dies ætasque (LHym 183)`) are not in the proposals; read them off the page.

## Top-level fields

| field | meaning |
|---|---|
| `page` | printed page, string |
| `page_kind` | `assign` · `continuation_only` · `no_chant` |
| `jurisdiction` | not used (all `UNIVERSAL`); per row only if the book prints a regional scope |
| `context_in` / `context_out` | headings in force at the top / bottom (part › day › hour › last rubric), and whether a chant runs over. The next page's producer reads `context_out` |
| `continues` | `{"from_page": "931", "incipit": "…"}` or `null` |
| `rows` | the assignments (below) |
| `inherits` | whole-office references the loader can't expand, e.g. `{"rubric": "Omnia ut in Officio Defunctorum.", "from": "officium-defunctorum"}` (p929), `Omnia de octava Nativitatis Domini, die 26 decembris` (p963). Recorded, not loaded; the director raises them as one intake question class (`oco-omnia-inherits`) |
| `questions` | anything you can't model from the page. **Non-empty blocks the load** (exit 3) |
| `flags` | notes for the reviewer that don't block: index codes that disagree with the page, margin numbers, odd layout |

## A row

```json
{"incipit": "Sacerdos Dei Martine", "kind": "engraved", "mode": "8g",
 "text": "Sacerdos Dei Martine, aperti sunt tibi cæli et regnum Patris mei.",
 "index_id": 2658, "chant_uuid": null, "chant_group_id": null,
 "lit_epoch_slug": "martin-of-tours", "service": "LAUDS", "part": "ant1",
 "wkday": null, "wknum_mod_2": null, "wknum_mod_4": null, "rank_codes": null,
 "cycle_sun": null, "cycle_wkday": null, "option_num": 1, "option_txt": null, "rubric": null}
```

| field | meaning |
|---|---|
| `incipit` | opening words, as printed (accents don't matter) |
| `kind` | `engraved` (staff begins here) or `xref` (a cue) |
| `text` | engraved rows: the engraving's full white text from the draft (the loader checks identity against it) |
| `mode` | as printed (`8g`, `2*d`, `E`, `per.`) |
| `ref_book`, `ref_page` | xref only: `OCO` + the page of the cited engraving (from the link; `ut ad Vesperas` → the page with that office's cue), or `LIBER_HYMNARIUS` + the LHym page N |
| `index_id` | the `chant_indices.id` of this chant, when one fits (gives identity if the row has one) |
| `chant_uuid` / `chant_group_id` | explicit identity: one edition, or a chant_group when every member fits equally (see Identity). Overrides `index_id` |
| `allow_unresolved` | `true` + a `flags` line when no gregobase chant is this chant (the director makes a placeholder local chant (`chants` row `chant_uuid='local:<uuid>'`, `elements='[]'`), LH ruling 2026-10-16) |
| `lit_epoch_slug` / `lit_epoch_slugs` | epoch(s); `null` = psalter (per annum, with the psalter fields below) |
| `service`, `part` | `service_part` codes (table below) |
| `wkday` / `wkdays` | 1 = Sunday … 7 = Saturday |
| `wknum_mod_2` / `wknum_mod_4` | psalter weeks: 1.3/2.4 → `wknum_mod_2` 1/0; a single week k → `wknum_mod_4` k % 4 |
| `rank_code` / `rank_codes` | only when the book conditions the chant on rank (`mem.`, `fest.`, `soll.`) |
| `cycle_sun` / `cycle_wkday` | a/b/c → 1/2/3; I/II → 1/2 (but see the Lent Gospel ruling) |
| `option_num` | 1 = the primary. An alternative: the number the page's order gives, or `null` = the next free number in the slot (counted after the options other pages already put there) |
| `option_txt` | the printed condition of an alternative, in the book's words: `Vel:`, `TP:`, `Ad libitum`, `Quando officium dicitur diurno tempore`, `pro pluribus` … Give option 1 its rubric too when the page prints one (intake #28) |
| `rubric` | the printed rubric(s) governing the row, verbatim |
| `notes` | anything else (≤ 500 chars with `rubric`) |
| `verified_despite` | substrings of `⚠ CHECK` lines you checked against the engraving and accept (explain in `flags`) |

The loader expands `lit_epoch_slugs × wkdays × rank_codes` into one LPS row each.

## Services and parts

| printed | service | parts |
|---|---|---|
| Inv. | `INVITATORY` | `invan` |
| Off. lect. | `OFFREAD` | `hymn`, `ant1-3`, `resp` (Ɽ br.) |
| CV / C at Ol (vigil canticles, Appendix pp1179–1200) | `VIGILIAE` | `antcv` |
| Laudes | `LAUDS` | `hymn`, `ant1-3`, `resp`, `antB` (B, Benedictus) |
| Tertia / Sexta / Nona | `TERCE` / `SEXT` / `NONE` | `hymn`, `ant` (a feast's single antiphon), `ant1-3` (complementary psalmody, intake #14) |
| Hor. med. | `MIDDAY` | `hymn`, `ant1-3`, `resp` |
| I Vesp. | `VESPERS1` | `hymn`, `ant1-3`, `resp`, `antM` |
| II Vesp., Vesp. | `VESPERS` | `hymn`, `ant1-3`, `resp`, `antM` (M, Magnificat) |
| Compl. | `COMPLINE` | `hymn`, `ant1-3`, `resp`, `antN` (Nunc dimittis), `antMar` (final Marian antiphon) |

`I & II Vesp.` / `Vesp. I & II` → a `VESPERS1` and a `VESPERS` row. I Vespers belongs to the
celebration it opens (store it on the Sunday or feast, `wkday: 1` for a Sunday). A part the table lacks →
`questions`. New `service_part` rows are schema changes: the director holds and asks.

## Assignment conventions (the mapper's; the draft proposes them)

- **Psalter** (pp548–700): `lit_epoch_slug: null` + `wkday`; Hebdomada I & III → `wknum_mod_2: 1`, II & IV → `0`;
  a single week k → `wknum_mod_4: k % 4`. `Ut in hebd. I.` for a chant whose own row already covers this week
  (a 1.3H/2.4H code: `wknum_mod_2`) adds **no** row; for a single-week chant (e.g. week I's Benedictus antiphon
  cited in week III) it is an xref row with this week's fields. Complementary psalmody (pp698–700, `H | T/S/N | 1-3`)
  → `TERCE/SEXT/NONE.ant1-3`, null epoch, no `wkday`. `H0` = Saturday-night Compline (after I Vespers of
  Sunday) → `wkday 7`.
- **Psalter rank tones** (`1.3H mem.`, `2.4H fest.`, `… soll.`) are per annum only → `OT-OT` + `rank_codes` +
  `wknum_mod_2` (user, 2026-10-20). Plain psalter rows stay epoch-less.
- **Rank suffixes**: mem. → `MEMORIAL`+`OPTIONAL_MEMORIAL`; fest. → `FEAST`+`FEAST_OF_THE_LORD`; soll. → `SOLEMNITY`.
  `fer TpA` → `OT-OT` + `WEEKDAY`.
- **Advent IV** and the 17–23 Dec weekday sets → `ADV-II` + `wkday` (GR precedent).
- **Easter week 6, Thu–Sat**: before Ascension (pp336–339, TOC before 'In Ascensione Domini') →
  `PASC-AD_ASC-06-d`; after (p350, 'Post Ascensionem Domini') → `PASC-POST_ASC-06-d`, no option_txt. The page's
  heading decides; never guess (user). `2-7P6/7` psalm antiphons go on both.
- **Sanctorale**: the `Die N:` heading names the celebration; find its slug by date in `proper_of_saints`
  and pick by the printed title, never by date alone (`Vel: S. Ansgarii` = a second saint of the date).
  A missing saint → `questions`. B1/B2/B3, M1/M2/M3 in the index = alternative Benedictus/Magnificat
  antiphons of one office (`option_num` n), on the saint(s) the page shows (intake #12/#16/#22).
- **Commons** (pp975–1161): slugs `COM-DED`, `COM-BMV`, `COM-APOST`, `COM-MART-PLUR`, `COM-MART-UNO`,
  `COM-PAST`, `COM-DOCT`, `COM-VIRG`, `COM-SANCT-VIR`, `COM-SANCT-MULIER`, `COM-SANCT-RELIG`; Office of the
  Dead pp1162–1176 `officium-defunctorum`. Subject qualifiers go in **sub-epochs** (next section).
  `Antiphonæ ad libitum` lists of a Common (`ad lib n`) → options (`option_txt` 'Ad libitum') of
  LAUDS.antB + VESPERS1.antM + VESPERS.antM, unless the page names the hour.
  Don't copy a Common's I Vespers Magnificat antiphon to `VESPERS.antM` on the page: the p975 preamble's
  memorial ad-lib rows are one director sweep after the Commons lane (intake #38, BOOK.md phase 8).
- **Sanctorale suggestions** (p701 preamble): antiphons printed by their first words only and taken from
  a Common "meram vim suggestionis" have. They are still assignments the page prints: xref rows with
  `option_txt` from the page (`Vel:` etc.) or as the primary if nothing else fills the slot.
- **Inheritance rubrics**: `Ut in hebd. I.`, `ut supra`, `ut ad II Vesperas`, `de Communi …`,
  `de die 4 augusti`, `ut in dominica Resurrectionis` → xref rows, one per part the cue covers; `ref_page`
  = the cited engraving's page (from the link, or the page that holds that office). `Antiphonæ ut in
  dominica Resurrectionis` covers ant1-3 of that hour: three rows. `Omnia ut in …` → `inherits`.

## Structure before option_txt (user, 2026-10-23)

"Any time option text can be modeled by our data structure, do that. They should go in sub-epochs."
`option_txt` is only for a condition no field or epoch can express. Before writing one, check:

| printed condition | modelled as |
|---|---|
| a subject: "pro pluribus", "pro una virgine", "pro martyre virgine", "pro papa vel episcopo", "pro presbytero", "pro religiosis", "in ipsa ecclesia dedicata" / "in aliis ecclesiis" | the **sub-epoch** of the Common/epoch (`COM-SANCT-VIR-PLUR`, `COM-PAST-UNO-PAPA` + `COM-PAST-UNO-EPISC` via `lit_epoch_slugs`, `COM-MART-UNO-VIRG`, `COM-DED-IPSA` …). Rows the page prints without a subject heading stay on the parent |
| year A/B/C, I/II | `cycle_sun` / `cycle_wkday` (except where the book says another Gospel may be read: #23) |
| mem. / fest. / soll., "in sollemnitatibus" | `rank_codes` |
| psalter week I/III, II/IV, a single week; "in dominica", "in feriis", a named weekday | `wknum_mod_2` / `wknum_mod_4`, `wkday` / `wkdays` |
| before/after Ascension, a named day or season inside a season | the day's / subseason's own epoch (and no `option_txt` repeating it) |
| "Tempore paschali / Quadragesimae / per annum" **inside** a Common or a saint's office | stays `option_txt` (T.P. variants are handled by global logic: user ruling, don't model further) |
| time of day ("Quando officium dicitur noctu …"), "pro ecclesiis minoribus", "Ad libitum", "Vel:", "Alia melodia", "cum Evangelio de …" (#23) | `option_txt` |

Find the sub-epoch: `SELECT t.child_slug, e.title FROM lit_epoch_tree t JOIN lit_epoch e ON e.slug=t.child_slug
WHERE t.parent_slug='<Common>'` (and their children). Pick the narrowest whose title is the printed condition.
If none fits, write the row with a proposed slug `<PARENT>-<CONDITION>` (e.g. `COM-VIRG-UNA-MART` for "pro una
martyre" in the Virgins Common), put the slug and the printed heading in `questions`, and expect the dry-run to
fail on the unknown slug: the director creates it. `page_draft.py` already maps the unambiguous cases
(`oco/oco_sigla.py` SUBJECT_EPOCHS) and marks the others `SUBJECT QUALIFIER … put it in a sub-epoch`. A legacy
row that held the chant on the parent with the qualifier as `option_txt` is ADOPTED and moved (dry-run:
`ADOPTS legacy text_id N from <parent>`), not duplicated.

## Identity

Every row's chant is checked against the engraving, not only against text:
- `python oco/show_row.py <row_id>` (for an index row: siblings, candidates, CAO) and
  `python oco/candidates.py "<engraving text>" [--cao N] [--mode 8g] [--part …]` list gregobase candidates
  with group, mode, cited editions and the opening of the gabc. Render the page
  (`python tools/render_page.py --book OCO <p>`) and compare **opening neumes, one cadence, the Euouae
  termination, the mode and the end of the text** (OCO often prints the SHORT form).
- Several candidates in different groups are common (gregobase splits versions). Pick the one whose
  melody matches; prefer an edition the ref line cites.
- **Group** (`chant_group_id`, no `chant_uuid`; user, 2026-10-20): only when every member of ONE group fits
  the engraving equally. Members often differ by a single note vs clivis, a cadence or the termination;
  check every syllable and the Euouae of each member first. One member matches and another doesn't → that
  one's `chant_uuid` (batch 4: r6351, r6382).
- Same text, different melody = a different chant. No gregobase chant is this chant → `allow_unresolved`
  + flag (the director makes a placeholder). Two melodies fit equally → `questions`.
- `- cum alleluia`, `… all.`, `TP` variants and numbered settings (`Ecce Agnus Dei 1` / `2`) are different chants.
- An index row's identity (`index_id`) is a starting point, not proof: the index pass linked by text and
  cited editions without comparing neumes (p932: 17559 is mode 7, the engraving is 8g). The dry-run prints
  `✓? <id> = '<incipit>' m<mode> <office-part>` and `⚠ CHECK` on a text, mode or office-part mismatch.
  Resolve each CHECK: a better chant, `verified_despite` + flag, or a question.
- Xref rows to an OCO page with no identity of their own take the cited page's loaded identity. If that page
  has no page-spec rows yet the dry-run says `DEPENDENCY` (exit 4): the unit is `blocked_dep`, not wrong.
- Hymn cues: the gregobase link on the cue is the identity (`chant_uuid`); `ref_book` `LIBER_HYMNARIUS`.

## Index-only rows

Some index rows claim an assignment no page prints (e.g. a hymn's second melody, intake #26). User ruling
2026-10-21 (#26): the hymn index lists two rows for one slot (same hymn, LHym N and N+1) but the page names
only one → the other loads as the slot's next option, `option_txt` 'Alia melodia (LHym <its own N>)', on the
page that names the hymn. The draft's NOTES list index rows linked to the page that nothing placed; any other
kind → `flags` (not loaded) unless the page supports it.

## Legacy rows (index pass, 2026-10-20 … 10-23)

About 2,200 OCO rows were loaded from the index codes (`notes` 'OCO index #…'). The page loader:
- **adopts** a legacy row with the same slot and chant (rewrites page, option, option_txt, notes);
- **replaces** a legacy row holding the same slot and option with a different chant (the page wins);
- never touches legacy rows outside the spec's slots. `load_oco_page.py --legacy-report` lists the ones no
  page has adopted; they are reviewed when the sweep ends.
Page-owned rows (`notes` 'OCO p<page>') belong to their page: a reload prunes the page's rows that left the
spec. Two pages claiming one slot + option is an error the director settles.

## Validation (definition of done)

```
set PYTHONUTF8=1
C:\Users\johna\liturgio\.venv\Scripts\python.exe oco\load_oco_page.py --spec oco\specs\p<NNNN>.json --dry-run
```
Exit 0 `DRY-RUN OK`; 3 = open questions (fine when genuine); 4 = a cited page isn't loaded yet; 1 = error.
`ℹ no option 1 in this slot yet` is a note (the primary may come from a later page).

## User rulings (carried over; they hold on the page)

- 2026-10-23 (intake_queue #38) p975 preamble 'Si de Communi, antiphonae ad Magnificat, quae pro I Vesperis
  indicantur, possunt adhiberi ad libitum ad Vesperas' is governed by 'In memoriis': each Common's
  `VESPERS1.antM` gets a copy as a `VESPERS.antM` option, `option_txt` 'Ad libitum', `rank_codes` MEMORIAL
  only (never unconditioned: Feasts take the Common's II Vespers antM, Solemnities keep I/II Vesp. apart),
  rubric quoted in notes. The Common's own `VESPERS.antM`, its ad-lib list and the feria stay valid.
  Done as ONE director sweep after the Commons lane, not on the pages.

- 2026-10-23 (intake_queue #37) a 'Hor. med.: Antiphonæ ut in dominica …' cue whose model day prints one
  antiphon each under Tertia / Sexta / Nona → `TERCE.ant` / `SEXT.ant` / `NONE.ant` (same parts as the model
  day; a Middle Hour said at a given time uses that hour's antiphon), not `MIDDAY.ant1-3`.
- 2026-10-23 structure before `option_txt`: subject conditions are sub-epochs; any condition a field or epoch
  can express goes there (section "Structure before option_txt").
- 2026-10-23 the page is the authority, the index a finding aid; page-by-page sweep with the index codes as a
  verified first pass (this contract).
- 2026-10-21 (#27) a wrong index day/office code is ignored: make the LPS row right from the page, don't
  re-code the index. (Superseded the 2026-10-21 #25 practice of re-coding `chant_indices`.)
- 2026-10-21 (#28) psalter Off. lect. hymn pairs: option 1 gets its printed 'Quando officium dicitur …'
  rubric as `option_txt` too.
- 2026-10-21 (#32) a `vel` hymn in a cue line (p590 'Salve dies (LHym 210) vel Dies ætasque (LHym 183)') is a
  further option of that slot with the governing rubric.
- 2026-10-20 (#18) index hour `M` = Magnificat place; (#19) `M2` = Magnificat option 2.
- 2026-10-20 (#12, #16, #22) B1-3 / M1-3 = alternatives (option n) of one office; trailing `TP` = Paschaltide
  (`option_txt`); `TpA` unsettled (flag it).
- 2026-10-20 (#15) Regina caeli after Compline in Paschaltide → PASC `COMPLINE.antMar`: solemn (p695)
  option 1, '[simpl.]' mode 6 (p696) 'Tonus simplex (modus 6)', mode 1 (p697) 'Tonus simplex (modus 1)'.
- 2026-10-20 (#14) complementary psalmody → `TERCE/SEXT/NONE.ant1-3`; feasts mostly have their own `.ant`.
- 2026-10-20 (#13, #17, #23) where the book says another Gospel may be read (Lent III–V Sundays, Year A sets:
  "Quae antiphonae etiam aliis annis adhibendae sunt, si legatur evangelium de …", pp178/194/211), no
  `cycle_sun`; `option_txt` 'cum Evangelio de Samaritana / de caeco nato / de Lazaro'. (#24) the weekday
  rubrics 'Infra hebdomadam, si quavis die legatur evangelium de …' (pp183/199/215–216) → xref options on that
  week's weekdays: Lauds Mon–Sat, Vespers Mon–Fri, `option_txt` 'cum Evangelio de …'.
- 2026-10-20 (#20, #21) Elizabeth of Portugal UNIVERSAL 4/7, Paul of the Cross UNIVERSAL 19/10.
- 2026-10-20 group-only identities are stored (`chant_group_id`), not forced to an edition.
- 2026-10-20 Office hours have antiphon / short-responsory parts; hora media is its own `MIDDAY` service.

## Known quirks

<!-- one line per recurring producer mistake; the /book-batch director appends here -->
- Master PDF is v.6: printed p974 is missing, PDF = printed − 1 from p975. Every page here is printed;
  never open the PDF by index yourself (`oco/oco_pages.py`, `tools/render_page.py --book OCO`).
- v.6 p184: the white text and ref line belong to 'Amen amen dico vobis: Non Moyses', the engraving is
  'Amen dico vobis, quia nemo propheta'. Trust the engraving.
- The index's page link goes to the FIRST engraving of a text; the book usually re-engraves it under the
  right day (Elevamini: index p95, Holy Saturday re-engraves it on p251 with its own destination).
- p934 labels St Martin's Vespers 'Laudes' (Off. lect. on p932 says 'ut ad Vesperas'; p935 has the Magnificat antiphon): the content decides the hour.
- p993 invitatory 'Festivitatem Virginis' (COM-BMV, `[Vel:]`, mode 2): the index identity gregobase:15315 is a
  Dominican mode-1 'N... Virginis' template, not this chant (was intake #33). The LH already has a placeholder for it,
  `local:2232fa00-86e4-4ee4-a20f-12eb886f125a` (LH p255, mode 2): compare the two engravings and use it if they are the
  same melody; gregobase:17466 ('Nativitatem…', same melody, other text) is the fallback to discuss in `flags`.
- Compline final Marian antiphons pp689–697 (was intake #34): the pages print no seasonal rubric, so model what they
  print: `COMPLINE.antMar`, null epoch, every day, options in book order (Alma Redemptoris, Ave Regina, Salve Regina,
  Sub tuum); a `[simpl.]` setting is the next option with `option_txt` 'Tonus simplex (modus N)' (as Regina caeli, #15).
  Don't add the traditional seasons the book doesn't print. Regina caeli stays PASC (#15).
- Underlined margin numbers (p932 '225') are links of unknown meaning: `flags`, no row.
- An engraving's hidden text can sit at the FOOT of a page while its drop cap, mode and staff begin on the next page
  (p548 'Humiliavit' → p549, p265 'Postulavi' → p266). The row belongs to the page where the staff begins;
  `page_draft.py` carries such engravings forward (`carried from pN`). Batch 1, 2026-10-23.
- A rule printed 'Pro cunctis diebus' for a week or octave goes once on the week/subseason epoch (e.g. `PASC-OCT-01`),
  not on each weekday epoch; the Sunday's own rows override it (LH ruling 2026-10-18 #2). Batch 1, p265.
- A cited edition (`RM 149` → 17966) or an index identity (#2606 → 17892) is not proof: in pages batch 3 both lost to a
  Verona edition on a note-by-note check (p550 In lege Domini → 11002, p259 Redemptor noster → 14915). Compare every
  syllable + Euouae of each candidate before writing `chant_uuid`, even when the ref line cites it.
