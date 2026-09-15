# Build Brief — demo-01, fix run 3

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — demo-01-fix-3 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is trial **demo-01**,
**fix run 3**, after audit run 3 returned `FIX REQUIRED` with one HIGH.
Your branch is `demo/01`: run `git switch demo/01 && git fetch origin &&
git merge --ff-only origin/demo/01`, then `git log --oneline -3` — the
newest commit must be the director's "Post-audit-3 document updates".
You cannot push to `main` and must not try.

This run is small and exact. Audit run 3 found the build strong; what
remains is six findings, every one named by file and function below.
Fix those, prove each, and stop. Do not touch anything else.

## Read first, in this order, in full

1. `CLAUDE.md`.
2. `audits/demo-01-audit-3.md` — every finding, "Previously reported, still present", and the one ambiguity (now settled in DATABASE §4.17).
3. `HISTORY.md` — the last three entries.
4. `ARCHITECTURE.md` §3 (`PUBLIC_BASE_URL`), §6 (pagination rule and exemptions), §7 (`recommend_references`, `build_export`), §10; `DEMOCRACY.md` §11.5; `DATABASE.md` §4.17.
5. `TODO.md`.

## Step 0 — Pre-checks (paste the output of each)

1. `git branch --show-current` and `git log --oneline -3`.
2. `docker compose --env-file .env -f infra/docker-compose.yml up -d`; `docker compose ps`.
3. `curl -sS $OLLAMA_BASE_URL/api/tags`.

## Work items, in order, one commit each

- **FIX-21 (HIGH) — pagination.** Wire `cursor`/`limit` into all seven:
  `umbrellas.py::umbrella_solutions`, `::umbrella_comments`,
  `::umbrella_references`, `transparency.py::settings_history`,
  `ballots.py::community_cycles`, `amendments.py::list_amendments`,
  `summaries.py::hash_list`. Default 25, max 100, `limit > 100` → 422,
  `next_cursor` in the response. No new exemptions — ARCHITECTURE §6
  names exactly five. Add `backend/tests/test_pagination.py`: walk every
  `GET` route in `app.routes` whose response model contains a list and
  assert it takes `cursor` and `limit`, or its path is one of the five.
  Paste the test failing before the fix (naming all seven) and passing
  after. Paste a `?limit=500` → 422 and a two-page walk of
  `/summaries/hashes` with `limit=2`.
- **FIX-22 (MEDIUM) — reference recommendation is a job.**
  `admin.py::recommend_as_admin` writes the `admin_actions` row and
  schedules the Ollama/search work with `runner.spawn_after_commit`,
  returning 202 `{status: "pending"}` at once (ARCHITECTURE §7). The
  umbrella page shows "AI is looking for references…" until the
  `ai_actions` row exists. Paste the 202, then the row appearing.
- **FIX-23 (MEDIUM) — verified, not signed-in.**
  `posts.py::confirm_label` and `::correct_label` take `VerifiedUser`.
  Paste an unverified account getting 403 `email_not_verified` on both.
- **FIX-24 (MEDIUM) — the two remaining router-logic offenders.**
  `geo.py::community` → `community_service.detail_view`;
  `amendments.py::propose_amendment` → one service call. Then change
  `test_layering.py` to count distinct service **function** calls per
  endpoint (one, beyond `require_*` resolvers), not modules. Paste the
  test failing on both before the fix and passing after. If the stricter
  test finds further endpoints, fix those too and list them — do not
  loosen the test.
- **FIX-25 (LOW) — absolute summary URL.** Add `PUBLIC_BASE_URL` to
  `settings_env.py` and `.env.example` (Demo 1: `http://localhost:3000`);
  startup refuses without it like every key. `_mailto` body, PDF footer,
  and the summary page's verify text use it. Paste a `mailto:` href from
  a published summary showing the full URL.
- **FIX-26 (LOW) — documentation match.** ARCHITECTURE §7 now lists
  `build_export`; confirm the job's name in code matches and paste the
  lifespan/registry line.
- **FIX-27 — evidence.** Full suite (including the new tests),
  `verify_schema.py`, seed dry-run, the greps, `npm audit
  --audit-level=high`, `git status`, pasted.

## What you must not do

- Edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md,
  SANDBOX.md, AUDIT.md, or `audits/`.
- Mark an item done with less than it says. Audit runs 2 and 3 each
  caught this once (FIX-01, FIX-11). If you fixed some of a list and not
  all, the item is `[~]` and the residue is named.
- Change any file the six findings do not name, except tests and
  `.env.example`. Audit run 4 will diff your commits against the named
  files; anything outside them turns a short re-audit into a full one.
- Push to `main`. Ask for approval.

## At the end

1. Append the director's planning entry below to HISTORY.md **verbatim**,
   then your own: `## <today> — Session N (Claude Code build — demo-01,
   fix run 3)`, where N is one more than the last entry's session number
   for that date.
2. Update TODO.md: "Phase 2c — demo-01 fix run 3" with FIX-21…FIX-27;
   snapshot.
3. `git add -A && git commit -m "demo-01 fix run 3 complete" && git push origin demo/01`.
4. No pull request.

### Planning entry to append verbatim (before your own)

```
## 2026-09-15 — Session 1 (Claude.ai planning session — audit run 3 review)

**Completed:**
- Reviewed `audits/demo-01-audit-3.md` (CRITICAL 0 · HIGH 1 · MEDIUM 3 · LOW 2; FIX REQUIRED) and fix run 2's entry. The three items fix run 2 existed for — deep-reply names, jury redraw, minority hold-backs — were independently reproduced as fixed by the auditor. Fix brief `briefs/demo-01-fix-3.md` written: six findings, each named by file and function.
- Document changes: ARCHITECTURE §3 (`PUBLIC_BASE_URL`), §7 (`recommend_references` returns 202 and runs as a job; `build_export` row added); DEMOCRACY §11.5 (absolute summary URL); DATABASE §4.17 (per-seat replacement vs whole-jury supersession — settles the "replaced" ambiguity both fix run 2 and audit run 3 flagged). `briefs/audit.md` now states the AUDIT.md §2 rule for re-audits: re-verify reported items first, full pass only if the fix run's diff went beyond the files those findings named.

**Decisions made:**
1. All seven unpaginated endpoints paginate; no exemptions added. DEMOCRACY §3.3's "nothing is ever hidden" is met by paging, not by unbounded lists.
2. Fix run 2 marked FIX-11 done while two of audit run 2's five named handlers were untouched, and the layering test counted modules rather than function calls. Fix briefs now name offenders by file and function and forbid loosening a test to pass it.

**Issues encountered:**
- Fix runs are getting smaller (thirteen items → six → this) and audits are converging; the next audit should be a re-audit under AUDIT.md §2 rather than a fourth full sweep.
```

[[[ END BUILD BRIEF — demo-01-fix-3 ]]]
