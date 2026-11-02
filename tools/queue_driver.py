#!/usr/bin/env python
"""queue_driver.py — one terminal, one usage budget, every parser queue: each job runs in a fresh
headless Claude session, paced to hit a target share of the weekly usage limit.

JOBS, picked deterministically (no session is started to find out there is nothing to do):
  1. intake triage — `intake.py claimable` (the exact claim-next condition) has an answered question
     → `claude -p "/intake-triage --driven"`. Always first.
  2. a book batch — every `*/BOOK.md` Stages table, in table order per book: the first stage whose
     queue has `remaining` > 0 is that book's stage (a missing queue file = the book needs
     /book-intake; it is skipped and reported once). If `work_queue.py claimable` would claim units
     there → `claude -p "/book-batch <CODE> <stage> --driven"`. Among books with work, the one
     driven least recently goes first.
  Nothing to do → sleep --idle-poll minutes and look again (or exit with --exit-when-idle).

PACING. `/usage` runs headless for free, so the driver samples it before and after every job and
every --repoll minutes while waiting. Calibration, from all logged jobs:
    k_week    = Σ Δweek%    / Σ cost_usd   (pairs whose pre/post samples share a reset window)
    k_session = Σ Δsession% / Σ cost_usd
    cost_est  = median cost_usd of the last 10 successful jobs with this job key (e.g. `OCO:conflicts`,
                `triage`), else of this kind, else of any
--week-target is PRO-RATED over the week: it is the share of what should be left that may be used,
    cap = 100 − (100 − target)·f      f = hours left to the weekly reset / 168
so --week-target 70 caps week% at 70 when the week starts and at 97 with 10% of it left. At or over
the cap, jobs wait until the cap has risen past week%. Below it, the account may spend target% of
what is left, (target/100)·(100 − week%), over the hours left, so jobs start
every k_week·cost_est / allowed_rate hours. A job is also held until the 5-hour session reset when
session% + k_session·cost_est would pass --session-cap (default = --week-target: the same
share of every 5-hour window stays yours as of the week). Until there is calibration data (Σ cost <
$CALIB_MIN_USD), jobs are --initial-wait apart. Week% is account-wide, so your other use counts
against the target; that is the point (it leaves your headroom alone).

FAILURES. A job key that fails --max-failures times in a row, or reports `stop` (needs a human, e.g.
/book-intake), is dropped for the rest of the run. Rows left claimed under `intake-triage driven`
are returned to `answered` at start-up and after a triage job that didn't finish.

Everything goes to SQLite (--db, default propers-parser/driver/queue_driver.sqlite): runs,
usage_samples, batches (one row per job, with the full `claude -p` JSON), decisions (every pacing
computation and its inputs), events. Touch propers-parser/driver/STOP to stop cleanly.

    python tools/queue_driver.py run --week-target 60 [--session-cap N] [--books OCO,GRADUALE]
           [--no-triage] [--exit-when-idle] [--model opus] [--max-jobs N] [--once] [--dry-run]
    python tools/queue_driver.py jobs            what each queue would do now (read-only)
    python tools/queue_driver.py usage           sample /usage now, print it
    python tools/queue_driver.py report [--n 20] recent jobs + current calibration

Run it from a plain terminal or Task Scheduler, not as a Claude background task (it would die
with that session).
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from _db import PP_ROOT, engine
from work_queue import Queue, pick, remaining

DRIVER_DIR = os.path.join(PP_ROOT, "driver")
DEFAULT_DB = os.path.join(DRIVER_DIR, "queue_driver.sqlite")
STOP_FILE = os.path.join(DRIVER_DIR, "STOP")
TRIAGE_BY = "intake-triage driven"   # the claimed_by name the triage skill uses in driven mode
CALIB_MIN_USD = 15.0        # Σ job cost needed before k_week / k_session are trusted
CALIB_WINDOW = 40           # most recent jobs used for calibration
LIMIT_PCT = 99              # a usage line at/above this means the limit was hit
RESET_SLACK = dt.timedelta(minutes=3)
WEEK_HOURS = 168.0
OK_STATUSES = {"ran", "done", "resolved", "unclaimed", "none"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY, started TEXT, ended TEXT, end_reason TEXT,
  book TEXT, stage TEXT, argv TEXT, config_json TEXT);
CREATE TABLE IF NOT EXISTS usage_samples (
  id INTEGER PRIMARY KEY, run_id INTEGER, ts TEXT, phase TEXT,
  session_pct REAL, session_resets TEXT, week_pct REAL, week_resets TEXT,
  lines_json TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS batches (
  id INTEGER PRIMARY KEY, run_id INTEGER, book TEXT, stage_arg TEXT, prompt TEXT,
  started TEXT, ended TEXT, duration_s REAL, exit_code INTEGER, timed_out INTEGER,
  is_error INTEGER, api_error_status TEXT, session_id TEXT,
  cost_usd REAL, input_tokens INTEGER, output_tokens INTEGER,
  cache_read_tokens INTEGER, cache_create_tokens INTEGER, num_turns INTEGER,
  subagents_spawned INTEGER, permission_denials INTEGER, model_usage_json TEXT,
  status TEXT, stage TEXT, queue TEXT, queue_batch_id INTEGER, units_json TEXT,
  rows_loaded INTEGER, questions_json TEXT, note TEXT,
  pre_sample_id INTEGER, post_sample_id INTEGER,
  result_tail TEXT, stderr_tail TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY, run_id INTEGER, ts TEXT, after_batch_id INTEGER, sample_id INTEGER,
  week_pct REAL, session_pct REAL, hours_to_week_reset REAL,
  k_week REAL, k_session REAL, calib_usd REAL, cost_est REAL,
  pred_week_delta REAL, pred_session_delta REAL, allowed_rate REAL,
  interval_s REAL, next_due TEXT, rule TEXT, inputs_json TEXT);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, run_id INTEGER, ts TEXT, kind TEXT, detail TEXT);
"""
MIGRATIONS = {  # columns added after the first schema: table → [(column, type)]
    "batches": [("kind", "TEXT"), ("job_key", "TEXT"), ("planned_units_json", "TEXT")],
    "decisions": [("job_key", "TEXT")],
}


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.isoformat() if t else None


def parse(s):
    return dt.datetime.fromisoformat(s) if s else None


def say(msg):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


class DB:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.c = sqlite3.connect(path)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r[1] for r in self.c.execute(f"PRAGMA table_info({table})")}
            for col, typ in cols:
                if col not in have:
                    self.c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        self.c.commit()
        self.run_id = None

    def insert(self, table, **cols):
        cur = self.c.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             list(cols.values()))
        self.c.commit()
        return cur.lastrowid

    def update(self, table, rid, **cols):
        self.c.execute(f"UPDATE {table} SET {', '.join(k + '=?' for k in cols)} WHERE id=?", [*cols.values(), rid])
        self.c.commit()

    def event(self, kind, detail=""):
        say(f"{kind}: {detail}")
        self.insert("events", run_id=self.run_id, ts=iso(now()), kind=kind,
                    detail=detail if isinstance(detail, str) else json.dumps(detail))


# ---------------------------------------------------------------- jobs

@dataclass
class Job:
    kind: str                 # 'triage' | 'book'
    key: str                  # 'triage' | '<CODE>:<stage>'
    prompt: str
    book: str = None
    stage: str = None
    detail: dict = field(default_factory=dict)


def books():
    """[(code, [(stage, queue_abs_path)])] from every <book_dir>/BOOK.md, stages in table order."""
    out = []
    for path in sorted(glob.glob(os.path.join(PP_ROOT, "*", "BOOK.md"))):
        md = open(path, encoding="utf-8").read()
        code = re.search(r"^\|\s*Book code\s*\|\s*`([^`]+)`", md, re.M)
        sec = re.search(r"^## Stages.*?\n(.*?)(?=^## |\Z)", md, re.M | re.S)
        if not code or not sec:
            continue
        stages = []
        for line in sec[1].splitlines():
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) < 2 or cols[0] in ("Stage", "") or set(cols[0]) <= set("-: "):
                continue
            q = re.search(r"`([^`]+\.json)`", cols[1])
            if q:
                stages.append((cols[0].strip("`"), os.path.join(PP_ROOT, q[1])))
        out.append((code[1], stages))
    return out


def book_jobs(only=None):
    """→ (jobs with claimable units, notes about books with nothing to do and why)."""
    jobs, notes = [], {}
    for code, stages in books():
        if only and code not in only:
            continue
        for stage, qpath in stages:
            if not os.path.exists(qpath):
                notes[code] = f"stage {stage}: no queue file (needs /book-intake {code})"
                break
            q = Queue(qpath).load()
            if remaining(q) == 0:
                continue
            if q["state"]["batch_open"]:  # driver runs one job at a time: an open batch is dead
                for u in q["state"]["batch_units"]:
                    if q["units"][u]["status"] == "claimed":
                        q["units"][u]["status"] = "pending"
            units, _ = pick(q, q["config"]["batch_size"])
            if units:
                jobs.append(Job("book", f"{code}:{stage}", f"/book-batch {code} {stage} --driven", code, stage,
                                {"units": units, "remaining": remaining(q), "queue": os.path.relpath(qpath, PP_ROOT)}))
            else:
                notes[code] = f"stage {stage}: {remaining(q)} remaining, none claimable (held/blocked)"
            break
        else:
            notes.setdefault(code, "all stages drained")
    return jobs, notes


def triage_ids():
    from intake import claimable_cond
    from sqlalchemy import text
    with engine().connect() as c:
        return [r[0] for r in c.execute(text(f"SELECT question_id FROM intake_queue WHERE {claimable_cond(None)} "
                                             "ORDER BY priority DESC, answered_at"))]


def release_dead_triage_claims(db):
    from sqlalchemy import text
    try:
        with engine(rw=True).begin() as c:
            ids = [r[0] for r in c.execute(text("SELECT question_id FROM intake_queue WHERE status='claimed' "
                                                "AND claimed_by=:b"), {"b": TRIAGE_BY})]
            if ids:
                c.execute(text("UPDATE intake_queue SET status='answered', claimed_by=NULL, claimed_at=NULL "
                               "WHERE status='claimed' AND claimed_by=:b"), {"b": TRIAGE_BY})
        if ids:
            db.event("triage_unclaimed", f"returned dead driven claims to answered: {ids}")
    except Exception as e:  # noqa: BLE001
        db.event("triage_unclaim_error", repr(e))


def pick_job(db, a, dropped, quiet=False):
    """The next job, or None. Triage first; then the least recently driven book key."""
    if not a.no_triage and "triage" not in dropped:
        try:
            ids = triage_ids()
            if ids:
                return Job("triage", "triage", "/intake-triage --driven", detail={"question_ids": ids})
        except Exception as e:  # noqa: BLE001 — MySQL down shouldn't stop book work
            db.event("triage_check_error", repr(e))
    jobs, notes = book_jobs(a.books)
    jobs = [j for j in jobs if j.key not in dropped]
    if not quiet:
        for code, why in notes.items():
            if db.notes.get(code) != why:
                db.notes[code] = why
                db.event("book_idle", f"{code}: {why}")
    if not jobs:
        return None
    last_run = {r[0]: r[1] for r in db.c.execute("SELECT job_key, MAX(started) FROM batches GROUP BY job_key")}
    return min(jobs, key=lambda j: last_run.get(j.key) or "")


# ---------------------------------------------------------------- /usage

CLAUDE = shutil.which("claude") or "claude"
USAGE_LINE = re.compile(r"^(Current [^:\n]+):\s*(\d+(?:\.\d+)?)% used(?:\s*·\s*resets\s+(.+?)\s*\(([^)]+)\))?\s*$", re.M)
RESET_TEXT = re.compile(r"(?:([A-Z][a-z]{2})\w*\.? (\d{1,2}),?\s*)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)", re.I)
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def parse_reset(text, tzname):
    """'Oct 27, 5pm' / '10:30pm' in tzname → aware UTC datetime, or None."""
    m = RESET_TEXT.search(text or "")
    if not m:
        return None
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = dt.datetime.now().astimezone().tzinfo
    local = dt.datetime.now(tz)
    hour = int(m[3]) % 12 + (12 if m[5].lower() == "pm" else 0)
    t = local.replace(hour=hour, minute=int(m[4] or 0), second=0, microsecond=0)
    if m[1]:
        t = t.replace(month=MONTHS[m[1].lower()[:3]], day=int(m[2]))
        if t < local - dt.timedelta(days=1):
            t = t.replace(year=t.year + 1)
    elif t < local - dt.timedelta(hours=1):
        t += dt.timedelta(days=1)
    return t.astimezone(dt.timezone.utc)


def sample_usage(db, phase):
    """Run headless /usage (0 tokens), store and return the sample row as a dict."""
    try:
        p = subprocess.run([CLAUDE, "-p", "/usage", "--output-format", "json"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=180,
                           env={**os.environ, "MSYS_NO_PATHCONV": "1"})
        raw = json.loads(p.stdout).get("result", "") if p.stdout.strip().startswith("{") else p.stdout
    except Exception as e:  # noqa: BLE001 — a failed sample must not kill the run
        db.event("usage_error", repr(e))
        return None
    lines = {}
    for label, pct, reset_txt, tzname in USAGE_LINE.findall(raw):
        r = parse_reset(reset_txt, tzname) if reset_txt else None
        lines[label.strip()] = {"pct": float(pct), "resets": iso(r), "resets_text": reset_txt or None}
    sess = next((v for k, v in lines.items() if k.startswith("Current session")), {})
    week = lines.get("Current week (all models)") or next(
        (v for k, v in lines.items() if k.startswith("Current week")), {})
    row = dict(run_id=db.run_id, ts=iso(now()), phase=phase,
               session_pct=sess.get("pct"), session_resets=sess.get("resets"),
               week_pct=week.get("pct"), week_resets=week.get("resets"),
               lines_json=json.dumps(lines), raw=raw)
    row["id"] = db.insert("usage_samples", **row)
    row["lines"] = lines
    if row["week_pct"] is None:
        db.event("usage_unparsed", raw[:500])
    return row


# ---------------------------------------------------------------- calibration + pacing

def calibration(db, job=None):
    rows = db.c.execute("""
        SELECT b.cost_usd, a.session_pct s0, z.session_pct s1, a.session_resets sr0, z.session_resets sr1,
               a.week_pct w0, z.week_pct w1, a.week_resets wr0, z.week_resets wr1
        FROM batches b JOIN usage_samples a ON a.id=b.pre_sample_id JOIN usage_samples z ON z.id=b.post_sample_id
        WHERE b.cost_usd > 0 ORDER BY b.id DESC LIMIT ?""", (CALIB_WINDOW,)).fetchall()

    def same_window(r0, r1):  # reset times can wobble by a minute between samples
        return r0 and r1 and abs((parse(r0) - parse(r1)).total_seconds()) < 600

    wk = [(r["w1"] - r["w0"], r["cost_usd"]) for r in rows
          if r["w0"] is not None and r["w1"] is not None and same_window(r["wr0"], r["wr1"])]
    ss = [(r["s1"] - r["s0"], r["cost_usd"]) for r in rows
          if r["s0"] is not None and r["s1"] is not None and same_window(r["sr0"], r["sr1"])]
    usd_w, usd_s = sum(c for _, c in wk), sum(c for _, c in ss)
    ok = "status IN (%s) AND cost_usd > 0" % ",".join(f"'{s}'" for s in OK_STATUSES)
    costs, basis = [], None
    for basis, where, arg in [("job", "job_key=?", job and job.key), ("kind", "kind=?", job and job.kind),
                              ("any", "1=?", 1)]:
        if arg is None:
            continue
        costs = [r[0] for r in db.c.execute(
            f"SELECT cost_usd FROM batches WHERE {ok} AND {where} ORDER BY id DESC LIMIT 10", (arg,))]
        if costs:
            break
    return {
        "k_week": max(sum(d for d, _ in wk), 0) / usd_w if usd_w >= CALIB_MIN_USD else None,
        "k_session": max(sum(d for d, _ in ss), 0) / usd_s if usd_s >= CALIB_MIN_USD else None,
        "calib_usd": round(min(usd_w, usd_s), 2), "n_week_pairs": len(wk), "n_session_pairs": len(ss),
        "cost_est": statistics.median(costs) if costs else None, "n_costs": len(costs),
        "cost_basis": basis if costs else None,
    }


def week_cap(target, hours_left):
    """Pro-rated week% cap: `target`% of what should be left, 100 − (100 − target)·(share of week left)."""
    f = min(max(hours_left / WEEK_HOURS, 0.0), 1.0)
    return 100 - (100 - target) * f


def plan(db, a, u, last, job):
    """→ (next_due, rule, decision dict). `last` is the previous job row of this run, or None."""
    t = now()
    cal = calibration(db, job)
    d = dict(week_pct=u and u["week_pct"], session_pct=u and u["session_pct"], job_key=job.key, **cal)
    week_reset, sess_reset = parse(u and u["week_resets"]), parse(u and u["session_resets"])
    d["hours_to_week_reset"] = (week_reset - t).total_seconds() / 3600 if week_reset else None
    nd, rule = None, None

    if u is None or u["week_pct"] is None:
        nd, rule = t + dt.timedelta(minutes=a.initial_wait), "no usage reading: initial wait"
    else:
        # hard limits on any line (incl. per-model weekly lines)
        for label, v in u["lines"].items():
            if v["pct"] >= LIMIT_PCT and v["resets"]:
                cand = parse(v["resets"]) + RESET_SLACK
                if not nd or cand > nd:
                    nd, rule = cand, f"{label} at {v['pct']}%: wait for reset"
    h = d["hours_to_week_reset"]
    d["week_cap"] = week_cap(a.week_target, h) if h is not None else a.week_target
    if nd is None and u["week_pct"] >= d["week_cap"]:
        if week_reset:
            # the cap reaches week% when the share of week left falls to (100 − week%)/(100 − target)
            f_ok = (100 - u["week_pct"]) / (100 - a.week_target) if a.week_target < 100 else 0.0
            nd = max(week_reset - dt.timedelta(hours=f_ok * WEEK_HOURS), t + dt.timedelta(minutes=a.repoll))
        else:
            nd = t + dt.timedelta(hours=6)
        rule = (f"week ≥ pro-rated cap: {u['week_pct']}% ≥ {d['week_cap']:.1f}% "
                f"({a.week_target}% of what's left), wait for the cap to rise")
    if nd is None and cal["cost_est"] and cal["k_session"] is not None and u["session_pct"] is not None:
        d["pred_session_delta"] = cal["k_session"] * cal["cost_est"]
        if u["session_pct"] + d["pred_session_delta"] > a.session_cap and sess_reset:
            nd, rule = sess_reset + RESET_SLACK, (f"session {u['session_pct']}% + {d['pred_session_delta']:.1f} "
                                                  f"> cap {a.session_cap}%: wait for session reset")
    if nd is None:
        if last is None:
            nd, rule = t, "first job of run"
        elif cal["k_week"] is None or not cal["cost_est"] or not d["hours_to_week_reset"]:
            nd = parse(last["ended"]) + dt.timedelta(minutes=a.initial_wait)
            rule = f"uncalibrated (Σ${cal['calib_usd']} < ${CALIB_MIN_USD}): initial wait"
        else:
            d["pred_week_delta"] = cal["k_week"] * cal["cost_est"]
            d["allowed_rate"] = a.week_target / 100 * (100 - u["week_pct"]) / d["hours_to_week_reset"]   # %/h
            d["interval_s"] = d["pred_week_delta"] / d["allowed_rate"] * 3600
            start_to_start = parse(last["started"]) + dt.timedelta(seconds=d["interval_s"])
            lo = parse(last["ended"]) + dt.timedelta(minutes=a.min_wait)
            hi = parse(last["ended"]) + dt.timedelta(minutes=a.max_wait)
            nd = min(max(start_to_start, lo), hi)
            rule = (f"paced: {d['pred_week_delta']:.2f}%/job at {d['allowed_rate']:.2f}%/h allowed "
                    f"→ every {d['interval_s'] / 60:.0f} min" + (" (clamped)" if nd != start_to_start else ""))
    db.insert("decisions", run_id=db.run_id, ts=iso(t), after_batch_id=last and last["id"], job_key=job.key,
              sample_id=u and u["id"], week_pct=d["week_pct"], session_pct=d["session_pct"],
              hours_to_week_reset=d["hours_to_week_reset"], k_week=cal["k_week"], k_session=cal["k_session"],
              calib_usd=cal["calib_usd"], cost_est=cal["cost_est"], pred_week_delta=d.get("pred_week_delta"),
              pred_session_delta=d.get("pred_session_delta"), allowed_rate=d.get("allowed_rate"),
              interval_s=d.get("interval_s"), next_due=iso(nd), rule=rule, inputs_json=json.dumps(d))
    return nd, rule, d


def sleep_until(t):
    """Sleep until t, checking for the STOP file every minute. → False if STOP appeared."""
    while now() < t:
        if os.path.exists(STOP_FILE):
            return False
        time.sleep(max(1, min((t - now()).total_seconds(), 60)))
    return not os.path.exists(STOP_FILE)


def next_job(db, a, last, dropped):
    """Wait until some job is due. → (job, fresh usage sample), or (None, reason) to end the run.
    The job is re-picked at every re-poll, so an answered question jumps the line, and the plan is
    recomputed for whichever job is next."""
    shown = None
    while True:
        job = pick_job(db, a, dropped)
        if job is None:
            if a.exit_when_idle:
                return None, "idle"
            if shown != "idle":
                say(f"nothing to do; checking every {a.idle_poll:g} min")
                shown = "idle"
            if not sleep_until(now() + dt.timedelta(minutes=a.idle_poll)):
                return None, "STOP file"
            continue
        u = sample_usage(db, "pre")
        nd, rule, _ = plan(db, a, u, last, job)
        if nd <= now():
            return job, u
        # print only real changes: the plan drifts a minute per re-poll as the hours left to the reset
        # shrink (every re-plan is still in `decisions`)
        kind = (job.key, rule.split(":")[0])
        if not isinstance(shown, tuple) or shown[0] != kind or abs((nd - shown[1]).total_seconds()) > 600:
            say(f"next: {job.key} at {nd.astimezone():%a %H:%M} — {rule}")
            shown = (kind, nd)
        if not sleep_until(min(nd, now() + dt.timedelta(minutes=a.repoll))):
            return None, "STOP file"


# ---------------------------------------------------------------- one job

SENTINEL = re.compile(r"(?:BOOK-BATCH|INTAKE-TRIAGE)-RESULT\s+(\{.*\})")


def run_job(db, a, job, pre):
    cmd = [CLAUDE, "-p", job.prompt, "--output-format", "json", "--permission-mode", a.permission_mode,
           "--permission-prompts", "none"] + (["--model", a.model] if a.model else [])
    started = now()
    bid = db.insert("batches", run_id=db.run_id, kind=job.kind, job_key=job.key, book=job.book,
                    stage_arg=job.stage, prompt=job.prompt, started=iso(started), pre_sample_id=pre and pre["id"],
                    planned_units_json=json.dumps(job.detail))
    say(f"job #{bid}: {job.prompt}  {json.dumps(job.detail)[:200]}")
    out, err, code, timed_out = "", "", None, 0
    try:
        p = subprocess.run(cmd, cwd=PP_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=a.timeout * 60, env={**os.environ, "PYTHONUTF8": "1", "MSYS_NO_PATHCONV": "1"})
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err, timed_out = (e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")), 1
    ended = now()
    try:
        j = json.loads(out)
    except ValueError:
        j = {}
    usage = j.get("usage") or {}
    result = j.get("result") or ""
    m = SENTINEL.findall(result)
    try:
        sent = json.loads(m[-1]) if m else {}
    except ValueError:
        sent = {}
    post = sample_usage(db, "post")
    questions = sent.get("questions") if job.kind == "book" else \
        [x for x in (sent.get("question_id"), sent.get("followup_id")) if x]
    db.update("batches", bid, ended=iso(ended), duration_s=(ended - started).total_seconds(), exit_code=code,
              timed_out=timed_out, is_error=int(bool(j.get("is_error")) or not j),
              api_error_status=str(j.get("api_error_status")) if j.get("api_error_status") else None,
              session_id=j.get("session_id"), cost_usd=j.get("total_cost_usd"),
              input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
              cache_read_tokens=usage.get("cache_read_input_tokens"),
              cache_create_tokens=usage.get("cache_creation_input_tokens"), num_turns=j.get("num_turns"),
              subagents_spawned=(j.get("subagent_stats") or {}).get("spawned"),
              permission_denials=len(j.get("permission_denials") or []),
              model_usage_json=json.dumps(j.get("modelUsage")) if j else None,
              status=sent.get("status") or ("timeout" if timed_out else "error" if not j or j.get("is_error")
                                            else "no_result_line"),
              stage=sent.get("stage"), queue=sent.get("queue"), queue_batch_id=sent.get("batch_id"),
              units_json=json.dumps(sent.get("units") or sent.get("released")) if sent else None,
              rows_loaded=sent.get("rows_loaded"), questions_json=json.dumps(questions) if sent else None,
              note=sent.get("note"), post_sample_id=post and post["id"], result_tail=result[-4000:],
              stderr_tail=err[-4000:], raw_json=out if j else out[-20000:])
    if j.get("permission_denials"):
        db.event("permission_denials", json.dumps(j["permission_denials"])[:4000])
    row = db.c.execute("SELECT * FROM batches WHERE id=?", (bid,)).fetchone()
    if job.kind == "triage" and row["status"] not in OK_STATUSES:
        release_dead_triage_claims(db)
    say(f"job #{bid} {job.key} → {row['status']} in {row['duration_s'] / 60:.0f} min, ${row['cost_usd'] or 0:.2f}; "
        f"{row['units_json'] or ''} {row['note'] or ''}; week {pre and pre['week_pct']}→{post and post['week_pct']}%, "
        f"session {pre and pre['session_pct']}→{post and post['session_pct']}%")
    return row, post


# ---------------------------------------------------------------- commands

def cmd_run(db, a):
    lock = acquire_lock()
    if a.session_cap is None:
        a.session_cap = a.week_target
    db.run_id = db.insert("runs", started=iso(now()), book=",".join(a.books or []) or None,
                          argv=json.dumps(sys.argv), config_json=json.dumps({k: v for k, v in vars(a).items() if k != "f"}))
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    last, n, reason = None, 0, None
    fails, dropped = {}, set()
    try:
        if a.dry_run:
            job = pick_job(db, a, dropped)
            if job is None:
                print("nothing to do")
            else:
                u = sample_usage(db, "dry")
                nd, rule, d = plan(db, a, u, db.c.execute(
                    "SELECT * FROM batches WHERE ended IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone(), job)
                print(json.dumps({"job": job.__dict__, "usage": u and u["lines"], "next_due": iso(nd),
                                  "rule": rule, **d}, indent=1))
            reason = "dry_run"
            return
        if not a.no_triage:
            release_dead_triage_claims(db)
        while True:
            if a.max_jobs and n >= a.max_jobs:
                reason = f"max_jobs {a.max_jobs}"
                break
            if a.once:
                job = pick_job(db, a, dropped)
                if job is None:
                    reason = "idle"
                    break
                pre = sample_usage(db, "pre")
            else:
                job, pre = next_job(db, a, last, dropped)
                if job is None:
                    reason = pre
                    break
            row, post = run_job(db, a, job, pre)
            n += 1
            last = row
            if row["status"] in OK_STATUSES:
                fails[job.key] = 0
            elif row["status"] == "stop":
                dropped.add(job.key)
                db.event("job_dropped", f"{job.key} reported stop: {row['note']}")
            elif post and any(v["pct"] >= LIMIT_PCT for v in post["lines"].values()):
                db.event("limit_hit", f"job #{row['id']} {row['status']}; the plan waits for the reset")
            else:
                fails[job.key] = fails.get(job.key, 0) + 1
                db.event("job_failed", f"#{row['id']} {job.key} {row['status']} ({fails[job.key]}/{a.max_failures}): "
                                       f"{(row['result_tail'] or row['stderr_tail'] or '')[-300:]}")
                if fails[job.key] >= a.max_failures:
                    dropped.add(job.key)
                    db.event("job_dropped", f"{job.key} after {fails[job.key]} consecutive failures")
            if a.once:
                reason = "once"
                break
    except KeyboardInterrupt:
        reason = "interrupted"
    finally:
        db.update("runs", db.run_id, ended=iso(now()), end_reason=reason)
        say(f"run {db.run_id} ended: {reason}")
        lock.close()


def acquire_lock():
    os.makedirs(DRIVER_DIR, exist_ok=True)
    f = open(os.path.join(DRIVER_DIR, "driver.lock"), "a+")
    f.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another queue_driver is running (driver/driver.lock is held)")
    return f


def cmd_jobs(db, a):
    try:
        ids = triage_ids()
    except Exception as e:  # noqa: BLE001
        ids = f"unavailable: {e!r}"
    print(f"triage: answered questions claimable now: {ids}")
    jobs, notes = book_jobs(a.books)
    for j in jobs:
        print(f"{j.key}: would claim {j.detail['units']} ({j.detail['remaining']} remaining)")
    for code, why in notes.items():
        print(f"{code}: {why}")


def cmd_usage(db, a):
    u = sample_usage(db, "manual")
    print(json.dumps(u and u["lines"], indent=1))


def cmd_report(db, a):
    rows = db.c.execute("""SELECT b.id, b.started, b.job_key, b.status, round(b.duration_s/60) min,
        round(b.cost_usd, 2) usd, b.subagents_spawned ag, b.rows_loaded rows, b.units_json,
        a.week_pct w0, z.week_pct w1, a.session_pct s0, z.session_pct s1
        FROM batches b LEFT JOIN usage_samples a ON a.id=b.pre_sample_id
        LEFT JOIN usage_samples z ON z.id=b.post_sample_id ORDER BY b.id DESC LIMIT ?""", (a.n,)).fetchall()
    for r in reversed(rows):
        print(f"#{r['id']:<4} {r['started'][:16]} {r['job_key'] or '-':<22} {r['status'] or 'running':<14}"
              f" {r['min'] or 0:>4}m ${r['usd'] or 0:>6} ag={r['ag'] or 0} rows={r['rows'] or 0}"
              f" week {r['w0']}→{r['w1']} sess {r['s0']}→{r['s1']}  {r['units_json'] or ''}")
    print("calibration:", json.dumps(calibration(db)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=DEFAULT_DB)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def books_arg(p):
        p.add_argument("--books", type=lambda s: [b.strip() for b in s.split(",") if b.strip()],
                       help="only these book codes (comma-separated); default all")

    p = sp.add_parser("run"); books_arg(p)
    p.add_argument("--week-target", type=float, required=True, help="share (%%) of what should be left of the week that may be used: pro-rated cap "
                        "100 − (100 − T)·(share of week left), e.g. 70 → 70%% at week start, 97%% with 10%% left")
    p.add_argument("--session-cap", type=float,
                   help="don't start a job that would pass this session%% (default: --week-target, so each "
                        "5-hour window leaves you the same headroom as the week)")
    p.add_argument("--no-triage", action="store_true", help="don't run /intake-triage jobs")
    p.add_argument("--exit-when-idle", action="store_true", help="exit instead of polling when nothing is claimable")
    p.add_argument("--idle-poll", type=float, default=10, help="minutes between looks for work when idle")
    p.add_argument("--initial-wait", type=float, default=30, help="minutes between jobs until calibrated")
    p.add_argument("--min-wait", type=float, default=2, help="minutes")
    p.add_argument("--max-wait", type=float, default=360, help="minutes (between jobs, outside reset waits)")
    p.add_argument("--repoll", type=float, default=15, help="minutes between re-picks and /usage samples while waiting")
    p.add_argument("--timeout", type=float, default=180, help="minutes before a job's session is killed")
    p.add_argument("--max-jobs", type=int)
    p.add_argument("--max-failures", type=int, default=3, help="consecutive failures before a job key is dropped")
    p.add_argument("--model", help="director model (default: your Claude Code default)")
    p.add_argument("--permission-mode", default="auto")
    p.add_argument("--once", action="store_true", help="run the next job now, no pacing")
    p.add_argument("--dry-run", action="store_true", help="pick the next job, print the pacing decision, run nothing")
    p.set_defaults(f=cmd_run)
    p = sp.add_parser("jobs"); books_arg(p); p.set_defaults(f=cmd_jobs)
    sp.add_parser("usage").set_defaults(f=cmd_usage)
    p = sp.add_parser("report"); p.add_argument("--n", type=int, default=20); p.set_defaults(f=cmd_report)
    a = ap.parse_args()
    db = DB(a.db)
    db.notes = {}
    a.f(db, a)


if __name__ == "__main__":
    main()
