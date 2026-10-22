#!/usr/bin/env python
"""intake.py — raise, claim and resolve questions in liturgio.intake_queue (answered at /intake).

The protocol and JSON column shapes are in liturgio-tools/sql/make-intake-queue.sql. In short:
open → (human answers at /intake) → answered → claimed (by one agent, atomically) → done.

    I = python tools/intake.py

    I raise FILE.json        insert a question; if an OPEN row has the same topic_key, append this
                             one's pages/blocks/chants to it instead (prints {"question_id", "merged"})
    I list [--status open|answered|claimed|done|withdrawn] [--pipeline P] [--book B]
    I show ID                the full row as JSON
    I claim-next [--pipeline P] [--by NAME]
                             atomically claim the oldest highest-priority ANSWERED row → full row JSON
                             (skipping rows whose follow-up — parent_id = it, or refs naming it
                             {"table": "intake_queue", "pk": {"question_id": N}} — is not done yet),
                             or {"question_id": null} when there is nothing to do
    I claimable [--pipeline P]          read-only: ids claim-next could take now → {"question_ids": [...]}
    I resolve ID --resolution TEXT      claimed → done
    I unclaim ID                        claimed → answered (you could not carry it out)
    I withdraw ID [--parent N]          open → withdrawn (retracted, or folded into question N)

FILE.json for `raise` (pipeline, category, title, prompt, raised_by required):
    {"pipeline": "book-batch", "book": "LIBER_HYMNARIUS", "category": "modeling",
     "topic_key": "lh-compline-per-annum", "priority": 3,
     "title": "...", "prompt": "self-contained question; what is loaded, what waits on it",
     "pages":   [{"book": "LIBER_HYMNARIUS", "page": "241", "note": "..."}],
     "chants":  [{"chant_uuid": "gregobase:18100", "note": "..."}],
     "options": [{"label": "...", "detail": "...", "recommended": true}],
     "refs":    [{"table": "chant_indices", "pk": {"row_id": 5561}, "note": "..."}],
     "context": [{"label": "Spec", "path": "propers-parser/lhymn/specs/p0241.json"}],
     "blocks":  ["LIBER_HYMNARIUS:241"],
     "raised_by": "book-batch director, LIBER_HYMNARIUS pages batch 197",
     "parent_id": null}   (set it for a follow-up to, or a split of, another question)
Give enough context that an agent with no memory of your session can act on the answer.
"""
import argparse
import json
import sys

from sqlalchemy import text

from _db import engine

JSON_COLS = ["pages", "chants", "options", "refs", "context", "blocks"]
REQUIRED = ["pipeline", "category", "title", "prompt", "raised_by"]


def row_json(r):
    d = dict(r._mapping)
    for k in JSON_COLS:
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()}


def cmd_raise(a):
    q = json.load(open(a.file, encoding="utf-8"))
    missing = [k for k in REQUIRED if not q.get(k)]
    if missing:
        sys.exit(f"missing {missing}")
    with engine(rw=True).begin() as c:
        if q.get("topic_key"):
            hit = c.execute(text("SELECT question_id FROM intake_queue WHERE topic_key=:t AND status='open' "
                                 "ORDER BY question_id LIMIT 1 FOR UPDATE"), {"t": q["topic_key"]}).scalar()
            if hit:
                for k in ("pages", "blocks", "chants"):
                    for el in q.get(k, []):
                        c.execute(text(f"UPDATE intake_queue SET {k} = JSON_ARRAY_APPEND({k}, '$', CAST(:v AS JSON)) "
                                       "WHERE question_id=:id"), {"v": json.dumps(el), "id": hit})
                c.execute(text("UPDATE intake_queue SET priority = priority + :n WHERE question_id=:id"),
                          {"n": max(len(q.get("blocks", [])), 1), "id": hit})
                print(json.dumps({"question_id": hit, "merged": True}))
                return
        cols = ["pipeline", "book", "category", "topic_key", "priority", "title", "prompt", "raised_by",
                "parent_id"] + JSON_COLS
        vals = {k: q.get(k) for k in cols}
        vals["priority"] = vals["priority"] or 0
        for k in JSON_COLS:
            vals[k] = json.dumps(q.get(k, []), ensure_ascii=False)
        c.execute(text(f"INSERT INTO intake_queue ({', '.join(cols)}) VALUES ("
                       + ", ".join(f"CAST(:{k} AS JSON)" if k in JSON_COLS else f":{k}" for k in cols) + ")"), vals)
        print(json.dumps({"question_id": c.execute(text("SELECT LAST_INSERT_ID()")).scalar(), "merged": False}))


def cmd_list(a):
    where, p = ["1=1"], {}
    for k in ("status", "pipeline", "book"):
        if getattr(a, k):
            where.append(f"{k} = :{k}")
            p[k] = getattr(a, k)
    with engine().connect() as c:
        for r in c.execute(text("SELECT question_id, status, priority, pipeline, book, category, topic_key, title "
                                f"FROM intake_queue WHERE {' AND '.join(where)} "
                                "ORDER BY priority DESC, raised_at"), p):
            print("\t".join(str(x) for x in r))


def cmd_show(a):
    with engine().connect() as c:
        r = c.execute(text("SELECT * FROM intake_queue WHERE question_id=:i"), {"i": a.id}).first()
    print(json.dumps(row_json(r) if r else None, indent=1, ensure_ascii=False))


def claimable_cond(pipeline):
    cond = "status='answered'" + (" AND pipeline=:p" if pipeline else "")
    # an answered question with an unfinished follow-up (child) waits for it: the child's answer completes it
    # … or one that an unfinished question lists in its refs ({"table": "intake_queue", "pk": {"question_id": N}})
    return cond + (" AND NOT EXISTS (SELECT 1 FROM intake_queue ch WHERE ch.status IN ('open','answered','claimed') "
                   "AND (ch.parent_id=intake_queue.question_id OR JSON_CONTAINS(ch.refs, "
                   "JSON_OBJECT('table','intake_queue','pk',JSON_OBJECT('question_id',intake_queue.question_id)))))")


def cmd_claimable(a):
    with engine().connect() as c:
        ids = [r[0] for r in c.execute(text(f"SELECT question_id FROM intake_queue WHERE {claimable_cond(a.pipeline)} "
                                            "ORDER BY priority DESC, answered_at"), {"p": a.pipeline})]
    print(json.dumps({"question_ids": ids}))


def cmd_claim_next(a):
    with engine(rw=True).begin() as c:
        cond = claimable_cond(a.pipeline)
        for (qid,) in c.execute(text(f"SELECT question_id FROM intake_queue WHERE {cond} "
                                     "ORDER BY priority DESC, answered_at LIMIT 10"), {"p": a.pipeline}).all():
            n = c.execute(text("UPDATE intake_queue SET status='claimed', claimed_by=:me, claimed_at=NOW() "
                               "WHERE question_id=:i AND status='answered'"), {"me": a.by, "i": qid}).rowcount
            if n:   # rowcount 0 ⇒ another agent got it first
                r = c.execute(text("SELECT * FROM intake_queue WHERE question_id=:i"), {"i": qid}).first()
                print(json.dumps(row_json(r), indent=1, ensure_ascii=False))
                return
    print(json.dumps({"question_id": None}))


def transition(qid, frm, sets, params):
    with engine(rw=True).begin() as c:
        n = c.execute(text(f"UPDATE intake_queue SET {sets} WHERE question_id=:i AND status='{frm}'"),
                      dict(params, i=qid)).rowcount
    if not n:
        sys.exit(f"question {qid} is not {frm}")
    print(f"#{qid} updated")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("raise"); p.add_argument("file"); p.set_defaults(f=cmd_raise)
    p = sp.add_parser("list")
    for k in ("status", "pipeline", "book"):
        p.add_argument(f"--{k}")
    p.set_defaults(f=cmd_list)
    p = sp.add_parser("show"); p.add_argument("id", type=int); p.set_defaults(f=cmd_show)
    p = sp.add_parser("claim-next"); p.add_argument("--pipeline"); p.add_argument("--by", default="intake-triage")
    p.set_defaults(f=cmd_claim_next)
    p = sp.add_parser("claimable"); p.add_argument("--pipeline"); p.set_defaults(f=cmd_claimable)
    p = sp.add_parser("resolve"); p.add_argument("id", type=int); p.add_argument("--resolution", required=True)
    p.set_defaults(f=lambda a: transition(a.id, "claimed", "status='done', resolution=:r, resolved_at=NOW()",
                                          {"r": a.resolution}))
    p = sp.add_parser("unclaim"); p.add_argument("id", type=int)
    p.set_defaults(f=lambda a: transition(a.id, "claimed", "status='answered', claimed_by=NULL, claimed_at=NULL", {}))
    p = sp.add_parser("withdraw"); p.add_argument("id", type=int); p.add_argument("--parent", type=int)
    p.set_defaults(f=lambda a: transition(a.id, "open", "status='withdrawn', parent_id=:p", {"p": a.parent}))
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
