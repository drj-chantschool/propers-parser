# FEBRUARIUS — open items for John's ruling

Graduale Romanum `Proprium de Sanctis`, February (printed pp. 539–550).
Batch run 2026-09-02. 12 Masses produced and loaded (57 rows); Feb 2 (the Presentation,
13 rows) was already loaded before this batch. Every Mass VERIFY PASS.

Nothing on any February page was silently dropped. Everything below is either a question,
or a decision I made under an existing precedent that I want confirmed.

---

## 1. Our Lady of Lourdes (Feb 11) — the `præter :` partial-override Mass — **NEEDS A RULING**

**What the page prints** (p547, y275–393), in full:

> *B. MARIÆ VIRGINIS DE LOURDES*
> *Ut in sollemnitate Conceptionis immaculatæ B. M. V., die 8 decembris,*
> *præter :*
> `IN.  Vultum tuum deprecabúntur, 404.`
> *Tempore Quadragesimæ :* `OF.  Ave, María, 419.`

That is the whole Mass. **No GR., no AL., no CO. is printed.** They are inherited from the
Immaculate Conception (8 December), which the GR names as a *day*, not as a page.

**What I did.** Loaded exactly the two printed chants (2 rows):
- `in` → xref p404 → `gregobase:124`, with the full rubric recorded verbatim in `notes`.
- `of` → xref p419 → `gregobase:843`, with `option_txt = "Tempore Quadragesimae :"` and a
  `notes` field saying the non-Lenten offertory is the Immaculate Conception's own
  (engraved p630 — a *different* chant from p419's `Ave, Maria et benedictus`).

I did **not** materialize gr/al/co. Rationale: the closest repo precedent for a `…, præter:`
Mass that references a *different day* is `specs/pasc-ad-asc-06.json`, which models only the
printed exception and records "the rest of the Mass is the <referenced> Mass" in `notes`. The
other precedent, `ADV-II`'s *"Ut supra feria N, **p**, praeter:"*, DOES materialize the
inherited parts as cross-references — but there the rubric prints the target **page**, so the
`ref_page_num` came from the book. Here it does not; I would have had to look the Dec-8 Mass up
myself and assert pages (629/630/631) that p547 never prints.

**The loader raised `⚠ COMPLETENESS: missing [gr, co, al/tr]`.** I treated that as a blocker,
re-read the page myself, and cleared it: this is a genuine partial override, not a mis-scoped
rubric. But the warning is pointing at something real —

**What I need decided:** as loaded, a query for Lourdes' gradual/alleluia/communion returns
nothing. There is **no `lit_epoch_tree` edge from `our-lady-of-lourdes` to
`immaculate-conception`**, so the inheritance the book asserts is not reachable in the data.
Three options:
   a. leave it as-is (faithful to the page; the inheritance lives only in prose `notes`);
   b. materialize gr/al/co as cross-references to the Immaculate Conception's engraved pages
      (629 `Benedicta es tu`, 630 `Tota pulchra es`, 631 `Gloriosa dicta sunt de te`), i.e.
      follow the ADV-II shape and accept derived page numbers;
   c. add a `lit_epoch_tree` edge (Lourdes → Immaculate Conception) and let the existing
      most-specific-wins inheritance walk resolve it — structurally the cleanest, but it is a
      tree change I would not make unilaterally, and the tree currently hangs every saint
      directly off `SAINTS`.

I recommend (c), but it is a structural decision, not a parsing one.

**Related, same ruling:** the Lenten offertory is currently the *only* `of` row for the day, so
a consumer that ignores `option_txt` will use the Lent chant year-round. Under (b) or (c) that
resolves itself; under (a) it does not.

---

## 2. `gr_index_entry` OCR typo fixed on p528 — **done, please confirm**

The index row for p528's Alleluia (row_id 1373) read **`Loquear`**. The printed page (verified
against the p528 page image from `books`) reads
`℣. Loquébar, Dómine, de testimóniis tuis in conspéctu regum, et non confundébar.`

St. Agatha (Feb 5) cites `AL. Loquébar, Dómine, 528.` Because p528 carries only one alleluia
row, the loader's single-candidate fallback still resolved it correctly (`gregobase:642`) — but
it printed an `ℹ index incipit mismatch`, and the typo would hard-fail any future citation to a
2-candidate page.

**What I did.** Per the established remedy (fix the index row, keep the printed spelling in the
spec), updated as `jcost`:
`UPDATE gr_index_entry SET incipit='Loquebar, Domine' WHERE row_id=1373` — `gregobase_id` (642)
and `match_status` untouched.

Blast-radius check: no spec used the string `Loquear`; the one other spec citing p528
(`pasc-ad-asc-03.json`) already used `Loquebar, Domine` and now matches exactly instead of
falling back. Re-dry-ran it: clean.

**Caveat for you:** the typo persists in the upstream OCR artifacts
(`propers-parser/gr_index_entries.json`, `graduale/VALIDATED/gr_chant_index_reviewed.csv`), so
a rebuild of `gr_index_entry` would reintroduce it. I did not edit those provenance files.

---

## 3. Ambiguous date resolutions — **please confirm both**

The resolver returned `✗ AMBIGUOUS` for two February dates. I picked by the printed GR title,
never by matching Latin title to English slug.

- **Feb 3** carries two `proper_of_saints` slugs, and the GR prints **two Masses**:
  `Die 3 februarii — S. BLASII, EPISCOPI ET MARTYRIS` → `st-blaise`, and
  `Eodem die — S. ANSGARII, EPISCOPI` → `st-anskar`.
  Loaded as two separate Masses with two separate `lit_epoch` slugs, 5 chants each. Confident.
- **Feb 8** carries two slugs, `jerome-emiliani` and `josephine-bakhita`. The GR prints only
  `S. HIERONYMI EMILIANI` → **`jerome-emiliani`**. `josephine-bakhita` gets no GR Mass
  (see §4). Confident, but it was a resolver-flagged ambiguity so I am recording it.

---

## 4. February calendar coverage — two gaps, both benign as far as I can tell

- **`brigid-of-kildare` (Feb 1)** — has a `proper_of_saints` row but **no GR Sanctorale entry
  at all**; the GR's February chapter opens at Feb 2. Not a parsing gap; the book simply has no
  Mass there. Flagging only so it is not later mistaken for unparsed backlog.
- **`josephine-bakhita` (Feb 8)** — has a `proper_of_saints` row but the GR prints only Jerome
  Emiliani on that date, so she gets no GR rows. Same situation.

Neither needs action unless you want these days to inherit from a Common.

---

## 5. St. Blaise (Feb 3) and St. Polycarp (Feb 23) cite an identical Mass

Both print exactly:
`IN. Sacerdótes Dei, 447.` / `GR. Glória et honóre, 476.` / `AL. Hic est sacérdos, 449.` /
`OF. Invéni David, 447.` / `CO. Posuísti, Dómine, 483.`

This is genuine duplication in the book (both are bishop-martyrs drawing the same Common set),
not a copy error on my side. Loaded as two independent 5-row Masses under their own slugs; the
same five `chant_uuid`s therefore appear twice in February. No dedup collision — the slugs
differ, so the loader's slot key separates them.

---

## 6. Chair of Peter (Feb 22) — the offertory resolves to a `(T.P.)`-tagged chant

`OF. In omnem terram, 435.` resolves via the index to **`gregobase:9185`**, whose gregobase
incipit is tagged `In omnem terram(T.P.)`, in `chant_group` 3360 together with its non-paschal
counterpart. Per your standing ruling (2026-08-31) a T.P. variant sharing a `chant_group` with
its non-T.P. counterpart is handled by global logic elsewhere, so I did **not** investigate it,
split the group, or add an `office_part` override. Recording it only so you know it was seen
and deliberately left alone. No action expected.

---

## 7. Psalm-tone plans recorded in `notes`, still unmodeled schema-wide

Two February chants print a psalm plan that the schema has no home for. Both were modeled per
the established convention — chant modeled normally, plan verbatim in `notes`, never a
`target_page`, never `option_txt`, never a separate row:

- **St. Anskar `co`** — `CO. Beátus servus, 491, cum ps. 32*.` → target page **491**, gb 1154.
  (`32*` is a psalm number, not a page.)
- **Chair of Peter `co`** — the line below the engraved *Tu es Petrus*:
  `Ps. 79*, 2 ab. 9. 10. 11. 12. 15. 16. 18. 19` → recorded in `notes`, band includes it.
  Same shape as the `Cant. Magnificat…` note already in `specs/immaculate-conception.json`.

No ruling needed unless you want psalm-tone data modeled properly, which would be a schema
change.

---

## 8. One expected `ℹ` note worth knowing about — St. Agatha's introit

St. Agatha's engraved introit (p545) resolves with:
`ℹ index incipit mismatch for in 'Gaudeamus omnes in Domino' on p545 — using the page's single
resolved in entry ('Gaudeamus Agathe')`

This is **correct**, not a defect. The p545 index row carries a curated *disambiguator* incipit
(`Gaudeamus Agathe`) that the page never prints, because gregobase's own incipit for this chant
is the unreachable ellipsis form `Gaudeamus... Agathae`. The spec keeps the printed incipit; the
single-candidate fallback lands on the right chant (`gregobase:1183`). No action needed — noted
because the same `ℹ` line on a *multi*-candidate page would be a real problem.

---

## Nothing else is outstanding

Every other chant on pp. 545–550 resolved to the gregobase id predicted in pre-flight, with a
full `in/gr/al/of/co` set, no `⚠ COMPLETENESS` (except Lourdes, §1), no `⚠ REVIEW`, and no
version-split. Boundary page p551 was checked directly from the page image: it opens with the
`MARTIUS` chapter title, so no February material spills past p550.

The two chapter-wide `Proprium de Sanctis` preamble rubrics on printed p532 are already modeled
on the `SAINTS` epoch node and are deliberately not re-raised here.
