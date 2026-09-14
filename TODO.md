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

*As of 2026-09-13. Nothing has been built against the new documents
yet. Phase 0 is complete except the optional search provider. The "legacy" code (`main`, commit 263d4c6) works but predates the
constitution's laws; Demo 1 replaces it.*

| Layer | Half | Status | Notes |
|---|---|---|---|
| Documents | — | All nine written; consistency audit 2026-09-13 applied; both briefs current | Ready for Demo 1 |
| Sandbox | — | Set up and verified 2026-09-12 | `sbx ports` syntax and audit read-only policy still open |
| GitHub | — | Public repo; `main` protected by ruleset; scoped sandbox token `ddc-sandbox` expires 2026-10-12 | |
| Infra (Docker Postgres + Redis) | F | Legacy, working | Secrets to be regenerated in Demo 1 |
| Backend skeleton | F | Legacy: sync ORM, routers hit DB directly | Replaced by layered async build |
| Auth | F | Legacy: JWT login only | Refresh, verification, reset not built |
| Accounts / identity / display | F | Not built | |
| Verification levels | F | Not built | `unverified` only in Demo 1 |
| User rights (export, delete) | F | Not built | |
| Legal pages | F | Not built | Placeholder text, marked draft |
| Geography seed | F | `seed_geography.yaml` + `seed_cities.csv` (483 cities) in `backend/config/` | |
| Officials directory | F | Not built | |
| Settings table + public pages (settings, AI log, admin log) | F | Not built | Transparency pages are Foundation (2026-09-13) |
| Admin role + log | F | Not built | |
| AI action log | F | Not built | |
| Umbrellas | I | Legacy: one test umbrella via raw SQL | Seed file needed |
| Posts + labeling | I | Legacy: works, violates Laws 7/10/11 | Rebuild |
| Feed | I | Legacy: newest first, no filters | feed-v0 |
| Solutions / versions / amendments | I | Legacy: solutions only, upvote-only | Rebuild |
| Comments | I | Not built | |
| Votes / net score / statuses | I | Not built | |
| Similarity | I | Not built | |
| References | I | Not built | |
| Jury | I | Not built | |
| Cycles / ballot | I | Not built | |
| Summary document | I | Not built | |
| Director controls | I | Not built | |
| Frontend | I/F | Legacy: signup, login, feed, post form | Rebuild per style brief |

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
- [ ] **F-01** `pyproject.toml` at repo root; `backend` as a package; layer directories per ARCHITECTURE §2
- [ ] **F-02** `settings_env.py` with every key in ARCHITECTURE §3; startup refuses on missing keys; `.env.example`
- [ ] **F-03** Async engine + session (asyncpg); Alembic with `foundation` and `iteration` branch labels
- [ ] **F-04** Redis client; rate limiter; typed exceptions and the single error handler
- [ ] **F-05** Structured logging with request ids

### Accounts and auth
- [ ] **F-06** `users`, `user_display_settings`, `terms_versions`, `terms_acceptances` (DATABASE §3.1, 3.2, 3.5)
- [ ] **F-07** Signup with `min_signup_age` check, terms acceptance and email verification token; `console` email backend
- [ ] **F-08** Login; access JWT with `jti`; refresh token rotation and reuse detection (DATABASE §3.3)
- [ ] **F-09** Logout with Redis `jti` blacklist
- [ ] **F-10** Password reset flow
- [ ] **F-11** `verified_user`, `admin_user`, `community_member` dependencies; `last_active_at` debounce
- [ ] **F-12** Display settings endpoint and author-display rendering rule
- [ ] **F-13** Data export (async job, JSON, expiring file) with the contributor registry (`export.py::register_contributor`, ARCHITECTURE §2)
- [ ] **F-14** Account deletion with the anonymization procedure (DATABASE §3.1)

### Reference data and record
- [ ] **F-15** Geography tables; seed from `seed_geography.yaml` (state, counties) and `seed_cities.csv` (all incorporated cities)
- [ ] **F-16** Officials table and seed
- [ ] **F-17** Settings table, seed, `services/settings.py` with cache, public `GET /settings` and history
- [ ] **F-18** `admin_actions` and `ai_actions` tables; public read endpoints
- [ ] **F-19** Seed runner `python -m backend.seed --dry-run/--apply` with two-way coverage report, `${VAR}` substitution, CSV input (DATABASE §5)
- [ ] **F-20** `verify_schema.py`; `reconcile.py` skeleton (Foundation checks only)

### Legal and frontend
- [ ] **F-21** Privacy policy, terms, cookie consent pages with placeholder text marked DRAFT; terms version recorded at signup
- [ ] **F-22** Frontend: signup, login, verify, forgot/reset, `/me`, legal pages; `api.ts` with in-memory access token and cookie refresh
- [ ] **F-24** Frontend transparency pages: `/settings`, `/ai/actions`, `/admin/log` (public) and `/admin` settings change (moved from I-27, 2026-09-13)

### Tests
- [ ] **F-23** Auth tests (rotation, reuse, blacklist); anonymization test; every endpoint's 401/403

---

## Phase 2 — Iteration, Demo 1

Demo mode. Built by a long run on `demo/01`. Rebuilt in Demo 2 from the
documents, not from this code.

### Data
- [ ] **I-01** Iteration schema, single fresh migration (DATABASE §4, including `post_solutions` and `umbrella_references`); `main_categories` sync from config
- [ ] **I-02** Umbrella seed from `seed_umbrellas.yaml`

### Posts and labeling
- [ ] **I-03** `POST /posts` per DEMOCRACY §4.1 (AI or pick; no propose); `posts` + `post_solutions` + `post_communities` in one transaction; `content_hash`; `label_status`
- [ ] **I-04** Ollama client; `ai/prompts/labeler.md`; `label_post` job writing `ai_actions` → `labels` → `post_communities` → solutions created per `post_solutions` row (`solutions.py::create_from_post_community`)
- [ ] **I-05** Confirm / correct label (correction moves unvoted, unamended solutions; otherwise records only); `label_retry` job
- [ ] **I-06** `GET /feed` feed-v0 with filters and the printed ranking explanation

### Workshop
- [ ] **I-07** Solutions with versions; author-edit rule; `GET /solutions/{id}`
- [ ] **I-08** Votes table; `PUT/DELETE /votes`; net-score recompute; `rules.py` with `threshold()` and docstring; `RULES_VERSION`
- [ ] **I-09** Dominant evaluation on vote and nightly; `dominant_since`
- [ ] **I-10** Amendments: create (dominant only), withdraw, absorption → new version, supersede others
- [ ] **I-11** Similarity: embed client, `similarity_check` job, `same`/`different` decisions, merged supporter counting
- [ ] **I-12** Comments: threaded, depth cap, edit window, soft remove, votes
- [ ] **I-13** References: user-added; AI recommendation pipeline with search client and two prompt files; useful/not-useful; rejection
- [ ] **I-14** Umbrella page endpoint assembling every DEMOCRACY §3.3 section including the AI action list

### Cycle
- [ ] **I-15** Cycles with state machine and `settings_snapshot`; one-open-per-community constraint
- [ ] **I-16** Prepare: qualification snapshot, frozen ballot items in `position` order, jury draw with logged pool and random bytes; zero-item `prepared → published` path
- [ ] **I-17** Jury: duties endpoint, accept/decline with replacement, `no_response` not seated, `seated_count` at open, hold-back with category and text, majority over seated jurors
- [ ] **I-18** Ballot: open/close, yes/no votes with verification level stamp, results with `simple_majority` and quorum
- [ ] **I-19** After close: `last_ballot_*` on solutions (passed, failed, held back alike); §7.2 condition 4 "needs new version to return"
- [ ] **I-20** Summary: canonical JSON, SHA-256, `summaries` row, public page data, `/verify`, `/hashes`, `/results`
- [ ] **I-21** PDF export with hash in footer
- [ ] **I-22** `mailto:` send-to-representatives with directory recipients
- [ ] **I-23** Admin endpoints for every director control (DEMOCRACY §13), each logging to `admin_actions`
- [ ] **I-24** `reconcile.py` Iteration checks (net scores, dominance, orphans, hashes)

### Frontend
- [ ] **I-25** `/feed`, `/posts/new`, `/umbrellas/[id]`, `/solutions/[id]`
- [ ] **I-26** `/ballot`, `/jury`, `/results`, `/summaries/...`
- [ ] **I-27** Cycle controls on `/admin` (the page itself is F-24)
- [ ] **I-28** Style brief applied; images-off check; keyboard and screen-reader pass on every page

### Tests
- [ ] **I-29** `rules.py` table-driven tests at boundaries
- [ ] **I-30** Full-cycle integration test (ARCHITECTURE §10)
- [ ] **I-31** Hash round-trip test on summaries, solution versions, and `post_solutions`
- [ ] **I-32** Export contributor `export_iteration.py::contribute` registered at startup; test that `DELETE /me` export contains the user's own ballot votes and nothing of anyone else's

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

---

*Last updated: 2026-09-13 — document consistency audit applied.*
