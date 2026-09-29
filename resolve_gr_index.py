#!/usr/bin/env python
r"""
resolve_gr_index.py — Resolve each gr_index_entry row to a gregobase_chants id.

WHAT THIS DOES
--------------
The back-of-book index (`gr_index_entry`) lists every chant in the Graduale Romanum
(page, section_type, mode, incipit). This first pass resolves each mappable entry to the
single best gregobase chant id — choosing the edition by the project policy in
load_graduale_propers.version_rank (Solesmes 1974 > Solesmes 1961 > generic Solesmes >
Vatican > other-year Solesmes > rest) — and records it on the index row:

    gregobase_id  INT NULL  FK -> gregobase_chants(id)
    match_status  ENUM('resolved','ambiguous','unmatched','reviewed')

Statuses written by this script:
    resolved    one best gregobase chant found (exact, or a confident fuzzy correction
                of an OCR-garbled index incipit).
    ambiguous   the incipit matches >1 distinct chant_group at the best rank — a human
                must pick. gregobase_id left NULL.
    unmatched   no match and no confident fuzzy correction. gregobase_id left NULL.

These two are NEVER written by this script and are PROTECTED — a re-run skips rows that
carry either (unless --repopulate), so curation is not clobbered:
    resolved_with_difficulty  a human/agent resolved it by judgment (disambiguating a tie,
                an abbreviated/OCR incipit, or a chant not auto-matched). Feeds a manual
                review queue.
    reviewed    a human stamped it after confirming the row.

Once populated, cross-references and engraved-chant identity in load_graduale_propers can
read the pre-resolved id instead of live-matching.

FUZZY CORRECTION
----------------
~7% of index incipits are OCR typos ('Confesio', 'Domine refugum', 'Exclaamaverunt').
For an otherwise-unmatched entry the script finds, within the same office-part+mode, the
gregobase incipit most similar (difflib ratio on condensed text) to the garbled one; if
the best is >= FUZZY_THRESHOLD and clearly ahead of the runner-up, it re-resolves through
match_gregobase using that (correct) incipit so the edition policy still applies. Every
fuzzy correction is printed for human verification.

HOW TO RUN  (always the canonical repo venv)
--------------------------------------------
    PY=C:\Users\johna\liturgio\.venv\Scripts\python.exe
    $PY propers-parser/resolve_gr_index.py --dry-run     # report only, no DB writes
    $PY propers-parser/resolve_gr_index.py               # add columns (if needed) + populate

DB credentials come from the keyring entry ('liturgio-mysql', 'jcost').
"""

import argparse
import difflib
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# Reuse the matcher / version policy / SECTION_TYPE_TO_PART from the loader.
_spec = importlib.util.spec_from_file_location(
    "lgp", os.path.join(_HERE, "load_graduale_propers.py"))
lgp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lgp)

FUZZY_THRESHOLD = 0.84   # min difflib ratio (condensed) to accept an OCR correction
FUZZY_MARGIN = 0.06      # best must beat runner-up by at least this much

ADD_COLS_SQL = [
    "ALTER TABLE gr_index_entry ADD COLUMN gregobase_id INT NULL",
    "ALTER TABLE gr_index_entry ADD COLUMN match_status "
    "ENUM('resolved','ambiguous','unmatched','reviewed','resolved_with_difficulty') NULL",
    "ALTER TABLE gr_index_entry ADD CONSTRAINT fk_gie_gregobase "
    "FOREIGN KEY (gregobase_id) REFERENCES gregobase_chants(id) "
    "ON UPDATE CASCADE ON DELETE SET NULL",
]


def column_exists(conn, table, col):
    from sqlalchemy import text as t
    return conn.execute(t(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name=:tb AND column_name=:c"
    ), {"tb": table, "c": col}).scalar() > 0


def ensure_columns(conn):
    from sqlalchemy import text as t
    if not column_exists(conn, "gr_index_entry", "gregobase_id"):
        conn.execute(t(ADD_COLS_SQL[0]))
        conn.execute(t(ADD_COLS_SQL[1]))
        conn.execute(t(ADD_COLS_SQL[2]))
        conn.commit()
        print("Added columns gregobase_id, match_status (+ FK) to gr_index_entry.")
    else:
        print("Columns already present on gr_index_entry.")


def fuzzy_correct(conn, part, mode, garbled):
    """Return (corrected_incipit, ratio) for the best same-part+mode gregobase incipit
    near `garbled`, or None if not confident."""
    from sqlalchemy import text as t
    rows = list(conn.execute(t(
        "SELECT DISTINCT incipit FROM gregobase_chants "
        "WHERE `office-part`=:p AND mode=:m AND incipit IS NOT NULL"
    ), {"p": lgp.gregobase_office_part(part), "m": str(mode)}))
    g = lgp.condense(garbled)
    scored = sorted(
        ((difflib.SequenceMatcher(None, g, lgp.condense(r[0])).ratio(), r[0]) for r in rows),
        reverse=True)
    if not scored:
        return None
    best_ratio, best_inc = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    if best_ratio >= FUZZY_THRESHOLD and (best_ratio - runner) >= FUZZY_MARGIN:
        return best_inc, best_ratio
    return None


def resolve_all(conn, dry_run, repopulate):
    from sqlalchemy import text as t

    # The status/id columns may not exist yet (a --dry-run before the first real run).
    has_cols = column_exists(conn, "gr_index_entry", "match_status")
    sel_extra = "gregobase_id, match_status" if has_cols else "NULL, NULL"
    rows = list(conn.execute(t(
        f"SELECT row_id, page, section_type, mode, incipit, {sel_extra} "
        "FROM gr_index_entry ORDER BY row_id")))

    counts = {"resolved": 0, "fuzzy": 0, "ambiguous": 0, "unmatched": 0,
              "not_mappable": 0, "skipped_human": 0}
    fuzzy_log, ambiguous_log, unmatched_log = [], [], []
    updates = []  # (row_id, gregobase_id_or_None, status)

    # Never auto-overwrite a status a human has set/curated.
    PROTECTED = ("reviewed", "resolved_with_difficulty")

    for row_id, page, st, mode, inc, cur_gid, cur_status in rows:
        if cur_status in PROTECTED and not repopulate:
            counts["skipped_human"] += 1
            continue
        part = lgp.SECTION_TYPE_TO_GREGOBASE.get(st)
        if not part or mode is None or not (1 <= (page or 0) <= 906):
            counts["not_mappable"] += 1
            updates.append((row_id, None, None))
            continue
        try:
            cands, _note = lgp.match_gregobase(conn, part, mode, inc)
            if len(cands) > 1:
                counts["ambiguous"] += 1
                ambiguous_log.append((page, st, mode, inc, [c[1] for c in cands]))
                updates.append((row_id, None, "ambiguous"))
            else:
                counts["resolved"] += 1
                updates.append((row_id, cands[0][1], "resolved"))
        except Exception:
            corr = fuzzy_correct(conn, part, mode, inc)
            if corr is None:
                counts["unmatched"] += 1
                unmatched_log.append((page, st, mode, inc))
                updates.append((row_id, None, "unmatched"))
                continue
            corrected, ratio = corr
            try:
                cands, _note = lgp.match_gregobase(conn, part, mode, corrected)
            except Exception:
                counts["unmatched"] += 1
                unmatched_log.append((page, st, mode, inc))
                updates.append((row_id, None, "unmatched"))
                continue
            if len(cands) > 1:
                counts["ambiguous"] += 1
                ambiguous_log.append((page, st, mode, f"{inc} ~> {corrected}",
                                      [c[1] for c in cands]))
                updates.append((row_id, None, "ambiguous"))
            else:
                counts["fuzzy"] += 1
                fuzzy_log.append((page, st, mode, inc, corrected, round(ratio, 3),
                                  cands[0][1]))
                updates.append((row_id, cands[0][1], "resolved"))

    print("=" * 72)
    print("RESOLUTION SUMMARY")
    for k in ("resolved", "fuzzy", "ambiguous", "unmatched", "not_mappable",
              "skipped_human"):
        print(f"  {k:18} {counts[k]}")
    print(f"  {'TOTAL':18} {sum(counts.values())}")

    print("\nFUZZY CORRECTIONS (verify these):")
    for page, st, mode, inc, corr, ratio, gid in fuzzy_log:
        print(f"  p{page} {st}/{mode}  {inc!r}  ~>  {corr!r}  (r={ratio})  -> gregobase:{gid}")
    print("\nAMBIGUOUS (left NULL, status=ambiguous):")
    for page, st, mode, inc, gids in ambiguous_log:
        print(f"  p{page} {st}/{mode}  {inc!r}  candidates={gids}")
    print("\nSTILL UNMATCHED (left NULL, status=unmatched):")
    for page, st, mode, inc in unmatched_log:
        print(f"  p{page} {st}/{mode}  {inc!r}")

    if dry_run:
        print("\nDRY-RUN: no rows written.")
        return

    for row_id, gid, status in updates:
        conn.execute(t(
            "UPDATE gr_index_entry SET gregobase_id=:g, match_status=:s WHERE row_id=:r"
        ), {"g": gid, "s": status, "r": row_id})
    conn.commit()
    print(f"\nWrote {len(updates)} rows.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and report, write nothing (and don't add columns)")
    ap.add_argument("--repopulate", action="store_true",
                    help="also re-resolve rows already stamped match_status='reviewed' "
                         "(default: leave human-reviewed rows untouched)")
    args = ap.parse_args(argv)

    engine = lgp.make_engine()
    try:
        with engine.connect() as conn:
            if not args.dry_run:
                ensure_columns(conn)
            resolve_all(conn, args.dry_run, args.repopulate)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
