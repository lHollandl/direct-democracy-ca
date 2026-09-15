# ARCHITECTURE.md — System Shape

> How the system is put together: layers, boundaries, endpoints,
> background work, and the external services it talks to. This
> document describes the **target** shape that every demo is built
> toward. Where the current code differs, the code is wrong.
>
> Changes to design philosophy require director approval.

---

## 1. Overview

```
 ┌──────────────────────────────────────────────────────────────┐
 │  Browser — Next.js (TypeScript, Tailwind)        /frontend    │
 └────────────────────────────┬─────────────────────────────────┘
                              │ HTTPS/JSON, JWT bearer
 ┌────────────────────────────▼─────────────────────────────────┐
 │  FastAPI                                          /backend    │
 │  routers/  ──▶  services/  ──▶  repositories/  ──▶ Postgres   │
 │                    │                                          │
 │                    ├──▶ clients/ollama      (host GPU, HTTP)  │
 │                    ├──▶ clients/search      (web search API)  │
 │                    ├──▶ clients/email       (SMTP / console)  │
 │                    └──▶ Redis  (rate limits, token blacklist) │
 │  jobs/  (background: labeling, retries, nightly reconcile)    │
 └──────────────────────────────────────────────────────────────┘
        ai/prompts/*.md   backend/config/*.yaml   .env
```

One repository, one database, two halves (CLAUDE.md). Foundation and
Iteration share this architecture; they differ only in which tables and
routers they own (DATABASE.md §2; §6 below).

---

## 2. Layers and Boundaries

| Layer | Directory | May call | Must not |
|---|---|---|---|
| **Routers** | `backend/routers/` | services | repositories, clients, the database, each other |
| **Services** | `backend/services/` | repositories, clients, other services | routers, raw SQL |
| **Repositories** | `backend/repositories/` | the database (async session) | services, clients, anything else |
| **Clients** | `backend/clients/` | external processes over HTTP | the database |
| **Jobs** | `backend/jobs/` | services | routers, repositories directly |
| **Config** | `backend/config/` | `.env`, YAML | anything |

Rules:

- A router parses the request into a Pydantic model, calls **one** service
  function, and shapes the response. No logic. This holds for reads too:
  every read the frontend needs has a service function, even a one-line
  pass-through to a repository. A router never imports a repository
  module, a client, or the session.
- A service owns a transaction. Every multi-table write happens in one
  service function inside one session (Law 5).
- A repository is the only place that touches a table. One module per
  aggregate: `users.py`, `solutions.py` (with versions and amendments),
  `cycles.py` (with ballot items, votes, juries), etc. A service never
  calls `session.execute`, `session.get`, or `select(...)` itself; it
  calls a repository function. `backend/tests/test_layering.py` enforces
  both rules by scanning the source (audit finding, demo-01 run 1).
- Ranking and threshold code lives in `backend/services/rules.py`, with
  its plain-English explanation as the module docstring and a
  `RULES_VERSION` constant printed in every summary (Law 9).
- Nothing reads `os.environ` except `backend/config/settings_env.py`
  (Law 10). Runtime settings (DEMOCRACY §7.4) come from the `settings`
  table via `backend/services/settings.py`, cached for 60 seconds.
- `main.py` registers routers and lifespan hooks. Nothing else.
- Background jobs are scheduled by the **service that owns the
  transaction**, inside the same function, through
  `backend/jobs/runner.py::spawn_after_commit` (§7). A router never
  schedules a job.
- Foundation services never import an Iteration repository. Where
  Foundation needs Iteration data (the data export, DATABASE §3.11),
  Iteration registers a contributor at startup and Foundation calls it
  through the registry (`backend/services/export.py::register_contributor`).

The current code (`routers/posts.py` etc.) hits the ORM directly from
routers and imports `ai.labeler` via a `sys.path` hack. Both are
replaced: repositories for data, `backend/clients/ollama.py` for
inference, `ai/` holds prompt files and evaluation scripts only.

---

## 3. Configuration

One `.env` at the repository root (never committed; `.env.example` is),
read by `settings_env.py` into a single `Settings` object and passed to
Docker Compose with `--env-file`. There is no separate `infra/.env` or
`backend/.env`; the legacy pair is retired in Demo 1.

| Key | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://…` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | read by Docker Compose; must match the credentials inside `DATABASE_URL` |
| `REDIS_URL` | |
| `JWT_SECRET`, `ACCESS_TOKEN_MINUTES` (30), `REFRESH_TOKEN_DAYS` (14) | |
| `EMAIL_VERIFY_HOURS` (24), `PASSWORD_RESET_MINUTES` (30), `EXPORT_FILE_HOURS` (48) | |
| `EMAIL_BACKEND` (`console` / `smtp`), `SMTP_*`, `EMAIL_FROM` | `console` prints emails to the log — Demo 1 default |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `EMBED_MODEL`, `OLLAMA_TIMEOUT_SECONDS` | host GPU |
| `SEARCH_PROVIDER`, `SEARCH_API_KEY`, `SEARCH_BASE_URL` | reference recommendation |
| `OFFICIALS_TEST_EMAIL` | Demo 1 directory address |
| `BUILD_LABEL` | `demo-01`; stamped on `ai_actions` |
| `CORS_ORIGINS` | |
| `PUBLIC_BASE_URL` | the address the frontend is reached at (Demo 1: `http://localhost:3000`); used wherever a link must work outside the site — the `mailto:` body, the PDF footer, the summary's verify text |
| `RATE_LIMIT_WRITE_PER_MINUTE` (30) | |
| `LOG_LEVEL` | |

Startup validates every key and refuses to start on a missing one, with
the key name in the error.

---

## 4. Authentication and Authorization

- Signup checks age against `min_signup_age` (settings) and refuses
  under-age applicants with 422 `too_young` storing nothing; otherwise
  creates the user, a `terms_acceptances` row, and an email
  verification token; sends the verification email; returns 201 with
  no tokens. The account can log in but every write endpoint returns
  403 `email_not_verified` until the link is used — **except the three
  that act only on the caller's own account**: `PATCH /me/display`,
  `POST /me/export`, `DELETE /me`. A person's rights over their own data
  (CLAUDE §6) never depend on our verification email having worked.
- Login returns a 30-minute access JWT (`sub`, `exp`, `iat`, `jti`) and
  an opaque refresh token (random 32 bytes, base64url), stored hashed.
- The refresh token travels only in an `httpOnly`, `SameSite=Strict`
  cookie set by the backend on login and refresh; `POST /auth/refresh`
  reads it from the cookie, never the body. It rotates: the old refresh
  token is marked `replaced_by`; presenting a replaced token revokes
  its whole chain. CORS therefore allows credentials for
  `CORS_ORIGINS` only.
- `POST /auth/logout` revokes the refresh token and puts the access
  token's `jti` in Redis with TTL = remaining lifetime; the auth
  dependency rejects blacklisted `jti`s.
- Dependencies: `current_user` (valid JWT, not deleted),
  `verified_user` (+ `email_verified_at`), `admin_user` (+ `is_admin`),
  `community_member(level, entity_id)` (user's home community matches).
- Passwords: bcrypt, cost 12, policy per Law 13; maximum 72 bytes (bcrypt's
  limit), refused with a plain message rather than silently truncated.
- **Administrators are made only from the machine:**
  `backend/scripts/grant_admin.py <email> (--dry-run | --apply) [--revoke]`. There is no
  endpoint and no UI. The grant writes an `admin_actions` row like any
  other administrator action (DEMOCRACY §13).
- Every authenticated request updates `users.last_active_at` at most
  once per minute (Redis debounce) — the active-user source.

---

## 5. Rate Limiting and Errors

- Every `POST`/`PUT`/`PATCH`/`DELETE` passes through a Redis
  token-bucket keyed by user id (or IP when unauthenticated), limit
  `RATE_LIMIT_WRITE_PER_MINUTE`. 429 with `Retry-After`.
- Errors: services raise typed exceptions (`NotFound`, `Forbidden`,
  `Conflict`, `ValidationFailed`, `ExternalServiceDown`); one exception
  handler maps them to status codes and a body `{error: <code>, message:
  <plain English>}`. Anything else is logged with a request id and
  returned as 500 `{error: "internal", request_id}`. No stack traces
  to the client (Law 12).

---

## 6. Endpoints

`F` = Foundation, `I` = Iteration. All JSON. All list endpoints paginate
with `?cursor=&limit=` (default 25, max 100; a `limit` above 100 is
refused with 422, never silently capped) **except** five fixed-size
reference lists, which return whole: `GET /geo/counties`, `GET
/geo/counties/{id}/cities`, `GET /communities/{level}/{id}/officials`,
`GET /settings`, and the main-category list inside `GET /feed`'s filter
metadata. No other exemptions.

### Service and legal (F, public)
`GET /health` (liveness; no database access), `GET /legal/privacy`,
`GET /legal/terms`, `GET /legal/cookies` (current markdown), `GET
/legal/current-version`.

### Auth and account (F)
| | |
|---|---|
| `POST /auth/signup` | body per DATABASE §3.1; returns user id |
| `POST /auth/verify-email` | token |
| `POST /auth/login`, `/auth/refresh`, `/auth/logout` | |
| `POST /auth/forgot-password`, `/auth/reset-password` | |
| `GET /auth/me` | user, display settings, home communities with names, verification level — the one read; `/me/*` below are the writes |
| `PATCH /me/display` | `public_name_mode` |
| `POST /me/export` → `GET /me/export/{id}` | async export |
| `DELETE /me` | password confirm; runs anonymization |

### Geography and officials (F)
`GET /geo/counties`, `GET /geo/counties/{id}/cities`,
`GET /communities/{level}/{id}` (name, active user count with definition,
officials list), `GET /communities/{level}/{id}/officials`.

### Settings and logs (F, public read)
`GET /settings` (current values with definitions and effective_from),
`GET /settings/history?key=`, `GET /admin/log`, `GET /ai/actions?subject_type=&subject_id=`.

### Posts and labels (I)
| | |
|---|---|
| `POST /posts` | problem, solutions[] (≥1), communities[], category_choice, optional umbrella per community; writes `posts` + `post_solutions` + `post_communities` in one transaction; workshop solutions are created when each community gets its umbrella (DATABASE §4.7) |
| `GET /posts/{id}` | includes each community's label status and, once filed, links to the created solutions |
| *(no `PATCH`/`DELETE /posts`)* | posts are immutable in Demo 1 (DEMOCRACY §4.1) |
| `GET /feed?community=&category=&cursor=` | newest first; response includes `ranking: "feed-v0", explanation` |
| `POST /posts/{id}/label/confirm`, `.../label/correct` | author only |

### Umbrellas (I)
`GET /umbrellas?community=`, `GET /umbrellas/{id}` (the whole page data:
DEMOCRACY §3.3 sections, including the AI action list),
`GET /umbrellas/{id}/solutions`, `GET /umbrellas/{id}/comments`,
`GET /umbrellas/{id}/references`.

### Solutions, amendments, comments, votes (I)
| | |
|---|---|
| `POST /umbrellas/{id}/solutions` | member |
| `GET /solutions/{id}` (with versions), `PATCH /solutions/{id}` (author, only while unvoted/unamended) | |
| `POST /solutions/{id}/amendments`, `GET /solutions/{id}/amendments` | dominant only |
| `POST /amendments/{id}/withdraw` | author |
| `POST /similarity/{id}/decide` | `same` / `different` |
| `POST /comments` (target_type, target_id, parent_id), `PATCH /comments/{id}`, `DELETE /comments/{id}` | |
| `PUT /votes` (target_type, target_id, direction) / `DELETE /votes` | member; returns new net_score and any status change |
| `POST /umbrellas/{id}/references`, `PUT /references/{id}/feedback` | URL keeps "references"; the table is `umbrella_references` |

### Cycles, ballot, jury (I)
| | |
|---|---|
| `GET /communities/{level}/{id}/cycles`, `GET /cycles/{id}` | |
| `GET /cycles/{id}/ballot` | items in `position` order with frozen text; the caller's own votes if any (the one place a vote row is shown, and only to its voter — DATABASE §4.16) |
| `PUT /cycles/{id}/ballot/{item_id}/vote` | `yes`/`no`; member; state `open` only |
| `GET /juries/mine` | current juror duties |
| `POST /jurors/{id}/accept`, `/decline` | |
| `POST /ballot-items/{id}/holdback` | juror; category + text |

### Summaries (I, public)
`GET /summaries/{level}/{id}/{number}` (page data), `.../{number}/json`,
`.../{number}/pdf`, `.../{number}/verify`, `GET /summaries/hashes`,
`GET /results` (logged-in: the user's three communities).

### Admin (F for settings; I for cycle controls)
`POST /admin/settings` (key, value, reason), `POST /admin/cycles/prepare`,
`/admin/cycles/{id}/redraw-jury`, `/open`, `/close`, `/publish`,
`POST /admin/umbrellas/{id}/recommend-references`,
`POST /admin/posts/{id}/relabel`, `GET /admin/users/{id}` (verification,
jury history; never ballot votes).

---

## 7. Background Work

`backend/jobs/` — asyncio tasks; no Celery. A job triggered by a request
is started by `runner.py::spawn_after_commit(session, factory)`, called
from the service that owns the transaction: the task is created only
after that session commits, and the runner holds a strong reference so
the task outlives the request and is never cancelled by a client
disconnect (demo-01 bug: FastAPI `BackgroundTasks` died with the
connection). Periodic jobs are started in the lifespan.

| Job | Trigger | Does |
|---|---|---|
| `label_post` | after `POST /posts` commits | calls Ollama; writes `ai_actions` then `labels` then `post_communities.umbrella_id`; sets `label_status` |
| `label_retry` | every `label_retry_minutes` | re-queues `unlabeled` posts, and `pending` posts older than the retry window whose job never started |
| `similarity_check` | after amendment create | embeds, compares, writes `amendment_similarity` |
| `recommend_references` | admin trigger (`POST /admin/umbrellas/{id}/recommend-references`) — the endpoint returns 202 `pending` at once; the Ollama and search calls run in this job | DEMOCRACY §9.4 |
| `build_export` | after `POST /me/export` commits | assembles the export file; DATABASE §3.11 |
| `reconcile` | 03:00 daily and on demand | DATABASE §7 |
| `evaluate_dominance` | inside `reconcile`, and after every solution vote | DEMOCRACY §7.1 |
| `expire_exports` | hourly | delete export files past `expires_at` (files only; rows stay) |

Each job logs start, end, counts, and failures with a job id; a failure
never crashes the app and never swallows the exception (Law 12).

---

## 8. External Services

### 8.1 Ollama — `backend/clients/ollama.py`
Async httpx client. `generate(prompt_file, variables) -> str` renders a
prompt file from `ai/prompts/` with the variables, calls
`/api/generate` with `OLLAMA_MODEL`, returns text; `embed(text) ->
list[float]` calls `/api/embeddings` with `EMBED_MODEL`. Every call
records the prompt file and its hash so the `ai_actions` row can cite
them. Timeouts raise `ExternalServiceDown`; the caller decides (labeling
→ `unlabeled` and retry; similarity → skip and log).

Prompt files: `ai/prompts/labeler.md`, `reference_queries.md`,
`reference_select.md`. Each has a header block stating its inputs, its
required output JSON shape in prose **and** as a JSON Schema, and its
version. The client passes the schema to Ollama's `format` parameter so
the model's output is constrained to the shape; the prose remains the
contract (Law 7). Generation runs at temperature 0 so the same input
files the same way twice. Embedding calls have no prompt file (§9.3 of
DEMOCRACY; DATABASE §3.10 says how their `ai_actions` rows record that). Output is parsed strictly;
malformed output is logged as an `ai_actions` row with
`output.error` and treated as failure.

### 8.2 Web search — `backend/clients/search.py`
One interface, `search(query) -> list[Result{title, url, snippet}]`,
with one implementation per `SEARCH_PROVIDER`. The raw provider
response is stored on the `ai_actions` row. Provider choice is
configuration; the first implementation is whichever the director
selects when the key is obtained. If `SEARCH_API_KEY` is unset, the
admin trigger returns 503 `search_not_configured` and nothing else
breaks.

### 8.3 Email — `backend/clients/email.py`
`send(to, subject, text_body)`. Backends: `console` (logs the message —
Demo 1) and `smtp`. Only Foundation sends email: verification and
password reset. Iteration sends none (DEMOCRACY §11.5).

### 8.4 Redis
Rate-limit buckets, access-token blacklist, `last_active_at` debounce,
settings cache. Loss of Redis degrades: rate limiting falls open with a
logged warning, blacklist check fails closed (401), the app stays up.

---

## 9. Frontend

Next.js App Router, TypeScript, Tailwind. `frontend/src/app/` routes:

| Route | Page |
|---|---|
| `/signup`, `/login`, `/verify-email`, `/forgot-password`, `/reset-password` | Foundation |
| `/me` (display settings, export, delete), `/legal/privacy`, `/legal/terms`, `/legal/cookies` | Foundation |
| `/settings` (public), `/ai/actions` (public), `/admin/log` (public), `/admin` (settings change only) | Foundation — the transparency pages ship with the tables they display; the cycle controls on `/admin` are Iteration |
| `/feed` | feed-v0 with community and category filters |
| `/posts/new` | DEMOCRACY §4.1; three sections: problem, solutions, communities; category: AI or pick |
| `/umbrellas/[id]` | the umbrella page, DEMOCRACY §3.3 |
| `/solutions/[id]` | full solution with versions, amendments, discussion |
| `/ballot` | current cycle for each home community |
| `/jury` | duties |
| `/results`, `/summaries/[level]/[id]/[number]`, `/summaries/hashes` | the summary document; the public hash list (DEMOCRACY §11.3) |
| `/`, `/posts/[id]`, `/cycles/[id]` | landing page; a post with its label status and created solutions; a cycle with its state, items, and every jury draw |
| `/admin` (cycle controls: prepare, redraw, open, close, publish, recommend references, relabel) | Iteration — added to the Foundation page |

`frontend/src/lib/api.ts` is the only place `fetch` is called; it holds
the access token in memory and the refresh token in an `httpOnly`
cookie set by the backend, and silently refreshes on 401.

**Style brief** (director, 2026-09-06): mobile-first; plain language;
one accent color; California photography in page headers; every page
works with images disabled; accessible per CLAUDE §8. Iterate on the
UI freely between demos.

---

## 10. Testing

`backend/tests/` with pytest-asyncio against a throwaway Postgres
**database** on whatever server `DATABASE_URL` points at, created and
dropped by the test session and built from both migration chains, never
`create_all`. Required coverage:

- Every service function in `rules.py` with table-driven cases,
  including the `threshold()` formula at boundaries (0, 1, exact,
  rounding).
- The full cycle as one integration test: seed → post → label (Ollama
  mocked) → votes → dominant → prepare → jury holds one back → open →
  vote → close → publish → hash verifies → JSON re-hashes to the same
  value.
- Anonymization: after `DELETE /me`, every PII column is erased and
  every civic row still resolves.
- Auth: refresh rotation and reuse detection; blacklist on logout.
- Every endpoint: 401/403 paths.
- Layering (`test_layering.py`): no router imports a repository, client,
  job, or session; no service calls the session or `select` directly;
  and no endpoint function calls more than one service module beyond a
  `require_*` resolver, or contains arithmetic on a setting (§2).
- `npm audit --audit-level=high` in `frontend/` returns no findings;
  it is part of every run's evidence set.

Ollama and search are mocked in tests via the client interfaces; one
opt-in test (`-m live`) hits the real Ollama to validate prompt-file
output shapes.

---

## 11. The Sandbox Boundary

Everything above runs inside a Docker Sandbox microVM (SANDBOX.md).
From the app's point of view: Postgres and Redis are containers inside
the VM; Ollama is reached at the host address the sandbox exposes;
`api.anthropic.com` and package registries are reachable; nothing else
is. `OLLAMA_BASE_URL` in the sandbox's `.env` points at the host.

---

## 12. Known Debt Carried From the Current Code

Recorded so the first build replaces them deliberately:

- Sync SQLAlchemy sessions inside `async def` — replaced by async
  engine (Law 11).
- `ai/labeler.py` module-level constants and inline prompt string —
  replaced by client + prompt file (Laws 7, 10).
- `sys.path` import hack in `routers/posts.py` — gone with the layer
  split; `backend` is a package with `pyproject.toml` at the repo root.
- `@app.on_event("startup")` and `create_all` — replaced by lifespan and
  migrations.
- `solutions.title` and `upvote_count` — superseded by versions and
  `net_score`; not carried into the Iteration schema (fresh per demo).
- `Solution.governance_levels` array — superseded by the umbrella's
  community.
