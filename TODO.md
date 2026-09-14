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

*As of 2026-09-14. Demo 1 is built on `demo/01`: both halves, front to back,
from an empty database. The full cycle runs — signup through a published,
verifiable results document — and the test suite and the manual walkthrough are
in `briefs/evidence/demo-01/`. Nothing has been merged to `main`; the audit run
comes next. Phase 0 remains complete except the optional search provider.*

| Layer | Half | Status | Notes |
|---|---|---|---|
| Documents | — | All nine current; consistency audit 2026-09-13 applied | Demo 1 built from them |
| Sandbox | — | Set up and verified 2026-09-12; boundaries confirmed again by this run | The Docker Hub blob CDN and the browser download host are **not** reachable — see technical debt |
| GitHub | — | Public repo; `main` protected; scoped sandbox token `ddc-sandbox` expires 2026-10-12 | `demo/01` pushed from the sandbox |
| Infra (Docker Postgres + Redis) | F | `infra/docker-compose.yml` rebuilt on postgres:16 and the single root `.env`; **not run in this sandbox** | Legacy `backend/.env` and `infra/.env` were committed secrets; both removed and a `.gitignore` added |
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
  workstation.
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
  three-day rule. Bites if the rule is wrong: nothing here would show it.
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
  search engines — until the cause is found.
- **Export files sit on local disk** under `var/`, deleted by an hourly job past
  their expiry. Bites at deployment: there is no shared storage and no
  encryption at rest.

---

*Last updated: 2026-09-14 — Demo 1 built on `demo/01` by an unattended Claude Code run.*
