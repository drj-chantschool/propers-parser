# APRILIS — decisions and open questions

Graduale Romanum, `Proprium de Sanctis`, printed pages **554–557**.
Batch run 2026-09-03. 13 dates in the month, all at zero rows before this run.
**10 Masses / 62 chants loaded** (text_ids 3705–3766, all VERIFY PASS);
**3 Masses deliberately not loaded** (§1).

Every chant in April is a **cross-reference** — `gr_index_entry` has zero rows on pp.554–557,
which positively confirms the month engraves nothing. All 62 rows carry `ref_page_num`; none is
NULL.

---

## 1. HEADLINE — THREE days print `Cantus ut supra, die N aprilis.` (NOT LOADED)

The unruled construct from February (Our Lady of Lourdes) and March (S. Ioannis a Deo, 8 March)
recurs **three times** in April. Each prints a heading, a title, one italic line, and no chants
at all — no `IN.`/`AL.`/`OF.`/`CO.`, no incipits, no page citations.

| date | slug | page / y | printed line | points at |
|---|---|---|---|---|
| Die 7 aprilis, S. Ioannis Baptistæ de la Salle | `john-baptist-de-la-salle` | p555, y63–101 | `Cantus ut supra, die 5 aprilis.` | Vincent Ferrer (loaded, 6 chants) |
| Die 13 aprilis, S. Martini I | `martin-i` | p555, y347–383 | `Cantus ut supra, die 11 aprilis.` | Stanislaus (loaded, 10 chants) |
| Die 24 aprilis, S. Fidelis de Sigmaringen | `fidelis-of-sigmaringen` | p556, y186–235 | `Cantus ut supra, die 23 aprilis.` | George (loaded, 5 chants) |

7 April also prints a `Mem.` rank marker (already MEMORIAL in `lit_epoch`); 13 and 24 April print
none.

**What I did.** Loaded **nothing** for these three slugs. All three `lit_epoch` rows exist
(`kind='saint'`, each with a single `SAINTS → <slug>` tree edge) and all three have zero
`lit_part_sources` rows. As of now each of these days resolves to **no Mass whatsoever**.

**Why I did not decide it.** This is exactly the question March's director raised for 8 March and
you have not ruled on it. The options are unchanged, and are restated here only so this file
stands alone:

- **(a) Tree edge** — `lit_epoch_tree(parent='vincent-ferrer', child='john-baptist-de-la-salle')`
  etc., letting the most-specific-wins walk inherit the source day's chants. Cheap, models the
  rubric exactly, and works for Lourdes' partial override too. Caveat: it makes a *saint* the
  parent of another saint, a lateral relationship the `SAINTS → commons → saints` design did not
  anticipate; it may deserve its own edge type.
- **(b) Copy the rows** onto the pointing day with `printed_page_num=555`/`556`. Self-contained,
  but invents rows the book does not print and loses the fact that the GR expresses this as a
  reference.
- **(c) Model the rubric only** (there is no home for it today — `lit_part_sources.part_id` is
  `NOT NULL` and a rubric fills no slot; `lit_epoch.notes` is the precedent used for the p532
  chapter rubrics).
- **(d) Leave as is** — these days load empty, revisit later.

April strengthens the case for deciding it: the construct is not a one-off. It has now cost
**four** Masses across three months (Lourdes partially, 8 March, and these three), and April's
three all point at days loaded in the very same batch, so the inherited data is sitting right
there, unreachable.

**Scope check.** I grepped the whole month's text layer for `ut supra` and `præter`/`praeter`.
`præter` does not occur in April at all. `ut supra` occurs four times: the three rows above, plus
`CO. Data est mihi, 213, cum ps. 77* ut supra.` on 28 April — which is **not** this construct
(see §6). No other April day defers to another day.

---

## 2. The Paschaltide Gradual-replacement Alleluia → modelled as `al1` (LOADED; please confirm)

Three days print a Gradual, then an italic Paschaltide rubric, then a single `AL.` line, then the
offertory and communion:

| day | slug | rubric printed | AL line |
|---|---|---|---|
| Die 2 aprilis, S. Francisci de Paola | `francis-of-paola` | `Tempore paschali omittitur Graduale, et eius loco dicitur :` | `Beátus vir qui timet, 511, vel Iustus germinábit, 496.` |
| Die 4 aprilis, S. Isidori | `isidore` | `Tempore paschali :` | `Iurávit Dóminus, 489, vel Amávit eum, 495.` |
| Die 5 aprilis, S. Vincentii Ferrer | `vincent-ferrer` | `Tempore paschali :` | `Beátus vir qui suffert, 511, vel Amávit eum, 495.` |

**What I did.** Gave each of those Alleluias `service_part: "al1"` (part_id 20, display_order 20
— the Gradual's own slot), with the printed rubric as `option_txt` and the reasoning in `notes`.

**Why.** 2 April spells the semantics out: the Gradual is omitted and *in its place* (`eius
loco`) the Alleluia is said. 4 and 5 April are the same construct with the rubric abbreviated —
identical layout, identical position on the same page. `al1` is precisely "the first Alleluia,
sung in the Gradual's place", and there is a direct precedent in `specs/annunciation.json`
(25 March, `Tempore paschali, omissis Graduali et Tractu, dicitur:` → `al1` + `al`).

**Deliberately NOT applied elsewhere.** Six other April days print `AL.` with **no Gradual and no
rubric at all** (§3), and 11 April prints two complete seasonal formularies without any
"replaces the Gradual" wording. Those all got plain `al`. That is fidelity to what each page
prints rather than a blanket rule — flagging it so you can overrule if you would rather see one
uniform treatment.

## 3. Six Masses print no Gradual — `⚠ COMPLETENESS` cleared against the page (LOADED)

`⚠ COMPLETENESS: … is missing [gr]` fired on six specs. I treated each as a blocker and cleared
it against the dpi=200 page image before loading:

| day | slug | page / span | printed parts |
|---|---|---|---|
| Die 21 aprilis, S. Anselmi | `anselm-of-canterbury` | p555, y401–494 | IN, AL(+vel), OF, CO |
| Die 23 aprilis, S. Georgii | `george` | p556, y44–141 | IN, AL(+vel), OF, CO |
| Die 25 aprilis, S. Marci | `st-mark` | p556, y257–378 | IN, AL, OF(+alt), CO(+alt) |
| Die 28 aprilis, S. Petri Chanel | `peter-chanel` | p556, y399–496 | IN, AL, OF, CO |
| Die 29 aprilis, S. Catharinæ Senensis | `catherine-of-siena` | p557, y48–248 | IN, AL(+vel), OF, CO ×2 formularies |
| Die 30 aprilis, S. Pii V | `pius-v` | p557, y273–372 | IN, AL(+vel), OF, CO |

**Why I am confident this is editorial, not a parsing gap.** There is **no rubric of any kind**
in any of those six spans — nothing that could have been mis-scoped onto a default chant, and no
line above or below the boundary that could have been mis-assigned. All six dates fall in
Paschaltide in effectively every year (latest possible Easter is 25 April), and Paschaltide has
no Gradual. The book itself says so three days earlier on p554: *"Tempore paschali omittitur
Graduale."* The loader's paschal waiver only triggers on a `PASC-*` slug, so on a Sanctorale
saint-slug this warning is a structural false positive — the same shape as the known Lenten
`gr-lent-feria-no-tract` case. **Confirm you are happy these six stay without a Gradual.**

## 4. The `chant_group` collision hazard: checked everywhere, nothing held back

The loader dedups on slot + `chant_group` and **ignores `option_num`**, so two printed options in
one slot whose chants share a `chant_group` collapse silently on the real write (a dry-run cannot
show it). April is the first month to exercise this shape at scale — **13 multi-option slots
across 7 Masses**, including the `Tempore paschali … vel …` construct this hazard was first
predicted for.

I queried `v_chant_item` for the `chant_group_id` of every member of every multi-option slot
**before** the real write. **All 13 slots came back with distinct groups**, and every one loaded
as its own row (62 rows inserted, 62 distinct `chant_uuid` values, zero duplicate
slot+`chant_uuid` pairs, all ten ROW COUNT assertions PASS). **Nothing was held back on these
grounds and no `notes` workaround was needed.**

The tightest case, worth recording: **Pius V (30 April) cites the SAME page for both Alleluia
options** — `AL. Tu es sacérdos, 449, vel Hic est sacérdos, 449.` p449 holds exactly two
alleluias, so the incipit is the sole discriminator; they resolved to gregobase 477 (mode 8) and
1118 (mode 2), chant_groups 477 and 1118. Runner-up: Catherine of Siena's `al` slot carries
**three** options (gregobase 208 / 406 / 1082) across the primary and `Vel ad libitum`
formularies.

## 5. Two whole-Mass alternate formularies (LOADED as printed; convention noted)

Two days print more than one complete set of propers. Both are modelled as extra rows in the same
slots, distinguished by `option_txt` carrying the book's rubric verbatim — the established
`com-sanct-*` convention, no `wkday`/`cycle_sun` anywhere:

- **Die 11 aprilis, S. Stanislai (p555)** — `Tempore paschali :` (IN/AL+vel/OF/CO) and
  `Extra tempus paschale :` (IN/GR/AL/OF/CO) = **10 rows**. Note this is the only April Mass that
  loads a `gr` at all outside the p554 trio.
- **Die 29 aprilis, S. Catharinæ Senensis (p557)** — the primary Mass (IN/AL+vel/OF/CO) and
  `Vel ad libitum :` (IN/AL/OF/CO) = **9 rows**.

## 6. St Mark's em-dash alternates, and the `cum ps.` traps (LOADED)

**Em-dash alternates (25 April, p556).** The GR marks two alternates with an em-dash instead of
`vel`:
```
OF.  Confitebúntur, 441.
 —   In omnem terram, 435.
CO.  Signa, cum ps. 88*, 437.
 —   Data est mihi, 213, cum ps. 77*, l. 3-4 a. 23. 24. 25. 27.
```
Each `—` line is a genuine second chant of the part above it. Loaded as its own row with
`option_txt` set to the printed marker `—` (U+2014) and a `notes` line saying the book uses an
em-dash rather than `vel`. Raised only so a later reviewer does not read a bare `—` in
`option_txt` as junk.

**`cum ps. NNN*` psalm plans** — the established convention (plan → `notes`, never a
`target_page`, never a row, never `option_txt`) applied to five chants: `isidore` CO (`ps. 118*`),
`vincent-ferrer` CO (`ps. 120*`), `st-mark` CO ×2 (`ps. 88*`; `ps. 77*, l. 3-4a. 23. 24. 25. 27.`),
`peter-chanel` CO (`ps. 77* ut supra`), `pius-v` CO (`ps. 131*`). Psalm-tone data itself remains
unmodelled — the schema does not carry it.

Two April-specific variants of the trap, both handled:
- **St Mark's CO prints the psalm BEFORE the page**: `CO. Signa, cum ps. 88*, 437.` — `88` is a
  psalm, `437` is the page. Everywhere else in April the order is reversed.
- **Peter Chanel's `ut supra` is about the PSALM VERSES, not the Mass**: `CO. Data est mihi, 213,
  cum ps. 77* ut supra.` refers back to St Mark's verse list three days above on the same page.
  It is **not** the §1 inheritance construct — 28 April prints its own four chants in full.

## 7. Things I checked and found clean (no action needed)

- **No calendar gaps.** All 13 GR April dates have a `proper_of_saints` row and an existing
  `lit_epoch` slug. Nothing was invented.
- **Both ambiguous dates confirmed against the printed title**, as March's director had settled
  them: 23 April `S. GEORGII, MARTYRIS` → `george` (not `adalbert`/`giles`); 28 April
  `S. PETRI CHANEL, PRESBYTERI ET MARTYRIS` → `peter-chanel` (not `louis-de-montfort`). The pages
  agree; no override was needed.
- **Ranks already correct — no writes made.** The GR prints `Mem.` on 7, 11 and 29 April and
  `Fest.` on 25 April, and nothing on the other nine days. `lit_epoch.rank_code` already holds
  MEMORIAL / MEMORIAL / MEMORIAL / FEAST and NULL for the rest, in agreement. No NULL was filled
  from a blank margin (23 April in particular prints no marker, and `Fest.` two days below on the
  same page proves that is a genuine blank rather than an OCR miss).
- **No dropped month tail.** The April split PDF ends at printed p557. I read p558 from the
  CHAPTER pdf (splits end one page early, so the tail above the next month's heading is invisible
  in the split): its first content block is the `MAIUS` chapter heading at y37.7, with only the
  running header above it. Nothing of April spills past the split.
- **No index/OCR repairs were needed.** All 62 chants resolved `via index` with **zero**
  `ℹ index incipit mismatch`, zero `ℹ version-split` and zero `⚠ REVIEW` lines. No
  `gr_index_entry` row was edited this month.
- **Same-page collisions all landed right.** Pre-flighted and confirmed: p494 (`Os iusti` as both
  graduale gb 511 for 2 April and introitus gb 1374 for 5 April), p511 (two `Beatus vir …`
  alleluias, separable only by `qui timet` / `qui suffert`), p476 (two graduals **both mode 5** —
  incipit the only discriminator), p416 (two alleluias **both mode 8**), p449 (both of Pius V's
  options), p441 (`Confitebuntur cæli` vs `Repléti sumus`, cited by three different days),
  p491 (`Beatus servus` vs `Fidelis servus`), p447 (cited twice by Stanislaus as two different
  parts), and three distinct `Iustus ut palma` chants on pp.508/510/497 as introit/gradual/
  offertory.
- **`Domine, Deus salutis meæ, 317`** (Catherine's `Vel ad libitum` AL) looks like a Lenten tract
  but the curated index genuinely holds p317's entry as an **alleluia** (mode 3, gb 1082). The
  printed `AL.` is correct; no `office_part` override was needed.
- **Chapter preamble (GR p532).** The two `Proprium de Sanctis` chapter-wide rubrics are already
  modelled on the `SAINTS` epoch's `notes`. Not re-raised here.

## 8. Scratch space not cleaned

`propers-parser/_tmp/aprilis/` holds five dpi=200 page PNGs (554–558). Deleting
`propers-parser/_tmp` is blocked by the permission classifier (both `rm -rf` and `shutil.rmtree`
are denied), so it was left in place rather than burning turns retrying.
