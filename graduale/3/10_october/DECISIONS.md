# October (GR `Proprium de Sanctis`, printed pp. 612–618) — decisions & open questions

Run: 2026-09-03, director-owned end-to-end batch.
**18 Masses printed · 17 loaded (92 chants: 4 engraved, 88 cross-reference) · 1 held.**
Every loaded Mass: dry-run clean, full `in`/`gr`/`al`/`of`/`co` set, `VERIFY PASS`.

---

## 1. BLOCKED — SS. Ioannis de Brebeuf et Isaac Jogues (19 Oct) has no `lit_epoch` row

**What the page shows.** GR p617 y424 → p618 y83.7:

> `Die 19 octobris` / `SS. IOANNIS DE BREBEUF ET ISAAC JOGUES, PRESBYTERORUM, ET SOCIORUM,
> MARTYRUM` — `IN. Clamavérunt iusti, 450.` `GR. Anima nostra sicut passer, 453.`
> `AL. Confitémini... et invocáte, 340.` `OF. Lætámini in Dómino, 468.` `CO. Iustórum ánimæ, 470.`

A complete, ordinary five-citation Mass, no rubrics, no options.

**What I did.** Searched `proper_of_saints` AND `lit_epoch` by slug *and* by title for
`%rebeuf%`, `%ogues%`, `%isaac%`, `%orth Am%`, `%artyrs of%` — **nothing**. This is a genuine
calendar gap, not a date shift (unlike Paul of the Cross below, and unlike 4 July's
Elizabeth of Portugal). All five citations resolve cleanly (probe-verified: 788 / 432 / 1192 /
786 / 209), so the Mass is fully parsed and ready — it only lacks a slug to hang on.
No slug invented; the Mass is **held**, unloaded.

**What I need decided.** Whether to create `proper_of_saints` + `lit_epoch` rows for the North
American Martyrs (US calendar: 19 October; the GR here already prints them, so this edition is
not purely general-calendar). If yes, the spec is a five-minute job.

Related standing gaps, unchanged: Bernardine of Siena (20 May), Dedication of St Mary Major
(5 Aug), John Eudes (19 Aug — parsed and ready).

**Correction to the standing gap list:** **Francis of Assisi (4 Oct) is NOT a gap.**
`proper_of_saints` has `francis-of-assisi` at 10-4, `rank_code='MEMORIAL'`, and `lit_epoch` has the
matching node. The Mass loaded normally (5 chants, text_ids 4183–4187). The `gr-sanctorale-rank-markers`
memory lists 10/4 among four dates with no row; that entry is stale and should be dropped.

---

## 2. The book contradicts itself on one page number — Ignatius of Antioch's Alleluia

**What the page shows.** GR p617 prints `AL. Qui séquitur me, 481.` (confirmed at 600 dpi; the
edition's old-style `1` is not an OCR artifact).

**Why that is a problem.** p481 holds **no alleluia at all** — it holds the tractus `Beatus vir`.
The chant meant is the 5th Alleluia of the *Commune Martyrum extra T.P.*, mode II, `Io. 8, 12`:
its `Allelúia.` antiphon is engraved at the **foot of p480** and its verse
`℣. Qui séquitur me, non ámbulat in ténebris…` runs onto the **top of p481**. So p617 cites the
verse page while everything else in the book cites the antiphon page:

- printed back-of-book index, p898 (ALLELUIA): `2 Qui sequitur me . . . . 480`
- every other citation in the GR: p518 (Commune), p548 (Peter Damian), p562 (Pancras),
  p565 (Justin Martyr) — **all print 480**, and all four existing specs use `target_page: 480`.

**What I did.** Loaded with `target_page: 480` (the only resolvable value; 481 raises `LookupError`),
resolving to gregobase 1201, and recorded the deviation verbatim in that row's `notes`
(text_id 4236). I did **not** edit `gr_index_entry` — its 480 is a faithful transcription of the
printed index.

**What I need decided.** Nothing blocking; flagging because `ref_page_num` now stores 480 while the
book prints 481. If provenance should preserve the printed citation instead, say so and I will
revisit — it would need a loader change, since 481 is unresolvable.

*(Note this is the inverse of the `gr-alleluia-index-verse-page` hazard: there the index keys to the
verse page and a spec using the antiphon page mis-resolves. Here the index keys to the **antiphon**
page and it is the Sanctorale citation that names the verse page.)*

---

## 3. Curated-index correction: the Rosary's communion was pointing at a Dominican edition

**What I found.** `gr_index_entry` row **1645** (p614, communio, mode 1, `Florete, flores`) held
`gregobase_id = 7919`, `match_status='resolved'` — and gregobase 7919 is
`version='Dominican'`, `book: Graduale O.P. (Suarez), 1950, p. 582`. A Dominican-rite chant standing
as the engraved communion of a Solesmes *Graduale Romanum* page.

**Why it happened.** Textbook `gregobase-ellipsis-incipit-trap`, face 1. The two Solesmes editions
store ellipsis incipits — `Florete... et date` (104) and `Florete... et collaudate` (995) — which the
loader's prefix matcher can never reach, so the Dominican row's bare stub `Florete` won.

**How I settled it.** By `gabc` underlay against the printed page, not by incipit:

| id | version | book header | text |
|---|---|---|---|
| **104** | Solesmes | Graduale Romanum, **1961, p. 622** | `Florete flores * quasi lilium, et date odorem, et frondete in gratiam : collaudate canticum, et benedicite Dominum in operibus suis.` |
| 995 | Solesmes | Graduale Romanum, 1961, p. 87\*\* | *short form* — omits `et date odorem, et frondete in gratiam` |
| 7919 | Dominican | Graduale O.P. (Suarez), 1950 | same words, Dominican melody |

GR p614 prints exactly 104's text, asterisk placement included.

**What I did.** As `jcost`: `UPDATE gr_index_entry SET gregobase_id=104, match_status='reviewed'
WHERE row_id=1645`. Blast radius checked first and **zero**: no spec mentions `Florete` or cites
p614, and no `lit_part_sources` row held `gregobase:7919`. Re-probed; the Rosary communion now
resolves to 104. (The row was machine-`resolved`, not human-`reviewed`, so this overrides no human
decision — cf. the St Wenceslaus introit, which was correctly *held* because that row was `reviewed`.)

**Ruling wanted:** confirm you are happy with the correction, and with the precedent that a
*machine-resolved* row pointing at a non-Solesmes edition may be repaired in-flight when the `gabc`
matches the printed page verbatim.

---

## 4. Curated-index correction: `æ` dropped to `e` in one incipit

`gr_index_entry` row **1723** (p519, communio) read `Simile est regnum **celorum**`. The printed
back-of-book index (p902, COMMUNIONES) reads `8 Simile est regnum **cælorum** 519`, and the table's
own convention everywhere else expands `æ`→`ae` (13 rows with `cael…` vs 2 stragglers with bare
`cel…`). A genuine OCR slip.

**What I did.** As `jcost`, corrected the incipit to `Simile est regnum caelorum`
(`gregobase_id` 673 and `match_status` untouched). This *removed* a spurious `ℹ index incipit
mismatch` from four specs rather than creating one — `com-sanct-mulier`, `com-sanct-relig` and
`ot-ot-17` (×2) already spelled it `caelorum` and were relying on the single-candidate fallback;
all three were re-dry-run after the edit and now match exactly.

⚠ The typo persists upstream in `propers-parser/gr_index_entries.json` and
`graduale/VALIDATED/gr_chant_index_reviewed.csv`, so an index rebuild would reintroduce it.

**Still outstanding, not fixed (outside October):** row for **p689, antiphona,
`Audivi vocem de celo`** has the same `æ`→`e` slip. Left alone — nothing in this batch cites it.

---

## 5. `subsections_ai.json` mis-transcribes two headings, and the resolver silently drops two Masses

**What I found.** `resolve_gr_subsection.py --season sanctorale --date 10-16` and `--date 10-19`
each returned **one** anchor, not two — even though 16 and 19 October each carry a second Mass.
For 10-16 the resolver handed back a boundary of y446, which silently **swallows** the second Mass;
for 10-19 it reported `✗ NO proper_of_saints ROW` and stopped.

**Cause — not the resolver's code.** `graduale/3/subsections_ai.json` records those two level-1
headings as **`Eadem die`**, while the printed page (checked at 600 dpi on both) reads
**`Eodem die`**:

| file entry | chapter page / y | printed page | what the book actually prints |
|---|---|---|---|
| `Eadem die` | p85, y340.5 | 616 | **`Eodem die`** (S. Margaritæ Mariæ Alacoque) |
| `Eadem die` | p87, y83.7 | 618 | **`Eodem die`** (S. Pauli a Cruce) |

The resolver looks for `Eodem die`, so both entries are invisible to it. 9 October (correctly
transcribed) produced its two anchors fine.

**What I did.** Derived both Masses' anchors from the page myself and briefed them explicitly.
Both loaded correctly (`margaret-mary-alacoque` 4229–4233, `paul-of-the-cross` 4245–4249), and
`hedwig`'s boundary was corrected from the resolver's y446 to the true y340.5.
I did **not** edit `subsections_ai.json` — it is an upstream extraction artifact and editing
provenance files unilaterally is against standing practice.

**What I need decided.** Whether to correct those two `text` values to `Eodem die`. It is a
two-character fix that makes the resolver emit correct anchors for both dates. Until then, **every
month must be checked for this**: grep `subsections_ai.json` for `Eadem` before trusting the
resolver's Mass count against `subsections_ai.json`'s own level-1 entries.

---

## 6. Paul of the Cross — deliberate GR-vs-DB date divergence

The GR prints S. Pauli a Cruce as the second Mass of **19 October** (general Roman calendar);
`proper_of_saints` dates `paul-of-the-cross` to **20 October** (US calendar, which moves it to make
room for the North American Martyrs). Loaded to the slug the **printed title** identifies, per the
standing rule; divergence recorded in the introit's `notes` (text_id 4245). `proper_of_saints` was
**not** "fixed".

Same shape as the already-known 4 / 5 / 14 July conflicts. Running list of GR-vs-DB date
divergences now: 4 Jul, 5 Jul, 14 Jul, **19/20 Oct**.

---

## 7. Multi-option slots — all three verified after the real write

`load_graduale_propers.py` dedups on slot + `chant_group` **ignoring `option_num`**, and a dry-run
cannot reveal a collapse. Pre-flighted every pair with one `v_chant_item` query, then re-checked the
loaded rows:

| Mass | slot | printed | option 1 | option 2 | groups |
|---|---|---|---|---|---|
| Our Lady of the Rosary | `co` | engraved + `Ad libitum :` | `gregobase:104` | `gregobase:1144` | 104 / 1144 |
| Teresa of Avila | all five | `Vel ad libitum :` | 629 / 174 / 208 / 1333 / 1301 | 11 / 1022 / 745 / 143 / 639 | all distinct |
| Luke | `co` | `V vel VI, 438` | `gregobase:1028` | `gregobase:97` | 1028 / 3409 |

No collisions; nothing collapsed; all distinct `chant_uuid`s confirmed in `lit_part_sources`.
**Nothing was held on this hazard in October.**

Note on Luke: `V vel VI` are **option markers** (5th and 6th communio of the *Commune Apostolorum
extra T.P.*), not modes — modelled as two `co` rows exactly like the Matthias precedent (GR p562,
same target page 438). Option VI's spec incipit is extended to the index's full
`Vos qui secuti estis me dicit Dominus` because the shorter form is a prefix of it; the deviation is
in that row's `notes`.

---

## 8. `ut supra` / `præter` sweep — October holds NOTHING on the open question

Grepped the whole month's page text for `ut supra`, `præter`/`praeter`, `Cantus`, `vel`,
`libitum` and bare em-dash continuation lines. **Four hits, all modelled, none held:**

| page | printed | sense | disposition |
|---|---|---|---|
| 615 | `Ad libitum :` + `CO. Ecce Virgo concipiet, 37, cum ps. 44*, ut supra.` | (2) psalm back-reference | modelled normally — second `co` option, plan in `notes` |
| 616 | `Vel ad libitum :` (heads Teresa of Avila's full alternate set) | option rubric | `option_txt` on all five alternates |
| 617 | `CO. Vos qui secuti estis me, V vel VI, 438, cum ps. 30*.` | option markers | two `co` rows |

**No `Cantus ut supra, die N` and no `Ut in sollemnitate … præter :` anywhere in October.**
The running held list is unchanged at **ten Masses**: 11 Feb, 8 Mar, 7 / 13 / 24 Apr, 3 / 11 Jun,
5 / 7 Aug, 8 Sep. No new variant to report.

---

## 9. One benign `ℹ` deliberately left alone

`ℹ index incipit mismatch for of 'Ave, Maria, gratia plena' on p419 — using the page's single
resolved of entry ('Ave, Maria et benedictus')` (Our Lady of the Rosary, text_id 4196).

The GR's own printed index (p899, OFFERTORIA) reads `8 Ave, Maria... et benedictus . . 36, 419`,
against a plain `8 Ave, Maria . . . 630` — i.e. `Ave, Maria et benedictus` is a **faithful
transcription of a deliberate disambiguator**, not an OCR typo. p419 carries exactly one
offertorium, so it resolves correctly to gregobase 843 (Solesmes, Graduale Romanum, mode 8). The
spec keeps the **printed** incipit and explains itself in `notes`. Nothing to fix.

This was the **only** `ℹ` in the entire month after the two index corrections above — the 96-citation
month probe was otherwise silent.

---

## 10. Flagged for visibility only (no action wanted)

- **Simon & Jude's offertory** resolves to gregobase **9185**, tagged `In omnem terram(T.P.)`,
  `Solesmes 1974`, though 28 October is not in Paschaltide. 9185 shares `chant_group` 3360 with the
  non-T.P. Solesmes edition (570) and the edition policy prefers the 1974 print. Per the standing
  user ruling, T.P. variants sharing a group with their non-T.P. counterpart are handled by global
  logic — **not investigated, not "fixed"**.
- **Callistus's gradual** resolves to gregobase **8201** (`Solesmes 1961`) rather than a 1974 print.
  Same `chant_group` (827) as the other editions; correct per `version_rank`. Normal.
- **Rank markers**: all 17 printed markers were checked against `lit_epoch.rank_code` and **all 17
  already agree** — 6 × `Mem.`→`MEMORIAL` (Therese, Guardian Angels, Francis, Rosary, Teresa of
  Avila, Ignatius), 2 × `Fest.`→`FEAST` (Luke, Simon & Jude), 9 blank → `NULL`. **No rank write was
  needed.** Nine October days print nothing in the right margin; per the standing ruling that
  absence is left as `NULL`, never inferred.
- `propers-parser/_tmp/october/` still holds the month's page images, the two 600-dpi zoom crops,
  the index-page renders and the throwaway `probe-october.json`. Deleting `_tmp` is blocked by the
  permission classifier, so it is left in place as usual.
