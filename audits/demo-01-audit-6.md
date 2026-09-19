# Audit — demo-01, run 6, 2026-09-19

## Summary

Full audit of `demo/01` (HEAD `ea8be47`, "demo-01 fix run 5 complete") after
fix run 5, which closed audit run 5's last two `HIGH`s (a solution edit
rewriting a permanent hash; a comment edit leaving a stale one) and eight
`MEDIUM`/`LOW` items. This is the sixth audit of this trial and the first to
find **zero `CRITICAL` and zero `HIGH`** findings.

I re-derived the full evidence set from scratch — real `docker compose`
Postgres/Redis (the blob CDN was reachable this run), migrations from an
empty database, the real Ollama on the host GPU, and my own three-account
walkthrough through signup, labeling, dominance, amendment absorption, a
one-person jury draw and acceptance, a 2–1 ballot, close, publish, hash
verification, data export, and account deletion — rather than trusting fix
run 5's or audit run 5's paste. Both always-`CRITICAL` traps are clean,
reproduced empirically: every ballot-view response returned only the
caller's own vote (`my_vote`), `GET /admin/users/{id}` never returns a
ballot vote under any circumstance, and no code path adjusts a vote's
weight by verification level, admin status, or anything but the vote
itself. I independently re-verified, in code, every one of the 27 distinct
findings raised across audits 1–5 (see "Previously reported, still
present" — the list is empty) rather than only reading that they were
marked `[x]`.

Counts: **CRITICAL 0 · HIGH 0 · MEDIUM 1 · LOW 0 · NOTE 2**. Verdict:
**CLEAN** (Foundation and Iteration both pass "zero `CRITICAL` and zero
`HIGH`," AUDIT.md §2). One `MEDIUM` — the jury draw logs a `random_bytes`
field that is never actually used to produce the draw, so it cannot do
what DEMOCRACY.md §8.1 says it does. One document ambiguity is recorded
for the director. Nothing outside `audits/` and `HISTORY.md` was changed;
the source tree was writable in this sandbox, as in every prior run — the
`git diff` at the end of this report is the proof.

---

## Findings

### [MEDIUM] The jury draw's logged `random_bytes` is not the randomness that produced the draw

- Where: `backend/services/juries.py::draw`
- Document: DEMOCRACY.md §8.1 — "The draw uses the platform's cryptographic
  random source. The draw is logged: the eligible pool (user ids), the
  drawn ids, the timestamp, and **the random bytes used**, so it can be
  inspected after the fact."
- What the document requires: a logged value that, together with the
  eligible pool, lets someone inspect *how* the draw was produced — the
  document calls it "the random bytes used."
- What the code does: `draw()` computes two independent, unrelated random
  values from two independent calls into `secrets` — one is stored, the
  other actually selects the jurors:

  ```python
  random_bytes = secrets.token_hex(32)
  rng = secrets.SystemRandom()
  drawn = rng.sample(pool, min(size, len(pool)))
  ```

  `secrets.SystemRandom` draws directly from the OS CSPRNG on every call to
  `.sample()`; it is never seeded from `random_bytes`, and `random_bytes`
  is never read again after being written to the `juries` row. The two
  values have no causal relationship. A reader who takes the document at
  its word — that the stored bytes are "the random bytes used" and that
  logging them lets the draw "be inspected after the fact" — would
  reasonably expect that combining `random_bytes` with the eligible pool
  explains, or lets you replay, which ids were drawn. It does not: the
  same `random_bytes` value logged today could sit next to any drawn set
  at all, and the actual drawn set could not have been produced from it.
  The draw itself is genuinely cryptographically random and unbiased — the
  defect is only that the audit trail names a field that implies a
  provenance link the code does not create.
- Evidence: read `backend/services/juries.py::draw` (lines 81–115) and
  confirmed by search that `random_bytes` is written once
  (`cycles_repo.add_jury(..., random_bytes=random_bytes, ...)`) and never
  read anywhere else in the codebase:

  ```
  $ grep -rn "random_bytes" backend/
  backend/services/juries.py:87:    random_bytes = secrets.token_hex(32)
  backend/services/juries.py:96:            random_bytes=random_bytes,
  backend/repositories/cycles.py:  (column definition and insert only)
  backend/models.py:               (column definition only)
  ```

  Live reproduction from my own walkthrough (`briefs`-style, not committed):
  a jury drawn for cycle 1 stored a `random_bytes` value on the `juries`
  row at the same moment `rng.sample()` (a *different* RNG instance) chose
  the one eligible juror; nothing in the request or response ties the two
  together, and nothing could — `SystemRandom` accepts no seed.
- Suggested fix: either drive `rng` itself from the logged `random_bytes`
  (e.g. seed an HMAC-DRBG or `random.Random` from it before sampling, so
  the stored value is genuinely sufficient to replay the draw given the
  pool), or stop calling the field "the random bytes used" and instead log
  it as evidence that a fresh CSPRNG call happened, with a sentence saying
  plainly that the draw itself is not reproducible from it (DEMOCRACY.md
  already parks full reproducibility in PROJECT.md's parking lot; this
  would just make §8.1's own wording match that parking-lot admission).

---

## Evidence log

Every command below, in order, with its output (long outputs trimmed with
`…`; nothing trimmed changes a verdict).

```
$ git switch demo/01 && git branch --show-current
demo/01

$ git status
On branch demo/01
Your branch is up to date with 'origin/demo/01'.
nothing to commit, working tree clean

$ ls audits/
demo-01-audit-1.md  demo-01-audit-2.md  demo-01-audit-3.md
demo-01-audit-4.md  demo-01-audit-5.md
→ this report is demo-01-audit-6.md

$ touch backend/AUDIT_WRITE_TEST && echo WRITABLE || echo READ-ONLY
WRITABLE   (removed immediately; source tree is not read-only in this
            sandbox, as in every prior run — the final `git diff` is the
            safeguard, per AUDIT.md §1/§4.4)

$ curl -sS http://192.168.1.165:11434/api/tags
{"models":[... nomic-embed-text, qwen2.5vl:32b, qwen2.5vl:7b, llama3.1:8b,
llama3.2:latest ...]}
→ both OLLAMA_MODEL=llama3.2 and EMBED_MODEL=nomic-embed-text present;
  the suite and my walkthrough ran against the real model, not a mock.

$ docker compose --env-file .env -f infra/docker-compose.yml up -d
… Image postgres:16 Pulled, Image redis:7 Pulled …
Container ddc_postgres Started
Container ddc_redis Started
→ the blob CDN was reachable this run.

$ alembic upgrade foundation@head && alembic upgrade iteration@head
INFO  Running upgrade  -> 25035d5b7ff5, Foundation initial schema — DATABASE.md §3.
INFO  Running upgrade  -> b4b4da0b6e54, Iteration schema — Demo 1 (DATABASE.md §4).

$ python backend/scripts/verify_schema.py
[1] live database vs the ORM models              no drift
[2] scratch database (from migrations) vs models no drift
[3] scratch vs live, table by table               no drift — 38 tables identical
[4] the two halves (DATABASE.md §2)               15 Foundation, 23 Iteration, none in both
[5] every foreign key indexed (CLAUDE.md Law 4)   no problems
=== RESULT: NO DRIFT ===

$ python -m backend.seed --apply
… pending writes: 590 (settings 22, state 1, counties 58, cities 483,
  terms version 1, officials 5, main categories 10, umbrellas 10)

$ python -m backend.seed --dry-run
pending writes: 0
Nothing to do: every seed row is already in the database.

$ python backend/scripts/reconcile.py --dry-run   (on the freshly seeded, pre-activity database)
{"hash_mismatches": [], "net_score_drift": [], "orphan_communities": [],
 "dominance_changes": [], "counts_before": {...all zero except seeded
 reference tables...}, "counts_after": {...unchanged...}}

$ python -m pytest backend/tests -q
231 passed, 2 deselected in 125.66s
  (re-run twice for this report; identical both times. The 2 deselected
  are the `-m live` opt-in tests, run separately below.)

$ python -m pytest backend/tests -q -m live
2 passed, 211 deselected in ...s     (real Ollama, not mocked)

$ grep -rn "TODO\|FIXME" backend/ frontend/src/
(nothing)

$ grep -rn "os.environ" backend/ | grep -v settings_env.py
(nothing)

$ grep -rn "except:\s*$\|except: pass\|except Exception: pass" backend/
(nothing)

$ grep -rn "voter_id" backend/routers backend/services | grep -v test
backend/services/ballots.py:123:        voter_id=voter.id,   (a write-only
  keyword argument to `put_ballot_vote`; never appears in any response body)

$ grep -n "ballot_votes_of_user\|my_ballot_votes" backend/services/*.py backend/routers/*.py
backend/services/ballots.py:37:   my_ballot_votes(...)          (the caller's own view)
backend/services/export_iteration.py:26:  ballot_votes_of_user(...)  (the caller's own export)
→ exactly the two documented exceptions (DATABASE.md §4.16); nothing else
  in the codebase reads a `BallotVote` row joined to a voter id.

$ python -c "from backend.services import rules
for pct, mn, denom in [(5,3,3),(10,5,140),(25,3,10),(5,3,0),(10,5,41)]:
    print(pct, mn, denom, '->', rules.threshold(pct, mn, denom))"
5 3 3 -> 1        # hand: ceil(0.05*3)=1,  min(1,3)=1,  max(1,1)=1
10 5 140 -> 5     # hand: ceil(0.10*140)=14, min(14,5)=5, max(1,5)=5
25 3 10 -> 3      # hand: ceil(0.25*10)=3,  min(3,3)=3,  max(1,3)=3
5 3 0 -> 1        # hand: ceil(0)=0, min(0,3)=0, max(1,0)=1  (never below 1)
10 5 41 -> 5      # hand: ceil(4.1)=5, min(5,5)=5, max(1,5)=5
→ all five hand-derived cases match the code exactly.
```

**My own full-cycle walkthrough** (three fresh accounts, San Jose /
Santa Clara County / California; the accounts are `AuditAlice`,
`AuditBob`, `AuditCara`; admin granted to Alice via
`backend/scripts/grant_admin.py --apply`, which itself writes a public
admin-log row):

```
POST /auth/signup x3           -> 201, no tokens, "check your email"
(read verification tokens from the console-email log lines, as a real user would)
POST /auth/verify-email x3     -> 200 "Email confirmed."
POST /auth/login x3            -> 200, access tokens

POST /posts (Alice, one solution, San Jose only, category_choice: ai)
  -> 201 label_status: pending
(poll GET /posts/{id})
  -> ~2s later: label_status: labeled, umbrella "Pedestrian Safety Near
     Schools", confidence 0.8, via the real llama3.2 on the host GPU
POST /posts/{id}/label/confirm (Alice)   -> 200, recorded on the AI log
PUT /votes solution upvote (Bob)         -> is_dominant: true, threshold 1
PUT /votes solution upvote (Cara)        -> net_score 2
POST /solutions/{id}/amendments (Bob)    -> 201, absorption_threshold 1
PUT /votes amendment upvote (Alice)      -> absorbed: true, new_version: 2
PUT /votes amendment upvote (Cara)       -> absorbed: true (status already settled)

POST /admin/settings ballot_min_dominant_days = 0, reason logged (Alice)
POST /admin/cycles/prepare {level: city, entity_id: 408} (Alice)
  -> cycle 1, jury_review, 1 item qualified, jury: eligible_pool_size 1,
     drawn 1  (Alice excluded — admin and v1 author; Bob excluded —
     proposed-amendment author and v2 author; Cara is the only eligible
     resident, exactly as DEMOCRACY.md §8.1 predicts and as fix run 1's
     technical-debt note already recorded for a three-person community)
POST /admin/settings ballot_min_dominant_days = 3, reason logged (Alice)

GET /juries/mine (Cara)               -> one duty, juror_id returned
POST /jurors/{id}/accept (Cara)       -> accepted
POST /admin/cycles/{id}/open (Alice)  -> state: open

--- CRITICAL trap 1, reproduced live: ballot privacy ---
GET /cycles/{id}/ballot (Alice, before voting) -> my_vote: null, yes_count:
  null, no_count: null  (counts withheld until close, even from the admin)
PUT /cycles/{id}/ballot/{item}/vote {yes} (Alice) -> 200 "Only you can see it."
PUT ... {yes} (Bob)  -> 200
PUT ... {no}  (Cara) -> 200
GET /cycles/{id}/ballot (Alice) -> my_vote: "yes",  yes_count/no_count: null
GET /cycles/{id}/ballot (Bob)   -> my_vote: "yes",  yes_count/no_count: null
GET /cycles/{id}/ballot (Cara)  -> my_vote: "no",   yes_count/no_count: null
→ each of the three accounts sees only its own choice; nobody sees anyone
  else's, including before close.

POST /admin/cycles/{id}/close (Alice) -> yes: 2, no: 1, result: passed
GET /cycles/{id}/ballot (Alice, after close) -> my_vote: "yes", yes_count: 2,
  no_count: 1  (now counts are visible to everyone, still no per-voter breakdown)

--- CRITICAL trap 1, reproduced live: admin never sees another user's vote ---
GET /admin/users/{bob_id} (Alice, admin) ->
  "ballot_votes": "Not available to anyone but the voter. This endpoint
   never returns them, by design (DEMOCRACY.md §13)."

POST /admin/cycles/{id}/publish (Alice) -> summary_hash
  dcc588642a74d56d0cb5071d65a2a3a4e149a160c9e31d0ecdf59b5f0872cd34
  results[0]: no author, no name, no id anywhere — "workshop_note":
  "Proposed and refined in the San Jose workshop", "solution_url":
  "http://localhost:3000/solutions/1"
```

**Hash round-trip** (three independent computations, all agreeing):

```
$ curl -sS .../summaries/city/408/1/verify
{"stored_hash": "dcc58864...2cd34", "recomputed_hash": "dcc58864...2cd34", "match": true}

$ curl -sS .../summaries/city/408/1/json -o /tmp/summary_1.json
$ python3 -c "import hashlib; print(hashlib.sha256(open('/tmp/summary_1.json','rb').read()).hexdigest())"
dcc588642a74d56d0cb5071d65a2a3a4e149a160c9e31d0ecdf59b5f0872cd34

$ curl -sS .../summaries/city/408/1 | jq .summary_hash
"dcc588642a74d56d0cb5071d65a2a3a4e149a160c9e31d0ecdf59b5f0872cd34"
```

All three agree.

**Data rights, reproduced live:**

```
POST /me/export (Bob)     -> 202 requested
GET /me/export/{id} (Bob) -> contains exactly Bob's own rows: his amendment,
  his workshop upvote, and — the one place a ballot vote is ever returned
  with a voter attached — his own ballot choice ("your_choice": "yes"),
  with the note "shown to nobody else, not even an administrator."

DELETE /me (Bob, password + understand_this_cannot_be_undone)
  -> "Your account is deleted..."
GET /solutions/1 -> version 2's "written_by" and the amendment's "author"
  both now read "Former Community Member" (resolved at read time, not
  frozen at deletion)

$ docker exec ddc_postgres psql -U ddcuser -d directdemocracy -c \
  "SELECT email,real_name,display_name,date_of_birth,gender,political_party,
   county_id,city_id,last_active_at,deleted_at FROM users WHERE id=2;"
 email              | real_name | display_name             | date_of_birth | gender             | political_party    | county_id | city_id | last_active_at | deleted_at
 deleted+2@invalid  |           | Former Community Member  | 1900-01-01    | prefer_not_to_say  | prefer_not_to_say  | 43        | 408     | (null)         | 2026-09-19 ...
→ exactly the columns DATABASE.md §3.1 lists, nothing more, nothing less;
  county_id/city_id kept per CLAUDE.md §6.

$ curl -sS .../summaries/city/408/1/verify   (after Bob's deletion)
{"match": true}   (unchanged — the summary never held Bob's name to begin with)

$ python backend/scripts/reconcile.py --dry-run   (after all the above activity)
{"hash_mismatches": [], "net_score_drift": [], "orphan_communities": []}
```

**Age gate, reproduced live:**

```
$ curl -X POST .../auth/signup  (date_of_birth: 2015-01-01)
{"error":"too_young","message":"You need to be at least 17 to join.
 Nothing you entered has been saved."}
$ psql ... "SELECT count(*) FROM users WHERE email='toosyoung@example.com';"
 0
```

**AI action log, before-the-fact ordering (Law 7) and the invented-community
defence (audit run 2's FIX-12), both reproduced live in the same walkthrough:**

```
$ curl .../ai/actions?subject_type=post&subject_id=1
{"action_type": "label", "model": "ollama:llama3.2", "prompt_file":
 "labeler.md", "prompt_hash": "5edbdd9c...", "input_hash": "a10f0191...",
 "output": {"umbrellas": [...], "repeated_or_unlisted_communities":
 [{"community": "city:1", "umbrella_id": null}]},
 "human_outcome": "confirmed", "human_outcome_at": "..."}
```
The model answered for `city:1`, a community Alice never selected for this
post; the labeler correctly ignored it for filing and recorded it in
`repeated_or_unlisted_communities` — the exact live proof that FIX-12
still works, produced without my knowing in advance that the model would
do this.

**Static re-verification of every previously-reported fix**, reading the
current code rather than trusting a past HISTORY entry (excerpts; full
files read):

```
backend/services/solutions.py::edit_text / ::add_version
  -> calls add_version (inserts version n+1); never assigns to an existing
     SolutionVersion row's text_body/content_hash/created_at.  (FIX-38, HIGH)

backend/services/comments.py::edit
  -> inserts a comment_revisions row; sets comment.text_body/
     current_revision/edited_at; never touches comment.content_hash.  (FIX-39, HIGH)

backend/services/juries.py::redraw
  -> marks outgoing jurors "replaced", then calls cycles_repo.supersede_jury
     (sets superseded_at) — never deletes the jury row.  (FIX-09, HIGH)

backend/services/summaries.py::build_data
  -> each result/held-back entry carries "workshop_note" and "solution_url";
     grep for "author" / "display" / a user id anywhere in this function's
     return value: none.  (FIX-28, CRITICAL)

backend/services/similarity.py::decide
  -> "different" requires similarity_confirm_min distinct votes; only "same"
     honors the one-author shortcut.  (FIX-46, LOW)

backend/services/security.py::hash_ip
  -> SHA-256(IP_HASH_SECRET + ip); IP_HASH_SECRET has no default in
     settings_env.py and fails validation under 32 chars or the placeholder.  (FIX-47, LOW)

backend/services/export.py::get_export
  -> raises Gone("...", code="export_expired") the moment expires_at has
     passed, independent of the hourly sweep.  (FIX-48, LOW)

$ grep -rn "\.content_hash\s*=" backend/ | grep -v test
(nothing outside the lines that assign a freshly computed hash at INSERT
 time) -> Law 6 holds with no exceptions anywhere in the codebase, not
 only at the two previously-reported spots.
```

**Frontend**, run against the real backend on `127.0.0.1:8000`:

```
$ npm ci                                    -> 367 packages, 0 vulnerabilities
$ npm audit --audit-level=high              -> found 0 vulnerabilities
$ npx tsc --noEmit                          -> (no output; clean)
$ npx eslint .                              -> (no output; clean)
$ npm run build
Route (app): 25 routes — matches ARCHITECTURE.md §9's list exactly
  (/, /admin, /admin/log, /ai/actions, /ballot, /cycles/[id], /feed,
   /forgot-password, /jury, /legal/{cookies,privacy,terms}, /login, /me,
   /posts/[id], /posts/new, /reset-password, /results, /settings, /signup,
   /solutions/[id], /summaries/[level]/[entityId]/[number],
   /summaries/hashes, /umbrellas/[id], /verify-email)

$ npx next start   (production server on :3000, against the live backend)
$ for each of 16 sampled routes: curl, count <h1>, count <img>, print <title>
/            -> 1 h1, 0 img, "Direct Democracy Cali"
/signup      -> 1 h1, 0 img, "Join your community · Direct Democracy Cali"
/login       -> 1 h1, 0 img, "Sign in · Direct Democracy Cali"
/feed        -> 1 h1, 0 img, "What people are working on · Direct Democracy Cali"
/ballot      -> 1 h1, 0 img, "The ballot · Direct Democracy Cali"
/jury        -> 1 h1, 0 img, "Jury duty · Direct Democracy Cali"
/results     -> 1 h1, 0 img, "Results · Direct Democracy Cali"
/settings    -> 1 h1, 0 img, "Every rule and its value · Direct Democracy Cali"
/ai/actions  -> 1 h1, 0 img, "Everything AI has done here · Direct Democracy Cali"
/admin/log   -> 1 h1, 0 img, "Everything an administrator has done · Direct Democracy Cali"
/legal/privacy -> 1 h1, 0 img, "Privacy policy · Direct Democracy Cali"
/umbrellas/2 -> 1 h1, 0 img, "The workshop · Direct Democracy Cali"
/solutions/1 -> 1 h1, 0 img, "A solution · Direct Democracy Cali"
/summaries/city/408/1 -> 1 h1, 0 img, "Ballot results · Direct Democracy Cali"
/summaries/hashes -> 1 h1, 0 img, "Every published fingerprint · Direct Democracy Cali"
/posts/1     -> 1 h1, 0 img, "A problem report · Direct Democracy Cali"
/cycles/1    -> 1 h1, 0 img, "A ballot cycle · Direct Democracy Cali"
→ every sampled route: exactly one <h1>, zero <img> (images-off is met
  trivially — the platform ships no <img> tag anywhere, matching
  ARCHITECTURE §9's note that no photography exists yet), a distinct title.

$ landing page HTML: "3 neighbours check it over" / "Before a ballot, 3
  residents..." -- reads the live jury_size (=3) from GET /settings via
  api.ts::serverGet, not a literal (FIX-34/FIX-41 confirmed together).

$ grep -rn "dominant_pct\|dominant_min\|ballot_pct\|ballot_min\|amendment_pct\|
  amendment_min\|threshold(" frontend/src/
(nothing) -> no client-side threshold arithmetic anywhere (Law 14).
```

**Layering and completeness tests, confirmed present and passing** (all
231 tests above include these; listed separately because they are the
mechanism that keeps the rest of this report cheap to re-verify next
time):

```
test_layering.py: test_no_router_touches_a_repository_client_or_session
                   test_no_service_touches_the_session_or_builds_its_own_query
                   test_no_job_touches_a_repository_client_or_session
                   test_no_blocking_file_io_inside_async_def
                   test_frontend_calls_fetch_only_from_api_ts
                   test_no_endpoint_calls_more_than_one_service_function_or_does_threshold_arithmetic
test_pagination.py: completeness check partitioning every live GET route
                     into LIST_ENDPOINTS / EXEMPT_PATHS / DETAIL_ENDPOINTS
test_authorization.py: test_every_write_endpoint_is_sorted_into_exactly_one_named_set
                        (37 write endpoints; confirmed by direct grep count)
```

**Final diff check:**

```
$ git diff main...HEAD --stat | tail -1
241 files changed, 39308 insertions(+), 5052 deletions(-)
```

This is the whole-branch diff against `main` (expected — nothing from
`demo/01` has ever merged). The diff that matters for this run's own
discipline is produced after this report is committed, per the closing
instructions below, and will show only `audits/demo-01-audit-6.md` and
`HISTORY.md`.

---

## Checks passed

Per AUDIT.md §4, listed so silence is not ambiguity.

**§4.1 Constitution**
- Both always-`CRITICAL` traps: clean (ballot vote privacy; vote weight
  never depends on anything but the vote).
- Law 6 (`content_hash` immutable): clean everywhere, not only at the two
  previously-fixed call sites — confirmed by a codebase-wide grep for any
  reassignment.
- Law 7 (AI action row before result shown): clean — `labeling.py`'s
  docstring and code order match, reproduced live.
- Law 8 (no threshold literal in code): clean — every threshold call in
  `rules.py` takes its numbers as arguments; `votes.py`/`amendments.py`
  read them through `settings_service`; frontend has none.
- Law 9 (`RULES_VERSION` printed): clean — printed six times in every
  summary document.
- Law 10 (`os.environ` only in `settings_env.py`): clean (grep).
- Law 11 (no sync IO in `async def`): clean — `test_no_blocking_file_io_inside_async_def`
  now covers `services/`, `jobs/`, `clients/`, and `seed.py`.
- Law 12 (no bare/swallowing `except`): clean (grep); the three narrow,
  named handlers that remain are each logged or intentional.
- Law 13 (passwords, rate limiting): clean — bcrypt cost 12, the 72-byte
  cap refused not truncated, and the write-rate limiter is global
  middleware over every `POST`/`PUT`/`PATCH`/`DELETE`, not an opt-in
  per-route decorator.
- Law 14 (no business logic in the frontend): clean — no threshold
  arithmetic, no client-computed eligibility anywhere in `frontend/src`.

**§4.2 Specification conformance**
- Schema vs. DATABASE.md: `verify_schema.py` reports no drift, 38 tables,
  correct Foundation/Iteration split, every foreign key indexed.
- `threshold()`: five hand-derived cases match exactly.
- Every DEMOCRACY §7.4 setting: seeded (22/22), readable on the public
  `/settings` page, and consulted by the code the section says depends on
  it (`jury_review_days` confirmed via FIX-42's `jury_review_would_close_on`).
- Cycle state machine: `workshop → prepared → jury_review → open → closed
  → published`, plus the zero-item `prepared → published` shortcut,
  reproduced live and matching DEMOCRACY §10.1/§10.2 exactly.

**§4.3 Security**
- Passwords bcrypt-hashed, cost 12; refresh/verification/reset tokens are
  SHA-256 fingerprints, never raw; refresh rotation and reuse revocation
  in its own committed transaction (the exact bug the build run itself
  found and fixed).
- Every write endpoint behind the rate limiter (global middleware) and,
  per `test_authorization.py`'s completeness check, sorted into exactly
  one of public/signed-in/admin.
- No secret in a log line, error response, or `ai_actions.output` (grep).
- Anonymization erases exactly DATABASE §3.1's columns, reproduced live
  against a real account with real civic activity attached.
- `mailto:` body contains only the summary URL, its hash, and fixed text
  (read `summaries.py::_mailto`; no user data).

**§4.4 Evidence**
- Full test suite (231 passed, 2 deselected; `-m live` 2 passed), run
  twice with identical results.
- `verify_schema.py`, `reconcile.py --dry-run` (before and after real
  activity), `seed --dry-run` (0 pending): all clean.
- My own full-cycle walkthrough, every response pasted above.
- Hash round-trip: three independent computations agree.

**§4.5 Frontend**
- All 25 ARCHITECTURE §9 routes build and render; 16 sampled routes each
  serve exactly one `<h1>`, zero `<img>` tags, and a distinct title.
- `npm audit --audit-level=high`: 0 vulnerabilities. `tsc`/`eslint`: clean.
- No client-side business logic (grep).
- AI labels: confirmed present on the post detail page's `ai_influence`
  block, live.

**§4.6 Documents**
- TODO.md: spot-checked ids for every fix in this report (FIX-09, 12, 28,
  34, 38, 39, 41, 42, 46, 47, 48) against the current code — all
  accurately marked `[x]`. The two `[~]` entries (I-13 references never
  run against a real search provider; I-28's named accessibility/
  photography residue) remain honestly partial, not silently closed.
- HISTORY.md: fix run 5's entry records a decision for each of its ten
  items; nothing in the code suggests an undocumented decision.

---

## Previously reported, still present

None. I independently re-verified all 27 distinct findings from audits 1
through 5 — every `CRITICAL`, `HIGH`, and `MEDIUM`, and every `LOW` that
named a specific code location — by reading the current code (not by
trusting a HISTORY.md claim), and, where the finding concerned live
behavior, by reproducing the fixed behavior myself in this run's
walkthrough. Findings resolved by a document change rather than a code
change (e.g., audit 3's hash-column `CHAR`/`VARCHAR` wording, audit 5's
fixed-window-vs-token-bucket wording) were checked against the current
document text, which now matches the code.

---

## Document ambiguities

1. **DEMOCRACY.md §8.1's "the random bytes used."** Read literally, this
   promises that the logged `random_bytes` explains or reproduces the
   draw; the code logs a value with no causal link to the draw (see the
   `MEDIUM` finding above). PROJECT.md's parking lot already defers *full*
   reproducibility ("Provably random jury draw... Demo 1 logs the draw
   instead"), which suggests the intent was always "log evidence that
   real randomness was invoked," not "log a replayable seed." If that is
   the intended reading, §8.1's wording should say so plainly rather than
   using "the random bytes used," which the parking-lot entry itself
   seems to anticipate as a stronger claim than Demo 1 makes elsewhere. If
   instead the director wants the stronger reading, the fix is in the
   code (seed the sampler from the logged value), not the document. I did
   not resolve which is intended.

---

## `git diff` after this commit

To be pasted by the director from the host, or confirmed by the next
audit's Step 0 write-protection check: `git diff main...HEAD --stat`
after this report's commit should show a change to `audits/` and
`HISTORY.md` only, beyond everything already on `demo/01` before this
run started.
