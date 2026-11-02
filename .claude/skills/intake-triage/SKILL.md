---
name: intake-triage
description: Claim ONE answered row from liturgio.intake_queue, carry out the user's answer if it is unambiguous, release the work units it was blocking, and mark it done. Normally fired by `tools/queue_driver.py` (as `/intake-triage --driven`) ahead of any book batch; by hand, `/intake-triage` or `/loop 5m /intake-triage`.
argument-hint: [--driven]
---

# Intake triage: one answered question

The user answers parser questions at `/intake` in liturgio-api (with the cited pages in view).
Your job is to make an answer **happen**. Protocol and column shapes:
`liturgio-tools/sql/make-intake-queue.sql`; helper `tools/intake.py` (below, `I`). Root
`C:\Users\johna\liturgio\propers-parser`, Python `..\.venv\Scripts\python.exe`, `PYTHONUTF8=1`.

1. **Claim.** `I claim-next --by "intake-triage <date time>"`. `{"question_id": null}` → nothing
   answered; end with `noop` (under `/loop`, just stop). The claim is atomic: never work a row you
   didn't claim.
2. **Understand.** Read the whole row: `prompt`, `answer`, `options` (the answer often picks one),
   `pages` (render them: `python tools/render_page.py --book <book> <page>`), `chants`, `refs`, and
   every `context` path (the spec, the contract README section, the log entry). Read the pipeline's
   contract README and the book's `BOOK.md`.
3. **Decide whether it is unambiguous.** You can act when the answer, read with the question, says
   exactly what to change. If it doesn't (it answers a different question, contradicts a recorded
   ruling, or needs a choice it leaves open), do NOT guess: `I unclaim <id>`, then raise a follow-up
   with `parent_id` = this question (`I raise`), quoting the answer and asking the narrower thing.
   Stop.
4. **Carry it out.** Typical changes: edit the held spec(s) and dry-run / load / `--verify` them with
   the book's loader (its `BOOK.md` says how to load and verify); fix a `chant_indices` row (then repoint already-loaded
   `lit_part_sources` rows — loaders never overwrite `chant_uuid`); create a
   placeholder local chant (`chants` row `chant_uuid='local:<uuid>'`, `elements='[]'`); a loader change. Schema/API changes get a `../maintenance.md` entry.
5. **Standing rule?** If `is_standing_rule=1` (or the answer is plainly general), add it to the
   contract README's "User rulings" with the date and `intake_queue #<id>`, and to the book's
   memory file if one exists.
6. **Release.** For each entry in `blocks` (`<BOOK>:<unit>`): `python tools/work_queue.py --queue
   <book_dir>/queues/<stage>.json release --question <id>` (the unit goes back to pending; if you
   already loaded it yourself, `finish <unit> loaded` instead). Log a line in that queue's log:
   `✅ intake_queue #<id> resolved: <what changed>`.
7. **Close.** `I resolve <id> --resolution "<what you changed, where: files, rows, text_ids>"`.
   One question per firing.

## Driven mode (`$ARGUMENTS` is `--driven`)

Fired by `tools/queue_driver.py`, a fresh headless session with nobody reading the chat. The same
steps, except:
- Claim with exactly `I claim-next --by "intake-triage driven"`. The driver runs one session at a
  time and returns any row still claimed under that name to `answered` after a session dies.
- Never wait on the user; anything unclear goes through step 3's follow-up question.
- The very last line of your final message is exactly one line:
  `INTAKE-TRIAGE-RESULT {"status": "resolved"|"unclaimed"|"none"|"error", "question_id": <id or null>,
  "followup_id": <id raised in step 3, or null>, "released": ["<BOOK>:<unit>", …], "note": "<one line>"}`.
