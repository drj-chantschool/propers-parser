# Gregorian Missal (Solesmes 1990) — intake profile

Book-specific instructions for directors working on `GREGORIAN_MISSAL`. Producers read `PRODUCER.md`.

| | |
|---|---|
| Book code | `GREGORIAN_MISSAL` |
| Master PDF | `GM/gregorian-missal.pdf` (outline present); per-Mass section PDFs under `GM/sections/` |
| Printed-page rule | `books.printed_page_num` = pdf page (718 pages seeded with identity mapping) |
| gregobase source | 16 (Gregorian Missal 1990) |
| Assignment authority | rows keep `GRADUALE`; `translation_source_code='GREGORIAN_MISSAL'`, `book='GREGORIAN_MISSAL'` |
| Text layer | yes (English) |
| Unit model | section (one Mass per producer); chant identity is BORROWED from the GRADUALE rows of the same slot |
| Contract README | `GM/specs/README.md` |
| Producer instructions | `GM/PRODUCER.md` (agent `content-producer`) |
| Loader | `GM/load_gm_propers.py --spec-file … [--dry-run|--reconcile]` |

## Status (2026-10-19)

| Phase | State | Evidence |
|---|---|---|
| 0 Register | ✓ | `p_sources` |
| 1 Page images | ✓ | 718 `books` rows |
| 2 Structure | ✓ | `GM/sections/` (split from the outline; `tools/split_by_outline.py` reproduces it) |
| 3–4 Index | n/a | the GM has no chant index; identity comes from the GRADUALE slot |
| 5 Epochs | ✓ | GR epochs |
| 6 Content | ◐ | 87 specs, 122 slugs; blocked wherever the GRADUALE slot isn't loaded |
| 7 Questions | — | `tools/intake.py list --book GREGORIAN_MISSAL` |
| 8 Sweep | ✗ | |

## Stages (read by /book-batch)

| Stage | Queue | Producer agent | Output | Validate | Load + verify |
|---|---|---|---|---|---|
| content | `GM/queues/content.json` (units = section slugs) | `content-producer` + `GM/PRODUCER.md` | `GM/specs/<section-slug>.json` | `load_gm_propers.py --spec-file … --dry-run` | plain run (or `--reconcile`, below), then re-run `--dry-run`: every row `existing text_id=…` |

## Director instructions

### Before spawning, per section
1. **GRADUALE rows must exist** (the loader borrows their chant_uuids):
   `SELECT COUNT(*) FROM lit_part_sources WHERE lit_epoch_slug LIKE :prefix AND book='GRADUALE'`.
   Zero → block the section and say why. That count also validates the slug (don't query
   `lit_epoch` by a `lit_epoch_slug` column; there is none). ⚠ Scope by `book`, never by
   `assignment_authority_code`: GM rows keep authority `GRADUALE` and would double-count.
2. **Existing GM rows:** `SELECT text_id, printed_page_num FROM lit_part_sources WHERE
   lit_epoch_slug LIKE :prefix AND book='GREGORIAN_MISSAL'`. Rows with `printed_page_num` NULL
   predate page provenance → load with `--reconcile`; rows with pages → already loaded, skip.
   A missing per-day/per-week GM slug is usually "nothing printed there", not backlog — confirm
   against the page before treating a gap as work.
3. Confirm the section PDF exists. Give the producer the slug, `wkday`, PDF path and known quirks
   from the table below.

### Section → slug map (Liturgical Year; ✓ = loaded)

| Section | PDF | lit_epoch_slug | wkday | Notes |
|---|---|---|---|---|
| nat-day | `08 Christmas - Mass of the Day.pdf` | `NAT-DAY-00-0-day` | null | ✓ text_ids 1543–1547 |
| ash-wed | `14 Ash Wednesday.pdf` | `TQ-LENT-00-4` | 4 | ✓ 2674–2681; 3 ASHES-rite chants (`an1`/`an2`/`re`) beyond the 5 propers |
| tq-lent-01 | `15 1st Sunday of Lent.pdf` | `TQ-LENT-01-1` | 1 | ✓ 2682–2686; Tract, no options |
| tq-lent-02 | `16 2nd Sunday of Lent.pdf` | `TQ-LENT-02-1` | 1 | ✓ 2687–2692; Introit "Vel:" alternate |
| tq-lent-03 | `17 3rd Sunday of Lent.pdf` | `TQ-LENT-03-1` | 1 | ✓ 2708–2715; Introit Vel: (xref); Communion 3-way Gospel-conditional (incl. same-text alternate melody) |
| tq-lent-04 | `18 4th Sunday of Lent.pdf` | `TQ-LENT-04-1` | 1 | ✓ 2693–2700; Offertory (2) and Communion (3) Gospel-conditional |
| tq-lent-05 | `19 5th Sunday of Lent.pdf` | `TQ-LENT-05-1` | 1 | ✓ 2701–2707; Communion 3-way, no unconditional default |
| 2nd-easter | `25 2nd Sunday of Easter.pdf` | `PASC-AD_ASC-02` | null | ✓ 2781–2785; `al` lives at the `-1` day slug though cycle_sun is null (loader falls back) |
| 3rd-easter | `26 3rd Sunday of Easter.pdf` | `PASC-AD_ASC-03` | null | ✓ 2786–2791 (+ pre-existing 109); Communion default + A + C |
| 4th-easter | `27 4th Sunday of Easter.pdf` | `PASC-AD_ASC-04` | null | ✓ 2792–2796 |
| 5th-easter | `28 5th Sunday of Easter.pdf` | `PASC-AD_ASC-05` | null | ✓ 2797–2802; Communion default + A |
| 6th-easter | `29 6th Sunday of Easter.pdf` | `PASC-AD_ASC-06` | null | ✓ 2803–2814; al1/al/co all A/B/C; al1 Year C offers the A or B chant (2 options) |
| ascension | `30 Ascension of the Lord.pdf` | `PASC-ASC-06-5` | null | ✓ 2815–2822; leaf day slug; Offertory "Or:"; Communion A/B/C. Vigil epoch `-vigil` has no GRADUALE rows and this PDF has no Vigil |
| 7th-easter | `31 7th Sunday of Easter.pdf` | `PASC-POST_ASC-07` | null | ✓ 2823–2834; carries the transferred-Ascension Mass as "Or:" xref options citing `ascension` / `6th-easter` |
| pentecost-vigil | `32 Pentecost - Vigil.pdf` | `PASC-PENT-08-1-vigil` | null | ✓ 4977–4982; starts mid p391; two Alleluias p393 → `al1` Emitte, `al` Dum complerentur; Introit primary is an xref (p405), its Or: is engraved |
| pentecost | `33 Pentecost Sunday.pdf` | `PASC-PENT-08-1` | 1 | ✓ 2835–2840; Sequence; one Alleluia (no `al1`) |
| ot-ot-13 | `48 13th Sunday OT.pdf` | `OT-OT-13` | null | ✓ 1568–1575 |
| ot-ot-NN | `<NN+35> <NN>th Sunday OT.pdf` | `OT-OT-NN` | null | week slug; cycle A/B/C |

Other sections: find the slug in `lit_epoch`, then the PDF by title. **Advent Sundays use the week
base** `ADV-I-0N` (no cycles). The Feasts folder's 19 PDFs are not 19 Masses: §15–19 are chantless
(prayers only), §14 is a chapter, §13 splits into two epochs. Holy Week sections are rites: ritual
`service_part` codes (`gfgr`, `vigcan2`, `vigasp`…), and COMPLETENESS warnings there are benign; the
Exsultet is not modellable (open). The Funeral Mass (`missa-pro-defunctis`) and Last Farewell
(`EXSEQCOM`, one ritual epoch) are loaded; Dedication is two epochs (`COM-DED-IPSA` / `COM-DED-ALIIS`).

### Review and load
- Re-run the dry-run yourself; every chant `-> chant_uuid=gregobase:<id>`. "N chant(s) here but the
  spec provides M" = wrong option count.
- `⚠ COMPLETENESS` means the producer skipped a part (the GM prints whole Masses) — except Holy
  Week rites and `EXSEQCOM`, where it always false-warns.
- **Proofread `vernacular_text`** — no check reads the English. Fix spec and any loaded row.
- Re-check every `cycle_sun` against the GRADUALE inventory by incipit (the letter alone misleads).
- Load: plain run if no GM rows exist, `--reconcile` to backfill pages on old rows. Then re-run
  `--dry-run`: every row must show `existing text_id=…` (idempotent).

## Known decisions
`GM/specs/README.md` and the `gm-*` memories.
