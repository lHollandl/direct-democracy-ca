# Audit — demo-01, run 2, 2026-09-14

## Summary

One `CRITICAL`, one `HIGH`, six `MEDIUM`, seven `LOW`, three `NOTE`.
**Verdict: FIX REQUIRED.**

Both traps AUDIT.md §4.1 marks always-`CRITICAL` are clean, and I confirmed
both by running the platform rather than by reading it: every caller of
`GET /cycles/{id}/ballot` sees their own vote and nothing else, an
administrator asking about a voter is told the vote is not available to
anyone but the voter, no endpoint I could reach emits a `voter_id`, and an
administrator's upvote moved a net score by exactly one, the same as any
member's. Fix run 1's work holds up: the two layering greps return nothing,
`test_layering.py` enforces them by AST, no router imports a job, and
`comments.content_hash` now covers `parent_id`. The machinery underneath is
genuinely good — I rebuilt the database from empty, ran the full cycle with
seven accounts through `curl`, and every hash recomputed, every threshold
matched a hand derivation, every state transition refused what the document
says it must refuse, and anonymization erased exactly the columns
DATABASE §3.1 lists and nothing else.

The `CRITICAL` is not in the ballot or the AI log; it is in comments. When a
reply is pushed past the depth cap, the platform writes the parent author's
**resolved display name** into the child comment's stored `text` — the column
that feeds `content_hash`. I reproduced a user setting their display to their
real name, receiving a deep reply, then switching to anonymous and finally
deleting their account: `users.real_name` was erased as promised, and the
public thread still reads `replying to @Audit Person 6`, inside a permanent
hash that Law 6 forbids rewriting. That defeats CLAUDE §6 for a reader who
chose anonymity, and it defeats the erasure promise the deletion endpoint
makes in its own response text.

The `HIGH` is that redrawing a jury deletes the previous jury row outright,
so the first draw's eligible pool, drawn ids, timestamp and random bytes are
destroyed — DEMOCRACY §8.1 requires them kept "so it can be inspected after
the fact". The public admin log still records *that* a redraw happened and
why, which is why this is `HIGH` and not `CRITICAL`, but no one can inspect
any draw except the last one.

One item from run 1 is marked done and is only half delivered; see
"Previously reported, still present".

Counts: **CRITICAL: 1 · HIGH: 1 · MEDIUM: 6 · LOW: 7 · NOTE: 3**

---

## Findings

### [CRITICAL] A deep reply freezes the parent author's display name — possibly their real name — into permanent, hashed comment text

- Where: `backend/services/comments.py::create`
- Document: CLAUDE.md §6 ("Users own their identity… Users control what is
  shown publicly, including full anonymity"); DATABASE.md §3.2 ("**Author
  display** everywhere = per this row at render time"); DATABASE.md §3.1
  (anonymization erases `real_name` and `display_name`); CLAUDE.md Law 6
  (`content_hash` is permanent, never modified).
- What the document requires: a person's public name is resolved at render
  time from their current `public_name_mode`, so changing that setting — or
  deleting the account — changes what every reader sees, everywhere. The
  `content_hash` attests to the content the author wrote.
- What the code does: when a reply would exceed `comment_max_depth`, the
  service resolves the parent author's display name and **prepends it to the
  stored text**, which is then hashed:

  ```python
  if parent.depth >= max_depth:
      displays = await author_displays(session, [parent.author_id])
      replying_to = displays.get(parent.author_id)
      ...
  body = f"replying to @{replying_to}: {clean}" if replying_to else clean
  ```

  The name is a snapshot in a row that is immutable by law, not a render-time
  lookup. It does not follow the named user's later choices.
- Evidence: user 6 set their display to their real name, posted at the depth
  cap, received a reply, then went anonymous and deleted the account.

  ```
  === user6 sets their public display to their REAL NAME ===
  {"public_name_mode":"real_name","shown_as":"Audit Person 6"}

  === what got STORED and HASHED ===
   id | depth |                              stored_text
  ----+-------+------------------------------------------------------------------
    7 |     3 | I walk this crossing daily and can confirm the timing is far too
    8 |     3 | replying to @Audit Person 6: Thank you for confirming that, it ma

  === user6 exercises the right to erasure ===
  {"message":"Your account is deleted. Your name, email, password, date of
   birth, gender and political party are erased. ..."}

  === users.real_name is erased as promised ===
   id | real_name |      display_name       | deleted
  ----+-----------+-------------------------+---------
    6 |           | Former Community Member | t

  === but the public thread still publishes their real name ===
  replying to @Audit Person 6

  === and it is inside the immutable content_hash ===
   id |                     text                      |             content_hash
  ----+-----------------------------------------------+--------------------------------------
    8 | replying to @Audit Person 6: Thank you for co | 26e8d05622408e0c4f79ac33b66f8c05...
  ```

  The same run showed the render-time rule working correctly for the `author`
  field — user 5's own comment flipped to `Anonymous Community Member` the
  moment they changed the setting — which is precisely the contrast: the
  field the platform controls follows the user's choice, the text it wrote on
  their behalf does not.
- Suggested fix: store the pre-reattachment parent's `author_id` in a new
  column and render `replying to @display` at read time through
  `author_displays`, leaving `text` — and therefore `content_hash` — as only
  what the person actually typed.

---

### [HIGH] Redrawing a jury destroys the previous draw's record, which DEMOCRACY §8.1 requires be inspectable afterwards

- Where: `backend/services/juries.py::redraw`
- Document: DEMOCRACY.md §8.1 — "The draw is **logged**: the eligible pool
  (user ids), the drawn ids, the timestamp, and the random bytes used, so it
  can be inspected after the fact." DATABASE.md §4.17 gives `jurors.status`
  the values `replaced` and a `replaced_by_id` column.
- What the document requires: every draw remains on record, so a reader can
  check after the fact that the jury gating the ballot was drawn fairly.
- What the code does: `redraw` marks the old jurors `replaced`, flushes, then
  deletes the whole `juries` row, which cascades and removes those juror rows
  before the status is ever observable:

  ```python
  for juror in await cycles_repo.jurors(session, existing.id):
      if juror.status in ("drawn", "accepted"):
          juror.status = "replaced"
  await session.flush()
  await cycles_repo.delete_jury(session, existing.id)
  ```

  So `status = 'replaced'` and `replaced_by_id` are unreachable states, and
  the prior draw's `eligible_pool`, `random_bytes` and `drawn_at` are gone.
- Evidence: jury 2 for cycle 4 before the redraw, and after.

  ```
  === the ORIGINAL draw record ===
  id | 2   cycle_id | 4   eligible_pool | [2, 4, 5]
  random_bytes | 6bb7dcce5774ad94d885c8abdab367587a8ea3c3a62ba0d8a43abb2b07b186f0
   id | jury_id | user_id | seat | status
    5 |       2 |       5 |    1 | drawn
    6 |       2 |       2 |    2 | drawn
    7 |       2 |       4 |    3 | drawn

  === REDRAW ===  {"jury_id": 3, "drawn": 3, ...}

  === what survives of the FIRST draw? ===
  (only jury 1 for cycle 2 and the new jury 3 for cycle 4 remain;
   jury 2 and juror rows 5, 6, 7 no longer exist)

  === the public admin log retained ===
  "action": "redraw_jury", "old_value": {"jury_id": 2},
  "new_value": {"drawn": 3, "jury_id": 3}, "reason": "..."
  ```

  The admin log's `old_value` points at a row that no longer exists. A reader
  can count redraws but cannot inspect any draw except the final one, which
  is the specific check §8.1 exists to make possible.
- Suggested fix: keep superseded `juries` rows — drop the unique constraint on
  `cycle_id` in favour of a `superseded_at`/`supersedes_id` marker, so every
  draw for a cycle stays on record and `replaced` becomes observable.

---

### [MEDIUM] The labeler ignores communities the model invents but does not record them, though DEMOCRACY §9.1 names the field for exactly that

- Where: `backend/services/labeling.py::label_post`
- Document: DEMOCRACY.md §9.1 — "the labeler keeps the first answer that names
  an umbrella actually active in that community and ignores the rest;
  **everything ignored is recorded on the AI action row under
  `output.repeated_or_unlisted_communities`**".
- What the document requires: both kinds of ignored answer — a *repeated*
  community and an *unlisted* one — land in that field. The field name says
  so.
- What the code does: the `duplicates` list is only appended to when the key
  has already been seen, so a community the model invented that the author
  never selected is silently ignored and never recorded there:

  ```python
  if key in choices:
      duplicates.append({"community": ..., "umbrella_id": chosen})
      ...
      continue
  choices[key] = chosen if resolves else None   # unlisted community: no record
  ```
- Evidence: my own post was filed correctly, and `llama3.2` also answered for
  `city:1`, which was never selected. The public log row shows the invented
  community ignored and the field empty:

  ```json
  "output": {
    "umbrellas": [
      {"umbrella_id": 2,    "community_level": "city", "community_entity_id": 408},
      {"umbrella_id": null, "community_level": "city", "community_entity_id": 1}
    ],
    "confidence": 0.8,
    "repeated_or_unlisted_communities": []
  }
  ```

  Mitigating: the model's raw answer *is* stored in `output.umbrellas`, so the
  public log does show what the model said. The constitutional promise
  (CLAUDE §5, Law 7) is kept; DEMOCRACY §9.1's specific field is not.
- Suggested fix: append to `duplicates` in the `else` branch too, when the key
  is not one of the post's selected communities.

---

### [MEDIUM] ARCHITECTURE §2's "one service function, no logic" half is unmet, and `test_layering.py` does not cover it

- Where: `backend/routers/solutions.py::get_solution` (worst case) and 36
  other endpoints; `backend/tests/test_layering.py`
- Document: ARCHITECTURE.md §2 — "A router parses the request into a Pydantic
  model, calls **one** service function, and shapes the response. No logic."
- What the document requires: one service call per endpoint; no rule
  arithmetic and no eligibility decisions in a router.
- What the code does: 37 endpoints call more than one service function. Most
  are the benign `require_X(...)` + action pair. `get_solution` is not: it
  makes ten service calls, computes three thresholds itself, and decides
  whether discussion is visible:

  ```python
  "dominant_threshold": rules.dominant_threshold(...),
  "ballot_threshold":   rules.ballot_threshold(...),
  "on_track_for_ballot": rules.on_track_for_ballot(...),
  "discussion": (await comments_service.thread(...) if solution.is_dominant else []),
  ```

  `test_layering.py` checks only forbidden imports and `session.execute`/
  `session.get`/`select(`, so this half of §2 is unguarded and can regress.
- Evidence: an AST pass over `backend/routers/` counting service calls per
  decorated handler — full table in the evidence log; the top rows are
  `solutions.py::get_solution` (10), `amendments.py::propose_amendment` (4),
  `amendments.py::list_amendments` (4), `geo.py::community` (4),
  `umbrellas.py::umbrella_solutions` (4).
- Suggested fix: move `get_solution`'s assembly into
  `solutions_service.detail_view` so the router returns what it is given, and
  extend `test_layering.py` to fail an endpoint that calls more than one
  service module beyond a `require_*` resolver.

---

### [MEDIUM] Several list endpoints do not paginate, and accept an over-limit `limit` silently

- Where: `backend/routers/geo.py::counties`, `::cities`, `::officials`;
  `backend/routers/umbrellas.py::list_umbrellas`;
  `backend/routers/transparency.py::settings`
- Document: ARCHITECTURE.md §6 — "All list endpoints paginate with
  `?cursor=&limit=` (default 25, max 100)."
- What the document requires: every list endpoint returns a page and a cursor,
  capped at 100.
- What the code does: these five return a complete bare list with no
  `next_cursor`, and `?limit=500` is accepted rather than refused.
- Evidence:

  ```
  /geo/counties    default_items=58 next_cursor=False  limit=500 -> http 200, 58 items
  /ai/actions      default_items=2  next_cursor=True   limit=500 -> http 422
  /admin/log       default_items=9  next_cursor=True   limit=500 -> http 422
  /feed            default_items=1  next_cursor=True   limit=500 -> http 422

  /geo/counties/43/cities            -> bare list
  /communities/city/408/officials    -> bare list
  /umbrellas?community=city:408      -> no next_cursor
  /settings                          -> no next_cursor
  ```

  The paginated endpoints do it correctly, so this is inconsistency rather
  than absence. All five are currently small (58 counties, at most 88 cities
  in Los Angeles County, 5 officials, 10 umbrellas, 22 settings); umbrellas
  is the one that grows without bound once the proposal system lands.
- Suggested fix: either paginate these five, or amend ARCHITECTURE §6 to
  exempt fixed-size reference lists by name.

---

### [MEDIUM] The documented `grant_admin.py <email>` invocation does not work

- Where: `backend/scripts/grant_admin.py`
- Document: ARCHITECTURE.md §4 — "`backend/scripts/grant_admin.py <email>
  [--dry-run]`", i.e. the bare form applies and `--dry-run` is optional.
- What the document requires: `grant_admin.py <email>` grants the flag.
- What the code does: the script requires an explicit `--dry-run` **or**
  `--apply`; the documented form exits with an argparse error.
- Evidence:

  ```
  $ python backend/scripts/grant_admin.py auditor1@example.com
  usage: grant_admin.py [-h] (--dry-run | --apply) [--revoke] email
  grant_admin.py: error: one of the arguments --dry-run --apply is required
  ```

  The code's behaviour is the safer of the two and matches the `--dry-run` /
  `--apply` pattern DATABASE §6 sets for scripts; the document is probably
  what is wrong. Flagged because the fix brief asked that ARCHITECTURE §4 be
  checked against the code and this survived.
- Suggested fix: change ARCHITECTURE §4 to
  `grant_admin.py <email> (--dry-run | --apply) [--revoke]`.

---

### [MEDIUM] A juror's hold-back reason is published only if the hold-back reaches a majority, though the API promises otherwise

- Where: `backend/services/summaries.py` (the `held_back` section) and
  `backend/services/juries.py::hold_back`
- Document: DEMOCRACY.md §8.3 — "Each juror's category and reason are recorded
  and all are published." DEMOCRACY.md §11.2 item 3 describes the "Held back"
  section only.
- What the document requires: at minimum, the platform should not tell a juror
  their reason will be published and then not publish it.
- What the code does: `hold_back` returns `"Your reason will be published with
  the results."` to every juror. Only hold-backs that reach a majority of
  seated jurors appear in the summary; a minority hold-back is stored and
  never surfaced on any endpoint.
- Evidence: juror 1 held item 1 back; with two seated jurors that is not a
  majority, so the item stayed votable and passed. The row exists:

  ```
   id | juror_id | ballot_item_id |     reason_category      | reason
    3 |        1 |              1 | incomplete               | The repainting schedule is sound but the amen...
  ```

  and is published nowhere:

  ```
  /cycles/2                      -> 0
  /cycles/2/ballot               -> 0
  /solutions/1                   -> 0
  /umbrellas/2                   -> 0
  /summaries/city/408/2/json     -> 0
  (occurrences of that reason text)
  ```
- Suggested fix: either show non-effective hold-backs on the solution page
  (§8.4 already says previous reasons are shown there), or change the message
  the endpoint returns so it only promises publication when the hold-back
  takes effect. The director should settle which, per the ambiguity below.

---

### [MEDIUM] The frontend dependency tree carries 12 known advisories, one rated critical

- Where: `frontend/package.json` (`next` pinned to `16.1.6`)
- Document: CLAUDE.md Principle 7 — "When in doubt, choose the more secure
  option even if it takes longer to build."
- What the document requires: a platform real people trust with their
  political views should not ship on dependencies with open critical
  advisories when a patch release exists.
- What the code does: pins `next@16.1.6`; `npm audit` reports
  `{'low': 1, 'moderate': 2, 'high': 8, 'critical': 1, 'total': 12}`, with the
  critical in `next` itself (`9.3.4-canary.0 - 16.3.2`). Fix is `next@16.3.5`.
- Evidence:

  ```
  critical  next   9.3.4-canary.0 - 16.3.2
            - Next.js: HTTP request smuggling in rewrites
            - Next.js: Unbounded next/image disk cache growth can exhaust storage
            - Next.js: Unbounded postponed resume buffering can lead to DoS
            - Next.js: null origin can bypass Server Actions CSRF checks
  high      browserslist, flatted, js-yaml, nanoid, brace-expansion, sharp
  ```

  Stated plainly: I found **no reachable path** for the critical advisories in
  this app as built — there are no Server Actions (`grep "use server"` finds
  nothing), no `rewrites` in `next.config.ts`, and no `next/image` or `<img>`
  anywhere. The remaining highs are DoS in build-time tooling. I am reporting
  the pin, not a demonstrated exploit.
- Suggested fix: bump `next` to `16.3.5` and re-run `npm audit` as part of the
  build evidence set.

---

### [LOW] Five endpoints exist that ARCHITECTURE §6 does not list

- Where: `backend/routers/legal.py`, `backend/main.py`
- Document: AUDIT.md §4.2 — "nothing exists that is not in DATABASE.md (or is,
  and is reported as 'undocumented')".
- What the code does: `GET /health`, `GET /legal/privacy`, `GET /legal/terms`,
  `GET /legal/cookies`, `GET /legal/current-version` are implemented and
  public-read. The three `/legal/*` pages are required by ARCHITECTURE §9's
  route table, so the endpoints behind them are clearly intended; §6 simply
  never lists them.
- Evidence: 72 endpoints in `/openapi.json`; all of §6's appear; these five
  are the remainder.
- Suggested fix: add a "Legal and health (F)" row to ARCHITECTURE §6.

---

### [LOW] Two exception handlers swallow without logging, one of them over-broadly

- Where: `backend/middleware.py::_caller_key`, `backend/jobs/scheduler.py::stop`
- Document: CLAUDE.md Law 12 — "Never swallowed… logged server-side with full
  detail."
- What the code does:

  ```python
  # middleware.py::_caller_key
  try:
      payload = security.decode_access_token(header[7:])
      return f"user:{payload['sub']}"
  except Exception:
      pass          # falls back to the IP bucket, silently
  ```

  The fallback itself is right, but catching bare `Exception` means a genuine
  fault in `decode_access_token` would silently degrade every authenticated
  caller to a shared per-IP rate-limit bucket with nothing in the log.
  `backend/routers/auth.py::logout` catches the narrow `Unauthorized` for the
  same operation, so the codebase already has the better idiom.
  `scheduler.py::stop` swallows any task exception on shutdown, also unlogged.
  Note these are invisible to the brief's grep, which only matches
  `except:`/`except: pass` on one line.
- Suggested fix: narrow `_caller_key` to `Unauthorized` and log at debug; log
  the exception in `stop` before continuing.

---

### [LOW] A blocking file read inside `async def`

- Where: `backend/seed.py::_seed_cities`
- Document: CLAUDE.md Law 11 — "No blocking calls inside `async` code."
- What the code does: `with CITIES_FILE.open(...)` then `list(csv.DictReader(...))`
  inside an `async def`. It is a one-shot CLI path, not the request path, so
  nothing stalls in practice — and `backend/clients/email.py` shows the
  codebase knows `asyncio.to_thread` for exactly this.
- Suggested fix: wrap the read in `asyncio.to_thread`.

---

### [LOW] A stale docstring claims DATABASE.md does not fix the amendment hash fields

- Where: `backend/services/hashing.py::amendment_content_hash`
- Document: DATABASE.md §4.9 now lists the fields explicitly.
- What the code does: the field list is **correct** and I verified it
  recomputes; only the docstring is stale — "the document does not fix its
  fields, so the build uses the same shape as every other one". Fix run 1's
  FIX-04 aligned the fields and left the comment.
- Suggested fix: replace the docstring with a plain citation of §4.9.

---

### [LOW] A setting's default is duplicated as a literal on a fallback path

- Where: `backend/jobs/scheduler.py::_label_retry_loop`
- Document: CLAUDE.md Law 8.
- What the code does: `interval = 600` when `label_retry_minutes` cannot be
  read — 600 seconds is the Demo 1 default of that setting, restated in code.
  The exception is logged, and a retry interval decides no democratic status,
  so this is the mildest form of the trap AUDIT §4.1 names.
- Suggested fix: name the constant and comment it as a last-resort fallback,
  or re-read the setting on the next tick instead of substituting a value.

---

### [LOW] User-facing error copy has a grammar slip

- Where: `backend/services/settings.py` (the `bad_setting_value` message)
- Document: CLAUDE.md §8 — "Plain language over jargon in all UI copy."
- Evidence: `{"error":"bad_setting_value","message":"The value for jury_size
  must be a int."}`
- Suggested fix: render the type name in words — "must be a whole number".

---

### [LOW] Every server-rendered page carries the same `<title>`

- Where: `frontend/src/app/layout.tsx`, `frontend/src/components/useDocumentTitle.ts`
- Document: CLAUDE.md §8 — accessibility, and "works on low-end devices and
  slow connections".
- What the code does: all 31 pages are client components; the per-page title
  is set in a `useEffect` after hydration, so the HTML as served titles every
  route "Direct Democracy Cali". The hook's own docstring cites WCAG 2.4.2 as
  its reason for existing, which is the standard this misses before JS runs.
- Evidence: all 25 routes returned 200 with `<title>Direct Democracy Cali</title>`.
- Suggested fix: keep the hook, and add a per-route `metadata` export (or a
  thin server component wrapper) so the title is right in the first response.

---

## Previously reported, still present

**Run 1's `HIGH` (ARCHITECTURE §2 layering) is marked fixed but only half
delivered.** Run 1 stated the requirement as "a router parses the request,
calls **one** service function, and shapes the response", and named
`backend/routers/solutions.py::get_solution` among the offenders. Fix run 1
fixed the repository/client/session half completely — I verified both greps
return nothing and `test_layering.py` enforces them — but the "one service
function / No logic" half was not addressed, and `get_solution` still makes
ten service calls and computes three thresholds inline. `briefs/demo-01-fix-1.md`
asked for "Every router calls **exactly one** service function", and
`TODO.md` line 184 marks `FIX-01` `[x]` with the narrower wording "every
router calls only services". Reported above as its own `MEDIUM`; recorded here
because the id is marked done and the narrowing was not called out.

Run 1's other items are genuinely resolved, and I re-verified each
independently rather than taking the fix entry's word:

- `[LOW]` HISTORY test count — corrected in Session 3's entry as FIX-05
  requires. My own run reports `203 passed, 2 deselected`.
- `[LOW]` `pyproject.toml` PEP 440 — `version = "0.1.0"`; an editable install
  with `[dev]` extras succeeded in this sandbox.
- `[LOW]` zero-item publish guard — resolved by documentation; DEMOCRACY §10.2
  now explains the guard is unreachable today and kept deliberately. I
  confirmed the behaviour: `open` on a zero-item `prepared` cycle is refused
  (`"A ballot opens from jury review."`) and `publish` is allowed.
- Ambiguity 1 (who schedules a job) — settled in ARCHITECTURE §2/§7; no router
  imports `backend.jobs`.
- Ambiguity 2 (Docker reachability) — `docker compose up -d` pulled and
  started both containers on the first try here, as in the fix run.
- Ambiguity 3 (PEP 440) — moot, fixed.

---

## Evidence log

Every command in order. Long outputs are trimmed at the point noted.

### Step 0 — pre-checks

```
$ echo $SANDBOX_NAME
ddc-demo-01-audit-2b

$ git switch demo/01 && git branch --show-current
demo/01

$ git status
On branch demo/01
Your branch is up to date with 'origin/demo/01'.
nothing to commit, working tree clean

$ git log --oneline -3
15d18ec demo-01 fix run 1 complete
210dfdc FIX-07: re-run the full evidence set after FIX-01..FIX-06
98d0253 FIX-06: scripted walkthrough for the three scenarios three accounts can't reach

$ ls audits/
demo-01-audit-1.md
    -> highest existing K is 1, so this report is audits/demo-01-audit-2.md

$ touch backend/AUDIT_WRITE_TEST && echo WRITABLE || echo READ-ONLY
WRITABLE
$ rm backend/AUDIT_WRITE_TEST
```

**The source tree is writable.** AUDIT.md §1's read-only mount is not
enforced in this sandbox (SANDBOX.md §6.5 already records this). I relied on
discipline; the closing `git diff main...HEAD --stat` is the proof.

```
$ docker compose version
Docker Compose version v5.5.0

$ docker compose --env-file .env -f infra/docker-compose.yml up -d
Image postgres:16 Pulled / Image redis:7 Pulled
Container ddc_postgres Started / Container ddc_redis Started

$ docker compose --env-file .env -f infra/docker-compose.yml ps
ddc_postgres   postgres:16   Up (health: starting)   0.0.0.0:5432->5432/tcp
ddc_redis      redis:7       Up (health: starting)   0.0.0.0:6379->6379/tcp

$ curl -sS $OLLAMA_BASE_URL/api/tags
{"models":[{"name":"nomic-embed-text:latest",...},{"name":"llama3.2:latest",...},...]}
```

No `.env` existed; I generated one from `.env.example` with a fresh
`JWT_SECRET` and `POSTGRES_PASSWORD` (never printed, never committed — it is
covered by `.gitignore`). `OLLAMA_BASE_URL` was unset in my shell; I used the
host LAN address SANDBOX.md §5 records (`192.168.1.165:11434`), which
answered with both required models, so the suite ran against the **real**
Ollama, not the mock.

### Migrations from empty, schema, seed

```
$ alembic upgrade foundation@head
INFO  [alembic.runtime.migration] Running upgrade  -> 25035d5b7ff5, Foundation initial schema — DATABASE.md §3.
$ alembic upgrade iteration@head
INFO  [alembic.runtime.migration] Running upgrade  -> b4b4da0b6e54, Iteration schema — Demo 1 (DATABASE.md §4).

$ python backend/scripts/verify_schema.py
[1] live database vs the ORM models              no drift
[2] scratch database (from migrations) vs models no drift
[3] scratch vs live, table by table              no drift — 37 tables identical
[4] the two halves (DATABASE.md §2)              15 Foundation, 22 Iteration, none in both
[5] every foreign key indexed (CLAUDE.md Law 4)  no problems
=== RESULT: NO DRIFT ===

$ python -m backend.seed --apply      # 590 writes
$ python -m backend.seed --dry-run
pending writes: 0
Nothing to do: every seed row is already in the database.
```

### Test suite (real Ollama available)

```
$ python -m pytest -q
203 passed, 2 deselected in 95.98s (0:01:35)
```

### The three greps the brief names

```
$ grep -rn "TODO\|FIXME" backend/ frontend/src/          -> (nothing, exit 1)
$ grep -rn "os.environ" backend/ | grep -v settings_env.py -> (nothing, exit 1)
$ grep -rn "except:\s*$\|except: pass\|except Exception: pass" backend/ -> (nothing, exit 1)
```

Widened, because the third pattern only matches one-line forms:

```
$ grep -rn -A1 "except.*:" backend/ --include=*.py | grep -B1 "pass$"
backend/middleware.py:104:        except Exception:
backend/middleware.py-105-            pass
backend/routers/auth.py:147:        except Unauthorized:      # narrow, intentional
backend/jobs/scheduler.py:37:     except (asyncio.CancelledError, Exception):
backend/services/settings.py:131: except json.JSONDecodeError:  # narrow, cache-miss path
$ grep -rn "except\s*:" backend/ ai/ --include=*.py       -> (nothing)
```

### Layering (fix run 1's own acceptance greps)

```
$ grep -rn "^from backend\.\(repositories\|clients\|jobs\)\|..." backend/routers/  -> (nothing)
$ grep -rn "session\.\(execute\|get\|add\|commit\|scalar\|flush\)\|select(" backend/routers/ -> (nothing)
$ grep -rn "session\.\(execute\|get\|scalar\)\|[^_a-z]select(" backend/services/   -> (nothing)
```

AST pass counting service calls per decorated handler (top rows):

```
router                 endpoint                            n  service calls
solutions.py           get_solution                       10  require_solution, detail_view,
                                                              rules.dominant_threshold, rules.ballot_threshold,
                                                              rules.on_track_for_ballot, ai_log.influence,
                                                              absorption_threshold_for, pairs_for_solution,
                                                              diff, comments_service.thread
amendments.py          propose_amendment                   4
amendments.py          list_amendments                     4
geo.py                 community                           4
umbrellas.py           umbrella_solutions                  4
admin.py               (6 endpoints)                       3
...
endpoints calling >1 service function: 37
```

### Three hand-derived `threshold()` cases (six, in fact)

```
 pct  min   den  hand  code      derivation
   5    3   100     3     3  OK  ceil(5/100*100)=5; min(5,3)=3; max(1,3)=3   [large community -> fixed minimum]
  25    3     4     1     1  OK  ceil(25/100*4)=1; min(1,3)=1; max(1,1)=1    [small denominator -> percentage]
  10    5     0     1     1  OK  ceil(0)=0; min(0,5)=0; max(1,0)=1           [the floor of one person]
   5    3    21     2     2  OK  ceil(1.05)=2; min(2,3)=2                    [rounding up mid-range]
   5    3    41     3     3  OK  ceil(2.05)=3; min(3,3)=3                    [exact tie with the minimum]
  10    5     1     1     1  OK  ceil(0.1)=1; min(1,5)=1                     [denominator of one]
ALL MATCH
```

Confirmed live too: with 7 active users the API reported
`dominant_threshold: 1` and `ballot_threshold: 1`, and on a solution with 6
supporters `absorption_threshold: 2` — matching `ceil(0.25*6)=2`, capped at 3.

### My own full cycle, seven accounts, through `curl`

Seven signups (a `.invalid` domain is refused by `EmailStr`, so I used
`example.com`), seven verifications from the console email log, seven logins:

```
$ curl -X POST /auth/signup ... x7
{"id":1,"message":"Account created. Check your email and use the confirmation link ..."} ... {"id":7,...}

$ grep '"email_console"' api.log   # the Demo 1 console backend
auditor1@example.com | Confirm your email address — Direct Democracy Cali | token Yhoq7P8zo_aG...
... (7 tokens)

$ curl -X POST /auth/verify-email ... x7
{"message":"Email confirmed. You can now post, vote and comment."}  x7

$ curl -X POST /auth/login ... x7
{"access_token":"eyJ...","token_type":"bearer","user_id":N,"email_verified":true}
    -> no refresh token in any body
```

Admin granted only from the machine, and logged publicly:

```
$ python backend/scripts/grant_admin.py auditor1@example.com --dry-run
WOULD GRANT administrator on auditor1@example.com (user 1)
$ python backend/scripts/grant_admin.py auditor1@example.com --apply
GRANT administrator on auditor1@example.com (user 1)

$ curl /admin/log
{"action":"grant_admin","administrator":"auditor1","old_value":{"is_admin":false},
 "new_value":{"is_admin":true},"reason":"Set from the machine by backend/scripts/grant_admin.py"}
```

Post with two solution texts, labelled by the real `llama3.2`:

```
$ curl -X POST /posts ...
{"id":1,"label_status":"pending","message":"Posted. It is being filed into an umbrella now ..."}

t=10s label_status=labeled

$ curl /posts/1
"umbrella_name": "Pedestrian Safety Near Schools", "confidence": 0.8,
"solution_ids": [1, 2],
"content_hash": "0f590e4b61366c7ac030acf100b876aece4e2ef71e7269b0a610b4bb8ebe47fc"
```

Votes — and the equal-weight check:

```
user2..user7 upvote solution 1 -> net_score 1..6, is_dominant true at 1,
                                  dominant_threshold 1, ballot_threshold 1, active_users 7

EQUAL WEIGHT: admin (user1) upvotes solution 2   -> net_score 4 -> 5   (+1, same as anyone)
admin votes AGAIN                                -> net_score 5        (idempotent, no double count)
user7 downvotes solution 2                       -> net_score 4, downvotes 1, still listed
```

Amendment proposed, backed, absorbed:

```
$ curl -X POST /solutions/1/amendments   {"id":1,"absorption_threshold":2}
user3 upvote -> net 1, absorbed false
user4 upvote -> net 2, absorbed true, new_version 2, status "absorbed"

$ curl /solutions/1
current_version : 2      net_score : 6   supporters : 6
v1 by auditor1  hash=60c58144b5e6951a  from_amendment=None
v2 by auditor2  hash=e8f0090799472cf2  from_amendment=1
```

The `ballot_min_dominant_days = 3` guard bites, producing a real zero-item
cycle (DEMOCRACY §10.2):

```
$ curl -X POST /admin/cycles/prepare
"state": "prepared", "items": [], "jury": null,
"considered": [{"solution_id":1,"conditions":{"dominant":true,"dominant_long_enough":false,
                "score_at_or_above_ballot_threshold":true,"newer_than_last_ballot_version":true}}, ...]
"zero_item_note": "No solution qualified. Publish this cycle when ready ..."

$ curl -X POST /admin/cycles/1/open
{"error":"cycle_wrong_state","message":"A ballot opens from jury review."}
$ curl -X POST /admin/cycles/1/publish
summary_hash: 639bc85edef80ab5ecb0c8cfac0f2012701721e534168affa23e5f6c3b76a5fe
"jury": "No jury was drawn", "empty_note": "No solutions reached the ballot this cycle."
```

Setting lowered with a reason, cycle 2 prepared with two items and a jury:

```
$ curl -X POST /admin/settings {"key":"ballot_min_dominant_days","value":"0","reason":"Audit run 2: ..."}
{"old_value":3,"new_value":0,...}

$ curl -X POST /admin/cycles/prepare
"state":"jury_review", items: solution 1 (v2, net 6), solution 2 (v1, net 4)
"jury": {"jury_id":1,"size_requested":3,"eligible_pool_size":5,"drawn":3}
```

Pool of 5 = 7 users minus the author/admin (user 1) and the amendment author
(user 2), exactly DEMOCRACY §8.1's exclusions. Jurors drawn: users 6, 7, 5.

Accept / decline / no-response, and the seat-ownership probes:

```
user6 accept -> {"juror_id":1,"status":"accepted",...}
user7 accept -> {"juror_id":2,"status":"accepted",...}
user5 decline -> {"declined":3,"replacement_drawn":true,...}   -> user4 gets seat 3
user4 never responds

SECURITY PROBE user3 holdback on seat 1 -> {"error":"not_your_seat",...}
SECURITY PROBE admin  holdback on seat 1 -> {"error":"not_your_seat",...}
SECURITY PROBE user3 accept seat 1       -> {"error":"not_your_seat",...}
```

Hold-backs and the majority rule:

```
juror1 + juror2 hold back item 2   (2 of 2 seated -> majority)
juror1 alone holds back item 1     (1 of 2 seated -> not a majority)

$ curl -X POST /admin/cycles/2/open
{"state":"open","jurors_drawn":4,"jurors_seated":2,"items_votable":1,"items_held_back":1}
```

Ballot votes, and the `CRITICAL` privacy trap:

```
$ curl -X PUT /cycles/2/ballot/2/vote   (the held-back item)
{"error":"item_held_back","message":"The jury held this one back, ..."}

users 1,2,3 vote yes; users 4,5 vote no

=== each caller's view of item 1 ===
user1 (yes)      -> my_vote=yes
user2 (yes)      -> my_vote=yes
user3 (yes)      -> my_vote=yes
user4 (no)       -> my_vote=no
user5 (no)       -> my_vote=no
user6 (no vote)  -> my_vote=None
user7 (no vote)  -> my_vote=None
anonymous        -> my_vote=None

$ curl /admin/users/2 -H "admin token"
"ballot_votes": "Not available to anyone but the voter. This endpoint never
                 returns them, by design (DEMOCRACY.md §13)."

occurrences of "voter_id" in /cycles/2, /cycles/2/ballot, /summaries/hashes,
/ai/actions, /admin/log, /feed:  0, 0, 0, 0, 0, 0
```

Close, publish, and the result rule:

```
$ curl -X POST /admin/cycles/2/close
{"results":[{"ballot_item_id":1,"yes":3,"no":2,"result":"passed"},
            {"ballot_item_id":2,"result":"held_back"}]}          # 3>2, turnout 5 >= quorum 1

$ curl -X POST /admin/cycles/2/publish
summary_hash: c9b46bbd08f75265d07126aa09298e0bd1bafa535a6dc7c07df6b2ef7434b7c0
header: "verification_mix": "5 voters: 5 unverified",
        "residency_note": "Residency is self-declared and unverified at this verification level.",
        "jury": "4 drawn, 2 seated"
held_back[0].jury_reasons: "Juror 1 of 2" (not_actionable), "Juror 2 of 2" (outside_governance_level)
```

### Hash round-trip, two ways, plus a tamper test

```
$ curl /summaries/city/408/2/verify
stored     : c9b46bbd08f75265d07126aa09298e0bd1bafa535a6dc7c07df6b2ef7434b7c0
recomputed : c9b46bbd08f75265d07126aa09298e0bd1bafa535a6dc7c07df6b2ef7434b7c0
match      : True

$ curl /summaries/city/408/2/json | (local recomputation)
sha256 of served bytes    : c9b46bbd08f75265d07126aa09298e0bd1bafa535a6dc7c07df6b2ef7434b7c0
sha256 of canonical JSON  : c9b46bbd08f75265d07126aa09298e0bd1bafa535a6dc7c07df6b2ef7434b7c0

TAMPER TEST: change yes 3 -> 4
after tampering           : 3b89f7ec717151022e1b4688a8c14e44e4ff7f878f181ca33311c1f5b1a5a523
```

The bytes as served are already canonical, so the instruction printed on the
page — "download the JSON from this page, run SHA-256 over the file" — is
literally true for a citizen with `sha256sum`.

Every hash type recomputed independently from raw database rows, using
DATABASE.md's documented field lists rather than the app's own helper:

```
posts.content_hash              match: True
post_solutions.content_hash     match: True
solution_versions.content_hash  match: True
amendments.content_hash         match: True
summaries.summary_hash cycle 1  match: True
summaries.summary_hash cycle 2  match: True
```

### Settings snapshot fidelity

```
cycle 2's published document  : ballot_min_dominant_days = 0   (the value in force at prepare)
prose paragraph               : "ballot_pct = 10.0; ballot_min = 5; ballot_min_dominant_days = 0"
the live settings page now    : 3

$ curl /settings/history?key=ballot_min_dominant_days
3 (audit restore) <- 0 (audit lower) <- 3 ("Demo 1 default", changed_by "the platform seed")
```

Append-only, with reasons, and the document permanently records what was
actually in force — Law 8 exactly as written.

### Reconciliation

```
$ python backend/scripts/reconcile.py --dry-run     (empty database, then populated, then after a deletion)
corrected           : False
net_score_drift     : []
dominance_changes   : []
orphan_communities  : []
hash_mismatches     : []
```

### Account rights

```
$ curl -X POST /me/export (user3); GET /me/export/1 (user3)  -> http 200
account: {"id":3,"email":"auditor3@example.com","real_name":"Audit Person 3", ...}
civic_record.iteration.your_ballot_votes:
  [{"cycle_id":2,"ballot_item_id":1,"your_choice":"yes","cast_at":"..."}]
note: "These are yours alone. No other endpoint on this platform returns a
       ballot vote with a voter attached to it, including to administrators."

$ curl /me/export/1 (user4, someone else's)
{"error":"export_not_yours","message":"That export belongs to someone else."} [403]
```

Anonymization, checked column by column against DATABASE §3.1:

```
BEFORE  email auditor7@example.com | password_hash $2b$12$NxH9... | real_name Audit Person 7
        display_name auditor7 | dob 1985-04-07 | county 43 | city 408
        last_active_at 2026-09-14 23:35:09 | deleted_at (null)

$ curl -X DELETE /me  {"password":"WrongPass99",...}  -> {"error":"bad_credentials",...}
$ curl -X DELETE /me  {"password":"AuditPass79","understand_this_cannot_be_undone":true}
{"message":"Your account is deleted. ..."}

AFTER   email deleted+7@invalid | password_hash ! | real_name (empty)
        display_name Former Community Member | dob 1900-01-01
        gender/political_party prefer_not_to_say | county 43 | city 408  (kept, per CLAUDE §6)
        last_active_at (null) | deleted_at 2026-09-14 23:37:11
        refresh_tokens: live = f      user_display_settings: reset to display_name
        untouched: verification_level, email_verified_at, is_admin, influence_score
```

Erases exactly what §3.1 lists and nothing it does not. The civic record
survives:

```
jury_holdbacks 1 | ballot_votes 0 (never voted) | votes 2 | jurors 1
deleted account login -> {"error":"bad_credentials",...}
published summary still verifies -> match: True
their published juror reason still reads "Juror 2 of 2"
reconcile after deletion -> hash_mismatches: []
```

### Auth security

```
$ curl -i -X POST /auth/login
set-cookie: refresh_token=...; HttpOnly; Max-Age=1209600; Path=/; SameSite=strict
body: {"access_token":"eyJ...","token_type":"bearer","user_id":6,"email_verified":true}
    -> the refresh token is never in a body

$ refresh #1 (rotates)                 -> http 200, new access token
$ reuse the OLD refresh token          -> {"error":"refresh_reused","message":"For your safety
                                           we signed you out of every device..."} [401]
$ the NEW token afterwards             -> {"error":"refresh_reused",...} [401]   (whole chain revoked)

$ /auth/me before logout               -> 200
$ POST /auth/logout                    -> {"message":"Signed out."}
$ /auth/me with the SAME access token  -> {"error":"token_revoked",...} [401]
$ a write with the same token          -> {"error":"token_revoked",...} [401]
```

Password policy and the 72-byte cap (CLAUDE Law 13 as amended):

```
short (7)        -> "Your password needs to be at least 8 characters long."
no uppercase     -> "Your password needs to contain a capital letter."
no digit         -> "Your password needs to contain a number."
valid            -> created
72 bytes exact   -> created
73 characters    -> "String should have at most 72 characters"
40 x 'é' (82 B)  -> "Your password needs to be no longer than 72 characters."   (refused, not truncated)

underage (dob 2015) -> {"error":"too_young","message":"You need to be at least 17 to join.
                        Nothing you entered has been saved."} [422]
users stored with that email: 0
```

Rate limiting (`RATE_LIMIT_WRITE_PER_MINUTE=30`):

```
36 writes as user3 -> 30 x 200, 6 x 429
retry-after: 60
{"error":"rate_limited","message":"You are sending changes faster than the platform
 accepts them. Try again in 60 seconds."}
GET /settings -> 200   (reads are not limited)
```

Secrets:

```
$ git ls-files | grep -i "\.env"     -> .env.example only
$ (secret-shaped strings in tracked files) -> none
occurrences in the request log of: a real password 0 | "password_hash" 0 | JWTs 0 | JWT_SECRET 0
```

Verification tokens do appear in the log — that is the `console` email
backend ARCHITECTURE §8.3 specifies for Demo 1, and is how the links are read.

Error hygiene:

```
/solutions/99999 -> {"error":"solution_not_found","message":"That solution does not exist."} [404]
/posts/99999     -> {"error":"post_not_found",...} [404]
admin action as non-admin -> {"error":"not_admin","message":"That is an administrator action."} [403]
write with no token       -> {"error":"not_signed_in","message":"Please sign in to do that."} [401]
bad setting value         -> {"error":"bad_setting_value",...} [422]
unknown setting key       -> {"error":"unknown_setting",...} [422]
traceback/SQL/driver text in any response: 0
```

### DEMOCRACY rules re-checked live

```
=== §7.2 condition 4: nothing returns to the ballot unchanged ===
after cycle 2: solution 1 passed (v2, last_ballot_version 2)
               solution 2 held_back (v1, last_ballot_version 1)
prepare cycle 3 -> 0 items; both show "newer_than_last_ballot_version": false

=== §10.1: one non-published cycle per community ===
second prepare -> {"error":"cycle_already_open","message":"Cycle 3 for San Jose (city)
                   is still prepared. Publish it before preparing the next one."} [409]

=== ALLOWED_TRANSITIONS in backend/services/cycles.py ===
workshop -> (prepared,) | prepared -> (jury_review, published) | jury_review -> (open,)
open -> (closed,) | closed -> (published,) | published -> ()          == DEMOCRACY §10.1

=== §6 comments: depth cap and the replying-to marker ===
ids 1..4 nest to depth 0,1,2,3; ids 5,6 stay at depth 3 and render
"replying to @auditor5" / "@auditor2"    (the CRITICAL above)

=== §5.4 similarity, real embeddings ===
two near-identical amendments -> score 0.982 >= 0.85, decision "pending",
"labelled": "Flagged as similar by AI. People decide."
ai_actions row: model ollama:nomic-embed-text, prompt_file "(embeddings: no prompt file)",
prompt_hash 000...0  (DATABASE §3.10 sentinel, exactly)

=== §9.4 with no SEARCH_API_KEY ===
POST /admin/umbrellas/2/recommend-references
{"error":"search_not_configured","message":"Reference recommendation needs a web search
 provider, and none is configured on this platform yet."} [503]

=== CLAUDE §5 label correction recorded ===
POST /posts/1/label/confirm -> "Thank you — 1 filing confirmed. That is recorded in the public AI log."
ai_actions.human_outcome: confirmed | at 2026-09-14T23:40:39Z
```

### Specification conformance

```
=== tables ===
FOUNDATION: documented 15  in code 15   in DATABASE.md but not in code: none   extra: none
ITERATION:  documented 22  in code 22   in DATABASE.md but not in code: none   extra: none

=== settings (DEMOCRACY §7.4) ===
settings present: 22 of 22 documented    missing: none   extra: none
values differing from the §7.4 Demo 1 default: none

=== endpoints ===
72 in /openapi.json; every endpoint in ARCHITECTURE §6 present;
5 undocumented (the LOW above); no PATCH or DELETE on /posts, correctly
```

### Frontend

```
$ npx tsc --noEmit        -> exit 0
$ npm run build           -> Compiled successfully; 25 routes
$ npm run start; curl each route

/ /signup /login /verify-email /forgot-password /reset-password /me
/legal/privacy /legal/terms /legal/cookies /settings /ai/actions /admin/log
/admin /feed /posts/new /ballot /jury /results /summaries/hashes
/umbrellas/2 /solutions/1 /posts/1 /cycles/2 /summaries/city/408/2
    -> all http 200; all <title> "Direct Democracy Cali"  (the LOW above)
```

Every route in ARCHITECTURE §9 exists.

**With images blocked:** the app contains no images at all — `grep "next/image"`
and `grep "<img"` over `frontend/src/` both return nothing, and headers are CSS
gradients per the director's note. Every page therefore renders identically with
images off; there is nothing to block.

**No business logic client-side** (Law 14):

```
$ grep -rn "Math.ceil|Math.max|Math.min|/ 100|threshold" frontend/src/
    -> only display of backend-computed values:
       "Dominant at a net score of {data.dominant_threshold}."
       "On track for the ballot at {data.ballot_threshold}."
$ grep -rniE "dominant_pct|ballot_pct|jury_size|quorum|0\.85|simple_majority" frontend/src/
    -> one false positive in globals.css (margin 0.85rem)
$ grep -rn "is_dominant =|qualified =|=== 'passed'|net_score >" frontend/src/  -> nothing
```

**Keyboard-only traversal (signup, post creation, voting, ballot):** no
browser is available in this sandbox, so I could not tab through the live
pages. I assessed it from the source instead, and every structural
precondition holds:

```
non-native click targets (<div|<span|<li with onClick)  : none
positive tabIndex (breaks tab order)                    : none
outline:none / outline-none (focus suppression)         : none
:focus-visible styling in globals.css                   : present
.skip-link:focus                                        : present
interactive elements: <button 40 | <Link 43 | <a 14 | <input 22
                      <select 11 | <textarea 6 | <form 14   (all native)
```

Every control is a native element, so it is focusable and operable by
keyboard by default, tab order follows document order, and focus is visibly
styled rather than suppressed. I am reporting this as "no barrier found in
the source", not as an observed tab-through.

**Accessibility markers:**

```
<label 39 | htmlFor 35 | inputs 22 + selects 11 + textareas 6 = 39   (one label each)
skip link 3 | sr-only 8 | aria-label 4 | aria-live 1 | aria-current 1 | role= 3
aria-describedby 0 | aria-invalid 0        (see NOTE 3)
errors surface through <Notice kind="bad"> which carries role="alert"
served HTML carries the nav and a "Skip to the main content" link before hydration
```

**PDF (§11.6):** the served PDF is compressed, so I re-rendered the same
document with `reportlab.rl_config.pageCompression = 0` in a scratch script
(the repository was not modified) and searched the bytes:

```
full summary hash on the page : True
published URL on the page     : True
page-number footer            : True
```

`backend/services/pdf.py::render` registers the footer via
`PageTemplate(..., onPage=footer)`, so it is drawn on every page.

### Documents (§4.6)

```
$ for D in CLAUDE.md PROJECT.md DEMOCRACY.md DATABASE.md ARCHITECTURE.md SANDBOX.md AUDIT.md;
    do git log --oneline main..demo/01 -- $D; done

CLAUDE.md       867d68f Post-audit document updates; fix brief demo-01-fix-1
PROJECT.md      (none)
DEMOCRACY.md    867d68f
DATABASE.md     867d68f
ARCHITECTURE.md 867d68f
SANDBOX.md      867d68f
AUDIT.md        (none)

$ git show --no-patch --format="author: %an <%ae>" 867d68f
author: Zack <zacksoares16@yahoo.com>
```

Every edit to a protected document came from the director's own commit, not
from a build or fix run — exactly what `briefs/demo-01-fix-1.md` describes. No
`HIGH` under §4.6.

### Final diff

`git diff main...HEAD --stat` compares the whole branch against `main`, so it
necessarily lists all 204 files the build and fix runs changed. The check that
actually proves the auditor touched nothing is against `15d18ec`, the branch
head as I found it:

```
$ git diff --cached --stat 15d18ec --
 HISTORY.md                |   31 ++
 audits/demo-01-audit-2.md | 1293 +++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 1324 insertions(+)

$ git diff --cached --name-only 15d18ec --
HISTORY.md
audits/demo-01-audit-2.md

$ git diff main...HEAD --stat | tail -1
 204 files changed, 29571 insertions(+), 4458 deletions(-)
    (203 of them the build's and fix run's; the 204th is this report)
```

Nothing outside `audits/` and my HISTORY.md paragraph was modified, which
matters because the write-protection pre-check above came back `WRITABLE`.
Untracked build artefacts I created and did not commit — `.env`, `.venv/`,
`node_modules/`, `frontend/.next/` — are all covered by `.gitignore`.

Working files I created outside the repository (the walkthrough's token and
response captures, the uncompressed PDF re-render) live in the session
scratchpad, not in the tree.

---

## Checks passed

Recorded so silence is not ambiguity. Each of these I ran or read myself.

**§4.1 Constitution**
- Ballot vote returned only to its voter — verified across seven callers plus
  anonymous, plus the admin endpoint, plus a `voter_id` sweep. **Clean.**
- Vote weight independent of everything but the voter's choice — the admin's
  upvote moved the score by exactly 1; `verification_level` is recorded on the
  vote row, reported only in aggregate (`group_by`), and appears in no
  arithmetic; `is_admin` appears in the vote path only as the jury-pool
  exclusion §8.1 requires. **Clean.**
- AI row written before its result is shown (Law 7) — `ai_log.record` precedes
  the `labels` row, `post_communities.umbrella_id`, the solutions and
  `label_status` in `labeling.py::label_post`.
- Ranking code carries plain English and a version (Law 9) — `rules.py`'s
  module docstring explains every rule in full, `RULES_VERSION = "rules-v1"`,
  plus `solutions-v0`, `comments-v0`, `ballot-order-v0`, `feed-v0`, each
  printed where it applies; the file states the A/B prohibition.
- `os.environ` outside `settings_env.py` — none, including in scripts.
- Sync database or HTTP inside `async def` — none in the request path; all
  sleeps are `asyncio.sleep`; only `async_sessionmaker` in app code; `smtplib`
  is wrapped in `asyncio.to_thread`. (One CLI-path exception, reported LOW.)
- `TODO`/`FIXME` in committed code — none.
- Router touching a repository, client, or session — none.

**§4.2 Specification conformance**
- All 37 tables exist in the documented halves, none in both, nothing extra,
  nothing missing; `verify_schema.py` reports no drift three ways.
- Every foreign key indexed (Law 4) — `verify_schema.py` check [5].
- Every ARCHITECTURE §6 endpoint exists with its method and path.
- `threshold()` matches six hand derivations including 0, 1, exact-tie and
  rounding boundaries.
- All 22 DEMOCRACY §7.4 settings seeded, readable, at their documented
  defaults, and each consulted by code outside `settings.py`.
- State transitions match §10.1 exactly; the zero-item path, the
  one-open-cycle rule and §7.2 condition 4 all refuse what they must.
- Ballot order (umbrella A–Z, snapshot score desc, id asc) and the §10.4
  result rule both confirmed live.
- Hold-back majority rule confirmed in both directions: 2 of 2 seated took
  effect, 1 of 2 did not.
- Jury exclusions (§8.1) confirmed: pool of 5 excluded the author and the
  amendment author; admins excluded in `users_repo`.
- Decline draws a replacement; no-response is not seated and not replaced
  (§8.2) — `jurors_seated: 2` with a third drawn and silent.

**§4.3 Security**
- bcrypt cost 12 (`$2b$12$`); raw passwords never stored.
- Refresh tokens stored hashed, delivered only in an `httpOnly`
  `SameSite=strict` cookie, rotated, with whole-chain revocation on reuse.
- Access-token `jti` blacklisted on logout, for reads and writes.
- Write endpoints behind `verified_user` and the rate limiter; unverified
  accounts refused; 30/minute enforced with `Retry-After`.
- Password policy including the 72-byte cap refused rather than truncated;
  age gate stores nothing.
- No secret in any committed file, log line, or error response; no stack
  traces to the client.
- Anonymization erases every column §3.1 lists and nothing it does not.
- `mailto:` payload carries only office, test address, subject, the summary
  URL and hash, and fixed text — no user data.
- Juror seat ownership enforced against ordinary users *and* the admin.
- Export readable only by its owner (403 otherwise).

**§4.4 Evidence**
- Test suite, `verify_schema.py`, `reconcile.py --dry-run`, seed dry-run
  (0 pending), full cycle walkthrough, hash round-trip, three (six) hand
  derivations — all run by me from an empty database, all pasted above.
- Fix run 1's acceptance claims re-verified independently: `203 passed`, both
  layering greps empty, `comments.content_hash` covering `parent_id`, and an
  editable install succeeding (the one claim the fix entry declined to paste).

**§4.5 Frontend**
- Every ARCHITECTURE §9 route exists, builds, and returns 200.
- Every page works with images off — there are no images.
- Keyboard traversal: no non-native click target, no positive `tabIndex`, no
  suppressed focus outline, `:focus-visible` styled, skip link present —
  assessed from source, not tabbed through (no browser in this sandbox).
- TypeScript compiles clean.
- No thresholds, eligibility, or status computed client-side.
- AI disclosure present where DEMOCRACY requires: the umbrella action-list
  sentence (§9.5), per-report label status (§3.3 item 2), and the 0%
  influence label with its honest caveat about outside AI.

**§4.6 Documents**
- No protected document was edited by a build or fix run.
- TODO.md's completed ids check out apart from `FIX-01` (reported above).
- The fix run's HISTORY entry records its decisions and even flags the
  `redraw` no-op it declined to fix — which is how I found the `HIGH`.

---

## Document ambiguities

For the director. I did not resolve these.

1. **Are minority hold-back reasons meant to be published?** DEMOCRACY §8.3
   says "Each juror's category and reason are recorded and all are published",
   but in context that sentence follows the majority rule, and §11.2 item 3
   describes only a "Held back" section. §8.4 says previous hold-back reasons
   are shown on the solution page, which suggests they should be visible
   somewhere. As built, a reason that does not reach a majority is published
   nowhere — while the API tells the juror who wrote it that it will be. Either
   reading is defensible; the promise in the response text is not, under the
   current behaviour.

2. **Does "drawn" in the summary header mean `jury_size` or everyone ever
   drawn?** DEMOCRACY §11.2 item 1 gives the example "3 drawn, 2 seated",
   which reads as the requested size. With a decline and a replacement my
   cycle printed "4 drawn, 2 seated" — literally true, and arguably more
   informative, but it no longer matches the example and a reader may wonder
   why four were drawn for a jury of three. Worth one clarifying sentence
   either way.

3. **Is `comment_max_depth` a count of levels or the highest depth value?**
   The code stores depth 0-based, so `comment_max_depth = 3` yields four
   visible levels (0–3). DEMOCRACY §6 says replies "nest to
   `comment_max_depth`" but then says deeper replies "attach to the depth-3
   comment" — which is exactly what the code does. The two halves of the
   sentence imply different counts; the code follows the second. No change
   needed if the second is what was meant.

4. **How far should form-field accessibility go in Demo 1?** Errors are
   announced (`role="alert"`) and every control has a label, but no field
   carries `aria-invalid` or `aria-describedby` tying it to its message. CLAUDE
   §8 requires accessibility without naming a conformance level. If WCAG 2.1 AA
   is the target, this is a gap; if "labelled, announced, keyboard-reachable"
   is the Demo 1 bar, it is met. Worth naming the bar.
