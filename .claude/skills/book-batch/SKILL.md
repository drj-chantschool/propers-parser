---
name: book-batch
description: One firing of a book's work queue (any book, any stage — index-pages, index-rows, content pages/subsections) — pacing gate, claim a batch, fan out Sonnet producers, review, load, verify, log, raise questions to intake_queue, schedule the next firing. Run as `/loop /book-batch <BOOK_CODE> [stage]`, or headless one batch per fresh session via `tools/queue_driver.py` (which appends `--driven`); with no stage it works the book's next unfinished stage. Queues are created by /book-intake.
argument-hint: <BOOK_CODE> [stage [unit …]] [--driven]
---

# Book queue: one batch

Book and stage: **$ARGUMENTS**

You are the **director** for one batch. This prompt fires repeatedly, from `/loop` wakeups and a
2-hourly safety cron, often into a context that remembers nothing. **Everything you need is in
files; treat your conversation memory as disposable.** Anything the user must know goes into the
stage's log or `intake_queue` before the firing ends.

Golden rule (`.claude/agents/parser-director.md`): every mark on a page must be modeled. Anything a
producer could not model is a **question**, never guessed and never silently dropped.

## Driven mode (`--driven`)

If the last argument is `--driven`, drop it before parsing the rest. This firing was launched by
`tools/queue_driver.py`: a fresh headless session per batch, with the driver owning pacing and
scheduling, and no human watching. Everything below applies, except:

- **No scheduling at all.** Skip steps 1 and 2; never call `CronCreate`/`CronDelete`/`ScheduleWakeup`
  (including step 0's stop cases and step 7.3); never run `Q due`.
- **Dead batch recovery.** The driver runs one firing at a time, so once the stage is picked, if
  `Q status` shows `state.batch_open`, a previous driven run died: `Q batch-end`, then
  `Q log "⏸ driven: batch <id> left open by a dead run; units returned to pending"`, and go on.
- **Stage drained** (step 0 finds `remaining` = 0 for a named stage, or for every stage): do step 2's
  `DONE` bookkeeping (final `Q status` summary in the log, BOOK.md Status row), then report `done`.
- **Nobody reads the chat.** Questions go to `intake_queue` as always; nothing waits on a reply.
- **Result line.** The very last line of your final message is exactly one line:
  `BOOK-BATCH-RESULT {"status": "ran"|"done"|"stop", "book": "<CODE>", "stage": "<stage or null>",
  "queue": "<queue path or null>", "batch_id": <n or null>, "units": {"<u>": "<final status>", …},
  "rows_loaded": <n>, "questions": [<intake ids raised>], "note": "<one line>"}`.
  `ran` = a batch was worked; `done` = nothing left to work in what was asked; `stop` = a stage needs
  `/book-intake`, or bad arguments (say which in `note`). The driver stops on anything but `ran`.

## 0: Orient (every firing)

- Root `C:\Users\johna\liturgio\propers-parser`. Python `..\.venv\Scripts\python.exe`, `PYTHONUTF8=1`.
- Read `<book_dir>/BOOK.md` (the directory is `tools/_db.py:book_dir(<CODE>)`). Its **Stages** row
  for this stage names the queue, producer agent, output path, validate and load/verify commands;
  its **Director instructions** hold everything specific to this book (resolving a unit, review and
  load rules, allowed actions) and win over this file where they overlap. Read no other book's files.
- `Q` = `python tools/work_queue.py --queue <queue path>`. `I` = `python tools/intake.py`.
- Producer: the agent type the Stages row names, model sonnet. If that type isn't registered this
  session (agents are discovered walking UP from the working directory, so a session started outside
  `propers-parser/` may not see `propers-parser/.claude/agents/`), use `general-purpose` with
  `model: "sonnet"` and tell it to Read and follow `propers-parser/.claude/agents/<agent>.md`.

- **Which stage.** The first argument is the book code. If the second matches a stage name in
  BOOK.md's Stages table, that is the stage, and any further arguments are units. Otherwise no stage
  was given (units can only be named after a stage — if there are extra arguments, stop and say so)
  and you pick it: walk the Stages rows **in table order** (it is phase order: `index-pages` →
  `index-rows` → `content`) and take the first whose queue isn't finished, judged with the
  read-only `Q status` (never `Q due` here: it has side effects on a queue you are not running) —
  - queue file exists and `remaining` > 0 → **this is the stage**;
  - queue file exists and `remaining` = 0 → next row (note any `held` units it left, from `Q status`);
  - queue file doesn't exist → stop: that stage hasn't been set up. Tell the user to run
    `/book-intake <CODE>` (it creates the next queue), end the loop (`ScheduleWakeup stop: true`,
    `CronDelete` this prompt's cron if any), and report what is finished;
  - every row at `remaining` = 0 → the book's queues are all drained: same stop, and suggest `/book-intake <CODE>`
    for the completion sweep.
  Say which stage you picked in the batch log line and the summary. Re-resolve on **every** firing:
  the cron and wakeups re-use the prompt exactly as given, so a stage-less loop moves on by itself
  when a stage finishes and the next one already has a queue.

- **Units named in the arguments** (e.g. `/book-batch GRADUALE content pro-papa com-bmv`): a one-off
  run of just those units. If the queue file doesn't exist, create it from them
  (`Q init --book <CODE> --stage <stage> --units-file …` or `--pages …`, as BOOK.md's Stages row
  says); otherwise `Q add` any that aren't queued, and `Q reset` any already finished that should
  be redone. Then `Q claim --units <u …>`, skip steps 1–2 (no cron, no pacing), and don't schedule a next
  firing. With no units named and no queue file, stop and tell the user to run `/book-intake <CODE>`.

## 1: Safety cron

`CronList`. If no job's prompt is `/book-batch $ARGUMENTS`, `CronCreate` with cron `17 */2 * * *`,
that prompt, recurring. Cron jobs expire after 7 days; this renews it. It is how the loop survives a
session-limit stall.

## 2: Pacing gate

`Q due`, then by `action`:
- `WAIT` — `ScheduleWakeup` for `minutes_left`×60 s (min 60), same prompt, `noop: true`; stop.
- `BUSY` — `ScheduleWakeup` 900 s, `noop: true`; stop.
- `DONE` — log a final summary (`Q status`) and update BOOK.md's Status row. If the stage was
  **named**: `CronDelete` this cron, `ScheduleWakeup stop: true`, tell the user, and suggest
  re-running `/book-intake <CODE>` for the next phase. If it was **picked** (no stage given): pick
  again (step 0); if another stage has a live queue, carry on with it in this firing; if not, stop as
  step 0 says.
- `RUN` — continue. `limit_detected: true` means the queue already reset a dead batch, added 5 min
  to the wait and logged it; just carry on.

## 3: Answered questions and blocked units (cheap, no agents)

- `Q status` → `flagged`. For each `held` unit with a `question_id`, `I show <id>`: if it is `done`,
  `Q release --question <id>` (that unit is now pending and may be claimed below). Answered-but-not-
  done questions belong to `/intake-triage`, not to you.
- For each `blocked_dep` unit whose output exists, re-run its validate command; if it now passes,
  load + verify it (step 6) and `Q finish <u> loaded`.

## 4: Claim and fan out

`Q claim` → `units`, `previous_in_lane`. Spawn **one producer per unit in a single message**
(parallel, foreground). Brief:

> Produce the <stage> output for **<BOOK> unit {u}** (book directory `<book_dir>`; read its
> `PRODUCER.md` first). Previous unit in your lane: **{prev}** — its
> output, if present, is `<output path for prev>`; read its carried context first. Output:
> `<output path for u>`. Follow `.claude/agents/<agent>.md` and `<contract README>` exactly. Leave it
> validate-clean; do NOT do a real DB write; do NOT delete `propers-parser/_tmp`.
> {the Stages row's brief extras} {any quirk for this range from the log / README "Known quirks"}

Before spawning, do the cheap pre-flight a producer can't: render the pages (`tools/render_page.py
--book <CODE> …`) and pass the paths; for content units that cite other pages, list the index rows
on each cited page and every same-page collision (LESSONS §6).

## 5: Review each returned output (yours; never skip)

1. Re-run the validate command yourself. Never trust a pasted result.
2. Read the page image and check the output against it, mark by mark: nothing printed is missing,
   nothing continued from the previous unit is duplicated, every option/rubric/cross-reference is
   captured with the right scope.
3. Chant identity: compare each resolved chant (opening words, mode, office-part, and for anything not
   tied to this page, the opening neumes) with the engraving. Any `⚠` line is resolved — a better
   candidate, or an acknowledgement you agree with after looking — or it becomes a question.
4. Small certain fixes (a mode letter, a missed day field, an incipit typo): make them, re-validate.
   Anything that changes **what a chant is or which act it is assigned to** and isn't plain from the
   page: a question.

## 6: Load, verify, record

- Clean → run the load command, then verify (`VERIFY PASS` / re-run dry-run shows all unchanged).
  `Q finish <u> loaded --summary '<last JSON line>'` (or `no_rows` / `done` as the stage defines).
- Questions → write each to a JSON file and `I raise <file>` with `pipeline: "book-batch"`, `book`,
  a `topic_key` (reuse it for the same class of question — `raise` merges into an open row),
  `pages`, `options` (one `recommended`), `context` (the output file, the contract section), and
  `blocks: ["<CODE>:<unit>"]`. Then `Q finish <u> held --question <id> --note "<short>"` and
  `Q log "❓ HELD <u>: intake_queue #<id> <title>"`.
- Waiting on another unit (a cited Common not loaded yet) → `Q finish <u> blocked_dep --note "…"`.
- Error you can't fix → `Q finish <u> error --note "…"` and `Q log "⛔ <u>: …"`.

Also `Q log` any ⚠ you accepted, and anything structural you created (an epoch, a saint, a
placeholder `local_chants` row). New tables, columns or `service_part` rows are schema changes: hold
and ask. When the same producer mistake shows up twice, add a one-line rule to the contract README's
"Known quirks" and log that you did.

## 7: Close

1. `Q log "batch <id>: <u> <status> (<n> rows), …"` — one line for the batch.
2. `Q batch-end` → `wait_minutes`.
3. `ScheduleWakeup` `delaySeconds` = `wait_minutes`×60, prompt `/book-batch $ARGUMENTS`,
   `noop: false`, reason like "next <BOOK> <stage> batch in 20 min".
4. A 2–4 line summary for the user: units done, rows loaded, questions raised.

## Session limits

A firing cut short leaves the batch open; the next firing's `Q due` marks it stale, returns its
units to pending and adds 5 min to the wait. Loads are idempotent upserts, so a half-finished unit is
simply redone. Don't adjust the wait by hand except on the user's word (`Q bump-wait N`).
