#!/usr/bin/env python
r"""
load_graduale_propers.py — Load Graduale Romanum Mass propers into `lit_part_sources`.

WHAT THIS DOES
--------------
Implements the "Revised procedure (v2)" from
`propers-parser/docs/graduale-propers-to-lit_part_sources.md`: for one liturgical
subsection (a day/Mass) it turns the engraved proper chants into `lit_part_sources`
rows (one per chant), with:

  - `chant_uuid`     IDENTIFIES the chant: the matched gregobase chant as a
                     `v_chant_item.chant_item_uid` ('gregobase:<id>'), keyed on
                     incipit + office-part (the chant's KIND, independent of `service_part`
                     — see `office_part` below) + mode. The full Latin text is reached by
                     joining `chant_uuid` -> `v_chant_item`/gregobase.
                     `original_text` is left NULL on purpose — OCR of the engraved text
                     is unreliable and the text already lives in gregobase, so we link
                     instead of copying.
  - `text_src`       the right-justified scripture citation as printed in the 1974 GR
                     (additive data not present in gregobase). NULL when none is printed
                     (e.g. the Christmas Alleluia).
  - `book`/`printed_page_num`  the engraving's location by book + PRINTED page number
                     (the scanner-independent source of truth). The per-scan PDF page (and
                     its dpi=200 image) is looked up via `books(book, printed_page_num)`.
  - `bbox`           the chant's box on the BODY page, computed from the PDF text layer
                     in the dpi=200 page-image pixel space (the space `books` uses).
  - `lit_epoch_slug` + `wkday`  the liturgical assignment (per the subsection spec).

The chant set / identity / count comes from the parsed back-of-book index
(`gr_index_entry`); the body-page vertical bands (for ordering + `bbox`) were located
from the text layer and confirmed by vision (see the docs file). Each chant is described
declaratively (page, part, mode, incipit, citation, y-band).

PRODUCER / BACKEND SPLIT
------------------------
This script is the deterministic BACKEND: given a subsection spec it matches each chant
to gregobase (-> `chant_uuid`), computes the `bbox`, enforces idempotency, and writes.
It does NOT decide which chants are on a page or where they sit — that PRODUCER role is
done per-subsection by an agent that reads the index checklist (`gr_index_entry`) and
locates each chant on its body page (text layer + vision), emitting a JSON spec.

A spec can therefore come from either source:
  * a built-in entry in SUBSECTIONS (used for the bootstrap `nat-day` case), or
  * an agent-produced JSON file via `--spec-file` (the scaling path).

CHANT IDENTITY — CURATED INDEX FIRST, LIVE MATCH AS FALLBACK
------------------------------------------------------------
`resolve_gr_index.py` already resolved the whole back-of-book index to gregobase ids
(`gr_index_entry.gregobase_id`, with `match_status`) once, under the edition policy
(version_rank) and with the hard cases curated by hand. The loader therefore prefers that
pre-resolved id (resolve_via_index): the chant's index row is on the page that engraves
it — its own `page` for an engraved chant, the cited `target_page` for a cross-reference.
Reading the curated id keeps load-time identity consistent with that one-time resolution
(and any human review) and avoids re-running the matcher. It falls back to LIVE matching
(match_gregobase / resolve_xref) only when the curated id is unusable — no index row, an
unresolved row (gregobase_id NULL: status ambiguous/unmatched), an incipit matching
several rows with different ids, or an ungrouped chant with no v_chant_item uid — which
preserves the live matcher's raise / multi-candidate review-queue behavior for exactly
those cases. The dry-run prints `via index` or `via live` per row so the source is plain.

JSON spec format (one subsection per file):
  {
    "subsection": "pasc-oct-fri",                  # slug for logging
    "label": "Easter Octave — Friday (...)",
    "lit_epoch_slug": "...",                       # FK into lit_epoch
    "jurisdiction": "OSB",                         # optional: FK into p_jurisdiction, default
                                                   # "UNIVERSAL". Set this to load into an
                                                   # order/rite-specific calendar (e.g. the
                                                   # Missae Propriae O.S.B. appendix) that reuses
                                                   # the same book/page/bbox machinery but is a
                                                   # separate row family in lit_part_sources.
    "wkday": 6,                                     # calendar weekday (Sun=1..Sat=7) iff the
                                                   # GR labels it (Feria N/Dominica/Sabbato),
                                                   # else null; NOT the slug's seq suffix

    "chants": [
      {
        "page": 220,                               # PRINTED page number the row points at
        "service_part": "in",                      # in/gr/al/tr/of/co/... — the LITURGICAL
                                                   # SLOT this chant fills (drives STORAGE:
                                                   # which lit_part_sources.part_id it writes)
        "mode": 4,                                  # int (omit for a cross-reference)
        "incipit": "Eduxit eos",                   # printed incipit (drives the match)
        "text_src": "Ps. ...",                     # citation top-right, or null
        "band": [ytop_pt, ybot_pt],                # PDF points (text-layer coords)
        "engraved": true,                          # false = cross-reference
        "target_page": 288,                        # xref only: page the chant is engraved on
        "option_txt": "Vel:",                      # optional: alternate-chant marker
        "notes": "…",                               # optional: free-text editorial note written
                                                   # to lit_part_sources.notes (varchar 500).
                                                   # For recording a judgement the page itself
                                                   # does not carry — e.g. a printed rubric this
                                                   # edition gets wrong, and the reasoning for
                                                   # departing from it. Never clobbers an
                                                   # existing note on upsert (see below).
        "cycle_sun": 1,                             # optional: 1=anno A, 2=anno B, 3=anno C
        "office_part": "hy"                         # optional: the chant's actual gregobase
                                                   # KIND, when it's sung in a slot other than
                                                   # its own genre (e.g. a hymn sung *pro GR.*,
                                                   # or a responsory sung *pro Graduali* — set
                                                   # this to whatever `gr_index_entry.section_type`
                                                   # / gregobase `office-part` the page's own
                                                   # heading says it IS, not what slot it fills.
                                                   # Free-form: matched straight through, no
                                                   # allow-list gate — a wrong value simply
                                                   # fails to match downstream. Omit when the
                                                   # KIND coincides with service_part (the norm).
      }
    ]
  }
The `band` is in PDF points (the text layer's native unit), NOT dpi=200 pixels: the agent
reads start-y from `get_text("dict")` block boxes (points) and confirms by vision.
compute_bbox() scales the result to the dpi=200 space `books`/`bbox` use.

Two kinds of chant:
  * ENGRAVED (`engraved: true`): music is on `page`. `band` boxes the engraving; `mode`
    is given; the row's printed_page_num/bbox point at the engraving.
  * CROSS-REFERENCE (`engraved: false`): the page only CITES the chant ("GR. Propitius
    esto, 288."); the music is on `target_page`. The chant's identity (incipit+part+mode)
    is resolved from the index entry on `target_page` (mode is read there, not supplied).
    printed_page_num stays the REFERENCE page, `ref_page_num` records the cited (engraving)
    page the citation points to, and `band` boxes the reference LINE — so a human reviewer
    renders that box to confirm the citation was interpreted correctly. text_src is
    normally null (no citation prints at a reference). (Engraved chants leave ref_page_num
    NULL.)

IDEMPOTENCY / UPSERT (update in place, never duplicate)
-------------------------------------------------------
`lit_part_sources` now has a NULL-safe slot backstop constraint `uq_lps_slot` (added
2026-07-20) over (jurisdiction, lit_epoch_slug, part_id, book, assignment_authority_code,
cycle_sun, cycle_wkday, wkday, wknum_mod_4, wknum_mod_2, translation_source_code, option_num,
chant_uuid) via generated sentinel columns. That key is a SUPERSET of this loader's dedup slot
key, so the loader's own dedup (below) still governs UPSERT-vs-INSERT; the constraint only fires
as a last-resort guard against a genuinely duplicate row. The write is an UPSERT by default. Because other sources/humans may already have
populated rows (and may have picked a specific edition), the match is on the ASSIGNMENT, not
the exact chant: an existing row counts as the same assignment when it shares the SLOT —
(lit_epoch_slug, wkday, part_id, assignment_authority_code, book, cycle_sun, cycle_wkday,
option_num), NULL-safe `<=>` — AND its chant is in the SAME `chant_group` as the loaded chant
(join via `v_chant_item`). `option_num` was ADDED to this key on 2026-09-06 so the loader stops
being narrower than `uq_lps_slot`: without it, two DIFFERENT printed options of one part in one
slot whose chants share a chant_group (two editions of one chant) could not both be loaded — the
second matched the first and silently UPDATEd it, one row short, invisible to `--dry-run`. Then:
  - MATCH  -> UPDATE only the GR-provenance METADATA (text_src, book, printed_page_num,
             ref_page_num, bbox). We do NOT overwrite chant_uuid (the edition choice) or
             original_text (another source's text).
  - NO MATCH -> INSERT.
Matching on chant_GROUP (not chant_uuid) is what makes the legitimate "multiple rows for one
part" patterns safe: several `Vel:`/`or:` alternates and un-collapsed review candidates are
each a DIFFERENT group, so they never match one another and are never clobbered — while a
different EDITION of the same chant (same group) is correctly recognized as the same slot.
Authority is in the key, so rows from OTHER sources (MISSAL text, GREGORIAN_MISSAL, ...) are
never matched or touched. `--skip-existing` restores SKIP-on-match; `--reconcile` is a
deprecated no-op.
  - ALTERNATES — the GR's "Vel:" alternate chant becomes a second row of the same part,
    tagged with `option_txt` (e.g. "Vel:"); primary and alternate differ by chant_uuid.
  - YEAR-CYCLE — a part with per-year propers ("Dom. anno A/C: ...") becomes several rows
    of the same part distinguished by `cycle_sun` (1=A, 2=B, 3=C; null = default).
  - REVIEW CANDIDATES — when an incipit matches several un-collapsed gregobase chant_groups
    (see match_gregobase), the loader writes one row per candidate (distinct chant_uuid)
    for a human to disambiguate, instead of guessing or silently folding.

HOW TO RUN  (always the canonical repo venv)
--------------------------------------------
    PY=C:\Users\johna\liturgio\.venv\Scripts\python.exe

    # Built-in subsection (bootstrap nat-day case):
    # 1. Dry run — extract, match, compute bbox, print rows, write nothing:
    $PY propers-parser/load_graduale_propers.py --subsection nat-day --dry-run

    # 2. Tiny REAL write first (the doc's lesson: exercise one real insert):
    $PY propers-parser/load_graduale_propers.py --subsection nat-day --limit 1

    # 3. The rest (already-written rows are UPDATED in place by the upsert; --skip-existing
    #    to skip them instead):
    $PY propers-parser/load_graduale_propers.py --subsection nat-day

    # Agent-produced JSON spec (the scaling path) — same dry/tiny/full progression:
    $PY propers-parser/load_graduale_propers.py --spec-file specs/pasc-oct-fri.json --dry-run

DB credentials come from the keyring entry ('liturgio-mysql', 'jcost').
"""

import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(_HERE, "graduale", "graduale romanum.pdf")

DEFAULT_BOOK = "GRADUALE"  # `books` PK value (renamed from 'GR' on 2026-06-19).
DPI = 200  # MUST match the DPI used to seed `books` (bbox lives in that pixel space).
SCALE = DPI / 72.0  # PDF points -> dpi=200 pixels.

KEYRING_SERVICE = "liturgio-mysql"
KEYRING_USER = "jcost"
DB_HOST, DB_PORT, DB_NAME = "localhost", 3306, "liturgio"

# Constants written on every GRADUALE row.
ROW_CONSTANTS = dict(
    cycle_sun=None,
    cycle_wkday=None,
    vernacular_text=None,
    original_lang="la",
    vernacular_lang=None,
    assignment_authority_code="GRADUALE",
    translation_source_code=None,
    review_status="draft",
    common_of=None,
    book=DEFAULT_BOOK,
    option_txt=None,  # alternate-chant marker (e.g. "Vel:"); NULL for the primary
    ref_page_num=None,  # xref only: the page the citation points to; NULL when engraved
    notes=None,  # optional per-chant editorial note from the spec; NULL for the norm
)

# --------------------------------------------------------------------------- #
# Subsection specs. Each chant: (page, service_part, mode, incipit, text_src, band)
#   page       page number (printed == PDF, since the PDF has been renumbered)
#   service_part  in/gr/al/tr/of/co/...  the liturgical SLOT (governs storage); usually but
#              not necessarily the same as the chant's gregobase `office-part` KIND — see the
#              per-chant `office_part` override in read_spec_file() for when they diverge.
#   mode       Roman-numeral mode as an int
#   incipit    the printed incipit (for the gregobase match + a sanity check)
#   text_src   the scripture citation printed top-right, or None if none printed
#   band       (ytop_pt, ybot_pt) vertical band on the page (PDF points) enclosing
#              the chant's blocks; the bbox is the union of text blocks centred in it.
# --------------------------------------------------------------------------- #
SUBSECTIONS = {
    "nat-day": {
        "label": "Christmas — AD MISSAM IN DIE (Mass during the Day)",
        "lit_epoch_slug": "NAT-DAY-00-0-day",
        "wkday": None,
        "chants": [
            (47, "in", 7, "Puer natus est nobis", "Is. 9, 6; Ps. 97", (365, 505)),
            (48, "gr", 5, "Viderunt omnes", "Ps. 97, 3 cd-4; V. 2", (205, 505)),
            (49, "al", 2, "Dies sanctificatus", None, (160, 425)),
            (49, "of", 4, "Tui sunt caeli", "Ps. 88, 12 et 15 a", (430, 505)),
            (50, "co", 1, "Viderunt omnes", "Ps. 97, 3 cd", (275, 425)),
        ],
    },
}


def read_spec_file(path):
    """Load an agent-produced JSON subsection spec into the internal spec shape.

    Validates required keys and normalizes each chant dict to the same
    (page, service_part, mode, incipit, text_src, band) tuple the built-in
    SUBSECTIONS use, so build_rows() is agnostic to the spec's origin.
    Raises ValueError on a malformed spec or an unsupported cross-reference chant.
    """
    import json

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    for k in ("label", "lit_epoch_slug", "chants"):
        if k not in data:
            raise ValueError(f"spec {path!r}: missing top-level key {k!r}")
    if not isinstance(data["chants"], list) or not data["chants"]:
        raise ValueError(f"spec {path!r}: 'chants' must be a non-empty list")

    chants = []
    for i, c in enumerate(data["chants"]):
        for k in ("page", "service_part", "incipit", "band"):
            if k not in c:
                raise ValueError(f"spec {path!r} chant[{i}]: missing key {k!r}")
        band = tuple(c["band"])
        if len(band) != 2:
            raise ValueError(
                f"spec {path!r} chant[{i}]: 'band' must be [ytop_pt, ybot_pt]"
            )
        engraved = c.get("engraved", True)
        if engraved:
            # An engraved chant normally prints its mode, so a MISSING 'mode' key is a
            # producer error. But a few chants are genuinely modeless — a recitative on a
            # single pitch with no modal indication (the Palm Sunday versicle "Procedamus in
            # pace", the Good Friday Improperia) — and gregobase stores those with
            # `mode` NULL. Spell that out as an EXPLICIT "mode": null, which the matcher
            # turns into `g.mode IS NULL`. Absent key vs. explicit null keeps the two cases
            # distinguishable, so "I forgot the mode" still fails loudly.
            if "mode" not in c:
                raise ValueError(
                    f"spec {path!r} chant[{i}]: engraved chant needs 'mode' "
                    f"(use an explicit \"mode\": null only for a chant the book prints "
                    f"with no mode at all)")
            mode = None if c["mode"] is None else int(c["mode"])
            target_page = None
        else:
            # Cross-reference ("GR. <incipit>, <target_page>."): mode is resolved
            # from the TARGET page's index entry; band boxes the reference LINE on
            # the reference page (`page`) for human review, not an engraving.
            if c.get("target_page") is None:
                raise ValueError(
                    f"spec {path!r} chant[{i}]: cross-reference chant needs "
                    f"'target_page'")
            mode = int(c["mode"]) if c.get("mode") is not None else None
            target_page = int(c["target_page"])
        cycle_sun = c.get("cycle_sun")
        if cycle_sun is not None and int(cycle_sun) not in (1, 2, 3):
            raise ValueError(
                f"spec {path!r} chant[{i}]: cycle_sun must be 1 (anno A), 2 (anno B), "
                f"3 (anno C), or null")
        # Per-chant weekday assignment (for ferial options in a whole-week spec). A chant
        # may carry its own `wkday` (calendar weekday Sun=1..Sat=7, from a printed
        # `Feria N`) and `cycle_wkday` (weekday two-year cycle: Anno I=1, Anno II=2). When
        # `wkday` is omitted/null the chant inherits the subsection-level wkday.
        ch_wkday = c.get("wkday")
        if ch_wkday is not None and int(ch_wkday) not in (1, 2, 3, 4, 5, 6, 7):
            raise ValueError(
                f"spec {path!r} chant[{i}]: wkday must be 1 (Dominica)..7 (Sabbato) or null")
        # `wkdays`: an "In feriis" ferial default that applies to SEVERAL weekdays at once
        # (e.g. [2,3,4,5,6] — Mon–Fri, when Sabbato has its own proper). The loader expands
        # it to one row per weekday. Mutually exclusive with the single `wkday`.
        ch_wkdays = c.get("wkdays")
        if ch_wkdays is not None:
            if (not isinstance(ch_wkdays, list) or not ch_wkdays
                    or any(int(w) not in (1, 2, 3, 4, 5, 6, 7) for w in ch_wkdays)):
                raise ValueError(
                    f"spec {path!r} chant[{i}]: wkdays must be a non-empty list of 1..7")
            if ch_wkday is not None:
                raise ValueError(
                    f"spec {path!r} chant[{i}]: give either 'wkday' or 'wkdays', not both")
            ch_wkdays = [int(w) for w in ch_wkdays]
        cycle_wkday = c.get("cycle_wkday")
        if cycle_wkday is not None and int(cycle_wkday) not in (1, 2):
            raise ValueError(
                f"spec {path!r} chant[{i}]: cycle_wkday must be 1 (Anno I), 2 (Anno II), "
                f"or null")
        # `office_part`: the chant's gregobase office-part / gr_index_entry section_type KIND —
        # what the book's OWN heading/subheading says this chant IS — when it differs from its
        # liturgical USE (`service_part`, the slot it fills). Usually omitted (they coincide);
        # set it for a chant used in a slot other than its own genre — e.g. the "Benedictus es"
        # hymn sung *pro GR.* (service_part 'gr', office_part 'hy'), or a responsory sung *pro
        # Graduali* (service_part 'gr', office_part 're'). Passed straight through to the
        # matcher — no allow-list here: office_part identifies a chant by matching gregobase's
        # own KIND classification (or gr_index_entry's section_type), which is a much larger
        # vocabulary than the handful of Mass-service-part codes this loader writes, and a wrong
        # value simply fails to match downstream (LookupError / zero index rows) rather than
        # needing to be pre-approved here.
        office_part = c.get("office_part")
        # `option_txt` holds the printed rubric that introduces this option — usually a short
        # marker ("Vel:", "Ad libitum:"), but a Gospel-conditional or regional rubric can be a
        # full sentence, so the column was widened to varchar(512) (2026-08-15). Length-checked
        # here so an over-long string fails at spec-read time instead of blowing up mid-load
        # with a MySQL 1406, which would leave the spec's earlier rows already committed.
        opt_txt = c.get("option_txt")
        if opt_txt is not None and len(opt_txt) > 512:
            raise ValueError(
                f"spec {path!r} chant[{i}]: option_txt is {len(opt_txt)} chars, max 512 — "
                f"option_txt is the rubric the page prints before this option; an editorial "
                f"comment of your own belongs in `notes` instead")
        # `notes`: free-text editorial note for lit_part_sources.notes — the place to record a
        # judgement the page does not carry (e.g. this edition mis-files a chant under a rubric
        # and the load deliberately departs from it). Length-checked here because the column is
        # varchar(500) and MySQL would otherwise truncate/error deep in the write.
        ch_notes = c.get("notes")
        if ch_notes is not None:
            if not isinstance(ch_notes, str) or not ch_notes.strip():
                raise ValueError(f"spec {path!r} chant[{i}]: notes must be a non-empty string")
            ch_notes = ch_notes.strip()
            if len(ch_notes) > 500:
                raise ValueError(
                    f"spec {path!r} chant[{i}]: notes is {len(ch_notes)} chars, max 500")
        # `unmatched`: an EXPLICIT declaration that this chant has no counterpart in
        # gregobase at all, so the row is written with `chant_uuid` NULL and no matching is
        # attempted. This is not a fallback for a failed match — a LookupError still means
        # the spec is wrong (bad incipit/part/page, or an ungrouped edition to fix at the
        # source; see the `office_part` notes above). It exists for music the corpus
        # genuinely lacks, e.g. the responsorial psalms composed for the 1974 Ordo
        # Exsequiarum (GR p681-683), which gregobase does not carry in any edition.
        # Because such a row has no chant_uuid, it also has no text via the chant link, so
        # `original_text` is REQUIRED: it carries the printed text and is what makes the row
        # identifiable (and what dedup keys on — see slot_group_matches).
        unmatched = bool(c.get("unmatched", False))
        original_text = c.get("original_text")
        if unmatched:
            if not isinstance(original_text, str) or not original_text.strip():
                raise ValueError(
                    f"spec {path!r} chant[{i}]: an \"unmatched\": true chant needs a "
                    f"non-empty 'original_text' — with no chant_uuid there is no other "
                    f"way to know what the row records, and dedup keys on it")
            original_text = original_text.strip()
            if not engraved:
                raise ValueError(
                    f"spec {path!r} chant[{i}]: 'unmatched' applies to an engraved chant "
                    f"the corpus lacks; a cross-reference resolves on the TARGET page, so "
                    f"an unmatched xref means the target page or incipit is wrong")
        elif original_text is not None:
            raise ValueError(
                f"spec {path!r} chant[{i}]: 'original_text' is only for an "
                f"\"unmatched\": true chant — a matched chant's text comes from chant_uuid")
        chants.append(dict(
            page=c["page"], service_part=c["service_part"], mode=mode,
            incipit=c["incipit"], text_src=c.get("text_src"), band=band,
            target_page=target_page, engraved=engraved,
            unmatched=unmatched,          # no gregobase counterpart -> chant_uuid NULL
            original_text=original_text,  # required iff unmatched; else None
            office_part=office_part,  # gregobase KIND override (e.g. 'hy' pro-GR); usually None
            option_txt=c.get("option_txt"),  # alternate marker ("Vel:"), or None
            notes=ch_notes,                  # editorial note -> lit_part_sources.notes, or None
            cycle_sun=(None if cycle_sun is None else int(cycle_sun)),  # 1=A/2=B/3=C year
            wkday=(None if ch_wkday is None else int(ch_wkday)),        # ferial: Feria N
            wkdays=ch_wkdays,                                          # "In feriis": many ferias
            cycle_wkday=(None if cycle_wkday is None else int(cycle_wkday)),  # Anno I/II
        ))

    return {
        "label": data["label"],
        "lit_epoch_slug": data["lit_epoch_slug"],
        "wkday": data.get("wkday"),
        "jurisdiction": data.get("jurisdiction", "UNIVERSAL"),
        "chants": chants,
    }


# section_type (full Latin word in gr_index_entry) -> service_part code.
SECTION_TYPE_TO_PART = {
    "introitus": "in", "graduale": "gr", "alleluia": "al", "tractus": "tr",
    "offertorium": "of", "communio": "co", "sequentia": "seq",
}

# liturgio service_part code -> gregobase `office-part` code, for the few codes that are
# ALWAYS one fixed kind by definition (not a per-chant USE that can vary): gregobase codes
# sequences 'se' where liturgio's service_part code is 'seq'; the Paschaltide
# gradual-replacement Alleluia 'al1' is engraved/indexed as an ordinary 'al'; the ASHES
# sub-rite's 'an1'/'an2' (first/second ash-imposition antiphon) are always antiphons ('an').
# This is NOT a claim that service_part and office-part are generally the same (they are
# independent vocabularies — USE vs. KIND) — it is a deterministic, verified mapping for
# codes that have no other possible kind. A chant whose KIND genuinely diverges from what
# its service_part would suggest (e.g. an introit gregobase catalogs as an antiphon, or a
# hymn sung *pro GR.*) still needs a per-chant `office_part` override in the spec.
# Also: the overflow Mass slots 'gr2'/'tr2' (a second gradual/tract — e.g. Palm Sunday's
# "Christus factus est" sung after the tract) are still a graduale/tractus by kind, and each
# PALMS sub-rite slot has exactly one possible kind (antiphons; the "Procedamus in pace"
# versicle 'or'; the hymn "Gloria laus et honor" 'hy'; the responsory "Ingrediente Domino" 're').
GREGOBASE_OFFICE_PART = {
    "seq": "se", "al1": "al", "an1": "an", "an2": "an",
    "gr2": "gr", "tr2": "tr",
    "palan": "an", "palan1": "an", "palan2": "an",
    "palproc": "or", "palhy": "hy", "palre": "re",
    # CANDLES sub-rite (Presentation of the Lord, GR p539-543 AD PROCESSIONEM CANDELARUM).
    # Structurally the twin of PALMS, down to sharing the 'Procedamus in pace' versicle
    # (gregobase 9119, office-part 'or', modeless) with palproc.
    "candan": "an", "candan1": "an", "candan2": "an", "candan3": "an",
    "candproc": "or", "candre": "re",
    # LOTIO sub-rite (Holy Thursday washing of feet, GR p164-167): seven numbered antiphons.
    **{f"lotan{i}": "an" for i in range(1, 8)},
    # GOODFRIDAY service (GR p172-184). 'im' is gregobase's own Improperia office-part, which
    # holds both the Reproaches (Popule meus) and the Trisagion (Hagios o Theos / Sanctus Deus).
    # 'gfco' is deliberately absent: the GR prints no proper communion chant for Good Friday,
    # only "Durante communione, fieri potest cantus aptus", so nothing should resolve into it.
    "gftr": "tr", "gfgr": "gr", "gfecce": "an", "gfadan": "an",
    "gfimp": "im", "gftris": "im", "gfhy": "hy",
    # VIGIL sub-rite (Easter Vigil, GR p185-195): the seven canticles after the Old Testament
    # readings are engraved/indexed as tracts; 'su' is gregobase's office-part for the Litany
    # ("Litaniae in Vigil. pasch.", cg 457); the aspersion antiphon is a plain antiphon.
    **{f"vigcan{i}": "tr" for i in range(1, 8)},
    "viglit": "su", "vigasp": "an",
    # The paschal dismissal engraved at GR p195 is gregobase office-part 'or'.
    "ite": "or",
    # EXSEQVIG sub-rite (De vigilia pro defuncto, GR p678-680): three antiphons sung with
    # their psalms. Each is printed under an "AN." label and indexed as section_type
    # 'antiphona', so the slot's KIND is antiphon by definition — no per-chant override.
    "vigan1": "an", "vigan2": "an", "vigan3": "an",
    # EXSEQPRE sub-rite (Ad processionem ad ecclesiam, GR p686-691): the six chants under the
    # printed subheading "ANTIPHONAE CUM PSALMIS", numbered I-VI, each with a mode letter in
    # the left margin and an 'antiphona' row in gr_index_entry. Antiphons by definition.
    # NB the SLOT's kind being 'an' does not settle any one chant's edition: prean6
    # ("Qui exspectant Dominum") exists in gregobase only as a Graduale Simplex OFFERTORY
    # (15499, office_part 'of'), so that chant carries a per-chant `office_part` override in
    # the spec, which takes precedence over this dict. See the specs README.
    # The section's two responsorial psalms (preps1/preps2) are deliberately ABSENT: they load
    # as "unmatched", which skips resolution entirely, so an entry here would assert a KIND
    # nobody has verified.
    "prean1": "an", "prean2": "an", "prean3": "an",
    "prean4": "an", "prean5": "an", "prean6": "an",
    # EXSEQCOM sub-rite (Ad ultimam commendationem et valedictionem, GR p692-698). Two printed
    # groups, each fixed in kind: six numbered RESPONSORIES (gregobase office-part 're') and,
    # under the subheading "ANTIPHONAE", three numbered antiphons ('an').
    "comre1": "re", "comre2": "re", "comre3": "re",
    "comre4": "re", "comre5": "re", "comre6": "re",
    "coman1": "an", "coman2": "an", "coman3": "an",
    # EXSEQPRC sub-rite (Ad processionem ad coemeterium, GR p698-702): five numbered antiphons
    # with psalms, under the printed subheading "ANTIPHONAE CUM PSALMIS".
    # NB coeman1 ("Aperite mihi portas iustitiae") carries a per-chant office_part:'in' override
    # in the spec — gregobase has it only as 15642 (Graduale Simplex, an INTROIT) — which takes
    # precedence over this dict. The slot is still an antiphon; the edition is what differs.
    "coeman1": "an", "coeman2": "an", "coeman3": "an", "coeman4": "an", "coeman5": "an",
    # EXSEQST3 sub-rite (Statio tertia : ad sepulcrum, GR p703-704 — the end of the book's
    # Liturgia defunctorum): two numbered antiphons with psalms, again under "ANTIPHONAE CUM
    # PSALMIS".
    "sepan1": "an", "sepan2": "an",
}


def gregobase_office_part(service_part):
    return GREGOBASE_OFFICE_PART.get(service_part, service_part)


# section_type (gr_index_entry) -> gregobase `office-part` code, for resolving the index
# to gregobase chants. Broader than SECTION_TYPE_TO_PART (the liturgio service_part used
# when WRITING lit_part_sources): it also covers antiphons/hymns/psalms, which gregobase
# carries (codes 'an'/'hy'/'ps') even though they have no liturgio Mass service_part.
SECTION_TYPE_TO_GREGOBASE = {
    "introitus": "in", "graduale": "gr", "alleluia": "al", "tractus": "tr",
    "offertorium": "of", "communio": "co", "sequentia": "se",
    "antiphona": "an", "hymnus": "hy", "psalmus": "ps",
}


def _chant_to_dict(c):
    """Normalize a built-in 6-tuple chant into the canonical engraved-chant dict.
    (read_spec_file already emits dicts; this only adapts the in-code SUBSECTIONS.)"""
    if isinstance(c, dict):
        return c
    page, part, mode, incipit, text_src, band = c
    return dict(page=page, service_part=part, mode=mode, incipit=incipit,
                text_src=text_src, band=tuple(band), target_page=None,
                engraved=True, option_txt=None, cycle_sun=None,
                wkday=None, wkdays=None, cycle_wkday=None,
                unmatched=False, original_text=None)


def condense(s):
    """Canonicalize an incipit for whitespace/punctuation/orthography-insensitive
    comparison: lowercase, strip a bare verse/response marker, drop all
    whitespace+punctuation, and fold classical vs medieval Latin letterforms j->i and
    v->u. Absorbs OCR spacing ('Eduxiteos' == 'Eduxit eos'), index punctuation
    ('Domine, Dominus' == 'Domine Dominus'), and the I/J + U/V split between sources
    ('Iacta' (index) == 'Jacta' (gregobase)). It also removes a standalone verse/response
    marker (V./℣./℟.) so the index's 'Haec dies V Benedictus' matches the producer's
    'Haec dies Benedictus' — that bare 'V' is a letter, so without this it would fold to
    'u' and break the match (it must be stripped while spaces still delimit it). Folding
    only ever merges letterforms, and part+mode (and, for xrefs, target page) keep the
    candidate set narrow, so it does not introduce false matches in practice."""
    s = _VERSE_MARKER.sub(" ", (s or "").strip().lower())
    s = re.sub(r"[\W_]+", "", s, flags=re.UNICODE)
    return s.translate(_LATIN_FOLD)


_LATIN_FOLD = str.maketrans("jv", "iu")
# A standalone verse/response marker (V./℣./℟.) — a single letter delimited by spaces or
# string ends, not the first letter of a word ('Vidi', 'Vir'). Stripped by condense().
_VERSE_MARKER = re.compile(r"(?<![^\s])[v℣℟]\.?(?![^\s])")


def load_part_ids(conn):
    """Map service_part.part_code -> part_id (lit_part_sources.part_id replaced the
    old service_part VARCHAR column on 2026-06-19; the spec still uses part codes)."""
    from sqlalchemy import text as sa_text
    return {code: pid for pid, code in conn.execute(sa_text(
        "SELECT part_id, part_code FROM service_part"))}


def make_engine():
    import keyring
    from sqlalchemy import create_engine

    pw = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if not pw:
        raise RuntimeError(
            f"No keyring password for ({KEYRING_SERVICE!r}, {KEYRING_USER!r})"
        )
    url = f"mysql+mysqlconnector://{KEYRING_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url)


_PAGE_MAPPING_CANDIDATES = (
    os.path.join(_HERE, "graduale", "page_mapping.json"),
    os.path.join(_HERE, "graduale", "APPLIED", "page_mapping.json"),
)
_printed_to_pdf_page_cache = None


def printed_to_pdf_page(printed_page):
    """Translate a PRINTED Graduale page number to its 1-based PDF page index.

    Below ~p378 the two coincide, but unnumbered plates inserted later in the
    book (Communia p392+, Proprium de Sanctis p529+, ...) shift PDF pages ahead
    of their printed number by a growing, non-constant offset (e.g. printed 434
    is PDF page 432; printed 585 is PDF page 582). `graduale/page_mapping.json`
    (built by pdf_page_mapper.py, keyed pdf_page->printed_page) is the
    calibrated source of truth; invert it here rather than assuming identity.
    """
    global _printed_to_pdf_page_cache
    if _printed_to_pdf_page_cache is None:
        for path in _PAGE_MAPPING_CANDIDATES:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    mapping = json.load(fh)["mapping"]
                _printed_to_pdf_page_cache = {
                    str(printed): int(pdf_str) for pdf_str, printed in mapping.items()
                }
                break
        else:
            raise FileNotFoundError(
                "page_mapping.json not found in any of: "
                + ", ".join(_PAGE_MAPPING_CANDIDATES)
            )
    pdf_page = _printed_to_pdf_page_cache.get(str(printed_page))
    if pdf_page is None:
        raise LookupError(f"no PDF page mapped for printed page {printed_page!r}")
    return pdf_page


def compute_bbox(doc, pdf_page, band):
    """Union of text blocks centred in `band` on PDF page `pdf_page` (1-based), in dpi=200 px space.

    Returns 'x0,y0,x1,y1' (ints) or None if no blocks fall in the band.
    """
    ytop, ybot = band
    pg = doc[pdf_page - 1]
    xs0 = ys0 = xs1 = ys1 = None
    for b in pg.get_text("dict")["blocks"]:
        if "lines" not in b:
            continue
        bx0, by0, bx1, by1 = b["bbox"]
        cy = (by0 + by1) / 2.0
        if not (ytop <= cy < ybot):
            continue
        xs0 = bx0 if xs0 is None else min(xs0, bx0)
        ys0 = by0 if ys0 is None else min(ys0, by0)
        xs1 = bx1 if xs1 is None else max(xs1, bx1)
        ys1 = by1 if ys1 is None else max(ys1, by1)
    if xs0 is None:
        return None
    return "{},{},{},{}".format(
        round(xs0 * SCALE), round(ys0 * SCALE),
        round(xs1 * SCALE), round(ys1 * SCALE),
    )


_PAREN = re.compile(r"\(.*?\)")  # any parenthetical incipit suffix
# A parenthetical is SEASONAL (restricts the chant to a season — deprioritize it when the
# target is not that season) vs a mere part-label like "(Grad.)"/"(Comm.)" (ignore it).
_SEASONAL_PAREN = re.compile(r"t\.?\s*p\.?|pasch|advent|\badv\b|quadr|temp\.?\s*pasch", re.I)


def _seasonal_paren(raw):
    """True if `raw`'s incipit carries a seasonal parenthetical (e.g. '(T.P.)')."""
    return any(_SEASONAL_PAREN.search(inner) for inner in re.findall(r"\(([^)]*)\)", raw or ""))


def version_rank(version):
    """Edition preference (lower = better), per the project's chant-version policy:
    Solesmes 1974 > Solesmes 1961 > generic 'Solesmes' (no year) > Vatican >
    other-year Solesmes (1934, 1935, 1983, 2000s, ...) > everything else (Dominican,
    Palmer & Burgess, Offertoriale, Finlandiae, ...). Tolerant of the version-string
    typos in gregobase ('Solemes', 'Solsmes', ...)."""
    v = (version or "").strip().lower()
    is_sol = ("sole" in v) or ("solem" in v) or ("solsm" in v)
    if is_sol:
        if "1974" in v:
            return 0
        if "1961" in v:
            return 1
        if not re.search(r"\d{4}", v):  # generic 'Solesmes' (no year)
            return 2
        return 4                         # other-year Solesmes — below Vatican
    if v.startswith("vatic"):
        return 3
    return 5


def _incipit_quality(cand_incipit, target):
    """(seasonal, distance) for ranking a candidate's incipit against the target,
    lower = better. `seasonal` flags a seasonal parenthetical the target lacks (e.g.
    '(T.P.)' = Eastertide — deprioritized so it does not win outside its season; a plain
    label like '(Grad.)' is NOT penalized). `distance` is 0 for an exact (paren-stripped)
    match, else the length gap of a prefix match; None = not a match."""
    raw = cand_incipit or ""
    seasonal = 1 if _seasonal_paren(raw) else 0
    cnd = condense(_PAREN.sub("", raw))
    if not cnd:
        return seasonal, None
    if cnd == target:
        return seasonal, 0
    if cnd.startswith(target) or target.startswith(cnd):
        return seasonal, abs(len(cnd) - len(target))
    return seasonal, None


def match_gregobase(conn, service_part, mode, incipit, office_part=None):
    """Match a chant to gregobase on office-part(code) + mode + incipit, choosing the
    best EDITION. Returns (candidates, note):

    `office_part` is the gregobase `office-part` code to match on. It defaults to the code
    derived from `service_part` (they are usually the same), but a chant whose liturgical USE
    differs from its gregobase KIND passes it explicitly — e.g. the "Benedictus es" canticle
    sung *pro GR.* on Trinity Sunday is USED as a gradual (service_part 'gr') but IS a hymn
    (office_part 'hy'). service_part governs storage; office_part governs identity.

      candidates : LIST of (chant_uuid, gregobase_id, chant_group_id). chant_uuid is the
                   'gregobase:<id>' value v_chant_item exposes. Normally length 1. It is
                   length>1 only when several DISTINCT chant_groups tie at the very best
                   (version, incipit) rank — a genuine same-edition ambiguity — in which
                   case the caller writes one row per candidate (the review queue) for a
                   human to keep one and delete the rest.
      note       : None, or a 'version-split' message when the chosen chant also appears
                   in OTHER chant_groups at worse editions (e.g. the Solesmes 'Panis quem
                   ego' in cg 782 vs the Palmer & Burgess 'Panis quem ego dedero' in cg
                   14026). Those groups should be merged in gregobase; the note surfaces
                   them so a human can do so.

    Candidates are every part+mode chant whose (paren-stripped) incipit exactly equals or
    is in a prefix relationship with the target, then ranked by (version_rank, has_paren,
    distance). Editon preference dominates incipit-exactness, which is why a Solesmes
    prefix match beats a Palmer & Burgess exact match. Raises only on a true dead end.
    """
    from sqlalchemy import text as sa_text

    # `mode` None means the chant is MODELESS (the book prints no mode and gregobase stores
    # NULL) — e.g. the "Procedamus in pace" versicle. Match `IS NULL` rather than binding the
    # string "None", which would silently match nothing and surface as a bogus LookupError.
    params = {"op": office_part or gregobase_office_part(service_part)}
    if mode is None:
        mode_pred = "g.mode IS NULL"
    else:
        mode_pred = "g.mode = :mode"
        params["mode"] = str(mode)
    rows = list(conn.execute(sa_text(
        "SELECT g.id, g.incipit, g.version, m.chant_group_id "
        "FROM gregobase_chants g "
        "LEFT JOIN gregobase_chant_group_map m ON m.gregobase_id = g.id "
        f"WHERE g.`office-part` = :op AND {mode_pred} "
        "ORDER BY g.id"
    ), params))

    target = condense(incipit)
    pool = []
    for gid, inc, ver, cg in rows:
        if cg is None:  # not in v_chant_item -> cannot be a chant_uuid
            continue
        sea, dist = _incipit_quality(inc, target)
        if dist is None:
            continue
        pool.append(dict(gid=gid, inc=inc, ver=ver, cg=cg,
                         rank=(version_rank(ver), sea, dist)))
    if not pool:
        raise LookupError(
            f"no gregobase match in v_chant_item for part={service_part!r} mode={mode} "
            f"incipit={incipit!r}"
        )

    bestkey = min(c["rank"] for c in pool)
    best = [c for c in pool if c["rank"] == bestkey]
    # one representative (lowest id; rows are ORDER BY id) per group at the best rank
    winners = {}
    for c in best:
        winners.setdefault(c["cg"], c)
    winners = [winners[cg] for cg in sorted(winners)]
    result = [(f"gregobase:{c['gid']}", c["gid"], c["cg"]) for c in winners]

    note = None
    other_groups = {c["cg"] for c in pool} - {c["cg"] for c in winners}
    if len(winners) == 1 and other_groups:
        # Same incipit also matched in other (worse-edition) groups -> probable split.
        best_other = {}
        for c in pool:
            if c["cg"] in other_groups and (
                    c["cg"] not in best_other or c["rank"] < best_other[c["cg"]]["rank"]):
                best_other[c["cg"]] = c
        w = winners[0]
        listing = ", ".join(f"cg {c['cg']} [{c['ver']}]"
                            for c in sorted(best_other.values(), key=lambda c: c["cg"]))
        note = (f"version-split: chose cg {w['cg']} [{w['ver']}] for "
                f"{service_part}/{mode} {incipit!r}; same chant also in {listing} "
                f"— consider merging the chant_groups")
    return result, note


def _column_exists(conn, table, col):
    from sqlalchemy import text as sa_text
    return conn.execute(sa_text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name=:t AND column_name=:c"
    ), {"t": table, "c": col}).scalar() > 0


def _index_part_rows(conn, office_part, page):
    """All gr_index_entry rows on `page` whose section_type maps (via SECTION_TYPE_TO_GREGOBASE)
    to the gregobase `office_part` code (unfiltered by incipit), as mappings with keys
    section_type, mode, incipit, gregobase_id, match_status (the last two NULL if the
    resolution columns don't exist). Keying on the gregobase office-part (the chant's KIND),
    not the liturgio service_part (its USE), lets a chant be resolved by what it IS while stored
    by how it is used — e.g. an 'hy' (hymnus) index row resolved for a 'gr'-slot chant. For the
    seven standard Mass parts the two codes coincide, so existing specs are unaffected."""
    from sqlalchemy import text as sa_text

    has_res = _column_exists(conn, "gr_index_entry", "gregobase_id")
    extra = ("gregobase_id, match_status" if has_res
             else "NULL AS gregobase_id, NULL AS match_status")
    rows = list(conn.execute(sa_text(
        f"SELECT section_type, mode, incipit, {extra} "
        "FROM gr_index_entry WHERE page = :p"
    ), {"p": page}).mappings())
    return [r for r in rows
            if SECTION_TYPE_TO_GREGOBASE.get(r["section_type"]) == office_part]


def _index_rows_for(conn, office_part, incipit, page):
    """gr_index_entry rows on `page` whose section_type maps to gregobase `office_part`, narrowed
    to the best incipit match: the exact (condensed) matches, else the longest prefix
    match in either direction. Returns a list of row mappings (see _index_part_rows for
    the keys). Shared by resolve_via_index (the curated-id shortcut) and resolve_xref (the
    live fallback's target-page mode lookup)."""
    part_rows = _index_part_rows(conn, office_part, page)

    target = condense(incipit)
    exact = [r for r in part_rows if condense(r["incipit"]) == target]
    if exact:
        return exact
    pref = [r for r in part_rows if condense(r["incipit"]) and
            (condense(r["incipit"]).startswith(target)
             or target.startswith(condense(r["incipit"])))]
    if pref:
        longest = max(len(condense(r["incipit"])) for r in pref)
        pref = [r for r in pref if len(condense(r["incipit"])) == longest]
    return pref


def resolve_via_index(conn, service_part, incipit, page, office_part=None):
    """Curated shortcut: return (chant_uuid, gregobase_id, chant_group_id, mode) from the
    pre-resolved gr_index_entry row on `page` that matches office_part + incipit, or None
    to signal "fall back to live matching".

    `office_part` is the gregobase office-part / index KIND used to pick the index row; it
    defaults to the code derived from `service_part` (identical for standard parts) but is
    passed explicitly when a chant's use (service_part) differs from its kind (e.g. an 'hy'
    hymn used pro-GR). `service_part` is used only in log messages.

    gr_index_entry.gregobase_id is the project's single source of truth: resolve_gr_index
    populated it once for the whole book under the edition policy (version_rank) and a
    human curated the hard cases (match_status 'resolved_with_difficulty'/'reviewed'), so
    reading it here keeps load-time identity consistent with that curation and skips a
    live match. None is returned — deferring to the live matcher's raise / review-queue
    behavior — when the curated id can't be used as-is:
      * no index row for this part+incipit on `page`;
      * the row is unresolved (gregobase_id NULL — status ambiguous/unmatched/null);
      * the incipit matches several index rows carrying DIFFERENT ids (ambiguous);
      * the resolved chant is ungrouped (no gregobase_chant_group_map row), so it has no
        v_chant_item chant_uuid and cannot be written as a valid link.
    """
    from sqlalchemy import text as sa_text

    office_part = office_part or gregobase_office_part(service_part)
    if page is None:
        return None
    cands = _index_rows_for(conn, office_part, incipit, page)
    if not cands:
        # The incipit didn't match any index row. By project convention the index keeps an
        # OCR-typo'd incipit verbatim (only gregobase_id is corrected), so a citation's
        # clean incipit (e.g. "Exaltabo te") can fail to match a typo'd index entry
        # ("Exalabo te"). Fall back to the part's rows on the page: if exactly one carries
        # a gregobase_id, the citation is unambiguous (you cannot cite a chant not on the
        # page), so use it.
        resolved = [r for r in _index_part_rows(conn, office_part, page)
                    if r["gregobase_id"] is not None]
        if len(resolved) != 1:
            return None
        print(f"      ℹ index incipit mismatch for {service_part} {incipit!r} on p{page}"
              f" — using the page's single resolved {service_part} entry "
              f"({resolved[0]['incipit']!r})")
        cands = resolved
    gids = {r["gregobase_id"] for r in cands if r["gregobase_id"] is not None}
    if len(gids) != 1:
        return None
    (gid,) = gids
    row = next(r for r in cands if r["gregobase_id"] == gid)
    cg = conn.execute(sa_text(
        "SELECT chant_group_id FROM gregobase_chant_group_map WHERE gregobase_id = :g"
    ), {"g": gid}).scalar()
    if cg is None:
        print(f"      ⚠ index resolves {service_part} {incipit!r} on p{page} to ungrouped "
              f"gregobase:{gid} (no v_chant_item uid) — live-matching instead")
        return None
    return (f"gregobase:{gid}", gid, cg, row["mode"])


def resolve_xref(conn, service_part, incipit, target_page, office_part=None):
    """Live fallback for a cross-reference chant when the curated index id is unusable.

    A cross-reference ("GR. Propitius esto, 288.") is NOT engraved on the page that
    cites it; the music lives on `target_page`. The index entry on that target page
    supplies the chant's `mode` (the citation prints none), after which the normal
    incipit+part+mode gregobase match applies. Disambiguation by service_part is
    essential — e.g. a graduale and an alleluia can share an incipit on different
    pages. Returns (LIST of (chant_uuid, gregobase_id, chant_group_id, mode), note),
    mirroring match_gregobase. Raises on no index entry, or an index entry whose mode is
    itself ambiguous on the target page.

    The gregobase match uses the TARGET-page index incipit, not the citing page's
    abbreviated stub: a citation like "GR. Beatus vir, 475." truncates the incipit, and
    that stub ("Beatus vir") can prefix the WRONG chant ("Beatus vir cujus") — the index
    entry on p475 carries the full "Beatus vir qui timet" that disambiguates.
    """
    office_part = office_part or gregobase_office_part(service_part)
    cands = _index_rows_for(conn, office_part, incipit, target_page)
    if not cands:
        raise LookupError(
            f"no index entry for cross-reference part={service_part!r} "
            f"incipit={incipit!r} on target page {target_page}"
        )
    modes = {r["mode"] for r in cands}
    if len(modes) > 1:
        raise LookupError(
            f"AMBIGUOUS cross-reference (part={service_part!r} incipit={incipit!r} "
            f"target page {target_page}): index gives modes={sorted(modes)} — "
            f"cannot pick the target-page mode"
        )
    mode = cands[0]["mode"]
    index_incipit = cands[0]["incipit"]  # authoritative full incipit on the target page
    matched, note = match_gregobase(conn, service_part, mode, index_incipit,
                                    office_part=office_part)
    return [(uuid, gid, cg, mode) for (uuid, gid, cg) in matched], note


def build_rows(conn, doc, spec):
    """Turn a subsection spec into fully-populated row dicts (no DB writes)."""
    from sqlalchemy import text as sa_text
    part_ids = load_part_ids(conn)
    rows = []
    # Is the spec's base epoch a LEAF DAY (kind='day', e.g. a titled solemnity like
    # OT-FOL-00-1 Trinity Sunday) rather than a WEEK formulary (OT-OT-13)? A week base has a
    # week→day layer, so a per-chant day qualifier promotes it to its Sunday/ferial day slug
    # ("<base>-<wkday>"). A leaf-day base has no such layer: a year-cycle (cycle_sun) or
    # weekday option refines the SAME day, recorded via the cycle_sun/wkday columns, and must
    # NOT append a "<base>-1" child (no such lit_epoch exists). See build loop below.
    # kind='common' (a Communia formulary, GR ch. 2) is a leaf for the same reason: it is not
    # a calendar day at all, so it has no week→day layer to promote into.
    base_kind = conn.execute(
        sa_text("SELECT kind FROM lit_epoch WHERE slug = :s"),
        {"s": spec["lit_epoch_slug"]},
    ).scalar()
    base_is_day = base_kind in ("day", "common")
    # Almost every spec is UNIVERSAL (the GR's own calendar); a spec may override this to
    # load into an order/rite-specific calendar (e.g. "OSB" for the Missae Propriae O.S.B.
    # appendix) that shares the same book/page/bbox machinery but is a DIFFERENT jurisdiction
    # row in lit_part_sources (part of uq_lps_slot's key, see slot_group_matches).
    jurisdiction = spec.get("jurisdiction", "UNIVERSAL")
    # option_num orders the chants that occupy the SAME slot (slug/wkday/part/cycle): the
    # primary (no option_txt) is 1, and each alternate — a chant marked with an option_txt
    # ("Vel:", "Ad libitum:", …) — takes the next number in the order it is printed. Chants
    # in the spec are authored primary-first, so a slot's `Vel ad libitum:` chant becomes
    # option_num 2. Keyed by the FINAL (post-promotion) slot so a per-day/per-cycle override,
    # which lives in its own slot, correctly stays option_num 1.
    option_counters = {}
    for raw in spec["chants"]:
        c = _chant_to_dict(raw)
        part = c["service_part"]
        if part not in part_ids:
            raise LookupError(f"unknown service_part code {part!r} (not in service_part)")
        # Prefer the curated gr_index_entry resolution (edition policy already applied,
        # human review preserved); only live-match when it can't be used. The chant's
        # index row sits on the page that ENGRAVES it: its own `page` if engraved here,
        # else the cited `target_page`.
        idx_page = c["page"] if c["engraved"] else c["target_page"]
        # The gregobase office-part / index KIND used to resolve identity — the chant's USE
        # (service_part) by default, but overridden when they differ (e.g. an 'hy' canticle
        # sung pro-GR: service_part 'gr', office_part 'hy'). See match_gregobase.
        office_part = c.get("office_part") or gregobase_office_part(part)
        if c.get("unmatched"):
            # Declared absent from the corpus: write the slot with chant_uuid NULL and do
            # not search. One "candidate" so the row-building loop below is unchanged; its
            # chant_uuid/gregobase_id/chant_group_id are all None. The mode is whatever the
            # book prints (usually nothing for these).
            cands, note, source = [(None, None, None, c["mode"])], None, "unmatched"
        elif (via_index := resolve_via_index(conn, part, c["incipit"], idx_page,
                                             office_part=office_part)) is not None:
            cands, note, source = [via_index], None, "index"
        elif c["engraved"]:
            matched, note = match_gregobase(conn, part, c["mode"], c["incipit"],
                                            office_part=office_part)
            cands = [(u, g, cg, c["mode"]) for (u, g, cg) in matched]
            source = "live"
        else:
            cands, note = resolve_xref(conn, part, c["incipit"], c["target_page"],
                                       office_part=office_part)
            source = "live"
        # For BOTH kinds the bbox/page are on `page`: an engraved chant's box on its own page,
        # or (for an xref) the box of the reference LINE on the citing page.
        pdf_page = printed_to_pdf_page(c["page"])
        bbox = compute_bbox(doc, pdf_page, c["band"])
        if bbox is None:
            raise ValueError(f"empty bbox band for {part} on p{c['page']}: {c['band']}")
        # One row per candidate chant_group. >1 means an unresolved gregobase split:
        # all are written (distinct chant_uuid) for the human to disambiguate in review.
        # Effective weekday(s) (Sun=1..Sat=7) and lit_epoch slug, from the chant's day-
        # specificity. An "In feriis" default lists SEVERAL weekdays ("wkdays" -> one row
        # each); a ferial option states its own weekday ("Feria N"); a Sunday-specific
        # year-cycle option ("Dom. anno A/B/C", carrying cycle_sun) is the Sunday (wkday 1);
        # otherwise inherit the subsection-level wkday (the week-DEFAULT Mass is null for an
        # OT week spec; a day-slug spec carries its day). Only a PER-CHANT day qualifier
        # promotes the week slug to its day slug "<base>-<wkday>" — so every chant in a
        # day-slug spec (a Lenten feria, Pentecost: wkday set once at the spec level and
        # inherited) stays at the base slug, no spurious suffix. wkday then mirrors the
        # slug's day suffix whenever there is one.
        base_slug = spec["lit_epoch_slug"]
        if c.get("wkdays"):
            wkday_list, promote = c["wkdays"], True
        elif c.get("wkday") is not None:
            wkday_list, promote = [c["wkday"]], True
        elif c.get("cycle_sun") is not None:
            wkday_list, promote = [1], True
        else:
            wkday_list, promote = [spec["wkday"]], False
        # Leaf-day base: keep the base slug and the spec-level wkday (null for a titled
        # feast); the cycle_sun year still lands in its own column below. No "<base>-1".
        if base_is_day:
            wkday_list, promote = [spec["wkday"]], False
        for eff_wkday in wkday_list:
            epoch_slug = f"{base_slug}-{eff_wkday}" if promote else base_slug
            # Number this chant within its slot (all its candidate-split rows share the
            # number — a split is one assignment awaiting disambiguation, not two options).
            slot_key = (epoch_slug, eff_wkday, part_ids[part],
                        c.get("cycle_sun"), c.get("cycle_wkday"))
            option_counters[slot_key] = option_counters.get(slot_key, 0) + 1
            option_num = option_counters[slot_key]
            for chant_uuid, gid, cg, mode in cands:
                row = dict(ROW_CONSTANTS)
                row.update(
                    jurisdiction=jurisdiction,
                    lit_epoch_slug=epoch_slug,
                    wkday=eff_wkday,
                    cycle_wkday=c.get("cycle_wkday"),
                    part_id=part_ids[part],
                    # Normally NULL on purpose — the text is reached via chant_uuid. An
                    # `unmatched` chant has no chant_uuid, so it carries its printed text
                    # here instead (read_spec_file requires it).
                    original_text=c.get("original_text"),
                    chant_uuid=chant_uuid,
                    text_src=c["text_src"],
                    printed_page_num=c["page"],  # PRINTED page (source of truth), not pdf index
                    # For a cross-reference, record the cited (engraving) PRINTED page; the
                    # citing page stays in printed_page_num. Engraved chants leave this NULL.
                    ref_page_num=(None if c["engraved"] else c["target_page"]),
                    bbox=bbox,
                    option_txt=c.get("option_txt"),
                    option_num=option_num,
                    cycle_sun=c.get("cycle_sun"),
                    notes=c.get("notes"),
                )
                row["_part_code"] = part  # for logging; stripped before the SQL params
                row["_meta"] = dict(incipit=c["incipit"], mode=mode, gregobase_id=gid,
                                    chant_group_id=cg, xref=(not c["engraved"]),
                                    target_page=c["target_page"], n_candidates=len(cands),
                                    note=note, source=source)
                rows.append(row)
    return rows


def slot_group_matches(conn, row, chant_group_id):
    """text_ids of existing rows that are the SAME assignment as the row being loaded:
    same SLOT — lit_epoch_slug / wkday / part_id / authority / book / cycle_sun / cycle_wkday
    / **option_num** (NULL-safe `<=>`) — AND whose chant is in the SAME `chant_group` as the
    loaded chant.
    `book` is in the key because a Gregorian Missal row may share authority ('GRADUALE') with
    a Graduale row on the same slot, distinguished only by book ('GREGORIAN_MISSAL' vs
    'GRADUALE'); without it, loading a GR chant would clobber the GM row's provenance.

    `option_num` is in the key so the loader AGREES WITH `uq_lps_slot`, the table's own
    NULL-safe unique backstop, whose column list is (jurisdiction, lit_epoch_slug, part_id,
    slot_book, slot_auth, slot_csun, slot_cwkday, slot_wkday, slot_wm4, slot_wm2, slot_tsrc,
    **option_num**, slot_chant). Without it the loader's key was NARROWER than the constraint:
    two DIFFERENT printed options of one part, in one slot, whose chants happen to share a
    chant_group (two editions/variants of one chant — e.g. gb 786 `sine alleluia` / gb 870
    `cum alleluia`, a CORRECT grouping) could not both be loaded. The second MATCHed the first
    and silently UPDATEd its provenance instead of inserting, one row short, with no dry-run
    signal (dedup queries the DB, and in a dry-run nothing is inserted yet, so both report
    `would INSERT`). Adding it does not affect the single-option case: `option_num` is
    `NOT NULL DEFAULT 1` in the schema and build_rows() always assigns an int >= 1 from the
    per-slot counter, so re-loading an unchanged spec yields the same number and keeps matching
    its existing row. The comparison is still `<=>` to mirror the constraint's NULL-safe
    semantics exactly and to stay correct if a hand-written row ever carries NULL.

    Matching on chant_GROUP (not exact chant_uuid) is deliberate: a different EDITION of the
    same chant counts as the same assignment, so we refresh its metadata and LEAVE its
    chant_uuid alone (the human's / other source's edition choice stands). A genuinely
    different chant is a different group and does NOT match — so several `Vel:`/`or:`
    alternates in one slot, and un-collapsed review candidates, are each independent and never
    clobbered. Authority is in the key, so other sources' rows (MISSAL text, GREGORIAN_MISSAL)
    are never matched. A row whose chant_uuid is not in v_chant_item (NULL / ungrouped) simply
    doesn't join, hence doesn't match.

    An `unmatched` row (declared absent from gregobase: chant_uuid NULL, see read_spec_file)
    cannot key on chant_group at all, so it keys on the same SLOT plus its `original_text` —
    the printed text that stands in for the chant's identity — and only ever matches other
    chant_uuid-NULL rows. Without this branch such a row would never find itself and would
    re-INSERT on every load, i.e. the loader would stop being idempotent."""
    from sqlalchemy import text as sa_text

    if row.get("chant_uuid") is None:
        if not row.get("original_text"):
            return []
        return [r[0] for r in conn.execute(sa_text(
            "SELECT l.text_id FROM lit_part_sources l "
            "WHERE l.chant_uuid IS NULL "
            "AND (l.jurisdiction <=> :jurisdiction) "
            "AND l.lit_epoch_slug = :slug AND (l.wkday <=> :wkday) AND l.part_id = :part_id "
            "AND l.assignment_authority_code = :auth AND (l.book <=> :book) "
            "AND (l.cycle_sun <=> :cycle_sun) AND (l.cycle_wkday <=> :cycle_wkday) "
            "AND (l.option_num <=> :option_num) "
            "AND (l.option_txt <=> :option_txt) AND l.original_text = :original_text"
        ), {
            "jurisdiction": row.get("jurisdiction", "UNIVERSAL"),
            "slug": row["lit_epoch_slug"], "wkday": row["wkday"], "part_id": row["part_id"],
            "auth": row["assignment_authority_code"], "book": row["book"],
            "cycle_sun": row["cycle_sun"], "cycle_wkday": row["cycle_wkday"],
            "option_num": row.get("option_num"),
            "option_txt": row.get("option_txt"), "original_text": row["original_text"],
        })]
    if chant_group_id is None:
        return []
    return [r[0] for r in conn.execute(sa_text(
        "SELECT l.text_id FROM lit_part_sources l "
        "JOIN v_chant_item vci ON vci.chant_item_uid = l.chant_uuid "
        "WHERE (l.jurisdiction <=> :jurisdiction) "
        "AND l.lit_epoch_slug = :slug AND (l.wkday <=> :wkday) AND l.part_id = :part_id "
        "AND l.assignment_authority_code = :auth AND (l.book <=> :book) "
        "AND (l.cycle_sun <=> :cycle_sun) "
        "AND (l.cycle_wkday <=> :cycle_wkday) AND (l.option_num <=> :option_num) "
        "AND vci.chant_group_id = :cg"
    ), {
        "jurisdiction": row.get("jurisdiction", "UNIVERSAL"),
        "slug": row["lit_epoch_slug"], "wkday": row["wkday"], "part_id": row["part_id"],
        "auth": row["assignment_authority_code"], "book": row["book"],
        "cycle_sun": row["cycle_sun"],
        "cycle_wkday": row["cycle_wkday"], "option_num": row.get("option_num"),
        "cg": chant_group_id,
    })]


def _deaccent(s):
    """Drop combining accents (the Gregorian Missal texts carry pronunciation accents that
    the incipit does not, e.g. 'Láuda ánima')."""
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(ch))


def gregorian_missal_targets(conn, row, incipit):
    """text_ids of UNLINKED Gregorian Missal rows this chant should link: same slot+option
    (translation_source_code='GREGORIAN_MISSAL' AND chant_uuid IS NULL, same lit_epoch_slug /
    wkday / part_id / cycle_sun / cycle_wkday / option_txt, NULL-safe) AND whose Latin text
    (`original_text`) starts with this chant's `incipit`. The Gregorian Missal uses the same
    (Solesmes) chants as the Graduale, so an unlinked GM text row inherits this chant's
    chant_uuid — and the incipit check keeps the RIGHT chant linked when a slot legitimately
    holds more than one (e.g. a Sunday + an 'in feriis' communion both at the week slug). NOT
    scoped by assignment_authority_code — a GM row may carry authority 'GRADUALE' or
    'GREGORIAN_MISSAL'; the translation source identifies it."""
    from sqlalchemy import text as sa_text

    tgt = condense(_deaccent(incipit))
    rows = conn.execute(sa_text(
        "SELECT text_id, original_text FROM lit_part_sources "
        "WHERE translation_source_code = 'GREGORIAN_MISSAL' AND chant_uuid IS NULL "
        "AND lit_epoch_slug = :slug AND (wkday <=> :wkday) AND part_id = :part_id "
        "AND (cycle_sun <=> :cycle_sun) AND (cycle_wkday <=> :cycle_wkday) "
        "AND (option_txt <=> :option_txt)"
    ), {
        "slug": row["lit_epoch_slug"], "wkday": row["wkday"], "part_id": row["part_id"],
        "cycle_sun": row["cycle_sun"], "cycle_wkday": row["cycle_wkday"],
        "option_txt": row["option_txt"],
    })
    return [tid for tid, ot in rows if ot and condense(_deaccent(ot)).startswith(tgt)]


INSERT_SQL = (
    "INSERT INTO lit_part_sources "
    "(jurisdiction, lit_epoch_slug, wkday, part_id, original_text, chant_uuid, vernacular_text, "
    " text_src, original_lang, vernacular_lang, assignment_authority_code, "
    " translation_source_code, review_status, "
    " common_of, book, printed_page_num, ref_page_num, bbox, cycle_sun, cycle_wkday, "
    " option_txt, option_num, notes) "
    "VALUES "
    "(:jurisdiction, :lit_epoch_slug, :wkday, :part_id, :original_text, :chant_uuid, "
    " :vernacular_text, :text_src, :original_lang, :vernacular_lang, "
    " :assignment_authority_code, :translation_source_code, :review_status, "
    " :common_of, :book, :printed_page_num, :ref_page_num, :bbox, "
    " :cycle_sun, :cycle_wkday, :option_txt, :option_num, :notes)"
)

# Upsert UPDATE — refresh only the GR-provenance METADATA of a matched row. Deliberately does
# NOT touch chant_uuid (the edition choice — may be a human's / another source's pick) nor
# original_text / vernacular_text (may hold another source's text) nor the slot columns.
# option_num IS refreshed: it is loader-derived slot ordering (primary=1, alternates 2+), so
# a re-load keeps it in sync with the spec (and corrects rows loaded before it was assigned).
# `notes` is written only when the SPEC supplies one (COALESCE on the incoming value, not the
# stored one): a spec that asserts a note keeps it in sync on re-load, while a spec with no note
# can never blank out a note a human left on the row.
UPDATE_METADATA_SQL = (
    "UPDATE lit_part_sources SET "
    "text_src = :text_src, book = :book, printed_page_num = :printed_page_num, "
    "ref_page_num = :ref_page_num, bbox = :bbox, option_num = :option_num, "
    "notes = COALESCE(:notes, notes) "
    "WHERE text_id = :text_id"
)


# The standard proper parts of a complete Mass. `tr` (Tract) substitutes for `al` (Alleluia)
# in Lent, so the Alleluia slot is satisfied by either; in Paschaltide the Gradual is replaced
# by a first Alleluia (`al1`), so `gr` is not required there and `al1` also satisfies the
# Alleluia slot (a ferial Paschal Mass often carries only `al1`, dropping the 2nd Alleluia).
_MASS_CORE = ("in", "gr", "of", "co")

# Slots a DIFFERENT service_part code can legitimately satisfy. Palm Sunday engraves its
# gradual ("Christus factus est", GR p148) in the `gr2` slot — a second gradual, printed AFTER
# the tract, which is why `gr2` sorts at display_order 60 rather than the gradual's 20. It
# still fills the Gradual requirement, exactly as `al1` fills the Alleluia one in Paschaltide.
_SLOT_FILLED_BY = {"gr": ("gr", "gr2")}

# Every service_part code the Mass-completeness check knows how to reason about. A spec whose
# base chants use NONE of these is not a Mass at all — e.g. the GOODFRIDAY service, whose liturgy
# has no introit, offertory or communion by definition — so the check does not apply and is
# skipped, rather than reporting the entire Mass ordinary as "missing".
_MASS_PROPER_CODES = set(_MASS_CORE) | {"al", "al1", "tr", "tr2", "gr2", "seq"}


def _mass_parts_missing(parts, slug):
    """Which core Mass parts are absent from `parts` (a set of service_part codes), given the
    season implied by `slug`. The Alleluia slot is satisfied by `al`, `al1`, OR `tr`; the
    Gradual slot by `gr` or `gr2` (see _SLOT_FILLED_BY); in Paschaltide (a `PASC-*` slug) the
    Gradual is replaced by an Alleluia, so `gr` is not required."""
    paschal = (slug or "").upper().startswith("PASC")
    missing = [p for p in _MASS_CORE
               if not (set(_SLOT_FILLED_BY.get(p, (p,))) & parts)
               and not (p == "gr" and paschal)]
    if not ({"al", "al1", "tr"} & parts):
        missing.append("al/tr")
    return missing


def warn_incomplete_default(spec):
    """Advisory check: warn if the WEEK-DEFAULT (base-slug) Mass is missing a standard proper.

    The week-default Mass is the set of chants that stay at the bare `lit_epoch_slug` — those
    with no per-chant `wkday`/`wkdays`/`cycle_sun` (a day-slug spec's whole Mass, or an OT
    week's default). A missing DEFAULT part is almost always a mis-scoped rubric (a week-default
    chant wrongly filed under a `Feria N`/`Anno I` rubric — the real OT-17 bug), NOT an
    editorial omission by Solesmes. Prints a `⚠` line so review catches it; never blocks."""
    base = set()
    for raw in spec["chants"]:
        c = _chant_to_dict(raw)
        if c.get("wkday") is None and not c.get("wkdays") and c.get("cycle_sun") is None:
            base.add(c["service_part"])
    if not base:
        print("  ℹ completeness: this spec has no week-default chants — not checked")
        return
    if not (base & _MASS_PROPER_CODES):
        print("  ℹ completeness: this spec has no Mass proper chants (a non-Mass service, "
              "e.g. GOODFRIDAY) — not checked")
        return
    missing = _mass_parts_missing(base, spec["lit_epoch_slug"])
    if missing:
        print(f"  ⚠ COMPLETENESS: week-default Mass ({spec['lit_epoch_slug']}) is missing "
              f"[{', '.join(missing)}] — a missing default proper is usually a mis-scoped "
              f"rubric (a week-default chant filed under a Feria/Anno rubric), not an "
              f"editorial omission. Re-check the page before loading.")


def run_verify(spec, spec_name, engine):
    """Read-only post-load verification for a spec's slug family.

    1. Builds the expected rows from the spec (reusing build_rows).
    2. Queries lit_part_sources for the actual DB rows in that slug family.
    3. Prints a readable table of the DB rows.
    4. Asserts row count, idempotency, and ref_page_num sanity.
    Returns True on full PASS, False if any assertion FAILs.
    """
    import fitz
    from sqlalchemy import text as sa_text

    base_slug = spec["lit_epoch_slug"]
    jurisdiction = spec.get("jurisdiction", "UNIVERSAL")
    print(f"Subsection: {spec_name}  ({spec['label']})")
    print(f"  lit_epoch_slug={base_slug!r}  wkday={spec['wkday']}  jurisdiction={jurisdiction!r}")
    print(f"  mode=VERIFY (read-only)")
    print("-" * 72)

    doc = fitz.open(PDF_PATH)
    try:
        with engine.connect() as conn:
            # Step 1: build expected rows from the spec.
            built_rows = build_rows(conn, doc, spec)

            # Step 2: query actual DB rows for this slug family.
            db_rows = list(conn.execute(sa_text(
                "SELECT lps.lit_epoch_slug, lps.wkday, lps.cycle_sun, lps.cycle_wkday, "
                "       lps.part_id, lps.printed_page_num, lps.ref_page_num, "
                "       sp.part_code, lps.text_id, lps.chant_uuid, lps.jurisdiction "
                "FROM lit_part_sources lps "
                "JOIN service_part sp ON sp.part_id = lps.part_id "
                "WHERE lps.lit_epoch_slug LIKE :slug_pat AND lps.book = 'GRADUALE' "
                "AND lps.assignment_authority_code = 'GRADUALE' "
                "AND (lps.jurisdiction <=> :jurisdiction) "
                "ORDER BY lps.lit_epoch_slug, lps.part_id, lps.wkday, lps.cycle_sun"
            ), {"slug_pat": base_slug + "%", "jurisdiction": jurisdiction}).mappings())

            # A `part_id=0` (MASS.all) row is a whole-Mass POINTER — the "Cantus ut supra, die
            # N ..." / "Ut infra notatur ..., 669." rubric that names another day's or another
            # chapter's formulary instead of a chant. It fills no chant slot, carries chant_uuid
            # NULL, and NO spec can express it (read_spec_file requires an incipit + a match or
            # an explicit `unmatched` original_text), so it is written by hand. Show it in the
            # table but hold it out of the ROW COUNT comparison, which is spec-vs-DB.
            pointer_rows = [r for r in db_rows if r["part_id"] == 0]
            db_rows = [r for r in db_rows if r["part_id"] != 0]

            # Step 3: print the readable table.
            col_w = [max(len(h), 20) for h in
                     ("lit_epoch_slug", "wkday", "cycle_sun", "cycle_wkday",
                      "part_id(code)", "printed_page_num", "ref_page_num")]
            headers = ["lit_epoch_slug", "wkday", "cycle_sun", "cycle_wkday",
                       "part_id(code)", "printed_page_num", "ref_page_num"]
            col_widths = [20, 6, 10, 12, 14, 16, 14]
            fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
            print(fmt.format(*headers))
            print("  ".join("-" * w for w in col_widths))
            for r in db_rows:
                part_label = f"{r['part_id']}({r['part_code']})"
                print(fmt.format(
                    str(r["lit_epoch_slug"]),
                    str(r["wkday"]) if r["wkday"] is not None else "NULL",
                    str(r["cycle_sun"]) if r["cycle_sun"] is not None else "NULL",
                    str(r["cycle_wkday"]) if r["cycle_wkday"] is not None else "NULL",
                    part_label,
                    str(r["printed_page_num"]) if r["printed_page_num"] is not None else "NULL",
                    str(r["ref_page_num"]) if r["ref_page_num"] is not None else "NULL",
                ))
            for r in pointer_rows:
                print(f"  [pointer] {r['lit_epoch_slug']}  part_id=0(all)  "
                      f"printed_page_num={r['printed_page_num']}  "
                      f"ref_page_num={r['ref_page_num']}  text_id={r['text_id']}  "
                      f"— whole-Mass rubric, excluded from ROW COUNT")
            print()

            # Step 4: assertions.
            failures = []

            # 4a: row count.
            expected_count = len(built_rows)
            actual_count = len(db_rows)
            if actual_count == expected_count:
                print(f"ROW COUNT:    PASS ({actual_count} rows)")
            else:
                print(f"ROW COUNT:    FAIL (expected {expected_count}, got {actual_count})")
                failures.append(f"row count {actual_count} != {expected_count}")

            # 4b: idempotency — every built row must match an existing DB row via
            # slot_group_matches (same key the loader uses for dedup). A would-INSERT
            # means the row is not yet in the DB (or the dedup key doesn't match).
            would_insert = 0
            for row in built_rows:
                m = row["_meta"]
                matches = slot_group_matches(conn, row, m["chant_group_id"])
                if not matches:
                    would_insert += 1
            if would_insert == 0:
                print(f"IDEMPOTENT:   PASS (would-insert=0)")
            else:
                print(f"IDEMPOTENT:   FAIL (would-insert={would_insert})")
                failures.append(f"would-insert={would_insert}")

            # 4c: ref_page_num sanity — engraved rows must have ref_page_num NULL;
            # cross-reference rows must have it set. We check the DB rows by joining
            # built row expectations per text_id (matched by slot_group_matches).
            # Build a lookup: for each built row, record whether it is engraved.
            engraved_by_cg = {}
            for row in built_rows:
                m = row["_meta"]
                cg = m["chant_group_id"]
                # xref=True means cross-reference (ref_page_num should be set)
                engraved_by_cg[(
                    row["lit_epoch_slug"], row["wkday"], row["part_id"],
                    row["cycle_sun"], row["cycle_wkday"], cg
                )] = not m["xref"]

            ref_violations = []
            for row in built_rows:
                m = row["_meta"]
                cg = m["chant_group_id"]
                matches = slot_group_matches(conn, row, cg)
                if not matches:
                    continue  # already counted above; skip
                is_engraved = not m["xref"]
                for tid in matches:
                    # find the db row
                    db_r = next((r for r in db_rows if r["text_id"] == tid), None)
                    if db_r is None:
                        continue
                    if is_engraved and db_r["ref_page_num"] is not None:
                        ref_violations.append(
                            f"text_id={tid} engraved but ref_page_num={db_r['ref_page_num']}"
                        )
                    elif not is_engraved and db_r["ref_page_num"] is None:
                        ref_violations.append(
                            f"text_id={tid} xref but ref_page_num=NULL"
                        )

            if not ref_violations:
                print(f"REF_PAGE_NUM: PASS")
            else:
                print(f"REF_PAGE_NUM: FAIL ({len(ref_violations)} violation(s))")
                for v in ref_violations:
                    print(f"  - {v}")
                failures.append(f"ref_page_num violations={len(ref_violations)}")

            print()
            if not failures:
                print("VERIFY PASS")
                return True
            else:
                print("VERIFY FAIL: " + "; ".join(failures))
                return False
    finally:
        doc.close()
        engine.dispose()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--subsection", choices=sorted(SUBSECTIONS),
                     help="which built-in subsection spec to load")
    src.add_argument("--spec-file",
                     help="path to an agent-produced JSON subsection spec")
    ap.add_argument("--dry-run", action="store_true",
                    help="extract/match/compute and print, but write nothing")
    ap.add_argument("--limit", type=int, default=None,
                    help="only attempt the first N chants (tiny real write first)")
    ap.add_argument("--reconcile", action="store_true",
                    help="deprecated / no-op: updating an existing row in place is now the "
                         "DEFAULT (upsert). Kept for backward compatibility.")
    ap.add_argument("--skip-existing", action="store_true",
                    help="restore the old behavior: SKIP an existing row instead of updating "
                         "it (still inserts genuinely-new rows)")
    ap.add_argument("--verify", action="store_true",
                    help="read-only post-load check: parse the spec, build expected rows, "
                         "query the DB, and assert row count / idempotency / ref_page_num "
                         "sanity. Requires --spec-file. Exits non-zero on any FAIL.")
    args = ap.parse_args(argv)

    if args.spec_file:
        spec = read_spec_file(args.spec_file)
        spec_name = os.path.basename(args.spec_file)
    elif args.subsection:
        spec = SUBSECTIONS[args.subsection]
        spec_name = args.subsection
    else:
        ap.error("one of --subsection or --spec-file is required")

    if args.verify:
        if not args.spec_file:
            ap.error("--verify requires --spec-file")
        engine = make_engine()
        ok = run_verify(spec, spec_name, engine)
        sys.exit(0 if ok else 1)

    print(f"Subsection: {spec_name}  ({spec['label']})")
    print(f"  lit_epoch_slug={spec['lit_epoch_slug']!r}  wkday={spec['wkday']}  "
          f"jurisdiction={spec.get('jurisdiction', 'UNIVERSAL')!r}")
    mode_lbl = ("DRY-RUN" if args.dry_run
                else ("SKIP-EXISTING" if args.skip_existing else "UPSERT"))
    print(f"  mode={mode_lbl}" + (f"  limit={args.limit}" if args.limit else ""))
    warn_incomplete_default(spec)
    print("-" * 72)

    import fitz

    engine = make_engine()
    doc = fitz.open(PDF_PATH)
    inserted = updated = skipped = gm_linked = 0
    try:
        with engine.connect() as conn:
            rows = build_rows(conn, doc, spec)
            if args.limit is not None:
                rows = rows[: args.limit]

            from sqlalchemy import text as sa_text, bindparam
            for row in rows:
                m = row["_meta"]
                kind = f"xref->p{m['target_page']}" if m["xref"] else "engraved"
                ambig = (f"  ⚠ REVIEW: 1 of {m['n_candidates']} candidate groups"
                         if m["n_candidates"] > 1 else "")
                bits = [f"{k}={row[k]}" for k in ("wkday", "cycle_sun", "cycle_wkday")
                        if row[k] is not None]
                if row.get("jurisdiction", "UNIVERSAL") != "UNIVERSAL":
                    bits.insert(0, f"jurisdiction={row['jurisdiction']}")
                if row.get("option_num", 1) > 1:
                    bits.append(f"option_num={row['option_num']} ({row['option_txt']!r})")
                asg = ("  {" + " ".join(bits) + "}") if bits else ""
                print(f"[{row['_part_code']:>3}] printed p{row['printed_page_num']} "
                      f"mode {m['mode']} "
                      f"'{m['incipit']}' -> {row['chant_uuid']} (cg {m['chant_group_id']}) "
                      f"[{kind} via {m['source']}]{asg}{ambig}")
                if m.get("note"):
                    print(f"      ℹ {m['note']}")
                ot = ("NULL" if row["original_text"] is None
                      else f"{row['original_text']!r}  ⚠ NOT IN GREGOBASE (chant_uuid NULL)")
                print(f"      bbox={row['bbox']}  text_src={row['text_src']!r}  "
                      f"original_text={ot}")
                if row.get("notes"):
                    print(f"      notes={row['notes']!r}")

                params = {k: v for k, v in row.items() if not k.startswith("_")}

                # Upsert (update in place, never duplicate): an existing row in the SAME slot
                # whose chant is in the SAME chant_group is the same assignment — refresh its
                # provenance metadata (NOT its chant_uuid). No such row -> INSERT. A different
                # chant (different group: an `or:` alternate, a review candidate) does not
                # match, so it is added as its own row, not clobbered.
                targets = slot_group_matches(conn, row, m["chant_group_id"])

                if args.skip_existing and targets:
                    print(f"      SKIP — {len(targets)} existing row(s) in slot+group {targets}")
                    skipped += 1
                    continue
                # Unlinked Gregorian Missal text rows in this slot inherit this chant
                # (same Solesmes chant); only when the chant is unambiguous (n_candidates==1).
                # An unmatched row has no chant_uuid to hand down, so it links nothing.
                gm = (gregorian_missal_targets(conn, row, m["incipit"])
                      if m["n_candidates"] == 1 and row["chant_uuid"] is not None else [])

                if args.dry_run:
                    print(f"      (dry-run: would UPDATE metadata on {targets} — same "
                          f"chant_group)" if targets else "      (dry-run: would INSERT)")
                    if gm:
                        print(f"      (dry-run: would link {len(gm)} Gregorian Missal "
                              f"row(s) {gm} -> {row['chant_uuid']})")
                    continue

                if targets:
                    for tid in targets:
                        conn.execute(sa_text(UPDATE_METADATA_SQL), {**params, "text_id": tid})
                    print(f"      UPDATED metadata on {targets} (same chant_group; "
                          f"chant_uuid kept)")
                    updated += len(targets)
                else:
                    res = conn.execute(sa_text(INSERT_SQL), params)
                    print(f"      INSERTED text_id={res.lastrowid}")
                    inserted += 1
                if gm:
                    conn.execute(sa_text(
                        "UPDATE lit_part_sources SET chant_uuid = :cu WHERE text_id IN :ids"
                    ).bindparams(bindparam("ids", expanding=True)),
                        {"cu": row["chant_uuid"], "ids": gm})
                    gm_linked += len(gm)
                    print(f"      + linked {len(gm)} Gregorian Missal row(s) {gm} -> "
                          f"{row['chant_uuid']}")
                conn.commit()
    finally:
        doc.close()
        engine.dispose()

    print("-" * 72)
    print(f"Done. inserted={inserted}  updated={updated}  skipped={skipped}  "
          f"gm_linked={gm_linked}  {'(dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
