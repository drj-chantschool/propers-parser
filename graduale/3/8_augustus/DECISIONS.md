# AUGUSTUS — decisions, holds and open questions

Graduale Romanum, *Proprium de Sanctis*, printed pp. 584–596.
Batch run 2026-09-03. 23 Mass units loaded, 121 chants (11 engraved / 110 cross-reference), all
`VERIFY PASS`. This file records only what needs a human ruling or is worth knowing later.

---

## 1. HELD — `Cantus ut supra` / whole-Mass inheritance (the standing open question)

August adds **two** days to the running tally of Masses that point at another Mass instead of
printing chants. Both are sense (1) whole-Mass inheritance, which is **unruled**; neither was
loaded.

### 1a. 7 August, `Eodem die` — S. CAIETANI, PRESBYTERI (p586, y236→296)
Printed content, in full — one italic line, no chants at all:

> *Cantus ut supra, die 4 augusti.*

Names a **day only**, no page. Points at 4 August (S. Ioannis Mariae Vianney, p584), which IS
loaded (6 chants). Slug `cajetan` exists (`lit_epoch.kind='saint'`) and currently has **zero**
`book='GRADUALE'` rows.
*What I need decided:* the same ruling as 11 Feb / 8 Mar / 7, 13, 24 Apr / 3, 11 Jun — add a
`lit_epoch_tree` edge, copy rows, store the rubric only, or leave the day empty.

### 1b. 5 August — IN DEDICATIONE BASILICAE S. MARIAE (p584, y435→p585 y44)
Printed content, in full — one italic line, no chants at all:

> *Cantus ut in Missa votiva de B.M.V., tempore per annum, A, B, C, 663.*

This is a **third variant** of the construct and may matter to the ruling: it names neither a day
nor a fixed Mass but a **votive Mass** (`de B.M.V., tempore per annum`), it names a **page (663)**,
and it names **three year-cycles (A, B, C)** — i.e. the target is itself a menu, so a naive
row-copy would have to decide what `cycle_sun` the inherited rows get. Compare 11 June, which
named a page as well as a day; that page-naming distinction is what let `adv-ii-in-ultimis-feriis`
resolve.

**This day is doubly blocked** — see §2.1, it has no epoch either.

### Not held (classified and dismissed)
I grepped the whole month for `ut supra` / `præter` / `Cantus ut`. Only the two hits above are
sense (1). There is **no `præter` anywhere in August**, no `Extra tempus paschale` block and no
`(T. P. NNN)` parenthetical. The one other `vel` in the month is
`vel ps. 96*, …` inside a psalm plan (§5), which models normally.

---

## 2. Calendar / epoch gaps — cannot load, no slug invented

### 2.1 5 August — IN DEDICATIONE BASILICAE S. MARIAE (Dedication of St Mary Major)
No `proper_of_saints` row and no `lit_epoch` row anywhere (searched by date **and** by name:
`%major%`, `%dedication%` — the only hit is `lateran-basilica` at 11-9). A genuine calendar gap in
the DB, not a date shift. Also held under §1b, so it needs both an epoch and the inheritance
ruling before it can be loaded.

### 2.2 19 August — S. IOANNIS EUDES, PRESBYTERI (p593, y281→395)
No `proper_of_saints` row and no `lit_epoch` row (searched `%eudes%` across both tables — nothing).
A genuine gap, not a date shift. **Unlike 5 August this Mass is fully printed and ready to load** —
five ordinary cross-references, all of which resolve cleanly (I proved it in the month probe):

| part | printed citation | gregobase |
|---|---|---|
| `in` | `Os iusti meditábitur, 494.` | 1374 |
| `gr` | `Iustus ut palma, 510.` | 34 |
| `al` | `Beátus vir qui suffert, 511.` | 724 |
| `of` | `Véritas mea, 483.` | 630 |
| `co` | `Beátus servus, 491, cum ps. 120*.` | 1154 |

*What I need decided:* whether to create a `john-eudes` epoch (GR/general calendar puts him at
19 Aug). If so this Mass loads immediately with no further parsing.

### 2.3 No wrong-saint traps in August
Per the July `S. CAMILLI DE LELLIS` → `kateri-tekakwitha` incident I read the **printed Latin
title against the returned slug for every one of the 25 dates**, not just the flagged ones. August's
general and US calendars agree throughout: all 17 `status: OK` dates matched their title, and the
6 `✗ AMBIGUOUS` dates were resolved by title —
2 Aug `S. EUSEBII VERCELLENSIS` → `eusebius-of-vercelli` (not `peter-julian-eymard`, also at 8-2);
7 Aug `SS. XYSTI II` → `sixtus-ii` and `Eodem die S. CAIETANI` → `cajetan`;
8 Aug `S. DOMINICI` → `st-dominic` (not `mary-mackillop-of-the-cross`, also at 8-8);
25 Aug `S. LUDOVICI` → `louis-king-of-france` and `Eodem die S. IOSEPH DE CALASANZ` →
`joseph-calasanz`.
Three `proper_of_saints` saints at August dates get **no GR Mass at all** (`peter-julian-eymard`
8-2, `mary-mackillop-of-the-cross` 8-8, `teresa-benedicta-of-the-cross` 8-9,
`st-jane-frances-de-chantal` 8-12) — normal, the Graduale simply does not print them. No action.

---

## 3. `Die 14 augusti` printed OUT OF SEQUENCE — resolved, not an anomaly

`subsections_ai.json` lists `Die 14 augusti` **after** `Die 29`, on chapter page 65. I read the
page rather than assuming. What is actually printed:

- **p596**, below the complete 29 August Mass, there is a **horizontal rule** across the page, then
  a fresh heading `Die 14 augusti` / `S. MAXIMILIANI MARIAE KOLBE, MARTYRIS` + `Mem.`, with its own
  five cross-references. A complete, ordinary Mass.
- **p589**, in Kolbe's proper calendar place (immediately after the 13 August Mass), the book prints
  a single large-type line: `Die 14 aug., S. Maximiliani Mariæ Kolbe, 596.`

Reading: Kolbe was canonized in 1982, after this edition's body was set, so his Mass was appended as
a **ruled-off addendum at the end of AUGUSTUS**, with a pointer line holding his calendar place.
Not a vigil, not a displaced fragment, not a TOC artifact.

**Modeling decision (mine, flagging for confirmation):** the Mass loads normally at
`st-maximilian-kolbe` (5 chants, p596). The **p589 pointer line names no part and no chant, so it
emits no row** — it is navigation, not a citation. To satisfy the golden rule it is recorded
verbatim in the `notes` of the 13 August communio, the chant it immediately follows. If you would
rather see such pointers modeled some other way, this is the first instance in the run.

---

## 4. `CO. Vos qui secúti estis me, VI, 438.` — deliberate deviation from the printed incipit

24 August (Bartholomew), p594. The trailing `VI` is an **option marker, not a mode** (mode prints at
the left margin beside a staff; there is no staff here). p438 carries a numbered menu of communios
from the Commune Apostolorum, and `gr_index_entry` holds **two** communio rows there whose incipits
prefix one another:

- `Vos qui secuti estis me` — mode 1, gregobase **1028** (option V)
- `Vos qui secuti estis me dicit Dominus` — mode 2, gregobase **97** (option VI)

Prefix-matching alone cannot separate them, so the spec incipit was **extended to p438's full index
form** and the reason recorded in the row's `notes`. Loaded as gregobase **97**.
Precedent followed: `specs/matthias.json`, which handles `438, V vel VI` on the same page and reads
option VI the same way. No ruling needed unless you disagree with that precedent.

---

## 5. Unmodelled printed items found by re-reading the four pre-existing specs

The four August slugs that already carried `book='GRADUALE'` rows (`transfiguration` 5,
`assumption` 6 + `assumption-vigil` 5, `bernard-of-clairvaux` 5, `st-monica` 5) were **re-read
against their pages** rather than marked done. Two printed items had no model at all — a dry-run,
`ROW COUNT` and `--verify` are all spec-relative and can never see text that was never captured.

1. **Transfiguration (6 Aug), communio.** The engraving starts p585 and finishes at the top of
   **p586**, under which the book prints a psalm plan with an alternate psalm:
   `Ps. 44*, 2 ab. 3. 4. 5. 6. 7. 8. 18 ab` / *vel* `ps. 96*, 1. 2. 3. 4. 5. 6. 11. 12`.
   Neither the plan nor the `vel ps.` alternate was in the spec.
2. **Assumption in die (15 Aug), communio.** The engraving starts p592 and finishes at the top of
   **p593**, under which the book prints `Cant. Magníficat : Luc. 1, 46-47. 50. 51. 52. 53. 54. 55`.
   Not in the spec.

Both were patched into the respective chant's `notes` following the established `cum ps.` convention
(psalm/canticle-tone data is not modeled by the schema), the specs re-loaded (`updated=5` / `6`,
`inserted=0`) and re-verified. `bernard-of-clairvaux` and `st-monica` were re-read and are complete
as they stand — nothing printed on their pages is unmodelled.

*Worth noting:* both misses are the **same shape** — an engraving that spills onto the next page,
whose trailing psalm plan sits below the spill and outside the spec's page. See the lessons list.

---

## 6. `gr_index_entry` OCR typos corrected (written as `jcost`)

The month-wide probe exposed three index incipits that are OCR corruptions, not curated
disambiguators. I confirmed each against the **printed back-of-book index** before editing
(fitz over the INDICES chapter), corrected `incipit` only (leaving `gregobase_id` and
`match_status` untouched), and grepped `specs/` for the old wording first — **blast radius was zero,
no spec had adopted any of them.** Re-probed after the edits; all three `ℹ` lines cleared.

| row_id | page | part | was | now | printed index reads |
|---|---|---|---|---|---|
| 1004 | 586 | introitus | `Confesio` | `Confessio` | `Confessio` |
| 1494 | 589 | offertorium | `Confesio` | `Confessio` | `Confessio` |
| 1297 | 585 | alleluia | `Candor est lucis aeterne` | `Candor est lucis aeternae` | `Candor est lucis ætérnæ` |

No loaded-row repair was needed: all three already pointed at the right gregobase chant
(956 / 105 / 10479), so no stale `chant_uuid` resulted from the fix.

⚠ The typos persist in the upstream OCR artifacts (`propers-parser/gr_index_entries.json`,
`graduale/VALIDATED/gr_chant_index_reviewed.csv`), so a rebuild of the index table will reintroduce
them. Flagging rather than editing the provenance files.

### Two `ℹ` lines deliberately NOT "fixed"
Both are faithful transcriptions of what the printed index actually says, verified the same way:

- p523 `In virtute tua rex` — the printed index really reads `In virtute tua ... rex`. The page
  prints `IN. In virtúte tua… lætábitur rex, 523.` Single introit on p523, resolves correctly to
  gregobase **15921**, whose gregobase name is literally *In virtute tua (St Louis)*. Affects
  16 Aug and 25 Aug.
- p591 `Gaudeamus Mariae Assumptione` — a curated disambiguator matching gregobase 3312
  (`Gaudeamus... Mariae... Assumptione`). Correct as it stands.

---

## 7. Multi-option slots — swept in advance, no collisions

The loader dedups on slot + `chant_group` **ignoring `option_num`**, and a dry-run cannot reveal a
collapse. All six of August's multi-option slots were `chant_group`-swept in one query **before** any
real write; all six pairs are in distinct groups, so nothing collapsed. Confirmed after loading:
every Mass's `count(*)` equals its `count(DISTINCT chant_uuid)`.

| day | part | option 1 | option 2 | groups |
|---|---|---|---|---|
| 4 Aug Vianney | `co` | `Beatus servus` p491 → 1154 | `— Multitudo languentium` p471 → 1267 | 1154 / 1267 |
| 10 Aug Laurence | `in` | engraved p586 → 956 | `Ad libitum :` p519 → 544 | 956 / 544 |
| 10 Aug Laurence | `of` | engraved p589 → 105 | `Ad libitum :` p513 → 185 | 105 / 185 |
| 15 Aug Assumption | `in` | engraved p590 → 23 | `Ad libitum:` engraved p591 → 3312 | 23 / 3312 |
| 21 Aug Pius X | `co` | `Manducaverunt` p278 → 677 | `— Qui manducat carnem meam` p383 → 798 | 677 / 798 |
| 22 Aug Queenship | `in` | `Salve, sancta Parens` p403 → 1140 | `— Vultum tuum deprecabuntur` p404 → 124 | 1140 / 124 |

**Three of the six alternates are bare em-dash lines**, not `vel:` — 4 Aug and 21 Aug under the
communion, 22 Aug under the **introit**. All three were confirmed by page image (the dash sits in
the `IN./GR./AL./OF./CO.` label column) and loaded as separate rows with `option_txt: "—"`.

---

## 8. Feb–Jun read-only title audit (the bounded extra task)

Because the wrong-saint trap was only discovered in July, Feb–Jun were resolved without title
verification. Audit run read-only over printed pp. **539–577**, both directions, using
`subsections_ai.json` titles + `proper_of_saints`. **Nothing was changed.**

**Result: no mismatches found.** All **64** slugs carrying `book='GRADUALE'` rows in that window
resolve to a Feb–Jun DB date, and at every one of those dates the GR's printed Latin title matches
the slug's saint.

The five multi-saint dates were checked individually for a **swap** (both saints loaded, but to each
other's slug) by reading each spec's own Latin label — all correctly paired:
3 Feb Blasii/Ansgarii · 12 May Nerei-Achillei/Pancratii · 25 May Bedae/Gregorii VII/Mariae
Magdalenae de Pazzi · 22 Jun Paulini Nolani/Ioannis Fisher-Thomae More · 31 May Visitatione/
Immaculati Cordis.

Reverse direction — GR Feb–Jun dates with **no** loaded slug — returns exactly the five already-known
items and no surprises: **8 Mar, 7 Apr, 13 Apr, 24 Apr** (the held `Cantus ut supra` / `ut in
sollemnitate … præter` Masses) and **20 May** (Bernardine of Siena, the known missing-epoch gap).

Note `immaculate-heart-of-mary` is filed at placeholder date **5-31** though it is movable; its spec
label correctly records the real rubric (*Sabbato post dominicam II post Pentecosten*), so the
placeholder date is a DB artifact, not a claim about the page. Known, unchanged.

---

## 9. Housekeeping

`propers-parser/_tmp` still holds this month's chunked PDFs, thirteen dpi=200 page renders and the
throwaway `probe_augustus.json`. **Deleting it is blocked by the permission classifier** (both
`rm -rf` and `shutil.rmtree` on that path are denied), so it needs clearing by hand.
