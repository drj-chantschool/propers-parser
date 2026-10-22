#!/usr/bin/env python
r"""
load_gm_propers.py — Load Gregorian Missal Mass propers into `lit_part_sources`.

WHAT THIS DOES
--------------
Given an agent-produced JSON spec for one liturgical day/Mass from the Gregorian Missal
(GM), this loader inserts `lit_part_sources` rows carrying the GM's English vernacular text.

Key differences from `load_graduale_propers.py`:
  - assignment_authority_code = 'GRADUALE': the authority to assign a chant to a day
    comes from the Graduale Romanum; the GM is a Sunday/Solemnity translation of it.
    translation_source_code = 'GREGORIAN_MISSAL' carries the translation credit.
  - Dedup key includes book='GREGORIAN_MISSAL' to distinguish GM rows from GR rows
    on the same (slug, wkday, part, chant_uuid, cycle_sun, authority) slot.
  - Page provenance: sets book='GREGORIAN_MISSAL' and printed_page_num from the spec's
    per-chant `page` field. For cross-references, ref_page_num = gm_xref_page. bbox=NULL
    (no page images seeded for GM).
  - NO gregobase matching: chant identity (`chant_uuid`) is BORROWED from the already-
    loaded GRADUALE row for the same (lit_epoch_slug, wkday, part, cycle_sun). The GM's
    chant assignments are always the same as the Graduale Romanum's for the same day.
  - `assignment_authority_code` = 'GRADUALE': the Graduale Romanum is the authority
    that assigns chants to days; the GM is a translation/adaptation of it for Sundays
    and Solemnities. `translation_source_code` = 'GREGORIAN_MISSAL' carries the
    translation credit. `p_translation_source` already has the 'GREGORIAN_MISSAL' entry.

PRODUCER / BACKEND SPLIT
------------------------
An AGENT reads the Gregorian Missal PDF (full `gregorian-missal.pdf` is preferred over
section PDFs, which may truncate chants at TOC boundaries), extracts the English text for
each chant part, and emits a JSON spec. This LOADER is the deterministic backend: given
the spec it looks up the GRADUALE chant_uuid, enforces idempotency, and writes.

JSON spec format (see GM/specs/README.md for full producer contract):
  {
    "subsection": "nat-day",                   # slug for logging
    "label": "Christmas — Mass of the Day (Gregorian Missal)",
    "lit_epoch_slug": "NAT-DAY-00-0-day",      # FK into lit_epoch (week or day slug)
    "wkday": null,                             # same rules as GR: null for OT Sundays,
                                               # null for date-keyed feasts, 1–7 for
                                               # Feria-labelled days
    "chants": [
      {
        "service_part": "in",                  # in/gr/tr/al/of/co/seq
        "page": 198,                           # GM printed page where this chant's
                                               # part-label first appears → printed_page_num
        "vernacular_text": "...",              # English text from the GM
        "text_src": "Is 9:6; Ps 97",          # GM's scripture citation (optional)
        "cycle_sun": null,                     # 1=anno A, 2=anno B, 3=anno C, or null
        "gm_xref_page": null,                  # For cross-references: GM page where the
                                               # cited music is engraved → ref_page_num
        "option_num": 1,                       # 1=primary (default); 2+=an "Or:"/ad-libitum
                                               # alternate. A slot (part+cycle_sun) with N
                                               # GRADUALE chants needs N entries, option_num
                                               # 1..N, each with its OWN vernacular_text/page.
        "option_txt": null                     # rubric for an alternate (e.g. "Or:"); null
                                               # for the primary → printed_page_num/option_txt
      }
    ]
  }

ALTERNATES ("Or:" / ad libitum)
-------------------------------
When the GM prints a primary chant plus one or more alternates for the same slot
(e.g. Introit "Dum clamarem" then "Or: Ego autem"), the GRADUALE already stores one row
per chant (distinct chant_uuids; the alternate carries option_txt). The spec must supply
one entry per chant — same service_part and cycle_sun — distinguished by option_num
(1=primary, 2+=alternate) and each carrying its own vernacular_text/page/text_src (and
gm_xref_page if the alternate is a cross-reference). The loader matches spec entries (in
option_num order) to the GRADUALE candidates (primary-first) and errors if the counts
differ, so a missed alternate is caught rather than silently duplicating the primary text.

SLUG DERIVATION (mirrors load_graduale_propers.py)
--------------------------------------------------
  - `cycle_sun` is not null → Sunday-specific variant; use `{base_slug}-1`, wkday=1.
  - `cycle_sun` is null → use base_slug and spec.wkday as-is.

For OT Sundays (base_slug="OT-OT-19", spec.wkday=null):
  - Default chants (cycle_sun=null) → slug="OT-OT-19", wkday=null.
  - Cycle options (cycle_sun=1/3) → slug="OT-OT-19-1", wkday=1.

For day-slug specs (Lent Sunday, Pentecost: wkday set at spec level):
  - All chants inherit spec.wkday; no cycle_sun expected → slug unchanged.

FALLBACK: SLUG-TIER MISMATCH
-----------------------------
Some parts don't live where the cycle_sun-only promotion rule above expects. Example:
Paschaltide's Sunday-only second Alleluia (part 'al', distinct from 'al1' which replaces
the Gradual) is reslugged by the GR loader to the Sunday's day slug ({base}-1, wkday=1)
even when cycle_sun is null, while the rest of that Sunday's Mass stays at the week slug
(base, wkday=null). When the primary (cycle_sun-derived) lookup finds no GRADUALE row,
build_rows() retries at the OTHER slug tier for that same part+cycle_sun and, if found,
writes the GM row there instead — i.e. it copies whatever the GRADUALE actually has for
that part, wherever it lives, rather than forcing one slug tier for the whole Mass.

CHANT_UUID BORROWING
--------------------
For each chant the loader queries:
  SELECT chant_uuid, text_id FROM lit_part_sources
  WHERE lit_epoch_slug = :slug AND (wkday <=> :wkday)
    AND part_id = :part_id AND assignment_authority_code = 'GRADUALE'
    AND (cycle_sun <=> :cycle_sun)

If 0 rows → error (must load the Graduale section first).
If 1 row → use its chant_uuid.
If N>1 rows → write N GM rows (one per GRADUALE review candidate), same pattern.

IDEMPOTENCY
-----------
Same dedup key as the GR loader: (lit_epoch_slug, wkday, part_id,
assignment_authority_code, chant_uuid, cycle_sun). Re-running skips existing rows.

HOW TO RUN
----------
    PY=C:\Users\johna\liturgio\.venv\Scripts\python.exe

    # Dry run — match, print rows, write nothing:
    $PY propers-parser/GM/load_gm_propers.py --spec-file propers-parser/GM/specs/nat-day.json --dry-run

    # Tiny REAL write first (test one insert before the batch):
    $PY propers-parser/GM/load_gm_propers.py --spec-file propers-parser/GM/specs/nat-day.json --limit 1

    # Full run (already-written rows are skipped by the dedup check):
    $PY propers-parser/GM/load_gm_propers.py --spec-file propers-parser/GM/specs/nat-day.json

    # Reconcile: UPDATE book/printed_page_num/ref_page_num on already-loaded rows,
    # INSERT any that are missing:
    $PY propers-parser/GM/load_gm_propers.py --spec-file propers-parser/GM/specs/nat-day.json --reconcile

DB credentials from keyring entry ('liturgio-mysql', 'jcost').
"""

import argparse
import json
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

KEYRING_SERVICE = "liturgio-mysql"
KEYRING_USER = "jcost"
DB_HOST, DB_PORT, DB_NAME = "localhost", 3306, "liturgio"

ASSIGNMENT_AUTHORITY = "GRADUALE"
TRANSLATION_SOURCE = "GREGORIAN_MISSAL"

ROW_CONSTANTS = dict(
    cycle_wkday=None,
    original_text=None,
    original_lang="la",
    vernacular_lang="en",
    assignment_authority_code=ASSIGNMENT_AUTHORITY,
    translation_source_code=TRANSLATION_SOURCE,
    review_status="draft",
    common_of=None,
    book="GREGORIAN_MISSAL",
    bbox=None,
    option_txt=None,
    option_num=1,
)

UPDATE_SQL = (
    "UPDATE lit_part_sources SET "
    "book = :book, printed_page_num = :printed_page_num, ref_page_num = :ref_page_num, "
    "vernacular_text = :vernacular_text, text_src = :text_src, "
    "option_num = :option_num, option_txt = :option_txt "
    "WHERE text_id = :text_id"
)

INSERT_SQL = (
    "INSERT INTO lit_part_sources "
    "(lit_epoch_slug, wkday, cycle_sun, cycle_wkday, part_id, "
    " original_text, vernacular_text, text_src, original_lang, vernacular_lang, "
    " assignment_authority_code, translation_source_code, review_status, "
    " common_of, book, printed_page_num, ref_page_num, bbox, "
    " chant_uuid, option_txt, option_num) "
    "VALUES "
    "(:lit_epoch_slug, :wkday, :cycle_sun, :cycle_wkday, :part_id, "
    " :original_text, :vernacular_text, :text_src, :original_lang, :vernacular_lang, "
    " :assignment_authority_code, :translation_source_code, :review_status, "
    " :common_of, :book, :printed_page_num, :ref_page_num, :bbox, "
    " :chant_uuid, :option_txt, :option_num)"
)


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


def load_part_ids(conn):
    from sqlalchemy import text as sa_text
    return {code: pid for pid, code in conn.execute(sa_text(
        "SELECT part_id, part_code FROM service_part"))}


def read_spec_file(path):
    """Load and validate a GM spec JSON. Returns the spec dict."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    for k in ("label", "lit_epoch_slug", "chants"):
        if k not in data:
            raise ValueError(f"spec {path!r}: missing top-level key {k!r}")
    if not isinstance(data["chants"], list) or not data["chants"]:
        raise ValueError(f"spec {path!r}: 'chants' must be a non-empty list")
    chants = []
    for i, c in enumerate(data["chants"]):
        for k in ("service_part", "page", "vernacular_text"):
            if k not in c:
                raise ValueError(f"spec {path!r} chant[{i}]: missing key {k!r}")
        if not isinstance(c["page"], int):
            raise ValueError(f"spec {path!r} chant[{i}]: 'page' must be an integer")
        if not (c["vernacular_text"] or "").strip():
            raise ValueError(
                f"spec {path!r} chant[{i}]: vernacular_text is empty")
        cycle_sun = c.get("cycle_sun")
        if cycle_sun is not None and int(cycle_sun) not in (1, 2, 3):
            raise ValueError(
                f"spec {path!r} chant[{i}]: cycle_sun must be 1 (A), 2 (B), 3 (C), or null")
        option_num = c.get("option_num", 1)
        if not isinstance(option_num, int) or option_num < 1:
            raise ValueError(
                f"spec {path!r} chant[{i}]: option_num must be an integer >= 1 "
                f"(1=primary, 2+=alternates)")
        omits = c.get("gm_omits_options", False)
        if not isinstance(omits, bool):
            raise ValueError(
                f"spec {path!r} chant[{i}]: gm_omits_options must be true/false")
        chants.append(dict(
            service_part=c["service_part"],
            page=c["page"],
            vernacular_text=c["vernacular_text"].strip(),
            text_src=c.get("text_src"),
            cycle_sun=(None if cycle_sun is None else int(cycle_sun)),
            gm_xref_page=c.get("gm_xref_page"),
            option_num=option_num,
            option_txt=c.get("option_txt"),
            gm_omits_options=omits,
        ))
    return {
        "label": data["label"],
        "lit_epoch_slug": data["lit_epoch_slug"],
        "wkday": data.get("wkday"),
        "chants": chants,
    }


def find_graduale_rows(conn, epoch_slug, wkday, part_id, cycle_sun):
    """Return all GRADUALE rows matching this liturgical slot, primary chant first.

    Returns list of (chant_uuid, text_id, option_txt) ordered so the primary chant
    (option_txt IS NULL) comes first, then any alternates by text_id. Length 1 is the
    normal case. Length > 1 means the GM prints alternates for the slot (a primary chant
    plus one or more "Or:"/ad-libitum options); the spec must supply one entry per
    candidate, and build_rows zips them to this ordered list (see build_rows).
    """
    from sqlalchemy import text as sa_text
    rows = conn.execute(sa_text(
        "SELECT chant_uuid, text_id, option_txt FROM lit_part_sources "
        "WHERE lit_epoch_slug = :slug AND (wkday <=> :wkday) "
        "AND part_id = :part_id AND assignment_authority_code = 'GRADUALE' "
        "AND book = 'GRADUALE' "
        "AND (cycle_sun <=> :cycle_sun) "
        "ORDER BY (option_txt IS NULL) DESC, text_id ASC"
    ), {"slug": epoch_slug, "wkday": wkday, "part_id": part_id,
        "cycle_sun": cycle_sun}).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def existing_row_id(conn, row):
    """Return text_id of an existing GM row on the dedup natural key, or None."""
    from sqlalchemy import text as sa_text
    return conn.execute(sa_text(
        "SELECT text_id FROM lit_part_sources "
        "WHERE lit_epoch_slug = :slug AND (wkday <=> :wkday) "
        "AND part_id = :part_id AND assignment_authority_code = :auth "
        "AND (chant_uuid <=> :chant_uuid) AND (cycle_sun <=> :cycle_sun) "
        "AND book = :book"
    ), {
        "slug": row["lit_epoch_slug"], "wkday": row["wkday"],
        "part_id": row["part_id"], "auth": row["assignment_authority_code"],
        "chant_uuid": row["chant_uuid"], "cycle_sun": row["cycle_sun"],
        "book": row["book"],
    }).scalar()


def build_rows(conn, spec):
    """Turn a GM spec into fully-populated row dicts (no DB writes).

    Chant entries are grouped into liturgical SLOTS keyed by (service_part, cycle_sun).
    A slot with one entry is the normal case. A slot with several entries means the GM
    prints ALTERNATES for that part — a primary chant plus one or more "Or:"/ad-libitum
    options — each a DISTINCT chant with its own text and page. The GRADUALE stores these
    as several rows (distinct chant_uuids) for the slot; the loader zips one spec entry to
    each GRADUALE candidate (primary-first ordering), borrowing chant_uuid from the GR and
    taking vernacular_text / page / option_num / option_txt from the spec. option_num is
    1 for the primary and 2+ for alternates; option_txt carries the GM's rubric (e.g. "Or:").
    """
    from sqlalchemy import text as sa_text
    part_ids = load_part_ids(conn)
    base_slug = spec["lit_epoch_slug"]
    spec_wkday = spec.get("wkday")

    # Is the spec's base epoch a LEAF DAY (kind='day', e.g. a titled solemnity/feast like
    # NAT-IO-01-0 Holy Family) rather than a WEEK formulary (OT-OT-13)? A week base has a
    # week->day layer, so a cycle-specific chant (anno A/B/C) promotes it to its Sunday day
    # slug ("<base>-1"). A leaf-day base has no such layer: a year-cycle option refines the
    # SAME day and must stay at the base slug (mirrors load_graduale_propers.py's base_is_day
    # handling) -- no spurious "<base>-1" child lit_epoch exists for those.
    base_kind = conn.execute(
        sa_text("SELECT kind FROM lit_epoch WHERE slug = :s"), {"s": base_slug}
    ).scalar()
    base_is_day = (base_kind == "day")

    # Group entries by slot, preserving first-appearance order (dict keeps insertion order).
    slots = {}
    for c in spec["chants"]:
        slots.setdefault((c["service_part"], c["cycle_sun"]), []).append(c)

    rows = []
    for (part, cycle_sun), entries in slots.items():
        if part not in part_ids:
            raise LookupError(
                f"unknown service_part code {part!r} (not in service_part table)")

        # Derive effective epoch slug and wkday (mirrors GR loader logic).
        # A cycle-specific chant (anno A/B/C) is normally a Sunday option: promote the
        # week slug to its day slug "-1" and set wkday=1. A leaf-day base (base_is_day)
        # has no week->day layer, so it keeps the base slug/spec wkday instead.
        if cycle_sun is not None and not base_is_day:
            epoch_slug = f"{base_slug}-1"
            eff_wkday = 1
        else:
            epoch_slug = base_slug
            eff_wkday = spec_wkday

        # Look up existing GRADUALE rows (primary first) to borrow chant_uuid.
        graduale_rows = find_graduale_rows(
            conn, epoch_slug, eff_wkday, part_ids[part], cycle_sun)

        # Some parts don't live where the cycle_sun-only promotion rule above expects
        # (e.g. Paschaltide's Sunday-only second Alleluia, which the GR loader reslugs
        # to the day slug even with cycle_sun=null, while the rest of that Sunday's Mass
        # stays at the week slug). Rather than guess, fall back to the OTHER slug tier
        # and write the GM row wherever the GRADUALE actually holds this part+cycle_sun.
        if not graduale_rows and not base_is_day:
            alt_slug, alt_wkday = (
                (f"{base_slug}-1", 1) if epoch_slug == base_slug
                else (base_slug, spec_wkday)
            )
            alt_rows = find_graduale_rows(
                conn, alt_slug, alt_wkday, part_ids[part], cycle_sun)
            if alt_rows:
                epoch_slug, eff_wkday, graduale_rows = alt_slug, alt_wkday, alt_rows

        if not graduale_rows:
            raise LookupError(
                f"no GRADUALE row found for {part!r} at epoch={epoch_slug!r} "
                f"wkday={eff_wkday} cycle_sun={cycle_sun} — "
                f"load the Graduale section first")

        n_cands = len(graduale_rows)
        cands = ", ".join(f"{u} (option_txt={ot!r})" for (u, _t, ot) in graduale_rows)

        # The GM is an ABRIDGED book: it can legitimately print fewer options for a slot
        # than the Graduale does (e.g. Feb 2's candle antiphon — the GR adds "Vel ant.
        # Lumen cum cant. ut infra", pointing at a chant printed later in the same rite,
        # and the GM prints no such alternate). A shortfall must be DECLARED, though:
        # silence still errors, because the usual cause is a producer missing an option.
        # Set "gm_omits_options": true on any entry of the slot to declare it.
        allow_shortfall = any(e.get("gm_omits_options") for e in entries)
        if len(entries) > n_cands:
            raise ValueError(
                f"slot {part!r} cycle_sun={cycle_sun} at epoch={epoch_slug!r}: the spec "
                f"provides {len(entries)} entry(ies) but the GRADUALE has only {n_cands} "
                f"chant(s) here — there is no chant_uuid to borrow for the extras. Either "
                f"the spec invents an option, or the Graduale section is missing one. "
                f"GRADUALE candidates: {cands}")
        if len(entries) < n_cands and not allow_shortfall:
            raise ValueError(
                f"slot {part!r} cycle_sun={cycle_sun} at epoch={epoch_slug!r}: the GRADUALE "
                f"has {n_cands} chant(s) here but the spec provides {len(entries)} entry(ies). "
                f"Provide exactly one spec entry per GRADUALE chant, each with its own "
                f"vernacular_text/page and an option_num (1=primary, 2+=alternates). "
                f"If the GM genuinely prints fewer, confirm it against the page and declare "
                f"it with \"gm_omits_options\": true on an entry of this slot. "
                f"GRADUALE candidates: {cands}")
        if len(entries) < n_cands:
            print(f"      ⚠ GM OMITS OPTIONS: {part!r} cycle_sun={cycle_sun} at "
                  f"{epoch_slug!r} — GM supplies {len(entries)} of the GRADUALE's "
                  f"{n_cands}; declared via gm_omits_options. GRADUALE candidates: {cands}")

        # Bind each entry to the GRADUALE candidate at its own option_num (primary-first
        # ordering), NOT by position — so a declared shortfall that skips the primary
        # still lands on the right chant instead of silently shifting up one.
        entries_sorted = sorted(entries, key=lambda e: e["option_num"])
        for entry in entries_sorted:
            if entry["option_num"] > n_cands:
                raise ValueError(
                    f"slot {part!r} cycle_sun={cycle_sun} at epoch={epoch_slug!r}: entry has "
                    f"option_num={entry['option_num']} but the GRADUALE has only {n_cands} "
                    f"chant(s). GRADUALE candidates: {cands}")
            chant_uuid, src_text_id, _ot = graduale_rows[entry["option_num"] - 1]
            row = dict(ROW_CONSTANTS)
            row.update(
                lit_epoch_slug=epoch_slug,
                wkday=eff_wkday,
                cycle_sun=cycle_sun,
                part_id=part_ids[part],
                vernacular_text=entry["vernacular_text"],
                text_src=entry.get("text_src"),
                chant_uuid=chant_uuid,
                printed_page_num=entry["page"],
                ref_page_num=entry.get("gm_xref_page"),
                option_num=entry["option_num"],
                option_txt=entry.get("option_txt"),
            )
            row["_part_code"] = part
            row["_meta"] = dict(
                cycle_sun=cycle_sun, n_candidates=n_cands,
                src_graduale_text_id=src_text_id)
            rows.append(row)

    return rows


# The standard proper parts of a complete Mass. `tr` (Tract) substitutes for `al` (Alleluia)
# in Lent; in Paschaltide the Gradual is replaced by a second Alleluia (see warn_incomplete_mass).
_MASS_CORE = ("in", "gr", "of", "co")


def warn_incomplete_mass(spec):
    """Advisory check: warn if a standard proper part is absent across the WHOLE section.

    The Gregorian Missal covers only Sundays and Solemnities (no ferial Masses), and it often
    prints the Gradual/Alleluia per year-cycle (Year A/B/C) rather than as a single default —
    so completeness is judged over the UNION of the default and all cycle chants, NOT the
    default alone (a default-only check would false-warn on every cycle-driven Sunday). A genre
    missing EVERYWHERE is a producer omission (a part skipped while reading the section), not an
    editorial gap. The Alleluia slot is satisfied by `al` OR `tr`; in Paschaltide (`PASC-*`) the
    Gradual is not required. Prints a `⚠` line so review catches it; never blocks."""
    parts = {c["service_part"] for c in spec["chants"]}
    paschal = (spec["lit_epoch_slug"] or "").upper().startswith("PASC")
    missing = [p for p in _MASS_CORE
               if p not in parts and not (p == "gr" and paschal)]
    if "al" not in parts and "tr" not in parts:
        missing.append("al/tr")
    if missing:
        print(f"  ⚠ COMPLETENESS: Sunday/Solemnity Mass ({spec['lit_epoch_slug']}) is missing "
              f"[{', '.join(missing)}] across the default and all cycles — a Mass proper absent "
              f"everywhere is usually a missed part, not an editorial omission. Re-check the "
              f"GM section before loading.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec-file", required=True,
                    help="path to an agent-produced GM JSON spec")
    ap.add_argument("--dry-run", action="store_true",
                    help="look up GRADUALE rows and print, but write nothing")
    ap.add_argument("--reconcile", action="store_true",
                    help="UPDATE existing rows (book/printed_page_num/ref_page_num/"
                         "vernacular_text/text_src); INSERT any missing rows")
    ap.add_argument("--limit", type=int, default=None,
                    help="only attempt the first N chants")
    args = ap.parse_args(argv)

    spec = read_spec_file(args.spec_file)
    spec_name = os.path.basename(args.spec_file)
    print(f"Spec: {spec_name}  ({spec['label']})")
    print(f"  lit_epoch_slug={spec['lit_epoch_slug']!r}  wkday={spec['wkday']}")
    mode = "DRY-RUN" if args.dry_run else ("RECONCILE" if args.reconcile else "WRITE")
    print(f"  mode={mode}" + (f"  limit={args.limit}" if args.limit else ""))
    warn_incomplete_mass(spec)
    print("-" * 72)

    engine = make_engine()
    inserted = updated = skipped = 0
    try:
        with engine.connect() as conn:
            rows = build_rows(conn, spec)
            if args.limit is not None:
                rows = rows[: args.limit]

            from sqlalchemy import text as sa_text
            for row in rows:
                m = row["_meta"]
                opt = ""
                if m["n_candidates"] > 1:
                    opt = (f"  [option {row['option_num']}/{m['n_candidates']}"
                           + (f" {row['option_txt']!r}" if row.get("option_txt") else "")
                           + "]")
                page_info = f"p.{row['printed_page_num']}"
                if row.get("ref_page_num"):
                    page_info += f" (→ p.{row['ref_page_num']})"
                print(
                    f"[{row['_part_code']:>3}] {row['lit_epoch_slug']} "
                    f"wkday={row['wkday']} cycle_sun={row['cycle_sun']} "
                    f"{page_info} -> chant_uuid={row['chant_uuid']}{opt}"
                )
                print(f"      (from GRADUALE text_id={m['src_graduale_text_id']})")
                trunc = row["vernacular_text"][:80]
                ellipsis = "…" if len(row["vernacular_text"]) > 80 else ""
                print(f"      vernacular_text: {trunc!r}{ellipsis}")
                print(f"      text_src={row['text_src']!r}")

                existing = existing_row_id(conn, row)
                params = {k: v for k, v in row.items() if not k.startswith("_")}

                if args.dry_run:
                    status = f"existing text_id={existing}" if existing else "new"
                    print(f"      (dry-run: {status})")
                    continue

                if existing is not None and args.reconcile:
                    update_params = dict(
                        text_id=existing,
                        book=row["book"],
                        printed_page_num=row["printed_page_num"],
                        ref_page_num=row.get("ref_page_num"),
                        vernacular_text=row["vernacular_text"],
                        text_src=row.get("text_src"),
                        option_num=row["option_num"],
                        option_txt=row.get("option_txt"),
                    )
                    conn.execute(sa_text(UPDATE_SQL), update_params)
                    conn.commit()
                    print(f"      UPDATED text_id={existing}")
                    updated += 1
                elif existing is not None:
                    print(f"      SKIP — existing text_id={existing} on natural key")
                    skipped += 1
                else:
                    res = conn.execute(sa_text(INSERT_SQL), params)
                    conn.commit()
                    print(f"      INSERTED text_id={res.lastrowid}")
                    inserted += 1
    finally:
        engine.dispose()

    print("-" * 72)
    print(f"Done. inserted={inserted}  updated={updated}  skipped={skipped}  "
          f"{'(dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
