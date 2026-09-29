# MARTIUS — decisions and open questions

Graduale Romanum, `Proprium de Sanctis`, printed pages **551–553**.
Batch run 2026-09-02. 9 dates in the month; `st-joseph` (6 rows) and `annunciation` (7 rows)
were already loaded; 6 Masses / 27 chants loaded in this run; **1 Mass deliberately not loaded**.

---

## 1. HEADLINE — Die 8 martii, S. Ioannis a Deo: `Cantus ut supra, die 4 martii.` (NOT LOADED)

**What the book prints.** GR p551, y 317–390. A heading, a title, and one italic line — and
nothing else:

```
Die 8 martii
S. IOANNIS A DEO, RELIGIOSI
Cantus ut supra, die 4 martii.
```

No `IN.` / `GR.` / `AL.` / `OF.` / `CO.` lines, no incipits, no page citations, no rank marker.
The Mass is entirely by reference to S. Casimiri (Die 4 martii, same page, y 75–196), whose five
chants ARE loaded (`casimir`, text_ids 3678–3682).

**What I did.** Loaded **nothing** for `john-of-god`. The slug exists (`lit_epoch.slug =
'john-of-god'`, `kind='saint'`) and its only `lit_epoch_tree` edge is `SAINTS → john-of-god`.
`lit_part_sources` for it is empty.

**Why I did not decide it.** This is the same construct as February's Our Lady of Lourdes (GR
p547: `Ut in sollemnitate Conceptionis immaculatæ B. M. V., die 8 decembris, præter :` followed by
only `IN. Vultum tuum deprecabuntur, 404.` and `Tempore Quadragesimæ: OF. Ave, Maria, 419.`).
There, only the two printed chants were loaded (`our-lady-of-lourdes`, 2 rows) and the four
inherited ones are unreachable, because there is no `lit_epoch_tree` edge to
`immaculate-conception`. **You have not ruled on that yet**, and March 8 is the same problem in
its purest form: Lourdes at least prints two overrides, John of God prints *zero* chants, so the
day currently resolves to no Mass at all.

**What I need decided.** One of:

- **(a) Tree edge.** Add `lit_epoch_tree(parent_slug='casimir', child_slug='john-of-god')` and let
  `sql/query-daily-mass-parts.sql`'s most-specific-wins walk inherit all five chants. Cheap
  (edge rows only, no schema change; the PK is already `(parent_slug, child_slug)` so multi-parent
  is fine). Models the rubric exactly: "chants as above". For Lourdes it also works — the two
  printed overrides sit at depth 0 and win over the inherited Dec 8 set. **Caveat:** it makes a
  *saint* the parent of another saint, which is not the intended `SAINTS → commons → saints` shape
  noted in the `saints-epoch-parent` design note; it is a lateral "cantus ut supra" edge, a
  different kind of relationship, and may deserve its own edge type rather than reusing the
  inheritance tree.
- **(b) Copy the rows.** Duplicate Casimir's five `lit_part_sources` rows onto `john-of-god` with
  `printed_page_num=551`. Simple and self-contained, but it invents five rows the book does not
  print on that day and loses the fact that the GR expresses this as a reference.
- **(c) Model the rubric only.** Store `Cantus ut supra, die 4 martii.` somewhere (there is no home
  for it today — `lit_part_sources.part_id` is `NOT NULL` and a rubric fills no part slot;
  `lit_epoch.notes` is the precedent used for the p532 chapter rubrics) and leave the day chantless
  until a general inheritance mechanism exists.
- **(d) Leave as is** — day loads empty, revisit later.

Whichever you choose, **Lourdes should be treated the same way** so the two do not diverge.

**Scope check:** I read all of pp. 551–553 and March 8 is the **only** `Cantus ut supra` /
`præter` construct in the month. No other March day defers to another day.

---

## 2. Three Masses print only four chants — no Alleluia (LOADED as printed; please confirm)

`⚠ COMPLETENESS: … is missing [al/tr]` fired on three specs. I investigated each against the
dpi=200 page image before loading, and in all three the book genuinely prints only
`IN. / GR. / OF. / CO.`:

| day | slug | page / span | printed parts |
|---|---|---|---|
| Die 17 martii, S. Patricii | `patrick-of-ireland` | p552, y 46–160 | IN, GR, OF, CO |
| Die 18 martii, S. Cyrilli Hierosolymitani | `cyril-of-jerusalem` | p552, y 160–285 | IN, GR, OF, CO |
| Die 23 martii, S. Turibii de Mongrovejo | `turibius-of-mongrovejo` | p553, y 217–337 | IN, GR, OF, CO |

**Why I am confident this is editorial, not a parsing gap.** All three dates fall inside Lent in
every year (earliest possible Easter is 22 March), and Lent has no Alleluia. The citations
themselves confirm it: Cyril's introit is `Sitientes, venite ad aquas, 114` and Turibius's gradual
and offertory are `Lætátus sum, 336` / `In te sperávi, Dómine, 322` — all **Lenten temporale**
pages, not Commons pages. By contrast the three earlier March days (4, 7, 9), which can fall
before Ash Wednesday, all print a full five-chant set including an `AL.`

This matches the existing `gr-lent-feria-no-tract` finding for Lenten ferias. **I flag it because
the missing part is a required slot and the golden rule says a gap is normally a mis-scoped
rubric.** Here it is not: there is no rubric anywhere in those spans, and no line above or below
the boundary that could have been mis-scoped. Confirm you are happy that these three days stay at
four chants, with no Tract substituted.

## 3. `cum ps. NNN*` psalm plans (LOADED; convention applied, no ruling needed)

Three communions carry a psalm-tone plan, recorded in the chant's `notes` per the established
convention — never as `target_page`, never as a separate row, never as `option_txt`:

- `casimir` CO — `Beatus servus, 491, cum ps. 32*.` → target_page 491
- `patrick-of-ireland` CO — `Fidelis servus et prudens, 491, cum ps. 131*.` → target_page 491
- `cyril-of-jerusalem` CO — `Beatus servus, 491, cum ps. 32*.` → target_page 491

Psalm-tone data itself remains unmodeled (the schema does not carry it). Raised only so it is on
the record.

## 4. Merged / overlapping OCR blocks on p552 (LOADED; bbox is approximate by design)

- **S. Cyrilli (p552, y 216.6–263.9):** fitz returns all **four** citation lines as ONE text
  block. All four rows share `band [216, 264]`; a `notes` line on the introit says so. The block
  was not subdivided — `bbox` is a sanity check that the right page region was parsed, not a crop.
- **S. Patricii (p552):** the `OF.` block (y 115.4–126.2) and `CO.` block (y 122.9–138.4) overlap
  in the OCR output although the printed lines are cleanly separated. Bands were set to
  `[115, 126]` / `[126, 139]`.

Neither affects which chant was loaded. Noted so a later bbox review does not read these as errors.

## 5. Things I checked and found clean (no action needed)

- **No calendar gaps.** All 9 GR March dates have a `proper_of_saints` row and an existing
  `lit_epoch` slug; the resolver reported no `✗ AMBIGUOUS` date for the month. Nothing was invented.
- **Ranks already correct — no writes made.** The GR prints `Mem.` on 7 March, `Sol.` on 19 and 25
  March, and nothing on the other six days. `lit_epoch.rank_code` and `proper_of_saints.rank_code`
  already hold `MEMORIAL` / `SOLEMNITY` / NULL–`UNDETERMINED` respectively, in agreement. No NULL
  was filled from a blank margin.
- **No dropped month tail.** The March split PDF ends at printed p553. I read p554 from the chapter
  PDF: it opens straight into the `APRILIS` heading (y 48) with only the running header above it —
  no March content spills past the split.
- **No index/OCR repairs were needed.** Every one of the 27 chants resolved `via index` with **no**
  `ℹ index incipit mismatch` and no `⚠ REVIEW`. Notably `AL. Spécie tua, 416` (Frances of Rome)
  resolved correctly to gregobase 406 — the `gr_index_entry` typo that used to read `Speie tua` on
  that page was already repaired in an earlier batch. No `gr_index_entry` row was edited this month.
- **Same-page collisions all landed right.** Pre-flighted and confirmed: p494 (`Os iusti` as both
  introit and gradual), p511 (two alleluias), p491 (two communions, one used by Casimir/Cyril and
  the other by Patrick), p470 (three communions), p416 (two alleluias **both mode 8** — incipit is
  the only discriminator), and `Diffusa est gratia` printed twice for Frances of Rome as two
  distinct chants (gradual p408 → 947, offertory p421 → 177).
- **Chapter preamble (GR p532).** The two `Proprium de Sanctis` chapter-wide rubrics are already
  modeled on the `SAINTS` epoch's `notes`. Not re-raised here.

## 6. Scratch space not cleaned

`propers-parser/_tmp/martius/` still holds three dpi=200 page PNGs (551, 552, 553). Deleting
`propers-parser/_tmp` is currently blocked by the permission classifier (both `rm -rf` and
`shutil.rmtree` are denied), so it was left in place rather than burning turns retrying.
