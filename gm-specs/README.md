# Gregorian Missal specs — producer contract

This directory holds **agent-produced JSON specs**, one per liturgical day/Mass from the
Gregorian Missal (Solesmes, 1990). A spec is the input to the deterministic backend
[`load_gm_propers.py`](../load_gm_propers.py), which looks up the matching GRADUALE
`chant_uuid` and writes `lit_part_sources` rows carrying the GM's English vernacular text.

## Context

The GM covers Sundays and Solemnities only. Its chant assignments are always the same as
the Graduale Romanum (GR) for the same day — so rather than re-match to gregobase, the
loader borrows `chant_uuid` from the already-loaded GRADUALE rows. What the GM rows add
that the GRADUALE rows lack is **English vernacular text** (`vernacular_text`) and its
source authority (`translation_source_code='GREGORIAN_MISSAL'`).

**Sections processable today** (GRADUALE rows already loaded):

| GM PDF | lit_epoch_slug | wkday | Notes |
|---|---|---|---|
| `08 Christmas - Mass of the Day.pdf` | `NAT-DAY-00-0-day` | null | No cycle variants |
| `16 2nd Sunday of Lent.pdf` | `TQ-LENT-02-1` | 1 | Tract instead of Alleluia |
| `20 Passion (Palm) Sunday.pdf` | `TQ-HOLYWEEK-00-1` | 1 | **Rite, not a plain Mass** — `palan`/`palproc`/`palan1`/`palan2`/`palhy`/`palre`, then `tr`/`gr2`/`of`/`co`. No Introit, no plain `gr` |
| `21 Holy Thursday.pdf` | `TQ-HOLYWEEK-00-5-supper` | 5 | Evening Mass only (Chrism Mass is a separate epoch). Adds `lotan1`–`lotan7` (mandatum) and `transl` |
| `22 Good Friday.pdf` | `TQ-HOLYWEEK-00-6` | 6 | **No Mass at all** — `gftr`/`gfgr`/`gfecce`/`gfadan`/`gfimp`/`gftris`/`gfhy` only |
| `23 Easter Sunday - Easter Vigil.pdf` | `PASC-OCT-01-1-vigil` | 1 | `vigcan1`–`vigcan7`/`al`/`viglit`/`of`/`vigasp`/`co`(2 options)/`ite`. No Introit, no Gradual. ⚠ Exsultet & *Lumen Christi* have no `service_part` — not loadable |
| `25 2nd Sunday of Easter.pdf` | `PASC-AD_ASC-02` | null | Paschaltide (al1/al, no Gradual) |
| `26 3rd Sunday of Easter.pdf` | `PASC-AD_ASC-03` | null | Paschaltide |
| `27 4th Sunday of Easter.pdf` | `PASC-AD_ASC-04` | null | Paschaltide, no cycle variants |
| `28 5th Sunday of Easter.pdf` | `PASC-AD_ASC-05` | null | Paschaltide |
| `29 6th Sunday of Easter.pdf` | `PASC-AD_ASC-06` | null | Paschaltide, cycle A/B/C on al1/al/co |
| `30 Ascension of the Lord.pdf` | `PASC-ASC-06-5` | null | Leaf-day slug; Communion cycle A/B/C |
| `31 7th Sunday of Easter.pdf` | `PASC-POST_ASC-07` | null | Paschaltide; carries the Ascension-transferred alternate Mass |
| `33 Pentecost Sunday.pdf` | `PASC-PENT-08-1` | 1 | Includes Sequence |
| `48 13th Sunday OT.pdf` | `OT-OT-13` | null | Cycle A/B/C options |
| `54 19th Sunday OT.pdf` | `OT-OT-19` | null | Cycle A/B/C options |
| `55 20th Sunday OT.pdf` | `OT-OT-20` | null | Cycle A/B/C options |

As more GR sections are parsed, add their GM counterparts here.

---

## Reading the GM PDF

**Use the pre-split section PDFs** in `propers-parser/GM/sections/`. Each section is one
liturgical day and includes one buffer page from the next section, so chants that overflow
a TOC boundary (e.g. the Christmas communion) are not truncated.

**Read the PDF directly with the `Read` tool** — no fitz or Python needed. The `Read`
tool renders PDF pages through Claude's native vision, which handles the GM's layout
(part labels, engraved music, English paragraph below) naturally and without text-layer
heuristics. For sections longer than 10 pages provide a `pages` range; most GM sections
are 4–6 pages and can be read all at once.

The last page of every section PDF is the buffer page (the first page of the next
section). It may contain overflow chant content from the current section — read it as
part of the current section and ignore any new-section heading that appears there.

---

## What to capture per chant

For each chant part present on the GM page (Introit, Gradual, Alleluia/Tract,
Offertory, Communion, and Sequence if present):

| Field | What to set |
|---|---|
| `service_part` | `in`/`gr`/`tr`/`al`/`of`/`co`/`seq` |
| `page` | **Required.** GM printed page number where this chant's part-label (e.g. "Introit", "Gradual B") first appears. Stored as `printed_page_num`. For cross-references this is the page where the citation is printed, not where the music is engraved. |
| `vernacular_text` | Full English text of the antiphon + psalm verse, as one string. Include the psalm verse after the antiphon body, separated by `♦` or `. ℟.` as printed. |
| `text_src` | Scripture citation printed above the chant (e.g. `"Is 9:6; Ps 97"`), or null if absent. |
| `cycle_sun` | `1`=anno A, `2`=anno B, `3`=anno C, or `null` for the default (no year label). |
| `gm_xref_page` | For cross-references only (e.g. "Gradual A: Ostende, p. 499"): the GM page where the cited music is engraved. Stored as `ref_page_num`. Omit (or set null) for chants engraved directly on the current page. |
| `option_num` | `1` for the primary chant (default — may be omitted); `2` (`3`, …) for each `"Or:"`/ad-libitum **alternate** of the same part. See "Alternates" below. |
| `option_txt` | The GM's rubric introducing an alternate, verbatim (almost always `"Or:"`). `null`/omitted for the primary. |

Capture only chant-proper text: **skip** Opening Prayer, Prayer over the Gifts, Prayer
after Communion, Preface, readings, and any "Prayer / Collect" blocks — these are easily
distinguished because they have Latin text on the left and English on the right (the GM's
facing-page format for prayers), whereas chant sections have the Latin engraving running
across the full page with English below.

---

## Cycle A/B/C handling

OT Sundays (and a few other days) have multiple graduals or communions, one per lectionary
year. The GM labels these explicitly.

### ⚠ Two INDEPENDENT axes — do not conflate them

Every chant sits on two axes that have nothing to do with each other:

| Axis | Values | Decided by | Fields |
|---|---|---|---|
| **default vs. override** | `cycle_sun=null` vs. `1`/`2`/`3` | the printed **label** (`Gradual A`, `Communion B & C`, unlabelled) | `cycle_sun` |
| **engraved vs. cross-reference** | music on this page vs. a citation `…, p. N` | whether **music is printed here** | `page`, `gm_xref_page` |

**All four combinations are legal.** A week's default can be a cross-reference, and a cycle
override can be engraved. Decide each axis on its own evidence:

- Does the page print **music** for this chant? → engraved: set `page`, omit `gm_xref_page`.
  Only a bare citation (`Esto mihi, p. 493.`)? → cross-reference: set `page` to where the
  citation is printed and `gm_xref_page` to the cited page.
- What does the **label** say? → that fixes `cycle_sun`, regardless of the above.

Real example (9th Sunday OT, loaded 2026-08-14): the communion's `Or:` alternate is a
**default-slot chant** (`cycle_sun=null`, `option_num=2`) that is a **cross-reference**
(`gm_xref_page=596`). Never reason "it's a citation, so it must be a cycle variant."

### Mapping a label to `cycle_sun`

`1`=year A, `2`=B, `3`=C, `null`=the default (the slot the GRADUALE holds at the week slug,
`wkday=null`).

**Confirm every mapping against the GRADUALE inventory by Latin incipit — never by the letter
alone.** Which letters are "the default" varies week to week, and the two genres on a single
page can disagree:

- 8th Sunday OT: "Gradual A & B" is the default + "Gradual C" is the override, but
  "Communion **A**" is the override + "Communion **B & C**" is the default.
- 9th Sunday OT: "Gradual A" is the override, "Gradual B & C" the default.

So a label like "Communion A & B" does **not** reliably mean `cycle_sun=null`, and
"Communion A" does not reliably mean `cycle_sun=1`. Dump the GRADUALE rows for the week
first and match incipit-to-incipit; the director normally hands you this inventory. The
loader zips your entries to those rows and a wrong `cycle_sun` still resolves cleanly to the
**wrong** `chant_uuid` — a clean dry-run will not catch it.

---

## Alternates ("Or:" / ad libitum)

Some parts print a **primary** chant followed by one or more alternates the celebrant may
choose instead, introduced by `Or:` (Latin `Vel ad libitum:` / `Ad libitum:` in the
Graduale). These are **distinct chants with their own text and page** — NOT the same chant,
and NOT year-cycle variants. Example (15th Sunday OT):

- Introit **Dum clamarem** (Ps 54, p. 496) — then `Or:` **Ego autem** (Ps 16, p. 497).
- Communion **Passer invenit** (Ps 83, p. 502) — then `Or: Qui manducat, p. 423` (a
  cross-reference to the engraved chant on GM p. 423).

Emit **one chant entry per option**, all sharing the same `service_part` and `cycle_sun`,
distinguished by `option_num`:

- `option_num: 1` → the primary (`option_txt` null).
- `option_num: 2` (`3`, …) → each alternate, with `option_txt: "Or:"` and its **own**
  `vernacular_text`, `page`, and `text_src`. If the alternate is a cross-reference, set
  `page` to the page where the `"Or: …, p. N"` citation is printed and `gm_xref_page` to
  the cited page `N` (read that page for the English text).

The GRADUALE already stores one row per option (distinct `chant_uuid`s). Each of your entries
binds to the GRADUALE candidate at its own `option_num` (candidates ordered primary-first), and
the loader **errors if the counts differ** — so if a slot's dry-run reports N candidates, supply
N entries. A slot with a single chant just omits `option_num` (defaults to 1), as before.

### When the GM genuinely prints fewer — `gm_omits_options`

The GM is an **abridged** book and sometimes prints fewer options than the Graduale. **Never pad
the spec to satisfy the count** — a fabricated entry dry-runs perfectly cleanly on a chant the GM
never printed, which is exactly the failure this check exists to catch.

Instead: confirm against the page that the GM really prints fewer, then declare it by setting
`"gm_omits_options": true` on any entry of that slot. The loader then loads what you supplied and
prints a loud `⚠ GM OMITS OPTIONS:` line naming the counts and every GRADUALE candidate. Leaving
it undeclared still errors, because the usual cause of a shortfall is a missed option.

Supplying **more** entries than the GRADUALE has is always an error — there is no `chant_uuid` to
borrow for the extras.

```json
{ "service_part": "candan", "page": 607, "gm_omits_options": true,
  "vernacular_text": "Behold, Our Lord shall come with mighty power…", "text_src": "Is 35:4,5" }
```

Real example: GR p539 offers `Vel ant. Lumen cum cant. ut infra.` at the candle-lighting; the GM
(p607) prints only *Ecce Dominus noster* there. 1 entry, 2 GRADUALE candidates, declared.

```json
{ "service_part": "co", "page": 502, "cycle_sun": null, "option_num": 1,
  "vernacular_text": "The sparrow has found herself a home…", "text_src": "Ps 83:4,5" },
{ "service_part": "co", "page": 503, "cycle_sun": null, "option_num": 2, "option_txt": "Or:",
  "gm_xref_page": 423, "text_src": "Jn 6:57",
  "vernacular_text": "He who eats my flesh and drinks my blood, abides in me…" }
```

---

## OT weeks — slug structure

For OT Sundays, set the spec's `lit_epoch_slug` to the **week slug** (e.g. `"OT-OT-19"`)
and `wkday: null`. The loader automatically promotes cycle-specific chants (those with
`cycle_sun != null`) to the day slug `"OT-OT-19-1"` with `wkday=1`, matching the GRADUALE
pattern exactly.

For Lenten Sundays (e.g. 2nd Sunday of Lent), use the **day slug** directly
(`"TQ-LENT-02-1"`) and set `wkday: 1`. No cycle variants are expected there.

---

## Output JSON format

```json
{
  "subsection": "ot-ot-19",
  "label": "19th Sunday in Ordinary Time (Gregorian Missal)",
  "lit_epoch_slug": "OT-OT-19",
  "wkday": null,
  "chants": [
    {
      "service_part": "in",
      "page": 519,
      "vernacular_text": "Remember, O Lord, your covenant...",
      "text_src": "Ps 73:20,19,22,23",
      "cycle_sun": null
    },
    {
      "service_part": "gr",
      "page": 520,
      "vernacular_text": "Remember, O Lord, your covenant and do not forget...",
      "text_src": "Ps 73:20,19",
      "cycle_sun": null
    },
    {
      "service_part": "gr",
      "page": 520,
      "vernacular_text": "Show us your mercy, O Lord...",
      "text_src": "Ps 84:8,2",
      "cycle_sun": 1,
      "gm_xref_page": 499
    },
    {
      "service_part": "gr",
      "page": 520,
      "vernacular_text": "Blessed is the nation whose God is the Lord...",
      "text_src": "Ps 32:12,6",
      "cycle_sun": 3,
      "gm_xref_page": 543
    },
    {
      "service_part": "al",
      "page": 521,
      "vernacular_text": "O Lord, you have been unto us a refuge from age to age.",
      "text_src": "Ps 89:1",
      "cycle_sun": null
    },
    {
      "service_part": "of",
      "page": 521,
      "vernacular_text": "In you have I put my trust, O Lord...",
      "text_src": "Ps 30:15,16",
      "cycle_sun": null
    },
    {
      "service_part": "co",
      "page": 522,
      "vernacular_text": "The bread which I will give is my flesh for the life of the world.",
      "text_src": null,
      "cycle_sun": null
    },
    {
      "service_part": "co",
      "page": 522,
      "vernacular_text": "Blessed is the servant whom the Lord, when he comes, will find to be vigilant...",
      "text_src": null,
      "cycle_sun": 3,
      "gm_xref_page": null
    }
  ]
}
```

---

## Validate before handing back

Run a dry-run to confirm the loader finds all matching GRADUALE rows:

```
C:\Users\johna\liturgio\.venv\Scripts\python.exe ^
  propers-parser/load_gm_propers.py --spec-file propers-parser/gm-specs/<name>.json --dry-run
```

A `LookupError: no GRADUALE row found` means either the GR section hasn't been loaded
yet (check `lit_part_sources` for GRADUALE rows on that epoch slug), or the `cycle_sun`
doesn't match an existing GRADUALE row.

A `⚠ REVIEW` line is not an error — it mirrors a case where the GRADUALE loaded multiple
review-candidate rows for that slot; the GM will have one row per candidate (same as the
GR). No action needed from the producer.

Do not run a real write yourself; the human runs `--limit 1` then the full run after
reviewing the dry-run output.
