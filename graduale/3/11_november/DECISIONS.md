# November (GR `Proprium de Sanctis`, printed pp. 619–626) — decisions & open questions

Run: 2026-09-03, director-owned end-to-end batch.
**18 Masses printed · 15 modelled (72 rows: 4 engraved, 68 cross-reference) · 3 not loaded.**
Of the 15: 12 produced and loaded in this run (61 rows), 3 pre-existing and re-read
(`all-saints`, `all-souls-day`, `lateran-basilica`). Every loaded Mass: dry-run clean,
full `in`/`gr`/`al`/`of`/`co` set, `VERIFY PASS`.

Chapter pages 88–95 = printed **619–626**. `subsections_ai.json` level-1 count (18) matches the
resolver's anchor count (18) exactly — **no `Eadem die` typo this month**; both `Eodem die`
entries (16 Nov Gertrude, 23 Nov Columban) are spelled correctly and resolved.

---

## 1. WRONG-SAINT TRAP #1 — 18 Nov resolves `OK` to the wrong saint; the printed feast has no slug

**What the page shows.** GR p623, y383.8 → y=foot:

> `Die 18 novembris` / `IN DEDICATIONE BASILICARUM` / `SS. PETRI ET PAULI, APOSTOLORUM`
> `IN. Sapiéntiam sanctórum, 452.` `GR. Iustórum ánimæ, 457.` `AL. Constítues eos príncipes, 429.`
> `OF. Exsultábunt sancti, 466.` `CO. Iustórum ánimæ, 470.`

A complete, ordinary five-citation Mass. No rubrics, no options, no rank marker printed.

**What the resolver said.** `--season sanctorale --date 11-18` returned
`lit_epoch_slug: rose-philippine-duchesne  [✓]`, `status: OK`. **Unflagged and wrong.** The GR
follows the general calendar (18 Nov = the Dedication of the Basilicas of SS Peter and Paul);
`proper_of_saints` follows the US calendar (18 Nov = Rose Philippine Duchesne). Two entirely
different feasts. Taking the `OK` would have loaded a correct-looking Mass onto the wrong saint,
with a clean dry-run and a `VERIFY PASS`, undetectable afterwards.

**What I did.** Searched `proper_of_saints` AND `lit_epoch` by slug *and* by name for
`%peter%`, `%dedicat%`, `%basilic%`. The only candidates are `ss-peter-paul` (the **29 June**
solemnity — a different feast, already loaded from June) and the `COM-DED*` commons. There is
**no row for the Dedication of the Basilicas**. This is a genuine calendar gap, not a date shift.
No slug invented; the Mass is **held, unloaded**. `rose-philippine-duchesne` was left at zero rows.

The Mass is otherwise fully parsed. All five citations were probe-verified against
`gr_index_entry`, including the two same-page collisions the producer could not have seen:

| part | citation | target page | resolves to | collision on that page |
|---|---|---|---|---|
| in | Sapientiam sanctorum | 452 | gregobase **11** | — |
| gr | Iustorum animae | 457 | gregobase **98** | — |
| al | Constitues eos principes | 429 | gregobase **548** | also `Ego vos elegi` (1030) |
| of | Exsultabunt sancti | 466 | gregobase **33** | also `Anima nostra` (1031) |
| co | Iustorum animae | 470 | gregobase **209** | also `Dico autem vobis` (699), `Et si coram hominibus` (658) |

**What I need decided.** Whether to create `proper_of_saints` + `lit_epoch` rows for the
Dedication of the Basilicas of SS Peter and Paul (18 Nov, general calendar, optional memorial).
If yes, the spec is a five-minute job — the ids above are settled.

---

## 2. WRONG-SAINT TRAP #2 — 23 Nov: the GR prints St Clement I, who has no slug at all

**What the page shows.** GR p624 y250.9 → p625 y206.4 (**two pages**):

> `Die 23 novembris` / `S. CLEMENTIS I, PAPÆ ET MARTYRIS`
> engraved introit, mode **I**, `Dicit Dóminus : * Sermónes mei…` with `Is. 59, 21 et 56, 7; Ps. 111`
> top-right — the engraving runs p624 y≈291 → p625 y≈133 — then
> `GR. Iurávit Dóminus, 486.` `AL. Hic est sacérdos, 449.` `OF. Véritas mea, 483.`
> `CO. Beátus servus, 491, cum ps. 32*.`

**What the resolver said.** `✗ AMBIGUOUS` for 11-23, offering `columban` and `miguel-agustn-pro`.
Neither is Clement. `proper_of_saints` has no `clement` row on any date, and `lit_epoch` has none
either (searched slug and title for `%clement%`). A genuine calendar gap.

**What I did.** Held the Mass, unloaded. No slug invented. The second Mass of 23 Nov
(`Eodem die — S. COLUMBANI, ABBATIS`) *does* match `columban`, and was produced and loaded
normally (5 chants, text_ids 4315–4319).

Note this one is not merely a citation list: it carries the month's **only unmodelled engraved
chant**, `gr_index_entry` row 1015 (p624, introitus, mode 1, `Dicit Dominus : Sermones mei`
→ gregobase **18851**). The four cross-references resolve to 8287 / 1118 / 630 / 1154.

**What I need decided.** Whether to create `proper_of_saints` + `lit_epoch` rows for
**St Clement I, Pope and Martyr** (23 Nov, general calendar, memorial). Note that
`miguel-agustn-pro` (Bl. Miguel Agustín Pro) sits at 11-23 in the DB but is **not** printed in the
GR — so 23 Nov currently has a DB saint the book does not print, and a printed saint the DB
does not have.

---

## 3. HELD (open question) — Elizabeth of Hungary, 17 Nov: `cantus ut supra die 16 novembris`

**What the page shows.** GR p623, y316.8 → y383.8. The whole Mass is ONE line:

> `Die 17 novembris` / `S. ELISABETH HUNGARIÆ, RELIGIOSÆ`  `Mem.`
> `IN. Cognóvi, et alii cantus ut supra die 16 novembris.`

**Classification.** This is sense (1) of the `ut supra` construct — **whole-Mass inheritance**,
the unruled open question, not the ordinary `cum ps. NNN* ut supra` psalm back-reference (sense 2)
and not the same-Mass `AL. <incipit>, ut supra.` back-reference (sense 3). It names a **DAY only —
no page** (`die 16 novembris`), which puts it in the same variant class as
S. Ioannis a Deo (8 Mar, `Cantus ut supra, die 4 martii`) rather than the page-naming variants
(11 Jun) that [[gr-adv-ii-in-ultimis-feriis]] was able to resolve.

Its own wrinkle: it is a **partial** form — it names one chant by incipit (`IN. Cognóvi`, without a
page) and defers `gr`/`al`/`of`/`co` wholesale. 16 Nov carries **two** Masses; the incipit `Cognovi`
identifies the FIRST of them (Margaret of Scotland, `IN. Cognóvi, Dómine, 525.` → gregobase 619),
not Gertrude. So the intended source is unambiguous, but there is still no `lit_epoch_tree` edge
from Elizabeth to Margaret and nothing that makes the inherited chants reachable.

**What I did.** Held the Mass, unloaded, per the standing instruction not to resolve this
question per-month. `elizabeth-of-hungary` remains at 0 rows.
⚠ Note this is a **change from the standing gap list**: the `gr-sanctorale-rank-markers` memory
lists Elizabeth of Hungary (11/17) among four GR days with no `proper_of_saints` row. That is now
**stale** — the row exists (`elizabeth-of-hungary`, `rank_code='MEMORIAL'`, matching the printed
`Mem.`) and so does the `lit_epoch` node. She is blocked by the *construct*, not by a missing slug.

**What I need decided.** Same ruling as the other ten held Masses (11 Feb, 8 Mar, 7/13/24 Apr,
3/11 Jun, 5/7 Aug, 8 Sep) — this is the **eleventh**. Options unchanged: add the
`lit_epoch_tree` edge, copy rows, store the rubric only, or leave the day empty.

**Full `ut supra` / `præter` grep for the month:** exactly two hits over pp. 619–626 —
this one, and All Souls' `Ut infra notatur` (§4). **Zero `præter`.**

---

## 4. RESOLVED — the anomalous single `all-souls-day` GRADUALE row is correct as it stands

**The anomaly.** `all-souls-day` carried exactly **one** `book='GRADUALE'` row (text_id 3203),
which is neither a partial load nor a pointer-line artifact.

**What the page shows.** GR p620, y370.8, in italic, under the heading
`Die 2 novembris / IN COMMEMORATIONE OMNIUM FIDELIUM DEFUNCTORUM`:

> `Ut infra notatur pro Missis defunctorum, 669.`

That is the **entire** entry. No `IN./GR./AL./OF./CO.` lines, and `gr_index_entry` has zero rows on
p620 — so nothing is engraved there either. It is a genuine single-entry Mass: a whole-Mass pointer
at the *chapter* level, to the `Missæ defunctorum` formularies at printed p669.

**How it is modelled.** `part_id=0` (`MASS.all`), `chant_uuid` NULL, `printed_page_num=620`,
`ref_page_num=669`, with the reasoning in `notes`, following the `ADV-II-00-8` precedent
(text_id 2886). I checked for a `-1`/`-2`/`-3` formulary family under `all-souls-day` — **there is
none**, and there is no suffixed sibling slug, so the `--verify` base-slug over-count caveat does
not apply here. The target formulary `missa-pro-defunctis` is already loaded separately (from
GR chapter 5).

**Minor flag, no action taken.** There is **no spec file** for this row —
`propers-parser/graduale/specs/all-souls-day.json` does not exist, so the row cannot be re-verified with the
loader and cannot be idempotently reloaded. Every other November slug has one. Worth creating for
consistency, but I did not invent a spec for a row I did not author.

---

## 5. RE-READ of the two already-loaded 5-row Masses — one genuine omission found and patched

Per the standing rule that already-loaded ≠ already-correct, both were re-read against the page
image and **diffed field by field**, not merely scanned for gaps.

**`all-saints` (1 Nov, pp. 619–620) — ONE omission, matching the known signature exactly.**
p620 prints, in its own text block (y 296.4–317.7) immediately below `CO. Beáti mundo corde, 514.`:

> `Ps. 125*, 1. 2 ab. 2 cd. 3. 4. 5. 6 ab. 6 cd`

This is the documented failure shape: **a psalm plan printed below an engraving that spills onto
the next page, on a page the spec's `co` band never reached** (the band `[293, 304]` excludes the
block's centre at 307.0). Nothing was in the wrong field — `text_src` was correctly NULL — the text
was simply absent. Patched into the `co` chant's `notes` in `specs/all-saints.json`; reloaded
(`updated=5`, `chant_uuid` untouched on all five), `VERIFY PASS`. Row **text_id 3202**.
The rest of the Mass checked out: `in` and `al` engraved (`ref_page_num` NULL), `gr`/`of`/`co`
cross-references to 458/468/514, `text_src` `Ps. 32` / `Mt. 11, 28` on the two engraved chants only.

**`lateran-basilica` (9 Nov, p621) — clean, nothing to patch.** All five are cross-references
(310/336/399/401/370), all `ref_page_num` set, all `text_src` NULL and correctly so (the page
prints no scripture citations and no psalm plan for this day), no notes needed. `VERIFY PASS`.

**Rank note (no action).** All Saints prints **no** rank marker — `OMNIUM SANCTORUM` is set
full-width and leaves no right margin — yet `lit_epoch.rank_code` is already `SOLEMNITY`. That
pre-existing value is correct and was left alone; absence of a marker is typographic here, not
semantic.

---

## 6. Rank markers — cross-check only, no writes needed

Every printed marker already agrees with `lit_epoch.rank_code`:
`Mem.` → MEMORIAL for Borromeo, Leo, Martin of Tours, Josaphat, Elizabeth, Presentation, Cecilia;
`Fest.` → FEAST for the Lateran Basilica and Andrew. The eight days that print **nothing**
(All Saints, All Souls, Martin de Porres, Albert the Great, Margaret, Gertrude, the 18 Nov
Dedication, Clement I, Columban) were left as-is — no NULL was filled from a blank margin.

p621 carries **four** markers and p624 **two**; each producer was given the y of its own and told
to disown the rest. Josaphat's `Mem.` is **merged into his title text block**, not a separate block.

---

## 7. Things that did NOT occur this month (recorded so the next run need not re-derive them)

- **No addendum Mass, no pointer line.** All 18 `Die N` entries are in ascending calendar order
  (1, 2, 3, 4, 9, 10, 11, 12, 15, 16, 16, 17, 18, 21, 22, 23, 23, 30); nothing is printed
  out of sequence at the month's end.
- **No `vel:` / `Ad libitum:` / `Or:` anywhere in the month.** The month's only alternate is an
  **em-dash** one (§8).
- **No `T. P.` / `Tempore paschali` / `Extra tempus paschale` block**, hence no intra-Mass
  `chant_group` collision risk of that shape.
- **No split-PDF boundary loss.** The November split contains all 8 pages 619–626, and printed
  p627 opens straight into `DECEMBER / Die 3 decembris` with no November tail above the heading
  (checked by image, not assumed).
- **No `ℹ index incipit mismatch` and no `⚠ REVIEW` in the whole month.** The 61-citation
  month-wide probe ran once, entirely clean, before any producer was spawned — so no
  `gr_index_entry` row needed curating this month.
- **Version sweep clean.** All 59 distinct gregobase ids the month touches are Solesmes or
  Vatican editions. The one apparent outlier, **3266** (`Sacerdotes ejus`, Josaphat's introit),
  has an empty `version` but a `book:` header reading `Graduale Romanum, 1974, p. 448` — the
  correct chant, and the documented false positive. No ellipsis-incipit trap fired.

---

## 8. Multi-option slots — one in the month, confirmed distinct after the real write

**St Andrew (30 Nov), GR p626** prints, on its own line directly under `CO. Veníte post me, 267.`:

> `—  Dicit Andréas Simóni, 263.`

A bare **em-dash** continuation line, not a `vel`. Modelled as a second `co` row with
`option_txt: "—"`, `target_page: 263`. Pre-flighted as distinct `chant_group`s (552 vs 1021) and
— per the rule that pre-flight is necessary but not sufficient — **re-checked after the real
write**: text_id 4324 → `gregobase:552` (option_num 1), text_id 4325 → `gregobase:1021`
(option_num 2). Distinct `chant_uuid`s, nothing collapsed. `VERIFY PASS` at 6 rows.

That is the month's **only** slot with more than one option — every other Mass is a clean
five-part set.

---

## 9. Psalm-tone plans — six in the month, all recorded in `notes`, none in `text_src`

| day | printed | row |
|---|---|---|
| All Saints (1 Nov) `co` | `Ps. 125*, 1. 2 ab. 2 cd. 3. 4. 5. 6 ab. 6 cd` | 3202 (patched, §5) |
| Charles Borromeo (4 Nov) `co` | `…, 491, cum ps. 131*.` | 4274 |
| Leo the Great (10 Nov) `co` | `…, 491, cum ps. 32*.` | 4279 |
| Martin of Tours (11 Nov) `co` | `Ps. 19*, 2. 3. 4. 5. 6. 7. 8. 9` (own block on p622) | 4284 |
| Columban (23 Nov) `co` | `…, 491, cum ps. 111*.` | 4319 |
| Clement I (23 Nov) `co` | `…, 491, cum ps. 32*.` | *(blocked, §2)* |

In every case `target_page` is **491** (or the page before the plan), never the psalm number, and
`text_src` is NULL — `text_src` is reserved for the right-justified scripture citation, of which
these citation lines print none.

---

## 10. Printed ellipses — three, all kept verbatim

The book itself elides three citation incipits: `OF. Afferéntur… post eam, 505.` (Presentation,
21 Nov), `OF. Afferéntur… próximæ, 504.` (Cecilia, 22 Nov), `AL. Confitémini… et invocáte, 340.`
(Columban, 23 Nov). All three were probe-verified in the month-wide probe **before** briefing:
written as `Afferentur... post eam` / `Afferentur... proximae` / `Confitemini... et invocate`
(three ASCII dots, `æ`→`ae`, no diacritics) they resolve to 768 / 1107 / 1192 respectively,
`via index`, with no mismatch note. The specs therefore keep the printed reading; no
`gr_index_entry` row was touched.

---

## 11. Standing open items — status after November

- **Unchanged gaps:** Bernardine of Siena (20 May), Dedication of St Mary Major (5 Aug),
  John Eudes (19 Aug — parsed and ready), Brebeuf & Jogues (19 Oct — parsed and ready).
  **New this month:** Dedication of the Basilicas of SS Peter and Paul (18 Nov, §1) and
  St Clement I (23 Nov, §2) — both parsed and ready, both needing a slug.
- **GR-vs-DB date/identity conflicts:** 4/5/14 Jul, 19 Oct, and now **18 Nov** and **23 Nov**.
  November's two are *identity* conflicts (a different feast on the same date), not date shifts —
  the saints the DB has at those dates are simply not the ones the GR prints.
- **Removed from the gap list:** Elizabeth of Hungary (17 Nov). She has a row; she is held on the
  `ut supra` question instead (§3). The `gr-sanctorale-rank-markers` memory's four-date gap list is
  now down to Chair of Peter (2/22) and Philip Neri (5/26) — Francis of Assisi was corrected in
  October, Elizabeth here.
- **`subsections_ai.json` `Eadem die` typos (16/19 Oct)** — still unedited, still awaiting a
  ruling. November needed no such fix.
- Unchanged and not re-raised: Immaculate Heart's placeholder date, St Wenceslaus' introit
  (ungrouped-edition hold), Our Lady of Sorrows' printed `Mem.` vs NULL `rank_code`.

---

## 12. Housekeeping

`propers-parser/_tmp/nov/` holds the nine page renders (printed 619–627) and
`propers-parser/_tmp/probe_november.json` the throwaway 61-citation probe spec. **Not deleted** —
deletion of `propers-parser/_tmp` is blocked by the permission classifier, as in previous months.
Nothing in `_tmp` is referenced by any loaded row.
