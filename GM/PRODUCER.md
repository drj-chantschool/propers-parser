# Gregorian Missal — producer instructions

For the `content-producer` agent working on book `GREGORIAN_MISSAL`. Read with the generic rules in
`.claude/agents/content-producer.md`; where they differ, this file wins.

## What you produce

ONE section spec (one Sunday / solemnity / rite section) at `GM/specs/<section-slug>.json`, dry-run
clean against `GM/load_gm_propers.py`. The loader does not identify chants itself: it **borrows each
chant_uuid from the GRADUALE row of the same slot** and writes rows with
`assignment_authority_code='GRADUALE'`, `translation_source_code='GREGORIAN_MISSAL'`,
`book='GREGORIAN_MISSAL'`. Your job is the slot, the option count, the page and the English text.

**Contract:** `GM/specs/README.md` — JSON format, required `page`, cycle A/B/C handling,
cross-references, slugs, validation. **Examples:** `GM/specs/ot-ot-13.json` (a full Sunday with cycle
options and cross-references) and `GM/specs/nat-day.json` (a simple feast). The brief gives your
slug and `wkday`; don't derive them.

## Reading the section

- Section PDFs: `GM\sections\The Liturgical Year\<NN> <Title>.pdf` and
  `GM\sections\Feasts of the Lord and Solemnities of Saints\`. They are small (4–7 pages): **Read
  them directly**, all pages at once (music plus English below). The master `GM\gregorian-missal.pdf`
  is too large for Read; use the section PDFs or `tools/render_page.py --book GREGORIAN_MISSAL <p>`.
- The **last page is a buffer page** (first page of the next section): read it for English that
  overflows from your last chant; take nothing that belongs to the next section.
- `page` = the printed GM page (running header) where each chant's part-label first appears.
- Capture only proper chants. Skip prayers, collects, readings, prefaces (the facing Latin/English
  blocks; chant sections have engraving across the full page with English below).

## Cross-references

- A citation (`Esto mihi, p. 493.`) instead of music: `page` = where the citation is printed,
  `gm_xref_page` = the cited page. Read the cited page for the English. Cited pages are almost
  always in OTHER section PDFs; OT week N ≈ section file N+35, or find it by existing specs' spans:
  ```bash
  for f in GM/specs/ot-ot-*.json; do python -c "import json,sys;d=json.load(open(sys.argv[1]));p=[c['page'] for c in d['chants']];print(sys.argv[1],min(p),max(p))" "$f"; done
  ```
  Confirm the target by its running header. For an xref, check the English against the already
  loaded GM row with the same chant_uuid; the page must match `gm_xref_page`.
- ⚠ **Two independent axes.** The printed LABEL decides `cycle_sun`; whether MUSIC is printed decides
  `page` vs `gm_xref_page`. All four combinations occur (OT 9's communion `Or:` is `cycle_sun=null`
  AND an xref to p596). Never infer one from the other.

## Fields

| Field | Notes |
|---|---|
| `service_part` | `in`/`gr`/`tr`/`al`/`al1`/`of`/`co`/`seq` (`tr` in Lent; `al1`/`al` in Paschaltide) |
| `page` | **Required.** printed GM page of the chant's label |
| `vernacular_text` | full English antiphon + verse, one string — proofread it; nothing else checks it |
| `text_src` | the scripture citation above the chant, or `null` |
| `cycle_sun` | `1`=A, `2`=B, `3`=C, `null` = default |
| `gm_xref_page` | only for cross-references |
| `option_num` / `option_txt` | primary 1 (no text); each `Or:` alternate 2, 3… with `"Or:"` |

- **Cycle labels:** "Gradual A & C" → two entries (`cycle_sun` 1 and 3); a label covering the
  remaining year(s) → `cycle_sun=null`. **Which letters are the default varies by week and even by
  genre on one page** — resolve every label against the GRADUALE inventory by Latin incipit, never by
  the letter (OT 8: "Gradual A & B" is the default, but "Communion A" is the override). A wrong
  `cycle_sun` dry-runs clean on the WRONG chant.
- **Option numbers follow the GRADUALE's slot index.** Where the GM abridges a slot, use gapped
  `option_num` values matching the GRADUALE and declare `gm_omits_options` (see README); sequential
  numbering dry-runs clean on the wrong chant. The loader errors if a slot's option count differs
  from the GRADUALE's without that declaration.
- **Complete:** the week-default set (week slug, no cycle) has `in`, `gr`, `al` (or `tr`), `of`, `co`.
  The GM covers Sundays and solemnities, so a missing genre is your parsing error.
- **Slugs:** OT Sundays use the week slug (`OT-OT-19`, `wkday: null`; the loader promotes cycle chants
  to `-1`). **Advent Sundays use the week base** (`ADV-I-0N`, no cycles), not the `-1` day slug.
  Day-keyed feasts and Lenten Sundays use the day slug with `wkday` per the README.

## Validate

```
set PYTHONUTF8=1
C:\Users\johna\liturgio\.venv\Scripts\python.exe C:\Users\johna\liturgio\propers-parser\GM\load_gm_propers.py --spec-file C:\Users\johna\liturgio\propers-parser\GM\specs\<name>.json --dry-run
```
Clean = every chant `-> chant_uuid=gregobase:<id>`, no `LookupError`/`ValueError`. A slot with
alternates prints `[option k/N …]` per row: check each option's text/page is distinct. "N chant(s)
here but the spec provides M" = wrong option count for that slot.

## Report

The spec path, the full final dry-run, the section PDF(s) read, the page assigned to each chant, how
you handled each cycle label and cross-reference, any REVIEW lines, and "no DB write performed".
