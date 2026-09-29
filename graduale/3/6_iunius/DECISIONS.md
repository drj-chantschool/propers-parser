# IUNIUS (Graduale Romanum, Proprium de Sanctis, printed pp. 565–577) — decisions & open items

Batch run 2026-09-03. **19 Masses on 16 dated entries, all 19 loaded — 103 rows,
12 engraved / 91 cross-reference.** Every spec dry-run clean, loaded, idempotent, `ref_page_num`
correct. Two `VERIFY` ROW COUNT lines report FAIL for a known benign reason (§6).

Composition note: 16 `Die N iunii` headings, plus one `Eodem die` (22 June, §5), plus the two
apostolic solemnities that each print `AD MISSAM IN VIGILIA` **and** `AD MISSAM IN DIE` as separate
level-2 Masses (24 and 29 June) — 16 + 1 + 2 = 19.

Four of the 19 (the two solemnities and their two vigils) were already produced and loaded on
2026-08-25/26 as part of earlier Gregorian-Missal cross-reference work. They were **re-reviewed
against the pages in this run**, not taken on trust; the three gaps that review found are §3.

---

## 1. HELD — two `Cantus ut supra` / whole-Mass inheritance days (needs the standing ruling)

Both are instances of the already-open `Cantus ut supra` construct. Neither is a parse failure;
both are the book working as designed, and both are deliberately **not** turned into rows.

### 1a. 3 June — SS. Caroli Lwanga et Sociorum (GR p565, y475.7–497.5)

Printed, immediately after the five default citations:

```
Tempore paschali :
Cantus ut supra die 2 iunii pro T. P.
```

**What I did.** Loaded the five default chants (`the-martyrs-of-uganda`, 5 rows). The Paschaltide
block is recorded verbatim in the `in` row's `notes` and is otherwise unmodelled — there is no
`lit_epoch_tree` edge from 3 June to 2 June, so the inherited paschal chants are unreachable.

### 1b. 11 June — S. Barnabæ, Apostoli (GR p566, y488.0–498.9)

Printed, after the five default citations:

```
T. P., cantus ut in festo S. Matthiæ, die 14 maii, 562.
```

**What I did.** Loaded the six default chants (`st-barnabas`; the `co` slot has two options, §4).
The whole-Mass Paschaltide inheritance is recorded in the `in` row's `notes` and otherwise
unmodelled. Note this one names a **page** (562) as well as a day, so if the ruling distinguishes
page-naming from day-naming inheritance (as `ADV-II` `ut supra … præter` did), 11 June may resolve
differently from 3 June.

**What I need decided.** The same ruling that settles 11 Feb (Lourdes, partial), 8 Mar, and
7/13/24 Apr. Running tally of held days is now **seven**, across five months. Options previously on
the table: add a `lit_epoch_tree` edge to the source day, copy rows, store the rubric only, or
leave the day paschally empty.

---

## 2. HELD — one intra-Mass `chant_group` collision, 2 June

**What the page shows.** GR p565, SS. Marcellini et Petri:

```
OF.  Lætámini in Dómino, 468 (T. P. 443).
…
Tempore paschali :
AL.  et OF. ut supra.
```

p468 → gregobase **786** `Laetamini in Domino (sine alleluia)`; p443 → gregobase **870**
`Laetamini in Domino (cum alleluia)`. These are two genuinely distinct engravings, but
**`v_chant_item` puts both in chant_group 786**, and `load_graduale_propers.py` dedups on
slot + chant_group **ignoring `option_num`** — so a second `of` row would not insert, it would
silently UPDATE the first and clobber its provenance. A dry-run cannot show this; it only appears
as a ROW COUNT failure after the real write.

**What I did.** Loaded **one** `of` row (target 468, gregobase 786) with the full reason in its
`notes`. The `(T. P. 443)` alternate is not loaded. This is the same treatment already applied to
`com-sanct-gen`'s `Lætámini in Dómino, 468 (T. P. 443)` in GR chapter 2 — deliberately consistent
with that precedent.

**What I need decided.** Whether to add `option_num` (or `chant_uuid`) to the loader's dedup key.
Until then this construct can never carry both of its options. Two live instances now
(`com-sanct-gen`, `marcellinus-and-peter`).

**Not a collision:** the same block's `AL. et OF. ut supra.` is sense-3 `ut supra` — a same-Mass
back-reference saying the paschal Alleluia and Offertory are the chants already listed. It adds no
chant and is recorded in the `al` row's `notes`. And the paschal block correctly prints no Gradual;
none was invented.

I swept every other multi-option slot in the month for this failure mode **before** writing —
`justin-martyr` of/co, `marcellinus-and-peter` in/co, `st-boniface` co, `st-barnabas` co,
`aloysius-gonzaga` co, `first-martyrs-of-rome` in. All are in distinct chant_groups; nothing else
collapsed, and all loaded at full row count.

---

## 3. FIXED in this run — three printed items the pre-existing solemnity specs had dropped

Re-reading the four already-loaded Masses against the pages found three pieces of printed text with
no model. All three are performance/verse plans, not chants; per the established convention they go
in the chant's `notes`, not into new rows. The three specs were patched and re-loaded
(`updated=5` each, `chant_uuid` untouched).

| page | printed text | now in |
|---|---|---|
| 571 | `Repetitur Priusquam usque ad versum.` | `nativity-john-baptist` **gr** `notes` |
| 572 | `Cant. Benedictus : Lc. 1. 68. … 79 / sed iuxta codices antiquiores, potissimum ante ceteros cantandi sunt : 77. 78. 79` | `nativity-john-baptist` **co** `notes` |
| 577 | `Ps. 79*, 2 ab. 8. 9. 10. 11. 12. 15. 16. 18. 19. 20` | `ss-peter-paul` **co** `notes` |

Everything else in those four Masses checked out: engraved-vs-xref split correct on all 20 rows
(engraved rows `ref_page_num` NULL, citations set), all 12 engraved chants match their
`gr_index_entry` row, all 8 citations resolve to the expected id, and the two
`Antiphona ad introitum I` / `III` headings are **modes** (1 and 3), which is what the specs
already carried.

---

## 4. Recorded, not held — constructs modelled per existing rules

- **`438, V vel VI` (11 June, p566).** A roman numeral trailing a *citation* is an option marker,
  not a mode: the 5th and 6th communio of that Common → **two** `co` rows (gregobase 1028 mode 1,
  gregobase 97 mode 2, distinct chant_groups). Because the first index incipit
  (`Vos qui secuti estis me`) is a **prefix** of the second
  (`Vos qui secuti estis me dicit Dominus`), option VI's spec incipit is written in the target
  page's full index form rather than the printed short form; the deviation is in its `notes`.
- **Em-dash alternates — two of them this month.** 21 June `aloysius-gonzaga` `— Panem de cælo,
  319.` (second `co`) and 30 June `first-martyrs-of-rome` `— Timéte Dóminum, 453.` (second `in`).
  Both are real second options with `option_txt: "—"`, both in distinct chant_groups, both loaded.
- **`Tempore paschali :` blocks** (1, 2, 5 June) are `option_txt` on the chants that follow, never
  subsections and never chants.
- **`cum ps. NNN*` psalm plans** (6, 9, 11, 13, 19, 22 June) — the number before the comma is the
  target page, the starred number is a psalm. Modelled as `notes`; no chant, no `option_txt`.
- **Rank markers** printed: `Mem.` on 1, 3, 5, 11, 13, 21, 28 June; `Sol.` on 24 and 29 June; none
  printed on 2, 6, 9, 19, 22 (both Masses), 27, 30 June. All nine printed markers already match
  `lit_epoch.rank_code`, and every unmarked day is already NULL. **No rank writes were made** and
  none are needed; absence was not treated as evidence.

---

## 5. Resolved (report only) — 22 June's two Masses, and the two Vigil/Day pairs

- **22 June is `✗ AMBIGUOUS`** in the resolver: the date carries two saints and two printed Masses.
  `Die 22 iunii / S. PAULINI NOLANI, EPISCOPI` (p567 y400) → `st-paulinus-of-nola`;
  `Eodem die / SS. IOANNIS FISHER … ET THOMÆ MORE` (p568 y40) → `john-fisher-and-thomas-more`.
  Picked by the printed GR titles, not by name-matching. Both `lit_epoch` rows already existed;
  both Masses loaded separately, 5 rows each. They were **not** merged.
- **24 June** → `nativity-john-baptist-vigil` (p568 y231 → p570 y92) and `nativity-john-baptist`
  (p570 y92 → p572 y370). **29 June** → `ss-peter-paul-vigil` (p573 y221 → p575 y46) and
  `ss-peter-paul` (p575 y46 → p577 y366). All four `lit_epoch` rows already existed
  (`kind='mass'` for the vigils); no slug was invented.
- **No missing-epoch case this month.** All 19 Masses resolved to an existing `lit_epoch`. Nothing
  like May's Bernardine of Siena gap.

---

## 6. Two benign `VERIFY` ROW COUNT FAILs — the base-slug-family caveat

`--verify` counts the whole base-slug *family*, and `<day>-vigil` is a suffix of `<day>`. So
verifying `nativity-john-baptist` (5 rows) also counts `nativity-john-baptist-vigil` (5) and
reports `FAIL (expected 5, got 10)`; same for `ss-peter-paul`. The printed tables show exactly 5
correct rows per slug, `IDEMPOTENT: PASS` and `REF_PAGE_NUM: PASS` on all four. Verifying the two
vigil slugs directly gives `VERIFY PASS`. This is the documented caveat, not a data problem.

---

## 7. One `gr_index_entry` repair

Row **1132** (p440, introitus, mode 3, gregobase 1231) read `Sanci tui` — a genuine OCR typo, not a
curated disambiguator: `gregobase_chants.incipit` for 1231 is `Sancti tui`. Corrected to
`Sancti tui` as `jcost` (`gregobase_id` and `match_status` left alone). No spec anywhere in
`specs/` used the misspelling, so there was no blast radius. 2 June's `IN. Sancti tui, Dómine, 440.`
now resolves with no `ℹ index incipit mismatch`. The typo persists in the upstream OCR artifacts
(`gr_index_entries.json`, `gr_chant_index_reviewed.csv`), so a rebuild of the index table would
reintroduce it.

---

## 8. Nothing else was omitted

Every printed line on pp. 565–577 within a June Mass's span has a model or a `notes` entry.
Specifically checked and cleared:

- p578's top holds only the `IULIUS` heading and `Die 3 iulii` — **no June tail spills past the
  month split**, so the usual split-drops-the-boundary-page hazard does not bite here.
- `gr_index_entry` has zero rows on pp. 565, 566, 567 and on the in-span parts of 572, 573, 577 —
  which *positively* confirms the 15 memorial Masses are all-cross-reference rather than assuming
  it. The 12 index rows on pp. 568–577 correspond exactly to the 12 engraved rows loaded.
- Merged OCR blocks (9 June OF+CO, 27 June IN+GR, 30 June OF+CO) were handed to producers as one
  shared whole-block band each; identical bboxes there are correct.
