# Audit Brief — change audits

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN AUDIT BRIEF ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with a
clone of `lHollandl/direct-democracy-ca`. You are the **auditor** for
the change named in the sandbox name (`ddc-change-NN-audit` → change
`NN`). Its branch is the one remote branch matching `change/NN-*`: run
`git fetch origin && git branch -r --list 'origin/change/NN-*'`, then
`git switch <that branch> && git merge --ff-only origin/<that branch>`,
and confirm with `git log --oneline -3` that you are at its newest
commit (the clone may carry a stale local branch — SANDBOX.md §6.2).

You did not build this code. Your only loyalty is to CLAUDE.md,
DEMOCRACY.md, DATABASE.md, and ARCHITECTURE.md. You **fix nothing**.
You write one file, the report, under `audits/`, and one paragraph in
HISTORY.md. Anything else you change is a `HIGH` finding against you.

**The documents changed in the same run as the code.** That is the
method (CLAUDE.md, The Two Halves), not a violation. It gives you one
extra duty: for every document edit in the diff, confirm it matches the
verbatim wording in the change's brief(s), character for character, and
that no other line of a protected document moved. A document edit the
briefs do not carry is a `HIGH`.

## Read first, in this order, in full (AUDIT.md §3)

1. `AUDIT.md` — your procedure: §2 scope, every check in §4, severities in §5, the report in §6.
2. `CLAUDE.md` — the constitution.
3. `briefs/change-NN.md` and every `briefs/change-NN-fix-*.md` — what the runs were told to do.
4. `HISTORY.md` — every entry since the last merge to `main`: planning entries, build entries, every decision recorded, every claim made.
5. `TODO.md` — the ids marked done.
6. `DEMOCRACY.md`, `DATABASE.md`, `ARCHITECTURE.md` — in full, as they stand on this branch.
7. The code: every file in `git diff origin/main...HEAD --stat`, then the modules they call.

Do **not** read any earlier `audits/change-NN-audit-*.md` until your own
findings list is written; then read them and add "Previously reported,
still present" for anything silently dropped.

## Scope (AUDIT.md §2) — decide it, and say which you ran and why

- List the diff's files by half (DATABASE §2 tables; ARCHITECTURE §6 and
  §9 F/I marks). **Any Foundation file in the diff → the Foundation
  audit is full**, every §4 check, not only the touched files.
- For Iteration: every touched file and every document section the
  briefs name. If the diff strays outside what the briefs named, full
  pass on Iteration too.
- **Re-audit:** if this change already has a report and the last build
  run was a fix run, first re-verify every earlier finding by running
  the platform, then compare the fix run's diff with the files those
  findings named. Inside them → the re-audit is the audit. Outside →
  the scope above as well.

## Step 0 — Pre-checks (paste the output of each)

1. `git branch --show-current`; `git status` — clean.
2. `ls audits/` — your report is `audits/change-NN-audit-K.md`, K one more than the highest existing K for this change (1 if none).
3. Write-protection check: `touch backend/AUDIT_WRITE_TEST && echo WRITABLE || echo READ-ONLY`. If `WRITABLE`, delete it at once, note it in the report, and rely on your own discipline — the closing diff must show nothing outside `audits/` and `HISTORY.md`.
4. `.env` from `.env.example` with `OLLAMA_BASE_URL` at the host LAN address (SANDBOX.md §5); `docker compose --env-file .env -f infra/docker-compose.yml up -d`; `alembic upgrade foundation@head && alembic upgrade iteration@head` from an **empty** database — you build your own; seed.
5. `curl -sS $OLLAMA_BASE_URL/api/tags`. The only address the sandbox policy allows is the one SANDBOX.md §5 records as the host's LAN address — read it there and use it; do not guess gateways or `host.docker.internal` (change-01 audit 1 did, and audited without Ollama). Only if that exact address fails, run with the mocked client, say so, and list what could not be exercised.

## What you do (AUDIT.md §4)

Work through §4.1 to §4.6 within your scope. For every check, record a
finding or list it under "Checks passed" — silence is not allowed.

Two checks are always first and always `CRITICAL`: a ballot vote
returned to anyone but its voter, and any path where a vote's weight
depends on anything but the voter's choice. Then the §4.1 traps,
including: a name stored, hashed, or published instead of resolved at
read time; an edit that rewrites a hashed row; **and any code path that
deletes a row carrying a `content_hash`** (Law 6 names no exception —
paste every `delete` in `backend/` outside tests with the table it
touches).

You run, and paste in the evidence log:
- the full backend suite and `npm test`; `npm run build`; `npm audit --audit-level=high`;
- `backend/scripts/verify_schema.py`; `python -m backend.seed --dry-run` (zero pending writes); `backend/scripts/reconcile.py --dry-run`;
- `grep -rn "TODO\|FIXME" backend/ frontend/src/`; `grep -rn "os.environ" backend/ | grep -v settings_env.py`; `grep -rn "except:\s*$\|except: pass\|except Exception: pass" backend/`; `grep -rn "fetch(" frontend/src | grep -v lib/api.ts`;
- your **own** walkthrough through the API, from scratch, every response pasted: with `ALLOW_TEST_DATA=true`, `load_test_data.py --apply`; then every new or changed endpoint in the diff, with each parameter and each refusal; then one **full cycle** in a community that has test residents — prepare, jury, open, vote, close, publish — and one **zero-item** cycle. You do not trust the build's paste;
- a hash round-trip on the published summary (fetch the JSON, recompute SHA-256 locally, compare); a replay of the jury draw from its logged pool and bytes;
- three hand-derived `threshold()` cases against the code; for any new rule in `rules.py`, three hand-derived cases of that too;
- every page the diff touched, as rendered HTML with the backend running, and once more with images blocked; each new page checked against CLAUDE §8 (WCAG 2.1 AA) as far as HTML allows;
- every sentence of new user-facing copy that makes a claim about the platform (landing page, explainers, help text): the document section that makes it true, or a finding. A number typed into copy that is a setting's value is a Law 8 finding;
- `git diff origin/main...HEAD --stat` at the very end, and `git status`, showing you changed only `audits/` and `HISTORY.md`.

**Named questions.** If the newest planning entry in HISTORY.md puts a
question to the auditor, answer each one in the report under its own
heading, with evidence, whether or not it becomes a finding.

**Browser-only checks.** You have no browser. Copy the "Director to
verify" list from the build's HISTORY entry into the report and mark
each item `director-verified` (only if a planning entry in HISTORY.md
says the director verified it) or `not yet verified`. An unverified item
is not a finding; it is a line the director must clear before merging.

## What you write

`audits/change-NN-audit-K.md`, exactly the structure in AUDIT.md §6,
plus three sections after "Checks passed": **Scope** (which you ran and
why), **Named questions**, **Browser-only checks**. Verdict `CLEAN`
means zero `CRITICAL` and zero `HIGH`.

Document ambiguities are places you could not tell whether the code or
the document is right. Do not resolve them; list them for the director.

## What you must not do

- Fix anything. Not a typo, not a comment, not a failing test.
- Edit any file outside `audits/` except to append your HISTORY.md paragraph. Edit TODO.md.
- Read a previous audit of this change before forming your own list.
- Open a pull request, push to `main`, or declare a keeper.
- Ask for approval, or stop early because the code is bad. A bad build is a long report, not a short run.

## At the end

1. Append one paragraph to HISTORY.md: `## YYYY-MM-DD — Session N
   (Claude Code audit — change-NN, run K)` with the report path, the
   counts by severity, and the verdict. Today's date from the system
   clock. Findings live in the report, not here.
2. `git add audits/ HISTORY.md && git commit -m "audit change-NN run K" && git push origin <the branch>`.
3. Do not open a pull request.

[[[ END AUDIT BRIEF ]]]
