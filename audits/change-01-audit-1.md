# Audit — change-01, run 1, 2026-09-20

## Summary

One paragraph. Counts by severity. Verdict: CLEAN / FIX REQUIRED.

Full audit of `change/01-site-shell` at commit `a5ff19c` ("change/01 fix run 1
complete"), covering the build run (`briefs/change-01.md`) and fix run 1
(`briefs/change-01-fix-1.md`). Foundation files (`backend/config/settings_env.py`,
`backend/services/auth.py`) are in the diff, so the Foundation half was audited
in full per AUDIT.md §2; Iteration was audited on every touched file and every
document section the briefs named. **Counts: CRITICAL 0 · HIGH 1 · MEDIUM 2 ·
LOW 0 · NOTE 2. Verdict: FIX REQUIRED.** Both always-`CRITICAL` traps (a ballot
vote shown to anyone but its voter; a vote's weight depending on anything but
the voter's choice) reproduced clean in my own walkthrough. The one `HIGH` is
a real, reproduced open-redirect vulnerability in the new `next`-parameter
guard (`frontend/src/lib/nextPath.ts`), not previously caught because the
brief's own three test cases (`//evil.example`, `https://evil.example`,
`/admin`) don't cover the backslash bypass. The two `MEDIUM`s are a residual
"Direct Democracy Cali" spelling the brief's own proof grep couldn't catch
(kebab-case, no space) and an unsupported AI-capability claim on the new
`/explained` page. FX-01, FX-02, and FX-03 all verified correct and complete.
The director's named question (San Jose's "0 eligible jurors") is answered
below with a live reproduction: it is correct, documented behavior, not a bug.

## Findings

### [HIGH] Open redirect via backslash bypass in the `next` guard
- Where: `frontend/src/lib/nextPath.ts::safeNextPath`
- Document: `ARCHITECTURE.md` §9, "Signing in returns you to where you were" — "after sign-in the site goes to `next` when it is a same-site path (begins with a single `/`)"; `briefs/change-01.md` C1-02 — "Reject any `next` that does not begin with exactly one `/`."
- What the document requires: any `next` value that is not a same-site path must be rejected, so a phishing link can never redirect a freshly-signed-in user off-site.
- What the code does: `safeNextPath` checks `next.startsWith("/")`, rejects `next.startsWith("//")`, and rejects `next.includes("://")`. A value that starts with `/` followed by a **backslash** — e.g. `/\evil.example` — passes all three checks (it starts with exactly one `/`, is not `//`, and contains no `://`) and is returned as "safe." `frontend/src/app/login/PageClient.tsx` then calls `router.push(next ?? "/home")`. Next.js's client router resolves that href with `new URL(addBasePath(href), location.href)` (`node_modules/next/dist/client/components/app-router-instance.js:219`); per the WHATWG URL spec, a backslash is treated the same as a forward slash for "special" schemes (http/https), so `/\evil.example` resolves to origin `https://evil.example`. Next's own `isExternalURL` check (`app-router-utils.js:25-27`, `url.origin !== window.location.origin`) then flags this `true`, and `navigateReducer` calls `completeHardNavigation` (`segment-cache/navigation.js:340`), which performs a real, full-page browser navigation to the attacker's origin (`mpaNavigation: true`, `canonicalUrl: url.href`).
- Evidence:
  ```
  $ node -e 'const u = new URL("/\\evil.example", "https://mysite.example"); console.log(u.href, u.host);'
  https://evil.example/ evil.example

  # Against the actual shipped module, via tsx:
  payload: "/\\evil.example"
  safeNextPath(payload): "/\\evil.example"          # not rejected
  browser resolves next to origin: https://evil.example href: https://evil.example/
  isExternalURL (origin differs from realsite.example)? true

  # Confirmed in node_modules/next (v16.3.5) source directly:
  app-router-instance.js:219   const url = new URL(addBasePath(href), location.href);
  app-router-utils.js:25-27    function isExternalURL(url) { return url.origin !== window.location.origin; }
  navigate-reducer.js:34-35    if (isExternalUrl) { return completeHardNavigation(state, url, navigateType); }
  segment-cache/navigation.js:345  canonicalUrl: url.origin === location.origin ? createHrefFromUrl(url) : url.href,
  ```
  `safeNextPath` is used in exactly one place (`frontend/src/app/login/PageClient.tsx`), and its own test file (`frontend/src/lib/nextPath.test.ts`) covers only the three cases the brief named — none include a backslash.
- Suggested fix: after the existing checks, also reject any `next` containing `\`; or resolve `next` through `new URL(next, "http://placeholder.invalid")` and require the resulting origin to equal the placeholder's before accepting it.

### [MEDIUM] "Direct Democracy Cali" survives in two places A1's own proof grep can't see
- Where: `frontend/package.json::name` (and the generated `frontend/package-lock.json`), `backend/routers/me.py` (data-export filename)
- Document: `briefs/change-01.md` §A1 — "Replace every occurrence of `Direct Democracy Cali` (any capitalisation) with `Direct Democracy CA` in every tracked file except [HISTORY.md, audits/, briefs/, archive/]... Proof: `git grep -il 'democracy cali'` lists only paths under those four exceptions."
- What the document requires: every occurrence of the old name replaced everywhere outside the four historical exceptions.
- What the code does: `frontend/package.json`'s `"name"` field is still `"direct-democracy-cali-frontend"` (mirrored into `package-lock.json` twice), and `backend/routers/me.py::export_download` still names the downloaded file `direct-democracy-cali-export-{user.id}.json`. Neither is the literal space-separated string `"democracy cali"` that the brief's own proof grep searches for, so both slipped through a grep that was itself too narrow. The export filename is directly user-facing — every citizen who exports their personal data (CLAUDE.md §6, right to export) downloads a file stamped with the old name.
- Evidence:
  ```
  $ grep -n '"name"' frontend/package.json
  "name": "direct-democracy-cali-frontend",
  $ grep -n "direct-democracy-cali" backend/routers/me.py
          filename=f"direct-democracy-cali-export-{user.id}.json",
  $ grep -n '"name"' pyproject.toml
  name = "direct-democracy-ca"        # already correct before this change — confirms the frontend/export spots were simply missed, not a design choice
  $ npm run build 2>&1 | head -3
  > direct-democracy-cali-frontend@0.1.0 build       # confirms this is live, not dead config
  ```
- Suggested fix: rename `frontend/package.json`'s `"name"` (regenerate `package-lock.json`), rename the export filename prefix, and widen the A1 proof grep for future passes (e.g. add a hyphen/underscore-insensitive check) so a non-space spelling can't slip through again.

### [MEDIUM] Unsupported AI-capability claim on `/explained`
- Where: `frontend/src/app/explained/PageClient.tsx` — "Where AI is, and is not" section
- Document: `DEMOCRACY.md` §9 — names exactly three AI functions in Demo 1: the labeler (§9.1), similarity (§9.3), and reference recommendation (§9.4). No summarization function is documented, and none exists under `ai/prompts/` or anywhere in `backend/`.
- What the document requires: AUDIT.md §4 requires every sentence of new user-facing copy that makes a claim about the platform to be backed by the document section that makes it true; CLAUDE.md §2 (radical transparency) and §5 (AI accountability) require the platform to represent AI's actual role accurately, especially on the page whose whole purpose is explaining that role.
- What the code does: the paragraph reads "AI sorts posts into topics, suggests reference sources, and **summarizes discussion**. It never decides anything..." No summarization feature exists — DEMOCRACY.md §9's three named AI roles are the labeler, similarity, and reference recommendation; none produces a discussion summary.
- Evidence:
  ```
  $ grep -rn "summarize\|summarization" backend/ ai/ DEMOCRACY.md \
      | grep -vi "summary_hash\|summary document\|summaries\|SummaryDocument\|summary_id\|summary page\|summary's\|summaries_"
  (no output)
  ```
  DEMOCRACY.md §9.1–§9.4 confirmed to name only three functions; `ai/prompts/` holds only `labeler.md`, `reference_queries.md`, `reference_select.md`.
- Suggested fix: drop "and summarizes discussion" from the sentence (or add the feature to DEMOCRACY.md §9 first, if one is actually planned).

## Named questions

**"The build's own evidence cycle in San Jose reported '0 eligible jurors' with eight test residents loaded. Possibly correct (authors of ballot items and administrators are excluded; activity window), possibly not."**

**Answer: correct, documented behavior — not a bug.** Reproduced live in this
audit's own sandbox (Ollama unreachable, so the mechanism differs slightly
from the build's run but the *cause* is the same):

1. `threshold(pct, min, denominator)` hand-derived for San Jose's 9 active
   users (8 test residents + this auditor's own admin account):
   `dominant_threshold(5, 3, 9) = 1`, `ballot_threshold(10, 5, 9) = 1`. With a
   community this small, **any solution with a net score ≥ 1 clears both
   bars** — there is nothing selective about "dominant" or "qualified" at
   this scale.
2. San Jose's 10 seed posts (`p01`–`p10`) are authored, between them, by all
   8 test residents (`t01`–`t08`) — confirmed by reading
   `backend/config/test_dataset.yaml`'s `author:` field on each.
3. Preparing San Jose's cycle with the **default** `ballot_min_dominant_days`
   (3) produced **zero** ballot items — every one of the 10 solutions was
   already dominant and above the ballot threshold, but none had been
   dominant for 3 days yet (`considered[].conditions.dominant_long_enough:
   false` on all 10). This is itself a second, independent confirmation that
   an empty ballot is the *expected* outcome for a freshly-loaded tiny
   community, not a symptom of a bug (and it gave a live, natural exercise of
   FX-02's zero-item wording — see Checks passed).
4. Setting `ballot_min_dominant_days` to 0 (as the build's own evidence run
   did) and re-preparing qualified **all 10 solutions simultaneously**
   (`considered[].conditions.dominant_long_enough: true` on all 10) —
   because the threshold bar is so low at this population size, nothing
   distinguishes "the strongest solution" from "every solution with any
   votes." DEMOCRACY.md §8.1 excludes, from the jury pool: authors of any
   version of any *qualified* solution on the ballot, and administrators.
   In this run, 7 of the 8 test residents had authored a solution that
   qualified once all 10 did (one resident, `t06`, happened not to, because
   their own post never resolved to a solution — in my environment because
   Ollama is unreachable so their AI-labeled post stayed `unlabeled`; in the
   build's environment, with real Ollama, `t06`'s post would also have
   labeled successfully and created a solution, extending the exclusion to
   all 8). My own admin account is excluded as an admin. Result:
   `eligible_pool_size: 1` (drawn: 1, the sole remaining resident `t06`) —
   directly explaining the build's `0` under the condition where every
   resident's post successfully became a qualifying solution.

This is the same phenomenon TODO.md's Technical Debt section already names
for Demo 1 ("A three-person community cannot produce a three-person jury...
the demo's jury was one person and a hold-back needed one voice"), and is
explicitly anticipated by DEMOCRACY.md §8.1 ("If fewer eligible users exist
than `jury_size`, the jury is the number available... If zero, the ballot
proceeds with no jury review") and §15 Open Question 3 ("Jury for tiny
communities... proceed with fewer or none, and say so"). No fix is needed;
this will not reproduce at real population scale, where the vast majority of
active users have authored nothing on the current ballot.

## Browser-only checks

Copied from the change/01 build's HISTORY entry (Session 4, "Browser-only
checks for the director") and cross-referenced against the planning session's
2026-09-20 report of what the director actually did in a browser:

- Sign in, reload the page, still signed in. — **not yet verified**
- Type `/admin` while signed out, sign in, land on `/admin`. — **director-verified** (2026-09-20: "`/admin` reachable after sign-out and sign-in")
- The three tabs and the footer on a phone-width window. — **not yet verified** (the director confirmed the three tabs, Admin, and the footer's links are present, but not specifically at phone width — "phone width" is separately listed as not yet reported)
- The landing page redirects to Home when signed in. — **not yet verified**
- Search, each sort, and "All of California" on Home. — **not yet verified**
- The ballot switch is remembered after a reload. — **not yet verified**
- Both "How it works" buttons open and close by keyboard. — **not yet verified** (the director did confirm `/ballot` renders with the "How the ballot works" control present, but not the keyboard open/close behavior specifically)

These are lines the director must clear before merging, not findings against
the build.

## Evidence log

Every command run, in order (condensed; full transcripts available in this
session).

**Pre-checks (AUDIT.md Step 0):**
```
$ git branch --show-current
change/01-site-shell
$ git log --oneline -3
a5ff19c change/01 fix run 1 complete
cac368d FX-02: an empty ballot says why it is empty
1ddd39b FX-03: AUDIT.md §6 names change reports
$ git status
nothing to commit, working tree clean
$ ls audits/
demo-01-audit-1.md … demo-01-audit-6.md      # no change-01-audit-*.md yet → this report is run 1
$ touch backend/AUDIT_WRITE_TEST && echo WRITABLE
WRITABLE                                      # deleted immediately; not committed (confirmed by the final `git status` below)
$ curl -sS $OLLAMA_BASE_URL/api/tags
Blocked by network policy (default deny) — this sandbox has no reachable Ollama.
  Tried the sandbox's own interface, its gateway (172.17.0.1, 172.18.0.1), and
  host.docker.internal; all blocked or unresolvable. Ran with the mocked
  client for the test suite (as the test suite always does — ARCHITECTURE.md
  §10) and noted every place Ollama-dependent behavior could not be
  exercised live (labeling of the 10 `category_choice: ai` test posts, which
  correctly resolved to `unlabeled` instead of `labeled` — see below).
```

**Environment build (from empty):**
```
$ cp .env.example .env   # + generated JWT_SECRET/IP_HASH_SECRET/POSTGRES_PASSWORD, OLLAMA_BASE_URL set to a sandbox-reachable address
$ docker compose --env-file .env -f infra/docker-compose.yml up -d
Container ddc_postgres Started / Container ddc_redis Started
$ alembic upgrade foundation@head
Running upgrade -> 25035d5b7ff5, Foundation initial schema
$ alembic upgrade iteration@head
Running upgrade -> b4b4da0b6e54, Iteration schema — Demo 1
$ python3 -m backend.seed --apply
... umbrellas (Iteration): to write 16, already present 0 ...
$ python3 -m backend.seed --dry-run
pending writes: 0
Nothing to do: every seed row is already in the database.
$ grep -c 'community:' backend/config/seed_umbrellas.yaml
16
$ docker exec ddc_postgres psql -U ddcuser -d directdemocracy -c "select key,value from settings where key='cycle_open_rule';"
cycle_open_rule | first_sunday_of_month
```

**Schema and tests:**
```
$ python3 backend/scripts/verify_schema.py
[1] live database vs the ORM models: no drift
[2] scratch database (from migrations) vs the ORM models: no drift
[3] scratch vs live, table by table: no drift — 38 tables identical
[4] the two halves (DATABASE.md §2): no problems — 15 Foundation tables, 23 Iteration tables, none in both
[5] every foreign key indexed (CLAUDE.md Law 4): no problems
=== RESULT: NO DRIFT ===

$ python3 -m pytest backend/tests/ -q
256 passed, 2 deselected in 147.94s    # matches fix-1's own claimed 256/2 exactly, independently reproduced

$ python3 backend/scripts/reconcile.py --dry-run     # before any test-data or walkthrough activity
corrected: false; net_score_drift: []; dominance_changes: []; orphan_communities: []; hash_mismatches: []
```

**Constitution / Law greps:**
```
$ grep -rn "TODO\|FIXME" backend/ frontend/src/
2 hits, both docstrings/comments citing the closed TODO.md task id "D2-00"
(`backend/services/juries.py`, `backend/tests/test_jury_and_ballot.py`) —
citations to a task-tracker id for traceability, not open work markers; not a
Law 12 violation.

$ grep -rn "os.environ" backend/ | grep -v settings_env.py
(no output)

$ grep -rn "except:\s*$\|except: pass\|except Exception: pass" backend/
(no output)

$ grep -rn "fetch(" frontend/src | grep -v lib/api.ts
(no output)

$ git grep -il 'democracy cali'
HISTORY.md, archive/*, audits/*, briefs/* — only the four historical exceptions.
(But see the MEDIUM finding above: this grep is itself too narrow — it misses
"direct-democracy-cali-frontend" and "direct-democracy-cali-export-...".)

$ git grep -n 'remove_test_data\|test_data_repo\|services\.test_data'
Only HISTORY.md/briefs/ hits — the withdrawn remover leaves no trace in code (FX-01).

$ git grep -n -i 'session\.delete\|\.delete(\|DELETE FROM' -- 'backend/' ':!backend/tests'
backend/clients/redis.py:100   await client.delete(key)                — Redis cache key, not a database row
backend/routers/comments.py:49 @router.delete("/{comment_id}")         — comments_service.remove is a soft update (text replaced, row kept)
backend/routers/me.py:72       @router.delete("", response_model=Message) — account_service.delete_account anonymizes, never deletes the row
backend/routers/votes.py:36    @router.delete("")                      — votes_service.withdraw hard-deletes a `votes` row, DATABASE.md §4.12's
                                                                          documented sole exception (no content_hash on a vote)
Confirmed by reading each service function directly — matches FX-01's own four-hit claim exactly.

$ ls backend/scripts/remove_test_data.py backend/services/test_data.py \
     backend/repositories/test_data.py backend/tests/test_test_data.py
No such file or directory (all four) — confirmed deleted.
```

**Frontend build/test:**
```
$ npm ci
added 370 packages, 0 vulnerabilities
$ npm audit --audit-level=high
found 0 vulnerabilities
$ npm test
# tests 4, # pass 4, # fail 0
$ npm run build
✓ Compiled successfully; 25 routes (matches fix-1's own claim)
```

**Test-data load and my own API walkthrough (from scratch, `ALLOW_TEST_DATA=true`):**
```
$ python3 backend/scripts/load_test_data.py --dry-run
would create 16 accounts, 40 posts

$ python3 backend/scripts/load_test_data.py --apply --log-path <backend log>
created: post 23, vote 173, vote (confirmed) 88, comment 16 (plus earlier
  progress: all 16 accounts, remaining posts/votes/comments)
Final DB state: 16 users, 40 posts, 261+ votes, 27+16=43 comments.
$ select label_status, category_choice, count(*) from posts group by 1,2;
  30 (author_selected) → labeled; 10 (ai) → unlabeled — exactly the 10
  posts whose `file_under` names `ai` in test_dataset.yaml; correctly none
  mislabeled, none silently succeeded, matching C1-13's three-state design
  under a genuine AI-unreachable condition.

# My own account, from scratch:
$ POST /auth/signup {auditor@example.com, San Jose (city 408), Santa Clara (43)}
201 Created
$ verify-email with the token read from the console-backend log
$ POST /auth/login → access token
$ python3 backend/scripts/grant_admin.py auditor@example.com --apply
GRANT administrator on auditor@example.com (user 17)

# Full cycle 1 (San Jose, default ballot_min_dominant_days=3):
$ POST /admin/cycles/prepare {city, 408}
state: prepared, items: [], zero_item_note: "No solution qualified..."
  (all 10 solutions dominant + above threshold, none dominant 3 days yet)
$ GET /cycles/1/ballot → settings_in_force present, matches DATABASE snapshot
$ GET /cycles/1 → settings_in_force matches the ballot endpoint's
$ GET /cycles/mine → San Jose entry: cycle.state "prepared",
  next_ballot_expected "2026-10-04" (independently hand-verified: 2026-10-04
  is a Sunday, and today 2026-09-20 is past September's own first Sunday
  2026-09-06, so October is correctly the next expectation)
$ POST /admin/cycles/1/publish → summary_hash ed37f68...

# Cycle 2 (ballot_min_dominant_days set to 0 with a reason, then back to 3):
$ POST /admin/settings {ballot_min_dominant_days: 0, reason: "..."}
$ POST /admin/cycles/prepare {city, 408}
state: jury_review, 10 items, jury eligible_pool_size: 1, drawn: 1
$ docker exec ... select jurors joined users where jury_id=1
t06@test.example.com — the one San Jose resident whose post never became a
  solution (see Named questions, above)
$ GET /juries/mine (as t06) → items: [] before accept
$ POST /jurors/1/accept (as t06) → status: accepted
$ GET /juries/mine (as t06) → items: [10 items] after accept
$ POST /ballot-items/9/holdback (as t06, juror_id 1) → recorded
$ POST /admin/cycles/2/open → items_votable: 9, items_held_back: 1
$ PUT /cycles/2/ballot/1/vote (as t01,t02,t03,t04: yes; t05: no)
$ GET /cycles/2/ballot (as t01) → my_vote: "yes"; yes_count/no_count: null (not open-counted)
$ GET /cycles/2/ballot (as admin) → my_vote: null, no other voter's choice visible
$ GET /cycles/2/ballot (signed out) → my_vote: null, no voter data visible
   — CRITICAL trap confirmed clean: no endpoint returns a vote to anyone but its voter.
$ POST /admin/cycles/2/close → item 1: 4 yes / 1 no → passed; all-0/0 items → failed (below quorum)
$ POST /admin/cycles/2/publish → summary_hash 414780a...
  header.jury: "1 drawn, 0 replaced, 1 seated"; held_back[0].jury_reasons[0].juror: "Juror 1 of 1" (no name)

# Hash round-trip (independent, not the platform's own /verify):
$ curl .../summaries/city/408/2/json > summary2.json
$ python3 -c "canonical = json.dumps(d, sort_keys=True, separators=(',',':')); sha256(canonical)"
414780a961d23fc335634ba71c5eb7fa0b7548a44ac6d2611eb284c177820124
$ curl .../summaries/city/408/2/verify
stored_hash / recomputed_hash both 414780a9... — match: true
Independently recomputed hash matches both the platform's own verify endpoint
and the value in the publish response. MATCH.

$ POST /admin/settings {ballot_min_dominant_days: 3, reason: "restoring default"}
$ python3 backend/scripts/reconcile.py --dry-run    # after the full walkthrough
corrected: false; all four drift/orphan/mismatch lists empty.

# Refusal paths (new/changed endpoints):
$ POST /admin/cycles/prepare as a non-admin → 403 not_admin
$ GET /cycles/mine signed out → 401 not_signed_in
$ GET /feed?q=a → 422 "String should have at least 2 characters"
$ GET /feed?sort=bogus → 422 "Input should be 'newest', 'oldest', 'most_votes' or 'most_comments'"
$ GET /feed?limit=500 → 422 "Input should be less than or equal to 100"

# Feed sorts/search/pagination against the loaded dataset:
$ GET /feed?community=city:408&sort=newest → feed-v1, "newest", "Newest first."
$ GET /feed?community=city:408&sort=most_votes → ordered by vote_count desc, correct
$ GET /feed?community=city:408&q=pothole → finds exactly post 1 (problem text match)
$ GET /feed?scope=all → filters.scope "all", filters.default "all of California"
$ GET /feed?community=city:408&sort=most_votes&limit=2 → cursor MTF8NQ==
$ GET ...&cursor=MTF8NQ== → next page, no overlap/gap with page 1

# Admin log transparency:
$ GET /admin/log → grant_admin, every change_setting (with my reasons),
  every cycle transition all present, publicly readable.
```

**Rendered HTML (frontend running, backend running):**
```
$ curl :3000/            → 200, <title>Direct Democracy CA</title>, one "Join" button, 0 <img> tags
$ curl :3000/ (signed in, cookie) → 307 → /home
$ curl :3000/home        → 200, <title>Home · Direct Democracy CA</title>, 0 <img> tags
$ curl :3000/explained   → 200, <title>Direct Democracy Explained · Direct Democracy CA</title>, 0 <img> tags
$ curl :3000/feed        → 307 → /home
$ curl :3000/login?next=/admin → 200, <title>Sign in · Direct Democracy CA</title>
$ curl :3000/admin (signed out) → 200 (client-side auth gate; useRequireAuth confirmed by source read)
$ curl :3000/settings, /ai/actions, /admin/log → all 200 (untouched Foundation pages still serve)
$ grep footer links in home.html → /results, /settings, /ai/actions, /admin/log, /summaries/hashes,
  /legal/privacy, /legal/terms, /legal/cookies — all eight present
$ grep nav in home.html → "Direct Democracy Explained", "Home", "New post" — exactly three tabs
```
Note: several pages (`/cycles/[id]`, `/ballot`, nav auth-state) are client
components that fetch their data after hydration, so a bare `curl` shows the
pre-hydration shell only; those states were verified instead by reading the
actual component source against live API responses (the same technique the
build's own HISTORY entries describe using, since no headless browser is
reachable from this sandbox — `SANDBOX.md` §5/§7 already names this gap).

**Hand-derived cases:**
```
threshold(5, 3, 8) = 1        # dominant, 8 active users
threshold(5, 3, 100) = 3      # dominant, 100 active users
threshold(5, 3, 0) = 1        # never less than 1
threshold(10, 5, 40) = 4      # ballot, 40 active users
All four match the code's own output exactly.

next_cycle_dates(2026-03-01, "first_sunday_of_month", 2, []) = (2026-03-01, 2026-02-27)
  — 2026-03-01 independently confirmed a Sunday.
next_cycle_dates(2026-03-01, ..., 2, [2026-03-01]) = (2026-04-05, 2026-04-03)
  — 2026-04-05 independently confirmed a Sunday.
next_cycle_dates(2026-12-15, ..., 2, []) = (2027-01-03, ...)
  — 2027-01-03 independently confirmed a Sunday (December's own first Sunday, 2026-12-06, already passed).
pacific_today at 06:00 UTC 2026-03-02 = 2026-03-01 (still evening in Pacific); at 20:00 UTC = 2026-03-02.
All match backend/tests/test_rules.py's own asserted values.
```

**Document-edit verbatim checks:** `git diff origin/main...HEAD -- CLAUDE.md PROJECT.md DEMOCRACY.md
DATABASE.md ARCHITECTURE.md AUDIT.md SANDBOX.md` read in full and compared,
character for character, against `briefs/change-01.md` Part A (A1–A8) and
`briefs/change-01-fix-1.md`'s FX-02/FX-03 wording. Every edit matches
verbatim; no other line of any protected document moved.

**Closing:**
```
$ git diff origin/main...HEAD --stat   # unchanged from the start of this audit — no source edits made
$ git status
On branch change/01-site-shell; nothing to commit, working tree clean
```

## Checks passed

- §4.1 Constitution — both always-`CRITICAL` traps (vote shown to a non-voter; vote weight not solely the voter's choice): clean, reproduced live.
- §4.1 — no name/display-name stored, hashed, or published instead of resolved at read time (the summary's "Proposed and refined in the [community] workshop" carries no author; "Juror 1 of 1" carries no juror identity; checked live in the published documents above).
- §4.1 — no edit rewrites a row carrying a `content_hash` (unchanged code in this diff; FX-38/39 from Demo 1 fix run 5 still hold, confirmed by the full suite).
- §4.1 — no code path deletes a hashed row (FX-01, confirmed by the exact proof grep, reproduced and matched to the build's own claimed four hits).
- §4.1 — Law 8 (no democratic number typed into code or copy): `next_cycle_dates`'s explanation lives beside the code with `cycle_open_rule`'s only value read from settings; `explainers.tsx`'s digit grep re-run and every hit accounted for (doc-section references, a CSS class, or grammar logic — including one I checked personally: "Juror 1 of N" is an illustrative naming-pattern example, not a threshold).
- §4.1 — Law 9 (ranking documented beside the code, versioned): `FEED_SORTS`/`FEED_VERSION` in `rules.py`, each sort's explanation printed by the API and matched by test.
- §4.1 — Law 10 (`os.environ` only in `settings_env.py`): grep clean.
- §4.1 — Law 11 (no sync IO in `async def`): not touched by this diff; full suite (which includes the AST-based blocking-IO check) passed.
- §4.1 — Law 12 (no bare `except`, no real `TODO`/`FIXME`): grep clean (two hits are task-id citations, not open markers).
- §4.1 — ARCHITECTURE §2 layering (router→service→repository only): `test_layering.py`'s full suite, including the new `test_api_ts_browser_path_has_no_hostname_literal`, passed; `/cycles/mine` and `/feed` are each one service call.
- §4.2 — feed-v1's four sorts match DEMOCRACY.md §12.1's table exactly (`feed_page` in `posts_repo`), verified both by reading the SQL and by live `curl` against the loaded dataset.
- §4.2 — `GET /cycles/mine` matches ARCHITECTURE.md §6's field list exactly, verified live.
- §4.2 — the rhythm (`cycle_open_rule`, `next_cycle_dates`) matches DEMOCRACY.md §10.1, verified by three independently hand-derived dates plus a live `/cycles/mine` call.
- §4.2 — `threshold()` re-derived by hand for four cases (not just three), all matching.
- §4.2 — DEMOCRACY.md §7.4's `cycle_open_rule` setting is seeded, readable (`GET /settings`), and actually refused when set to an unknown value (unit test + this document's own re-verification).
- §4.2 — jury draw replayability (C1-12): confirmed by the passing test plus my own reading of `eligible_pool`'s deterministic sort and `draw`'s seeded sampler.
- §4.2 — FX-02's zero-item wording: confirmed on a *naturally occurring* zero-item cycle (San Jose cycle 1, prepared with default settings) as well as on the fix's own test, reading the exact frozen sentence from `settings_in_force` on both `/ballot` and `/cycles/{id}`, and the shorter Home-panel line keyed off `cycle.state === "prepared"`.
- §4.3 Security — signup refuses the reserved test-data domain unless `ALLOW_TEST_DATA=true` (unit tests both ways, reproduced live for the `true` case in my own walkthrough).
- §4.3 — every new/changed write endpoint refuses correctly: non-admin prepare (403), signed-out `/cycles/mine` (401), out-of-range feed params (422 with the specific field named).
- §4.3 — no secret in a committed file, log line, or `ai_actions.output` (grep clean; `.env` confirmed gitignored).
- §4.4 Evidence — full suite (256/2, independently reproduced), `verify_schema.py` (no drift), seed `--dry-run` (0 pending), `reconcile.py --dry-run` (clean before and after my walkthrough), a full cycle walkthrough with a genuinely independent hash round-trip (not just the platform's own `/verify`).
- §4.5 Frontend — every page this change touched renders (200) with the backend running; zero `<img>` tags anywhere (trivially images-off compatible); the footer's eight transparency links and the three nav tabs both confirmed present in rendered HTML; the two explainers use native `<details>/<summary>` (free, standard keyboard open/close — code-level confirmation; browser confirmation is on the director's list above).
- §4.5 — no client-side business logic duplicating the backend: the zero-item sentence, filing-status wording, and jury-eligibility logic all read their numbers/state from the API, never recompute a threshold in the frontend.
- §4.6 Documents — TODO.md's C1-01…C1-16 and FX-01…FX-04 all independently confirmed done as described; no id marked done that fails a check above.
- §4.6 — HISTORY.md's build and fix-1 entries record every decision the code shows; no undocumented decision found beyond the two flagged above.
- Foundation full pass (triggered by `settings_env.py`/`auth.py` in the diff) — bcrypt hashing, refresh-token rotation/reuse revocation, rate limiting, and anonymization are unchanged by this diff and still pass their existing tests in the full suite; the new `ALLOW_TEST_DATA`/`TEST_DATA_EMAIL_DOMAIN`/`TEST_DATA_PASSWORD` settings match ARCHITECTURE.md §3's wording exactly and are exercised live above.

## Document ambiguities

- `frontend/src/content/explainers.tsx`'s `BallotExplainer` reads "A ballot is expected to open on the first Sunday of each month" as a hardcoded phrase, rather than describing whatever `cycle_open_rule` is currently set to. This passes the brief's own proof (a grep for digits, since the phrase has none), and today it is accurate because `first_sunday_of_month` is the only rule `rules.py::CYCLE_OPEN_RULES` recognizes — but if a second rule is ever added, this sentence would silently stop being true for a community using a different one. Not a finding against this change (nothing is wrong today), but worth a note for whoever adds the second rule.
- `frontend/src/app/home/PageClient.tsx::filingWords` collapses the `needs_review` post state to one sentence ("Not filed — no umbrella covers this yet in one of its communities") rather than the four-way split DEMOCRACY.md §4.1 describes, including the no-active-umbrella-at-all case. The build's HISTORY entry records this as a deliberate decision (compact, aggregate wording for a card that can span several communities in different states; the full per-community sentence is the post page's job) and I judge that reading reasonable — DEMOCRACY §4.1's "never share a sentence" rule is about the post page's per-community detail, which does implement all four states correctly. Flagged here only because it is a real interpretive call, not because I disagree with it.

[[[ END OF REPORT ]]]
