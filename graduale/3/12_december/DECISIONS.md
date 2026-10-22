# December (`Proprium de Sanctis`, printed pp. 627–639) — decisions & open items

Director run 2026-09-03. 16 printed Masses (`Die 3` … `Die 31`, no `Eodem die`).
14 produced + loaded this run; 1 (`immaculate-conception`) re-read and confirmed already correct;
1 (`Die 6`, S. Nicolai) **held**.

This is the last month of the chapter, so the chapter-wide sweep is recorded here too (§9).

---

## 1. Die 6 decembris — `S. NICOLAI, EPISCOPI` — HELD, no epoch exists

**What the book prints** (p627, y296–389, no rank marker):

```
Die 6 decembris
S. NICOLAI, EPISCOPI
IN. Státuit ei Dóminus, 445.
GR. Invéni David servum meum, 445.
AL. Iustus ut palma florébit, 516.
OF. Véritas mea, 483.
CO. Semel iurávi in sancto meo, 492.
```

A complete, ordinary five-citation memorial Mass. Nothing about the page is unusual.

**What I did.** Searched for a target slug well past the resolver's `✗ NO ROW`:

- `proper_of_saints` — no row at 12-6, and no row anywhere matching
  `slug REGEXP 'nich|nicol|nikol|myra|bari'`.
- `lit_epoch` — no row matching `slug REGEXP 'nich|nicol'` or `title REGEXP 'Nichol|Nicol'`.
- Searched by feast type as well as by name, per the November lesson; no candidate under any date.

All five citations were probed and resolve cleanly (`445→456`, `445→8201`, `516→946`, `483→630`,
`492→317`), so the Mass is fully parseable — the only blocker is the missing epoch.

**What I need decided.** Whether to add a `proper_of_saints` / `lit_epoch` row for St Nicholas
(6 December, general Roman calendar memorial). I did **not** invent a slug. The moment a row
exists this Mass loads in one shot. It joins the six other Masses blocked the same way (§9).

---

## 2. Die 21 decembris — the `thomas` decoy — RESOLVED, nothing was wrong

`proper_of_saints` holds **two** rows at 12-21: `peter-canisius` and `thomas`, so the resolver
returns `✗ AMBIGUOUS`.

**The decoy.** `thomas` does **not** carry 5 GRADUALE rows. It carries exactly **two** rows, both
`assignment_authority_code='MISSAL'` with `book` NULL (text_ids 1027/1028, created 2026-05-15) —
out of GR scope, and therefore *not* a resume pointer. The five GRADUALE rows that make it look
loaded belong to **`thomas-aquinas`** (28 Jan, printed p538, loaded in the January batch): a
`lit_epoch_slug LIKE 'thomas%'` resume query sweeps them in. `thomas-becket` is a third member of
that slug family.

**What I did.** Picked by the printed title — the GR prints `S. PETRI CANISII, PRESBYTERI ET
ECCLESIAE DOCTORIS` — and loaded to **`peter-canisius`**. `thomas` was left untouched.

**Context, for information only.** `thomas` (kind='saint', no GR rows) sits at 12-21, the
**pre-1970** date for St Thomas the Apostle. The GR (1974) prints St Thomas on **3 July**, and the
DB has a separate `st-thomas-apostle` row at 7-3 which carries the July batch's GRADUALE rows. So
`thomas` at 12-21 is a redundant older-calendar entry, not a Mass the Graduale prints.
**Nothing needs deciding to unblock December**, but you may want to rule on whether the `thomas`
12-21 row should exist at all.

---

## 3. Die 12 decembris — GR/DB date conflict — loaded to the printed title

The GR prints `S. IOANNAE FRANCISCAE DE CHANTAL, RELIGIOSAE` at **12 December** (general Roman
calendar). `proper_of_saints` (US calendar) dates **`st-jane-frances-de-chantal` at 12 August**,
and its 12-12 row is **`our-lady-of-guadalupe`** — a feast the GR does not print at all. The
resolver returned a confident `status: OK` on `our-lady-of-guadalupe`; that is the wrong-saint
trap, and taking it would have loaded a clean, verifying, entirely wrong Mass.

**What I did.** Loaded to `st-jane-frances-de-chantal` per the printed title, and confirmed the
GR prints **no `Die 12 augusti`** anywhere, so there is no competing Mass and no clobbering.
The divergence is recorded in the `in` row's `notes`.

**What I need decided (low priority).** Nothing blocks; but this joins the standing list of
GR-vs-DB date conflicts (4/5/14 Jul, 19 Oct) if you want them reconciled centrally rather than
noted per-Mass. I did **not** edit `proper_of_saints`.

## 3b. Die 23 decembris — ambiguous date, settled by title

`holy-family` and `john-of-kanty` both sit at 12-23. The GR prints
`S. IOANNIS DE KETY, PRESBYTERI` → loaded to **`john-of-kanty`**. `holy-family` untouched.
No ruling needed.

---

## 4. Die 8 decembris — `immaculate-conception` re-read — CLEAN, no repair needed

Already carried 5 `book='GRADUALE'` rows (text_ids 3421–3425, loaded 2026-08-28) spanning printed
pp. 628–631. Re-read all four pages and diffed **field by field** against the current conventions,
looking for both known failure shapes.

- **(a) Absent text — not present.** The one item matching the signature (a canticle plan printed
  below an engraving, on a page the spec might not name) is `Cant. Magníficat, Lc. 1, 46-47, 48.
  50. 51. 52. 53. 54. 55` at p631 y151–164. It **is** captured, in the `co` row.
- **(b) Misfiled text — not present.** The plan is in `notes`, not `text_src`. Every `text_src`
  holds exactly the printed right-justified scripture citation (`Is. 61, 10; Ps. 29` /
  `Iudith. 13, 23. V. 15, 10` / `Cant. 4, 7` / `Luc. 1, 28` / `Ps. 86, 3; Luc. 1, 49`).
- Page provenance correct: 628/629/630/630/631, all `ref_page_num` NULL (all five engraved), all
  `option_num=1`. Re-probed all five chants: they still resolve to 622/713/1057/210/1004,
  matching the stored `chant_uuid`s exactly.
- The introit's engraved `Ps. Exaltábo te, Dómine…` verse spills to the top of p629; it is the
  antiphon's own engraved verse, part of chant 622, not a separate plan.

**No action taken and none needed.** Recorded here because "already loaded" was explicitly not
treated as "already correct".

---

## 5. `ut supra` / `ut infra` / `præter` — DECEMBER ADDS NOTHING

Grepped the whole month's text layer and read all 13 page images. **Zero** hits for `ut supra`,
`ut infra` or `præter`. December contributes **no new Masses** to the held set; the running tally
stays at eleven (11 Feb, 8 Mar, 7/13/24 Apr, 3/11 Jun, 5/7 Aug, 8 Sep, 17 Nov).

Two rubric-ish constructs do appear, both on p635 (St Stephen), and **neither is the open
question**:

1. `Ad libitum iuxta codices antiquiores :` / `In virtúte tua, 512.` — an ordinary **second
   offertory option** naming a PAGE. Modelled as a second `of` row, `option_num=2`,
   `option_txt` verbatim, `ref_page_num=512`. Pre-flighted the collision risk: engraved
   `Elegerunt Apostoli` is chant_group 462, `In virtute tua` is chant_group 667 — distinct, so
   the option_num-blind dedup could not collapse them. Confirmed post-write that the two rows
   carry distinct `chant_uuid`s (`gregobase:462` / `gregobase:667`).
2. `T. P. Allelúia.` at the end of the communio — engraved, running on from the antiphon's own
   final text. Emits no row; recorded in the `co` row's `notes`.

No `vel:` and no bare em-dash alternate anywhere in the month (checked every part on every page).

---

## 6. `gr_index_entry` row 1638 — OCR typo fixed in-flight

p637's communio row read **`Exiit sermno`**. The printed page reads `EXiit sermo inter fratres`,
and the printed back-of-book index reads `Exiit sermo` twice (mode 5 graduale, mode 2 communio) —
confirmed by a fitz scan of the INDICES chapter before touching anything. `gregobase_id=781`
(`Exiit sermo(Com.)`, Solesmes) was already correct; only the incipit was wrong.

Blast-radius check first: **no** spec anywhere in `propers-parser/graduale/specs/` used the typo'd
spelling, so the edit is strictly an improvement. Repaired as `jcost`
(`match_status` left at `resolved`, `gregobase_id` untouched), then re-probed: the `ℹ index
incipit mismatch` is gone and `john-the-apostle` resolves by exact match.

⚠ The typo persists in the upstream OCR artifacts (`propers-parser/gr_index_entries.json`,
`graduale/VALIDATED/gr_chant_index_reviewed.csv`), so a rebuild of the index table reintroduces
it. Flagged rather than silently edited. Logged in `maintenance.md`.

---

## 7. `Meditabor (sine alleluia)` on p356 — deliberate, left alone

`peter-canisius`'s offertory prints `Meditábor in mandátis tuis, 356.` and produces a benign
`ℹ index incipit mismatch` because p356's index row carries the curated parenthetical
`Meditabor (sine alleluia)` — the GR's own printed back-of-book index convention, not an error.
p356 has a single offertorium row, so it resolves correctly to gregobase 810 (Solesmes, header
`Graduale Romanum, 1974, p. 356`). The spec keeps the **printed** incipit, matching the existing
precedent in `thomas-aquinas.json`, `com-doct.json`, `com-sanct-mulier.json` and
`immaculate-heart-of-mary.json`. **No index edit** — editing it would break those four specs.

---

## 8. Rank markers — zero writes, as expected

Printed markers in December: `Mem.` on Die 3, 7, 13, 14; `Sol.` on Die 8; `Fest.` on Die 26, 27,
28. Blank margin on Die 4, 6, 11, 12, 21, 23, 29, 31. Every one already agrees with the stored
`lit_epoch.rank_code` (MEMORIAL / SOLEMNITY / FEAST, and NULL where the book prints nothing).
**No rank was written, and no NULL was filled from a blank margin.**

---

## 9. Chapter-wide sweep (`Proprium de Sanctis`, all 12 months)

Printed Masses in the chapter (level-1 headings in `subsections_ai.json`): **189**
(incl. 11 `Eodem die` + 2 mis-transcribed `Eadem die`).
Loaded: **176 Masses / 929 chants** (79 engraved, 850 cross-reference). Zero duplicate slots.

### 9a. The 13 Masses still unloaded, and why

**Blocked on a missing epoch row (7)** — fully parseable, needs a `proper_of_saints` /
`lit_epoch` row before anything can load:

| date | printed title | page |
|---|---|---|
| 20 May | `S. BERNARDINI SENENSIS, PRESBYTERI` | 563 |
| 5 Aug | `IN DEDICATIONE BASILICAE S. MARIAE` | 584 |
| 19 Aug | `S. IOANNIS EUDES, PRESBYTERI` | 593 |
| 19 Oct | `SS. IOANNIS DE BREBEUF ET ISAAC JOGUES…` | 617 |
| 18 Nov | `IN DEDICATIONE BASILICARUM SS. PETRI ET PAULI` | 623 |
| 23 Nov | `S. CLEMENTIS I, PAPAE ET MARTYRIS` | 624 |
| **6 Dec** | **`S. NICOLAI, EPISCOPI`** | **627** | ← new, §1

**Held on the `ut supra` / `præter` ruling (6, fully unloaded)** — 8 Mar `S. IOANNIS A DEO`
(p551), 7 Apr `S. IOANNIS BAPTISTAE DE LA SALLE` (p555), 13 Apr `S. MARTINI I` (p555),
24 Apr `S. FIDELIS DE SIGMARINGEN` (p556), 7 Aug `S. CAIETANI` (p586, `Eodem die`),
17 Nov `S. ELISABETH HUNGARIAE` (p623).

### 9b. Partially-loaded Masses (rows exist, something is still held)

- `our-lady-of-lourdes` (11 Feb) — `in,of` only; the rest inherited via `Ut in sollemnitate …
  præter :`. Open question.
- `the-nativity-of-mary` (8 Sep) — `al` only, same construct. Open question.
- 3 Jun and 11 Jun — same construct, inherited chants unmodelled.
- `st-wenceslaus` (28 Sep) — `gr,al,of,co`; the **introit is held** on the ungrouped-edition
  problem (p523's `match_status='reviewed'` row points at a St-Louis-proper chant while the right
  chant, gregobase 20551 `Solesmes 1974` / `Graduale Romanum, 1974, p. 523`, is ungrouped and
  unreachable by the matcher).

### 9c. Incomplete part sets that are NOT defects (verified, no action)

- **9 Paschaltide Masses** print no Gradual (`in,al,of,co`): 21/23/25/28/29/30 Apr, 1/2/3 May.
- **3 Lenten Masses** print no Alleluia or Tract (`in,gr,of,co`): 17/18/23 Mar.
- `all-souls-day` — a single `MASS.all` row, `chant_uuid` NULL, `ref_page_num=669`: the
  already-modelled whole-Mass pointer (`Ut infra notatur pro Missis defunctorum, 669.`).

### 9d. Carried forward, unchanged

- `subsections_ai.json` still spells `Eadem die` at chapter pp. 85 and 87 (16 / 19 Oct) where the
  page prints `Eodem die`. A two-character fix, **left unedited pending a ruling** — it makes the
  19 Oct second Mass invisible to the resolver and silently extends the 16 Oct boundary.
  December's headings are all correctly spelled and its level-1 count (16) matched the resolver's
  anchor count exactly.
- `all-souls-day` has a loaded row but **no spec file**.
- GR-vs-DB date conflicts: 4 / 5 / 14 Jul, 19 Oct, and now **12 Dec** (§3).
- `immaculate-heart-of-mary` sits at placeholder date 5-31 though the feast is movable.
- `our-lady-of-sorrows` prints `Mem.` while `rank_code` is NULL.

---

## 10. Scratch

`propers-parser/_tmp/dec/` holds the 14 rendered page images (printed 627–640) and the throwaway
month-wide probe spec `_probe_december.json` (81 citations, one dry-run). **Not deleted** —
`_tmp` is parent-owned and deletion is blocked by the permission classifier.
