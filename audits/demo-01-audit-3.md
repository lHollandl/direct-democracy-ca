# Audit — demo-01, run 3, 2026-09-15

## Summary

**CRITICAL: 0 · HIGH: 1 · MEDIUM: 3 · LOW: 2 · NOTE: 0.** **Verdict: FIX REQUIRED**
(a HIGH is open), but this is a strong fix run on top of an already-strong
build. Both traps AUDIT.md §4.1 marks always-`CRITICAL` are clean, confirmed
by running the platform rather than reading it: `GET /cycles/{id}/ballot`
never returned anyone's vote but the caller's own, no endpoint emitted a
`voter_id`, and every vote counted as exactly one regardless of verification
level or admin status.

Fix run 2's own claims hold up under independent re-verification. I built my
own database from empty, ran the full suite (211 + 2 live), `verify_schema.py`
(no drift), the seed dry-run (0 pending), and my own six-account cycle through
`httpx` — signup through a published, hash-verified summary — deliberately
exercising exactly the three items fix run 2 was written to fix:

- **FIX-08 (deep replies).** I built a real depth-cap chain, watched the
  rendered "replying to @…" text change from a real name to "Anonymous
  Community Member" to "Former Community Member" across three identity
  states, and confirmed at the database row level that `comments.text` and
  `content_hash` never changed. **Genuinely fixed.**
- **FIX-09 (jury redraw).** I redrew a jury mid-`jury_review` and confirmed
  `GET /cycles/{id}` lists both draws, the superseded one's jurors marked
  `replaced`, pool and random bytes intact. **Genuinely fixed.**
- **FIX-10 (minority hold-backs published).** In the same cycle, one juror
  held a solution back alone (no majority) and two held another back
  together (majority); the published summary printed the minority reason
  under "Juror concerns" on the item that still passed, and the majority
  reason under "Held back" on the item that didn't. **Genuinely fixed.**

The hash round-trip verified two ways — the platform's own `/verify`
endpoint, and my own from-scratch SHA-256 over the downloaded JSON — and
both matched the stored hash. Three hand-derived `threshold()` cases,
including the denominator-zero edge case, matched the imported function
exactly. Anonymization, checked directly against the database after a real
`DELETE /me`, erased exactly the columns DATABASE §3.1 lists and nothing
else, including on a user who had just authored a comment inside the deep
reply I was testing.

Five agents independently reviewed AI accountability, security controls,
DATABASE.md conformance, DEMOCRACY.md rule implementations, and
ARCHITECTURE.md endpoints/layering/jobs against the code; I verified every
finding they returned by reading the cited code myself before including it
here. That process is where this run's open findings came from — a
previously-fixed category of problem (pagination, and the "one service
function" rule) each turned out to still have unaddressed instances the
brief's own acceptance checks didn't catch.

---

## Findings

### [HIGH] Seven list endpoints have no pagination support at all, not merely a wrong default

- Where: `backend/routers/umbrellas.py::umbrella_solutions` (`GET
  /umbrellas/{id}/solutions`), `::umbrella_comments` (`GET
  /umbrellas/{id}/comments`), `::umbrella_references` (`GET
  /umbrellas/{id}/references`); `backend/routers/transparency.py::settings_history`
  (`GET /settings/history`); `backend/routers/ballots.py::community_cycles`
  (`GET /communities/{level}/{entity_id}/cycles`);
  `backend/routers/amendments.py::list_amendments` (`GET
  /solutions/{id}/amendments`); `backend/routers/summaries.py::hash_list`
  (`GET /summaries/hashes`)
- Document: ARCHITECTURE.md §6 — "All list endpoints paginate with
  `?cursor=&limit=` (default 25, max 100; a `limit` above 100 is refused with
  422, never silently capped) **except** five fixed-size reference lists...
  No other exemptions."
- What the document requires: every one of these seven either paginates or
  is on the five-item exemption list (`GET /geo/counties`, `GET
  /geo/counties/{id}/cities`, `GET /communities/{level}/{id}/officials`,
  `GET /settings`, and the feed's category-filter metadata). None of these
  seven is on that list.
- What the code does: none of the seven functions accept `cursor` or `limit`
  parameters at all — confirmed by reading each router function's signature
  directly:

  ```python
  # backend/routers/umbrellas.py
  @router.get("/{umbrella_id}/solutions")
  async def umbrella_solutions(umbrella_id: int, session: SessionDep, viewer: OptionalUser) -> dict:
      ...
  ```

  Compare with the umbrella list endpoint one function above it in the same
  file, which does the pagination correctly (`cursor: CursorParam = None,
  limit: LimitParam = DEFAULT_LIMIT`) — the mechanism exists and is used
  elsewhere in the same file, just not wired into these seven.
- Evidence:

  ```
  $ grep -n "@router.get" backend/routers/transparency.py backend/routers/ballots.py \
        backend/routers/summaries.py backend/routers/amendments.py
  backend/routers/ballots.py:15:@router.get("/communities/{level}/{entity_id}/cycles")
  backend/routers/transparency.py:65:@router.get("/settings/history", response_model=list[SettingHistoryOut])
  backend/routers/summaries.py:16:@router.get("/summaries/hashes")
  backend/routers/amendments.py:51:@router.get("/solutions/{solution_id}/amendments")
  ```

  None of the four handler signatures above declares `cursor`/`limit`
  (read directly from source). Fix run 2's own FIX-13 fixed exactly one
  previously-flagged unpaginated endpoint (`GET /umbrellas`) and correctly
  matched the newly-worded five-item exemption list for the other four
  audit run 2 had named — but audit run 2 never looked past those five, so
  this second set went unreported and unfixed.
- Why HIGH: this is the same documented rule (ARCHITECTURE §6, "no other
  exemptions") the platform has already treated as worth a dedicated fix
  once this trial. `GET /umbrellas/{id}/comments` and `GET
  /summaries/hashes` are two of the endpoints most likely to grow without
  bound in ordinary use — every published cycle for every community adds a
  row to the second forever, and FIX-13's own stated reasoning for fixing
  `/umbrellas` ("grows without bound once the proposal system lands")
  applies at least as directly to umbrella comment threads.
- Suggested fix: wire `CursorParam`/`LimitParam` into all seven the same way
  `list_umbrellas` already does, and add a test that walks every
  `@router.get` returning a JSON array/list field and asserts it either
  takes `cursor`/`limit` or is in the exemption list, so a future endpoint
  cannot silently join this set again.

---

### [MEDIUM] `recommend_references` runs synchronously inside the admin request, though ARCHITECTURE §7 lists it as a background job

- Where: `backend/routers/admin.py::recommend_references`,
  `backend/services/references.py::recommend_as_admin` / `::recommend`
- Document: ARCHITECTURE.md §7 — the job table lists `recommend_references
  | admin trigger | DEMOCRACY §9.4` alongside six other rows, all of which
  are scheduled via `runner.py::spawn_after_commit` from the service that
  owns the transaction.
- What the document requires: an admin's `POST
  /admin/umbrellas/{id}/recommend-references` should return quickly and let
  the Ollama + web-search work happen after the request's transaction
  commits, the same pattern every other row in the table uses.
- What the code does: `recommend_as_admin` calls `recommend(session,
  umbrella=umbrella)` directly and awaits it inline, inside the same
  request/transaction — no `spawn_after_commit` call exists anywhere in
  `references.py` or `admin.py`. `recommend()` itself calls
  `client.generate(...)` (Ollama) and the search client synchronously in
  that same session. This is the identical "runs in the background so a
  slow external call doesn't hold a request open" rationale
  `services/export.py::build_export`'s own docstring states for exports —
  just not applied here.
- Evidence:

  ```
  $ grep -n "spawn_after_commit" backend/services/*.py
  backend/services/amendments.py:108:    runner.spawn_after_commit(session, ...)   # similarity_check
  backend/services/export.py:69:        runner.spawn_after_commit(session, ...)    # export build
  backend/services/posts.py:164:        runner.spawn_after_commit(session, ...)    # label_post
  ```

  `references.py` and `admin.py` do not appear in that list at all.
- Why MEDIUM, not HIGH: currently unreachable in Demo 1 — `search.require_configured()`
  raises `ExternalServiceDown`/503 before any Ollama or search call happens,
  since no `SEARCH_API_KEY` is set (Director Decision #7, still open). No
  citizen-facing behavior differs today; the moment a search provider is
  configured, an admin's click will block on two live external calls inside
  an open DB transaction, which is the exact failure mode the job-table
  architecture exists to avoid elsewhere.
- Suggested fix: move the Ollama/search work into a `runner.spawn_after_commit`
  callback scheduled from `recommend_as_admin`, matching every other row in
  the §7 table; have the endpoint return an accepted/pending response the
  umbrella page can poll, the same shape `label_post` already uses.

---

### [MEDIUM] Two write endpoints check for a signed-in user, not a verified one

- Where: `backend/routers/posts.py::confirm_label` (`POST
  /posts/{id}/label/confirm`), `::correct_label` (`POST
  /posts/{id}/label/correct`)
- Document: ARCHITECTURE.md §4 — "The account can log in but every write
  endpoint returns 403 `email_not_verified` until the link is used."
- What the document requires: every write endpoint depends on
  `VerifiedUser`.
- What the code does: both take `user: CurrentUser`, which requires only a
  valid JWT, not `email_verified_at IS NOT NULL`:

  ```python
  @router.post("/{post_id}/label/confirm", response_model=Message)
  async def confirm_label(post_id: int, user: CurrentUser, session: SessionDep) -> Message:
  ```
- Evidence: `backend/deps.py`'s `CurrentUser` vs `VerifiedUser` type aliases
  read directly; `grep -n "CurrentUser\|VerifiedUser" backend/routers/posts.py`
  shows `POST /posts` itself correctly requires `VerifiedUser` while these
  two later endpoints on the same resource do not.
- Why MEDIUM, not HIGH (missing security control would ordinarily be HIGH):
  I could not construct an exploit. Both service functions additionally
  check `post.author_id == user.id`, and `POST /posts` — the only way to
  become a post's author — requires `VerifiedUser`. An unverified account
  can therefore never be the author of any post and so can never pass the
  authorization check inside either endpoint regardless of its verification
  state. The gap is real against the document's literal blanket rule, but I
  found no path to a citizen-facing consequence.
- Suggested fix: change both to `user: VerifiedUser` for consistency with
  every other write endpoint, even though the practical risk is nil today —
  a future service change that widens who may call these (e.g. an editor
  role) would otherwise silently inherit the gap.

---

### [MEDIUM] ARCHITECTURE §2's "one service function" rule remains unmet for two of the endpoints audit run 2 already named — previously reported, still present

- Where: `backend/routers/geo.py::community` (`GET
  /communities/{level}/{id}`), `::officials` (`GET
  /communities/{level}/{id}/officials`), `backend/routers/amendments.py::propose_amendment`
  (`POST /solutions/{id}/amendments`)
- Document: ARCHITECTURE.md §2 — "A router parses the request into a
  Pydantic model, calls **one** service function, and shapes the response.
  No logic."
- What the document requires: one service call per endpoint beyond a
  `require_*` resolver.
- What the code does: `geo.py::community` calls four distinct
  `community_service` functions and assembles the response itself,
  including a list comprehension building `OfficialOut` objects in the
  router:

  ```python
  async def community(level: str, entity_id: int, session: SessionDep) -> CommunityOut:
      resolved = await community_service.resolve(session, level, entity_id)
      return CommunityOut(
          **resolved.as_dict(),
          active_users=await community_service.active_user_count(session, level, entity_id),
          active_user_definition=await community_service.active_user_definition(session),
          officials=[OfficialOut(...) for o in await community_service.officials_for(session, level, entity_id)],
      )
  ```

  `officials` calls two; `propose_amendment` calls
  `amendments_service.community_of_solution`, `.propose`, and
  `.absorption_threshold_for` — three, beyond `require_member`.
- Evidence: `audits/demo-01-audit-2.md`'s own evidence table under this
  exact finding lists `geo.py::community (4)` and, among the offending
  handlers, `amendments.py::propose_amendment` is the natural sibling of the
  `list_amendments`/`decide_similarity` pair fix run 2's `FIX-11` did
  address — but neither `geo.py` nor `propose_amendment` appears anywhere
  in `FIX-11`'s own list of what it fixed (`briefs/demo-01-fix-2.md`'s
  work-item text and HISTORY.md Session 5's completed-work paragraph both
  name only "seven in `admin.py`, two in `amendments.py`
  (`list_amendments`, `decide_similarity`), `auth.py::logout`,
  `summaries.py::summary_pdf` and `umbrellas.py::umbrella_solutions`").
  `backend/tests/test_layering.py`'s AST check (lines ~169–204) counts
  distinct **service modules** imported into an endpoint, not function
  calls — an endpoint calling four functions on one module passes cleanly,
  which is exactly why this survived FIX-11's own new enforcement test.
- Why MEDIUM: matches audit run 2's own severity for this rule ("spec
  mismatch without behavior change" — I found no eligibility or threshold
  arithmetic in either router, only response assembly).
- Suggested fix: add `community_service.detail_view` and fold `officials`
  into it or its own thin wrapper, matching the pattern `solutions_service.detail_view`
  already set for `get_solution`; extend the layering test to count
  distinct service **function** calls, not modules, closing the gap that
  let this recur.

---

### [LOW] The `mailto:` link embeds a relative summary URL, not an absolute one

- Where: `backend/routers/summaries.py::_mailto`
- Document: DEMOCRACY.md §11.5 — "body = a short note and the summary URL
  and hash."
- What the code does: the body includes the summary's path
  (`/summaries/{level}/{entity_id}/{number}`) rather than a fully-qualified
  URL. A recipient who receives the forwarded email outside a browser
  session with the platform open has nothing to resolve the path against.
- Evidence: read directly from `_mailto`'s body-construction code; confirmed
  live in my own walkthrough's publish response
  (`"send_to_representatives": {"subject": "Ballot results — San Jose
  (city), cycle 1", ...}` — the note references "the summary URL" but the
  actual interpolated value in the built body is the relative path).
- Suggested fix: build the link from a configured public base URL (or state
  in DEMOCRACY.md that the path is intentionally relative because the
  platform has no public base URL yet in Demo 1).

---

### [LOW] `build_export` is not listed in ARCHITECTURE §7's job table

- Where: `backend/services/export.py::_schedule_build`,
  `backend/jobs/exports.py::build_export_task`
- Document: ARCHITECTURE.md §7's job table enumerates seven jobs; an eighth
  exists in the code.
- What the code does: `POST /me/export` correctly schedules
  `build_export_task` via `spawn_after_commit` from the service that owns
  the transaction — the mechanism is used correctly — but the table meant
  to be the complete list of background jobs doesn't mention it.
- Suggested fix: add a row to ARCHITECTURE §7 for `build_export | POST
  /me/export | DATABASE §3.11`.

---

## Evidence log

### Step 0 — pre-checks

```
$ git branch --show-current
demo/01
$ git status
On branch demo/01
Your branch is up to date with 'origin/demo/01'.
nothing to commit, working tree clean
$ ls audits/
demo-01-audit-1.md  demo-01-audit-2.md
    -> highest existing K is 2, so this report is audits/demo-01-audit-3.md
$ touch backend/AUDIT_WRITE_TEST && echo WRITABLE || echo READ-ONLY
WRITABLE
$ rm -f backend/AUDIT_WRITE_TEST
```
The source tree is writable, as in both prior audits. I relied on discipline;
the final `git diff main...HEAD --stat` below is the proof of what changed.

```
$ docker compose --env-file .env -f infra/docker-compose.yml up -d
Container ddc_postgres Started / Container ddc_redis Started
$ docker compose --env-file .env -f infra/docker-compose.yml ps
ddc_postgres   postgres:16   Up (healthy)
ddc_redis      redis:7       Up (healthy)
$ curl -sS $OLLAMA_BASE_URL/api/tags
{"models":[{"name":"nomic-embed-text:latest",...},{"name":"llama3.2:latest",...},...]}
```
No `.env` existed; I generated one from `.env.example` with fresh
`JWT_SECRET`/`POSTGRES_PASSWORD` (never printed, never committed —
`.gitignore` covers `.env`). Both required Ollama models present; the suite
ran against the real model, not the mock.

### Migrations from empty, schema verification, seeding

```
$ alembic upgrade foundation@head
Running upgrade  -> 25035d5b7ff5, Foundation initial schema — DATABASE.md §3.
$ alembic upgrade iteration@head
Running upgrade  -> b4b4da0b6e54, Iteration schema — Demo 1 (DATABASE.md §4).

$ python3 backend/scripts/verify_schema.py
[1] live database vs the ORM models              no drift
[2] scratch database (from migrations) vs models no drift
[3] scratch vs live, table by table              no drift — 37 tables identical
[4] the two halves (DATABASE.md §2)              15 Foundation, 22 Iteration, none in both
[5] every foreign key indexed (CLAUDE.md Law 4)  no problems
=== RESULT: NO DRIFT ===

$ python3 -m backend.seed --apply      # pending writes: 590 (all written)
$ python3 -m backend.seed --dry-run
pending writes: 0
Nothing to do: every seed row is already in the database.
```

### Python environment

```
$ pip install --break-system-packages -e ".[dev]"
Successfully installed ... direct-democracy-ca-0.1.0 ...
```
`pyproject.toml`'s `version = "0.1.0"` is PEP 440-valid; an editable install
succeeds cleanly (FIX-03's claim confirmed; this Ubuntu image also lacks
`python3.14-venv`, same as audit run 1 found, so I used
`--break-system-packages` rather than a venv, same workaround).

### Full test suite, real Ollama available

```
$ python3 -m pytest -q
211 passed, 2 deselected in 107.62s (0:01:47)
$ python3 -m pytest -q -m live
2 passed, 211 deselected in 3.50s
```
Matches HISTORY.md's Session 5 claim exactly (211 + 2).

### Required greps

```
$ grep -rn "TODO\|FIXME" backend/ frontend/src/                          -> (nothing)
$ grep -rn "os.environ" backend/ | grep -v settings_env.py               -> (nothing)
$ grep -rn "except:\s*$|except: pass|except Exception: pass" backend/    -> (nothing)
$ grep -rn "^from backend\.\(repositories\|clients\|jobs\)" backend/routers/                -> (nothing)
$ grep -rn "session\.\(execute\|get\|add\|commit\|scalar\|flush\)\|select(" backend/routers/ -> (nothing)
$ grep -rn "session\.\(execute\|get\|scalar\)\|[^_a-z]select(" backend/services/            -> (nothing)
```
Widened except-handler sweep (the trap fix run 2's own evidence names):
every `except Exception:` found (in `jobs/scheduler.py`, `clients/redis.py`,
`deps.py`, `middleware.py`, `db.py`, `jobs/reconcile.py`, `jobs/labeling.py`,
`jobs/exports.py`, `jobs/similarity.py`) logs with `log.exception(...)` or
`log.warning(..., exc_info=True)` before continuing or falling open with a
named, logged reason (Redis unavailable, rate limiting falls open, etc.) —
none swallows silently. Read every one directly.

### `backend/scripts/reconcile.py --dry-run`

```
# before any civic data (seed only):
corrected: False   net_score_drift: []   dominance_changes: []
orphan_communities: []   hash_mismatches: []

# after my full walkthrough (6 users, 1 deleted; 1 post; 2 solutions;
# 1 amendment absorbed; 5 comments; 1 cycle; 2 ballot items; 5 ballot votes;
# 2 juries — 1 superseded; 3 jurors; 2 holdbacks; 1 summary):
corrected: False   net_score_drift: []   dominance_changes: []
orphan_communities: []   hash_mismatches: []
```

### My own full-cycle walkthrough — six accounts, from scratch, through `httpx`

Written independently (not the build's own `walkthrough_fix2.py`), covering
the build brief's original cycle plus live re-verification of FIX-08,
FIX-09, FIX-10, FIX-13, and FIX-19. Representative excerpts (raw script and
full log kept in the session scratchpad, not committed):

```
Six residents of San Jose / Santa Clara County sign up, verify (console-log
tokens), log in. Alice granted admin only via grant_admin.py --apply.

Ben posts one problem with one solution -> labeled into "Road Damage and
Pothole Repair" by the real llama3.2. Cara adds a second, competing
solution directly on the umbrella.

Derek, Elena, Farid each upvote both solutions -> both is_dominant: true
(dominant_threshold 1, active_users 6). Cara proposes an amendment on
solution A; Derek + Elena back it -> absorbed, current_version 2.

Five-comment chain on solution A: depth 0,1,2,3 (the cap), then a fifth
comment past the cap re-attaches at depth 3 with reply_to_comment_id
pointing at the depth-3 comment:

  BEFORE Farid changes display:
    "replying to @Audit3Farid: Thank you for laying that out, Farid."
  AFTER Farid switches to anonymous:
    "replying to @Anonymous Community Member: Thank you for laying that out, Farid."
  AFTER Farid's account is deleted (at the end of the script, once he is no
  longer needed for jury eligibility):
    "replying to @Former Community Member: Thank you for laying that out, Farid."

  $ SELECT id, text, reply_to_comment_id FROM comments WHERE id=5;
  text = "Thank you for laying that out, Farid."   -- unchanged across all three states
```

```
Admin lowers ballot_min_dominant_days to 0 (logged reason), prepares the
city ballot -> jury of 3 drawn (Derek, Elena, Farid — Alice/Ben/Cara all
correctly excluded as admin/author/amendment-author, DEMOCRACY §8.1).

FIX-09: redraw-jury with a logged reason.
  GET /cycles/1 afterward:
    jury_id 1: status "superseded", jurors [{"status":"replaced"} x3]
    jury_id 2: status "current",    jurors [{"status":"drawn"} x3]
  Both draws' pool, random bytes, and per-juror statuses fully inspectable.

Three jurors accept. Two hold back solution B together (majority of 3);
one holds back solution A alone (minority of 3).

  GET /cycles/1/ballot (after open):
    item A (solution 1): held_back=false, votable=true, result=null
    item B (solution 2): held_back=true,  votable=false, result="held_back"
```

```
All five non-deleted accounts vote yes on item A. Admin closes, publishes.

Published header: "jury": "3 drawn, 0 replaced, 3 seated" — correct math
(no decline occurred this cycle, so 0 replaced).

Results section, item A (passed 5-0):
  "juror_concerns": {"label": "Juror concerns (1 of 3 seated)",
    "reasons": [{"juror": "Juror 1 of 3", "category": "incomplete",
    "reason": "...the schedule-posting piece needs a named city
    department..."}]}
  -- the MINORITY hold-back, published even though it never took effect.

Held back section, item B:
  "jury_reasons": [{"juror": "Juror 2 of 3", ...}, {"juror": "Juror 3 of 3", ...}]
  -- the MAJORITY hold-back, and the item it removed from the ballot.

GET /solutions/1 .jury_notes, fetched fresh after open:
  {"cycle_number": 1, "seated": 3, "notes": [{"juror": "Juror 1 of 3",
   "category": "incomplete", "reason": "..."}]}
  -- "Jury notes" on the solution page, live, matching DEMOCRACY §8.3
  ("from the moment the ballot opens"); null when I checked before open.
```

### Hash round-trip — two independent methods

```
$ curl /summaries/city/408/1/verify
{"stored_hash": "0f9d3a4a...b927", "recomputed_hash": "0f9d3a4a...b927", "match": true}

$ curl /summaries/city/408/1/json > summary.json
$ python3 -c "import json,hashlib; d=json.load(open('summary.json'));
    print(hashlib.sha256(json.dumps(d, sort_keys=True,
    separators=(',',':'), ensure_ascii=False).encode()).hexdigest())"
0f9d3a4a5e2ca7f5806b52e901224bc396d8b722e83442da7c8fd77bfc42b927
```
My own from-scratch canonical re-serialization matches the stored hash and
the platform's own `/verify` endpoint, independently.

### Three hand-derived `threshold()` cases, against the imported function

```
threshold(5, 3, 1000)   hand: ceil(0.05*1000)=50, min(50,3)=3, max(1,3)=3    code: 3   MATCH
threshold(25, 3, 7)     hand: ceil(0.25*7)=2,    min(2,3)=2, max(1,2)=2     code: 2   MATCH
threshold(10, 5, 0)     hand: ceil(0.10*0)=0,    min(0,5)=0, max(1,0)=1     code: 1   MATCH
```
Run by importing `backend.services.rules.threshold` directly, not a
reimplementation.

### Anonymization — checked at the row level

```
$ DELETE /me (Farid, correct password) -> {"message": "Your account is deleted. ..."}
$ SELECT id, email, real_name, display_name, date_of_birth, gender,
         political_party, county_id, city_id, last_active_at,
         deleted_at IS NOT NULL, is_admin FROM users WHERE id=6;
  deleted+6@invalid | (empty) | Former Community Member | 1900-01-01 |
  prefer_not_to_say | prefer_not_to_say | 43 | 408 | (null) | t | f
$ SELECT password_hash FROM users WHERE id=6;         -> '!'
$ SELECT revoked_at IS NOT NULL FROM refresh_tokens WHERE user_id=6;  -> t
$ SELECT id, author_id, text, depth FROM comments WHERE author_id=6;
  id 4 | author_id 6 | "Audit3 depth3 (cap): the city should log every
  report." | depth 3          -- untouched, as CLAUDE §6 requires
```
Exactly DATABASE §3.1's list, nothing more, nothing less — county/city kept,
comment content and authorship untouched.

### Password policy, live

```
$ 72-char password containing multi-byte UTF-8 (é×70, 142 bytes actual)
{"error":"weak_password","message":"Your password needs to be no longer than 72 characters."}
```
`backend/services/security.py::validate_password` checks
`len(password.encode("utf-8")) > 72`, a genuine byte-length check, not a
character-count proxy — correctly refuses a password that passes the
Pydantic `max_length=72` character check but exceeds bcrypt's actual byte
limit. CLAUDE.md Law 13 (as amended) satisfied precisely.

### `grant_admin.py`, `pyproject.toml`, `/openapi.json`

```
$ python3 backend/scripts/grant_admin.py --help
usage: grant_admin.py [-h] (--dry-run | --apply) [--revoke] email
options: -h, --help  --dry-run  --apply  --revoke  take the administrator flag away instead

$ grep "^version" pyproject.toml
version = "0.1.0"

$ curl /openapi.json | (count paths/method-combos)
paths: 66   method-path combos: 72
```
Matches HISTORY.md's Session 5 claims exactly.

### Frontend — built, served, checked directly

```
$ npm install                 -> 0 vulnerabilities
$ npx tsc --noEmit             -> exit 0
$ npm run lint                 -> clean
$ npm run build                -> Compiled successfully; 25 routes (Next.js 16.3.5)
$ npm run start -p 3000; curl every route in ARCHITECTURE §9

/ /signup /login /verify-email /forgot-password /reset-password /me
/legal/privacy /legal/terms /legal/cookies /settings /ai/actions /admin/log
/admin /feed /posts/new /umbrellas/1 /solutions/1 /ballot /jury /results
/summaries/city/408/1 /summaries/hashes /cycles/1 /posts/1
  -> all HTTP 200, exactly one <h1>, a unique per-route server-rendered
     <title> present before hydration (e.g. "Join your community · Direct
     Democracy Cali") — confirms FIX-16/FIX-17's server-rendered-metadata
     claim; audit run 2's LOW finding on this point is resolved.

$ grep -rn "<img\|background-image\|backgroundImage\|next/image" frontend/src/
  (nothing — the platform ships no images at all; "images off" is trivially satisfied)

$ grep -n "aria-invalid\|aria-describedby\|focus()" frontend/src/components/useFormError.tsx
  present and wired; grep -c "useFormError" across signup/login/posts-new
  PageClient.tsx confirms the hook is actually applied, not just defined.
```

### Five parallel research passes, each independently verified before inclusion above

I dispatched five research agents to review, respectively: (1) FIX-08
through FIX-13/FIX-19 delivery against the actual code; (2) AI accountability
(Law 7 ordering, AI-never-decides) and the security checklist (§4.3); (3)
DATABASE.md table/column/constraint conformance; (4) ARCHITECTURE.md
endpoint/pagination/layering/job conformance; (5) DEMOCRACY.md rule
implementations (`threshold()`, dominance, qualification, absorption, jury
exclusions, majority rule, zero-item cycle, ballot result, summary hash).
Every finding any of them returned, I re-derived myself by reading the cited
file and function directly (not trusting their prose) before deciding
whether to include it here; several minor observations they raised (an
undocumented `UNIQUE` constraint on `officials`, a redundant index on
`users.email`, `evaluate_dominance` running inline rather than via
`spawn_after_commit`) I judged not to rise to a reportable finding after
reading the code myself, for the reasons noted inline in "Checks passed"
below. Passes (1), (3), and (5) returned zero findings after my own
verification; passes (2) and (4) are the source of the findings above.

### Final diff check

```
$ git status
On branch demo/01
nothing to commit, working tree clean   (before writing this report)

$ git diff main...HEAD --stat | tail -1
231 files changed, 32632 insertions(+), 5027 deletions(-)
    (all from the build and both fix runs; this report and my HISTORY.md
    paragraph are not yet committed at the time of this check)
```
I will re-run this after committing, and it must show only `audits/` and
`HISTORY.md` beyond the pre-existing 231.

---

## Checks passed

Every AUDIT.md §4 check with no finding above.

**§4.1 Constitution**
- Ballot vote returned only to its voter — `ballot_view` reads only the
  caller's own rows; the export contributor is scoped to the exporting
  user; the admin user-view endpoint returns a fixed sentence, never a row.
  Confirmed by code reading, by a dedicated research pass, and live in my
  own walkthrough (`my_vote` populated only for the account making the
  request).
- Vote weight independent of verification level or admin status —
  `net_score = upvotes − downvotes`; ballot tallies use plain `count()`;
  `verification_level` is stored per-vote for reporting only and never
  joined into a tally. No code path found where it or `is_admin` affects a
  count.
- AI row written before its result is shown (Law 7) — traced in order for
  all three AI actions (labeler, similarity, reference recommendation):
  `ai_log.record(...)` precedes the row that makes the result visible in
  every case.
- AI never decides — label rows are `unreviewed` until a human
  confirms/corrects; similarity decisions require a human press; no AI
  output crosses a threshold or creates an umbrella anywhere in `rules.py`
  or the status-transition path.
- No `os.environ` outside `settings_env.py`; no bare `except:`/`except:
  pass`; no `TODO`/`FIXME` — grep clean, and every `except Exception:`
  handler I read logs before continuing.
- No synchronous DB/HTTP call found inside request-path `async def` code.

**§4.2 Specification conformance**
- All 37 tables (15 Foundation, 22 Iteration) exist exactly as documented;
  `verify_schema.py` confirms no drift three ways, both before and after my
  data. A DATABASE-conformance research pass checked every named column,
  index, and constraint in §3–§4 against the migrations and models
  directly, including partial-unique indexes on `users.display_name`,
  `solutions.(post_solution_id, umbrella_id)`, `cycles`'s one-open-cycle
  constraint, and `juries`'s one-current-draw constraint — all genuine
  database-level constraints, not application-only checks. `content_hash`
  field lists for `comments` and `amendments` match DATABASE §4.11/§4.9
  exactly, field-for-field.
- `threshold()`, dominance, qualification (all four conditions, including
  the easy-to-miss "newer than last ballot version"), absorption
  (denominator is the solution's supporters, not the community), jury draw
  exclusions (all four), the majority hold-back rule (seated jurors,
  counted at ballot-open), the zero-item cycle's state-machine guard, the
  ballot result rule (strict `>`, quorum `>=`, ties fail), and the summary
  hash (computed once at publish, never recomputed) — a dedicated research
  pass verified each against the actual code, and I independently
  re-derived `threshold()` myself against the imported function (above).
- Every DEMOCRACY §7.4 setting seeded (22 keys) and consulted by the code
  the document says depends on it — watched `dominant_threshold` and
  `ballot_threshold` change live as I changed `ballot_min_dominant_days`.
- State transitions matched DEMOCRACY §10.1 exactly in my own walkthrough;
  the held-back item correctly never became votable.

**§4.3 Security**
- bcrypt hashing (cost 12), refresh tokens stored as SHA-256 only, rotation
  with whole-chain revocation on reuse, logout blacklist — all confirmed by
  a dedicated research pass reading the actual functions, consistent with
  both prior audits' own direct checks.
- Rate limiting is global ASGI middleware inspecting every write method, not
  a per-route dependency that could be omitted by accident.
- No secret found in any log line, error response, or committed file.
- Anonymization erases exactly DATABASE §3.1's list — confirmed at the row
  level in my own walkthrough (above), on an account that had also just
  authored content inside the very comment thread I was using to test
  FIX-08, so both checks share one piece of live evidence.
- 72-byte password cap is a genuine byte-length check, refused rather than
  truncated, confirmed live with a multi-byte password (above).

**§4.4 Evidence**
- Test suite, `verify_schema.py`, `reconcile.py --dry-run`, seed dry-run,
  full-cycle walkthrough, hash round-trip, and threshold derivations all
  reproduced independently on my own database, all pasted above. Every
  fix-run-2 claim I set out to re-verify (FIX-08, FIX-09, FIX-10, FIX-13,
  FIX-14, FIX-19, `npm audit`, the frontend build, `/openapi.json`'s 72
  endpoints) matched HISTORY.md's Session 5 entry exactly.

**§4.5 Frontend**
- Every ARCHITECTURE §9 route builds and returns 200 with exactly one
  `<h1>` and a unique server-rendered `<title>` — resolving audit run 2's
  LOW finding on this point.
- No images anywhere, so "works with images off" is trivially satisfied.
- `useFormError`'s `aria-invalid`/`aria-describedby`/focus-management
  wiring is genuinely present and applied across the forms I checked
  (signup, login, posts/new) — resolving audit run 2's document ambiguity
  #4, now that CLAUDE §8 names WCAG 2.1 AA as the bar.
- No client-side threshold/eligibility computation found in the frontend
  (spot-checked the same way both prior audits did).

**§4.6 Documents**
- No edit to CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, or
  ARCHITECTURE.md on this branch outside the director's own commits
  (`git log --oneline main..demo/01 -- CLAUDE.md ...` shows only
  director-authored commits, consistent with both prior audits' checks).
- TODO.md's Phase 2b ids: FIX-08, FIX-09, FIX-10, FIX-12, FIX-13, FIX-14,
  FIX-15, FIX-16, FIX-18, FIX-20 all check out against my own
  re-verification. **FIX-11 is marked `[x]` but is incomplete** — see the
  MEDIUM finding above and "Previously reported, still present" below.
  FIX-17 is honestly marked `[~]` with its own gap stated (`posts/new`'s
  dynamic fields); I did not find that gap understated.
- HISTORY.md's Session 5 entry records every decision I could independently
  verify a rationale for, including the "replaced" wording clash it flags
  itself (see Document ambiguities below) and the ordering fix for
  FIX-19's first, wrong implementation.

---

## Previously reported, still present

**Audit run 2's MEDIUM "ARCHITECTURE §2's 'one service function' half is
unmet" is only partially resolved.** Audit run 2's own evidence table named
five offending handlers: `solutions.py::get_solution` (10 calls),
`amendments.py::propose_amendment` (4), `amendments.py::list_amendments`
(4), `geo.py::community` (4), `umbrellas.py::umbrella_solutions` (4).
Fix run 2's `FIX-11` fixed `get_solution`, `list_amendments`,
`umbrella_solutions`, and a further seven `admin.py` endpoints,
`auth.py::logout`, and `summaries.py::summary_pdf` that were not
individually named in audit run 2's table but shared the same shape —
genuine, substantial progress, and the new AST check in `test_layering.py`
is a real, live-enforced guardrail for the cases it can see. But two of
audit run 2's own five named offenders — `geo.py::community` and
`amendments.py::propose_amendment` — are untouched, still call multiple
service functions from the router, and are invisible to the new test
because it counts distinct service **modules**, not function calls, and
both offenders call several functions from a single module. `FIX-11`'s own
completed-work list in HISTORY.md's Session 5 entry never names either one.
Reported above as its own MEDIUM finding; recorded here because `TODO.md`
marks the id done without this residue being called out, which is the same
shape of gap audit run 2 itself caught in fix run 1's `FIX-01` ("narrower
wording than the brief").

Every other item from audit run 1 and audit run 2 that I set out to
re-verify is genuinely resolved:

- The `CRITICAL` (deep-reply name freeze) and `HIGH` (jury redraw deletion)
  from audit run 2 — both fixed, both independently reproduced fixed in my
  own walkthrough (above).
- Audit run 2's MEDIUM on the labeler not recording invented communities
  (FIX-12) — fixed; I read `labeling.py::label_post`'s current branch
  directly and confirmed the unlisted-community case now appends to
  `duplicates` the same as the repeated-key case.
- Audit run 2's MEDIUM on five specific unpaginated endpoints — resolved:
  four are now correctly named exemptions in the updated ARCHITECTURE §6,
  and the fifth (`GET /umbrellas`) now paginates and refuses `limit>100`
  with 422 (confirmed live in my own walkthrough). A different, larger set
  of unpaginated endpoints exists — the HIGH finding above — but it is not
  a recurrence of this specific finding.
- Audit run 2's MEDIUM on `grant_admin.py`'s documented invocation — the
  code already matched the corrected ARCHITECTURE §4; `--help` confirmed
  live (above).
- Audit run 2's MEDIUM on the frontend dependency advisories — `next`
  16.3.5, `npm audit --audit-level=high` reports zero vulnerabilities
  (confirmed live, above).
- Audit run 2's MEDIUM on minority hold-backs not being published — fixed
  and independently reproduced (FIX-10, above).
- All seven of audit run 2's LOW findings (undocumented `/legal/*` and
  `/health` endpoints now listed in ARCHITECTURE §6; the two swallowing
  handlers narrowed and logged; the blocking CSV read moved behind
  `asyncio.to_thread`; the stale hashing docstring replaced; the
  label-retry fallback named as a constant; the `bad_setting_value`
  grammar fixed; every page's title now server-rendered) — each confirmed
  directly, either by reading the cited code or, for the frontend title
  fix, live via HTTP.
- Audit run 1's original `HIGH` (routers/services touching the ORM
  directly) remains fixed — both layering greps return nothing, and
  `test_layering.py` enforces it by AST, as both prior audits already
  confirmed and I re-confirmed here.

---

## Document ambiguities

For the director. I did not resolve this.

1. **DATABASE §4.17's `jurors.status = "replaced"` and `replaced_by_id` are
   never populated on the same row by any code path.** A decline
   (`juries.py::decline`) sets the declining juror's own status to
   `"declined"` and populates `replaced_by_id` on that row, pointing at
   their replacement. The only place `status = "replaced"` is ever written
   is a full redraw (`juries.py::redraw`), which bulk-marks every juror of
   the entire superseded jury `"replaced"` — and never touches
   `replaced_by_id` for any of them, since a redraw creates a wholesale new
   draw rather than seat-by-seat replacements. The schema's column list
   reads as though the two fields are meant to appear together for a
   single-seat replacement (which is what FIX-19's own summary-header
   logic actually counts, via `status = "declined"` — a distinct value from
   `"replaced"`). This does not affect any behavior I could find — the
   published header's math is correct and covered by a real end-to-end
   test — but a future reader of DATABASE §4.17 alone, without this
   session's or fix run 2's HISTORY notes, would reasonably expect the two
   fields to co-occur, and they never do. Worth a clarifying sentence in
   DATABASE §4.17 distinguishing the two mechanisms (redraw supersession
   vs. per-seat decline-and-replace) explicitly, which fix run 2's own
   HISTORY entry already flags as worth doing but which has not yet reached
   the document.
