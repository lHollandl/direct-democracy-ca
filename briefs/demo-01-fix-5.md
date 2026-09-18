# Build Brief — demo-01, fix run 5

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — demo-01-fix-5 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is trial **demo-01**,
**fix run 5**, after audit run 5 returned `FIX REQUIRED` with two HIGHs
and no CRITICAL. Your branch is `demo/01`: run `git switch demo/01 &&
git fetch origin && git merge --ff-only origin/demo/01`, then `git log
--oneline -3` — the newest commit must be the director's "Post-audit-5
document updates". You cannot push to `main` and must not try.

Narrow and exact. Every item is named by file and function. Fix, prove,
stop.

## Read first, in this order, in full

1. `CLAUDE.md` Law 6 (one clause added).
2. `audits/demo-01-audit-5.md` — every finding and the six ambiguities, all settled in the documents (below).
3. `HISTORY.md` — the last three entries.
4. `DEMOCRACY.md` §4.3, §5.4, §6, §11.5; `DATABASE.md` §1, §3.5, §4.8, §4.11; `ARCHITECTURE.md` §2, §3, §5, §6, §9.
5. `TODO.md`.

How the ambiguities were settled: **every edit is a new hashed row**
(solution edit → version n+1; comment edit → `comment_revisions`);
`mailto:` composition is service logic; whole-page endpoints embed the
first page of each list with a cursor; the author shortcut is "Same"
only; `char(n)` means `VARCHAR(n)` everywhere; photography is off until
the director supplies images and that is intended; the rate limiter is
documented as the fixed window that exists.

## Step 0 — Pre-checks (paste the output of each)

1. `git branch --show-current` and `git log --oneline -3`.
2. `docker compose --env-file .env -f infra/docker-compose.yml up -d`; `docker compose ps`.
3. `curl -sS $OLLAMA_BASE_URL/api/tags`.

## Work items, in order, one commit each

- **FIX-38 (HIGH) — solution edit is a new version.**
  `solutions_service.edit` (behind `PATCH /solutions/{id}`) inserts
  `solution_versions` version n+1 (`created_by` = author,
  `amendment_id` NULL) and bumps `current_version`; it updates no column
  of any existing version row. Test: edit twice, assert three version
  rows, all three hashes recompute, `reconcile.py --dry-run` clean.
- **FIX-39 (HIGH) — comment edit is a new revision.** Iteration
  migration adds `comment_revisions` and `comments.current_revision`
  (DATABASE §4.11); revision 1 written with the comment in the same
  transaction; `comments_service.edit` inserts revision n+1 and updates
  `text`, `current_revision`, `edited_at`; `comments.content_hash` stays
  revision 1's hash; `reconcile.py` checks every revision and the
  comment's hash against revision 1. The page shows "edited (revision
  2)" with the history reachable. Test as for FIX-38. Rebuild the demo
  database from empty since the schema changed; paste the migration run.
- **FIX-40 (MEDIUM) — jobs obey the layers.** Every `backend/jobs/*`
  module calls services only; `reconcile.py` gets a
  `services/reconcile.py` it delegates to. Extend `test_layering.py` to
  scan `jobs/` with the router rules. Paste it failing before and passing
  after.
- **FIX-41 (MEDIUM) — landing page uses `api.ts`.** No `fetch` outside
  `frontend/src/lib/api.ts`; add a grep-style check to the layering test
  (ARCHITECTURE §9).
- **FIX-42 (MEDIUM) — `jury_review_days` consulted.** Jury duties
  (`GET /juries/mine`, `/jury`) and `GET /cycles/{id}` show "would close
  on <jury_review_started_at + jury_review_days>" and the ballot shows
  "would close on <opened_at + ballot_window_days>" (DEMOCRACY §10.1).
  Paste both.
- **FIX-43 (MEDIUM) — "Jury notes" on the solution page.** Render what
  `GET /solutions/{id}` already returns, from ballot open (DEMOCRACY
  §8.3). Paste the rendered HTML with one note.
- **FIX-44 (MEDIUM) — AI-influence on comments and amendments.** The
  label "AI assistance on this platform: 0%" on every comment and
  amendment, as on posts and solutions (DEMOCRACY §6, §9.5). Paste HTML.
- **FIX-45 (LOW) — blocking IO in the two files** the AST check missed;
  extend the check to cover them. Paste failing-then-passing.
- **FIX-46 (LOW) — "Different" needs `similarity_confirm_min`**;
  the author shortcut applies to "Same" only. Test both.
- **FIX-47 (LOW) — `IP_HASH_SECRET`.** In `settings_env.py` and
  `.env.example`; `ip_hash = sha256(secret + ip)`; startup refuses
  without it.
- **FIX-48 (LOW) — expired exports.** `GET /me/export/{id}` returns 410
  once `expires_at` has passed, regardless of the hourly sweep. Test.
- **FIX-49 (LOW) — `mailto:` body** composed in `summaries_service`;
  the router returns it.
- **FIX-50 (LOW) — whole-page embeds** are the first page with
  `next_cursor` (ARCHITECTURE §6); update `test_pagination.py`'s
  comment and add an assertion for the three named endpoints.
- **FIX-51 — TODO residue.** I-28's note names photography as
  intentionally absent until images are supplied (ARCHITECTURE §9).
- **FIX-52 — evidence.** Full suite, `verify_schema.py`, seed dry-run,
  `reconcile.py --dry-run` after two solution edits and two comment
  edits, the greps, `npm audit --audit-level=high`, `git status`, pasted.

## What you must not do

- Edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md,
  SANDBOX.md, AUDIT.md, or `audits/`.
- Mark an item done with less than it says. Partial is `[~]` with the
  residue named.
- Touch files the findings do not name, except tests, the frontend pages
  in FIX-41/42/43/44, the Iteration migration, `.env.example`, and
  `settings_env.py`.
- Push to `main`. Ask for approval.

## At the end

1. Append the director's planning entry below to HISTORY.md **verbatim**,
   then your own: `## <today> — Session N (Claude Code build — demo-01,
   fix run 5)`.
2. Update TODO.md: "Phase 2e — demo-01 fix run 5" with FIX-38…FIX-52;
   snapshot; I-28 note.
3. `git add -A && git commit -m "demo-01 fix run 5 complete" && git push origin demo/01`.
4. No pull request.

### Planning entry to append verbatim (before your own)

```
## 2026-09-18 — Session 1 (Claude.ai planning session — audit run 5 review)

**Completed:**
- Reviewed `audits/demo-01-audit-5.md` (CRITICAL 0 · HIGH 2 · MEDIUM 5 · LOW 8 · NOTE 4; FIX REQUIRED) — the first audit with no CRITICAL; all ten audit-4 findings confirmed fixed. Fix brief `briefs/demo-01-fix-5.md` written.
- Document changes: CLAUDE.md Law 6 gains one clause (director-approved): where text may change, the change is a new hashed row, never a rewrite. DEMOCRACY §4.3 (pre-vote edit creates version n+1), §5.4 (author shortcut is "Same" only), §6 (comment edits are revisions), §11.5 (`mailto:` composed in the service); DATABASE §1 (`char(n)` reads `VARCHAR(n)` throughout), §3.5 (`ip_hash` salted with `IP_HASH_SECRET`), §4.8 (versions never updated), §4.11 (`comment_revisions`); ARCHITECTURE §2 (jobs scanned by the layering test), §3 (`IP_HASH_SECRET`), §5 (fixed-window limiter, as built), §6 (whole-page endpoints embed first pages), §9 (photography intentionally absent; `api.ts` sole `fetch`).

**Decisions made:**
1. **Director:** every edit is a new hashed row. Reason: it is what the version machinery already does, and Law 6 stays as written. The two HIGHs were the code answering an undefined question two different ways.
2. The remaining ambiguities settled as above; none required constitutional change beyond the Law 6 clause.
3. California photography stays absent until the director supplies images; this is recorded as intended, not as residue.

**Issues encountered:**
- Fix run 4 reported `archive.ubuntu.com` blocked in the sandbox (no `apt`); the run worked around it with `pip --break-system-packages`. Recorded for SANDBOX.md §9 — decide whether to allow the Ubuntu archive or document the workaround.
- Audits 1–5 each found a documented obligation the backend met and the page above dropped (jury notes, AI-influence labels, the references indicator). The auditor cannot run a browser; the fix briefs now ask for rendered HTML per UI item.

**Document changes flagged:**
- AUDIT.md §4.1: add the trap "a name stored, hashed, or published instead of resolved at read time" and "an edit that rewrites a hashed row". Director approval; next planning pass.
- SANDBOX.md §9: `archive.ubuntu.com` blocked; `sbx ports` syntax still unrecorded.
```

[[[ END BUILD BRIEF — demo-01-fix-5 ]]]
