# Build Brief — demo-01, fix run 1

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — demo-01-fix-1 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is trial **demo-01**,
**fix run 1**, after audit run 1 returned `FIX REQUIRED`. Your branch is
`demo/01`: run `git switch demo/01 && git pull origin demo/01` first and
confirm with `git log --oneline -3` that the newest commit is the
auditor's (`audit demo-01 run 1`). You cannot push to `main` and must
not try.

You are fixing the audit's findings on both halves. You are not
rebuilding. Change what the findings and this brief name; leave the
rest alone.

## Read first, in this order, in full

1. `CLAUDE.md`.
2. `audits/demo-01-audit-1.md` — every finding, and the "Document ambiguities" section.
3. `HISTORY.md` — the build run's entry and the audit paragraph.
4. `ARCHITECTURE.md` §2, §7, §8.1, §10 and `DEMOCRACY.md` §9.1, §10.2, §13 — the director has updated these since the build (see "Documents changed" below).
5. `TODO.md`.

Where the documents are silent, decide and record it in HISTORY.md.
Where they conflict, CLAUDE.md wins, then DEMOCRACY.md; report the
conflict rather than resolving it silently.

## Documents changed since the build run

The director updated the documents on this branch after the audit. The
changes that affect code:

- ARCHITECTURE §2: every read has a service function; routers never
  import repositories, clients, or the session; services never call
  `session.execute` / `session.get` / `select` directly;
  `backend/tests/test_layering.py` enforces both by scanning source.
- ARCHITECTURE §2 and §7: the **service that owns the transaction**
  schedules any background job via `runner.spawn_after_commit`; routers
  never schedule jobs (resolves the auditor's ambiguity 1).
- ARCHITECTURE §3 (`POSTGRES_*` keys), §4 (`grant_admin.py`, 72-byte
  password cap), §8.1 (JSON Schema in prompt headers, temperature 0),
  §10 (throwaway database, not container) — these record what you
  already built; check the code matches the wording.
- DEMOCRACY §9.1 (labeler answer selection), §9.3 (no prompt file),
  §13 (admin only by script); DATABASE §3.10, §3.11, §4.9, §4.11 (hash
  field lists — confirm the code's canonical JSON uses exactly the
  fields listed, and change the code if not; hashes on existing demo
  rows are not a concern, the database is rebuilt).

## Step 0 — Pre-checks (paste the output of each)

1. `git branch --show-current` — `demo/01`; `git log --oneline -3`.
2. `ls backend/config/` — the five seed files present.
3. `docker compose --env-file .env -f infra/docker-compose.yml up -d` —
   must succeed this time (the allowlist was corrected; SANDBOX.md §5).
   Paste `docker compose ps`. If it fails, paste the blocked hostname
   and continue with the direct-binary Postgres the build used.
4. `curl -sS $OLLAMA_BASE_URL/api/tags`.

## Work items, in order, one commit each

- **FIX-01 (HIGH) — layering.** Every router calls exactly one service
  function and imports nothing from `repositories/`, `clients/`, or the
  session. Every service reads and writes through its aggregate's
  repository module; no `session.execute`, `session.get`, or `select(`
  in `backend/services/`. Thin pass-through service functions are fine.
  Add `backend/tests/test_layering.py`: it walks `backend/routers/` and
  `backend/services/` and fails on any offending import or call, with
  the file and symbol in the message. The audit's evidence log has the
  two greps that found the violations; both must return nothing.
- **FIX-02 — job scheduling.** Move every `runner.spawn_after_commit`
  call out of routers into the service function that owns the
  transaction. The layering test should also catch a router importing
  `jobs`.
- **FIX-03 (LOW) — `pyproject.toml`.** `version = "0.1.0"`; the demo
  label stays in `BUILD_LABEL`. Paste a successful `pip install -e .`.
- **FIX-04 — canonical hash fields.** Compare `amendments` and
  `comments` hash construction with DATABASE §4.9 / §4.11 and align.
- **FIX-05 — HISTORY correction.** The build entry's narrative says
  "199 passed"; the evidence file and the auditor say 201. HISTORY is
  append-only: state the correction in your own entry, do not edit the
  build's.
- **FIX-06 — the three unproven scenarios.** Build a scripted walkthrough
  (`backend/scripts/walkthrough_extended.py` or a shell script under
  `briefs/evidence/demo-01/`) with **six** accounts — one admin who is
  also the post author, five ordinary members, all in the same home city
  and county — and paste every response:
  a. The admin posts one problem with **two** solution texts to **both**
     the city and the county community; after labeling, show four
     `solutions` rows, two per umbrella, each with its `post_solution_id`
     (DEMOCRACY §4.1).
  b. Members vote until a solution is dominant and qualified; lower
     `ballot_min_dominant_days` to 0 with a logged reason; prepare. The
     jury draw (size 3, author and admin excluded, pool of 5) yields
     three jurors: one accepts, one **declines** and is replaced from the
     pool, one **never responds**. Open the ballot; paste
     `seated_count` = 2 and the `no_response` juror's status. One seated
     juror holds an item back; with two seated, one hold-back is not a
     majority — show the item is still votable. Then restore
     `ballot_min_dominant_days` to 3 with a logged reason.
  c. In the county community, where nothing qualifies, prepare a cycle:
     zero items, no jury drawn, state `prepared`; publish directly; paste
     the empty summary and its hash; prepare cycle 2 to prove the
     community is unblocked.
- **FIX-07 — re-run the full evidence set** from the build brief's "What
  done means" (migrations from empty, `verify_schema.py`, seed dry-run,
  full test suite including the new layering test, the greps, `git
  status`) and paste it.

## What you must not do

- Edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md,
  SANDBOX.md, AUDIT.md, or `audits/`.
- Rebuild, restructure, or "improve" anything the audit did not name.
- Change any behaviour while fixing the layering; the audit found none
  wrong, and the test suite is the proof it stayed that way.
- Push to `main`. Ask for approval.

## At the end

1. Append the director's planning entry below to HISTORY.md **verbatim**,
   then your own entry after it:
   `## 2026-09-14 — Session 3 (Claude Code build — demo-01, fix run 1)`
   with the pasted evidence, every decision, every deviation.
2. Update TODO.md: add and mark `FIX-01`…`FIX-07` under a new heading
   "Phase 2a — demo-01 fix run 1"; update the snapshot; add any new
   technical debt with what makes it bite.
3. `git add -A && git commit -m "demo-01 fix run 1 complete" && git push origin demo/01`.
4. Do not open a pull request.

### Planning entry to append verbatim (before your own)

```
## 2026-09-14 — Session 2 (Claude.ai planning session — audit review and document updates)

**Completed:**
- Reviewed the demo-01 build entry and `audits/demo-01-audit-1.md` (CRITICAL 0 · HIGH 1 · MEDIUM 0 · LOW 3 · NOTE 2; FIX REQUIRED). Both always-critical traps clean. Fix brief `briefs/demo-01-fix-1.md` written.
- Adopted into the documents every decision the build made: seed keys transcribed; admin only by `grant_admin.py` (DEMOCRACY §13, ARCHITECTURE §4); JSON Schema in prompt headers and temperature 0 (ARCHITECTURE §8.1); labeler answer selection with ignored answers logged (DEMOCRACY §9.1); embedding actions' sentinel `prompt_file` (DATABASE §3.10); amendment and comment hash fields (DATABASE §4.9, §4.11); `POSTGRES_*` in `.env` (ARCHITECTURE §3); 72-byte password cap (CLAUDE.md Law 13, director-approved typo-grade addition); gradient headers until the director supplies photography.
- Document corrections the run found: DATABASE §3.11 export sentence; ARCHITECTURE §6 `/auth/me` vs `/me/*`; ARCHITECTURE §10 "throwaway database"; DEMOCRACY §10.2 note on the unreachable guard.
- ARCHITECTURE §2 and §7 now state that the service owning the transaction schedules background jobs (resolves audit ambiguity 1) and that `test_layering.py` enforces the layer boundaries.

**Decisions made:**
1. The HIGH layering finding stands; fixed in a fix run rather than downgraded. Reason: it reproduces the legacy code's shape that ARCHITECTURE §12 exists to remove, and the layer split is what keeps future audits cheap.
2. Fix runs use a fresh sandbox (`ddc-demo-NN-fix-K`) from a synced host branch; re-entering an existing sandbox with a new prompt is undocumented (SANDBOX.md §9).
3. Embedding actions keep the sentinel `prompt_file` the build chose rather than making the Foundation columns nullable, to avoid touching the Foundation migration before its first merge.

**Issues encountered:**
- SANDBOX.md §5 named the Docker Hub blob host `production.cloudflare.docker.com`; the real host is `production.cloudfront.docker.com`. The build could not pull images; the rule was corrected before the audit, which pulled cleanly. This resolves audit ambiguity 2. SANDBOX.md corrected.
- `--clone` copies the host's local branches: the audit sandbox started with `demo/01` at `main` because the host's local branch was stale. SANDBOX.md §6.2 now requires syncing the branch before every run.
- The audit sandbox's source tree is writable; the read-only mount in AUDIT.md §1 is not enforced. Recorded in SANDBOX.md §6.5 and §9; the diff check is the safeguard.
- Neither the build's nor the auditor's walkthrough exercised the two-community post, a jury decline and no-response, or the zero-item cycle — three accounts cannot produce them. The fix brief requires all three with six accounts.

**Document changes flagged:**
- The director owes real California photography for page headers (style brief) whenever ready; nothing blocks on it.
- P0-13 (search provider) still open.
```

[[[ END BUILD BRIEF — demo-01-fix-1 ]]]
