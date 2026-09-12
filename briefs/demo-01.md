# Build Brief — demo-01

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — demo-01 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with
your own clone of `lHollandl/direct-democracy-ca`. This is trial
**demo-01**. Your branch is `demo/01`; run `git switch demo/01` first
and confirm with `git branch --show-current` before anything else. You
cannot push to `main` and must not try.

You are building both halves of this project in this run: the
**Foundation** (built to keep, full rigor) and **Iteration Demo 1**
(built to be used and then rebuilt). CLAUDE.md, "The Two Halves of the
Codebase", says how they differ.

## Read first, in this order, in full

1. `CLAUDE.md` — the constitution. Every law applies to every file you write.
2. `PROJECT.md` — scope. "Demo 1 — Scope" is your definition of done. "Out of scope for Demo 1" is a list of things you must not build.
3. `DEMOCRACY.md` — every rule, threshold, status, and role. Build exactly this.
4. `DATABASE.md` — every table and column. Build exactly this.
5. `ARCHITECTURE.md` — layers, config, endpoints, jobs, clients, frontend routes, tests. Build exactly this.
6. `TODO.md` — task ids F-01…F-23 and I-01…I-31. You will mark them.
7. `HISTORY.md` — the last two entries.

Where these documents are silent, decide, and record every such
decision in your HISTORY.md entry with its reasoning. Where they
conflict, CLAUDE.md wins, then DEMOCRACY.md; report the conflict in
HISTORY.md rather than resolving it silently.

## Step 0 — Pre-checks (report before building)

Run and paste the output of each:

1. `git branch --show-current` — must be `demo/01`.
2. `ls backend/config/` — the four seed files in DATABASE.md §5 must be present: `seed_geography.yaml`, `seed_officials.yaml`, `seed_umbrellas.yaml`, `seed_settings.yaml`. **If any is missing, STOP** after writing a HISTORY.md entry that says so. Do not invent seed data.
3. `cat .env.example` if it exists; note whether `SEARCH_API_KEY` has a value in `.env`. If not, the reference-recommendation trigger returns 503 per ARCHITECTURE §8.2 and that is correct — do not stub a provider.
4. `curl -sS $OLLAMA_BASE_URL/api/tags` — Ollama reachable and the models named in `.env` present. If not reachable, build everything but note that labeling was tested only with the mocked client.
5. `docker compose version` — the sandbox's Docker works.

## Order of work

Build Foundation first (F-01 → F-23), run its tests, commit. Then
Iteration (I-01 → I-31), commit. Foundation must not depend on anything
in Iteration. Commit in small, labeled commits (`F-06 users and display
settings`, `I-16 prepare ballot and jury draw`), so the audit can read
the history.

The legacy code on the branch is a reference for what existed, not a
base to extend. ARCHITECTURE §12 lists what it gets wrong. Replace it;
do not patch it. Delete files the new layout makes obsolete (a demo
branch may delete freely; `main` never receives these deletions except
through the Foundation PR, which the director reviews).

## What "done" means

Every item below, with evidence pasted into HISTORY.md — not asserted:

- `alembic upgrade foundation@head && alembic upgrade iteration@head` from an empty database, output pasted.
- `backend/scripts/verify_schema.py` reports no drift, output pasted.
- `python -m backend.seed --dry-run` after seeding reports zero pending writes, output pasted.
- The test suite passes (ARCHITECTURE §10), full output pasted, including the full-cycle integration test.
- A manual full cycle through the API with `curl`, every response pasted: three users sign up and verify (links from the console email log) → one posts a problem with a solution → it is labeled → the others upvote and one amends → the amendment is absorbed → the solution becomes dominant → admin prepares the ballot → jury is drawn, one juror holds back a second solution with a reason → admin opens → all three vote → admin closes and publishes → `GET /summaries/.../verify` returns match → the JSON re-hashes locally to the stored hash.
- Every page in ARCHITECTURE §9 renders with the backend running; a screenshot-equivalent description or the HTML title of each, pasted.
- `grep -rn "TODO\|FIXME" backend/ frontend/src/` returns nothing.
- `grep -rn "os.environ" backend/ | grep -v settings_env.py` returns nothing.
- `git status` clean; `git log --oneline` pasted.

## What you must not do

- Build anything in PROJECT.md "Out of scope for Demo 1".
- Edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, or ARCHITECTURE.md. If one is wrong, say so in HISTORY.md.
- Put any threshold, window, or size in code. They come from the `settings` table.
- Write an AI prompt as a Python string. Prompts are files under `ai/prompts/`.
- Expose a ballot vote with a voter id through any endpoint, including admin.
- Commit a `.env` file or any secret. Generate fresh secrets into `.env` from `.env.example` and never print them.
- Push to `main`. Push `demo/01` when done.
- Ask for approval. You have it, within the boundaries above. If something outside them seems necessary, stop, write it in HISTORY.md, and end the run.

## At the end

1. Update `TODO.md`: mark every completed id `[x]`; mark partial ones `[~]` with a note; update the Current Status Snapshot; add technical debt you discovered, saying what makes each bite.
2. Append the HISTORY.md entry (format in CLAUDE.md): `## 2026-MM-DD — Session 1 (Claude Code build — demo-01, Foundation + Iteration)`. Use today's date from the system clock. Record everything in "What done means" as pasted evidence, every decision you made that the documents did not resolve, every deviation and why, every surprise, and every place a document seemed wrong.
3. `git add -A && git commit -m "demo-01 complete" && git push origin demo/01`.
4. Do not open a pull request. The director does that after the audit.

[[[ END BUILD BRIEF — demo-01 ]]]
