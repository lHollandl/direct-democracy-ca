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

*As of 2026-09-21, branch `change/02-who-and-where`: change/02 fix run 1
done; director's look, then full Foundation audit. `change/01-site-shell`
was merged to `main` 2026-09-20 (PR #6, squash `a85ccee`) after audit run 2
came back CLEAN (CRITICAL 0 · HIGH 0 · MEDIUM 0 · LOW 1); branch deleted.
change/02 — unincorporated residents, account editing, the home-change rule,
and the AI's suggestion on the draft before posting — is built per
`briefs/change-02.md`; see "Change 02" below for C2-01 through C2-13 and
HISTORY.md's latest entry for full evidence. It is the first change to
touch the Foundation schema since Demo 1 (an appended migration; the first
Foundation migration is untouched). Fix run 1 (FX-01 through FX-07,
`briefs/change-02-fix-1.md`) then applied what the director found using the
change: step 4 redesigned with no Keep control, an unverified author
stopped at step 1 with a working "Send me a new link", demo mail so a demo
environment needs no terminal, "Your posts" on the account page, and
`llama3.1:8b` as the labeling model. No schema change was needed.
Demo 1 was built on `demo/01`:
both halves, front to back,
from an empty database. The full cycle runs — signup through a published,
verifiable results document — and the test suite and the manual walkthrough are
in `briefs/evidence/demo-01/`. Audit run 1 returned FIX REQUIRED (one HIGH,
three LOW); fix run 1 (FIX-01 through FIX-07) is complete. Audit run 2
returned FIX REQUIRED (CRITICAL 1 · HIGH 1 · MEDIUM 6 · LOW 7 · NOTE 3); fix
run 2 (FIX-08 through FIX-20) is complete. Audit run 3 returned FIX REQUIRED
(HIGH 1 · MEDIUM 3 · LOW 2); fix run 3 (FIX-21 through FIX-27) is complete.
Audit run 4 returned FIX REQUIRED (CRITICAL 1 · MEDIUM 6 · LOW 3 · NOTE 3);
fix run 4 (FIX-28 through FIX-37) is complete. Audit run 5 returned FIX
REQUIRED (CRITICAL 0 · HIGH 2 · MEDIUM 5 · LOW 8 · NOTE 4) — the first audit
with no CRITICAL; fix run 5 (FIX-38 through FIX-51, FIX-52 evidence) is
complete — a solution edit and a comment edit are both a new hashed row now
(version n+1; a `comment_revisions` row), never a rewrite, so
`reconcile.py` never raises on ordinary use of either edit window; every
`backend/jobs/*` module calls services only, with `reconcile.py`'s query
logic moved into `backend/services/reconcile.py`; the landing page and
`frontend/src/lib/api.ts` are once again the only two files with a `fetch`
call between them (down to one, `api.ts`, with the landing page routed
through it); `jury_review_days` is consulted for a "would close on ..." the
same way the ballot window already was; the solution page renders "Jury
notes"; comments and amendments carry their AI-influence label; two more
files had blocking IO the AST check couldn't see (now fixed and covered);
the similarity "Same" shortcut no longer also settles "Different"; IP hashes
are salted; an expired export is refused immediately, not after the hourly
sweep; the `mailto:` body is composed in the service, not the router; and
`GET /umbrellas/{id}`, `GET /results`, `GET /solutions/{id}` embed only the
first page of the lists they show, with a `next_cursor`, per ARCHITECTURE
§6's now-explicit rule. Full evidence in HISTORY.md's latest build entry.
`demo/01` merged to `main` 2026-09-19 and tagged `demo-1`; work proceeds by
`change/NN` branches. Phase 0 remains complete except the optional search
provider.*

| Layer | Half | Status | Notes |
|---|---|---|---|
| Documents | — | All nine current; consistency audit 2026-09-13 applied | Demo 1 documents final; Demo 2 brief pending director's use notes |
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

**Demo 1 status:** six audits, run 6 CLEAN (CRITICAL 0 · HIGH 0 · MEDIUM 1). Merged to `main` 2026-09-19 as the one-time exception (PROJECT.md). Not the keeper; the director is using it.

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
- [~] **I-28** Style brief applied; images-off check passes (the platform ships no `<img>` and no background image at all); keyboard and structural accessibility audited statically — labels bound to every control, native focusable controls, focus never removed, 44px targets, landmarks, a skip link, live regions, a distinct browser-tab title per page. Residue, named in full (audit demo-01 run 5, LOW — FIX-51: the previous wording named only the first of these): **no screen reader and no browser were run** (the sandbox cannot download one); and the style brief's **California photography in page headers is unbuilt** — ARCHITECTURE.md §9 now records this as intended, not missing, until the director supplies the images, so it is named here as a settled decision rather than an open gap. Evidence in `briefs/evidence/demo-01/a11y.txt`.

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
  `"recommending"` until the `ai_actions` row exists.
  **Correction (audit demo-01 run 4):** this was marked `[x]` with the
  backend half done but the umbrella page never rendering the "AI is
  looking for references…" indicator the brief and the service
  docstring promised — the narrowing this brief itself forbids. The UI
  half was missing until fix run 4's FIX-30 rendered the `recommending`
  flag on `frontend/src/app/umbrellas/[id]/PageClient.tsx`.
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

## Phase 2d — demo-01 fix run 4

Fixes for `audits/demo-01-audit-4.md` (CRITICAL 1 · MEDIUM 6 · LOW 3 ·
NOTE 3; verdict FIX REQUIRED), from `briefs/demo-01-fix-4.md`. Each id is
one commit on `demo/01`; full evidence in HISTORY.md's latest build entry.

- [x] **FIX-28** (CRITICAL) `summaries_service.build_data` no longer writes
  `author_display_at_snapshot` (or any user id or name) into the canonical
  JSON; each result and held-back entry instead carries a fixed
  `workshop_note` ("Proposed and refined in the [community] workshop") and
  an absolute `solution_url`, per DEMOCRACY §11.1/§11.2 item 2; `pdf.py` and
  the summary page render the new fields. Test publishes a summary whose
  author displays their real name, asserts the page payload, the
  downloadable JSON, and the PDF text (its ASCII85+Flate stream, decoded)
  contain neither the real name nor the display name, deletes the account,
  and asserts the summary still verifies with an unchanged hash while the
  linked solution page reads "Former Community Member"
- [x] **FIX-29** (MEDIUM) `comments_service.create`: at the depth cap,
  `parent_id` is now `parent.parent_id` (was `parent.id`), keeping
  `reply_to_comment_id = parent.id` — DEMOCRACY §6, "under the same
  parent". Test: five sequential replies render depths `[0, 1, 2, 3, 3]`,
  the fifth a sibling of the fourth under the third, "replying to @…"
  intact
- [x] **FIX-30** (MEDIUM) The umbrella page renders the `recommending` flag
  the API has exposed since fix run 3's FIX-22
  (`frontend/src/app/umbrellas/[id]/PageClient.tsx`); FIX-22's note above
  corrected to say the UI half was missing until this run. Evidence:
  a real `GET /umbrellas/{id}` payload with `recommending: true`, mounted
  through the actual `PageClient` component in a scratch jsdom harness —
  rendered HTML contains `AI is looking for references…`
- [x] **FIX-31** (MEDIUM) `export.py`'s blocking file IO
  (`EXPORT_DIR.mkdir`, `path.write_text`, `path.exists`, `path.unlink`) now
  runs through `asyncio.to_thread`. `test_layering.py` gained an AST check,
  `test_no_blocking_file_io_inside_async_def`, walking every `async def` in
  `backend/services` and `backend/jobs` for a direct `open(`, `os.*`, or
  blocking pathlib IO call — confirmed failing against the pre-fix
  `export.py` (named all four offending calls) and passing after
- [x] **FIX-32** (MEDIUM) `EXPORT_FILE_HOURS` added to `settings_env.py`
  (required — no default, startup refuses without it, confirmed) and
  `.env.example` (48); `request_export`'s `expires_at` reads it instead of
  the old bare module constant `EXPORT_LIFETIME_HOURS`. Director decision
  recorded below: configuration, not a settings-table value
- [x] **FIX-33** (LOW) `security.py::validate_password`'s message now says
  "no longer than 72 bytes", not "characters"; the signup and
  reset-password form hints explain what that means in plain language.
  Test: a 41-character, 81-byte password is refused with "72 bytes" in the
  message
- [x] **FIX-34** (LOW) `frontend/src/app/page.tsx` is now an async Server
  Component that reads `jury_size` from `GET /settings` (falling back to
  wording with no number on a fetch failure) instead of the literal "Three
  neighbours"; verified against the real backend and `next start` that the
  rendered number follows a live setting change
- [x] **FIX-35** (LOW) `backend/jobs/exports.py`'s `build_export_task` and
  `expire_exports_task` now log `job_start`/`job_end` with a `job_id`, the
  same shape `labeling.py`, `references.py`, and `similarity.py` use
- [x] **FIX-36** `test_authorization.py` gains
  `test_every_write_endpoint_is_sorted_into_exactly_one_named_set`, walking
  the live route table (like `test_pagination.py`) into `PUBLIC_WRITE_PATHS`,
  `SIGNED_IN_WRITE_PATHS` (including the three own-account exceptions), and
  `ADMIN_WRITE_PATHS` — confirmed it actually catches a gap by removing one
  entry and watching it fail naming that exact route
- [x] **FIX-37** Full evidence set re-run (migrations, `verify_schema.py`,
  seed dry-run, full suite — 222 + 2 live — every required grep, `npm
  audit`, frontend `tsc`/`lint`/`build`, `git status`/`git log`); all clean.
  This run's diff stayed inside the ten findings' named files plus tests,
  the FIX-30 frontend page, `.env.example`, and `settings_env.py`
  (`git diff 013ec19..HEAD --stat`: 19 files)

---

## Phase 2e — demo-01 fix run 5

Fixes for `audits/demo-01-audit-5.md` (CRITICAL 0 · HIGH 2 · MEDIUM 5 ·
LOW 8 · NOTE 4; verdict FIX REQUIRED — the first audit with no CRITICAL),
from `briefs/demo-01-fix-5.md`. Each id is one commit on `demo/01`; full
evidence in HISTORY.md's latest build entry.

- [x] **FIX-38** (HIGH) `solutions_service.edit_text` now calls `add_version`
  — the same mechanism absorption uses — instead of mutating the existing
  `solution_versions` row's text, hash and timestamp in place (CLAUDE.md
  Law 6; DATABASE.md §4.8). Test: edit a solution twice, assert three
  version rows with three distinct hashes, `reconcile.py --dry-run` clean.
- [x] **FIX-39** (HIGH) Iteration migration adds `comment_revisions` and
  `comments.current_revision` (DATABASE.md §4.11); revision 1 is written
  with the comment in the same transaction; `comments_service.edit` inserts
  revision n+1 and updates `text`/`current_revision`/`edited_at`;
  `comments.content_hash` stays revision 1's hash forever;
  `reconcile.py` checks every revision's hash and the comment's hash
  against revision 1. The thread payload carries `current_revision` and
  `revision_history`. Dev database rebuilt from empty (schema changed).
- [x] **FIX-40** (MEDIUM) `backend/jobs/labeling.py`, `similarity.py` and
  `references.py` no longer import a repository directly — each calls a
  thin service wrapper instead; `reconcile.py`'s whole query logic moves to
  `backend/services/reconcile.py` (reading through each aggregate's
  repository, plus a new `repositories/reconcile.py` for the schema-wide
  table-count snapshot); `backend/jobs/reconcile.py` is now a thin
  delegator. `test_layering.py` gains
  `test_no_job_touches_a_repository_client_or_session`, scanning
  `backend/jobs/*.py` with the router check's AST approach; confirmed
  failing against the pre-fix files (every offending import/query named)
  and passing after.
- [x] **FIX-41** (MEDIUM) `frontend/src/app/page.tsx` reads `jury_size`
  through a new `api.ts` export, `serverGet` (server-side, unauthenticated,
  `cache: "no-store"`), instead of calling `fetch` itself.
  `test_layering.py` gains `test_frontend_calls_fetch_only_from_api_ts`, a
  grep-style scan over every `frontend/src` `.ts`/`.tsx` file; confirmed
  failing against the pre-fix `page.tsx` and passing after.
- [x] **FIX-42** (MEDIUM) `juries_service.jury_review_would_close_on(cycle)`
  computes `jury_review_started_at + jury_review_days` from the cycle's
  settings snapshot; `GET /juries/mine` returns it on every duty, and
  `GET /cycles/{id}` returns it as `jury_review_would_close_on` alongside
  the existing ballot `would_close_on`. `/jury` and `/cycles/[id]` render
  both timers.
- [x] **FIX-43** (MEDIUM) `frontend/src/app/solutions/[id]/PageClient.tsx`
  renders "Jury notes" from `GET /solutions/{id}`'s already-returned
  `jury_notes` block (same shape as fix run 4's FIX-30 — backend done, UI
  half missing). Evidence: rendered HTML from a disposable jsdom harness.
- [x] **FIX-44** (MEDIUM) `<AiInfluence>` now renders in
  `frontend/src/components/Comments.tsx` and in both amendment lists
  (`umbrellas/[id]` and `solutions/[id]` `PageClient.tsx`);
  `solutions_service.detail_view`'s own amendments block was missing
  `ai_influence` entirely and now has it, matching `umbrellas_service`'s.
  Comments.tsx also now shows "edited (revision N)" with an "Earlier
  revisions" disclosure, completing FIX-39's page half.
- [x] **FIX-45** (LOW) `ollama.py::generate` and four `seed.py` seeders now
  call `load_prompt`/`_load_yaml` through `asyncio.to_thread`; `seed_terms`'s
  three inline file reads move into a new sync helper,
  `_read_legal_files`; `_seed_cities`'s pre-existing `.exists()` call (same
  shape, previously uncaught) moves into the sync helper it already thread-
  wraps. `test_no_blocking_file_io_inside_async_def` now also scans
  `backend/clients` and `backend/seed.py`, and gained a second detector for
  a same-file sync helper called directly (not through `asyncio.to_thread`)
  from an `async def`; confirmed failing against the pre-fix files (every
  offending call named) and passing after.
- [x] **FIX-46** (LOW) `similarity_service.decide` no longer lets an
  amendment's author single-handedly settle a flag as "different" —
  DEMOCRACY.md §5.4's author shortcut is "Same" only. Test: one author's
  Different press leaves the flag pending; a second, distinct, non-author
  press reaches `similarity_confirm_min` and dismisses it.
- [x] **FIX-47** (LOW) `IP_HASH_SECRET` added to `settings_env.py` (required,
  no default) and `.env.example`; `security.py::hash_ip` now salts with it
  (SHA-256 of secret + address), so a stored `ip_hash` is no longer
  reversible by enumerating the IPv4 space.
- [x] **FIX-48** (LOW) `export_service.get_export` raises a new `Gone` (410)
  error, code `export_expired`, the moment `expires_at` has passed,
  independently of whether the hourly `expire_exports` sweep has run.
- [x] **FIX-49** (LOW) `_mailto` moves from `routers/summaries.py` into
  `summaries_service` (folded into `by_community_and_number`); the router
  now only returns what the one service call produced.
- [x] **FIX-50** (LOW) `GET /umbrellas/{id}`, `GET /results` and
  `GET /solutions/{id}` each embed only the first page (25) of the lists
  with a dedicated paginated endpoint to fall back on
  (`problem_discussion`, `solutions`, `references`, dominant solutions'
  `amendments` on the umbrella page; `past_cycles` on `/results`;
  `amendments` on the solution page), each with its own `*_next_cursor`.
  `problem_reports`, version history and a solution's own discussion have
  no dedicated list endpoint and are left as they were.
- [x] **FIX-51** I-28's `[~]` now names the style brief's unbuilt
  California photography explicitly as a settled decision (ARCHITECTURE.md
  §9), not only the missing screen-reader/browser runs.
- [x] **FIX-52** Full evidence set re-run (migrations from empty,
  `verify_schema.py`, seed dry-run, full suite — 231 + 2 live — every
  required grep, `npm audit`, frontend `tsc`/`lint`/`build`,
  `reconcile.py --dry-run` after two solution edits and two comment edits,
  `git status`); all clean.

---

## Phase 3 — Demo 2 (revise per CLAUDE.md 'The Two Halves')

Not scheduled. Pulled forward by the director after Demo 1 is used.

- [x] **D2-00** Jury draw seeded from the logged bytes (DEMOCRACY §8.1; audit-6 MEDIUM); test that pool + bytes replay the draw — done by change/01 C1-12
- [x] **D2-09** Director's use notes from Demo 1 folded into the documents (the input to the Demo 2 brief) — done: the eleven notes split into change/01 (this brief), change/02, change/03 (HISTORY.md, Session 2)
- [ ] **D2-10** California photography for page headers — director supplies images; ARCHITECTURE §9 — or the style brief drops it
- [ ] **D2-01** Proposal system (PROJECT.md parking lot) — "propose a new umbrella" in the post form; proposal tables; thresholds; dormancy; similarity grouping
- [ ] **D2-02** Comment moderation (needed before the friends beta)
- [ ] **D2-03** Real quorum decision and implementation
- [ ] **D2-04** Hysteresis on dominant status, if the audit shows flapping
- [ ] **D2-05** AI writing assist on the post form (makes AI influence real)
- [ ] **D2-06** Email notifications for jury duty and ballot open
- [ ] **D2-07** Timers firing for jury review and ballot window (replacing director controls)
- [ ] **D2-08** Deployment for the friends beta; HTTPS; invite gate; final legal text

---

## Change 01 — site shell

Built on `change/01-site-shell` from `briefs/change-01.md`. Awaiting the
director's test, then a change audit before its PR to `main`.

- [x] **C1-01** Browser API base tracks the page's own host, not a literal `127.0.0.1` — fixes the sign-out-on-reload bug
- [x] **C1-02** Sign-in returns you to where you were (`next`, validated); a session that ends mid-page says so
- [x] **C1-03** The name — Direct Democracy CA, everywhere outside historical records
- [x] **C1-04** Navigation and footer — three tabs, Admin, the full transparency footer
- [x] **C1-05** Landing page rewrite — verbatim copy, one Join button, signed-in redirect to `/home`
- [x] **C1-06** `/explained` — Direct Democracy Explained, two diagrams, both explainers
- [x] **C1-07** feed-v1 — search plus newest/oldest/most_votes/most_comments
- [x] **C1-08** The rhythm — `cycle_open_rule`, `next_cycle_dates`
- [x] **C1-09** `GET /cycles/mine`
- [x] **C1-10** `/home` — ballot and jury panels, pinned ballot items, the feed
- [x] **C1-11** "How the ballot works" / "How the jury works" explainers
- [x] **C1-12** Jury draw replayable (closes D2-00)
- [x] **C1-13** Three honest filing messages, and the no-umbrellas case
- [x] **C1-14** Test data: `load_test_data.py`, `ALLOW_TEST_DATA`
- [x] **C1-15** The admin page explains itself
- [x] **C1-16** Evidence — full suite, `verify_schema.py`, seed dry-run, a loaded test dataset against real Ollama, one full cycle through the API, `reconcile.py --dry-run`, the greps, `npm audit`/`build`/`test`, `git status`
- [x] **FX-01** No code path deletes a hashed row — the test-data remover withdrawn; test data cleared by rebuilding the database from empty
- [x] **FX-02** An empty ballot says why it is empty, with that cycle's own settings-snapshot numbers, on `/ballot`, `/cycles/[id]`, and the Home panel
- [x] **FX-03** `AUDIT.md` §6 names change reports (`audits/change-NN-audit-K.md`)
- [x] **FX-04** Fix-run-1 evidence — full suite, `verify_schema.py`, seed dry-run, `load_test_data.py --apply`, a zero-item and a non-empty cycle, `reconcile.py --dry-run`, `npm run build`/`test`, `git status`
- [x] **FX-05** [HIGH, audit run 1] `safeNextPath` resolves `next` through the browser's own URL parser instead of matching strings — closes the `/\evil.example` backslash open-redirect bypass; `ARCHITECTURE.md` §9 restated to match
- [x] **FX-06** [MEDIUM, audit run 1] The old name in `frontend/package.json`, `package-lock.json`, and the data-export filename (`backend/routers/me.py`) — spellings the audit's own space-separated proof grep missed. `CLAUDE.md`/`PROJECT.md` still cite the historical filename `DirectDemocracyCali_ProjectSummary_v2.md` in the document map's not-yet-absorbed list; left untouched (not a live branding string; both documents are outside this brief's authorization)
- [x] **FX-07** [MEDIUM, audit run 1] `/explained` no longer claims AI "summarizes discussion" — no such feature exists or is planned; every AI-capability sentence on `/explained`, the landing page, and `explainers.tsx` traced to `DEMOCRACY.md` §9
- [x] **FX-08** [audit ambiguity 1] The ballot rhythm's words come from `CYCLE_RULE_WORDS` in `frontend/src/content/explainers.tsx`, keyed by the live `cycle_open_rule` setting, everywhere it's said (`explainers.tsx`, `/explained` "Two clocks" and Diagram 2) — an unknown rule links to Settings instead of a stale sentence; `backend/tests/test_layering.py` asserts every `rules.py::CYCLE_OPEN_RULES` key has an entry
- [x] **FX-09** [audit ambiguity 2] `DEMOCRACY.md` §4.1 records the Home-card decision (one short line per filing state present; the full per-community sentence is the post page's) — document only, no code change
- [x] **FX-10** Fix-run-2 evidence — full suite (257/2), `npm test` (15/15), `npm run build` (25 routes), `verify_schema.py` (no drift), both proof greps, `git diff --stat`

---

## Change 02 — who you are and where you post

Built on `change/02-who-and-where` from `briefs/change-02.md`. Awaiting the
director's test, then a change audit before its PR to `main`. Closes
Director Decision #9.

- [x] **C2-01** Schema: `users.city_id` nullable (appended Foundation
  migration `b3f270601b35`, never editing `25035d5b7ff5`); `user_home_changes`,
  `email_change_requests` (Foundation); `label_previews`, `posts.category_choice`
  gains `preview` (regenerated Iteration migration); `home_change_cooldown_days`
  and `label_preview_max_per_hour` seeded. Proof: upgrade from empty and from
  the old Foundation head with a user in it; `verify_schema.py`; downgrade
- [x] **C2-02** One source for "your communities":
  `backend/services/communities.py::home_communities` (module renamed from
  `community.py`); every membership check funnels through it or `is_member`/
  `require_member`; active-user counts and the jury pool use the same
  nullable-`city_id`-safe SQL clause. Proof: `git grep -n 'city_id'` walked and
  explained; `test_communities.py` walks an unincorporated user through
  post → vote → comment → ballot in county and state, refused in any city
- [x] **C2-03** Signup: county first, then that county's cities with
  "Unincorporated — no city" first; backend accepts `city_id: null`
- [x] **C2-04** Profile and email: `PATCH /me/profile`, `POST /me/email`,
  `POST /auth/confirm-email-change`; a rename shows on an existing post and
  changes no hash; anonymization deletes both new tables' rows; export
  includes them
- [x] **C2-05** Changing home: `account_service.change_home` (DEMOCRACY §2.3
  rules 1–3), `GET/POST /me/home`; ballot eligibility (§10.3) in
  `ballots.py::_eligible`, one-sentence refusal
- [x] **C2-06** The account page (`/me`): profile, email change, home change
  with the §2.3 warning and next-allowed date, display settings, export,
  delete
- [x] **C2-07** Labeler prompt states "none" is a correct answer, not a
  fallback (version 4 → 5)
- [x] **C2-08** Suggestion on a draft: `POST /posts/label-preview`,
  `POST /posts` `category_choice=preview`; `label_previews` → `ai_actions` →
  model call, survives a failed call; rate limited from settings; refuses
  another user's, a consumed, or a stale preview
- [x] **C2-09** `/posts/new` rebuilt as a four-step form: problem, solutions,
  communities (nothing pre-selected, Federal disabled), "Where it goes" (the
  suggestion runs on reaching the step; Keep/Change/None of these fit;
  Choose myself; Post now file later when the AI is unreachable);
  preview-born labels on `/ai/actions` and the post page
- [x] **C2-10** Test data: `test_dataset.yaml`'s two unincorporated residents
  and two posts load cleanly; `load_test_data.py` handles `city: ~`
- [x] **C2-11** Housekeeping: (a) the environment-leakage test clears
  `os.environ`; (b) `next.config.ts` disables `agentRules`, both files
  gitignored; (c) `.env.example` `BUILD_LABEL=change-02`; (d) the
  `/tmp/uvicorn.log` debt entry now names `load_test_data.py` too
- [x] **C2-12** Labeler comparison (evidence only, HISTORY.md): `llama3.2`
  vs `llama3.1:8b` on the same 11 `file_under: ai` test posts
- [x] **C2-13** Evidence: full suite (287 passed, 2 deselected) and `npm test`
  (15/15) in a clean shell; `verify_schema.py` clean; seed `--dry-run` zero
  pending; test data loaded with both models; `walkthrough_change02.py`
  end to end through the API; `reconcile.py --dry-run` clean; hash
  round-trip; `npm run build` (25 routes); `npm audit --audit-level=high`
  (0); `pip-audit` (0 in project dependencies; 12 against the sandbox's own
  `pip` tooling, unrelated to this repo); `git status` clean

### change/02 fix run 1 (`briefs/change-02-fix-1.md`)

- [x] **FX-01** Step 4 as the director redesigned it: no Keep control
  (posting untouched is keeping); per community the suggestion under its own
  umbrella's main category, two buttons (Choose myself, None of these fit),
  the current choice always in words, "Use the AI's suggestion" to undo;
  the page-level "Choose myself instead" removed; Post enabled as soon as a
  suggestion arrives; the two fallbacks only on 503/429, never 403. The
  decision-to-payload mapping is a pure module (`frontend/src/lib/postPreview.ts`)
  with `npm test` cases. `POST /posts`'s contract is unchanged
- [x] **FX-02** An unverified author is told at step 1 of `/posts/new`, with
  "Send me a new link", and Continue is disabled; the same
  `UnverifiedEmailNotice` component backs the site banner
- [x] **FX-03** `POST /me/resend-verification`: voids older unused tokens,
  issues a new one, `VERIFY_RESEND_MINUTES` rate limit (429), 409 when
  already verified; `services/auth.py`'s stale "ask for a new one from the
  sign-in page" message now names the control that exists
- [x] **FX-04** Demo mail: `demo_link` on signup, resend-verification and
  email-change **only** when `EMAIL_BACKEND=console` and
  `ALLOW_TEST_DATA=true`; absent in the other three combinations for all
  three endpoints; never in a log record but the console email (caplog)
- [x] **FX-05** `GET /posts/mine` and the "Your posts" section on `/me`,
  between "Your communities" and "Your profile"
- [x] **FX-06** The labeling model is `llama3.1:8b` (director's decision on
  the C2-12 evidence); no test or script names a model literal
- [x] **FX-07** Evidence: clean-shell full suite (303 passed, 2 deselected),
  `npm test` (22/22), `npm run build` (25 routes), `verify_schema.py` NO
  DRIFT (no schema change was needed), `walkthrough_change02.py` end to end
  against real Ollama on the new model (exit 0, hash round-trip `match:
  true`), `reconcile.py --dry-run` clean, `git status` clean

---

## Change 03 — propose a new umbrella

Not started. A design session first; the parked Proposal system design in
PROJECT.md is the starting point.

- [ ] Design session: thresholds, dormancy, similarity grouping, what happens to posts under a rejected umbrella
- [ ] "Propose a new umbrella" option in the post form
- [ ] Proposal tables and migration
- [ ] AI similarity check against pending proposals; human-confirmed merges
- [ ] The labeler starts routing to an approved umbrella

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
| 10 | When to declare the keeper and freeze the Iteration schema | not yet | AUDIT.md §7 |

Resolved 2026-09-13 (see HISTORY): #6 keep home city/county — now CLAUDE §6.
Resolved 2026-09-19 (see HISTORY, Session 2): #9 — "Unincorporated — no
city" at signup; county and state communities only; built in change/02
(2026-09-21), awaiting the director's test and a change audit before merge.

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
- **Home preferences (`ddca.home.showBallot`) live in the browser, not the account.** A user who switches devices or clears site data loses the setting; there is no server-side record of it. Bites if a future change assumes a signed-in user's Home preferences follow them anywhere.

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
- **`backend/scripts/walkthrough_extended.py` and `load_test_data.py` read
  verification tokens from `/tmp/uvicorn.log`**, a fixed path (a
  `--log-path` default on `load_test_data.py`), on the assumption the
  server's stdout/stderr is redirected there. Bites if the server is ever
  run with logging configured differently — the script will time out
  looking for a token that was written somewhere else.
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

*Last updated: 2026-09-19 — Demo 1 cleared and merged; documents final for Demo 1.*
