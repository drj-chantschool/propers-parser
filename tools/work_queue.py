#!/usr/bin/env python
"""work_queue.py — file-backed work queue + pacing state for any book and any pipeline stage.

Generalizes the Liber Hymnarius page queue (which ran 200 batches to completion, 2026-10-18).
One queue file per (book, stage), e.g. lhymn/queues/pages.json, graduale/queues/index-rows.json.
Never hand-edit a queue file; every command rewrites it atomically.

UNITS are strings: a printed page ("245"), an index page ("i612"), a chant_indices row_id
("r5561"), a subsection slug ("OT-OT-14"). Each unit belongs to a LANE. With strict lanes
(default) a lane is worked strictly in order, one unit at a time, so a unit's predecessor is
always finished before it is claimed (producers read the predecessor's spec context_out).
With --unordered, a claim takes any pending units regardless of order (independent units such
as index rows). A unit may also list `after` dependencies (ids that must be done first).

    Q = python tools/work_queue.py --queue <book_dir>/queues/<stage>.json

    Q init --book B --stage S (--pages "1-130,177-244" | --units-file F) [--lane NAME] [--unordered]
           [--skip "131-176:Ps 94 tones"] [--batch-size 3] [--wait 20] [--log PATH] [--force]
    Q add (--pages … | --units-file F) [--lane NAME]   append units (e.g. a second lane)
    Q due              → {"action": RUN|WAIT|BUSY|DONE, ...}; detects session-limit hits
    Q claimable        read-only: the units a claim would take now (an open batch counts as dead)
    Q claim [--n N]    claim the next units (one per lane if strict), start a batch
    Q claim --units U…   claim exactly these pending units (one-off run)
    Q finish UNIT STATUS [--note ..] [--summary JSON] [--question ID]
                       STATUS: done | loaded | no_rows | held | blocked_dep | error | pending
                       held + --question links the unit to its intake_queue row
    Q release --question ID   put every unit held on that intake question back to pending
    Q batch-end        close the batch, next_due = now + wait
    Q reset UNIT       back to pending
    Q status           read-only: remaining (pending + claimed), counts, lane heads, flagged units, pacing
    Q list [--status S]   unit ids (optionally filtered)
    Q log TEXT         append a timestamped line to the queue's log (markdown)
    Q bump-wait [MIN]  wait_minutes += MIN (default 5)

--units-file: one unit per line: `id[<TAB>lane[<TAB>after1,after2]]`; '#' comments allowed.

Run `finish --summary '<json>'` from the Bash tool, not PowerShell 5.1 (it strips the inner
double quotes before the argument reaches python, and json.loads fails).
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

from _db import PP_ROOT

STALE_MINUTES = 60          # a batch open longer than this died (session limit / crash)
MISSED_SLACK_MINUTES = 30   # a wakeup this late was missed (session limit)
DONE = {"done", "loaded", "no_rows", "skipped"}
STATUSES = ["done", "loaded", "no_rows", "held", "blocked_dep", "error", "pending"]


def now():
    return dt.datetime.now().replace(microsecond=0)


def iso(t):
    return t.isoformat() if t else None


def parse(s):
    return dt.datetime.fromisoformat(s) if s else None


class Queue:
    def __init__(self, path):
        self.path = path if os.path.isabs(path) else os.path.join(PP_ROOT, path)

    def load(self):
        with open(self.path, encoding="utf-8") as f:
            self.q = json.load(f)
        return self.q

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.q, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)

    def log(self, msg):
        rel = self.q["meta"].get("log")
        if not rel:
            return
        path = rel if os.path.isabs(rel) else os.path.join(PP_ROOT, rel)
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if new:
                m = self.q["meta"]
                f.write(f"# {m['book']} — {m['stage']} log\n\nAppend-only. Newest at the bottom. "
                        "`❓ HELD` = waiting on an intake_queue answer; `⛔` = error; "
                        "`⏸` = session-limit backoff.\n\n")
            f.write(f"- {now():%Y-%m-%d %H:%M} — {msg}\n")


def expand_pages(spec):
    """'1-3,7' → ['1','2','3','7']; a letter prefix is kept: 'i608-i610' → ['i608','i609','i610']."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"([A-Za-z]*)(\d+)-\1?(\d+)", part)
        if m:
            out += [f"{m[1]}{p}" for p in range(int(m[2]), int(m[3]) + 1)]
        elif part:
            out.append(part)
    return out


def read_units(a, default_lane):
    """[(id, lane, after)] from --pages or --units-file."""
    rows = []
    if a.pages:
        rows = [(u, default_lane, []) for u in expand_pages(a.pages)]
    elif a.units_file:
        with open(a.units_file, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].rstrip("\n")
                if not line.strip():
                    continue
                cols = line.split("\t")
                lane = cols[1].strip() if len(cols) > 1 and cols[1].strip() else default_lane
                after = [x.strip() for x in cols[2].split(",")] if len(cols) > 2 and cols[2].strip() else []
                rows.append((cols[0].strip(), lane, after))
    else:
        sys.exit("give --pages or --units-file")
    return rows


def add_units(q, rows):
    for uid, lane, after in rows:
        if uid in q["units"]:
            sys.exit(f"unit {uid} already queued")
        q["units"][uid] = {"lane": lane, "status": "pending"}
        if after:
            q["units"][uid]["after"] = after
        q["lanes"].setdefault(lane, []).append(uid)


def cmd_init(Q, a):
    if os.path.exists(Q.path) and not a.force:
        sys.exit(f"{Q.path} exists (use --force to rebuild)")
    Q.q = {"meta": {"book": a.book, "stage": a.stage, "created": iso(now()), "log": a.log},
           "config": {"wait_minutes": a.wait, "batch_size": a.batch_size, "stale_minutes": STALE_MINUTES,
                      "strict_lanes": not a.unordered},
           "state": {"batch_id": 0, "batch_open": False, "batch_started": None, "batch_finished": None,
                     "next_due": None, "limit_hits": 0, "batch_units": []},
           "lanes": {}, "units": {}}
    add_units(Q.q, read_units(a, a.lane))
    for s in a.skip or []:
        rng, _, why = s.partition(":")
        for u in expand_pages(rng):
            e = Q.q["units"].setdefault(u, {"lane": None})
            e.update(status="skipped", note=why or "skipped")
            for lane in Q.q["lanes"].values():
                if u in lane:
                    lane.remove(u)
    Q.save()
    print(f"initialised {len(Q.q['units'])} units in {len(Q.q['lanes'])} lane(s) → {Q.path}")


def cmd_add(Q, a):
    Q.load()
    rows = read_units(a, a.lane)
    add_units(Q.q, rows)
    Q.save()
    print(f"added {len(rows)} units")


def remaining(q):
    return sum(1 for v in q["units"].values() if v["status"] in ("pending", "claimed"))


def cmd_due(Q, a):
    q = Q.load()
    s, c, t = q["state"], q["config"], now()
    limit = None
    if s["batch_open"] and parse(s["batch_started"]) < t - dt.timedelta(minutes=c["stale_minutes"]):
        limit = f"batch {s['batch_id']} open since {s['batch_started']} never finished"
        for u in s["batch_units"]:
            if q["units"][u]["status"] == "claimed":
                q["units"][u]["status"] = "pending"
        s["batch_open"] = False
    elif (not s["batch_open"] and s["next_due"]
          and t > parse(s["next_due"]) + dt.timedelta(minutes=MISSED_SLACK_MINUTES)):
        limit = f"wakeup due {s['next_due']} was missed"
    if limit:
        c["wait_minutes"] += 5
        s["limit_hits"] += 1
        s["next_due"] = iso(t)
        Q.log(f"⏸ session limit inferred ({limit}); wait between batches → {c['wait_minutes']} min")
        Q.save()
    if s["batch_open"]:
        out = {"action": "BUSY", "batch_id": s["batch_id"], "since": s["batch_started"]}
    elif s["next_due"] and t < parse(s["next_due"]):
        out = {"action": "WAIT", "minutes_left": round((parse(s["next_due"]) - t).seconds / 60, 1),
               "next_due": s["next_due"]}
    else:
        out = {"action": "RUN"}
    out.update(wait_minutes=c["wait_minutes"], limit_detected=bool(limit), remaining=remaining(q))
    if out["remaining"] == 0:
        out["action"] = "DONE"
    print(json.dumps(out))


def deps_done(q, uid):
    return all(q["units"].get(d, {}).get("status") in DONE for d in q["units"][uid].get("after", []))


def pick(q, n):
    """The units the next `claim` (no --units) would take, and each one's predecessor in its lane."""
    strict = q["config"].get("strict_lanes", True)
    claimed, prev = [], {}
    for lane, order in q["lanes"].items():
        for i, u in enumerate(order):
            if len(claimed) >= n:
                break
            st = q["units"][u]["status"]
            if st == "pending" and deps_done(q, u):
                claimed.append(u)
                prev[u] = order[i - 1] if i else None
                if strict:
                    break
            elif strict and st in ("pending", "claimed"):
                break  # lane busy, or head blocked on a dependency
    return claimed, prev


def cmd_claimable(Q, a):
    """Read-only: what a claim would take now. A batch left open is treated as dead (its claimed
    units counted as pending), as a driven firing's batch-end would make it."""
    q = Q.load()
    if q["state"]["batch_open"]:
        for u in q["state"]["batch_units"]:
            if q["units"][u]["status"] == "claimed":
                q["units"][u]["status"] = "pending"
    units, _ = pick(q, q["config"]["batch_size"])
    print(json.dumps({"book": q["meta"]["book"], "stage": q["meta"]["stage"], "units": units,
                      "remaining": remaining(q), "batch_open": q["state"]["batch_open"]}))


def cmd_claim(Q, a):
    q = Q.load()
    s = q["state"]
    if s["batch_open"]:
        sys.exit(f"batch {s['batch_id']} still open — run batch-end or due first")
    n = a.n or q["config"]["batch_size"]
    claimed, prev = [], {}
    if a.units:   # a one-off run of named units, ignoring lane order and batch size
        for u in a.units:
            if u not in q["units"]:
                sys.exit(f"no unit {u} (Q add it first)")
            if q["units"][u]["status"] != "pending":
                sys.exit(f"unit {u} is {q['units'][u]['status']} (Q reset it first)")
            order = q["lanes"].get(q["units"][u]["lane"], [])
            i = order.index(u) if u in order else 0
            claimed.append(u)
            prev[u] = order[i - 1] if i else None
    if not a.units:
        claimed, prev = pick(q, n)
    s["batch_id"] += 1
    for u in claimed:
        q["units"][u].update(status="claimed", batch=s["batch_id"], claimed_at=iso(now()))
    s.update(batch_open=bool(claimed), batch_started=iso(now()), batch_units=claimed)
    Q.save()
    print(json.dumps({"batch_id": s["batch_id"], "units": claimed, "previous_in_lane": prev,
                      "lanes": {u: q["units"][u]["lane"] for u in claimed}}))


def cmd_finish(Q, a):
    q = Q.load()
    if a.unit not in q["units"]:
        sys.exit(f"no unit {a.unit}")
    e = q["units"][a.unit]
    e.update(status=a.status, finished_at=iso(now()))
    if a.note:
        e["note"] = a.note
    if a.summary:
        e["summary"] = json.loads(a.summary)
    if a.question:
        e["question_id"] = a.question
    Q.save()
    print(f"{a.unit} → {a.status}")


def cmd_release(Q, a):
    q = Q.load()
    hit = [u for u, e in q["units"].items() if e.get("question_id") == a.question and e["status"] == "held"]
    for u in hit:
        q["units"][u]["status"] = "pending"
    Q.save()
    if hit:
        Q.log(f"↩ intake_queue #{a.question} answered: released {', '.join(hit)} to pending")
    print(json.dumps({"released": hit}))


def cmd_batch_end(Q, a):
    q = Q.load()
    s, c, t = q["state"], q["config"], now()
    s.update(batch_open=False, batch_finished=iso(t), next_due=iso(t + dt.timedelta(minutes=c["wait_minutes"])))
    left = [u for u in s["batch_units"] if q["units"][u]["status"] == "claimed"]
    for u in left:
        q["units"][u]["status"] = "pending"
    Q.save()
    print(json.dumps({"next_due": s["next_due"], "wait_minutes": c["wait_minutes"], "returned_to_pending": left}))


def cmd_reset(Q, a):
    q = Q.load()
    q["units"][a.unit]["status"] = "pending"
    Q.save()
    print(f"{a.unit} → pending")


def cmd_status(Q, a):
    q = Q.load()
    counts = {}
    for v in q["units"].values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    heads = {lane: next((u for u in order if q["units"][u]["status"] not in DONE), "done")
             for lane, order in q["lanes"].items()}
    flagged = {u: {k: v.get(k) for k in ("status", "note", "question_id") if v.get(k)}
               for u, v in q["units"].items() if v["status"] in ("held", "blocked_dep", "error")}
    print(json.dumps({"meta": q["meta"], "remaining": remaining(q), "counts": counts, "lane_heads": heads, "flagged": flagged,
                      "config": q["config"], "state": q["state"]}, indent=1, ensure_ascii=False))


def cmd_list(Q, a):
    q = Q.load()
    for u, v in q["units"].items():
        if not a.status or v["status"] == a.status:
            print(u)


def cmd_log(Q, a):
    Q.load()
    Q.log(" ".join(a.text))
    print("logged")


def cmd_bump(Q, a):
    q = Q.load()
    q["config"]["wait_minutes"] += a.minutes
    Q.save()
    print(q["config"]["wait_minutes"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--queue", required=True, help="queue JSON path (absolute or relative to propers-parser/)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    def units_args(p):
        p.add_argument("--pages", help='ranges, e.g. "1-130,177-244" or "i608-i619"')
        p.add_argument("--units-file")
        p.add_argument("--lane", default="A")

    p = sp.add_parser("init"); units_args(p)
    p.add_argument("--book", required=True); p.add_argument("--stage", required=True)
    p.add_argument("--unordered", action="store_true"); p.add_argument("--skip", action="append")
    p.add_argument("--batch-size", type=int, default=3); p.add_argument("--wait", type=int, default=20)
    p.add_argument("--log"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_init)
    p = sp.add_parser("add"); units_args(p); p.set_defaults(f=cmd_add)
    sp.add_parser("due").set_defaults(f=cmd_due)
    sp.add_parser("claimable").set_defaults(f=cmd_claimable)
    p = sp.add_parser("claim"); p.add_argument("--n", type=int)
    p.add_argument("--units", nargs="+", help="claim exactly these units (one-off run)"); p.set_defaults(f=cmd_claim)
    p = sp.add_parser("finish"); p.add_argument("unit"); p.add_argument("status", choices=STATUSES)
    p.add_argument("--note"); p.add_argument("--summary"); p.add_argument("--question", type=int)
    p.set_defaults(f=cmd_finish)
    p = sp.add_parser("release"); p.add_argument("--question", type=int, required=True); p.set_defaults(f=cmd_release)
    sp.add_parser("batch-end").set_defaults(f=cmd_batch_end)
    p = sp.add_parser("reset"); p.add_argument("unit"); p.set_defaults(f=cmd_reset)
    sp.add_parser("status").set_defaults(f=cmd_status)
    p = sp.add_parser("list"); p.add_argument("--status"); p.set_defaults(f=cmd_list)
    p = sp.add_parser("log"); p.add_argument("text", nargs="+"); p.set_defaults(f=cmd_log)
    p = sp.add_parser("bump-wait"); p.add_argument("minutes", nargs="?", type=int, default=5); p.set_defaults(f=cmd_bump)
    a = ap.parse_args()
    a.f(Queue(a.queue), a)


if __name__ == "__main__":
    main()
