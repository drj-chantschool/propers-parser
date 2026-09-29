# IULIUS (July) — Graduale Romanum, Proprium de Sanctis — decisions & open items

Printed pp. **578–583**. 17 Masses, 86 chants (2 engraved, 84 cross-reference). All 17 loaded,
all `VERIFY PASS`. Nothing was held back from loading.

Recon evidence: every one of the 17 slugs had **0** `book='GRADUALE'` rows before this run
(each carried exactly 2 pre-existing rows with `assignment_authority_code='MISSAL'`, `book` NULL —
outside the GR loader's scope). **25 July (St James) was NOT pre-loaded**, contrary to the
possibility raised at the start; there was no pre-existing spec anywhere in July to re-read.

---

## 1. Three saints where the GR's date and the DB's date disagree — needs a ruling on the DATA, not the load

The Graduale follows the **general Roman calendar**; `proper_of_saints` follows the **US
calendar**. Three July days therefore resolve wrongly (or not at all) if you go by date.
`resolve_gr_subsection.py --season sanctorale --date` matches on date ONLY, so it silently
hands out the wrong saint. In each case I used the slug that matches the **printed GR title**.

| GR prints | GR date | slug used | `proper_of_saints` date | what the resolver did |
|---|---|---|---|---|
| `S. ELISABETH LUSITANIÆ` | Die 4 iulii | `elizabeth-of-portugal` | **7-5** | `✗ NO proper_of_saints ROW … real calendar gap` |
| `S. ANTONII MARIÆ ZACCARIA, PRESBYTERI` | Die 5 iulii | `anthony-mary-zaccaria` | 7-5 | `✗ AMBIGUOUS` (two saints on 7-5) — picked by title, correct |
| `S. CAMILLI DE LELLIS, PRESBYTERI` | Die 14 iulii | `camillus-de-lellis` | **7-18** | reported `kateri-tekakwitha` as an unflagged **OK** — silently wrong |

- **4 July** is not a calendar gap: `elizabeth-of-portugal` exists, it is unambiguously the same
  saint, and it is otherwise unused (5 July's GR Mass is Zaccaria's). Loaded there. This differs
  from the May Bernardine-of-Siena case, where no row existed at all.
- **14 July** is the dangerous one: the resolver returned `status: OK` with
  `kateri-tekakwitha`. Had I taken it, a complete Camillus Mass would have loaded onto the wrong
  saint with a clean dry-run and a `VERIFY PASS`. Loaded to `camillus-de-lellis`.
  `kateri-tekakwitha` remains at 0 GR rows, which is correct — the GR does not print her.

**For decision:** (a) confirm these three slug picks; (b) decide whether
`proper_of_saints.month_nominal/day_nominal` should carry the GR/general-calendar date, a second
"GR date" column, or stay US-only with the mismatch documented; (c) consider making the resolver
cross-check the GR title against the candidate slug and refuse to emit `OK` on a mismatch.

## 2. `ut supra` / `præter` — NOTHING held this month

Grepped the full text layer of pp. 578–583. **Zero** occurrences of `ut supra`, `Ut in
sollemnitate`, `præter`, or `Cantus ut supra`. Every July Mass prints its own five citations.
The running tally of held Masses is unchanged at **seven** (11 Feb, 8 Mar, 7/13/24 Apr, 3/11 Jun).

## 3. `chant_group` collisions — none in July

One month-wide `v_chant_item` sweep over all 68 distinct gregobase ids: **zero shared
`chant_group_id`s**, so no two chants anywhere in July could collapse under the loader's
option_num-blind dedup. The only multi-option slot in the month is 4 July's introit
(619 vs 544 — distinct groups). Nothing held back. Confirmed at write time: 86 spec chants → 86
rows, all `ROW COUNT: PASS`.

## 4. `gr_index_entry` — no edits made, one harmless typo noted

The month-wide probe spec (71 citations, one dry-run) produced **zero** `ℹ index incipit
mismatch`, zero `⚠ REVIEW`, zero errors, so no index row needed correcting and no re-probe was
required.

One cosmetic OCR typo does exist but does **not** break anything and was deliberately left alone:
`gr_index_entry` row 1673, p218, communio, reads `Mitte manum tuam, et cognose` (for
*cognósce*). The printed citation `Mitte manum tuam` (3 July) is a clean prefix of it and resolves
correctly to gregobase 589. Flagging only so it is not mistaken for a new fault later.

## 5. Editions — all 68 chants are Solesmes/Vatican

Swept `gregobase_chants.version` for every id July loads. One flagged for review and cleared:
**gregobase 3266** (`Sacerdotes ejus(Intr.)`, 30 July introit, p448) has an empty `version`
string. Its header reads `Graduale Romanum, 1974, p. 448` — exactly the cited page. This is the
already-documented `version IS NULL` false positive; correct chant, no action.

Also cleared: the 31 July engraved introit is gregobase **1033**, whose stored incipit is the
ellipsis form `In nomine Jesu...Ps.Domine` — unreachable by the live matcher, but already curated
in `gr_index_entry` for p582, so it resolves `via index`. No spec workaround, no index edit.

## 6. Printed items modelled in `notes` rather than as rows (for the record)

None of these are open questions; listing them so the choices are auditable.

- **Psalm-tone plans** (`cum ps. NNN*`), per the established convention — no row, no `option_txt`:
  3 July CO (`Ps. 117*, …` **and** `vel ps. 115*, …`, two lines), 11 July CO (`cum ps. 111*`),
  13 July CO (`cum ps. 71*`), 26 July CO (`cum ps. 127*, …`).
  Note 3 July's is the richest form seen so far — a full psalm plan **plus** a `vel ps.` alternate
  psalm. It is an alternate PSALM, not an alternate chant, so it emits no row.
- **Printed ellipses in citations**, recorded verbatim in `notes` and truncated in the spec so they
  prefix-match the index: 13 July IN `In virtúte tua... lætábitur rex, 523`;
  15 July OF `Benedíctus es... in lábiis meis, 277`.
- **31 July** `IN. III` — the `III` is the **mode** (left margin), not an option marker. Recorded
  in `notes`; the engraving's `text_src` is the right-justified `Phil. 2, 10. 11; Ps. 8`.
- **Merged OCR blocks**, where two citation lines share one text block and therefore one bbox
  (noted on both rows): 25 July IN+GR; 26 July IN+GR and OF+CO.

## 7. The one alternate chant in the month

**4 July, p578** prints the introit as two lines:

```
IN.   Cognóvi, Dómine, 525.
 —    Dispérsit, dedit, 519.
```

The bare **em-dash** line is a second, real option of the introit, not a continuation. Modelled as
a second `in` row with `option_txt: "—"` (gregobase 544 vs 619, distinct groups). This is the only
Mass in July with six chants. 23 July prints the same formulary **without** the em-dash line and
correctly has five.

## 8. Rank markers — all agree with `lit_epoch.rank_code`, nothing written

Printed markers: `Fest.` 3 Jul, 25 Jul; `Mem.` 11, 15, 22, 26, 29, 31 Jul. All eight already match
the stored `rank_code`. The other nine days print no marker; per the standing ruling, absence is
not evidence and **no rank was inferred or written**. Note p579, p580, p581 and p582 each carry
markers belonging to more than one day — each producer was told explicitly which marker was theirs.

## 9. Boundary checks

- p583's lower half is blank; **p584 opens straight into `AUGUSTUS` / `Die 1 augusti`** (checked by
  image), so no July tail is hidden above the next month's heading — the usual
  split-drops-the-boundary-page hazard does not bite here.
- 31 July genuinely spans **p582 → p583**; the resolver's `printed span` reported `[582 … 583]`
  correctly this time, but the brief was written from `boundary page`/`boundary Y` regardless.

## 10. Housekeeping

`propers-parser/_tmp/iulius/` still holds the seven page PNGs (578–584) and the throwaway
`PROBE-iulius.json`. Deleting `propers-parser/_tmp` is blocked by the permission classifier, so it
is left in place for manual clearing.
