# Audit — demo-01, run 4, 2026-09-15

## Summary

A full pass over `demo/01` after fix run 3, from an empty database, with the
real Ollama reachable and the real `infra/docker-compose.yml`. Fix run 3's diff
reached past the six files its findings named (into `repositories/`,
`services/comments.py`, `services/umbrellas.py`), so under AUDIT.md §2 and
`briefs/demo-01-fix-3.md`'s own instruction this is a full audit rather than a
short re-audit.

All six of audit run 3's findings are fixed, five of them completely. Every
claim in fix run 3's HISTORY entry that I could re-run reproduced exactly:
218 passed / 2 deselected, `-m live` 2 passed, `verify_schema.py` no drift,
seed dry-run zero pending writes, all three required greps empty, `npm audit`
zero vulnerabilities. Both always-`CRITICAL` traps are clean, and I reproduced
that empirically rather than by reading: three different accounts and an
administrator each read the same open ballot and each saw only their own vote,
and nothing anywhere weights a vote by verification level or admin status.
The machinery underneath is in good shape — the full civic cycle ran end to
end on my own database, the summary hash round-tripped three independent ways,
the jury pool excluded exactly the right people, and reconciliation found no
drift, no orphans and no hash mismatch across every hashed row.

One `CRITICAL` stands. A published summary document freezes the author's
display name — their **real name** when that is their chosen display mode —
into immutable, hashed, permanently public JSON. Deleting the account erases
the name everywhere else, exactly as CLAUDE §6 promises, but cannot reach the
summary. I reproduced this end to end: after `DELETE /me`, the workshop
correctly reads "Former Community Member" while the published document still
reads "Patricia Quintero-Alvarez", and still verifies. This is the same
mechanism as audit run 2's `CRITICAL` (a display name frozen into a permanent
hash), in a different place.

Counts: **CRITICAL 1 · HIGH 0 · MEDIUM 6 · LOW 3 · NOTE 3.**

Verdict: **FIX REQUIRED.**

---

## Findings

### [CRITICAL] A published summary permanently contains a deleted user's real name, which account deletion cannot erase

- Where: `backend/services/summaries.py::build_data`
  (`author_display_at_snapshot`), read back through
  `backend/services/summaries.py::generate`
- Document: CLAUDE.md §6 — "All personal identifying information — name,
  email, password, date of birth, gender, political party — is permanently
  erased. Posts, solutions, comments, votes, and AI-correction data are
  anonymized and attributed to 'Former Community Member.'" DEMOCRACY.md §11.1
  — "Nothing personal in it." CLAUDE.md Law 6 — a `summary_hash` is
  permanent.
- What the document requires: deletion removes the identity from the civic
  record and leaves the record. Nothing personal survives in a published
  document.
- What the code does: `build_data` resolves each ballot item's author through
  the render-time display rule **once**, at publish, and writes the resulting
  string into `summaries.data` as `author_display_at_snapshot`. That JSON is
  then hashed and is immutable (DATABASE.md §4.18). When the author's
  `public_name_mode` is `real_name`, the string written is their real name.
  Deleting the account afterwards changes every live page but cannot change
  the document, because changing it would break the hash. There is no
  regeneration or redaction path: `generate()` returns the stored row if one
  exists.
- Evidence: one member signed up as `Patricia Quintero-Alvarez`, set
  `public_name_mode = real_name`, authored a solution that reached a published
  ballot, then deleted their account.

  ```
  ----- PATCH /me/display -> 200
  {"public_name_mode": "real_name", "shown_as": "Patricia Quintero-Alvarez"}

  ----- DELETE /me -> 200
  {"message":"Your account is deleted. Your name, email, password, date of birth,
   gender and political party are erased. What you wrote stays in the civic
   record as Former Community Member."}
  ```

  The users row is correctly and completely anonymized:

  ```
  id              | 9
  email           | deleted+9@invalid
  real_name       |
  display_name    | Former Community Member
  date_of_birth   | 1900-01-01
  gender          | prefer_not_to_say
  political_party | prefer_not_to_say
  county_id       | 43          <- kept, correctly (CLAUDE §6)
  city_id         | 408         <- kept, correctly
  last_active_at  |
  deleted_at      | 2026-09-15 18:41:06.001912+00
  password_hash   | !
  ```

  The live workshop obeys the rule:

  ```
  === workshop solution page after deletion ===
  author: 'Former Community Member'
  versions written_by: ['Former Community Member']
  ```

  The published document does not, and cannot:

  ```
  === the PUBLISHED, HASHED summary after deletion ===
  real name still in published summary: True
    results[].author_display_at_snapshot = 'Patricia Quintero-Alvarez'
  summary still verifies (hash unchanged): True

  === the downloadable canonical JSON ===
  1          <- occurrences of the real name in /summaries/city/408/2/json
  ```

  This is not limited to `real_name` mode: any non-anonymous display string is
  frozen the same way, and `held_back` entries carry the same field.
- Note for the director: DEMOCRACY.md §11.2 item 2 does say "author display as
  of snapshot", so the code follows *that* sentence. But it contradicts
  DEMOCRACY.md §11.1 ("Nothing personal in it") in the same section and
  CLAUDE.md §6, and CLAUDE.md's own rule is that when it conflicts with
  another document, CLAUDE.md wins and the other document is corrected. Also
  listed under Document ambiguities.
- Suggested fix: store the author's `user_id` (or nothing) in the canonical
  JSON and resolve the display at read time through the same rule every other
  page uses, so deletion reaches the summary without touching the hash.

---

### [MEDIUM] Over-cap comment replies attach to the comment they answer, so the rendered reply tree nests without bound

- Where: `backend/services/comments.py::create`, rendered by
  `backend/services/comments.py::thread`
- Document: DEMOCRACY.md §6 — "A reply to a depth-3 comment is stored at depth
  3 **under the same parent**, with `reply_to_comment_id` pointing at the
  comment it answered."
- What the document requires: at the cap, the new comment takes the *same
  parent* as the comment it answers, so the parent chain — and therefore the
  rendered nesting — stops growing at four visible levels (0–3).
- What the code does: it sets `parent_id` to the comment being answered and
  only copies its `depth`:

  ```python
  if parent.depth >= max_depth:
      reply_to_comment_id = parent.id
      while parent.parent_id is not None and parent.depth > max_depth:
          ...
      depth = parent.depth
      parent_id = parent.id      # <- the answered comment, not its parent
  ```

  The `while` loop cannot run in normal operation: `depth` is never set above
  `max_depth`, so `parent.depth > max_depth` is only reachable if the setting
  is later *lowered*. The `depth` column is capped, but the parent chain is
  not, and `thread()` builds the reply tree by recursing on `parent_id`.
- Evidence: a chain of replies, each answering the previous one.

  ```
     level 0 | depth field 0 | id 1 | depth 0 comment from the audit
         level 1 | depth field 1 | id 2 | depth 1 comment from the audit
             level 2 | depth field 2 | id 3 | depth 2 comment from the audit
                 level 3 | depth field 3 | id 4 | depth 3 comment from the audit
                     level 4 | depth field 3 | id 5 | replying to @Di497215: ...
                         level 5 | depth field 3 | id 6 | replying to @Cy497215: ...
                             level 6 | depth field 3 | id 7 | replying to @Di497215: ...
                                 level 7 | depth field 3 | id 8 | replying to @Cy497215: ...
                                     level 8 | depth field 3 | id 9 | replying to @Di497215: ...

    DEEPEST RENDERED NESTING LEVEL: 8  (DEMOCRACY §6 allows four visible levels, 0-3)
  ```

  Stored rows confirm `parent_id` follows the chain while `depth` stays 3:

  ```
   id | parent_id | reply_to_comment_id | depth
    4 |         3 |                     |     3
    5 |         4 |                   4 |     3
  ```

  This is a code-vs-current-document mismatch introduced by a document update:
  on `main`, DEMOCRACY §6 read "Deeper replies attach to the depth-3 comment",
  which is exactly what the code does. The director's post-audit-2 rewrite
  changed it to "under the same parent"; fix run 2's FIX-18 concluded "no code
  change expected" on the strength of the depth half of the sentence and the
  parent half was never revisited.
- Mitigation that limits the severity: the shipped UI indents by
  `comment.depth * 1rem`, which is capped at 3rem, so a reader of the web app
  does not see runaway indentation today. The unbounded nesting is real in the
  API response (`replies` within `replies`) — which Law 14 says must stand on
  its own — and in the DOM a screen reader traverses.
- Suggested fix: set `parent_id = parent.parent_id` when re-attaching at the
  cap, keeping `reply_to_comment_id = parent.id`; the "replying to @display"
  rendering already works and needs no change.

---

### [MEDIUM] Three account write endpoints require a signed-in user, not a verified one

- Where: `backend/routers/me.py::set_display` (`PATCH /me/display`),
  `::request_export` (`POST /me/export`), `::delete_me` (`DELETE /me`)
- Document: ARCHITECTURE.md §4 — "The account can log in but every write
  endpoint returns 403 `email_not_verified` until the link is used."
  AUDIT.md §4.3 — "Every write endpoint behind `verified_user` and the rate
  limiter."
- What the document requires: every write endpoint depends on `VerifiedUser`.
- What the code does: all three take `user: CurrentUser`, which requires only
  a valid JWT. Verified live — an account that had signed up but never used
  its confirmation link:

  ```
  ----- PATCH /me/display -> 200 (unverified account)
  {"public_name_mode": "real_name", "shown_as": "Patricia Quintero-Alvarez"}
  ```

  while every civic write on the same account is correctly refused:

  ```
  POST /posts                          -> 403 {"error":"email_not_verified", ...}
  PUT /votes                           -> 403 {"error":"email_not_verified", ...}
  POST /posts/1/label/confirm          -> 403 {"error":"email_not_verified", ...}
  POST /posts/1/label/correct          -> 403 {"error":"email_not_verified", ...}
  POST /comments                       -> 403 {"error":"email_not_verified", ...}
  POST /umbrellas/2/solutions          -> 403 {"error":"email_not_verified", ...}
  POST /solutions/1/amendments         -> 403 {"error":"email_not_verified", ...}
  ```
- Why MEDIUM and not HIGH: I could not construct a consequence. All three act
  only on the caller's own account, and an unverified account can author no
  civic content, so there is nothing for them to reach. The gap is against the
  document's blanket wording, not against any outcome.
- Note on the pattern: audit run 3 reported this same class against
  `posts.py::confirm_label` and `::correct_label`; fix run 3 changed exactly
  those two, which is what FIX-23 named, and these three siblings were never
  looked for. This is the third audit in a row where a fix applied only to the
  named locations left same-shaped instances elsewhere.
- Suggested fix: change all three to `VerifiedUser`, or state an explicit
  exemption in ARCHITECTURE §4 for endpoints that act only on the caller's own
  account — the second may be the better answer, since letting an unverified
  person delete their own account is defensible.

---

### [MEDIUM] FIX-22 is marked done, but the umbrella page never shows the "AI is looking for references…" indicator the brief and the code's own docstring promise

- Where: `backend/services/references.py::_recommend_pending` (docstring),
  `frontend/src/app/umbrellas/[id]/PageClient.tsx` (absent), `TODO.md`
  FIX-22
- Document: `briefs/demo-01-fix-3.md` FIX-22 — "The umbrella page shows 'AI is
  looking for references…' until the `ai_actions` row exists." AUDIT.md §4.6 —
  TODO.md marks done only what is actually done.
- What the document requires: the backend returns 202 and schedules the job
  (done, verified), **and** the umbrella page displays a pending indicator.
- What the code does: the backend half is correct and the flag is exposed on
  both `GET /umbrellas/{id}` and `GET /umbrellas/{id}/references`:

  ```
  === does the API expose the 'recommending' flag? ===
  backend/services/references.py:311:  "recommending": await _recommend_pending(...)
  backend/services/references.py:331:  "recommending": await _recommend_pending(...)

  === does the frontend render it? ===
  (exit 1 — nothing found = not rendered)
  ```

  Fix run 3's diff touched no frontend file at all. The service docstring
  nevertheless asserts the behaviour as fact: "the umbrella page shows 'AI is
  looking for references…' for exactly that stretch". TODO.md marks FIX-22
  `[x]` with wording narrowed to the API ("the umbrella references listing
  reports `recommending`"), which is the narrowing `briefs/demo-01-fix-3.md`
  explicitly forbids: "Mark an item done with less than it says … the item is
  `[~]` and the residue is named."
- Suggested fix: render the flag on the umbrella page, or mark FIX-22 `[~]`
  and correct the docstring to describe what the code actually provides.

---

### [MEDIUM] Blocking filesystem calls inside `async def` in the export service

- Where: `backend/services/export.py::build_export` (`EXPORT_DIR.mkdir`,
  `path.write_text`), `backend/services/export.py::expire_exports`
  (`path.unlink`)
- Document: CLAUDE.md Law 11 — "Every IO operation is `async`. … No blocking
  calls inside `async` code."
- What the code does:

  ```python
  async def build_export(session: AsyncSession, export_id: int) -> Path:
      ...
      EXPORT_DIR.mkdir(parents=True, exist_ok=True)
      path = EXPORT_DIR / f"export-{row.user_id}-{row.id}.json"
      path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
  ```

  Both run on the main event loop — the job is an `asyncio` task spawned by
  `runner.spawn_after_commit` — so a large export stalls every other request
  for the duration of the write.
- Evidence: the only two `to_thread` uses in the backend are elsewhere, which
  shows the codebase already knows the remedy:

  ```
  === to_thread usage (the correct escape hatch) ===
  backend/seed.py:232:    rows = await asyncio.to_thread(_read_cities_csv)
  backend/clients/email.py:49:    await asyncio.to_thread(_send_smtp, message)
  ```

  Audit run 2 reported this same class as a LOW against
  `backend/seed.py::_seed_cities`; FIX-16 fixed that one location only.
- Suggested fix: wrap the write, the `mkdir` and the `unlink` in
  `asyncio.to_thread`, as `seed.py` and `email.py` already do.

---

### [MEDIUM] Every hash column is `VARCHAR(64)`, where DATABASE §1 specifies `CHAR(64)`

- Where: `backend/models.py` (all hash columns), applied by
  `backend/alembic/versions/25035d5b7ff5_foundation_initial_schema.py` and
  `...b4b4da0b6e54_iteration_schema_demo_1.py`
- Document: DATABASE.md §1 — "**Hashes** are `CHAR(64)` hex SHA-256." §3.6
  likewise specifies `fips char(5)`, `abbreviation char(2)`.
- What the code does: every one is `character varying` with a 64 limit:

  ```
       table_name      | column_name  |     data_type     | character_maximum_length
   ai_actions          | input_hash   | character varying |                       64
   ai_actions          | prompt_hash  | character varying |                       64
   amendments          | content_hash | character varying |                       64
   comments            | content_hash | character varying |                       64
   email_verifications | token_hash   | character varying |                       64
   juries              | random_bytes | character varying |                       64
   password_resets     | token_hash   | character varying |                       64
   post_solutions      | content_hash | character varying |                       64
   posts               | content_hash | character varying |                       64
   refresh_tokens      | token_hash   | character varying |                       64
   solution_versions   | content_hash | character varying |                       64
   states              | abbreviation | character varying |                        2
   summaries           | summary_hash | character varying |                       64
   terms_acceptances   | ip_hash      | character varying |                       64
   cities              | fips         | character varying |                        7
   counties            | fips         | character varying |                        5
  ```
- No behaviour changes: the length cap is identical and every hash written is
  exactly 64 characters, so nothing is truncated and nothing recomputes
  differently. `verify_schema.py` cannot catch this because it compares the
  database against the ORM and the migrations — all three agree; only the
  document differs.
- Suggested fix: most likely correct DATABASE §1 to say `VARCHAR(64)`, since
  `CHAR` would space-pad and is the worse choice for a fixed-width hex string;
  otherwise change the models. Also listed under Document ambiguities.

---

### [MEDIUM] The export file lifetime is a build decision that appears in no document and in no HISTORY entry

- Where: `backend/services/export.py::EXPORT_LIFETIME_HOURS = 48`
- Document: AUDIT.md §4.6 — "The HISTORY entry records every decision the build
  made that the documents did not pre-resolve. The auditor lists decisions it
  can see in the code that are not in the entry." DATABASE.md §3.11 names the
  `expires_at` column but fixes no value; ARCHITECTURE.md §7 says only that
  `expire_exports` runs "hourly".
- What the code does: chooses 48 hours, which decides how long a citizen has
  to collect the personal data they asked for — a user-rights figure under
  CLAUDE §6.
- Evidence:

  ```
  === HISTORY mentions of export lifetime / 48 hours ===
  (none above = not recorded)
  ```
- Suggested fix: record the choice and its reasoning in HISTORY, and consider
  whether a user-rights window belongs in DATABASE §3.11 or in the settings
  table.

---

### [LOW] The password-length message says "characters" where the rule is bytes

- Where: `backend/services/security.py::validate_password`
- Document: CLAUDE.md Law 13 — "maximum 72 bytes (bcrypt's limit — refused,
  never silently truncated)." CLAUDE.md §8 — plain language, never assume the
  user is technical.
- What the code does: the *check* is correctly byte-based
  (`len(password.encode("utf-8")) > MAX_PASSWORD_BYTES`), but the message it
  produces says characters. A 43-character passphrase using accented letters
  is 83 bytes, and is refused with:

  ```
  {"error":"weak_password",
   "message":"Your password needs to be no longer than 72 characters."}
  ```

  The person counted 43 characters and is told the limit is 72.
- Suggested fix: word the message in terms the person can act on, e.g. "that
  password is too long for the encryption we use — some letters count as more
  than one character."

---

### [LOW] The jury size is hardcoded in the landing page's copy instead of read from the settings table

- Where: `frontend/src/app/page.tsx` — "Three neighbours check it over" /
  "three residents drawn at random look at what qualified"
- Document: CLAUDE.md Law 8 — "Every number that decides a democratic status —
  dominant, absorbed, qualified, active user, **jury size**, ballot window —
  lives in the settings table, is displayed on a public page, and is printed
  in every summary document it produced. Never a constant in code."
- What the code does: the page is fully static and fetches nothing; the
  applied value still comes from `jury_size` everywhere it matters, so no
  outcome is affected. But if the community votes `jury_size` to 5, the
  platform's own front door keeps saying three.
- Suggested fix: read `jury_size` from `GET /settings` for that sentence, or
  word it without a number.

---

### [LOW] The two export jobs do not log a start, an end, or a job id, unlike every other job

- Where: `backend/jobs/exports.py::build_export_task`,
  `::expire_exports_task`
- Document: ARCHITECTURE.md §7 — "Each job logs start, end, counts, and
  failures with a job id."
- What the code does: `build_export_task` logs only on failure and has no job
  id; `expire_exports_task` logs a count at the end but no start and no job
  id. `labeling.py`, `references.py` and `similarity.py` all follow the
  documented shape (`job_id = uuid.uuid4().hex[:8]`, `job_start`, `job_end`).
- Suggested fix: give both the same `job_id` / `job_start` / `job_end` shape
  the other three jobs use.

---

## Previously reported, still present

Fix run 3 resolved five of audit run 3's six findings completely, and I
re-verified each independently rather than reading the fix run's evidence:

- **HIGH, seven unpaginated list endpoints** — resolved. All seven paginate
  and refuse `limit > 100` with 422; the five ARCHITECTURE §6 exemptions
  still return whole (see the evidence log).
- **MEDIUM, `recommend_references` should be a background job** — the backend
  half is resolved (202 `{"status":"pending"}`, `spawn_after_commit`); the UI
  half is **not**, and is reported above as its own MEDIUM.
- **MEDIUM, two write endpoints take a signed-in rather than a verified
  user** — the two endpoints named (`posts.py::confirm_label`,
  `::correct_label`) are fixed and I reproduced both 403s. Three
  same-shaped endpoints in `backend/routers/me.py` were never named and are
  reported above.
- **MEDIUM, one service function per endpoint** — resolved, including the four
  further offenders the stricter test found. `test_layering.py` now counts
  `(module, function)` pairs and passes across the whole codebase.
- **LOW, relative summary URL in `mailto:`** — resolved; the body, the PDF
  footer on every page, and `verify.hash_list_url` are all absolute via
  `PUBLIC_BASE_URL`.
- **LOW, `build_export` missing from ARCHITECTURE §7** — resolved; the job
  table and the code agree.

Earlier audits' items I re-checked and found still fixed: audit run 2's
`CRITICAL` (no display name is stored in comment text — confirmed at the row
level), its `HIGH` (a redraw supersedes rather than deletes — `juries` carries
`superseded_at`, `redrawn_reason` and a partial unique index), minority
hold-backs published (reproduced in my own cycle), the labeler recording
invented communities (reproduced live — it invented `city:1` and recorded it),
`npm audit` clean, and audit run 1's original layering `HIGH`.

One class recurred in a new place rather than at the reported location:
audit run 2's LOW on a blocking file read inside `async def` was fixed in
`seed.py` only, and the same pattern remains in `export.py` (reported above).

---

## Evidence log

Every command in order. Output trimmed only where marked.

### Step 0 — pre-checks

```
$ echo $SANDBOX_NAME ; hostname
ddc-demo-01-audit-4
ddc-demo-01-audit-4

$ git switch demo/01 && git branch --show-current
Switched to a new branch 'demo/01'
branch 'demo/01' set up to track 'origin/demo/01'.
demo/01

$ git status
On branch demo/01
Your branch is up to date with 'origin/demo/01'.
nothing to commit, working tree clean

$ ls audits/
demo-01-audit-1.md  demo-01-audit-2.md  demo-01-audit-3.md
  -> this report is audits/demo-01-audit-4.md (K = 4)

$ touch backend/AUDIT_WRITE_TEST && echo WRITABLE || echo READ-ONLY
WRITABLE
$ rm backend/AUDIT_WRITE_TEST && git status --porcelain
  (empty)
```

**The source tree is writable in this audit sandbox**, as SANDBOX.md §6.5
records. I deleted the probe immediately and relied on my own discipline; the
final `git diff main...HEAD --stat` at the end of this log is the proof.

```
$ docker compose --env-file .env -f infra/docker-compose.yml up -d
 Image postgres:16 Pulled
 Container ddc_postgres Started
 Container ddc_redis Started
```

The real compose file works in this sandbox, as it did for fix run 3. There is
no `.env` in the repository (correctly — it is gitignored), so I generated one
from `.env.example` with fresh secrets, as SANDBOX.md §8 prescribes.

```
$ curl -sS $OLLAMA_BASE_URL/api/tags
{"models":[{"name":"nomic-embed-text:latest",...},{"name":"llama3.2:latest",...}]}
```

Ollama is reachable with both models named in `.env`, so everything below ran
against the real model, not a mock.

### Migrations from an empty database

```
$ alembic upgrade foundation@head
INFO  [alembic.runtime.migration] Running upgrade  -> 25035d5b7ff5, Foundation initial schema — DATABASE.md §3.
$ alembic upgrade iteration@head
INFO  [alembic.runtime.migration] Running upgrade  -> b4b4da0b6e54, Iteration schema — Demo 1 (DATABASE.md §4).
```

### `backend/scripts/verify_schema.py`

```
=== verify_schema.py ===
live database:    localhost:5432/directdemocracy
scratch database: ddc_schema_scratch (built from both migration chains)

[1] live database vs the ORM models
    no drift
[2] scratch database (from migrations) vs the ORM models
    no drift
[3] scratch vs live, table by table
    no drift — 37 tables identical
[4] the two halves (DATABASE.md §2)
    no problems — 15 Foundation tables, 22 Iteration tables, none in both
[5] every foreign key indexed (CLAUDE.md Law 4)
    no problems

=== RESULT: NO DRIFT ===
```

15 Foundation + 22 Iteration is exactly DATABASE §2's two lists.

### Seed runner

```
$ python -m backend.seed --dry-run     (empty database)
pending writes: 590

$ python -m backend.seed --apply
$ python -m backend.seed --dry-run
[settings (DEMOCRACY.md §7.4)]   to write: 0   already present: 22
[geography: state]               to write: 0   already present: 1
[geography: counties]            to write: 0   already present: 58
[geography: cities]              to write: 0   already present: 483
[legal: terms version]           to write: 0   already present: 1
[officials directory]            to write: 0   already present: 5
[main categories]                to write: 0   already present: 10
[umbrellas (Iteration)]          to write: 0   already present: 10
---
pending writes: 0
Nothing to do: every seed row is already in the database.
```

22 settings is exactly the count of keys in DEMOCRACY §7.4.

### Full test suite

```
$ python -m pytest -q
........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [ 99%]
..                                                                       [100%]
218 passed, 2 deselected in 113.98s (0:01:53)

$ python -m pytest -m live -q
..                                                                       [100%]
2 passed, 218 deselected in 2.83s
```

Both match fix run 3's claim exactly (218 + 2 live).

### The three required greps

```
$ grep -rn "TODO\|FIXME" backend/ frontend/src/
(exit 1 — nothing)

$ grep -rn "os.environ" backend/ | grep -v settings_env.py
(exit 1 — nothing)

$ grep -rn "except:\s*$\|except: pass\|except Exception: pass" backend/
(exit 1 — nothing)
```

I widened each of these. `getenv`/`dotenv` appear nowhere outside
`settings_env.py`. Of the eighteen `except Exception` handlers, every one
logs; the only three `pass` bodies are a JSON cache-decode fallback
(`services/settings.py`), an already-invalid token during logout
(`services/auth.py`), and `asyncio.CancelledError` on shutdown
(`jobs/scheduler.py`) — all narrow and all correct under Law 12.

### `backend/scripts/reconcile.py --dry-run`

On the populated database, after the whole walkthrough:

```
corrected         : False
net_score_drift   : []
dominance_changes : []
orphan_communities: []
hash_mismatches   : []

rows in play: {'admin_actions': 16, 'ai_actions': 1, 'amendments': 1,
 'ballot_items': 3, 'ballot_votes': 8, 'comments': 9, 'cycles': 4,
 'juries': 2, 'jurors': 6, 'jury_holdbacks': 3, 'labels': 2, 'posts': 2,
 'post_solutions': 3, 'solutions': 3, 'solution_versions': 4,
 'summaries': 3, 'users': 9, 'votes': 13, ...}
```

Every `content_hash` and `summary_hash` in the database recomputes to its
stored value (DATABASE §7 item 4).

### The two always-`CRITICAL` traps, reproduced rather than read

**A ballot vote returned to anyone but its voter.** Three accounts and an
administrator each read the same open ballot:

```
----- GET /cycles/1/ballot (voter1)  -> "my_vote": "yes"
----- GET /cycles/1/ballot (voter3)  -> "my_vote": "no"
----- GET /cycles/1/ballot (ADMIN)   -> "my_vote": null
```

Each caller sees only their own choice, and the administrator — who did not
vote — sees none. Item-level counts are `null` until close. The admin lookup
carries no votes at all:

```
----- GET /admin/users/2 -> 200
{"id":2,"display_name":"Bo497215","verification_level":"unverified",
 "jury_history":[],
 "ballot_votes":"Not available to anyone but the voter. This endpoint never
  returns them, by design (DEMOCRACY.md §13)."}
```

Statically, the only two reads of a ballot vote row keyed by voter are
`cycles_repo.my_ballot_votes` (called once, with `viewer.id`) and
`cycles_repo.ballot_votes_of_user` (called once, by the export contributor
with the exporting user's own id). Everything else is `func.count`.

**Vote weight depending on anything but the voter's choice.** `votes_repo.tally`
counts rows and `rules.net_score` subtracts; no multiplier exists anywhere.
`verification_level` appears in only three roles — stamped on the vote row,
reported in aggregate in the summary, and shown on the account page — and
`is_admin` only in authorization, in the jury exclusion the documents require,
and in display. No arithmetic anywhere reads either.

### Three hand-derived `threshold()` cases (six, in fact)

Derived by hand from DEMOCRACY §5.3 first, then compared with the imported
function:

```
 pct  min  denom  hand  code  match  working
   5    3    100     3     3     OK  ceil(5/100*100)=ceil(5.0)=5; min(5,3)=3; max(1,3)=3
  25    3      4     1     1     OK  ceil(25/100*4)=ceil(1.0)=1; min(1,3)=1; max(1,1)=1
  10    5      0     1     1     OK  ceil(10/100*0)=0; min(0,5)=0; max(1,0)=1   <- the floor
  10    5     41     5     5     OK  ceil(10/100*41)=ceil(4.1)=5; min(5,5)=5    <- rounding up
   5    3      1     1     1     OK  ceil(5/100*1)=ceil(0.05)=1; min(1,3)=1
  10    5     60     5     5     OK  ceil(6.0)=6; min(6,5)=5                    <- min caps the pct

ALL MATCH
```

### My own full-cycle walkthrough, six accounts, from scratch

Written from the build brief's "done" list, not from the build's scripts, and
run against my own database after a `DROP DATABASE`. Every response was
printed; the highlights follow.

Three accounts cannot produce a real jury (the draw excludes the author and
every administrator), so I used six.

**Post with two solutions, filed by the real labeler:**

```
----- POST /posts -> 201   {"id":1,"label_status":"pending", ...}
  attempt 1: label_status=pending
  attempt 2: label_status=labeled

----- GET /posts/1 -> 200
  "communities":[{"community":{"level":"city","entity_id":408,"name":"San Jose"},
    "umbrella_id":2,"umbrella_name":"Pedestrian Safety Near Schools",
    "main_category":"Public Safety","label_shown_as":"AI-labeled, not yet reviewed by the author",
    "confidence":0.8,"solution_ids":[1,2]}]
```

Two `post_solutions` rows produced two `solutions` rows in the one umbrella —
DEMOCRACY §4.1.

**The AI action row, written before the result was shown (Law 7):**

```
----- GET /ai/actions?subject_type=post&subject_id=1 -> 200
{"id":1,"action_type":"label","subject_type":"post","subject_id":1,
 "demo_build":"demo-01","model":"ollama:llama3.2","prompt_file":"labeler.md",
 "prompt_hash":"5edbdd9cbeec...","input_hash":"66f6f15da215...",
 "output":{"umbrellas":[{"umbrella_id":2,"community_level":"city","community_entity_id":408},
                        {"umbrella_id":null,"community_level":"city","community_entity_id":1}],
           "confidence":0.8,"main_category":"Public Safety","category_recognised":true,
           "repeated_or_unlisted_communities":[{"community":"city:1","umbrella_id":null}]},
 "human_outcome":"unreviewed"}
```

The model invented a community (`city:1`) that the author never selected, and
the platform recorded it in the public log rather than discarding it — audit
run 2's FIX-12, reproduced live.

**Amendment absorbed, new version created:**

```
----- POST /solutions/1/amendments -> 201  {"id":1,"absorption_threshold":1}
----- PUT /votes (voter2) -> 200
  {"absorbed":true,"absorption_threshold":1,"solution_supporters":4,
   "new_version":2,"status":"absorbed"}

----- GET /solutions/1 -> 200
  "current_version": 2, "supporters": 4, "is_dominant": true,
  "versions":[{"version":1,"written_by":"Ada497215","content_hash":"240bba14..."},
              {"version":2,"written_by":"Bo497215","from_amendment_id":1,
               "content_hash":"60e14894..."}]
```

**Prepare — snapshot, and the jury draw:**

```
----- POST /admin/cycles/prepare -> 200
{"cycle_id":1,"number":1,"state":"jury_review","active_users_at_prepare":12,
 "items":[{"solution_id":3,"version":2,...},{"solution_id":4,"version":1,...}],
 "considered":[ ... each non-qualifying solution with its four conditions ... ]}
```

The draw excluded exactly the right people. Stored pool:

```
 id | cycle_id | size_requested | eligible_pool | random_bytes            | seated_count
  1 |        1 |              3 | [3, 4, 5]     | f7e158590b5458b38474... |            3
```

Users 1 (solution author), 2 (author of the absorbed amendment's version) and
6 (administrator) are absent — DEMOCRACY §8.1, exactly.

**Hold-backs, majority and minority:** with three seated jurors, one juror held
back item A and two held back item B.

```
item A: "held_back": false, "votable": true      <- 1 of 3 is not a majority
item B: "held_back": true,  "votable": false, "result": "held_back"
```

**Close, publish, and the summary document** — every DEMOCRACY §11.2 section
present and in order:

```
"header":{"jury":"3 drawn, 0 replaced, 3 seated","cycle_number":1,
          "active_users_at_snapshot":6,"members_who_voted":5,
          "verification_mix":"5 voters: 5 unverified",
          "residency_note":"Residency is self-declared and unverified at this verification level."}
"results":[{"position":1,"yes":4,"no":1,"result":"Passed",
            "solution_version":2,"solution_version_hash":"60e14894...",
            "juror_concerns":{"label":"Juror concerns (1 of 3 seated)",
                              "reasons":[{"juror":"Juror 1 of 3","category":"other","reason":"..."}]}}]
"held_back":[{"position":2,"jury_reasons":[{"juror":"Juror 1 of 3",...},
                                            {"juror":"Juror 2 of 3",...}]}]
"how_this_was_produced":[ 5 paragraphs, each with settings_in_force and rule_version ]
"settings_in_force":{ all 22 keys }
```

The minority hold-back that did *not* remove the item is published under the
item anyway — audit run 2's FIX-10, reproduced.

### Hash round-trip, three independent ways

```
bytes downloaded : 5894
stored hash      : 7b93776f6a010663767f8cb5d96f56c26226366f7f657cdca53020ad6d9ee9b6
locally computed : 7b93776f6a010663767f8cb5d96f56c26226366f7f657cdca53020ad6d9ee9b6
verify endpoint  : {'match': True, 'verdict': 'This document is unchanged since it was published.'}

MATCH: True
independent re-canonicalisation matches stored hash: True
```

SHA-256 over the downloaded bytes, the platform's own verifier, and a
re-canonicalisation I performed myself (sorted keys, no whitespace, UTF-8) all
agree.

### The zero-item cycle path

```
----- POST /admin/cycles/3/publish -> 200
empty_note : No solutions reached the ballot this cycle.
results    : []
held_back  : []
jury       : No jury was drawn
hash       : 3e4cb3a76969f18b2293fd2bb2a1d328b12ce41ba7ab5e66c34bc1e28bbd0193

----- POST /admin/cycles/prepare -> 200   {"cycle_id":4, ...}
```

A zero-item cycle goes straight from `prepared` to `published`, and the
community is unblocked afterwards — DEMOCRACY §10.2.

### State-machine guards

```
  cycle 1 open         -> 409 {"error":"cycle_wrong_state","message":"A ballot opens from jury review."}
  cycle 1 close        -> 409 {"error":"cycle_wrong_state","message":"Only an open ballot can be closed."}
  cycle 1 publish      -> 409 {"error":"cycle_wrong_state", ...}
  cycle 1 redraw-jury  -> 409 {"error":"cycle_not_in_jury_review", ...}
  (same for cycle 2)

  second prepare       -> 409 {"error":"cycle_already_open",
      "message":"Cycle 3 for San Jose (city) is still prepared. Publish it before preparing the next one."}
  vote on a closed ballot -> {"error":"ballot_not_open", ...}
```

`ALLOWED_TRANSITIONS` matches DEMOCRACY §10.1 exactly, including
`prepared → published` guarded by a zero-item check. I found no transition the
code allows that the document does not.

### Pagination (ARCHITECTURE §6)

```
=== limit=500 must be 422 ===
  422  /ai/actions                 422  /admin/log
  422  /summaries/hashes           422  /umbrellas?community=city:408
  422  /umbrellas/2/solutions      422  /umbrellas/2/comments
  422  /umbrellas/2/references     422  /settings/history?key=jury_size
  422  /communities/city/408/cycles 422 /solutions/1/amendments

=== the documented exemptions return whole ===
  200  /geo/counties               200  /geo/counties/43/cities
  200  /communities/city/408/officials   200  /settings
```

All seven endpoints audit run 3 named now paginate.

### Endpoint inventory against ARCHITECTURE §6

72 endpoints live. I compared `/openapi.json` line by line against §6: every
documented endpoint exists with the documented method and path, and there is
nothing undocumented. `POST`/`PATCH`/`DELETE /posts` correctly do not exist
(DEMOCRACY §4.1, posts are immutable).

### Settings actually consulted (§4.2)

All 22 keys have consumers in the modules the documents say depend on them.
`jury_review_days` and `ballot_window_days` appear only on display paths,
which is what DEMOCRACY §10.1 prescribes ("the timers … do not fire").

### Security

```
=== password policy ===
  [short]        -> {"error":"weak_password","message":"... at least 8 characters long."}
  [nouppercase]  -> {"error":"weak_password","message":"... contain a capital letter."}
  [nonumber]     -> {"error":"weak_password","message":"... contain a number."}
  [83 bytes]     -> {"error":"weak_password","message":"... no longer than 72 characters."}
```

Refused, never truncated. The check is byte-based; only the wording is off
(LOW above). Hashing is bcrypt cost 12; token and IP fingerprints are SHA-256;
raw tokens are never stored.

```
=== refresh rotation and reuse ===
login  -> body carries NO refresh token; header carries
          set-cookie: refresh_token=...; HttpOnly; Max-Age=1209600; Path=/; SameSite=strict
refresh#1                    -> 200, new access token
reuse the OLD (replaced) one -> {"error":"refresh_reused","message":"For your safety we signed
                                 you out of every device. Please sign in again."}
the NEW one afterwards       -> {"error":"refresh_reused", ...}   <- whole chain revoked

=== logout blacklist ===
before logout -> GET /auth/me 200
logout        -> {"message":"Signed out."}
after logout  -> {"error":"token_revoked","message":"That session has been signed out."}
write attempt -> {"error":"token_revoked", ...}

=== rate limiting (RATE_LIMIT_WRITE_PER_MINUTE=30) ===
200 ×30 then 429 ×10
{"error":"rate_limited","message":"You are sending changes faster than the platform accepts them.
  Try again in 60 seconds."}
retry-after: 60

=== authorization ===
every write endpoint, unverified account -> 403 email_not_verified
admin endpoints, ordinary account        -> 403 {"error":"not_admin"}
any write, no token                      -> 401 {"error":"not_signed_in"}
```

I also checked completeness of `test_authorization.py` mechanically: of the 37
write endpoints in `app.routes`, 7 are public by specification (`/auth/*`) and
all 30 remaining are present in the test's `SIGNED_IN_ONLY`/`ADMIN_ONLY` lists.

**Anonymization** (DATABASE §3.1) erases every column the document lists and
nothing it does not — see the CRITICAL finding above for the row dump, plus:

```
user_display_settings -> public_name_mode reset to display_name
refresh_tokens        -> both rows revoked = t
```

**Secrets:**

```
$ git ls-files | grep -i env
.env.example
backend/alembic/env.py
backend/config/settings_env.py

JWT_SECRET occurrences in the server log : 0
raw password occurrences in the log      : 0
secret-shaped keys in any logged payload : none
secret-looking content in ai_actions.output : none
```

**Errors** leak nothing: every 404/422 returns a typed code and a plain
message, with no traceback, module path or SQL in any body.

### `mailto:` (AUDIT §4.3)

The body contains only fixed text, the absolute summary URL and the hash — no
user data:

```python
body = ("I am a resident of this community. These are the results of our ballot "
        "this cycle, voted on by residents and published in full:\n\n"
        f"{url}\n\n"
        f"Document fingerprint (SHA-256): {digest}\n\n"
        "The page explains every rule that produced these results and how to "
        "check that the document has not been altered.\n")
```

Recipients are the officials directory for that community; the subject is
"Ballot results — [community], cycle N".

### PDF export

Rendered in-process with compression off so the footer text is readable:

```
URL  in PDF text : True
hash in PDF text : True
  FOOTER: Fingerprint \(SHA-256\): 7b93776f6a010663767f8cb5d96f56c26226366f7f657cdca53020ad6d9ee9b6
  FOOTER: Published at: http://localhost:3000/summaries/city/408/1
  FOOTER: Fingerprint \(SHA-256\): 7b93776f6a010663767f8cb5d96f56c26226366f7f657cdca53020ad6d9ee9b6
  FOOTER: Published at: http://localhost:3000/summaries/city/408/1
```

Two pages, two footers, each with the hash and the absolute URL — DEMOCRACY
§11.6 and FIX-25.

### AI roles

Similarity ran on the real embedding model when two members proposed nearly
the same change:

```
----- GET /ai/actions?action_type=similarity -> 200
{"id":2,"action_type":"similarity","subject_type":"amendment","subject_id":3,
 "model":"ollama:nomic-embed-text",
 "prompt_file":"(embeddings: no prompt file)",
 "prompt_hash":"0000000000000000000000000000000000000000000000000000000000000000",
 "output":{"score":0.974,"flagged":true,"threshold":0.85,
           "amendment_a_id":2,"amendment_b_id":3},
 "confidence":0.974,"human_outcome":"unreviewed"}
```

The sentinel is exactly DATABASE §3.10. A human then decided, and the AI row
recorded the outcome — AI suggested, it did not decide:

```
----- POST /similarity/1/decide -> 200
{"same_presses":1,"presses_needed":2,"decision":"same","merged_amendment_id":3}

amendments:  3 | merged_into | merged_into_id 2
ai_actions:  2 | similarity  | human_outcome accepted | human_outcome_by 3
```

The umbrella page carries the §9.5 action list as a sentence, and every post,
solution, amendment and comment carries its AI-influence figure and the
honest caveat that pasted outside-AI text is not detectable.

With `SEARCH_API_KEY` unset the admin trigger behaves as ARCHITECTURE §8.2
requires:

```
----- POST /admin/umbrellas/2/recommend-references -> 503
{"error":"search_not_configured","message":"Reference recommendation needs a web
 search provider, and none is configured on this platform yet."}
```

References added by a member reject at `reference_reject_min` and are never
deleted:

```
not_useful 1 -> "status":"active"
not_useful 2 -> "status":"rejected"
listing: "active":[], "rejected":[{...}],
  "note":"References the community marked not useful are moved to the rejected
          list. They are never deleted."
```

### Frontend (§4.5)

```
$ npm audit --audit-level=high
found 0 vulnerabilities

$ npm run build
✓ Generating static pages (23/23)   — every route in ARCHITECTURE §9 built
```

Served on port 3000 against the live backend:

```
ROUTE                                    CODE  H1s  IMGs  TITLE
/                                        200   1    0     Direct Democracy Cali
/signup                                  200   1    0     Join your community · …
/login                                   200   1    0     Sign in · …
/verify-email                            200   1    0     Confirming your email address · …
/forgot-password                         200   1    0     Reset your password · …
/reset-password                          200   1    0     Choose a new password · …
/me                                      200   1    0     Your account · …
/legal/privacy                           200   1    0     Privacy policy · …
/legal/terms                             200   1    0     Terms of service · …
/legal/cookies                           200   1    0     Cookies · …
/settings                                200   1    0     Every rule and its value · …
/ai/actions                              200   1    0     Everything AI has done here · …
/admin/log                               200   1    0     Everything an administrator has done · …
/admin                                   200   1    0     Administrator controls · …
/feed                                    200   1    0     What people are working on · …
/posts/new                               200   1    0     Write down a problem · …
/umbrellas/1                             200   1    0     The workshop · …
/solutions/1                             200   1    0     A solution · …
/ballot                                  200   1    0     The ballot · …
/jury                                    200   1    0     Jury duty · …
/results                                 200   1    0     Results · …
/summaries/city/408/1                    200   1    0     Ballot results · …
/summaries/hashes                        200   1    0     Every published fingerprint · …
/posts/1                                 200   1    0     A problem report · …
/cycles/1                                200   1    0     A ballot cycle · …
```

Every page renders, each has exactly one server-rendered `<h1>` and a distinct
server-rendered `<title>` (audit run 2's LOW, still fixed). **The images-off
check is trivially satisfied: the platform ships no `<img>` element at all**,
so every page above is already its images-off rendering.

No page computes business logic. Every threshold on a page is a value the
backend supplied (`data.dominant_threshold`, `data.ballot_threshold`,
`data.absorption_threshold`); the only client-side arithmetic anywhere near a
rule is the comment indent, and no page recomputes eligibility or status. The
one hardcoded democratic number is the landing page's "three neighbours",
reported as a LOW.

I could not run a browser or a screen reader — the download host is blocked, as
TODO.md's technical debt records — so keyboard traversal remains a static
check, unchanged from previous runs.

### Documents (§4.6)

```
$ for f in CLAUDE.md PROJECT.md DEMOCRACY.md DATABASE.md ARCHITECTURE.md SANDBOX.md AUDIT.md;
    do git log --oneline main..demo/01 -- $f; done

CLAUDE.md       b5ed801, 867d68f    <- "Post-audit-N document updates"
DEMOCRACY.md    38637cc, b5ed801, 867d68f
DATABASE.md     38637cc, b5ed801, 867d68f
ARCHITECTURE.md 38637cc, b5ed801, 867d68f
SANDBOX.md      867d68f
PROJECT.md      (none)   AUDIT.md (none)
```

Every protected-document edit is in one of the director's three
"Post-audit … document updates" commits. **No build or fix-run commit touched
a document it was not allowed to touch** — AUDIT §4.6's `HIGH` does not apply.

TODO.md's ids: every id I checked is genuinely done except FIX-22, reported
above. HISTORY's fix-run-3 entry is backed by pasted output for every claim I
could re-run, and all of them reproduced; its one unbacked claim is FIX-22's
UI half, which is also the one that is not true.

### Final diff check

```
$ git diff main...HEAD --stat
```

Run and pasted at the very end of this audit — see the HISTORY entry commit.
Nothing outside `audits/` and `HISTORY.md` is changed by me. The `.env`,
`.venv/`, `node_modules/` and `frontend/.next/` I created to run the system are
all gitignored and `git status --porcelain` was empty throughout.

---

## Checks passed

Recorded so silence is not ambiguity. Every §4 check not producing a finding
above:

**§4.1 Constitution**

- Law 1 — a post cannot be saved without a solution: enforced in
  `services/posts.py::create` and by `solutions: list[str] = Field(min_length=1)`
  plus a non-blank validator; `posts` and `post_solutions` are written in one
  transaction.
- Law 2 — every schema change is an Alembic migration; two branch labels apply
  independently from empty; no `create_all` outside tests.
- Law 3 — `influence_score` is declared deprecated and appears nowhere in the
  backend except its model definition; no code writes it.
- Law 4 — `verify_schema.py` check [5] confirms every foreign key is indexed.
- Law 5 — multi-table writes happen in one service function inside one session.
- Law 6 — `content_hash` generated at creation for posts, post solutions,
  solution versions, amendments, comments, and `summary_hash` for summaries;
  reconciliation recomputed every one with zero mismatches. Field lists match
  DATABASE §4.3, §4.4, §4.8, §4.9 and §4.11 exactly.
- Law 7 — order verified by reading `services/labeling.py::label_post`: the
  `ai_log.record` call precedes the label rows, the umbrella assignment, the
  solution creation and the status change, all inside one transaction. Prompts
  are files under `ai/prompts/`; no prompt string exists in Python.
- Law 8 — no democratic threshold is a literal. The module-level constants in
  `services/` are validation lengths and infrastructure timings that the
  documents fix in prose (problem text 20–5,000; rationale 10–300; comment
  1–2,000; hold-back reason 20–1,000; title 80; bcrypt cost 12; settings cache
  60s; last-active debounce 60s; rate-limit window 60s; export expiry hourly).
  The one exception is the landing-page copy, reported as a LOW.
- Law 9 — `services/rules.py` carries the full plain-English explanation as its
  module docstring, `RULES_VERSION = "rules-v1"`, and per-rule version labels;
  `rules_version` is printed in every summary and every "how this was
  produced" paragraph. No A/B machinery exists anywhere.
- Law 10 — nothing reads the environment outside `settings_env.py`; startup
  refuses on a missing key.
- Law 11 — database access is async SQLAlchemy on asyncpg throughout, HTTP is
  async httpx; no synchronous database or HTTP call exists inside `async def`.
  The two filesystem exceptions are reported as a MEDIUM.
- Law 12 — no bare `except`, no `except: pass`; every handler logs; clients get
  a typed code and a plain message with a `request_id` on 500s.
- Law 13 — every request body is a Pydantic model; every query is
  parameterized (no string-built SQL anywhere); bcrypt cost 12; policy
  enforced; every write endpoint rate limited.
- Law 14 — every action is invocable from the API alone; my entire walkthrough
  used only HTTP. No page holds business logic.
- CLAUDE §2 — every rule is public at `/settings` with its meaning and
  `effective_from`; every AI action at `/ai/actions`; every admin action at
  `/admin/log`, readable with no login; each summary prints the settings in
  force.
- CLAUDE §3 — one vote per member per item; verification recorded and never
  weighted; ranking identical for all content and printed with its version.
- CLAUDE §4, downvotes never hide — `net_score` appears in `ORDER BY` only;
  no repository query filters content by score. (The separate minimum-visibility
  half of §4 is a NOTE below.)
- CLAUDE §5 — AI never creates an umbrella, never votes, never advances a
  threshold. Every AI result is labelled where it appears and logged. Label
  corrections are recorded on the label row and on the AI row.
- CLAUDE §6 — display mode is a setting honoured at render time everywhere;
  export is complete; deletion anonymizes exactly the documented columns and
  keeps city and county; hashes are never deleted. (The one place the identity
  survives is the CRITICAL above.)
- CLAUDE §7 — no raw password or raw token is ever stored; no credential is
  hardcoded; every write is rate limited.
- ARCHITECTURE §2 — no router imports a repository, a client or a job; no
  service calls `session.execute`, `session.get` or `select`; every endpoint
  calls at most one service function beyond a `require_*` resolver.
  `test_layering.py` enforces all three by AST and passes.

**§4.2 Specification conformance** — every table and column in DATABASE.md
exists with the stated nullability, default, index and constraint, and nothing
undocumented exists (the type-spelling difference is the MEDIUM above); every
endpoint in ARCHITECTURE §6 exists with nothing undocumented; every DEMOCRACY
rule I could exercise matched; `threshold()` re-derived by hand in six cases;
all 22 settings seeded, readable and consulted; every state transition matches
§10.1 and §5.2 and I found none the code allows that the document does not.

**§4.3 Security** — covered in the evidence log; no finding.

**§4.4 Evidence** — every acceptance claim in fix run 3's HISTORY entry that
can be re-run reproduced, with the single exception reported as a MEDIUM.

**§4.5 Frontend** — every §9 page renders with the backend running and with
images off; AI labels appear everywhere DEMOCRACY requires; no client-side
business logic.

**§4.6 Documents** — no protected document was edited by a build or fix run.

---

## Document ambiguities

For the director. I did not resolve these.

1. **Whether a published summary may keep a person's name after they delete
   their account.** DEMOCRACY §11.2 item 2 says "author display as of
   snapshot", which is what the code does; DEMOCRACY §11.1 says "Nothing
   personal in it"; CLAUDE §6 promises erasure and "Former Community Member"
   attribution. These three cannot all hold. I reported it as a `CRITICAL`
   because CLAUDE.md wins under its own rule, but the resolution is a design
   decision: either the document drops the frozen display name (and the
   summary attributes items to the umbrella or to a stable pseudonymous id),
   or CLAUDE §6 gains an explicit, stated exception for published documents —
   which would need to be visible to the user at signup, since today the
   signup copy tells them only that hashes are permanent.

2. **`CHAR(64)` versus `VARCHAR(64)` for hashes.** DATABASE §1 says `CHAR(64)`;
   every column is `VARCHAR(64)`. `CHAR` would space-pad, which is a worse fit
   for a fixed-width hex string and could surprise a future comparison, so I
   believe the document is what should change — but the document is explicit
   and I did not want to assume.

3. **Whether "every write endpoint" in ARCHITECTURE §4 is meant to include
   endpoints that act only on the caller's own account.** `PATCH /me/display`,
   `POST /me/export` and `DELETE /me` are writes by any reading, but requiring
   a confirmed email before someone may delete an account they created is
   arguably the wrong trade. Either the code or the sentence should move.

4. **CLAUDE §4's minimum-visibility rule has no implementation and no
   setting.** The constitution says "Minority viewpoints receive a documented
   minimum visibility regardless of vote count" and "The exact visibility rule
   is a public platform setting that the community can vote to adjust."
   DEMOCRACY §14 maps §4 onto §3.3 item 4 and §6 — which deliver "nothing is
   ever hidden" but not a minimum *visibility*, and §7.4 has no such key. In
   Demo 1 nothing ranks anything down out of sight, so no harm occurs today;
   the gap will matter the moment a smarter feed exists. Worth deciding
   whether the Small Voice protection is satisfied by "nothing is hidden" for
   now, or whether §7.4 owes a key.

5. **`test_authorization.py`'s endpoint lists are hand-maintained.** They are
   complete today — I checked all 37 write endpoints mechanically — but
   `test_pagination.py` sets a better precedent by walking `app.routes` and
   failing when a route is not accounted for. A new endpoint added later would
   silently have no 401/403 coverage. Not a finding; a suggestion.

6. **Four frontend routes are not in ARCHITECTURE §9's table**: `/` (the
   landing page), `/posts/[id]`, `/cycles/[id]` and `/summaries/hashes`. Each
   is sensible and `/summaries/hashes` is required by DEMOCRACY §11.3, but §9
   reads as a complete list. Worth adding them, or saying the table is
   illustrative.
