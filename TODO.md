# TODO.md — Task Tracker

> The living task tracker. Every task has a phase, an id, a status, and
> a home in the documents. Design decisions live in DEMOCRACY.md,
> DATABASE.md, ARCHITECTURE.md. History lives in HISTORY.md. Rules live
> in CLAUDE.md.
>
> Claude Code reads this at the start of every session and updates it
> at the end. Status symbols: `[ ]` not started · `[~]` in progress ·
> `[x]` done · `[!]` blocked · `[-]` dropped (reason in HISTORY).

---

## Current Status Snapshot

*As of 2026-09-15. Demo 1 is built on `demo/01`: both halves, front to back,
from an empty database. The full cycle runs — signup through a published,
verifiable results document — and the test suite and the manual walkthrough are
in `briefs/evidence/demo-01/`. Audit run 1 returned FIX REQUIRED (one HIGH,
three LOW); fix run 1 (FIX-01 through FIX-07) is complete. Audit run 2
returned FIX REQUIRED (CRITICAL 1 · HIGH 1 · MEDIUM 6 · LOW 7 · NOTE 3); fix
run 2 (FIX-08 through FIX-20) is complete. Audit run 3 returned FIX REQUIRED
(HIGH 1 · MEDIUM 3 · LOW 2); fix run 3 (FIX-21 through FIX-27) is complete —
all seven previously-unpaginated list endpoints now paginate, reference
recommendation runs as a background job with a "recommending" indicator on
the umbrella page, label confirm/correct require a verified user,
`geo.py::community`/`::officials` and `amendments.py::propose_amendment` are
down to one service call each (plus four further offenders the stricter
layering test found: `references.py::reference_feedback` and three
`summaries.py` endpoints paired with a resolver that wasn't named
`require_*`), the mailto/PDF footer/verify-section URLs are absolute via the
new `PUBLIC_BASE_URL`, and `ARCHITECTURE.md §7`'s `build_export` row was
confirmed to already match the code (no change needed). Full evidence in
HISTORY.md's Session 7 entry. Nothing has been merged to `main`; the next
audit run comes next — likely a re-audit under AUDIT.md §2 given how small
this run was. Phase 0 remains complete except the optional search provider.
This run also found the sandbox could pull Docker Hub blob-CDN images for
the first time (`docker compose up` succeeded cleanly), unlike every prior
run — see Technical Debt.*

| Layer | Half | Status | Notes |
|---|---|---|---|
| Documents | — | All nine current; consistency audit 2026-09-13 applied | Demo 1 built from them |
| Sandbox | — | Set up and verified 2026-09-12; boundaries confirmed again by this run | The Docker Hub blob CDN and the browser download host are **not** reachable — see technical debt |
| GitHub | — | Public repo; `main` protected; scoped sandbox token `ddc-sandbox` expires 2026-10-12 | `demo/01` pushed from the sandbox |
| Infra (Docker Postgres + Redis) | F | `infra/docker-compose.yml` on postgres:16 and the single root `.env`; ran cleanly in this sandbox (fix run 2) | Legacy `backend/.env` and `infra/.env` were committed secrets; both removed and a `.gitignore` added |
| Backend skeleton | F | Built: layered async on asyncpg, typed errors, request ids, rate limiting | Legacy code deleted |
| Auth | F | Built: signup with the age gate, email verification, login, refresh rotation with reuse detection, logout blacklist, password reset | |
| Accounts / identity / display | F | Built | |
| Verification levels | F | `unverified` only, disclosed in aggregate, never weighted | |
| User rights (export, delete) | F | Built, with the Iteration contributor registered at startup | |
| Legal pages | F | Built; placeholder text marked DRAFT, recorded as a terms version at signup | |
| Geography seed | F | 1 state, 58 counties, 483 cities | |
| Officials directory | F | Built and seeded; every address is `OFFICIALS_TEST_EMAIL` | |
| Settings table + public pages | F | Built; 22 settings, all of DEMOCRACY §7.4 | `reference_reject_min` and `min_signup_age` were missing from the seed file and were transcribed from §7.4 |
| Admin role + log | F | Built; the admin flag is granted only by a script on the machine, and that grant is logged | |
| AI action log | F | Built; public, filterable, written before any AI result is shown | |
| Umbrellas | I | Built; 10 seeded across the three test communities | |
| Posts + labeling | I | Built; labeler runs on the host GPU, output shape constrained by the prompt file | |
| Feed | I | `feed-v0`, with the rule printed on the page | |
| Solutions / versions / amendments | I | Built, including absorption, supersession and the diff | |
| Comments | I | Built: threaded, depth-capped, edit window, soft remove | |
| Votes / net score / statuses | I | Built; recomputed from the rows on every vote | |
| Similarity | I | Built on Ollama embeddings; humans decide | |
| References | I | User-added built; AI recommendation built but never run against a real provider | |
| Jury | I | Built: draw, logged pool and randomness, accept/decline with replacement, hold-back over seated jurors | |
| Cycles / ballot | I | Built, including the zero-item path | |
| Summary document | I | Built: canonical JSON, SHA-256, verifier, hash list, PDF, `mailto:` | |
| Director controls | I | Built; every one writes to the public admin log | |
| Frontend | I/F | Every route in ARCHITECTURE §9 built and rendering | No browser available, so no screenshots |
| Demo database | — | Rebuilt from empty for fix run 1 and reloaded by `walkthrough_extended.py`; `ballot_min_dominant_days` back to 3 | San Jose cycle 1 is published (passed); Santa Clara County cycle 1 (empty) is published and cycle 2 is `prepared` with zero items, waiting on the director to publish it before a third can be prepared |

---

## Phase 0 — Migration to the New Framework

Done in Claude.ai planning sessions; no Claude Code involved.

- [x] **P0-01** CLAUDE.md rewritten and approved (2026-09-07)
- [x] **P0-02** PROJECT.md written
- [x] **P0-03** DEMOCRACY.md written
- [x] **P0-04** DATABASE.md written
- [x] **P0-05** ARCHITECTURE.md written
- [x] **P0-06** TODO.md restructured (this file)
- [x] **P0-07** HISTORY.md converted to the new format
- [x] **P0-08** AUDIT.md written
- [x] **P0-09** SANDBOX.md written (Docker Sandboxes on Ubuntu, Ollama from the VM, scoped token, worktree-per-trial)
- [x] **P0-10** Demo 1 build brief written
- [x] **P0-11** New Claude.ai project instructions written (PROJECT_INSTRUCTIONS.md; director installs it in the project settings) (document-writer and reviewer role, not prompt-writer)
- [x] **P0-12** Seed files (DATABASE.md §5): all five drafted and moved to `backend/config/` 2026-09-13; umbrella placeholders remain the director's to revise at any time before the run
- [ ] **P0-13** Director obtains a web search API key and names the provider (ARCHITECTURE §8.2)
- [x] **P0-14** Repo housekeeping (PR #1 merged 2026-09-12; follow-up PR swaps in the full city list and removes PROJECT_INSTRUCTIONS.md from the repo) on `main` by PR: move HOPES.md, the Summary, and old `docs/design/` to `archive/`; delete `files(2)`, `files(3)`, `files(4)`; add the new documents; add `.env.example`; regenerate `infra/.env` and `backend/.env` secrets locally
- [x] **P0-15** Sandbox set up and verified 2026-09-12: all seven boundary checks passed (SANDBOX.md §7)
- [x] **P0-16** Audit brief `briefs/audit.md` written 2026-09-13 (was referenced by SANDBOX.md §6.5 but never written)

---

## Phase 1 — Foundation, first build (in Demo 1)

Full rigor. Built by a long run; audited by AUDIT.md procedure; merged
to `main` by PR when the audit passes. Each id is a unit the brief and
the audit refer to.

### Infrastructure
- [x] **F-01** `pyproject.toml` at repo root; `backend` as a package; layer directories per ARCHITECTURE §2
- [x] **F-02** `settings_env.py` with every key in ARCHITECTURE §3; startup refuses on missing keys; `.env.example`
- [x] **F-03** Async engine + session (asyncpg); Alembic with `foundation` and `iteration` branch labels
- [x] **F-04** Redis client; rate limiter; typed exceptions and the single error handler
- [x] **F-05** Structured logging with request ids

### Accounts and auth
- [x] **F-06** `users`, `user_display_settings`, `terms_versions`, `terms_acceptances` (DATABASE §3.1, 3.2, 3.5)
- [x] **F-07** Signup with `min_signup_age` check, terms acceptance and email verification token; `console` email backend
- [x] **F-08** Login; access JWT with `jti`; refresh token rotation and reuse detection (DATABASE §3.3)
- [x] **F-09** Logout with Redis `jti` blacklist
- [x] **F-10** Password reset flow
- [x] **F-11** `verified_user`, `admin_user`, `community_member` dependencies; `last_active_at` debounce
- [x] **F-12** Display settings endpoint and author-display rendering rule
- [x] **F-13** Data export (async job, JSON, expiring file) with the contributor registry (`export.py::register_contributor`, ARCHITECTURE §2)
- [x] **F-14** Account deletion with the anonymization procedure (DATABASE §3.1)

### Reference data and record
- [x] **F-15** Geography tables; seed from `seed_geography.yaml` (state, counties) and `seed_cities.csv` (all incorporated cities)
- [x] **F-16** Officials table and seed
- [x] **F-17** Settings table, seed, `services/settings.py` with cache, public `GET /settings` and history
- [x] **F-18** `admin_actions` and `ai_actions` tables; public read endpoints
- [x] **F-19** Seed runner `python -m backend.seed --dry-run/--apply` with two-way coverage report, `${VAR}` substitution, CSV input (DATABASE §5)
- [x] **F-20** `verify_schema.py`; `reconcile.py` skeleton (Foundation checks only)

### Legal and frontend
- [x] **F-21** Privacy policy, terms, cookie consent pages with placeholder text marked DRAFT; terms version recorded at signup
- [x] **F-22** Frontend: signup, login, verify, forgot/reset, `/me`, legal pages; `api.ts` with in-memory access token and cookie refresh
- [x] **F-24** Frontend transparency pages: `/settings`, `/ai/actions`, `/admin/log` (public) and `/admin` settings change (moved from I-27, 2026-09-13)

### Tests
- [x] **F-23** Auth tests (rotation, reuse, blacklist); anonymization test; every endpoint's 401/403

---

## Phase 2 — Iteration, Demo 1

Demo mode. Built by a long run on `demo/01`. Rebuilt in Demo 2 from the
documents, not from this code.

### Data
- [x] **I-01** Iteration schema, single fresh migration (DATABASE §4, including `post_solutions` and `umbrella_references`); `main_categories` sync from config
- [x] **I-02** Umbrella seed from `seed_umbrellas.yaml`

### Posts and labeling
- [x] **I-03** `POST /posts` per DEMOCRACY §4.1 (AI or pick; no propose); `posts` + `post_solutions` + `post_communities` in one transaction; `content_hash`; `label_status`
- [x] **I-04** Ollama client; `ai/prompts/labeler.md`; `label_post` job writing `ai_actions` → `labels` → `post_communities` → solutions created per `post_solutions` row (`solutions.py::create_from_post_community`)
- [x] **I-05** Confirm / correct label (correction moves unvoted, unamended solutions; otherwise records only); `label_retry` job
- [x] **I-06** `GET /feed` feed-v0 with filters and the printed ranking explanation

### Workshop
- [x] **I-07** Solutions with versions; author-edit rule; `GET /solutions/{id}`
- [x] **I-08** Votes table; `PUT/DELETE /votes`; net-score recompute; `rules.py` with `threshold()` and docstring; `RULES_VERSION`
- [x] **I-09** Dominant evaluation on vote and nightly; `dominant_since`
- [x] **I-10** Amendments: create (dominant only), withdraw, absorption → new version, supersede others
- [x] **I-11** Similarity: embed client, `similarity_check` job, `same`/`different` decisions, merged supporter counting
- [x] **I-12** Comments: threaded, depth cap, edit window, soft remove, votes
- [~] **I-13** References: user-added; AI recommendation pipeline with search client and two prompt files; useful/not-useful; rejection — all built and covered by tests against a mocked provider; **never run against a real one**, because no `SEARCH_API_KEY` exists (P0-13). The admin trigger answers 503 `search_not_configured`, which is the documented behaviour.
- [x] **I-14** Umbrella page endpoint assembling every DEMOCRACY §3.3 section including the AI action list

### Cycle
- [x] **I-15** Cycles with state machine and `settings_snapshot`; one-open-per-community constraint
- [x] **I-16** Prepare: qualification snapshot, frozen ballot items in `position` order, jury draw with logged pool and random bytes; zero-item `prepared → published` path
- [x] **I-17** Jury: duties endpoint, accept/decline with replacement, `no_response` not seated, `seated_count` at open, hold-back with category and text, majority over seated jurors
- [x] **I-18** Ballot: open/close, yes/no votes with verification level stamp, results with `simple_majority` and quorum
- [x] **I-19** After close: `last_ballot_*` on solutions (passed, failed, held back alike); §7.2 condition 4 "needs new version to return"
- [x] **I-20** Summary: canonical JSON, SHA-256, `summaries` row, public page data, `/verify`, `/hashes`, `/results`
- [x] **I-21** PDF export with hash in footer
- [x] **I-22** `mailto:` send-to-representatives with directory recipients
- [x] **I-23** Admin endpoints for every director control (DEMOCRACY §13), each logging to `admin_actions`
- [x] **I-24** `reconcile.py` Iteration checks (net scores, dominance, orphans, hashes)

### Frontend
- [x] **I-25** `/feed`, `/posts/new`, `/umbrellas/[id]`, `/solutions/[id]`
- [x] **I-26** `/ballot`, `/jury`, `/results`, `/summaries/...`
- [x] **I-27** Cycle controls on `/admin` (the page itself is F-24)
- [~] **I-28** Style brief applied; images-off check passes (the platform ships no `<img>` and no background image at all); keyboard and structural accessibility audited statically — labels bound to every control, native focusable controls, focus never removed, 44px targets, landmarks, a skip link, live regions, a distinct browser-tab title per page. **No screen reader and no browser were run**: the sandbox cannot download one. Evidence in `briefs/evidence/demo-01/a11y.txt`.

### Tests
- [x] **I-29** `rules.py` table-driven tests at boundaries
- [x] **I-30** Full-cycle integration test (ARCHITECTURE §10)
- [x] **I-31** Hash round-trip test on summaries, solution versions, and `post_solutions`
- [x] **I-32** Export contributor `export_iteration.py::contribute` registered at startup; test that `DELETE /me` export contains the user's own ballot votes and nothing of anyone else's

---

## Phase 2a — demo-01 fix run 1

Fixes for `audits/demo-01-audit-1.md` (CRITICAL 0 · HIGH 1 · MEDIUM 0 ·
LOW 3 · NOTE 2; verdict FIX REQUIRED), from `briefs/demo-01-fix-1.md`. Each
id is one commit on `demo/01`; full evidence in
`briefs/evidence/demo-01/fix-1-verification.txt`.

- [x] **FIX-01** Layering (HIGH): every router calls only services, every
  service reads and writes only through its aggregate's repository module;
  `backend/tests/test_layering.py` added (AST-based, enforces both rules and
  that no router imports a job)
- [x] **FIX-02** Background-job scheduling moved from routers into the
  service that owns the transaction (resolves audit ambiguity 1; now in
  ARCHITECTURE.md §2/§7)
- [x] **FIX-03** `pyproject.toml`'s `version` fixed to PEP 440
  (`"0.1.0"`); `pip install -e .` succeeds; `BUILD_LABEL` unaffected
- [x] **FIX-04** `comments.content_hash` was missing `parent_id`
  (DATABASE.md §4.11); `amendments.content_hash` already matched §4.9
  exactly
- [x] **FIX-05** HISTORY.md correction: Session 1's "199 passed" narrative
  should read 201 (the evidence file and the audit both say so); corrected
  in Session 3's entry, Session 1's left as-is (append-only)
- [x] **FIX-06** `backend/scripts/walkthrough_extended.py`: six accounts
  exercise the two-community post (four `solutions` rows), a jury
  decline-with-replacement and a no-response juror, a hold-back short of a
  majority, and a zero-item cycle publish that unblocks the next one —
  none of which three accounts can produce
- [x] **FIX-07** Re-ran the build brief's full evidence set (migrations from
  empty, `verify_schema.py`, seed dry-run, full test suite including
  `test_layering.py`, every required grep, `git status`/`git log`) after
  FIX-01 through FIX-06; all clean

---

## Phase 2b — demo-01 fix run 2

Fixes for `audits/demo-01-audit-2.md` (CRITICAL 1 · HIGH 1 · MEDIUM 6 ·
LOW 7 · NOTE 3; verdict FIX REQUIRED), from `briefs/demo-01-fix-2.md`. Each
id is one commit on `demo/01` except FIX-14 and FIX-18 (no code change
needed); full evidence in HISTORY.md's Session 5 entry.

- [x] **FIX-08** (CRITICAL) Deep replies: `comments.reply_to_comment_id`
  added; `text` is never a rendered name; "replying to @display" rendered at
  read time through the author-display rule; `content_hash` covers the new
  field
- [x] **FIX-09** (HIGH) Jury draws are never deleted: `juries.cycle_id` no
  longer unique; `superseded_at` with a partial unique index on the current
  jury; a redraw supersedes instead of deleting; `GET /cycles/{id}` lists
  every draw with its status
- [x] **FIX-10** (MEDIUM) Every hold-back published: "Jury notes" on the
  solution page from ballot open; "Juror concerns" under any summary result
  a juror held back without a majority
- [x] **FIX-11** (MEDIUM) Router logic: `get_solution` and every other
  multi-module endpoint (seven in `admin.py`, two in `amendments.py`,
  `auth.py::logout`, `summaries.py::summary_pdf`,
  `umbrellas.py::umbrella_solutions`) reduced to one service call each;
  `test_layering.py` extended with an AST check for it
- [x] **FIX-12** (MEDIUM) Labeler records communities it invents, not only
  ones it repeats, in `output.repeated_or_unlisted_communities`
- [x] **FIX-13** (MEDIUM) `GET /umbrellas` paginates (the only one of the
  five originally-flagged endpoints not exempted by ARCHITECTURE §6's
  updated wording); `limit > 100` refused with 422
- [x] **FIX-14** (MEDIUM) `grant_admin.py` already matched ARCHITECTURE §4
  exactly, including `--revoke`; no code change, `--help` evidenced
- [x] **FIX-15** (MEDIUM) `next` 16.1.6 → 16.3.5; `npm audit fix`;
  `npm audit --audit-level=high` clean
- [x] **FIX-16** (LOW ×7) Narrowed and logged the two swallowing exception
  handlers; moved the seed CSV read behind `asyncio.to_thread`; replaced a
  stale docstring; named the label-retry fallback constant; fixed the
  `bad_setting_value` grammar; every route gained server-rendered Next.js
  `metadata`; verified the five undocumented endpoints are already in
  ARCHITECTURE §6
- [x] **FIX-17** WCAG 2.1 AA: `useFormError` (aria-invalid/aria-describedby,
  focus management) applied to every form; every page's `PageHeader`
  (and therefore its one `<h1>`) now renders unconditionally, including
  during the loading and sign-in-gate states, not only once data has
  loaded
  - **[~]** `posts/new`'s dynamic solutions list and community checkboxes
    are not individually field-mapped to `aria-invalid` — only
    `problem_text` and the page-level banner are covered there
- [x] **FIX-18** Comment depth wording: no code change; DEMOCRACY §6's
  0-based depth already matches the code; re-confirmed with the depth-cap
  test
- [x] **FIX-19** Summary header reads "*n* drawn, *r* replaced, *s* seated";
  `replaced` counts `declined` jurors on the current jury, not the DB status
  `replaced` (reserved for a whole superseded jury)
- [x] **FIX-20** Full evidence set re-run from empty (migrations,
  `verify_schema.py`, seed dry-run, full suite — 211 + 2 live — every
  required grep, both walkthroughs, `npm audit`, `git status`/`git log`);
  all clean

---

## Phase 2c — demo-01 fix run 3

Fixes for `audits/demo-01-audit-3.md` (HIGH 1 · MEDIUM 3 · LOW 2; verdict
FIX REQUIRED), from `briefs/demo-01-fix-3.md`. Full evidence in HISTORY.md's
Session 2 entry (2026-09-15).

- [x] **FIX-21** (HIGH) All seven previously-unpaginated list endpoints now
  paginate: `umbrellas.py::umbrella_solutions`, `::umbrella_comments`,
  `::umbrella_references`, `transparency.py::settings_history`,
  `ballots.py::community_cycles`, `amendments.py::list_amendments`,
  `summaries.py::hash_list`; `backend/tests/test_pagination.py` added, a
  completeness check over every live GET route, not a hand-picked list
- [x] **FIX-22** (MEDIUM) `recommend_references` now runs as a background
  job (`backend/jobs/references.py`), scheduled via `spawn_after_commit`
  after a fast synchronous eligibility check; the endpoint returns 202
  `{"status": "pending"}`; the umbrella references listing reports
  `"recommending"` until the `ai_actions` row exists
- [x] **FIX-23** (MEDIUM) `posts.py::confirm_label` and `::correct_label`
  now require `VerifiedUser`, not merely a signed-in user
- [x] **FIX-24** (MEDIUM) `geo.py::community` and
  `amendments.py::propose_amendment` reduced to one service call each;
  `test_layering.py` now counts distinct service functions, not modules —
  the stricter test found four further offenders
  (`geo.py::officials`, `references.py::reference_feedback`,
  `summaries.py::summary_json`/`::summary_verify`/`::summary_pdf`), all
  fixed rather than narrowing the test
- [x] **FIX-25** (LOW) `PUBLIC_BASE_URL` added (`settings_env.py`,
  `.env.example`); the `mailto:` body, the PDF footer, and the summary
  page's verify section all use an absolute URL now
- [x] **FIX-26** (LOW) No code change — `build_export` already matched
  ARCHITECTURE §7's job table; confirmed by reading the code directly
- [x] **FIX-27** Full evidence set re-run (migrations, `verify_schema.py`,
  seed dry-run, full suite — 218 + 2 live — every required grep,
  `npm audit`, `git status`/`git log`); all clean

---

## Phase 3 — Demo 2 candidates

Not scheduled. Pulled forward by the director after Demo 1 is used.

- [ ] **D2-01** Proposal system (PROJECT.md parking lot) — "propose a new umbrella" in the post form; proposal tables; thresholds; dormancy; similarity grouping
- [ ] **D2-02** Comment moderation (needed before the friends beta)
- [ ] **D2-03** Real quorum decision and implementation
- [ ] **D2-04** Hysteresis on dominant status, if the audit shows flapping
- [ ] **D2-05** AI writing assist on the post form (makes AI influence real)
- [ ] **D2-06** Email notifications for jury duty and ballot open
- [ ] **D2-07** Timers firing for jury review and ballot window (replacing director controls)
- [ ] **D2-08** Deployment for the friends beta; HTTPS; invite gate; final legal text

---

## Director Decisions Pending

Questions the documents flag; Demo 1 proceeds with the stated default.

| # | Question | Default | Where |
|---|---|---|---|
| 1 | Hysteresis on dominant status | none | DEMOCRACY §7.1 |
| 2 | Real ballot quorum | 1 | DEMOCRACY §10.4 |
| 3 | Jury for tiny communities | proceed with fewer/none, say so | DEMOCRACY §8.1 |
| 4 | Amendment absorbed by a single upvote on an unsupported solution | allowed | DEMOCRACY §15 |
| 5 | "Strong" votes anywhere | no | DEMOCRACY §15 |
| 7 | Web search provider | unchosen; 503 until set | ARCHITECTURE §8.2 |
| 8 | Hosting for friends beta | local only | PROJECT.md parking lot |
| 9 | Residents of unincorporated areas have no city to select at signup (~10% of Californians) | blocked at signup | proposed: selectable "Unincorporated [County] County" → county + state communities only; decide before friends beta |

Resolved 2026-09-13 (see HISTORY): #6 keep home city/county — now CLAUDE §6.

---

## Technical Debt

What makes it bite, not only what it is.

- **Legacy code on `main` violates Laws 7, 10, 11** (inline prompt string, module-level Ollama constants, sync sessions in async handlers). Bites the moment anything is built on top of it. Resolved by Demo 1 replacing it; until then, nothing new is built on `main`.
- **Polymorphic community reference** `(community_level, community_entity_id)` cannot be a database FK. Orphans are possible on a bad write. Mitigated by `services/community.py::resolve` on every write and the nightly orphan check. Bites if a write path bypasses the service.
- **Denormalized `net_score` and `is_dominant`** can drift from the vote rows under concurrent votes. Mitigated by recompute-on-vote inside the transaction and nightly reconcile. Bites at scale; acceptable for demos.
- **Solutions are duplicated per community** (one row per solution text per umbrella, DEMOCRACY §4.1). Copies drift apart by design; nothing links their amendment histories except the `post_solution_id`. Bites if users expect an amendment in the county umbrella to appear in the city one — watch for it when using the demo.
- **`console` email backend** means no real verification email; Demo 1 reads links from the log. Bites at the friends beta — SMTP must be configured and tested first.
- **Redis loss fails rate-limiting open.** Acceptable locally; must be revisited before deployment.
- **Iteration ids restart per demo**; `ai_actions.demo_build` disambiguates but nothing else does. Bites if any Foundation table ever stores an Iteration id without the build label — the audit checks for this.

### Found by the Demo 1 build run (2026-09-14)

- **The sandbox cannot pull container images.** `docker compose up` fails: the
  Docker Hub registry is reachable but the blob CDN
  (`production.cloudfront.docker.com`) is not on the allowlist. The demo-01 run
  therefore ran PostgreSQL 16.14 from a wheel and a Redis-protocol server in
  process, and `infra/docker-compose.yml` **has never been started**. Bites the
  moment the director or an audit run assumes the compose file works — it is
  written from the documents, not from a successful run. Add the CDN host to
  the sandbox policy, or accept that infrastructure is only ever tested on the
  workstation. **Resolved in fix run 3's sandbox (2026-09-15):** the blob CDN
  was reachable and `docker compose --env-file .env -f infra/docker-compose.yml
  up -d` pulled `postgres:16` and `redis:7` and started both containers
  cleanly — this run used the real compose file for the first time. Left open
  as debt since it depends on the sandbox's own network policy at the time,
  not on anything this repository controls, and could regress on a future
  sandbox.
- **No browser can be installed in the sandbox.** The Chrome-for-Testing
  download host is blocked, so no build run can take a screenshot, drive a page,
  or run an automated accessibility audit. Every frontend claim in this build is
  a static audit plus a server-render check. Bites whenever a UI regression is
  only visible in a browser — nothing in the sandbox will catch it.
- **Background jobs depend on the process staying up.** A job is started from a
  SQLAlchemy `after_commit` hook. If the process dies between the commit and the
  job, nothing has run. `label_retry` now sweeps up posts left at `pending` past
  the retry window as well as `unlabeled` ones, so labeling recovers; the
  similarity check and the export build have no such sweep. Bites as a silently
  missing similarity flag or an export that never becomes downloadable.
- **`ballot_min_dominant_days` has to be lowered to walk through a demo in one
  day.** The walkthrough does this as a logged settings change, which is the
  right mechanism, but it means the build's own evidence never exercises the
  three-day rule. Bites if the rule is wrong: nothing here would show it. The
  setting was put back to 3 the same way at the end of the run, so the public
  history reads 3 → 0 → 3; the *habit* is the debt, not the value.
- **A three-person community cannot produce a three-person jury.** The draw
  excludes the authors of every qualified solution and every administrator, so
  the demo's jury was one person and a hold-back needed one voice. The
  behaviour is correct and documented (DEMOCRACY §8.1), but the majority rule is
  only meaningfully exercised by the test suite, not by the demo. Bites when
  reading the demo as evidence that the jury works at size.
- **Small models answer for communities that were never listed.** `llama3.2`
  repeated a community and echoed communities from the prompt's example. The
  labeler keeps the first answer that names an umbrella actually present in that
  community and records the rest in the public AI log. Bites if a future prompt
  change removes that defence, or if a larger model is assumed to need it less.
- **Passwords are capped at 72 bytes** because that is bcrypt's limit and a
  longer password would be silently truncated. The signup form says so. Bites
  as a surprise for anyone using a long passphrase from a password manager.
- **Next.js 16.1.6 did not apply nested-layout metadata** to the server-rendered
  head in this build, so each page sets its own browser-tab title from the
  client instead. Bites for anything that reads the served HTML — link previews,
  search engines — until the cause is found. **Resolved in fix run 2 (FIX-16):**
  every route now exports server-side `metadata` from a thin server `page.tsx`
  wrapping the client component; the cause was never isolated, but the
  workaround makes it moot.
- **Export files sit on local disk** under `var/`, deleted by an hourly job past
  their expiry. Bites at deployment: there is no shared storage and no
  encryption at rest.

### Found by demo-01 fix run 1 (2026-09-14)

- **`juries_service.redraw` marks the outgoing jurors `status = "replaced"`
  and then deletes their jury row**, whose `ON DELETE CASCADE` removes those
  juror rows before the status change is ever visible to a reader. Found
  while moving the function to comply with layering (FIX-01); preserved
  exactly, since the fix brief named layering, not this. Bites if anything
  ever reads a redrawn jury's history expecting to find `replaced` rows —
  today, nothing does. **Resolved in fix run 2 (FIX-09):** a redraw now sets
  `superseded_at` on the old row instead of deleting it.
- **`backend/scripts/walkthrough_extended.py` reads verification tokens from
  `/tmp/uvicorn.log`**, a fixed path, on the assumption the server's
  stdout/stderr is redirected there. Bites if the server is ever run with
  logging configured differently — the script will time out looking for a
  token that was written somewhere else.
- **The labeler does not reliably find a matching umbrella when one post
  goes to two communities with different topics on offer.** FIX-06's
  walkthrough needed the documented author-correction path
  (`POST /posts/{id}/label/correct`) to file both communities, even with a
  problem text written to closely match one umbrella name per community.
  Bites anyone assuming AI labeling alone files every multi-community post;
  it is designed to be correctable for exactly this reason (DEMOCRACY §9.1),
  but a demo script or a new user could still be surprised by a `needs_review`.

### Found by demo-01 fix run 2 (2026-09-14)

- **`posts/new`'s accessibility wiring is incomplete.** `useFormError` covers
  `problem_text` and the page-level banner, but the dynamic solutions list
  and the community checkboxes are not individually mapped to
  `aria-invalid`/`aria-describedby` — there was no clean per-item `name` to
  key off for the solutions array, and the checkboxes don't map to a single
  backend field. Bites if the backend ever returns a `problems` entry for
  `solutions.1` or a specific community: today it only surfaces in the
  page-level banner, not on the specific control.
- **`backend/scripts/walkthrough_fix2.py` (like `walkthrough_extended.py`)
  is not safely re-runnable against the same database** without a fresh
  `run_id` suffix on every email/display name, and a failed attempt can
  leave a stray non-published cycle that blocks the next prepare
  (DEMOCRACY §10.1). Both are handled in the script (a timestamp suffix, a
  cleanup step that publishes any stray cycle first) but the underlying
  fragility — demo/evidence scripts assume a clean run — remains.
- **DATABASE §4.17 and DEMOCRACY §8.2/§11.2 use "replaced" for two different
  mechanisms**: a `jurors.status` value reachable only on a jury a redraw
  superseded, and the summary header's per-seat replacement count, which
  actually counts `status = declined` on the *current* jury. Flagged in
  HISTORY.md's Session 5 entry for a clarifying sentence in DATABASE §4.17.

---

*Last updated: 2026-09-15 — demo-01 fix run 3 completed on `demo/01` by an unattended Claude Code run.*
