# Audit Brief

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN AUDIT BRIEF ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with a
clone of `lHollandl/direct-democracy-ca`. You are the **auditor** for
the trial named in the sandbox name (`ddc-demo-NN-audit` → trial
`demo-NN`, branch `demo/NN`). Run `git switch demo/NN` and confirm with
`git branch --show-current` before anything else.

You did not build this code. Your only loyalty is to CLAUDE.md,
DEMOCRACY.md, DATABASE.md, and ARCHITECTURE.md. You **fix nothing**.
You write one file, the report, under `audits/`, and one paragraph in
HISTORY.md. Anything else you change is a `HIGH` finding against you.

## Read first, in this order, in full (AUDIT.md §3)

1. `AUDIT.md` — your procedure. Every check in §4, every severity in §5, the report structure in §6.
2. `CLAUDE.md` — the constitution.
3. `briefs/demo-NN.md` — what the build was told to build.
4. `HISTORY.md` — the build run's entry: what it says it built, every decision it recorded, every claim it made.
5. `TODO.md` — the ids it marked done.
6. `DEMOCRACY.md`, `DATABASE.md`, `ARCHITECTURE.md` — in full.
7. The code: every file in `git diff main...demo/NN --stat`, then the modules they call.

Do **not** read any earlier `audits/demo-NN-audit-*.md` until your own
findings list is written; then read them and add a section "Previously
reported, still present" for anything silently dropped.

## Step 0 — Pre-checks (paste the output of each)

1. `git branch --show-current` — must be `demo/NN`.
2. `git status` — must be clean before you start.
3. `ls audits/` — your report is `audits/demo-NN-audit-K.md` where K is one more than the highest existing K for this trial (1 if none).
4. Write-protection check: `touch backend/AUDIT_WRITE_TEST && echo WRITABLE || echo READ-ONLY`. If `WRITABLE`, delete the file immediately, note in the report that the source was writable, and rely on your own discipline — `git diff main...HEAD --stat` at the end must show nothing outside `audits/` and `HISTORY.md`, and the director checks this from the host.
5. `docker compose up -d` and `alembic upgrade foundation@head && alembic upgrade iteration@head` from an empty database — you build your own database; you do not reuse the build run's.
6. `curl -sS $OLLAMA_BASE_URL/api/tags` — if unreachable, run the suite with the mocked client and say so.

## What you do (AUDIT.md §4)

Work through §4.1 to §4.6 in order. For every check, either record a
finding or list it under "Checks passed" — silence is not allowed.

You run, and paste in the evidence log:
- the full test suite;
- `backend/scripts/verify_schema.py`;
- `backend/scripts/reconcile.py --dry-run`;
- `python -m backend.seed --dry-run` (must report zero pending writes);
- `grep -rn "TODO\|FIXME" backend/ frontend/src/`;
- `grep -rn "os.environ" backend/ | grep -v settings_env.py`;
- `grep -rn "except:\s*$\|except: pass\|except Exception: pass" backend/`;
- your **own** full-cycle walkthrough through the API with `curl` or the test client — the same cycle as the build brief's "done" list, re-done from scratch, every response pasted. You do not trust the build's paste;
- a hash round-trip: fetch a summary's JSON, recompute SHA-256 locally, compare;
- three hand-derived `threshold()` cases compared with the code's output;
- every page in ARCHITECTURE §9 with the backend running, and once more with images blocked;
- `git diff main...HEAD --stat` at the very end, showing only `audits/` and `HISTORY.md`.

Specific traps to look for are listed in AUDIT.md §4.1. Two are always
`CRITICAL` and you check them first: a ballot vote returned to anyone
but its voter, and any code path where a vote's weight depends on
anything but the voter's choice.

## What you write

`audits/demo-NN-audit-K.md`, exactly the structure in AUDIT.md §6:
Summary with counts and verdict (`CLEAN` / `FIX REQUIRED`), Findings
(each with severity, `path::symbol`, the document section, what it
requires, what the code does, pasted evidence, one-sentence suggested
fix), Evidence log, Checks passed, Document ambiguities.

Document ambiguities are places you could not tell whether the code or
the document is right. Do not resolve them; list them for the director.

## What you must not do

- Fix anything. Not a typo, not a comment, not a failing test.
- Edit any file outside `audits/` except to append your HISTORY.md paragraph.
- Edit TODO.md — list ids that are marked done but fail a check in the report instead.
- Read the previous audit before forming your own list.
- Open a pull request, push to `main`, or declare a keeper.
- Ask for approval or stop early because the code is bad. A bad build is a long report, not a short run.

## At the end

1. Append one paragraph to HISTORY.md (format in CLAUDE.md):
   `## YYYY-MM-DD — Session N (Claude Code audit — demo-NN, run K)`
   with the report path, the counts by severity, and the verdict. Use
   today's date from the system clock. Findings live in the report, not
   here.
2. `git add audits/ HISTORY.md && git commit -m "audit demo-NN run K" && git push origin demo/NN`.
3. Do not open a pull request.

[[[ END AUDIT BRIEF ]]]
