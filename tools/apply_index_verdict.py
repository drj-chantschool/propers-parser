#!/usr/bin/env python
"""apply_index_verdict.py — write one reviewed index-row-resolver verdict to chant_indices.

    python tools/apply_index_verdict.py <book_dir>/index/resolve/r5561.json            # dry-run
    python tools/apply_index_verdict.py … --commit [--apply-index-fix]
    python tools/apply_index_verdict.py … --verify

verdict → chant_indices:
    link         chant_uuid = <uuid>, match_status = 'resolved_with_difficulty' (a judgment link)
    group        chant_group_id = <id>, chant_uuid NULL, 'resolved_with_difficulty': the chant is identified
                 but no single edition fits better than its group siblings (books that allow it, e.g. OCO)
    unmatched    match_status = 'unmatched' (chant_uuid untouched)
    ambiguous    match_status = 'ambiguous' — raise the verdict's `question` with tools/intake.py
    index_error  nothing, unless --apply-index-fix: then the `index_fix` column change (page /
                 mode / incipit / section_type), and the link too if the verdict carries one
Only rows whose match_status is NULL/unmatched/ambiguous are written: 'resolved', 'reviewed' and
'resolved_with_difficulty' rows are curated and never overwritten here. The chant_uuid must exist.
"""
import argparse
import json
import sys

from sqlalchemy import text

from _db import engine

STATUS = {"link": "resolved_with_difficulty", "group": "resolved_with_difficulty", "unmatched": "unmatched", "ambiguous": "ambiguous"}
FIXABLE = {"page", "mode", "incipit", "section_type"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--apply-index-fix", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    v = json.load(open(a.file, encoding="utf-8"))
    rid, verdict, uuid = v["row_id"], v["verdict"], v.get("chant_uuid")
    eng = engine(rw=a.commit)
    with (eng.begin() if a.commit else eng.connect()) as c:
        row = c.execute(text("SELECT row_id, chant_uuid, chant_group_id, match_status, page, mode, incipit, section_type "
                             "FROM chant_indices WHERE row_id=:i"), {"i": rid}).first()
        if row is None:
            sys.exit(f"no chant_indices row {rid}")
        want_status = STATUS.get(verdict) or ("resolved_with_difficulty" if uuid else None)
        if a.verify:
            ok = row.match_status == want_status and (verdict not in ("link",) or row.chant_uuid == uuid) and                 (verdict != "group" or row.chant_group_id == v.get("chant_group_id"))
            print(f"{'VERIFY PASS' if ok else 'VERIFY FAIL'}: row {rid} status={row.match_status} uuid={row.chant_uuid}")
            sys.exit(0 if ok else 1)
        if row.match_status not in (None, "unmatched", "ambiguous"):
            sys.exit(f"row {rid} is already {row.match_status} ({row.chant_uuid}) — curated, not overwriting")
        sets = {}
        if verdict == "index_error":
            fix = v.get("index_fix") or {}
            if not a.apply_index_fix:
                sys.exit(f"index_error on row {rid}: {fix} — review it, then re-run with --apply-index-fix")
            if fix.get("column") not in FIXABLE or getattr(row, fix["column"]) != (
                    int(fix["from"]) if fix["column"] == "mode" and fix.get("from") not in (None, "") else fix.get("from")):
                sys.exit(f"index_fix {fix} doesn't match the row as it stands: {dict(row._mapping)}")
            sets[fix["column"]] = fix["to"]
        if uuid and verdict in ("link", "index_error"):
            kind, _, ident = uuid.partition(":")
            exists = (c.execute(text("SELECT 1 FROM gregobase_chants WHERE id=:i"), {"i": ident}).first() if kind == "gregobase"
                      else c.execute(text("SELECT 1 FROM local_chants WHERE local_chant_id=:i"), {"i": ident}).first())
            if not exists:
                sys.exit(f"{uuid} does not exist")
            sets["chant_uuid"] = uuid
        if verdict == "group":
            gid = v.get("chant_group_id")
            if not gid or not c.execute(text("SELECT 1 FROM chant_group WHERE chant_group_id=:g"), {"g": gid}).first():
                sys.exit(f"group verdict needs an existing chant_group_id, got {gid!r}")
            sets["chant_group_id"] = gid
        if want_status:
            sets["match_status"] = want_status
        print(f"row {rid}: " + ", ".join(f"{k}: {getattr(row, k)!r} → {val!r}" for k, val in sets.items()))
        if verdict == "ambiguous" and v.get("question"):
            print("  ↳ raise the verdict's question with tools/intake.py raise")
        if a.commit and sets:
            c.execute(text("UPDATE chant_indices SET " + ", ".join(f"{k}=:{k}" for k in sets) + " WHERE row_id=:rid"),
                      {**sets, "rid": rid})
    print(json.dumps({"row_id": rid, "verdict": verdict, "commit": a.commit}))


if __name__ == "__main__":
    main()
