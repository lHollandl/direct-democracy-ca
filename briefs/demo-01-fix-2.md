# Build Brief — demo-01, fix run 2

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — demo-01-fix-2 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is trial **demo-01**,
**fix run 2**, after audit run 2 returned `FIX REQUIRED`. Your branch is
`demo/01`: run `git switch demo/01 && git fetch origin && git merge
--ff-only origin/demo/01`, then `git log --oneline -3` — the newest
commit must be the director's "Post-audit-2 document updates". You
cannot push to `main` and must not try.

You are fixing the findings of `audits/demo-01-audit-2.md`. You are not
rebuilding. Change what the findings and this brief name; leave the rest
alone. The audit says the machinery underneath is good; keep it that way.

## Read first, in this order, in full

1. `CLAUDE.md` (§8 now names WCAG 2.1 AA).
2. `audits/demo-01-audit-2.md` — every finding, "Previously reported, still present", and "Document ambiguities" (all four are now settled in the documents).
3. `HISTORY.md` — the last three entries (fix run 1, audit run 2, and the planning entry you will append below).
4. `DEMOCRACY.md` §6, §8.1, §8.3, §11.2, §13; `DATABASE.md` §4.11, §4.17; `ARCHITECTURE.md` §4, §6, §10 — changed since the fix run.
5. `TODO.md`.

Where the documents are silent, decide and record it in HISTORY.md.
Where they conflict, CLAUDE.md wins, then DEMOCRACY.md; report the
conflict rather than resolving it silently.

## Step 0 — Pre-checks (paste the output of each)

1. `git branch --show-current` and `git log --oneline -3`.
2. `docker compose --env-file .env -f infra/docker-compose.yml up -d`; `docker compose ps`.
3. `curl -sS $OLLAMA_BASE_URL/api/tags`.

## Work items, in order, one commit each

- **FIX-08 (CRITICAL) — deep replies.** Add `comments.reply_to_comment_id`
  (DATABASE §4.11) to the Iteration migration; stop writing any name into
  `text`; render "replying to @display" at read time through the
  author-display rule. `content_hash` covers the new field. Test: a user
  with `public_name_mode = real_name` receives a deep reply, switches to
  `anonymous`, then deletes the account — the stored text contains no
  name, the thread renders "replying to @Anonymous Community Member" then
  "@Former Community Member", and the comment's hash still recomputes.
- **FIX-09 (HIGH) — jury draws are never deleted.** DATABASE §4.17:
  `cycle_id` no longer unique; `superseded_at`; `redrawn_reason` on the
  superseded row; partial unique on the current jury. Redraw marks and
  inserts. `GET /cycles/{id}` shows every draw with its status. Test:
  redraw, then read both draws' pools and random bytes.
- **FIX-10 (MEDIUM) — every hold-back is published.** DEMOCRACY §8.3,
  §11.2 item 2: "Jury notes" on the solution page from ballot open;
  "Juror concerns" under any summary item a juror held back without a
  majority. The hold-back endpoint's message becomes true. The summary's
  canonical JSON gains the section; the hash covers it.
- **FIX-11 (MEDIUM) — router logic.** Move `get_solution`'s assembly into
  `solutions_service.detail_view`; every endpoint calls one service
  module beyond `require_*` resolvers; no threshold arithmetic in any
  router. Extend `test_layering.py` per ARCHITECTURE §10 so it fails on
  either. Paste the test finding the old `get_solution` before the fix,
  then passing after.
- **FIX-12 (MEDIUM) — labeler records invented communities.** Append to
  `output.repeated_or_unlisted_communities` in the unlisted case too
  (DEMOCRACY §9.1). Test with a mocked answer naming a community the
  post did not select.
- **FIX-13 (MEDIUM) — pagination.** ARCHITECTURE §6: the five named
  reference lists return whole; every other list endpoint paginates;
  `limit > 100` is 422. Paste the 422.
- **FIX-14 (MEDIUM) — `grant_admin.py`.** Code already matches the
  corrected ARCHITECTURE §4; add `--revoke` if absent; paste `--help`.
- **FIX-15 (MEDIUM) — frontend advisories.** `next` to 16.3.5 (or the
  current patched release); `npm audit --audit-level=high` clean, pasted.
- **FIX-16 (LOW ×7).** Document the five endpoints — already done in
  ARCHITECTURE §6, verify `/openapi.json` matches; log in the two
  swallowing handlers and narrow the broad one; the blocking CSV read in
  `async def` → `asyncio.to_thread` or a sync seed path; delete the stale
  amendment-hash docstring; the `600` fallback reads the seeded default
  through `services/settings.py` or fails loudly; fix the grammar slip;
  per-page `<title>` server-rendered (Next.js metadata), not in
  `useEffect`.
- **FIX-17 — WCAG 2.1 AA pass** (CLAUDE §8). Every form field with an
  error carries `aria-invalid` and `aria-describedby` pointing at its
  message; every page has a unique server-rendered title and one `h1`;
  focus moves to the first error on failed submit. Paste the rendered
  HTML of the signup form in its error state.
- **FIX-18 — comment depth wording.** No code change expected (the code's
  0-based depth is what DEMOCRACY §6 now says); confirm and paste the
  depth-3 re-attachment test.
- **FIX-19 — summary header.** "n drawn, r replaced, s seated" per
  DEMOCRACY §11.2 item 1; paste a header from a cycle with a replacement.
- **FIX-20 — full evidence set** (build brief "What done means" plus the
  extended walkthrough from fix run 1 plus `npm audit`), pasted.

## What you must not do

- Edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md,
  SANDBOX.md, AUDIT.md, or `audits/`.
- Narrow a work item's wording when marking it done. If you did less
  than an item says, mark it `[~]` and say what is missing (audit run 2
  caught this on FIX-01).
- Rebuild or restructure anything the audit did not name.
- Push to `main`. Ask for approval.

## At the end

1. Append the director's planning entry below to HISTORY.md **verbatim**,
   then your own: `## 2026-09-14 — Session 5 (Claude Code build —
   demo-01, fix run 2)`.
2. Update TODO.md: "Phase 2b — demo-01 fix run 2" with FIX-08…FIX-20;
   snapshot; technical debt.
3. `git add -A && git commit -m "demo-01 fix run 2 complete" && git push origin demo/01`.
4. No pull request.

### Planning entry to append verbatim (before your own)

```
## 2026-09-14 — Session 4 (Claude.ai planning session — audit run 2 review)

**Completed:**
- Reviewed `audits/demo-01-audit-2.md` (CRITICAL 1 · HIGH 1 · MEDIUM 6 · LOW 7 · NOTE 3; FIX REQUIRED) and fix run 1's entry. Fix brief `briefs/demo-01-fix-2.md` written.
- Document changes: DEMOCRACY §6 (deep replies rendered at read time via `reply_to_comment_id`; depth is 0-based), §8.1 and §13 (no draw is ever deleted; re-draw supersedes), §8.3 (every hold-back published), §11.2 (drawn/replaced/seated; "Juror concerns" under items); DATABASE §4.11 (`reply_to_comment_id`, hash fields), §4.17 (one `juries` row per draw, `superseded_at`, partial unique on the current jury); ARCHITECTURE §4 (`grant_admin.py` syntax), §6 (five named pagination exemptions; `limit > 100` refused; `/health` and `/legal/*` listed), §10 (layering test covers one-service-per-endpoint; `npm audit` in the evidence set); CLAUDE §8 names WCAG 2.1 AA (director-approved).

**Decisions made:**
1. The CRITICAL (a parent author's display name stored and hashed into deep replies) was caused by DEMOCRACY §6's wording, which said "with 'replying to @display'" without saying render-only; the builder followed the specific sentence over DATABASE §3.2's general rule. Fixed in the document first, then the code.
2. Minority hold-back reasons are published everywhere (solution page, summary) — CLAUDE §2, and it is what the juror was told. Director decision.
3. WCAG 2.1 AA is the named accessibility bar for every page, from Demo 1. Director decision.
4. "Drawn" in the summary counts everyone ever drawn, with replacements stated. `comment_max_depth` is the highest 0-based depth value; the code was right, the sentence was not.
5. Five fixed-size reference lists are exempt from pagination by name; everything else paginates and refuses `limit > 100`.

**Issues encountered:**
- Fix run 1 marked FIX-01 done with narrower wording than the brief ("calls only services" vs "exactly one service function"); the auditor caught it. Fix briefs now say explicitly that narrowing an item is not allowed.
- The jury-redraw deletion was flagged by fix run 1 itself as a pre-existing no-op and confirmed by the audit as a HIGH; the schema, not the code, was the cause (`juries.cycle_id` UNIQUE).

**Document changes flagged:**
- AUDIT.md §4.1 could add "any user-facing text stored from a rendered display name" as a named trap; consider in the next planning pass.
```

[[[ END BUILD BRIEF — demo-01-fix-2 ]]]
