# Liber Hymnarius page specs — contract

One JSON file per **printed page**: `propers-parser/lhymn/specs/pNNNN.json` (zero-padded, e.g.
`p0004.json`). The backend is `propers-parser/lhymn/load_lh_page.py`. It resolves each chant's
`chant_uuid` and writes `lit_part_sources` rows with `book = assignment_authority_code =
'LIBER_HYMNARIUS'`. A spec records **what the page assigns**: which chant goes with which
liturgical act.

## The page rule

A page assigns only the chants that **begin** on it. If a page opens partway through a chant that
began earlier, that chant was already assigned on its start page, so this page does not repeat it.
Record it only in `continues`. A page holding nothing but the middle or end of one chant is
`"page_kind": "continuation_only"` with no rows. A blank page, a section title page, or a page of
prose rubrics with no chant is `"no_chant"`.

Two things belong with the chant they attach to, even when they are printed on the next page:
- an invitatory antiphon's psalm cue (`Ps. Veníte, p. 149.`);
- an `Ad libitum` / `vel` alternative line that follows a chant whose start is on this page.

Both go in the spec of the chant's **start** page, with `rubric` noting where the cue is printed.
The next page's producer then treats that cue as already handled and lists it in `continues`.

## Top-level fields

| field | meaning |
|---|---|
| `page` | printed page number, string (`"4"`) |
| `page_kind` | `assign` · `continuation_only` · `no_chant` |
| `jurisdiction` | `UNIVERSAL` (default) or `OSB` for the Proprium monasticum (pp. 535–607) |
| `context_in` | the governing headings in force at the top of the page (section › day › hour › rubric), as text |
| `context_out` | the same at the bottom of the page. The next page's producer reads this |
| `continues` | `{"from_page": "3", "incipit": "..."}` for a chant carried over from an earlier page, else `null` |
| `rows` | the assignments (below) |
| `common_refs` | whole-Office references to a Common (below) |
| `questions` | anything you could not model confidently. **A non-empty list blocks the load** |
| `flags` | notes for the reviewer that do not block the load (odd rubric, index typo, ...) |

## A row

```json
{"incipit": "Te lucis ante terminum", "kind": "engraved", "mode": "IV",
 "lit_epoch_slug": "ADV-I", "service": "COMPLINE", "part": "hymn",
 "wkday": null, "option_num": 1, "option_txt": null,
 "rubric": "In Officio dominicali et feriali, a I Vesperis dominicae I Adventus usque ad diem 16 decembris"}
```

| field | meaning |
|---|---|
| `incipit` | the chant's opening words as printed, **without accents** (the matcher folds them anyway). Expand the big drop-cap: `C` + `Ondi-tor` → `Conditor alme siderum` |
| `kind` | `engraved` (music printed here) or `xref` (only a citation like `hymnus Dies aetasque, p. 183`) |
| `ref_page` | **xref only**: the page cited. The chant is looked up on THAT page |
| `mode` | the mode as printed in the left margin (`H.IV` → `"IV"`, `Ant.E` → `"E"`, `4*` → `"4*"`). It separates same-incipit chants |
| `lit_epoch_slug` | the epoch (see map below), or `null` for the per-annum psalter |
| `lit_epoch_slugs` | a list instead, when one printed rule spans several epochs (expands to one row each) |
| `service`, `part` | see the services table |
| `wkday` / `wkdays` | 1 = Sunday … 7 = Saturday. `wkdays: [2,3,4,5,6,7]` for "in feriis". Null = every day |
| `wknum_mod_2` / `wknum_mod_4` | psalter weeks (per annum only): weeks I & III → `wknum_mod_2: 1`; II & IV → `0`. A single psalter week k → `wknum_mod_4: k % 4` |
| `psalter_all_weeks` | `true` for a per-annum row (null epoch) that applies in every week, e.g. Compline |
| `rank_code` / `rank_codes` | only when the book conditions the chant on rank: "in memoriis" → `["MEMORIAL","OPTIONAL_MEMORIAL"]`; "in sollemnitatibus et festis" → `["SOLEMNITY","FEAST","FEAST_OF_THE_LORD"]`. Codes come from `p_lit_rank`. Base codes also match their `PROPER_` variants |
| `option_num` / `option_txt` | 1 = the primary. Each `vel` / `Ad libitum` / night-vs-day alternative is its own row with `option_num` 2, 3, … and `option_txt` = the printed condition (`"Ad libitum"`, `"Quando Officium lectionis dicitur noctu vel summo mane"`) |
| `rubric` | the printed rubric(s) that govern this row, verbatim |
| `index_row_id` / `chant_uuid` | overrides, used ONLY when the matcher can't find the chant. Use `index_row_id` when the LH index lists the chant on a wrong page; use `chant_uuid` only with a `flags` note saying why |
| `verified_despite` | list of substrings of `⚠ CHECK` warnings you checked against the page and accept (explain in `flags`). Unacknowledged CHECKs block the real load |
| `allow_unresolved` | `true` when the chant exists on the page but in neither `chant_indices` nor gregobase (e.g. the "ad lib." Venite tones on pp. 152/162/170/173). Requires a `flags` note |
| `notes` | anything else worth keeping (≤ 500 chars together with `rubric`) |

## Services and parts (`service_part`)

| printed heading | service | parts |
|---|---|---|
| AD INVITATORIUM | `INVITATORY` | `invan` (antiphon), `invps` (the cited Ps 94 tone, an xref row: incipit `Venite exsultemus`, `ref_page` = the cited page) |
| AD OFFICIUM LECTIONIS | `OFFREAD` | `hymn`, `resp` (responsory after the first reading — also any responsory the book doesn't place), `resp2` ("Post alteram lectionem"), `tedeum` |
| AD LAUDES MATUTINAS | `LAUDS` | `hymn` |
| AD TERTIAM / AD SEXTAM / AD NONAM (Ad Horam mediam) | `TERCE` / `SEXT` / `NONE` | `hymn` |
| AD I VESPERAS | `VESPERS1` | `hymn`, `resp` |
| AD II VESPERAS, or plain AD VESPERAS | `VESPERS` | `hymn` (part 110), `resp` |
| AD COMPLETORIUM | `COMPLINE` | `hymn` |

I Vespers belongs to the **celebration it opens**. Store it on the Sunday or feast's own epoch
(`wkday: 1` for a Sunday), never on the Saturday.

A plain "AD VESPERAS" under a section whose rule runs "a I Vesperis dominicae … usque ad …"
covers both I and II Vespers. Emit a `VESPERS1` row AND a `VESPERS` row (or explain in `flags`
why not).

When a heading names several hours ("Ad Tertiam, Sextam et Nonam"), emit one row per service.
If something is printed for a part the table lacks, put it in `questions`. Never force it into
the wrong part.

## Epoch map (Proprium de tempore)

| LH section (printed pages) | `lit_epoch_slug` |
|---|---|
| Tempus adventus I, usque ad diem 16 decembris (3–8) | `ADV-I` (Sundays `wkday: 1`) |
| Tempus adventus II, post diem 16 decembris (9–13) | `ADV-II` |
| Tempus Nativitatis I, usque ad soll. Epiphaniae (14–25) | `lit_epoch_slugs: ["NAT-DAY","NAT-IO","NAT-OCT","NAT-PO"]` for season-wide rules; Christmas Day itself `NAT-DAY-00-0` |
| Dom. infra oct. Nativitatis, Holy Family (26–30) | `NAT-IO-01-0` |
| Die 1 ianuarii (31–35) | `NAT-OCT-02-0` |
| Tempus Nativitatis II, a soll. Epiphaniae (36–42) | `NAT-EPI` (season-wide); Epiphany itself `NAT-EPI-00-0` |
| In Baptismate Domini (43–47) | `NAT-BAPT-01-0` |
| Quadragesima I, usque ad sabb. hebd. V (48–57) | `TQ-LENT` (Ash Wednesday `TQ-LENT-00-4`; weekly Sundays `wkday: 1`) |
| Hebdomada Sancta (58–66) | `TQ-HOLYWEEK` (Palm Sunday `TQ-HOLYWEEK-00-1`, Holy Thursday `-00-5`) |
| Feria VI in Passione Domini (67–68) | `TQ-HOLYWEEK-00-6` |
| Sabbato Sancto (69–73) | `TQ-HOLYWEEK-00-7` |
| Tempus paschale I, usque ad Asc. (74–87) | `lit_epoch_slugs: ["PASC-OCT","PASC-AD_ASC"]`; Easter Sunday `PASC-OCT-01-1` |
| Tempus paschale II, ab Ascensione (88–95) | `lit_epoch_slugs: ["PASC-ASC","PASC-POST_ASC"]`; Ascension `PASC-ASC-06-5` |
| Dominica Pentecostes (96–104) | `PASC-PENT-08-1` |
| Ss.ma Trinitas (105–109) · Corpus Christi (110–116) · Cor Iesu (117–121) · Christus Rex (122–125) | `OT-FOL-00-1` · `-00-2` · `-00-3` · `-00-4` |
| Hebdomada XXXIV per annum (126–130) | `OT-OT-34` |
| Tempus per annum (177–244) | `null` + psalter fields. Hebdomadae I & III (181–207): `wknum_mod_2: 1`. II & IV (208–240): `wknum_mod_2: 0`. Ad invitatorium (179–180): `wkday` per day, plus psalter week fields if the page splits by week. Ad completorium (241–244): `OT-OT` with rank tiers (SUNDAY / WEEKDAY / MEMORIAL+OPTIONAL_MEMORIAL / FEAST+FEAST_OF_THE_LORD / SOLEMNITY), no `wkday`/`wknum`; opt 1 *Te lucis*, opt 2 'Alter hymnus ad libitum' *Christe qui splendor*, each in its tier's tone (confirmed, intake_queue #8). Middle Hour (Terce/Sext/None): `OT-OT` + rank + `wknum_mod_2`, per ruling 2026-10-17b |

A section-wide rule ("In Officio dominicali et feriali …") gets the section slug with `wkday`
null. "In dominica" → `wkday: 1`; "In feriis" → `wkdays: [2..7]`. A named day ("Feria IV
Cinerum") gets that day's slug. When unsure which day slug exists, query
`SELECT slug,title FROM lit_epoch WHERE slug LIKE 'TQ-LENT-00%'`. Never invent a slug: an
unmatched day goes in `questions`.

## Commons (pp. 245–336, and the O.S.B. Commune p. 537)

| LH Common (page) | slug |
|---|---|
| Dedicationis ecclesiae (247) | `COM-DED` |
| B. Mariae V. (253) | `COM-BMV` |
| B.M.V. memoria in sabbato (263) | `COM-BMV-SAB` |
| Apostolorum (266) | `COM-APOST` |
| Martyrum, pro pluribus (273) | `COM-MART-PLUR` |
| Martyrum, pro uno (280) | `COM-MART-UNO` |
| Pastorum (289) | `COM-PAST` |
| Doctorum Ecclesiae (301) | `COM-DOCT` |
| Virginum (305) | `COM-VIRG` |
| Ss. virorum (311) | `COM-SANCT-VIR` |
| Ss. mulierum (318) | `COM-SANCT-MULIER` |
| pro religiosis (324) | `COM-SANCT-RELIG` |
| Officium defunctorum (328) | `officium-defunctorum` |
| Commune ss. monachorum & monialium, O.S.B. (537) | `COM-MON` (`jurisdiction: "OSB"`) |

Inside a Common, Paschaltide variants ("Tempore paschali") stay rows of the Common, carrying
`option_txt` and a `flags` note. Do not invent seasonal epochs.

## Sanctorale (pp. 337–486) and `common_refs`

Each `Die N mensis` heading names a celebration. Find its slug by date:

```sql
SELECT p.slug, p.common_name, p.rank_code, p.jurisdiction FROM proper_of_saints p
WHERE p.month_nominal = :m AND p.day_nominal = :d AND p.jurisdiction IN ('UNIVERSAL', :jur)
```

Pick by the printed title, never by date alone. Several saints share some dates
(`Eodem die …` is a second celebration on the same date). If the printed saint has no row, it
goes in `questions`.

A line like `De Communi pastorum, p. 289, vel doctorum Ecclesiae, p. 301.` becomes
`common_refs`, one entry per Common named:

```json
"common_refs": [
  {"lit_epoch_slug": "basil-the-great-and-gregory-nazianzen", "common_slug": "COM-PAST", "common_page": 289,
   "ref_option": 1, "rubric": "De Communi pastorum, p. 289, vel doctorum Ecclesiae, p. 301."},
  {"lit_epoch_slug": "basil-the-great-and-gregory-nazianzen", "common_slug": "COM-DOCT", "common_page": 301,
   "ref_option": 2, "option_txt": "vel de Communi doctorum Ecclesiae", "rubric": "..."}
]
```

The loader copies every row of the loaded Common onto the saint as cross-references
(`ref_page_num` = the Common's engraving page). Each slot's options are numbered after any
explicit options. A slot the page fills explicitly is skipped: a proper hymn plus "cetera de
Communi" gives the proper hymn as a row and the rest from `common_refs`. To narrow a reference
to a sub-Common (e.g. "pro religiosis" inside Ss. virorum), point `common_slug` at that
sub-Common. The loader expands a Common only after ALL of its pages are finished in the queue
(`COMMON_RANGES` in the loader). A slug without a range is an error the director fixes.
`De Communi …, praeter hymnum sequentem:` → `common_refs` PLUS the proper hymn as an explicit
row for the hour its heading names. The explicit row fills that slot, so the Common's hymn for
that hour is not copied. If the page doesn't say which hour the proper hymn replaces, ask. If the loader reports `DEPENDENCY` (Common not loaded yet), that is not your error:
report it.

Proper chants printed for a saint are ordinary `rows` on the saint's slug. The memorial/feast
marker under the title (`Memoria`, `Festum`, `Sollemnitas`) is not a chant. Report it in
`flags` if it disagrees with `proper_of_saints.rank_code`.

## Responsoria (pp. 487–534)

These are `OFFREAD.resp` responsories ("Post priorem lectionem" or unplaced → `resp`; "Post alteram lectionem" → `resp2`). The book proposes them "praecipue dominicis,
sollemnitatibus et festis". **User ruling (2026-10-13):** "praecipue" recommends rather than restricts.
A seasonal heading (`IN ADVENTU`) → that season's slug (`ADV`, `NAT`, `TQ`, `PASC`) with **no**
`wkday` and **no** `rank_codes`, unless the page itself prints a narrower rubric. This is not a
question; don't raise it. A heading naming
one celebration → that celebration's slug. `Vel ℟. Missus est, p. 517` → an xref alternative
(`option_num` 2…). The `℣. Gloria Patri … p. 604` pointer is navigation, not a row. The
Te Deum → `OFFREAD.tedeum`. Put its scope (Sundays outside Lent, solemnities, feasts) in
`questions` if the page doesn't state it.

## Proprium monasticum O.S.B. (pp. 535–607)

`"jurisdiction": "OSB"` at the top level. `C.S.` / `C.S.G.` beside a title scopes only that one
entry (Solesmes congregation / its French houses). Record it in `notes` and `flags`. OSB saints
are looked up with `jurisdiction='OSB'` first. A missing OSB saint goes in `questions`; the
director creates it.

## Chant identity: trust but verify

The loader resolves identity from the LH index first (`chant_indices` on the target page), then
gregobase source 15. The index is NOT guaranteed correct (wrong page, wrong linked edition,
misprints). So every row's dry-run line shows the resolved chant's own incipit, mode,
office-part, LH page tie and opening words. A mismatch with the spec prints `⚠ CHECK`. Resolve
each one: switch candidate, acknowledge with `verified_despite` + a flag, or ask.

## Validation (definition of done)

```
set PYTHONUTF8=1
C:\Users\johna\liturgio\.venv\Scripts\python.exe C:\Users\johna\liturgio\propers-parser\lhymn\load_lh_page.py --spec <spec> --dry-run
```

Clean means every row prints `-> gregobase:<id>` (or `NULL` with `allow_unresolved` and a
flag), the run ends `DRY-RUN OK`, and the exit code is 0. Exit 3 means `questions` is
non-empty, which is fine when you genuinely have one. `ERROR: no chant for …` prints the
page's candidate pool and any neighbouring-page hits. The LH index sometimes lists a chant
one page off, so use `index_row_id` in that case.

## Known quirks

<!-- one line per recurring producer mistake; the /book-batch director appends here -->
- A chant ends at its FINAL double bar (for a responsory, after the last verse and repetenda), not at the bottom of the page. Always read the TOP of the next page before writing `context_out`, and capture any trailing `Vel ℟. …, p. N` / `Ad libitum` lines that belong to a chant starting on your page (p487's responsory runs onto p488, which ends with two `vel` xrefs).
- Responsoria headings: only a SEASON name (`IN ADVENTU`, `TEMPORE PASCHALI`, `PER ANNUM`) takes the season slug. A heading naming a feast or day (`IN NATIVITATE DOMINI`, `IN EPIPHANIA`, `IN ASSUMPTIONE`) takes that celebration's own slug (e.g. `NAT-DAY-00-0`). Don't flag it as a choice.
- The "vel line belongs to the start page" rule covers only a one-line xref cue (`vel ℟. X, p. N`). A `vel:` / `Tempore paschali` alternative that is fully ENGRAVED with its own drop cap is a chant that begins where it is printed, so the page it's printed on assigns it (p248 → p249 `Christum Dominum`). Its own `Ps. Veníte` cue goes with it.
- `verified_despite` is only for a chant whose gregobase headers cite **Liber Hymnarius 1983, p. <this page>** and whose only fault is a metadata field (e.g. p10's 19799, filed mode 4 but its GABC ends on F = the printed VI). It is also fine for a pure GABC-markup artifact in the text comparison (e.g. p501's `EGo \greheightstar rogábo`) when the words, mode and office-part all match the page. Most Responsoria have no LH-1983 edition at all, so no LH tie is needed there. Never use it for another tradition's edition (Dominican, Cistercian…), a placeholder text (`N...`), or a different text. Those are questions (p255's 15315).
- `questions` are only for conditions PRINTED ON YOUR PAGE. Don't add a pre-emptive "same question as held pN" for a condition that is absent here, or for chants on later pages (p306/p307 did). A page with no open question of its own must not be held.
- A MISSING OSB EPOCH is never a reason to drop that saint's rows or common_refs. Write them with the proposed slug (e.g. `<name>-osb`), list the saint in `questions`, and expect the dry-run to fail on the unknown slug. The director creates the epoch and reruns. p547 and p561 omitted them, and the director had to rebuild them from the page.
- Same incipit ≠ same chant. A hymn text re-engraved on another page may carry a DIFFERENT melody: p96's Pentecost Compline 'Iesu redemptor saeculi' is not p77's. Never accept a candidate whose LH tie points to another page without comparing the opening neumes of both engravings, and look for a melody-specific edition (e.g. 4676 '(Dominica Pentecostes)').

## User rulings 2026-10-15 (supersede any held-page question on these topics)

1. **Subject conditions → sub-Commons.** A heading "Pro uno … / Pro pluribus …" (or "Pro una virgine",
   "Pro martyre virgine", "Pro papa / episcopo / presbytero") puts the row on the sub-Common, NOT an
   option_txt on the parent: `COM-MART-UNO-VIRG`; `COM-PAST-UNO`, `COM-PAST-PLUR`, `COM-PAST-UNO-PAPA`
   / `-EPISC` / `-PRESB`; `COM-VIRG-UNA`, `COM-VIRG-PLUR`; `COM-SANCT-VIR-UNO`, `COM-SANCT-VIR-PLUR`;
   `COM-SANCT-MULIER-UNA`, `COM-SANCT-MULIER-PLUR`. Rows without such a heading stay on the parent.
   A saint's `common_refs` should point at the narrowest sub-Common that fits (one virgin →
   `COM-VIRG-UNA`), since the loader adds the ancestors' shared rows. Pointing at the parent brings in all
   its sub-Commons as labelled options.
   **Text-only variants** that share one chant (Office of the Dead "pro uno/una defuncto/pluribus"
   stanzas; feminine interlinear words such as "Hae quas", "Beata", "quae/victrix") get ONE row on the
   parent with the variant described in `notes`. They are not a question.
2. **Tempore paschali** alternatives in Commons: an extra option with `option_txt` "Tempore paschali"
   (and "In aliis temporibus" etc. as printed). Not a question.
3. **"Ad Vigilias"** (monastic Vigils) → service `VIGILIAE` (`hymn`, `resp`, `tedeum`, `tedecet`), never
   OFFREAD. "Ad Vigilias et ad Vesperas" → a VIGILIAE row plus a VESPERS row. The Vigils invitatory stays
   `INVITATORY`. *Te decet laus* → `VIGILIAE.tedecet`.
4. **"praeter sequentia ad libitum"**: the proper row gets `"after_common": true` (no option_num). The
   Common's hymn stays option 1 and the proper becomes option 2. A plain "praeter" (no "ad libitum") still
   replaces the Common's row.
- `common_refs[].skip_slots` (e.g. `["LAUDS.hymn","VESPERS.hymn"]`): slots this saint fills with propers printed on OTHER pages of the same jurisdiction. The Common's row for those slots is not copied. Read ahead to the saint's following pages and list them (Scholastica p548 → Lauds p550, Vespers p551). Never list a slot filled only under another jurisdiction (an O.S.B. proper doesn't suppress the UNIVERSAL copy).
5. **Congregation-scoped alternatives** ("Pro Congregatione solesmensi", "… in Gallia", C.S./C.S.G. entries) are
   an option on the SAME epoch, with `option_txt` = the printed rubric. If the alternative is the saint's only
   proper for a slot the Common also fills, add `"after_common": true` so the Common's hymn stays option 1
   for the whole Order (Benedict of Aniane p555).
6. **O.S.B. rank override:** when the O.S.B. book prints a rank (Memoria/Festum/Sollemnitas) different from the
   universal `proper_of_saints.rank_code`, the director adds a second `proper_of_saints` row (jurisdiction OSB,
   same slug, printed rank). Flag it; it's not a question.
7. **Monastic Vigils ≠ Office of Readings** (user, 2026-10-15). `VIGILIAE` rows never stand in for OFFREAD or
   vice versa. O.S.B. saints citing a Roman Common keep that Common's OFFREAD rows unchanged.
- **Neume check (user correction, p96):** any chant whose gregobase LH page tie is missing or points to another
  page must be compared against the engraving (opening neumes plus one cadence) before it is accepted. The
  same text can carry a different melody.

## User rulings 2026-10-16

1. **Truly absent chants → placeholder `local_chants`.** When a printed chant has no gregobase edition
   (or only an edition whose text differs from the LH 1983), the director creates a blank `local_chants`
   row (`version='LH1983'`, `gabc=''`, `status='draft'`, `source_citation='Liber Hymnarius 1983 p. N'`,
   notes start `PLACEHOLDER`) and the spec row sets `"chant_uuid": "local:<uuid>"`. Use the existing
   gregobase chant's `chant_group` when the melody is the same, otherwise a new group. Producers still
   write `allow_unresolved` and flag it; the director makes the placeholder.
2. **O.S.B. uses the LH as normal** except where its Proprium prints overrides: OSB saints citing a Roman
   Common keep every row it supplies (OFFREAD, VESPERS1, …).
3. **Regional ranks** such as "in Europa, festum" → a second `proper_of_saints` row with that region's
   jurisdiction (`EU` exists), same slug, the regional rank.
4. **"Pro monasterio S. Petri de Solesmis"** (pp601-603) stays `jurisdiction: OSB`; the narrower scope goes
   in notes, as for C.S./C.S.G.
5. **Appendix pages** 604-607 (Gloria Patri responsory tones; old-edition hymns with no day/hour) carry no rows.

## User rulings 2026-10-17

1. **Ordinary Time Middle Hour hymns (SUPERSEDES the per-page psalter modeling, rebuilt 2026-10-17 by
   `propers-parser/_tmp/lh/ot_midhour.py`):** every Terce/Sext/None hymn of the per-annum psalter is
   `lit_epoch_slug: "OT-OT"`, no `wkday`, keyed by `rank_codes` (SUNDAY / WEEKDAY / MEMORIAL+OPTIONAL_MEMORIAL /
   FEAST+FEAST_OF_THE_LORD / SOLEMNITY), even though the solemn tone is printed under Sundays and the feast tone
   under weekdays. Per hour x tier, four rows: `wknum_mod_2: 1` → opt 1 weeks I&III text (Nunc Sancte / Rector
   potens / Rerum Deus), opt 2 the weeks II&IV text (Certum tenentes / Dicamus laudes / Ternis horarum);
   `wknum_mod_2: 0` → the reverse. Each in the tier's tone (texts swap, tone follows the day). Opt 1 is engraved
   on the setting's own page; opt 2 is an xref on that same page. "Tonus ut supra/infra, p. N" pointers add no
   rows (same slot as the engraved setting). The resolver will be adapted in a later session.
2. **Pastors Common for an abbot or other non-pope/bishop/priest:** "Pro uno pastore" hymns at OFFREAD/LAUDS
   exist only in pro papa / pro episcopo / pro presbytero stanza-2 variants (COM-PAST-UNO-PAPA/-EPISC/-PRESB);
   COM-PAST-UNO itself carries only VESPERS1/VESPERS. A priest-abbot (Columban) → COM-PAST-UNO-PRESB.

## User rulings 2026-10-18

1. **Rank-only universal rows** (intake_queue #3): `"universal": true`, `lit_epoch_slug` null, `rank_codes`
   required, no `wknum_mod_*` / `psalter_all_weeks`. The row means "any day of these ranks, in any season". Use it
   for rubrics like "in sollemnitatibus et festis" (Te Deum pp527/530). PRINCIPAL_TEMPORAL days (Epiphany,
   Ascension, …) are not covered by a rank row and need explicit epoch rows.
2. **Text-substitution antiphons** (intake_queue #1): when the LH prints a second text under the same staff
   (e.g. `[appáruit]` under "natus est"), and gregobase has no separate edition of each text, split the engraving into
   one `local_chants` row per text (derived gabc, `status='draft'`) and link each slot to its own text.
   When a gregobase edition with the substituted text and the same melody exists (p16 → 13371), link that instead.
3. **Don't duplicate rows across epochs or weekdays** (intake_queue #2): put a rule on the widest epoch it applies to
   (a subseason or season default) and let narrower epochs override. Holy Week hymns are `TQ-HOLYWEEK` defaults with
   no `wkday(s)`, so Good Friday's "Omnia sicut in hebdomada sancta, praeter…" inherits them. Paschaltide I hymns are
   `PASC` defaults, so post-Ascension pages ("Omnia sicut ante Ascensionem, praeter…") override them. If a
   spec seems to need the same row on several epochs or weekdays, ask the user (intake_queue) instead.
4. **Cross-book cues** (intake_queue #4), e.g. "Vel R. Emendemus, in Graduale": an `xref` row with
   `"ref_book": "GRADUALE"`, `ref_page` = the cited page in that book (look it up if the LH doesn't print one), and an
   explicit `chant_uuid`. `book` and the authority stay LIBER_HYMNARIUS.
5. **Alternating-week hymns** (intake_queue #5): when a section gives one hymn for weeks I, III, V and another for
   II, IV (e.g. Lent Compline, p51), use ONE row per hymn on the season slug, with `wknum_mod_2` 1 (odd weeks) or
   0 (even weeks). Never copy them onto each week epoch. `wknum_mod_2`/`wknum_mod_4` exist for hymns; week 0 (e.g.
   Ash Wednesday–Saturday) falls under 0.
