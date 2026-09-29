# September (Proprium de Sanctis, GR pp. 597–611) — decisions & open questions

Batch run 2026-09-03. 14 Masses, 67 chants loaded (13 engraved / 54 cross-reference), all
`VERIFY PASS`. This file records only what needs a ruling or was deliberately not modeled.

---

## 1. HELD — `Ut supra … præter :` on the Nativity of Mary (8 Sept, p597)

**What is printed.** Under the title `IN NATIVITATE B. MARIÆ VIRGINIS` (Fest.), an italic rubric:

> `Ut supra, in festo Visitationis B. M. V., die 31 maii, 564, præter :`

followed by **one** chant only — an engraved Alleluia, mode VII, `℣. Sollemnitas gloriosæ
Vírginis Maríæ ex sémine Abrahæ, ortæ de tribu Iuda, clara ex stirpe David.` No introit,
gradual, offertory or communion is printed.

**Variant (this matters to the ruling).** This instance names **all three** coordinates: a
**feast** (*in festo Visitationis B. M. V.*), a **day** (*die 31 maii*) **and** a **page**
(*564*). That is the richest form seen so far — richer than 11 Feb (Lourdes, partial, no page)
and comparable to 11 Jun, which named a day + page. If the ruling ends up distinguishing
page-naming from day-naming inheritance (as `ADV-II` did), this day is on the page-naming side.

**What I did.** Loaded the one printed Alleluia (`gregobase:420`, engraved, p597) with the
rubric verbatim in its `notes`. This follows the Lourdes precedent, where the printed override
chants were loaded and only the inheritance was left open. The `⚠ COMPLETENESS` warning for the
missing `in/gr/of/co` is expected and was cleared against the page image — the book genuinely
prints nothing else here.

**What is needed.** The whole-Mass-inheritance ruling. Note the target is immediately actionable:
`the-visitation-of-mary` already carries a complete 5-chant `book='GRADUALE'` row set, so a
`lit_epoch_tree` edge (or a row copy) would resolve this day the moment the ruling lands.

**Running tally of held `ut supra` / `præter` Masses: 11 Feb, 8 Mar, 7/13/24 Apr, 3/11 Jun,
5/7 Aug, and now 8 Sept — ten Masses.**

### `ut supra` hits classified (whole month)

Only one hit in September, and it is sense (1) above. There were no `cum ps. NNN* ut supra`
back-references and no `AL. … ut supra.` same-Mass back-references this month.

---

## 2. HELD — St Wenceslaus's introit: the p523 index row resolves to the wrong chant

**What is printed** (28 Sept, p607): `IN. In virtúte tua… lætábitur rex, 523.` — the ellipsis is
really printed.

**The problem.** GR p523 (bottom, under `Pro iis qui respublicas moderati sunt`,
`ANTIPHONA AD INTROITUM`, mode **VII**, `Ps. 20, 2. 3. 4`) engraves
*In virtúte tua, Dómine, lætábitur rex…*. gregobase has that exact chant:

| id | incipit | mode | version | `book:` header |
|---|---|---|---|---|
| **20551** | `In virtute tua ...rex` | 7 | **Solesmes 1974** | **`Graduale Romanum, 1974, p. 523`** |
| 15921 | `In virtute tua(St Louis)` | 7 | Solesmes | *(none)* |

`gr_index_entry` row **1067** (p523, introitus, mode 7) points at **15921** — a St-Louis-proper
introit — with `match_status='reviewed'`. The reason is the ellipsis trap: 20551's incipit
`In virtute tua ...rex` cannot prefix-match, **and 20551 has no row in
`gregobase_chant_group_map`**, so it is invisible to `v_chant_item` and cannot yield a
`chant_uuid` at all. The curator had nothing else reachable to pick.

The citation resolves *cleanly* (single-candidate fallback, only an `ℹ index incipit mismatch`),
so loading it would have silently stored the wrong chant with a `VERIFY PASS`.

**What I did.** Loaded St Wenceslaus's other **four** chants and **held the introit**. The
omission is recorded verbatim in the gradual's `notes`. The `⚠ COMPLETENESS: missing [in]`
warning is this, and only this.

**What is needed — a ruling on two writes I did not make:**
1. `INSERT INTO gregobase_chant_group_map (gregobase_id, chant_group_id) VALUES (20551, …)` —
   make the correct Solesmes-1974 edition matchable at all.
2. `UPDATE gr_index_entry SET gregobase_id=20551 WHERE row_id=1067` — this **overrides a
   `match_status='reviewed'` human pick**, which is why I stopped rather than acting.

I deliberately did *not* load-then-fix: the loaders never overwrite `chant_uuid`, so a row loaded
onto 15921 would keep the wrong chant even after the index is corrected.

**Blast radius:** no other September citation touches p523, and no other spec in `specs/` cites it.

---

## 3. Rank marker printed but not stored — Our Lady of Sorrows (15 Sept)

`lit_epoch.rank_code` and `proper_of_saints.rank_code` for `our-lady-of-sorrows` are `NULL` /
`UNDETERMINED`, but the GR **does** print a right-margin `Mem.` on p600 at y≈211, x≈301, on the
title line `B. MARIÆ VIRGINIS PERDOLENTIS`. The resolver reported "(none printed)" — the OCR
renders it `Mern.`, and the one-substitution tolerance did not catch it here.

This is a genuine printed-vs-stored **disagreement**, not an inference from a blank margin.
**I did not write it** — rank writes are outside a propers load. Suggested, pending approval:
set both `lit_epoch.rank_code` and `proper_of_saints.rank_code` for `our-lady-of-sorrows` to
`MEMORIAL`.

All 13 other September days agree with what is printed. Bellarmine (17th), Januarius (19th),
Cosmas & Damian (26th) and Wenceslaus (28th) print **no** marker and correctly stay NULL — their
titles do not run into the margin, so absence here is real, not typographic.

---

## 4. Unmodelled printed items found by re-reading the two already-loaded Masses

Both slugs had been loaded earlier and verified clean; re-reading the pages found printed text no
loader check could ever have seen.

**Holy Cross (14 Sept) — a real omission.** Below the communion engraving on **p600** (y≈153),
above the Die 15 heading, the book prints:

> `Ps. 17*, 2 - 3 a. 3 bc. 4. 18. 38. 39. 41. 48. 49. 50`

A psalm-tone plan for the communion, captured nowhere in the spec (its `text_src` was `null` and
it had no `notes`). This is exactly the predicted signature — a psalm plan printed below an
engraving, on a page the spec named but never described. **Patched into the `co` row's `notes`
(text_id 3197), reloaded, re-verified.** Nothing else on pp. 598–600 was missing.

**Gregory the Great (3 Sept) — a convention deviation, not an omission.** The `cum ps. 118*` on
the communion *was* captured, but in `text_src`, which is reserved for the right-justified
scripture citation (none is printed here). Moved to `notes` per the established convention;
`text_src` is now NULL (text_id 3009). This retires the competing precedent that
`specs/gregory-the-great.json` used to set.

---

## 5. Index / OCR — one `ℹ`, and it is NOT a typo

The month-wide probe (68 citations, one run) threw exactly one `ℹ index incipit mismatch`: the
p523 introit above. Checked against the **printed** back-of-book index, which reads

> `7  In virtute tua ... rex`

so `gr_index_entry.incipit = 'In virtute tua rex'` is a **faithful transcription** with the
ellipsis dropped. **Leave the incipit alone** — the defect is in `gregobase_id` (§2), not the
wording. **No `gr_index_entry` incipit was edited this month**, so no spec elsewhere was disturbed.

---

## 6. `chant_group` collisions — none

September has exactly **one** multi-option slot all month: the Archangels' Alleluia (29 Sept),
where the engraved `Sancte Michael archangele` (`gregobase:1103`, cg 1103) is followed by
`Vel ad libitum : AL. Laudáte Deum, omnes ángeli, 262.` (`gregobase:538`, cg 538). **Different
groups**, so both loaded as separate rows (option_num 1 and 2) — confirmed in the DB after the
real write, not just the dry-run. No `Extra tempus paschale` block and no inline `(T. P. NNN)`
parenthetical anywhere in the month, so no intra-Mass collision risk.

---

## 7. Calendar — no GR-vs-DB conflicts this month

All 14 printed Latin titles match the slug the date resolver returned. The one flagged case,
28 September (`✗ AMBIGUOUS`: `st-lawrence-ruiz` / `st-wenceslaus`), was resolved by the printed
title `S. VENCESLAI, MARTYRIS` → **`st-wenceslaus`**. `st-lawrence-ruiz` has no GR Mass and is
untouched. No missing `lit_epoch` / `proper_of_saints` rows blocked anything.

**No addendum Mass.** `subsections_ai.json` lists the 14 `Die N` entries in strict ascending
order (3, 8, 13, 14, 15, 16, 17, 19, 21, 26, 27, 28, 29, 30) with no `Eodem die`, and p611 runs
straight from the Archangels' tail into Die 30, with p612 opening on the `OCTOBER` heading. So
none of September's post-1974 canonizations is back-filled as a ruled-off addendum here.

---

## 8. Resolver span under-reports (recorded, handled)

Two Masses would have lost chants if briefed from `printed span`:

| Mass | reported span | true span | what sat past the end |
|---|---|---|---|
| Our Lady of Sorrows | `[600 … 604]` | 600–**605** | end of the Stabat Mater, plus the `OF.` and `CO.` citation lines (2 chants) |
| Archangels | `[607 … 610]` | 607–**611** | end of the communion engraving, plus the `Cant. Danielis` and `Ad libitum, psalmodia IV toni.` lines |

Both were briefed from `boundary page` / `boundary Y` instead and are complete.

---

## 9. Modeled without a ruling (recorded for the record, no action needed)

- **Sorrows sequence (p602–605).** The italic rubric `Quando canitur Allelúia cum suo ℣., addi
  potest Sequentia :` is an **option marker** on the `seq` chant (the Sequence is optional —
  *addi potest*), not a subsection heading. Loaded as `option_txt`.
- **Archangels introit heading `Antiphona ad introitum III`.** The `III` is the **mode** (3),
  confirmed against `gr_index_entry` (p607 introitus mode 3), not an option number.
- **Psalm/canticle plans recorded in `notes`, never as chants or target pages:** `cum ps. 118*`
  ×3 (Gregory, Chrysostom, Jerome), `cum ps. 24, 1-2a. …` (Sorrows co), `Ps. 17*, …` (Holy Cross
  co), `Cant. Danielis 3, 57. …` + `Ad libitum, psalmodia IV toni.` (Archangels co).
- **`T. P. Allelúia` appended** to the Archangels' introit and communion stays folded into its
  own chant — it cites a paschal ending, not an alternate engraving.
- **No em-dash alternates anywhere in September.** Checked on every part of every Mass.
