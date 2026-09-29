# MAIUS (Graduale Romanum, Proprium de Sanctis, printed pp. 558–564) — decisions & open items

Batch run 2026-09-03. 15 printed Masses; **14 loaded (85 rows, 5 engraved / 80 cross-reference),
1 blocked**. Every spec VERIFY PASS, idempotent, `ref_page_num` correct.

---

## 1. BLOCKED — 20 May, S. Bernardini Senensis, has no `lit_epoch` (needs a ruling)

**What the page shows.** GR p563, heading `Die 20 maii` (y41.8) / `S. BERNARDINI SENENSIS,
PRESBYTERI`, a complete five-chant Mass, no rank marker printed:

```
IN.  Os iusti meditábitur, 494.
GR.  Iustus ut palma, 510.
AL.  Beátus vir qui suffert, 511.
OF.  Véritas mea, 483.
CO.  Beátus servus, 491, cum ps. 120*.
```

**What I did.** Nothing — no spec, no rows. `resolve_gr_subsection.py --season sanctorale --date
5-20` returns `✗ NO proper_of_saints ROW for this date`, and there is no `lit_epoch` for Bernardine
either (`bernard-of-clairvaux`, 20 **August**, is a different saint and must not be reused). Per the
command doc, a date with no `proper_of_saints` row is a real calendar gap: report, do not invent a
slug.

**What I need decided.** Add `proper_of_saints` (5-20, `bernardine-of-siena`, MEMORIAL in the
current calendar — the GR prints no marker, so do **not** infer the rank from the page) plus the
matching `lit_epoch` under the `SAINTS` parent, then re-run this one Mass. All five target pages are
pre-flighted and resolve: 1374 / 34 / 724 / 630 / 1154. This is the only day of May with nothing
loaded.

---

## 2. RESOLVED (report only) — the movable Immaculate Heart

**What the page shows.** GR p564 y400.9: `Sabbato post dominicam II post Pentecosten` /
`IMMACULATI CORDIS B. MARIÆ VIRGINIS`, five citation lines. It is a **movable** day printed at the
foot of the May chapter, so `--season sanctorale --date` cannot key it (there is no `M-D`).

**How I resolved it.** `proper_of_saints` files it as a placeholder at **month 5, day 31** —
`immaculate-heart-of-mary`, "Immaculate Heart of Mary" — sharing 31 May with
`the-visitation-of-mary`. `lit_epoch` has exactly **one** row matching the title
(`immaculate-heart-of-mary`, kind='saint'). The Latin title `IMMACULATI CORDIS B. MARIÆ VIRGINIS`
maps to it unambiguously and there is no competing candidate anywhere in the table. Loaded at that
slug with `wkday` NULL (the heading's "Sabbato" is a position relative to Pentecost, not a weekday
label on a week formulary).

**What I want noted.** The `proper_of_saints` date **5-31 is a placeholder and is wrong** — the day
is the Saturday after the 2nd Sunday after Pentecost (a movable date in June). It did not affect this
load (the slug, not the date, is the key), but a future date-driven consumer would misplace the
feast. Not fixed here; flagging.

---

## 3. RULED BY THE DIRECTOR (confirm or overturn) — 25 May, "AL. Adducéntur regi, 511." cites a page that does not hold the chant

**What the page shows.** GR p563 y461.1, S. Mariæ Magdalenæ de Pazzi: `AL. Adducéntur regi, 511.`

**What I found.** Printed **p511** (`COMMUNE SANCTORUM ET SANCTARUM`, *Versus alleluiatici*) engraves
only two alleluias — I `Beátus vir qui suffert` (gb 724) and II `Beátus vir qui timet` (gb 765).
There is no `Adducentur` there, in the engraving or in `gr_index_entry`. The chant
`Allelúia. ℣. Adducéntur regi vírgines post eam` is engraved on printed **p500**
(`COMMUNE VIRGINUM`, *Versus alleluiaticus I*, mode III) — `gr_index_entry` row 1283, gregobase 208.
Both pages verified by image from `books(book, printed_page_num)`. A spec with `target_page: 511`
raises `LookupError`; 500 is the only page that resolves, and it is provably the right chant.

**What I did.** Loaded the row with `target_page`/`ref_page_num` = **500** and this note on the row:

> The Graduale prints 'AL. Adducentur regi, 511.' but p511 … engraves only 'Beatus vir qui suffert'
> (I) and 'Beatus vir qui timet' (II) — it holds no Adducentur. The alleluia 'Adducentur regi
> virgines post eam' is engraved on p500 … target_page is recorded as 500, the page that actually
> carries the chant; the printed 511 appears to be a page-number misprint. Flagged for a ruling.

**What I need decided.** Whether recording the *corrected* page (500) with a note is the right
policy for a printed page-number misprint, or whether the project prefers fidelity to 511 (which
would mean the chant cannot be loaded at all). This is the first instance of this shape in the
Sanctorale; a standing rule would help.

---

## 4. HELD BACK — two `ut supra` alleluias collapse under the loader's dedup key

The loader dedups on slot + `chant_group` and **ignores `option_num`**, so two options in one slot
whose chants share a `chant_group` cannot both exist. Two May lines hit this, both the same shape:
the `Extra tempus paschale` block repeats the *same* alleluia already cited in the default block.

| Day | Printed lines | Chant |
|---|---|---|
| 12 May, Nereus & Achilleus, p561 | `AL. Hæc est vera fratérnitas, 460.` (default) and `AL. Hæc est vera fratérnitas, ut supra.` (extra tempus) | one chant, p460, gregobase 32 |
| 14 May, Matthias, p562 | `AL. Ego vos elégi, 429.` (default) and `AL. Ego vos elégi, ut supra.` (extra tempus) | one chant, p429, gregobase 1030 |

**What I did.** One `al` row per Mass (the default-block citation), with the repetition recorded
verbatim in that row's `notes`. Loading a second row would have silently UPDATEd the first at write
time — invisible in a dry-run.

**What I need decided.** Whether the two seasonal uses of one chant should be representable as two
rows (i.e. add `option_num` or `chant_uuid` to `slot_group_matches()`'s dedup key), or whether one
row + note is the intended model. This is the same underlying question as the held-back
`com-sanct-gen` `(T. P. 443)` alternate from GR ch. 2 — a single ruling would settle both.

Note the classification: this `ut supra` is an ordinary **same-Mass page back-reference** ("as cited
six lines above"), *not* the whole-Mass inheritance construct. See §7.

---

## 5. MODELED, worth a look — 14 May Matthias, `CO. … 438, V vel VI.`

**What the page shows.** GR p562 y306.5: `CO. Vos qui secúti estis me, 438, V vel VI.`

**What I found.** The centred roman numerals **V** and **VI** on printed p438
(`COMMUNE APOSTOLORUM EXTRA T.P.`) are **option markers** — the fifth and sixth communio of that
Common — not modes. The two engravings are mode **I** (`Vos qui secúti estis me … tribus Israel`,
Ps. 125*, gregobase 1028) and mode **II** (`… tribus Israel, dicit Dóminus`, Ps. 18*, gregobase 97).
Confirmed by image; `gr_index_entry`'s mode column agrees (1 and 2).

**What I did.** Two `co` rows (option 2 `Extra tempus paschale :`, option 3 `vel VI`), distinct
chant_groups (1028 / 3409) so no collapse. Row 2's spec incipit is the *extended*
"Vos qui secuti estis me dicit Dominus" — the printed stub prefixes **both** index rows, so only the
extended form selects the mode-II setting deterministically. The deviation from the printed stub is
recorded in that row's `notes`; the incipit is match-only and is never persisted.

---

## 6. Index fixes applied (`gr_index_entry`, as `jcost`)

Two OCR typos, each an inserted duplicate letter, both confirmed against the GR's own printed
back-of-book index (`graduale/8/8_indices.pdf`) before editing:

| row_id | page | part | was | now | printed index reads |
|---|---|---|---|---|---|
| 1046 | 559 | introitus | `Exclaamaverunt` | `Exclamaverunt` | `1 Exclamaverunt . . . 559` |
| 1342 | 558 | alleluia | `Fac nos innocuaam` | `Fac nos innocuam` | `8 Fac nos innocuam . 558` |

Row 1342 mattered: p558 carries **two** resolved alleluia rows, so the single-candidate fallback was
unavailable and the printed incipit would have hard-failed. `gregobase_id` and `match_status` were
left alone. No existing spec used either old spelling (grepped `specs/`), so there is no blast radius.
⚠ The typos persist in the upstream OCR artifacts (`propers-parser/gr_index_entries.json`,
`graduale/VALIDATED/gr_chant_index_reviewed.csv`) and a rebuild of the index table would reintroduce them.

---

## 7. `ut supra` / `præter` sweep — nothing added to the open question

Grepped every May page (558–564) for `ut supra` and `præter`:

- **`præter`** — no hits. No `Ut in sollemnitate … præter :` in May.
- **`Cantus ut supra, die N <mensis>.`** (total inheritance, prints no chants) — no hits in May.
  (The first June instance is on p565: `Tempore paschali : Cantus ut supra die 2 iunii pro T. P.` —
  June's problem, not this batch's.)
- **`ut supra`** — two hits, p561 and p562, both `AL. <incipit>, ut supra.` Both are ordinary
  same-Mass back-references to a page cited a few lines above, and both were classified and handled
  in §4 — **not** the whole-Mass inheritance construct.

So **May adds nothing to the running tally of held `ut supra`/`præter` Masses** (still 11 Feb,
8 Mar, 7/13/24 Apr — four Masses across three months).

---

## 8. Benign / cleared, recorded so it is not re-raised

- **`⚠ COMPLETENESS: missing [gr]`** fired for three Masses — **1 May** (Joseph the Worker),
  **2 May** (Athanasius), **3 May** (Philip & James). Cleared against the dpi-220 page images: each
  prints only IN/AL/OF/CO with no Gradual and no `Extra tempus paschale` block (Paschaltide shape).
  No Gradual was invented. The waiver in the loader keys on `PASC-*` slugs, so it cannot fire for
  Sanctorale slugs — this warning will recur for every paschal-season saint.
- **`ℹ index incipit mismatch` — Immaculate Heart `of` `Meditabor in mandatis tuis` on p356.**
  This is the *curated-disambiguator* cause, not an OCR typo: the index deliberately reads
  `Meditabor (sine alleluia)` to separate the non-paschal p356 setting (gregobase 810) from the
  paschal p245 one. p356 has a single offertory, so the fallback resolves correctly. Printed incipit
  kept; `gr_index_entry` deliberately **not** edited.
- **`al` vs `al1`.** No May page prints `Graduale omittitur, et eius loco dicitur` or
  `omissis Graduali et Tractu`, and no day prints two Alleluias in the Gradual's place. Every
  alleluia in May is plain `al`. (1 May's two alleluias are a `Vel :` pair in ONE slot, not the
  Paschaltide al1+al pattern.)
- **Rank markers** printed in May: `Mem.` (2 May Athanasius, 26 May Philip Neri), `Fest.` (3 May
  Philip & James, 14 May Matthias, 31 May Visitation). All five already match `lit_epoch.rank_code`;
  nothing written. Absence of a marker on the other days was **not** treated as evidence of rank.
- **`cum ps. NNN*` psalm plans** recorded in `notes`, never as a target page: 20 May `120*`
  (blocked Mass), 25 May Gregory VII `131*`, 27 May Augustine `32*`, Immaculate Heart
  `9. 4. 5. 10. 11. 12. 13. 14. 15.`, and Philip & James' `Ps. 32*, 1. 2. 3. 6. 12. 13. 18
  (Differentia : f)`.
- **Month tail.** Printed p565 opens straight into the `IUNIUS` heading (y42) with no May content
  above it, so the split PDF's habit of dropping the boundary page cost nothing this month.
- **`propers-parser/_tmp/maius/`** holds the dpi-220 page renders (p558–p565) plus three
  `books`-table page images (p438, p500, p511) used to settle §3 and §5. Deleting `_tmp` is blocked
  by the permission classifier, so it is left in place deliberately.
