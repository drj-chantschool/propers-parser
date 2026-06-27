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
                     incipit + office-part (= service_part code) + mode. The full Latin
                     text is reached by joining `chant_uuid` -> `v_chant_item`/gregobase.
                     `original_text` is left NULL on purpose — OCR of the engraved text
                     is unreliable and the text already lives in gregobase, so we link
                     instead of copying.
  - `text_src`       the right-justified scripture citation as printed in the 1974 GR
                     (additive data not present in gregobase). NULL when none is printed
                     (e.g. the Christmas Alleluia).
  - `book`/`pdf_page_num`  FK into the seeded `books` table (book='GRADUALE').
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

JSON spec format (one subsection per file):
  {
    "subsection": "pasc-oct-fri",                  # slug for logging
    "label": "Easter Octave — Friday (...)",
    "lit_epoch_slug": "...",                       # FK into lit_epoch
    "wkday": 6,                                     # calendar weekday (Sun=1..Sat=7) iff the
                                                   # GR labels it (Feria N/Dominica/Sabbato),
                                                   # else null; NOT the slug's seq suffix

    "chants": [
      {
        "page": 220,                               # 1-based pdf page the row points at
        "service_part": "in",                      # in/gr/al/tr/of/co/...
        "mode": 4,                                  # int (omit for a cross-reference)
        "incipit": "Eduxit eos",                   # printed incipit (drives the match)
        "text_src": "Ps. ...",                     # citation top-right, or null
        "band": [ytop_pt, ybot_pt],                # PDF points (text-layer coords)
        "engraved": true,                          # false = cross-reference
        "target_page": 288,                        # xref only: page the chant is engraved on
        "option_txt": "Vel:",                      # optional: alternate-chant marker
        "cycle_sun": 1                             # optional: 1=anno A, 2=anno B, 3=anno C
      }
    ]
  }
The `band` is in PDF points (the text layer's native unit), NOT dpi=200 pixels: the agent
reads start-y from `get_text("dict")` block boxes (points) and confirms by vision.
compute_bbox() scales the result to the dpi=200 space `books`/`bbox` use.

Two kinds of chant:
  * ENGRAVED (`engraved: true`): music is on `page`. `band` boxes the engraving; `mode`
    is given; the row's pdf_page_num/bbox point at the engraving.
  * CROSS-REFERENCE (`engraved: false`): the page only CITES the chant ("GR. Propitius
    esto, 288."); the music is on `target_page`. The chant's identity (incipit+part+mode)
    is resolved from the index entry on `target_page` (mode is read there, not supplied).
    pdf_page_num stays the REFERENCE page and `band` boxes the reference LINE — so a human
    reviewer renders that box to confirm the citation was interpreted correctly. text_src
    is normally null (no citation prints at a reference).

IDEMPOTENCY
-----------
`lit_part_sources` has NO unique constraint (text_id is the only unique key), so dedup
lives here: before inserting a chant the loader checks for an existing row on
(lit_epoch_slug, wkday, part_id, assignment_authority_code, chant_uuid, cycle_sun) using
the NULL-safe `<=>` operator, and SKIPS if one exists. chant_uuid and cycle_sun are part
of the key on purpose, so the legitimate "multiple rows for one part" patterns stay
idempotent:
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

    # 3. The rest (already-written rows are skipped by the dedup check):
    $PY propers-parser/load_graduale_propers.py --subsection nat-day

    # Agent-produced JSON spec (the scaling path) — same dry/tiny/full progression:
    $PY propers-parser/load_graduale_propers.py --spec-file specs/pasc-oct-fri.json --dry-run

DB credentials come from the keyring entry ('liturgio-mysql', 'jcost').
"""

import argparse
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
    page_num=None,  # legacy column; superseded by book/pdf_page_num
    common_of=None,
    book=DEFAULT_BOOK,
    option_txt=None,  # alternate-chant marker (e.g. "Vel:"); NULL for the primary
)

# --------------------------------------------------------------------------- #
# Subsection specs. Each chant: (page, service_part, mode, incipit, text_src, band)
#   page       1-based pdf page in `graduale romanum.pdf` where the chant STARTS
#   service_part  in/gr/al/tr/of/co/...  (also the gregobase `office-part` code)
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
            if c.get("mode") is None:
                raise ValueError(
                    f"spec {path!r} chant[{i}]: engraved chant needs 'mode'")
            mode, target_page = int(c["mode"]), None
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
        chants.append(dict(
            page=c["page"], service_part=c["service_part"], mode=mode,
            incipit=c["incipit"], text_src=c.get("text_src"), band=band,
            target_page=target_page, engraved=engraved,
            option_txt=c.get("option_txt"),  # alternate marker ("Vel:"), or None
            cycle_sun=(None if cycle_sun is None else int(cycle_sun)),  # 1=A/2=B/3=C year
        ))

    return {
        "label": data["label"],
        "lit_epoch_slug": data["lit_epoch_slug"],
        "wkday": data.get("wkday"),
        "chants": chants,
    }


# section_type (full Latin word in gr_index_entry) -> service_part code.
SECTION_TYPE_TO_PART = {
    "introitus": "in", "graduale": "gr", "alleluia": "al", "tractus": "tr",
    "offertorium": "of", "communio": "co", "sequentia": "seq",
}

# liturgio service_part code -> gregobase `office-part` code. Identical for most parts,
# but gregobase codes sequences 'se' where liturgio's service_part code is 'seq'.
GREGOBASE_OFFICE_PART = {"seq": "se"}


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
                engraved=True, option_txt=None, cycle_sun=None)


def condense(s):
    """Canonicalize an incipit for whitespace/punctuation/orthography-insensitive
    comparison: lowercase, drop all whitespace+punctuation, and fold classical vs
    medieval Latin letterforms j->i and v->u. Absorbs OCR spacing ('Eduxiteos' ==
    'Eduxit eos'), index punctuation ('Domine, Dominus' == 'Domine Dominus'), and the
    I/J + U/V split between sources ('Iacta' (index) == 'Jacta' (gregobase)). Folding
    only ever merges letterforms, and part+mode (and, for xrefs, target page) keep the
    candidate set narrow, so it does not introduce false matches in practice."""
    s = re.sub(r"[\W_]+", "", (s or "").strip().lower(), flags=re.UNICODE)
    return s.translate(_LATIN_FOLD)


_LATIN_FOLD = str.maketrans("jv", "iu")


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


def compute_bbox(doc, page, band):
    """Union of text blocks centred in `band` on `page`, in dpi=200 px space.

    Returns 'x0,y0,x1,y1' (ints) or None if no blocks fall in the band.
    """
    ytop, ybot = band
    pg = doc[page - 1]
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


def match_gregobase(conn, service_part, mode, incipit):
    """Match a chant to gregobase on office-part(code) + mode + incipit, choosing the
    best EDITION. Returns (candidates, note):

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

    rows = list(conn.execute(sa_text(
        "SELECT g.id, g.incipit, g.version, m.chant_group_id "
        "FROM gregobase_chants g "
        "LEFT JOIN gregobase_chant_group_map m ON m.gregobase_id = g.id "
        "WHERE g.`office-part` = :op AND g.mode = :mode "
        "ORDER BY g.id"
    ), {"op": gregobase_office_part(service_part), "mode": str(mode)}))

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


def resolve_xref(conn, service_part, incipit, target_page):
    """Resolve a cross-reference chant to a chant_uuid via the TARGET page's index.

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
    from sqlalchemy import text as sa_text

    rows = list(conn.execute(sa_text(
        "SELECT section_type, mode, incipit FROM gr_index_entry WHERE page = :p"
    ), {"p": target_page}))
    part_rows = [r for r in rows if SECTION_TYPE_TO_PART.get(r[0]) == service_part]

    target = condense(incipit)
    exact = [r for r in part_rows if condense(r[2]) == target]
    if exact:
        cands = exact
    else:
        pref = [r for r in part_rows if condense(r[2]) and
                (condense(r[2]).startswith(target) or target.startswith(condense(r[2])))]
        if pref:
            longest = max(len(condense(r[2])) for r in pref)
            pref = [r for r in pref if len(condense(r[2])) == longest]
        cands = pref
    if not cands:
        raise LookupError(
            f"no index entry for cross-reference part={service_part!r} "
            f"incipit={incipit!r} on target page {target_page}"
        )
    modes = {r[1] for r in cands}
    if len(modes) > 1:
        raise LookupError(
            f"AMBIGUOUS cross-reference (part={service_part!r} incipit={incipit!r} "
            f"target page {target_page}): index gives modes={sorted(modes)} — "
            f"cannot pick the target-page mode"
        )
    mode = cands[0][1]
    index_incipit = cands[0][2]  # authoritative full incipit on the target page
    matched, note = match_gregobase(conn, service_part, mode, index_incipit)
    return [(uuid, gid, cg, mode) for (uuid, gid, cg) in matched], note


def build_rows(conn, doc, spec):
    """Turn a subsection spec into fully-populated row dicts (no DB writes)."""
    part_ids = load_part_ids(conn)
    rows = []
    for raw in spec["chants"]:
        c = _chant_to_dict(raw)
        part = c["service_part"]
        if part not in part_ids:
            raise LookupError(f"unknown service_part code {part!r} (not in service_part)")
        if c["engraved"]:
            matched, note = match_gregobase(conn, part, c["mode"], c["incipit"])
            cands = [(u, g, cg, c["mode"]) for (u, g, cg) in matched]
        else:
            cands, note = resolve_xref(conn, part, c["incipit"], c["target_page"])
        # For BOTH kinds the bbox/page are on `page`: an engraved chant's box on its
        # own page, or (for an xref) the box of the reference LINE on the citing page
        # — the latter is what a reviewer renders to confirm the citation was read right.
        bbox = compute_bbox(doc, c["page"], c["band"])
        if bbox is None:
            raise ValueError(f"empty bbox band for {part} on p{c['page']}: {c['band']}")
        # One row per candidate chant_group. >1 means an unresolved gregobase split:
        # all are written (distinct chant_uuid) for the human to disambiguate in review.
        for chant_uuid, gid, cg, mode in cands:
            row = dict(ROW_CONSTANTS)
            row.update(
                lit_epoch_slug=spec["lit_epoch_slug"],
                wkday=spec["wkday"],
                part_id=part_ids[part],
                original_text=None,   # left NULL on purpose — text is via chant_uuid
                chant_uuid=chant_uuid,
                text_src=c["text_src"],
                pdf_page_num=c["page"],
                bbox=bbox,
                option_txt=c.get("option_txt"),
                cycle_sun=c.get("cycle_sun"),
            )
            row["_part_code"] = part  # for logging; stripped before the SQL params
            row["_meta"] = dict(incipit=c["incipit"], mode=mode, gregobase_id=gid,
                                chant_group_id=cg, xref=(not c["engraved"]),
                                target_page=c["target_page"], n_candidates=len(cands),
                                note=note)
            rows.append(row)
    return rows


def existing_row_id(conn, row):
    """Return text_id of an existing row on the natural key, else None.

    The key includes chant_uuid so a day's ALTERNATE chants — multiple rows of the
    same part (e.g. an introit + its "Vel:" alternate) — are distinct rows yet the
    load stays idempotent on re-run (each alternate is a different chant_uuid).
    `lit_part_sources` has no DB-level unique key; text_id is the only unique key.
    """
    from sqlalchemy import text as sa_text

    return conn.execute(sa_text(
        "SELECT text_id FROM lit_part_sources "
        "WHERE lit_epoch_slug = :slug AND (wkday <=> :wkday) "
        "AND part_id = :part_id AND assignment_authority_code = :auth "
        "AND (chant_uuid <=> :chant_uuid) AND (cycle_sun <=> :cycle_sun) "
        "LIMIT 1"
    ), {
        "slug": row["lit_epoch_slug"], "wkday": row["wkday"],
        "part_id": row["part_id"], "auth": row["assignment_authority_code"],
        "chant_uuid": row["chant_uuid"], "cycle_sun": row["cycle_sun"],
    }).scalar()


INSERT_SQL = (
    "INSERT INTO lit_part_sources "
    "(lit_epoch_slug, wkday, part_id, original_text, chant_uuid, vernacular_text, "
    " text_src, original_lang, vernacular_lang, assignment_authority_code, "
    " translation_source_code, review_status, page_num, "
    " common_of, book, pdf_page_num, bbox, cycle_sun, cycle_wkday, option_txt) "
    "VALUES "
    "(:lit_epoch_slug, :wkday, :part_id, :original_text, :chant_uuid, "
    " :vernacular_text, :text_src, :original_lang, :vernacular_lang, "
    " :assignment_authority_code, :translation_source_code, :review_status, :page_num, "
    " :common_of, :book, :pdf_page_num, :bbox, "
    " :cycle_sun, :cycle_wkday, :option_txt)"
)

# --reconcile: refresh an already-loaded row to the loader's current computed
# values (used after an approach change — e.g. backfilling chant_uuid and nulling
# original_text on rows written before the chant_uuid realignment).
UPDATE_SQL = (
    "UPDATE lit_part_sources SET "
    "chant_uuid = :chant_uuid, original_text = :original_text, text_src = :text_src, "
    "book = :book, pdf_page_num = :pdf_page_num, bbox = :bbox "
    "WHERE text_id = :text_id"
)


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
                    help="UPDATE existing rows to current computed values "
                         "(chant_uuid/original_text/text_src/book/page/bbox) instead "
                         "of skipping them; new rows are still inserted")
    args = ap.parse_args(argv)

    if args.spec_file:
        spec = read_spec_file(args.spec_file)
        spec_name = os.path.basename(args.spec_file)
    elif args.subsection:
        spec = SUBSECTIONS[args.subsection]
        spec_name = args.subsection
    else:
        ap.error("one of --subsection or --spec-file is required")
    print(f"Subsection: {spec_name}  ({spec['label']})")
    print(f"  lit_epoch_slug={spec['lit_epoch_slug']!r}  wkday={spec['wkday']}")
    mode_lbl = "DRY-RUN" if args.dry_run else ("RECONCILE" if args.reconcile else "WRITE")
    print(f"  mode={mode_lbl}" + (f"  limit={args.limit}" if args.limit else ""))
    print("-" * 72)

    import fitz

    engine = make_engine()
    doc = fitz.open(PDF_PATH)
    inserted = updated = skipped = 0
    try:
        with engine.connect() as conn:
            rows = build_rows(conn, doc, spec)
            if args.limit is not None:
                rows = rows[: args.limit]

            from sqlalchemy import text as sa_text
            for row in rows:
                m = row["_meta"]
                kind = f"xref->p{m['target_page']}" if m["xref"] else "engraved"
                ambig = (f"  ⚠ REVIEW: 1 of {m['n_candidates']} candidate groups"
                         if m["n_candidates"] > 1 else "")
                print(f"[{row['_part_code']:>3}] p{row['pdf_page_num']} mode {m['mode']} "
                      f"'{m['incipit']}' -> {row['chant_uuid']} (cg {m['chant_group_id']}) "
                      f"[{kind}]{ambig}")
                if m.get("note"):
                    print(f"      ℹ {m['note']}")
                print(f"      bbox={row['bbox']}  text_src={row['text_src']!r}  "
                      f"original_text=NULL")

                existing = existing_row_id(conn, row)
                params = {k: v for k, v in row.items() if not k.startswith("_")}

                if existing is not None:
                    if args.reconcile and not args.dry_run:
                        conn.execute(sa_text(UPDATE_SQL), {**params, "text_id": existing})
                        conn.commit()
                        print(f"      RECONCILED text_id={existing}")
                        updated += 1
                    else:
                        print(f"      SKIP — existing text_id={existing} on natural key")
                        skipped += 1
                    continue
                if args.dry_run:
                    print("      (dry-run: not inserted)")
                    continue

                res = conn.execute(sa_text(INSERT_SQL), params)
                conn.commit()
                print(f"      INSERTED text_id={res.lastrowid}")
                inserted += 1
    finally:
        doc.close()
        engine.dispose()

    print("-" * 72)
    print(f"Done. inserted={inserted}  updated={updated}  skipped={skipped}  "
          f"{'(dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
