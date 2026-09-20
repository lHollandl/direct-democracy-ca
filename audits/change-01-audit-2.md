# Audit — change-01, run 2, 2026-09-20

## Summary

Re-audit of `change/01-site-shell` at `c5e9dc5` ("planning entry: browser
checks verified; re-audit questions"), the commit reached after fix run 2
(`audits/change-01-audit-1.md`'s HIGH 1 · MEDIUM 2, plus its two document
ambiguities). `git diff a5ff19c...HEAD --stat` (audit-1's commit to this
commit) touches only the files audit-1's findings named, plus their tests,
the two governed documents (`ARCHITECTURE.md`, `DEMOCRACY.md`) with their
brief-specified verbatim wording, and tracking files (`TODO.md`,
`HISTORY.md`, `briefs/`, `audits/`, `package-lock.json`). Per AUDIT.md §2's
re-audit rule, the diff stays inside what the findings named, so this
re-audit is the audit.

All five fix-run-2 items (FX-05 HIGH, FX-06 MEDIUM, FX-07 MEDIUM, FX-08
ambiguity 1, FX-09 ambiguity 2) were independently re-verified — re-read
against the verbatim brief text, re-tested with the existing suites, and
for FX-05 additionally probed with adversarial inputs beyond the brief's
own test list. All five hold. **CRITICAL 0 · HIGH 0 · MEDIUM 0 · LOW 1 ·
NOTE 2.** Both always-CRITICAL traps (a ballot vote returned to anyone but
its voter; a vote's weight depending on anything but the voter's choice)
were reproduced clean in my own full-cycle walkthrough against a freshly
loaded test dataset and real Ollama, including an independent SHA-256
hash round-trip and an independent replay of a jury draw from its logged
pool and bytes. All three named questions from the newest planning entry
are answered below with evidence, one of them (question 3) producing the
one LOW finding. **Verdict: CLEAN.**

## Findings

### [LOW] A leaked shell environment can silently defeat `test_ip_hash_is_salted_and_the_secret_is_required`
- Where: `backend/tests/test_auth.py::test_ip_hash_is_salted_and_the_secret_is_required`
- Document: none — a test-isolation issue, not a spec or constitution mismatch (CLAUDE.md Law 10 is still satisfied: `settings_env.py` remains the only module that reads the process environment; the gap is in how `pydantic_settings.BaseSettings` itself resolves values, not in a codebase module reading `os.environ` directly).
- What the document requires: n/a.
- What the code does: the test constructs `Settings(_env_file=None, **kwargs)` (every field except `IP_HASH_SECRET`) and asserts this raises `ValidationError`. `_env_file=None` only disables the dotenv-file source; `pydantic-settings`' default source order still falls back to `os.environ` for any field not in `kwargs`. If `IP_HASH_SECRET` (or any other required key) happens to already be set in the ambient shell — which happens whenever `.env` is `source`d or `export`ed into that shell, exactly as SANDBOX.md §6.7's own site-startup instructions do for manual browser testing — the fallback silently supplies the value, the expected error never raises, and the test fails with "DID NOT RAISE ValidationError". This is not hypothetical: it has now independently hit two separate build sessions (the original change/01 build, HISTORY.md Session 4; and fix run 2, HISTORY.md Session 7), each time requiring a manual diagnosis before the "real" pre-check suite could run.
- Evidence: reproduced live — `python -m pytest backend/tests/test_auth.py::test_ip_hash_is_salted_and_the_secret_is_required -q` passes in a clean shell; after `set -a; source .env; set +a` (the exact action SANDBOX.md §6.7 asks for) the same test fails with `Failed: DID NOT RAISE ValidationError`; unsetting those variables restores the pass. Both runs pasted in the Evidence log.
- Suggested fix: either give the test a `monkeypatch.delenv` fixture that clears every `Settings` field name from `os.environ` before constructing the probe instance, or set `model_config`'s source order to exclude the environment source for this one construction (e.g. via `Settings.settings_customise_sources` returning only `init_settings` when explicitly asked); either removes the dependency on the ambient shell being clean. Severity: LOW — real and recurring, but it only ever produces a false test failure (never a false pass that would hide a genuine missing-secret bug), and never reaches production behavior.

## Evidence log

**Step 0 pre-checks.**
- `git branch --show-current` → `change/01-site-shell`; `git log --oneline -3` → `c5e9dc5`, `ccf8325`, `e064312`.
- `ls audits/` before writing: `change-01-audit-1.md`, `demo-01-audit-1..6.md`. This report is run 2 (K=2).
- Write-protection: `touch backend/AUDIT_WRITE_TEST && echo WRITABLE` → **WRITABLE** (deleted immediately). The sandbox is not read-only; I relied on my own discipline. Final `git status` (below) shows nothing outside `audits/` changed.
- `.env` built from `.env.example` with generated `JWT_SECRET`/`IP_HASH_SECRET`/DB password and `OLLAMA_BASE_URL=http://192.168.1.165:11434` (SANDBOX.md §5's recorded address — re-checked reachable, not guessed).
- `curl -sS http://192.168.1.165:11434/api/tags` → 200, lists `llama3.2:latest` and `nomic-embed-text:latest` among others. **Ollama reached at the correct address for this run** (audit-1's own named gap).
- `docker compose --env-file .env -f infra/docker-compose.yml up -d` → `ddc_postgres`, `ddc_redis` both healthy.
- `pip install -e ".[dev]" --break-system-packages` (no venv available in this image; system Python 3.14, no `python3-venv` package — used `--break-system-packages` since the sandbox is disposable). `dev` extra needed for `psycopg[binary]`, which Alembic's sync `env.py` requires.
- `alembic upgrade foundation@head` → `25035d5b7ff5`. `alembic upgrade iteration@head` → `b4b4da0b6e54`. Both from empty, clean.
- `python -m backend.seed --dry-run` on empty DB → 597 pending writes, 16 umbrellas (`grep -c 'community:' backend/config/seed_umbrellas.yaml` → 16), `cycle_open_rule` present. `--apply`, then `--dry-run` again → 0 pending writes.
- `python backend/scripts/verify_schema.py` → `NO DRIFT`: ORM vs live, ORM vs scratch-from-migrations, scratch vs live (38 tables), Foundation/Iteration split (15/23, no overlap), every FK indexed.
- `python backend/scripts/reconcile.py --dry-run` → `corrected: false`, all four lists (`net_score_drift`, `dominance_changes`, `orphan_communities`, `hash_mismatches`) empty. Re-ran after loading test data and running a full cycle (below) — still clean.

**Full backend suite and frontend suites.**
- `pytest backend/tests -q` → **257 passed, 2 deselected** in 166.9s (matches fix run 2's own reported count exactly).
- Named question 2 (below) resolves the "2 deselected".
- Named question 3: reproduced the leaked-environment test failure directly. Clean shell: `pytest backend/tests/test_auth.py::test_ip_hash_is_salted_and_the_secret_is_required -q` → `1 passed`. After `set -a; source .env; set +a`: same test → `1 failed` — `Failed: DID NOT RAISE ValidationError`. After `unset`-ting the leaked variables: `1 passed` again. See the LOW finding above.
- `cd frontend && npm ci` → clean, 0 vulnerabilities. `npm test` → **15/15** (`node:test` via `tsx`, covers all 14 of FX-05's brief-specified `safeNextPath` cases plus one duplicate).
- `npm audit --audit-level=high` → **0 vulnerabilities**.
- `npm run build` → Turbopack, TypeScript clean, **25 routes** generated, matching the build's own count.

**FX-05 [HIGH] — `safeNextPath` re-verification.**
- Read `frontend/src/lib/nextPath.ts` and `nextPath.test.ts` in full: all 9 "Rejected" and 5 "Accepted" cases from the brief are present and pass.
- Independently probed the function (copied verbatim into a throwaway Node script, not the repo) with inputs beyond the brief's list: `/%5Cevil.example`, `/%2F%2Fevil.example`, `/..%2f..%2fevil.example`, `/@evil.example`, `/.evil.example`, NBSP/BOM/LS/PS Unicode space-likes before a path, `/%09evil.example`, a raw CR, `/%00/evil.example`, `http:/evil.example`, `/../../evil.example`, `/%5c%5cevil.example`, bare `\/evil.example` and `\\evil.example`. Every case either returned `null` or a same-origin path string (e.g. `/../../evil.example` → `/evil.example`) — **no bypass found**.
- `ARCHITECTURE.md` §9 diff (`git diff a5ff19c...HEAD -- ARCHITECTURE.md`) matches the brief's verbatim replacement text character for character, including the added sentence naming `frontend/src/lib/nextPath.ts::safeNextPath` as the guard.
- Confirmed the guard is wired into the real integration point: `frontend/src/app/login/PageClient.tsx:16` calls `safeNextPath(useSearchParams().get("next"))`. `curl http://127.0.0.1:3000/login?next=/admin` → 200.
- **CONFIRMED fixed.**

**FX-06 [MEDIUM] — naming re-verification.**
- `git grep -il 'democracy cali'` → only `HISTORY.md`, `archive/*`, `audits/*`, `briefs/change-01.md`, `briefs/evidence/demo-01/pages.txt` (the four documented historical exceptions).
- `git grep -ilE 'democracy[-_ .]*cali'` (the widened proof) → the same historical-exception files, plus `CLAUDE.md`, `PROJECT.md`, `TODO.md`. Read each hit: `CLAUDE.md:310` and `PROJECT.md:342` both cite the literal filename `DirectDemocracyCali_ProjectSummary_v2.md` in the Document Map's not-yet-absorbed list — confirmed this file does not exist anywhere in the working tree or in git history (`find . -iname '*ProjectSummary*'` and `git log --all --diff-filter=A --name-only | grep -i projectsummary` both empty) — it is a filename reference to a document outside this repository, pre-dating change/01, not a live branding string, and both documents are outside FX-06's editing authorization. `TODO.md`'s hit is its own description of this exact residue. Matches the fix-run-2 entry's claim exactly.
- `git diff a5ff19c...HEAD -- backend/routers/me.py backend/tests/test_account_rights.py` → filename prefix changed to `direct-democracy-ca-export-`, with a new `Content-Disposition` header assertion. `frontend/package.json`/`package-lock.json` → `"name": "direct-democracy-ca-frontend"` throughout.
- **CONFIRMED fixed; the named residue is accurately described and correctly out of scope.**

**FX-07 [MEDIUM] — AI-claim re-verification.**
- `grep -n -i "AI " frontend/src/app/explained/PageClient.tsx` — no "summarizes discussion"; reads "AI sorts posts into topics and suggests reference sources."
- Checked the landing page (`frontend/src/app/page.tsx`) and `explainers.tsx` — no unsupported AI claim in either.
- Read `DEMOCRACY.md` §9 (AI Roles) in full: three AI functions (labeler §9.1, similarity §9.3, reference recommendation §9.4) — "sorts posts into topics" (§9.1) and "suggests reference sources" (§9.4) are both true and complete as stated; no capability beyond these three is claimed anywhere on `/explained`, the landing page, or `explainers.tsx`.
- Rendered `curl http://127.0.0.1:3000/explained` → 200; the served HTML contains "sorts posts into topics and suggests reference sources" and does not contain "summarizes discussion".
- **CONFIRMED fixed.**

**FX-08 [ambiguity 1] — `CYCLE_RULE_WORDS` re-verification.**
- Read `frontend/src/content/explainers.tsx`: `CYCLE_RULE_WORDS = { first_sunday_of_month: "the first Sunday of each month" }`, `cycleRuleWords()` (plain text) and `CycleRuleWords` (JSX, links to Settings on an unknown key) both present.
- `grep -rn "CycleRuleWords|cycleRuleWords"` confirms wiring into `frontend/src/app/explained/Diagrams.tsx` (both the "Ballot open" step text and the `<desc>`), `explainers.tsx`'s own `BallotExplainer`, and `PageClient.tsx`'s "Two clocks" paragraph.
- Read `backend/tests/test_layering.py::test_cycle_rule_words_map_covers_every_cycle_open_rule` — reads `explainers.tsx` as text, asserts every `rules.py::CYCLE_OPEN_RULES` key has an entry. **Independently re-ran the drift check** by monkeypatching `CYCLE_OPEN_RULES` with an added fake rule in a disposable Python one-liner (no file edits) and re-running the same source-text check inline — it correctly reported the fake rule as missing, confirming the test construction actually catches drift, not merely that it currently passes.
- `DEMOCRACY.md`/`ARCHITECTURE.md` do not govern this file's prose directly (it is application content, not a constitution document), so no separate verbatim-text check applies here beyond the test above.
- **CONFIRMED fixed.**

**FX-09 [ambiguity 2] — document-only edit re-verification.**
- `git diff a5ff19c...HEAD -- DEMOCRACY.md` → exactly the four-sentence paragraph the fix-2 brief specified, inserted verbatim after "...transparency about weakness).", nothing else in the file changed.
- `git diff --stat` for this run's range shows no code file touched by this item.
- **CONFIRMED — document only, as specified.**

**Delete-trap check (Law 6).**
- `git grep -n -i 'session\.delete\|\.delete(\|DELETE FROM' -- backend/ ':!backend/tests'` → four hits, each read and confirmed:
  - `backend/clients/redis.py:100` — `client.delete(key)` is a Redis cache-key delete, not a database row.
  - `backend/routers/comments.py:49` — `DELETE /comments/{id}` route; `comments_service.remove` (read in full) sets `text_body = REMOVED_TEXT` and `removed_at`, the row is kept — a soft update.
  - `backend/routers/me.py:72` — `DELETE /me`; `account_service.delete_account` calls `anonymize(session, user)`, not a delete.
  - `backend/routers/votes.py:36` — `DELETE /votes`; `votes_service.withdraw` calls `votes_repo.remove_vote`, a genuine hard delete. `DATABASE.md` §4.12 (read) documents this exactly: `votes` carries no `content_hash`; it is "the only hard delete in Iteration."
- No other `delete`/`DELETE FROM` in `backend/` outside tests. **Clean.**

**Own full-cycle walkthrough (from scratch, against real Ollama).**
- `ALLOW_TEST_DATA=true`; database rebuilt from empty (`DROP SCHEMA public CASCADE`, both migration chains, seed `--apply`) after an earlier run hit the loader's `--log-path` requirement (see Named question 2's sibling note below) — this gave a clean, reproducible run.
- `python backend/scripts/load_test_data.py --apply` against real Ollama → **16 accounts, 40 posts, 310 votes, 27 comments, 0 skipped** — matches the original build's own C1-16 evidence exactly. Re-ran a second time immediately after: **0 new accounts/posts/comments; 310 votes "confirmed"** — idempotency confirmed independently (`PUT /votes` is itself idempotent, as the build's own notes say).
- `grant_admin.py t01@test.example.com --apply` → granted.
- Prepared a cycle for San Jose (city 408): 13 items qualified, jury pool 0 (all 8 residents authored a qualifying solution — reproduces the already-answered "0 eligible jurors" pattern; see below).
- **CRITICAL check 1 (no ballot vote returned to anyone but its voter):** logged in as t01/t02/t03/admin(t01) in turn and cast/fetched votes on ballot item 1. Each account's `GET /cycles/1/ballot` shows only `my_vote` for itself (`null` before voting, then its own choice) — `yes_count`/`no_count` are `null` while the cycle is open for every viewer, admin included. No endpoint or query (`item_tallies` in `backend/repositories/cycles.py:235`, read in full: `select(BallotVote.ballot_item_id, BallotVote.choice, func.count())` — no voter id ever leaves this function) returns another voter's choice or identity. **Clean.**
- **CRITICAL check 2 (vote weight depends only on choice):** read `backend/services/ballots.py::cast` — stores `verification_level` on the row for reporting only; `backend/repositories/cycles.py::item_tallies` counts rows with a bare `func.count()`, grouped by `choice` alone, no multiplier by verification level or admin status anywhere in `close_ballot`/`rules.ballot_result`. Cast yes/no/yes as t01/t02/t03 (one admin among them) on item 1; closed the ballot → tally reported exactly `{"yes": 2, "no": 1}`, i.e. one vote per account regardless of admin status. **Clean.**
- Closed the cycle, published it. **Hash round-trip:** fetched `GET /summaries/city/408/1/json`, ran `sha256sum` on the raw response locally → `d5111808a60a1c5f7106b2f86bbb1783396b9d34ef25bc9e237511c1638e73be`, identical to the `summary_hash` the publish call returned and to `GET /summaries/city/408/1/verify`'s own `recomputed_hash` (`match: true`). Independently confirmed, not just trusted from the API's self-report.
- Summary JSON contains no author name or display name anywhere — each result carries `"workshop_note": "Proposed and refined in the San Jose workshop"` and a bare `solution_url`, per the already-established FX-28 (demo-01) fix, still intact.
- **Jury-draw replay (C1-12):** prepared a second cycle (Santa Clara County, entity 43) that drew a non-trivial jury (`eligible_pool_size: 1, drawn: 1`). Read the stored `juries` row directly from Postgres: `eligible_pool = [5]`, `random_bytes = 540db992689ef753ae5a2a809133a0f5e1cf75ab87edded79ea63b42a16cf16c`. **Independently replayed** (`random.Random(int(random_bytes,16)).sample(pool, 1)`, in a bare Python one-liner using only the logged pool and bytes, not the app code) → `[5]`, matching the `jurors` table's actual drawn `user_id` exactly.
- **Zero-item cycle:** prepared San Jose a second time (its qualifying solutions had already been on a ballot and none had changed since) → `items: []`, `zero_item_note: "No solution qualified. Publish this cycle when ready and the next one can be prepared; no jury is drawn for an empty ballot."`, and `GET /cycles/{id}/ballot` on it returns `settings_in_force` with that cycle's own `ballot_min_dominant_days: 0` — confirming FX-02's snapshot mechanism (from fix run 1, already covered by audit-1) is still intact after fix run 2.
- Restored `ballot_min_dominant_days` to 3 with a logged reason afterward.

**Hand-derived `threshold()` cases (`backend/services/rules.py:127`).**
`threshold(pct, minimum, denominator) = max(1, min(ceil(pct/100 * denominator), minimum))`. Four cases run against the real function:
| pct | minimum | denominator | hand-derived | code returned |
|---|---|---|---|---|
| 5.0 | 3 | 8 | ceil(0.4)=1 → max(1,min(1,3))=**1** | 1 |
| 10.0 | 5 | 8 | ceil(0.8)=1 → max(1,min(1,5))=**1** | 1 |
| 10.0 | 5 | 100 | ceil(10)=10 → max(1,min(10,5))=**5** | 5 |
| 25.0 | 3 | 0 | ceil(0)=0 → max(1,min(0,3))=**1** | 1 |
All four match. The third case exercises the "fixed minimum caps a large-community percentage" branch; the fourth exercises "never less than one."

**Grep checks.**
- `grep -rn "TODO\|FIXME" backend/ frontend/src/` → two hits, both `backend/services/juries.py:85` and `backend/tests/test_jury_and_ballot.py:67`, both docstring citations of TODO.md's task id `D2-00` (already marked done) describing why the code is shaped this way — not an open/unfinished marker. No bare `TODO`/`FIXME` left as unfinished work.
- `grep -rn "os.environ" backend/ | grep -v settings_env.py` → empty.
- `grep -rn "except:\s*$|except: pass|except Exception: pass" backend/` → empty.
- `grep -rn "fetch(" frontend/src | grep -v lib/api.ts` → empty.

**Rendered pages (backend + frontend both running).**
- `curl http://127.0.0.1:3000/explained` → 200; verified AI-claim wording above.
- `curl http://127.0.0.1:3000/login?next=/admin` → 200; `safeNextPath` wiring confirmed in the page source.
- `curl http://127.0.0.1:3000/ballot`, `/jury`, `/home` → 200 each.
- Settings-driven prose (the "Two clocks" `CycleRuleWords` text, the explainer bodies) is client-rendered after a `/settings` fetch and does not appear in the raw SSR HTML a plain `curl` captures (confirmed by the "Loading" placeholder present instead) — consistent with every prior change/01 build/fix entry's own note that this class of content needs a `renderToStaticMarkup` harness or a browser to see rendered, neither of which is available in this sandbox (SANDBOX.md, "no browser can be installed"). FX-08's wiring and its backend drift-test were verified at the source level instead (above), which is sufficient corroboration given the mechanism (a plain object lookup keyed by a settings value already proven to flow through `/settings`) carries no async or state complexity a static read could hide.

**`git diff --stat a5ff19c...HEAD`** (audit-1's commit to this commit): 17 files — `ARCHITECTURE.md`, `DEMOCRACY.md`, `HISTORY.md`, `TODO.md`, `audits/change-01-audit-1.md`, `backend/routers/me.py`, `backend/tests/test_account_rights.py`, `backend/tests/test_layering.py`, `briefs/audit.md`, `briefs/change-01-fix-2.md`, `frontend/package-lock.json`, `frontend/package.json`, `frontend/src/app/explained/Diagrams.tsx`, `frontend/src/app/explained/PageClient.tsx`, `frontend/src/content/explainers.tsx`, `frontend/src/lib/nextPath.test.ts`, `frontend/src/lib/nextPath.ts` — exactly the set FX-10's own evidence claimed, independently reproduced.

**Final `git status`:** `nothing to commit, working tree clean` (before adding this report and the HISTORY.md paragraph). Two Next.js-auto-generated files (`frontend/AGENTS.md`, `frontend/CLAUDE.md`, written by `next dev` itself on startup) appeared as untracked during my own walkthrough and were deleted before this check — not part of the change, never committed.

## Checks passed

- §4.1 Constitution: both always-CRITICAL traps (vote-to-non-voter, vote-weight-not-by-choice); name/display-name resolved at read time (summary carries no author name, confirmed live); no edit rewrites a `content_hash` row (delete-trap grep, all four hits accounted for); `os.environ` outside `settings_env.py`; bare/swallowing `except`; router-touches-repository (covered by the passing `test_layering.py` AST checks, unchanged by this diff).
- §4.2 Specification conformance: `threshold()` re-derived by hand, 4 cases, all match; jury draw replayed independently from logged pool + bytes; zero-item cycle states the rule with its own settings snapshot.
- §4.3 Security: `safeNextPath` — brief's 14 cases plus 19 additional adversarial probes, no bypass; write-endpoint/rate-limit posture unchanged by this diff (not touched).
- §4.4 Evidence: full backend suite (257/2, both "live" tests independently run and passed), `npm test` (15/15), `verify_schema.py` (no drift), seed `--dry-run` (0 pending, 16 umbrellas), `reconcile.py --dry-run` (clean, both before and after live activity), hash round-trip (independently recomputed, matches).
- §4.5 Frontend: `/explained`, `/login`, `/ballot`, `/jury`, `/home` render (200); no stray `fetch`; `npm run build` clean, 25 routes; `npm audit --audit-level=high` clean.
- §4.6 Documents: `ARCHITECTURE.md` and `DEMOCRACY.md` edits both verbatim-matched to the fix-2 brief, character for character; no other line of either file moved; `TODO.md`'s FX-05…FX-10 lines match what was actually done.

## Scope

Diff since audit-1 (`a5ff19c...HEAD`) touches one Foundation file
(`backend/routers/me.py` — DATABASE.md §2 places account/export under
Foundation) and its test. That file was explicitly named by audit-1's own
FX-06 finding text ("the data-export filename (`backend/routers/me.py`)"),
so it is inside what the reported findings named, not a stray Foundation
touch. Per AUDIT.md §2's re-audit rule ("Inside them → the re-audit is the
audit"), I did not run a full unscoped Foundation pass (every §4 check
against every Foundation file) on top of the re-audit; I did independently
re-verify the one Foundation change itself (the filename constant and its
new test assertion) and ran the delete-trap grep and both CRITICAL vote
checks, which are Foundation-adjacent and always in scope regardless. I
name this judgment call explicitly in Document ambiguities below rather
than deciding it silently, since the "any Foundation file in the diff"
sentence in AUDIT.md §2 does not say whether it is subordinate to the
re-audit carve-out or stands independently of it.

No other file outside what FX-05 through FX-09 named was touched, so
Iteration likewise stays at the re-audit's scope, not a full pass.

## Named questions

**1. Reach Ollama at the SANDBOX.md §5 address; load the test data;
confirm the ten `file_under: ai` posts are labeled, and paste each one's
umbrella.**

Ollama reached at `http://192.168.1.165:11434` (confirmed reachable
before use, not guessed — audit-1's own named gap). All 16 test accounts,
40 posts, 310 votes, 27 comments loaded through the live HTTP API. All
ten `file_under: {level: ai}` posts came back `label_status = "labeled"`
(none `needs_review`, none `unlabeled`):

| post id | problem (excerpt) | community | umbrella assigned |
|---|---|---|---|
| 4 | Parents double-park and block the bike lane... | San Jose (city) | Pedestrian Safety Near Schools |
| 9 | Street lights are out along three full blocks... | San Jose (city) | Pedestrian Safety Near Schools |
| 10 | The city council votes on large developments... | San Jose (city) | Road Damage and Pothole Repair |
| 16 | On bad smoke days, people without air conditioning... | Santa Clara County | Wildfire Smoke and Air Quality Response |
| 17 | The county's public health clinics are only open... | Santa Clara County | Bus and Light Rail Frequency |
| 24 | Central Park's lake path floods every winter... | Fremont (city) | Downtown and Small Business Vitality |
| 25 | Fremont has one of the largest library branches... | Fremont (city) | Downtown and Small Business Vitality |
| 32 | The county's property tax and permit websites... | Alameda County | Homelessness Services and Shelter Capacity |
| 39 | Insurance companies are cancelling homeowner policies... | California (state) | Electricity Costs and Reliability |
| 40 | The DMV requires an in-person visit... | California (state) | Public Access to Government Records |

Each has a corresponding `ai_actions` row (`action_type = "label"`,
`model = "ollama:llama3.2"`, a real `confidence`, `human_outcome =
"unreviewed"`) written before the result was shown, satisfying Law 7.

**NOTE (not a finding):** several of these assignments are topically
weak — e.g. post 9 (street lights) landing under "Pedestrian Safety Near
Schools", post 10 (government-meeting accessibility) under "Road Damage
and Pothole Repair". Checking the actual umbrella set per community
(`umbrellas` table, queried directly), none of San Jose's four city-level
umbrellas is a strong match for either topic — the model was choosing
"closest" among a genuinely poor set of options, not ignoring a good one.
`ai_actions.output.repeated_or_unlisted_communities` for several of these
rows shows the model also inventing or echoing communities never
selected (e.g. `"city:1"`, `"state:15"`), which the code correctly
discards and logs — the exact mitigation TODO.md's existing Technical
Debt entry ("Small models answer for communities that were never
listed") already describes. This is expected, already-documented,
already-mitigated small-model imperfection with a working correction
path (DEMOCRACY §9.1, "the author can confirm or correct"), not a new
code defect, and change/01 did not touch the labeler.

**2. Fix run 2 reports "257 passed, 2 deselected". Which two tests, why
are they deselected, and do they pass when selected in a clean shell?**

`pyproject.toml`'s `[tool.pytest.ini_options]` defines `markers = ["live:
hits the real Ollama; opt in with -m live"]` and `addopts = "-m 'not
live'"` — the two deselected tests are both in
`backend/tests/test_live_ollama.py`
(`test_the_labeler_prompt_still_produces_the_shape_the_code_parses`,
`test_embeddings_come_back_the_same_length_and_compare_sensibly`), each
marked `@pytest.mark.live`. This is a documented, intentional opt-in
(`ARCHITECTURE.md:413`: "opt-in test (`-m live`) hits the real Ollama to
validate prompt-file..."), not a skip added to make the suite green. I
ran `pytest backend/tests/test_live_ollama.py -m live -v` in a clean
shell against the real Ollama at the SANDBOX.md §5 address: **both
passed.** Not a finding.

**3. Fix run 2 saw two tests fail when `ALLOW_TEST_DATA=true` and the
`.env` values were exported in the shell. Should the suite be isolated
from the process environment? Severity is the auditor's call.**

Reproduced directly: in a clean shell,
`test_ip_hash_is_salted_and_the_secret_is_required` passes; after
`set -a; source .env; set +a` (the exact action SANDBOX.md §6.7's
site-startup instructions ask for) it fails with "DID NOT RAISE
ValidationError"; unsetting those variables restores the pass. Root
cause: `Settings(_env_file=None, **kwargs)` only disables the dotenv-file
source — `pydantic-settings`'s default source order still falls back to
`os.environ` for any field not supplied via `kwargs`, so a required key
already present in the ambient shell silently satisfies the constructor
the test expects to fail. This is `test_auth.py`'s
`test_ip_hash_is_salted_and_the_secret_is_required` alone; the other
failure mode both build sessions independently hit
(`ALLOW_TEST_DATA=true` left set from a prior test-data-script run
against the one real `.env`) is a separate, already-documented gotcha
(HISTORY.md, 2026-09-20 build entry and fix-run-2 entry both name it) —
not a test-suite isolation bug, since there is deliberately no separate
test-only `.env` (`Settings` reads the one real file directly). Yes, the
suite should be isolated from the process environment for the
`_env_file=None` idiom specifically — recorded above as **[LOW]**, since
it only ever produces a false failure, never a false pass that would
hide a real missing-secret bug.

**Secondary observation surfaced while answering question 1 (not a
finding, offered as a note):** `backend/scripts/load_test_data.py` shares
the exact fixed-log-path mechanism (`--log-path`, default
`/tmp/uvicorn.log`, reading verification-email tokens from the server's
own log) that TODO.md's Technical Debt already names for
`walkthrough_extended.py`, but that entry currently names only the
latter script. I hit this directly: my first loader run, with the
backend logging elsewhere, failed with exactly the error the script's
own docstring predicts, and a database rebuild plus restarting the
backend with `> /tmp/uvicorn.log` was needed before the loader could run
end to end. The script documents the requirement itself
(`--log-path`, described in its own header) and offers the flag as a
workaround, so this is not a code defect — just a Technical Debt entry
that could name both scripts instead of one. Left for the director; not
a finding since nothing was narrowed or misrepresented.

## Browser-only checks

Per the newest planning entry (2026-09-20, "change/01 browser checks;
re-audit questions"), the director verified all seven items in the
browser and none remain outstanding:

- Sign in, reload the page, still signed in. — **director-verified**
- Type `/admin` while signed out, sign in, land on `/admin`. — **director-verified**
- The three tabs and the footer on a phone-width window. — **director-verified**
- The landing page redirects to Home when signed in. — **director-verified**
- Search, each sort, and "All of California" on Home. — **director-verified**
- The ballot switch is remembered after a reload. — **director-verified**
- Both "How it works" buttons open and close by keyboard. — **director-verified**

## Document ambiguities

1. **Does the re-audit carve-out subordinate the "any Foundation file in
   the diff → full Foundation audit" rule, or does the latter stand
   independently?** AUDIT.md §2 states both as separate sentences with no
   explicit ordering between them. This run's diff touches one Foundation
   file (`backend/routers/me.py`) that a reported finding (FX-06) itself
   named. I read this as "inside them" for the re-audit clause and did not
   run every §4 check against every Foundation file on that basis alone —
   see Scope above. If the director intends the Foundation-file rule to
   fire regardless of re-audit scope, that changes this run's required
   depth (though not, I believe, its verdict: the one Foundation change is
   a filename constant, independently re-verified above, and this run
   separately covers the two always-CRITICAL vote checks and the Law 6
   delete-trap grep, which are the highest-stakes Foundation-adjacent
   items §4.1 names by name).
2. **Should TODO.md's Technical Debt entry for the fixed `/tmp/uvicorn.log`
   path name `load_test_data.py` alongside `walkthrough_extended.py`?**
   Not a document the audit brief authorizes me to edit; noted for the
   next planning session (see Named question 2's secondary observation).
