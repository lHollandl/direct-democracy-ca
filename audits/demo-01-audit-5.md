# Audit — demo-01, run 5, 2026-09-18

## Summary

Full pass over `demo/01` after fix run 4, on a database built from empty by
both migration chains and seeded from the director's seed files, with the real
Ollama on the host GPU. **CRITICAL 0 · HIGH 2 · MEDIUM 5 · LOW 8 · NOTE 4.**
Verdict: **FIX REQUIRED**.

Both always-`CRITICAL` traps are clean and were reproduced empirically rather
than read. Five accounts and an administrator each read the same open ballot;
each saw only their own vote and no payload anywhere carried a `voter_id`. No
code path multiplies, weights or filters a vote by verification level, admin
status or anything but the voter's own choice — `votes.tally` and
`cycles.item_tallies` count rows grouped by direction and by choice and nothing
else. The whole civic cycle ran end to end from seven signups to a published,
hashed, independently re-computed summary document, and the deleted author's
real name appears nowhere in it.

The two `HIGH`s are a single unresolved question about what an "edit" does to a
permanent fingerprint, answered inconsistently in two places. `PATCH
/solutions/{id}` **rewrites** an existing `solution_versions` row's text, its
`content_hash` and its `created_at` in place, which CLAUDE.md Law 6 and
DATABASE.md §4.8 both forbid; `PATCH /comments/{id}` **leaves** the stale
`content_hash` behind, so every comment edited inside the documented
fifteen-minute window produces a permanent `CRITICAL content_hash_mismatch`
from `reconcile.py` that the job is forbidden to correct. One of the two is
wrong and the documents do not say which; the ambiguity is listed for the
director in the last section.

The `MEDIUM`s are all of one shape — a documented obligation the backend meets
and the layer above drops. `backend/jobs/*` reach past services into
repositories (and `reconcile.py` into the session itself) where ARCHITECTURE §2
allows jobs services only, and `test_layering.py` does not look at `jobs/` for
this. `frontend/src/app/page.tsx`, added by FIX-34 last run, calls `fetch`
directly where ARCHITECTURE §9 says `api.ts` is the only place `fetch` is
called. `jury_review_days` is seeded and readable but consulted by nothing: no
juror is ever shown the "would close on …" DEMOCRACY §10.1 promises for both
timers. The solution page never renders the "Jury notes" §8.3 promises every
juror when they submit a reason, though `GET /solutions/{id}` returns them. And
comments and amendments never display the AI-influence figure §6 and §9.5
require, though the API returns it on every one.

Everything fix run 4 claimed reproduced exactly: 222 passed / 2 deselected,
`-m live` 2 passed, `verify_schema.py` no drift across 37 tables, seed dry-run
zero pending writes, the three greps empty, `npm audit --audit-level=high` zero
vulnerabilities, `tsc`/`eslint`/`next build` clean. All ten of audit run 4's
findings are fixed, verified independently. Nothing outside `audits/` and
`HISTORY.md` was changed by this run.

---

## Findings

### [HIGH] `PATCH /solutions/{id}` rewrites a permanent `content_hash` in place

- **Where:** `backend/services/solutions.py::edit_text`
- **Document:** CLAUDE.md Law 6; DATABASE.md §4.8; DEMOCRACY.md §4.3
- **What the documents require:** Law 6 — "`content_hash` is permanent.
  Generated at creation for every post, solution, and summary document from the
  content plus its AI metadata. Never modified or deleted afterward."
  DATABASE §4.8 ends the `solution_versions` definition with the single word
  "Immutable."
- **What the code does:** the author's pre-vote edit window (DEMOCRACY §4.3)
  is implemented by mutating the existing version row rather than by creating a
  new version:

  ```python
  version.text_body = clean
  version.content_hash = hashing.solution_version_content_hash(...)
  version.created_at = now
  ```

  Text, fingerprint and creation time are all overwritten. Because the hash is
  recomputed from the new values, `reconcile.py::_check_hashes` recomputes it
  to the same value and reports nothing: the platform's own integrity check
  cannot see that the record changed. There is no second version, so nothing
  in the version history records that anything happened.
- **Evidence:** a member posts a solution on umbrella 2 and edits it; the row's
  fingerprint and timestamp change and the version list stays one entry long.

  ```
  POST /umbrellas/2/solutions -> 201 {"id":3,...}

  version 1 BEFORE edit:
    "text": "Install speed cushions on the two blocks either side of the school entrance."
    "content_hash": "b7ff65ead9c652c2a278dfa51c4526b4e116be7ae745ecf2d51a369950a4cddd"
    "created_at": "2026-09-18T21:59:21.012210Z"

  PATCH /solutions/3 -> 200 {"id":3,"message":"Updated."}

  version list AFTER edit: [
    {
      "version": 1,
      "text": "Install speed cushions on the four blocks either side of the school entrance.",
      "content_hash": "019b628677018d5d6260ad1a83fc4f7ecea3d0f6d51bad075ed39415fab3faef",
      "created_at": "2026-09-18T21:59:21.030359Z"
    }
  ]
  current_version: 1
  content_hash changed in place: True
  number of versions: 1
  ```
- **Suggested fix:** make the author's edit create version n+1 with its own
  hash (the amendment path already does exactly this), leaving version 1 and
  its fingerprint untouched — or, if the director prefers the edit to stay a
  true correction, say so in DATABASE §4.8 and Law 6 and record the rewrite in
  a visible way; do not leave the two documents saying "immutable" while the
  code overwrites.

### [HIGH] Editing a comment leaves a stale `content_hash`, which `reconcile.py` reports as a permanent CRITICAL

- **Where:** `backend/services/comments.py::edit`
- **Document:** DATABASE.md §4.11 and §7 item 4; DEMOCRACY.md §6
- **What the documents require:** §4.11 defines `comments.content_hash` as the
  canonical JSON of `{target_type, target_id, parent_id, reply_to_comment_id,
  text, author_id, created_at}`. §7 item 4: "Check every `content_hash` and
  `summary_hash` recomputes to its stored value; any mismatch is a critical
  alert, not a correction." DEMOCRACY §6 allows the author to edit for
  `comment_edit_minutes` (15).
- **What the code does:** `edit` assigns `comment.text_body = clean` and
  `comment.edited_at`, and never touches `content_hash`. The hash therefore no
  longer describes the comment, and the nightly reconciliation — which is
  forbidden to repair a hash — raises a `CRITICAL` for that row on every run,
  for ever. The exact opposite choice from `solutions.py::edit_text` above.
- **Evidence:** one comment, one edit inside the window, then the nightly job:

  ```
  POST /comments -> 201 {"id": 1, "depth": 0, "message": "Posted."}
  PATCH /comments/1 -> 200 {"id": 1, "message": "Edited.", "edited": true}

  $ python backend/scripts/reconcile.py --dry-run
  {"level": "CRITICAL", "logger": "backend.jobs.reconcile",
   "message": "content_hash_mismatch", "table": "comments", "id": 1,
   "stored":   "4f5c635efd8ada20771dd85f797077a113084d6a96356181028d9a6b8eeddd85",
   "computed": "037916fdc3a49b3cbe22babb7c703ffaab303d445f08f86d07c0711173a4044a"}
  ...
    "hash_mismatches": [
      {"table": "comments", "id": 1,
       "stored": "4f5c63...", "computed": "037916..."}
    ],
  ```

  Before the edit the same run reported `"hash_mismatches": []`.
- **Suggested fix:** decide the rule once for both edit paths and apply it to
  both — either every edit produces a new hashed row (and comments gain an
  edit history), or an edited row's hash is recomputed and the change recorded;
  whichever the director chooses, `reconcile.py` must stop alerting on ordinary
  use of a documented feature.

### [MEDIUM] Background jobs reach past services into repositories and the session

- **Where:** `backend/jobs/labeling.py::label_post_task`,
  `::label_retry_task`; `backend/jobs/similarity.py::similarity_check_task`;
  `backend/jobs/references.py::recommend_references_task`;
  `backend/jobs/reconcile.py::run`
- **Document:** ARCHITECTURE.md §2, layer table
- **What the document requires:** the table's `Jobs` row reads — May call:
  **services**; Must not: routers, **repositories directly**.
- **What the code does:** four job modules import and call repository functions
  (`posts_repo.get`, `posts_repo.set_label_status`,
  `posts_repo.posts_awaiting_labels`, `solutions_repo.get_amendment`,
  `umbrellas_repo.get`), and `reconcile.py` goes one layer further still,
  building its own queries and executing them on the session
  (`(await session.execute(select(Post))).scalars().all()` and nine more like
  it) — the thing ARCHITECTURE §2 forbids even to a service.
  `backend/tests/test_layering.py` walks `ROUTERS_DIR` and `SERVICES_DIR` for
  this rule and only ever opens `JOBS_DIR` for the unrelated blocking-file-IO
  check, so nothing fails.
- **Evidence:**

  ```
  $ grep -n "repositories" backend/jobs/*.py
  backend/jobs/labeling.py:15:   from backend.repositories import posts as posts_repo
  backend/jobs/references.py:16: from backend.repositories import umbrellas as umbrellas_repo
  backend/jobs/reconcile.py:36:  from backend.repositories import solutions as solutions_repo
  backend/jobs/reconcile.py:37:  from backend.repositories import votes as votes_repo
  backend/jobs/similarity.py:9:  from backend.repositories import solutions as solutions_repo

  $ grep -c "session.execute\|select(" backend/jobs/reconcile.py
  10
  ```
- **Suggested fix:** give each job the one service function it needs
  (`labeling.load_post_for_job`, a `reconcile` service that owns the queries)
  and extend `test_layering.py`'s repository/session checks over `JOBS_DIR`, so
  the boundary is enforced the way the router and service boundaries already
  are.

### [MEDIUM] The landing page calls `fetch` directly, where `api.ts` is documented as the only place that does

- **Where:** `frontend/src/app/page.tsx::citizensDrawnForJury`
- **Document:** ARCHITECTURE.md §9, last paragraph before the style brief
- **What the document requires:** "`frontend/src/lib/api.ts` is the only place
  `fetch` is called; it holds the access token in memory and the refresh token
  in an `httpOnly` cookie set by the backend, and silently refreshes on 401."
- **What the code does:** FIX-34 made the landing page an async Server
  Component that re-declares `API_BASE` and calls `fetch` itself. The fix it
  delivered is right — the jury size is read from `GET /settings` rather than
  written into the copy (Law 8) — but it was delivered by opening a second
  place in the frontend that talks to the API, and a second copy of the base
  URL. The `catch { return null }` around it also swallows the failure
  silently.
- **Evidence:**

  ```
  $ grep -rn "fetch(" frontend/src --include=*.ts --include=*.tsx
  frontend/src/lib/api.ts:69:   return fetch(`${API_BASE}${path}`, {
  frontend/src/lib/api.ts:80:   const response = await fetch(`${API_BASE}/auth/refresh`, {
  frontend/src/app/page.tsx:15: const response = await fetch(`${API_BASE}/settings`, { cache: "no-store" });

  $ grep -rn "NEXT_PUBLIC_API_BASE_URL" frontend/src
  frontend/src/lib/api.ts:11:   process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  frontend/src/app/page.tsx:4:  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  ```

  The behaviour itself is correct and was re-verified: the server-rendered HTML
  reads "3 neighbours check it over" / "Before a ballot, 3 residents drawn at
  random …" against the seeded `jury_size = 3`.
- **Suggested fix:** export a server-side read from `api.ts` (or a sibling the
  rule names) and call that from `page.tsx`, so one module still owns every
  call to the API and the base URL is declared once.

### [MEDIUM] `jury_review_days` is seeded and readable but consulted by nothing

- **Where:** `backend/services/juries.py::duties_for`,
  `backend/services/cycles.py::view` (both omit it);
  `backend/services/settings.py::SPECS` (declares it)
- **Document:** DEMOCRACY.md §10.1, §8.2, §7.4
- **What the document requires:** §10.1 — "The timers (`jury_review_days`,
  `ballot_window_days`) exist as settings and are **displayed as 'would close
  on …'** but do not fire." §8.2 — "Each accepts or declines within
  `jury_review_days`."
- **What the code does:** `ballot_window_days` is honoured —
  `cycles.open_ballot` returns `would_close_on` and `cycles.view` repeats it.
  `jury_review_days` has no counterpart anywhere: `GET /juries/mine` tells a
  drawn juror what they may do but never when the window shuts, and
  `GET /cycles/{id}` reports `jury_review_started_at` with no "would close on".
  The only two places the key is named in the whole backend are its own
  `SettingSpec` and one line of the summary document's prose.
- **Evidence:**

  ```
  $ grep -rn "jury_review_days" backend/ frontend/src/ --include=*.py --include=*.tsx | grep -v test
  backend/services/summaries.py:266:   f"jury_review_days = {values['jury_review_days']}"
  backend/services/settings.py:91:     SettingSpec("jury_review_days", "int",
  ```

  and from the walkthrough, a drawn juror's whole duty payload — no deadline in
  it:

  ```
  $ GET /juries/mine   [ben]
    {"duties": [{"juror_id": 1, "seat": 1, "status": "drawn", "cycle_id": 1,
                 "cycle_number": 1, "cycle_state": "jury_review",
                 "community": {...},
                 "what_you_can_do": "You can look at every solution that qualified …",
                 "items": []}], "note": "Jurors are anonymous to the public …"}
  ```
- **Suggested fix:** compute `would_close_on = jury_review_started_at +
  jury_review_days` in `juries_service.duties_for` and in `cycles_service.view`,
  from the cycle's `settings_snapshot`, exactly as the ballot window is done.

### [MEDIUM] The solution page never shows the "Jury notes" every juror is promised

- **Where:** `frontend/src/app/solutions/[id]/PageClient.tsx` (the `Solution`
  type and the render both omit `jury_notes`); backend
  `backend/services/juries.py::jury_notes_for_solution` supplies them
- **Document:** DEMOCRACY.md §8.3
- **What the document requires:** "Each juror's category and reason are
  recorded and **every one is published**, whether or not it reached a
  majority: **on the solution's page under 'Jury notes'** from the moment the
  ballot opens, and in the summary document (§11.2). A juror is told exactly
  this when they submit."
- **What the code does:** `GET /solutions/{id}` returns a fully-formed
  `jury_notes` block, and the platform tells the juror at submission time that
  "Your reason will be published with the results." The page that is supposed
  to carry it does not declare the field, so nothing renders. The summary
  document half is correct and was verified. This is the same shape as audit
  run 4's FIX-30 (backend done, UI half missing).
- **Evidence:** the field the API returns —

  ```
  $ grep -n "jury_notes" backend/services/solutions.py
  367:  "jury_notes": await juries_service.jury_notes_for_solution(session, solution.id),
  ```

  and every mention of a jury in the page that should render it:

  ```
  $ grep -n -i "jury\|juror\|held back\|holdback" frontend/src/app/solutions/\[id\]/PageClient.tsx
  (no output)
  ```

  The published document, by contrast, carries them correctly — from this run's
  summary, the minority concern on the passed item:

  ```json
  "juror_concerns": {
    "label": "Juror concerns (1 of 3 seated)",
    "reasons": [{"juror": "Juror 3 of 3", "category": "incomplete",
                 "reason": "The solution does not say who pays for the refuge island …"}]
  }
  ```
- **Suggested fix:** render `jury_notes` on `/solutions/[id]` under the heading
  "Jury notes", with each note attributed "Juror n of m" exactly as the
  document and the API already spell it.

### [MEDIUM] Comments and amendments never display their AI-influence figure

- **Where:** `frontend/src/components/Comments.tsx::CommentNode`;
  `frontend/src/app/umbrellas/[id]/PageClient.tsx` (amendment list);
  `frontend/src/app/solutions/[id]/PageClient.tsx` (amendment list)
- **Document:** DEMOCRACY.md §6 and §9.5; CLAUDE.md §5
- **What the documents require:** §6 — "Every comment carries the author's
  display, timestamp, **and AI influence** (always 0% until the writing assist
  exists)." §9.5 defines `ai_contribution_percentage` for "Post, solution
  version, comment, amendment" alike, and says the label "exists now so that
  the promise is visible before it is non-trivial."
- **What the code does:** the backend returns `ai_influence` on every comment
  and every amendment (`ai_log.influence(...)` in `comments_service.thread` and
  in `umbrellas_service._dominant_detail`). The comment component renders
  author, text, timestamp, the edited flag and the vote buttons, and drops the
  field; the amendment lists on both pages do the same. The four places the
  label *is* rendered — feed item, post, solution, umbrella problem report and
  umbrella solution — are correct.
- **Evidence:**

  ```
  $ grep -n "ai_influence" frontend/src/app/*/PageClient.tsx frontend/src/app/*/*/PageClient.tsx frontend/src/components/Comments.tsx
  app/feed/PageClient.tsx:144:          <AiInfluence influence={item.ai_influence} />
  app/posts/[id]/PageClient.tsx:115:     <AiInfluence influence={data.ai_influence} />
  app/solutions/[id]/PageClient.tsx:119: <AiInfluence influence={data.ai_influence} />
  app/umbrellas/[id]/PageClient.tsx:198: <AiInfluence influence={report.ai_influence} />
  app/umbrellas/[id]/PageClient.tsx:247: <AiInfluence influence={solution.ai_influence} />
  (components/Comments.tsx: no match; amendment blocks: no match)
  ```

  The backend supplies it on every comment — from this run's thread:

  ```json
  {"id": 3, "author": "BenO-768615", "text": "Reply number 2.", "depth": 1,
   "ai_influence": {"ai_contribution_percentage": 0,
                    "label": "AI assistance on this platform: 0%",
                    "explanation": "This is the share of the text that was written by AI …"}}
  ```
- **Suggested fix:** render `<AiInfluence>` in `Comments.tsx` and in both
  amendment lists, using the component that already exists.

### [LOW] Blocking file IO still reached from `async def`, in the two files the new AST check cannot see

- **Where:** `backend/clients/ollama.py::load_prompt` (called from
  `OllamaClient.generate`); `backend/seed.py::_load_yaml` (called from
  `seed_settings`, `seed_geography`, `seed_officials`, `seed_umbrellas`) and
  `backend/seed.py::seed_terms`
- **Document:** CLAUDE.md Law 11
- **What the document requires:** "Every IO operation is `async`. … No blocking
  calls inside `async` code."
- **What the code does:** FIX-31 fixed `export.py` and added
  `test_layering.py::test_no_blocking_file_io_inside_async_def`, but that check
  walks only `backend/services` and `backend/jobs` and only inspects an `async
  def`'s own body. `load_prompt` is a plain `def` doing `path.exists()` and
  `path.read_text()`, reached one frame down from `async def generate` on the
  live request path (it is `lru_cache`d, so it blocks once per prompt file per
  process). `seed.py`'s `_load_yaml` does the same and is called directly from
  four `async def` seeders; `seed_terms` reads three files inline in its own
  `async def` body. The file that already carries the comment "the rule makes
  no CLI-path exception" is the one still breaking it.
- **Evidence:**

  ```
  $ grep -n "read_text\|\.exists()" backend/clients/ollama.py backend/seed.py
  backend/clients/ollama.py:57:  if not path.exists():
  backend/clients/ollama.py:62:  text = path.read_text(encoding="utf-8")
  backend/seed.py:120:           if not path.exists():
  backend/seed.py:125:           data = yaml.safe_load(path.read_text(encoding="utf-8"))
  backend/seed.py:437:           if not path.exists():
  backend/seed.py:439:           version = version_file.read_text(encoding="utf-8").strip()
  backend/seed.py:449:                   privacy_policy_md=privacy_file.read_text(encoding="utf-8"),
  backend/seed.py:450:                   terms_of_service_md=terms_file.read_text(encoding="utf-8"),

  $ grep -n "_load_yaml\|^async def" backend/seed.py
  119: def _load_yaml(path: Path) -> dict:
  140: async def seed_settings(...)        142:  data = _load_yaml(SETTINGS_FILE)
  177: async def seed_geography(...)       178:  data = _load_yaml(GEOGRAPHY_FILE)
  321: async def seed_officials(...)       323:  data = _load_yaml(OFFICIALS_FILE)
  366: async def seed_umbrellas(...)       368:  data = _load_yaml(UMBRELLAS_FILE)
  426: async def seed_terms(...)
  ```
- **Suggested fix:** wrap both in `asyncio.to_thread` the way
  `_read_cities_csv`, `_write_export_file` and `email._send_smtp` already are,
  and widen the AST check to `backend/clients` and `backend/seed.py` and to
  sync helpers called from an `async def`.

### [LOW] One amendment author can settle a similarity flag as "different", which §5.4 grants only for "same"

- **Where:** `backend/services/similarity.py::decide`
- **Document:** DEMOCRACY.md §5.4
- **What the document requires:** "When `similarity_confirm_min` (Demo 1: 2)
  distinct users, **or either amendment's author**, press **Same**, the newer
  amendment is marked `merged_into` the older … When **the same number** press
  **Different**, the flag is dismissed and recorded." The author shortcut is
  written for `Same` only.
- **What the code does:**

  ```python
  if len(same_votes) >= needed or author_pressed_same:
      decided = "same"
  elif len(different_votes) >= needed or author_pressed_different:
      decided = "different"
  ```

  One press by either author also ends the question as `different`, dismissing
  a flag that two other members might have merged, and writing `rejected` to
  the AI action's `human_outcome`.
- **Evidence:** the source above; `similarity.decide` is the only path that
  sets `amendment_similarity.decision`.
- **Suggested fix:** drop `or author_pressed_different`, or extend §5.4 to say
  the author shortcut cuts both ways — but say which.

### [LOW] The write limiter is a fixed window, not the token bucket the document names

- **Where:** `backend/middleware.py::WriteRateLimitMiddleware`
- **Document:** ARCHITECTURE.md §5
- **What the document requires:** "Every `POST`/`PUT`/`PATCH`/`DELETE` passes
  through a Redis **token-bucket** keyed by user id (or IP when
  unauthenticated), limit `RATE_LIMIT_WRITE_PER_MINUTE`."
- **What the code does:** `incr_with_expiry(key, 60)` — a fixed 60-second
  window counter, as the class's own docstring says ("A fixed window of
  `RATE_LIMIT_WRITE_PER_MINUTE` writes per caller"). A fixed window lets a
  caller send up to twice the limit across a window boundary, which a token
  bucket does not. The limit itself works: this audit's own walkthrough was
  429'd nine times and backed off on `Retry-After`.
- **Evidence:**

  ```
  $ GET/POST bursts during the walkthrough
    -> HTTP 429 {"error": "rate_limited",
                 "message": "You are sending changes faster than the platform
                             accepts them. Try again in 12 seconds."}
  $ grep -c "HTTP 429" walkthrough.txt
  9
  ```
- **Suggested fix:** either implement the bucket (a Redis counter plus a
  refill timestamp) or change ARCHITECTURE §5 to say "fixed window"; the
  document should not name an algorithm the code does not use.

### [LOW] `ip_hash` is an unsalted SHA-256 of the IP address

- **Where:** `backend/services/security.py::hash_ip`
- **Document:** CLAUDE.md §7; DATABASE.md §3.5
- **What the documents require:** §3.5 says `terms_acceptances` "contains no
  PII beyond the user link". CLAUDE §7: "When in doubt, choose the more secure
  option even if it takes longer to build."
- **What the code does:** `hashlib.sha256(ip.encode()).hexdigest()` with no
  salt or pepper. The whole IPv4 space is 2³² candidates; a stored hash is
  therefore reversible to the address in seconds by anyone who reads the table,
  so the row does hold a recoverable identifier.
- **Evidence:** the two-line function, and DATABASE §3.5's claim beside it.
- **Suggested fix:** HMAC the address with a key from `.env` (or truncate to a
  /24) so the stored value cannot be reversed by enumeration.

### [LOW] Three reference columns are `VARCHAR(n)` where DATABASE §3.6 says `char(n)`

- **Where:** `backend/models.py::State.abbreviation`, `::County.fips`,
  `::City.fips`
- **Document:** DATABASE.md §3.6 and §1
- **What the document requires:** §3.6 — "`states`: … `abbreviation` char(2)
  UNIQUE. `counties`: … `fips` char(5) UNIQUE. `cities`: … `fips` char(7)
  UNIQUE NULL." §1's "where this document writes `char(64)` for a hash column,
  read `VARCHAR(64)`" was added after audit run 4 and is scoped to hash
  columns only.
- **What the code does:** all three are `VARCHAR`. The choice is the better one
  — `CHAR` would space-pad — which is precisely the reasoning §1 already
  records for hashes; it simply has not been extended here.
- **Evidence:**

  ```
  states   | abbreviation character varying(2) NOT NULL
  counties | fips character varying(5) NOT NULL
  cities   | fips character varying(7)
  ```
- **Suggested fix:** widen DATABASE §1's sentence to cover every fixed-width
  reference column, or change the three models; the code is almost certainly
  right and the document almost certainly out of date.

### [LOW] The style brief's "California photography in page headers" is unbuilt and is not named as I-28's residue

- **Where:** `frontend/src/components/ui.tsx::PageHeader`; every page
- **Document:** ARCHITECTURE.md §9, style brief
- **What the document requires:** "mobile-first; plain language; one accent
  colour; **California photography in page headers**; every page works with
  images disabled".
- **What the code does:** the platform ships no `<img>`, no `next/image`, and
  no `url(...)` in any stylesheet, so the images-off requirement passes
  trivially — because there are no images to disable. That is a legitimate
  build decision, but TODO.md marks **I-28** `[~]` with the residue named as
  the missing screen-reader and browser runs only; the missing photography
  appears only as a parenthetical inside the images-off evidence.
- **Evidence:**

  ```
  $ grep -rn "next/image" frontend/src            (no output)
  $ grep -n "url(" frontend/src/app/globals.css   (no output)
  $ for every one of the 25 routes: <img>/background-image count = 0
  ```
- **Suggested fix:** either add the header imagery or name it explicitly as
  I-28's open residue, so a `[~]` says what is actually missing.

### [LOW] The `mailto:` message body is composed in a router

- **Where:** `backend/routers/summaries.py::_mailto`
- **Document:** ARCHITECTURE.md §2; DEMOCRACY.md §11.5
- **What the documents require:** §2 — "A router parses the request into a
  Pydantic model, calls **one** service function, and shapes the response. **No
  logic.**" §11.5 fixes what the body contains.
- **What the code does:** the router builds the recipient list, the subject,
  the absolute URL and the fixed sentences of the §11.5 message itself and
  URL-encodes them. `test_layering.py` does not catch it because `_mailto` is a
  module-level function, not a second service call. The content is correct —
  the decoded body carries only the fixed text, the absolute URL and the hash,
  and no user data.
- **Evidence:** the decoded body from this run:

  ```
  I am a resident of this community. These are the results of our ballot this
  cycle, voted on by residents and published in full:

  http://localhost:3000/summaries/city/408/1

  Document fingerprint (SHA-256): c70c5cc901a15f12d8d21f6aa6f6b75bb55115e3d69cb128105365eeead4ad2f

  The page explains every rule that produced these results and how to check
  that the document has not been altered.
  ```
- **Suggested fix:** move `_mailto` into `summaries_service` and return it as
  part of the page data the one service call already produces.

### [LOW] An expired export is still downloadable until the hourly job runs

- **Where:** `backend/routers/me.py::download_export`,
  `backend/services/export.py::get_export`
- **Document:** DATABASE.md §3.11; ARCHITECTURE.md §7
- **What the documents require:** `expires_at` is "the window a person has to
  collect their own data export"; `expire_exports` runs hourly and deletes the
  files.
- **What the code does:** `get_export` checks ownership only, and the router
  checks `file_path is None`. Between `expires_at` and the next hourly sweep —
  up to an hour — the file is still served, so the window is
  `EXPORT_FILE_HOURS` plus up to one hour rather than `EXPORT_FILE_HOURS`.
- **Evidence:** `get_export` raises only `NotFound` and `Forbidden`; no
  comparison against `expires_at` exists anywhere in `export.py` outside
  `expire_exports`.
- **Suggested fix:** refuse the download when `row.expires_at < now`,
  independently of whether the file has been swept.

### [NOTE] Whole-page endpoints embed lists that grow without bound

`GET /umbrellas/{id}` returns every problem report, every solution, every
top-level comment with its whole reply tree, every amendment of every dominant
solution with its full diff, and every reference, in one payload. `GET
/results` returns every past cycle of all three of a user's communities.
`test_pagination.py` classifies both as `DETAIL_ENDPOINTS` deliberately, and
audit runs 1–4 never flagged them, so this is an observation rather than a
finding: at Demo 1 size the payloads are small, but the umbrella page is the
one page a real workshop lives on, and CLAUDE §8 promises a platform that
"works on low-end devices and slow connections". Worth a decision before the
friends beta rather than after.

### [NOTE] No browser was available, so the frontend was checked structurally

The sandbox still cannot download a browser (TODO.md technical debt, unchanged).
Every one of the 25 routes in ARCHITECTURE §9 was fetched from a production
`next start` against the live backend and returned 200 with a distinct
`<title>`, exactly one `<h1>`, a skip link, a `<nav aria-label="Main">` and a
`<main id="main">`; the client-side data layer was checked by reading the
source and by exercising every endpoint it calls directly. Keyboard traversal
and a screen-reader pass could not be run. The claims in this report about what
a page *renders* are therefore claims about its source and its served HTML.

### [NOTE] Dominance did not flap in this run, and the run is too small to answer §7.1's open question

DEMOCRACY §7.1 asks the audit to "report how often the status flips". In this
audit's cycle the status changed twice, both times `false → true`, and never
back; `reconcile.py` then reported `"dominance_changes": []`. With
`dominant_min = 3`, `dominant_pct = 5` and seven active users the threshold was
1, so the boundary was never anywhere near a real vote count. Answering the
hysteresis question needs a community large enough for the percentage arm of
`threshold()` to bind.

### [NOTE] `POST /posts` with `category_choice: "ai"` reached `label_status: "labeled"` on the real model, first attempt

Worth recording because the tracker's technical debt says the opposite is
common. `llama3.2` at temperature 0, with the `format` schema from
`ai/prompts/labeler.md`, filed a single-community post correctly and returned
`confidence 0.8`; it also answered for one community the author never selected
(`city:1`), which the labeler discarded and recorded under
`output.repeated_or_unlisted_communities` exactly as DEMOCRACY §9.1 requires.
The defence works.

---

## Previously reported, still present

All ten findings from audit run 4 are fixed, and each was re-verified
independently rather than read from the build's evidence: no author, name or
user id of any kind survives anywhere in a published summary or its PDF
(FIX-28); a fifth-level reply attaches under the depth-cap comment's own parent
(FIX-29); the umbrella page renders the `recommending` indicator (FIX-30);
`export.py`'s file IO runs through `asyncio.to_thread` (FIX-31);
`EXPORT_FILE_HOURS` is required configuration with no default (FIX-32); the
password message says bytes (FIX-33); the landing page reads `jury_size` from
`GET /settings` (FIX-34); both export jobs log `job_start`/`job_end` with a
`job_id` (FIX-35); `test_authorization.py` walks the live route table (FIX-36).
Audit runs 1–3's findings were spot-checked and remain fixed: every list
endpoint refuses `limit=500` with 422, `POST /posts/{id}/label/*` require a
verified user, a redrawn jury is superseded rather than deleted, every
hold-back is published whether or not it reached a majority, the `mailto:` URL
is absolute, `npm audit --audit-level=high` is clean, and no endpoint exists
that ARCHITECTURE §6 does not list.

One item is fixed where it was named and still present elsewhere:

- **Blocking file IO inside `async def`** — raised as `LOW` in audit run 2
  (fixed in `seed.py`'s CSV read only), raised again as `MEDIUM` in audit run 4
  (fixed in `export.py`, with an AST check added). It is still present in
  `backend/seed.py::_load_yaml` / `::seed_terms` and in
  `backend/clients/ollama.py::load_prompt`, which the AST check's scope
  (`backend/services`, `backend/jobs`, direct calls only) cannot reach. Third
  audit in a row; reported above as a `LOW` with the scope gap named.

---

## Checks passed

**§4.1 Constitution**

- Ballot-vote exposure (always `CRITICAL`) — clean. Five signed-in readers and
  an administrator each read `GET /cycles/{id}/ballot`; each saw only their own
  `my_vote` and no payload contained the string `voter_id`.
  `GET /admin/users/{id}` returns the sentence "Not available to anyone but the
  voter." `my_ballot_votes` and `ballot_votes_of_user` are the only two reads
  of a vote row with a voter id, filtered to that voter, called from the ballot
  view and the user's own export respectively; every other read is a `GROUP BY`
  count.
- Vote weighting (always `CRITICAL`) — clean. `votes_repo.tally` groups by
  `direction`; `cycles_repo.item_tallies` groups by `choice`.
  `voter_verification_level` is written at cast time and read only by
  `voter_verification_mix`, which produces the aggregate sentence §11.2 item 1
  requires. No admin, verification or reputation term appears in any counting
  path; `influence_score` is present, commented deprecated, and written by
  nothing.
- Law 7 order — every AI result is preceded by its row.
  `labeling.label_post` records the `ai_actions` row before any `labels` row,
  any `post_communities.umbrella_id`, any solution or any status change;
  `references.recommend` records before any reference row; `similarity` records
  per pair before any flag. Unparseable model output is itself recorded with
  `output.error`. `ai_actions.human_outcome_*` can be set once and never
  changed.
- Law 8 — no threshold, window or size is a literal. All 22 DEMOCRACY §7.4
  keys are seeded, readable at `GET /settings`, printed in the summary's
  `settings_in_force` and in its "How this was produced" paragraphs, and (with
  the one exception reported above) consulted by the code their section names.
  The only numeric constants in the services are the character-length limits
  DEMOCRACY states in prose and never lists as settings.
- Law 9 — `rules.py` carries the full plain-English explanation as its module
  docstring, `RULES_VERSION = "rules-v1"`, and a version label per ordering
  rule; `rules_version` is printed in every summary and on `GET /settings`;
  `feed-v0`'s rule is printed on the feed response.
- Law 10 — `grep -rn "os.environ" backend/ | grep -v settings_env.py` empty.
- Law 11 — no synchronous database or HTTP call in any `async def`; the two
  file-IO exceptions are reported above as `LOW`.
- Law 12 — `grep -rn "except:\s*$\|except: pass\|except Exception: pass"`
  empty; `grep -rn "TODO\|FIXME" backend/ frontend/src/` empty; every broad
  `except` logs; the 500 handler returns `{error, message, request_id}` with no
  stack trace.
- Law 1 — `posts_service.create` refuses a post with no solution text, in the
  same transaction as the `post_solutions` rows.
- Law 3 — `influence_score` deprecated in `models.py`, written by nothing.
- Law 5 — every multi-table write is one service function in one session.
- Law 13 — every body is a Pydantic model; every query is parameterized
  through SQLAlchemy; bcrypt cost 12; policy enforced server-side; every write
  method passes the limiter.
- ARCHITECTURE §2 router rule — `test_layering.py` passes: no router imports a
  repository, client or job, none touches the session, and no endpoint calls
  more than one service function beyond a `require_*` resolver.

**§4.2 Specification conformance**

- Schema: 37 tables, 15 Foundation + 22 Iteration, exactly DATABASE §2's lists.
  Every column, type, nullability, default, unique constraint, partial index
  and enum in DATABASE §3 and §4 exists as written, including
  `uq_users_display_name` partial on `deleted_at IS NULL`,
  `uq_cycles_one_open_per_community` partial on `state <> 'published'`,
  `uq_juries_current_per_cycle` partial on `superseded_at IS NULL`,
  `uq_solutions_post_solution_umbrella` partial on `post_solution_id IS NOT
  NULL`, `ck_votes_direction`, `ck_amendment_similarity_ordered` and
  `juries.seated_count`. All 25 enum types carry exactly the documented values.
  Nothing undocumented exists (the three `char`/`varchar` spellings are
  reported above). `verify_schema.py` reports no drift on all five of its
  checks.
- Endpoints: all 72 live routes are in ARCHITECTURE §6, and every §6 entry
  exists with the documented method, path and auth dependency. Nothing
  undocumented. Every list endpoint accepts `cursor`/`limit`, defaults to 25 and
  refuses `limit=500` with 422; exactly the five documented fixed-size lists
  return whole.
- `threshold()` re-derived by hand for five cases including both boundaries —
  all five match the code (table in the evidence log).
- State machine: `ALLOWED_TRANSITIONS` is exactly DEMOCRACY §10.1, including
  `prepared → published` guarded by a zero-item check; every other jump raises
  `bad_cycle_transition`. No transition the code allows is absent from the
  document.
- Ballot order, solution order and comment order match §10.2, §3.3 item 4 and
  §6; qualification is a snapshot with all four §7.2 conditions returned
  separately; absorption uses the solution's supporters as the denominator and
  counts merged amendments' upvoters once.
- Jury: the draw excludes every version author, every `proposed`-amendment
  author, previous jurors within `jury_no_repeat_cycles` and every admin; the
  pool, the drawn ids and 32 random bytes from `secrets` are logged; a decline
  draws a replacement for the same seat; a non-responder is marked
  `no_response` and is not seated; a hold-back takes effect on strictly more
  than half the seated jurors, counted once at open; a redraw supersedes and
  never deletes.
- Summary: DEMOCRACY §11.2's five sections in order, with no author, name or
  user id anywhere; `summary_hash` computed once at publish over the canonical
  JSON; the hash list, the verifier, the downloadable JSON and the PDF all
  agree.

**§4.3 Security**

- bcrypt cost 12, never a raw password; refresh, verification and reset tokens
  stored only as SHA-256; rotation with `replaced_by_id`; replaying a replaced
  token revokes the whole chain in its own committed transaction and the newly
  issued token dies with it; logout blacklists the access token's `jti` in
  Redis and the next request is refused 401 `token_revoked`.
- Every write endpoint is behind `verified_user` or `admin_user` except the
  seven public `/auth/*` routes and the three own-account endpoints
  ARCHITECTURE §4 now names by design; an unverified account is refused
  `POST /posts` with 403 `email_not_verified` and still allowed
  `PATCH /me/display`.
- Every length limit is enforced in the service layer, not only in the form.
- No secret in any committed file, log line, error response or
  `ai_actions.output`; only `.env.example` is tracked; `.env`, `.venv` and
  `var/` are gitignored.
- Anonymization erases exactly DATABASE §3.1's column list and nothing else:
  `email → deleted+3@invalid`, `password_hash → '!'`, `real_name → ''`,
  `display_name → Former Community Member`, `date_of_birth → 1900-01-01`,
  `gender`/`political_party → prefer_not_to_say`, `last_active_at → NULL`,
  `deleted_at` set, `county_id`/`city_id` kept, all refresh tokens revoked,
  display mode reset. The civic rows survive and resolve; the published summary
  still verifies with an unchanged hash.
- The `mailto:` body carries the fixed text, the absolute URL and the hash, and
  no user data.

**§4.4 Evidence** — every re-runnable claim in fix run 4's HISTORY entry
reproduced (full log below).

**§4.5 Frontend** — all 25 ARCHITECTURE §9 routes exist and return 200 against
the live backend; every page has a distinct server-rendered `<title>` and
exactly one `<h1>`; no page ships an image of any kind, so every page works
with images blocked; no page computes a threshold, an eligibility or a status
client-side — every number displayed comes from the API; AI labels appear on
the feed, the post page, the solution page and both umbrella sections (the two
gaps are reported above); `tsc --noEmit`, `eslint` and `next build` are clean
and `npm audit --audit-level=high` finds nothing.

**§4.6 Documents** — CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md,
ARCHITECTURE.md, SANDBOX.md and AUDIT.md were touched only by the director's
own "Post-audit-N document updates" commits; no build or fix commit edited any
of them. Fix run 4's diff (`013ec19..b90ec20`) touches 19 files, all of them
named by its ten findings or their tests, plus `.env.example` and
`settings_env.py` as the brief allowed.

**TODO ids marked done that fail a check above:**

- **FIX-34** `[x]` — the fix is correct but was delivered by opening a second
  `fetch` call site in the frontend, against ARCHITECTURE §9.
- **I-28** `[~]` — the residue named is the missing screen-reader/browser runs;
  the style brief's "California photography in page headers" is also unbuilt
  and is not named.

No other id marked `[x]` failed a check.

---

## Evidence log

### Step 0 — pre-checks

```
$ echo $SANDBOX_NAME
ddc-demo-01-audit-5

$ git switch demo/01 && git branch --show-current
Switched to a new branch 'demo/01'
branch 'demo/01' set up to track 'origin/demo/01'.
demo/01

$ git status
On branch demo/01
Your branch is up to date with 'origin/demo/01'.
nothing to commit, working tree clean

$ ls audits/
demo-01-audit-1.md  demo-01-audit-2.md  demo-01-audit-3.md  demo-01-audit-4.md
→ this report is audits/demo-01-audit-5.md (K = 5)

$ touch backend/AUDIT_WRITE_TEST && echo WRITABLE || echo READ-ONLY
WRITABLE
$ rm -f backend/AUDIT_WRITE_TEST
$ git status --porcelain
(empty)
```

**The source tree was writable.** No write protection was in force, so the
discipline was the auditor's own; `git diff main...HEAD --stat` at the end of
this log shows nothing outside `audits/` and `HISTORY.md`.

```
$ docker compose --env-file .env -f infra/docker-compose.yml up -d
 Image postgres:16 Pulled
 Container ddc_postgres  Started
 Container ddc_redis     Started

$ docker compose ps
NAME           IMAGE         STATUS                    PORTS
ddc_postgres   postgres:16   Up (health: starting)     0.0.0.0:5432->5432/tcp
ddc_redis      redis:7       Up (health: starting)     0.0.0.0:6379->6379/tcp

$ alembic upgrade foundation@head && alembic upgrade iteration@head
INFO  [alembic.runtime.migration] Running upgrade  -> 25035d5b7ff5, Foundation initial schema — DATABASE.md §3.
INFO  [alembic.runtime.migration] Running upgrade  -> b4b4da0b6e54, Iteration schema — Demo 1 (DATABASE.md §4).

$ alembic heads
25035d5b7ff5 (foundation) (head)
b4b4da0b6e54 (iteration) (head)

$ curl -sS $OLLAMA_BASE_URL/api/tags
{"models":[{"name":"nomic-embed-text:latest",...},{"name":"qwen2.5vl:32b",...},
 {"name":"qwen2.5vl:7b",...},{"name":"llama3.1:8b",...},{"name":"llama3.2:latest",...}]}
```

Ollama reachable at the host LAN address; both models named in `.env`
(`llama3.2`, `nomic-embed-text`) present. **The suite and the walkthrough ran
against the real model, not the mock.**

The sandbox's Python is 3.14 with no `ensurepip`, so the virtual environment
was built with `uv venv` and `uv pip install -e ".[dev]"` rather than
`python3 -m venv`. (Fix run 4 hit the same wall and used
`pip install --break-system-packages`; `uv` is already on the image and leaves
the system interpreter alone.)

### The greps

```
$ grep -rn "TODO\|FIXME" backend/ frontend/src/
[exit=1 — no matches]

$ grep -rn "os.environ" backend/ | grep -v settings_env.py
[exit=1 — no matches]

$ grep -rn "except:\s*$\|except: pass\|except Exception: pass" backend/
[exit=1 — no matches]
```

### `verify_schema.py`

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

### The seed runner

```
$ python -m backend.seed --dry-run          (empty database)
pending writes: 590

$ python -m backend.seed --apply
...
pending writes: 590

$ python -m backend.seed --dry-run          (after --apply)
=== backend.seed — DRY RUN ===
[settings (DEMOCRACY.md §7.4)]   to write: 0   already present: 22   in database only: 0
[geography: state]               to write: 0   already present: 1    in database only: 0
[geography: counties]            to write: 0   already present: 58   in database only: 0
[geography: cities]              to write: 0   already present: 483  in database only: 0
[legal: terms version]           to write: 0   already present: 1    in database only: 0
[officials directory]            to write: 0   already present: 5    in database only: 0
[main categories (config mirror)] to write: 0  already present: 10   in database only: 0
[umbrellas (Iteration)]          to write: 0   already present: 10   in database only: 0
---
pending writes: 0
Nothing to do: every seed row is already in the database.
```

### The test suite

```
$ python -m pytest -q
........................................................................ [ 32%]
........................................................................ [ 64%]
........................................................................ [ 97%]
......                                                                   [100%]
222 passed, 2 deselected in 114.28s (0:01:54)

$ python -m pytest -q -m live
..                                                                       [100%]
2 passed, 222 deselected in 4.36s
```

Matches fix run 4's claim exactly (222 + 2 live).

### `reconcile.py --dry-run` (clean database, before the walkthrough)

```
{
  "started_at": "2026-09-18 21:51:06.989671+00:00",
  "corrected": false,
  "net_score_drift": [],
  "dominance_changes": [],
  "orphan_communities": [],
  "hash_mismatches": [],
  "counts_before": { "cities": 483, "counties": 58, "main_categories": 10,
                     "officials": 5, "settings": 22, "states": 1,
                     "terms_versions": 1, "umbrellas": 10, ... all others 0 },
  ...
}
```

### `threshold()` re-derived by hand against the code

```
case                                                        by hand   code  match
dominant in a 7-person community: pct=5, min=3, denom=7           1      1  True
    ceil(5/100 x 7) = 1; min(1, 3) = 1; max(1, 1) = 1
amendment among 12 supporters:    pct=25, min=3, denom=12         3      3  True
    ceil(25/100 x 12) = 3; min(3, 3) = 3; max(1, 3) = 3
ballot in a 142-person community: pct=10, min=5, denom=142        5      5  True
    ceil(10/100 x 142) = 15; min(15, 5) = 5; max(1, 5) = 5
edge — empty denominator:         pct=10, min=5, denom=0          1      1  True
    ceil(10/100 x 0) = 0; min(0, 5) = 0; max(1, 0) = 1
edge — exact percentage:          pct=25, min=9, denom=8          2      2  True
    ceil(25/100 x 8) = 2; min(2, 9) = 2; max(1, 2) = 2
```

### Every setting against DEMOCRACY §7.4

```
key                                DEMOCRACY §7.4             live  match
active_user_window_days                        30               30  True
dominant_pct                                    5              5.0  True
dominant_min                                    3                3  True
amendment_pct                                  25             25.0  True
amendment_min                                   3                3  True
ballot_pct                                     10             10.0  True
ballot_min                                      5                5  True
ballot_min_dominant_days                        3                3  True
similarity_threshold                         0.85             0.85  True
similarity_confirm_min                          2                2  True
jury_size                                       3                3  True
jury_no_repeat_cycles                           0                0  True
jury_review_days                                2                2  True
ballot_window_days                              7                7  True
ballot_pass_rule                  simple_majority  simple_majority  True
ballot_quorum_min                               1                1  True
comment_max_depth                               3                3  True
comment_edit_minutes                           15               15  True
label_retry_minutes                            10               10  True
references_ai_max_per_umbrella                  5                5  True
reference_reject_min                            2                2  True
min_signup_age                                 17               17  True
keys in DB not in §7.4: []
keys in §7.4 not in DB: []
```

### The auditor's own full cycle through the API

Written from ARCHITECTURE §6 and DEMOCRACY, not from the build's script, and
run against a database migrated and seeded from empty with the real Ollama
behind it. The complete transcript — every request and every response, 2,286
lines — was produced by the auditor's own client; the material steps are
reproduced here.

**Seven signups** (the three the brief asks for, plus a jury pool and one
administrator, because DEMOCRACY §8.1 excludes every solution author and every
admin from the draw), each `201`. An under-age applicant is refused and nothing
is stored:

```
$ POST /auth/signup   (date_of_birth 2015-01-01)
  -> HTTP 422
  {"error": "validation_failed",
   "message": "You need to be at least 17 to join. Nothing you entered has been saved.",
   ...}
```

**Verification links read from the console email backend's log**, then used —
seven `POST /auth/verify-email` → `200 {"message": "Email confirmed. You can now
post, vote and comment."}`.

**The administrator is made from the machine**, never from the web:

```
$ python backend/scripts/grant_admin.py <gus> --apply
GRANT administrator on gus.768615@example.com (user 7)

$ GET /auth/me   [gus]
  {"id": 7, ..., "is_admin": true, "verification_level": "unverified",
   "verification_explanation": "Unverified means the platform has confirmed your
    email address and nothing else. … verification level is reported in totals and
    never changes the weight of a vote.", "home_communities": [...3 communities...]}
```

**A post with two proposed solutions**, filed by the real labeler:

```
$ POST /posts   [ann]
  -> HTTP 201 {"id": 1, "label_status": "pending",
               "message": "Posted. It is being filed into an umbrella now …"}

$ GET /posts/1   (after the background job)
  "label_status": "labeled",
  "content_hash": "c39cee4f3c36621a27255294bdc49d7b24381f579b2bdb3cc9c2b7bcc8401c25",
  "communities": [{"community": {"level":"city","entity_id":408,"name":"San Jose"},
                   "umbrella_id": 2, "umbrella_name": "Pedestrian Safety Near Schools",
                   "main_category": "Public Safety",
                   "label_shown_as": "AI-labeled, not yet reviewed by the author",
                   "confidence": 0.8, "solution_ids": [1, 2]}],
  "solution_texts": [{"id":1,"position":1,"content_hash":"c662c3d9…"},
                     {"id":2,"position":2,"content_hash":"6aebeab7…"}],
  "immutable_note": "Posts cannot be edited or deleted in this build. …"

$ POST /posts/1/label/confirm   [ann]
  -> 200 {"message": "Thank you — 1 filing confirmed. That is recorded in the public AI log."}
  → label_shown_as becomes "AI-labeled, confirmed by author"

$ GET /ai/actions?subject_type=post&subject_id=1
  {"id": 1, "action_type": "label", "demo_build": "demo-01",
   "model": "ollama:llama3.2", "prompt_file": "labeler.md",
   "prompt_hash": "5edbdd9cbeec6405372269be42a69312a3fb939a2cf24c1d343f6835fbd83651",
   "input_hash": "33dac54829b3d42a322d59550c3a0c81bd96ef0921b749570bb928379597e6c2",
   "output": {"umbrellas": [{"umbrella_id": 2, "community_level": "city",
                             "community_entity_id": 408},
                            {"umbrella_id": null, "community_level": "city",
                             "community_entity_id": 1}],
              "confidence": 0.8, "main_category": "Public Safety",
              "category_recognised": true, ...}}
```

**Five upvotes on each solution; an amendment; absorption at the threshold:**

```
$ POST /solutions/1/amendments   [cara]
  -> 201 {"id": 1, "absorption_threshold": 2,
          "message": "Proposed. It becomes the solution's text once enough of the
                      people who support that solution back your change."}

$ PUT /votes  (amendment 1, up)  [ben] -> {"net_score": 1, "absorbed": false,
                                           "absorption_threshold": 2, "solution_supporters": 5}
$ PUT /votes  (amendment 1, up)  [dev] -> {"net_score": 2, "absorbed": true,
                                           "new_version": 2, "status": "absorbed"}

$ GET /solutions/1
  "current_version": 2, "net_score": 5, "supporters": 5, "is_dominant": true,
  "dominant_threshold": 1, "ballot_threshold": 1, "absorption_threshold": 2,
  "versions": [
    {"version": 1, "written_by": "AnnR-768615",  "content_hash": "5fcc2f3f7e1f…"},
    {"version": 2, "written_by": "CaraN-768615", "from_amendment_id": 1,
     "content_hash": "7fad0061c856…"}]
```

**Prepare — snapshot and jury draw:**

```
$ POST /admin/cycles/prepare {"level":"city","entity_id":408}   [gus]
  -> 200 {"cycle_id": 1, "number": 1, "state": "jury_review",
          "active_users_at_prepare": 7,
          "items": [{"solution_id":1,"version":2,"net_score":5},
                    {"solution_id":2,"version":1,"net_score":5}],
          "considered": [ …each solution with all four §7.2 conditions… ],
          "jury": {"jury_id": 1, "size_requested": 3, "eligible_pool_size": 4,
                   "drawn": 3, "note": null},
          "zero_item_note": null}
```

The pool is 4, not 7: Ann (author of both solutions), Cara (author of version
2) and Gus (administrator) are excluded, exactly as DEMOCRACY §8.1 says.

**Jury — accept, then hold-backs on both sides of the majority line:**

```
$ GET /juries/mine  →  duties for ben (seat 1), dev (seat 2), eli (seat 3) only
$ POST /jurors/{1,2,3}/accept  → all "accepted"

$ POST /ballot-items/2/holdback  [ben]  category not_actionable  -> 200
$ POST /ballot-items/2/holdback  [dev]  category not_actionable  -> 200   (2 of 3 = majority)
$ POST /ballot-items/1/holdback  [eli]  category incomplete      -> 200   (1 of 3 = minority)
  each: {"note": "Recorded. Jurors do not see each other's hold-backs until the
                  ballot opens. Your reason will be published with the results."}
```

**Open, vote, close:**

```
$ POST /admin/cycles/1/open   [gus]
  -> {"state": "open", "jurors_drawn": 3, "jurors_seated": 3,
      "items_votable": 1, "items_held_back": 1,
      "would_close_on": "2026-09-25T21:57:02.382339Z"}

$ PUT /cycles/1/ballot/1/vote  [ann] yes, [ben] yes, [cara] no
  each -> {"your_vote": "...", "note": "You can change this until the ballot
                                        closes. Only you can see it."}

$ POST /admin/cycles/1/close  [gus]
  -> {"state": "closed", "results": [{"ballot_item_id": 1, "yes": 2, "no": 1,
                                      "result": "passed"},
                                     {"ballot_item_id": 2, "result": "held_back"}]}
```

**CRITICAL trap 1 — one vote, one reader.** Each account read the same open
ballot:

```
$ GET /cycles/1/ballot   [ann]       'voter_id' anywhere in payload: False
                                     this reader's own votes: [[1,"yes"], [2,null]]
$ GET /cycles/1/ballot   [ben]       'voter_id': False   own votes: [[1,"yes"], [2,null]]
$ GET /cycles/1/ballot   [cara]      'voter_id': False   own votes: [[1,"no"],  [2,null]]
$ GET /cycles/1/ballot   [dev]       'voter_id': False   own votes: [[1,null],  [2,null]]
$ GET /cycles/1/ballot   [gus ADMIN] 'voter_id': False   own votes: [[1,null],  [2,null]]

$ GET /admin/users/1     [gus ADMIN]
  {"id": 1, "display_name": "AnnR-768615", "verification_level": "unverified",
   "jury_history": [],
   "ballot_votes": "Not available to anyone but the voter. This endpoint never
                    returns them, by design (DEMOCRACY.md §13)."}
```

Dev, who did not vote, and the administrator both see `null` where Ann, Ben and
Cara each see their own choice and nobody else's.

**Publish, and the hash round-trip computed by the auditor:**

```
$ POST /admin/cycles/1/publish   [gus]
  -> {"summary_hash": "c70c5cc901a15f12d8d21f6aa6f6b75bb55115e3d69cb128105365eeead4ad2f", ...}

$ GET /summaries/city/408/1/verify
  {"stored_hash":    "c70c5cc901a15f12d8d21f6aa6f6b75bb55115e3d69cb128105365eeead4ad2f",
   "recomputed_hash":"c70c5cc901a15f12d8d21f6aa6f6b75bb55115e3d69cb128105365eeead4ad2f",
   "match": true, "verdict": "This document is unchanged since it was published."}

$ GET /summaries/city/408/1/json   then SHA-256 locally, in the auditor's own process
  bytes downloaded from /json:      5863
  SHA-256 computed locally:         c70c5cc901a15f12d8d21f6aa6f6b75bb55115e3d69cb128105365eeead4ad2f
  summary_hash stored by platform:  c70c5cc901a15f12d8d21f6aa6f6b75bb55115e3d69cb128105365eeead4ad2f
  MATCH: True

$ GET /summaries/hashes
  {"summaries": [{"community": {"level":"city","entity_id":408,"label":"San Jose (city)"},
                  "cycle_number": 1, "summary_hash": "c70c5cc9…",
                  "url": "/summaries/city/408/1"}], "next_cursor": null}

$ GET /summaries/city/408/1/pdf  -> HTTP 200, 4998 bytes, starts b'%PDF-1.4'
```

**Nothing personal in the document.** The canonical JSON was searched for all
seven accounts' real names and all seven display names: **none found.** The
published Results and Held-back sections:

```json
"results": [{
  "position": 1, "umbrella": "Pedestrian Safety Near Schools",
  "solution_text": "Paint a high-visibility crosswalk, install a pedestrian refuge island, and add a rapid-flashing beacon at the Cottle Road crossing.",
  "solution_version": 2,
  "solution_version_hash": "e4c221b11bebcf6b066686eecdb24c41cd35ade09bfb1b4fa7aaee14f838f76b",
  "workshop_note": "Proposed and refined in the San Jose workshop",
  "solution_url": "http://localhost:3000/solutions/1",
  "ai_influence_percentage": 0,
  "ai_influence_label": "AI assistance on this platform: 0%",
  "yes": 2, "no": 1, "result": "Passed",
  "juror_concerns": {"label": "Juror concerns (1 of 3 seated)",
                     "reasons": [{"juror": "Juror 3 of 3", "category": "incomplete",
                                  "reason": "The solution does not say who pays for the refuge island or when the work would happen."}]}
}],
"held_back": [{
  "position": 2, "umbrella": "Pedestrian Safety Near Schools",
  "solution_text": "Fund two crossing guards for the school's drop-off and pick-up hours every school day.",
  "workshop_note": "Proposed and refined in the San Jose workshop",
  "solution_url": "http://localhost:3000/solutions/2",
  "jury_reasons": [{"juror": "Juror 1 of 3", "category": "not_actionable", "reason": "Crossing guards are hired by the school district, not the city, so the city cannot act on this as written."},
                   {"juror": "Juror 2 of 3", "category": "not_actionable", "reason": "Crossing guards are hired by the school district, not the city, so the city cannot act on this as written."}]
}],
"header": {"community_name": "San Jose", "community_level": "city", "cycle_number": 1,
           "active_users_at_snapshot": 7, "members_who_voted": 3,
           "verification_mix": "3 voters: 3 unverified",
           "residency_note": "Residency is self-declared and unverified at this verification level.",
           "jury": "3 drawn, 0 replaced, 3 seated", "build": "demo-01"}
```

**The settings change was logged both ways.** `ballot_min_dominant_days` was
lowered to 0 to reach a ballot inside one day and restored to 3 afterwards,
each as an admin action with a reason:

```
$ GET /admin/log
  {"id": 7, "administrator": "GusA-768615", "action": "change_setting",
   "old_value": {"key": "ballot_min_dominant_days", "value": 0},
   "new_value": {"key": "ballot_min_dominant_days", "value": 3},
   "reason": "Audit run 5 walkthrough finished; restoring the documented Demo 1 default."}
  … and prepare_ballot, open_ballot, close_ballot, publish_summary, grant_admin,
    each with who, what, subject and values.
```

### Auth, the verification gate and anonymization

```
=== refresh rotation, reuse revocation, logout blacklist ===
login -> 200 | refresh cookie set: True
refresh #1 -> 200 | new access token differs: True | refresh token rotated: True
replaying the OLD refresh token -> 401 {'error': 'refresh_reused',
  'message': 'For your safety we signed you out of every device. Please sign in again.'}
the NEW token after a detected reuse -> 401 {'error': 'refresh_reused', ...}

GET /auth/me before logout -> 200
POST /auth/logout -> 200
GET /auth/me after logout -> 401 {'error': 'token_revoked',
                                  'message': 'That session has been signed out.'}

=== an unverified account cannot write, but owns its own account ===
POST /posts        as unverified -> 403 {'error': 'email_not_verified', ...}
PATCH /me/display  as unverified -> 200 {'public_name_mode': 'anonymous',
                                         'shown_as': 'Anonymous Community Member'}

=== DELETE /me on the author of the absorbed amendment ===
solution 1 version authors BEFORE: ['AnnR-768615', 'CaraN-768615']
DELETE /me -> 200
solution 1 version authors AFTER:  ['AnnR-768615', 'Former Community Member']
amendment author AFTER:            ['Former Community Member']
version content hashes unchanged:  True
summary still verifies after the deletion: True  c70c5cc9…
deleted person's real name in the published JSON: False
```

```
$ select ... from users where deleted_at is not null;
 id |       email       | password_hash | real_name |      display_name       | date_of_birth |      gender       |  political_party  | county_id | city_id | last_active_at | deleted
  3 | deleted+3@invalid | !             |           | Former Community Member | 1900-01-01    | prefer_not_to_say | prefer_not_to_say |        43 |     408 |                | t

live refresh tokens for that account: 0 of 2
display settings reset to:            display_name
their civic rows still present:       amendments 1 · workshop votes 2 · ballot votes 1 · solution versions 1
```

### The two HIGH findings, reproduced

The solution-edit transcript and the comment-edit reconcile output are pasted in
full under their findings above.

### Pagination

```
/umbrellas?community=city:408&limit=500                 422
/feed?limit=500                                         422
/ai/actions?limit=500                                   422
/admin/log?limit=500                                    422
/settings/history?key=jury_size&limit=500               422
/summaries/hashes?limit=500                             422
/communities/city/408/cycles?limit=500                  422
/solutions/1/amendments?limit=500                       422
/umbrellas/2/solutions?limit=500                        422
/umbrellas/2/comments?limit=500                         422
/umbrellas/2/references?limit=500                       422
--- the five documented fixed-size lists, which return whole ---
/geo/counties?limit=500                                 200
/settings?limit=500                                     200
/communities/city/408/officials?limit=500               200
```

### The route table against ARCHITECTURE §6

72 live routes; every one appears in §6 and every §6 entry appears here. Auth
column as FastAPI resolves it:

```
POST   /admin/cycles/prepare                       AdminUser
POST   /admin/cycles/{cycle_id}/close|open|publish|redraw-jury   AdminUser
GET    /admin/log                                  public
POST   /admin/posts/{post_id}/relabel              AdminUser
POST   /admin/settings                             AdminUser
POST   /admin/umbrellas/{id}/recommend-references  AdminUser
GET    /admin/users/{user_id}                      AdminUser
GET    /ai/actions                                 public
POST   /amendments/{id}/withdraw                   VerifiedUser
POST   /auth/{signup,verify-email,login,refresh,logout,forgot-password,reset-password}  public
GET    /auth/me                                    CurrentUser
POST   /ballot-items/{id}/holdback                 VerifiedUser
POST   /comments · PATCH/DELETE /comments/{id}     VerifiedUser
GET    /communities/{level}/{id}[/cycles|/officials]  public
GET    /cycles/{id}                                public
GET    /cycles/{id}/ballot                         OptionalUser
PUT    /cycles/{id}/ballot/{item_id}/vote          VerifiedUser
GET    /feed                                       OptionalUser
GET    /geo/counties[/{id}/cities]                 public
GET    /health                                     public
GET    /juries/mine                                VerifiedUser
POST   /jurors/{id}/{accept,decline}               VerifiedUser
GET    /legal/{cookies,current-version,privacy,terms}  public
DELETE /me · PATCH /me/display · POST /me/export · GET /me/export/{id}   CurrentUser
POST   /posts · POST /posts/{id}/label/{confirm,correct}   VerifiedUser
GET    /posts/{id}                                 public
PUT    /references/{id}/feedback                   VerifiedUser
GET    /results                                    VerifiedUser
GET    /settings · /settings/history               public
POST   /similarity/{id}/decide                     VerifiedUser
GET    /solutions/{id}                             OptionalUser
PATCH  /solutions/{id}                             VerifiedUser
GET    /solutions/{id}/amendments                  public
POST   /solutions/{id}/amendments                  VerifiedUser
GET    /summaries/hashes · /summaries/{level}/{id}/{n}[/json|/pdf|/verify]   public
GET    /umbrellas · /umbrellas/{id}[/comments|/references|/solutions]
POST   /umbrellas/{id}/{references,solutions}      VerifiedUser
PUT/DELETE /votes                                  VerifiedUser
TOTAL 72
```

### FIX-29, FIX-30, FIX-34 and FIX-35, re-verified

```
=== FIX-29: five replies deep with comment_max_depth = 3 ===
 id | parent_id | reply_to_comment_id | depth |        text
  2 |           |                     |     0 | Reply number 1.
  3 |         2 |                     |     1 | Reply number 2.
  4 |         3 |                     |     2 | Reply number 3.
  5 |         4 |                     |     3 | Reply number 4.
  6 |         4 |                   5 |     3 | Reply number 5.
→ the fifth is a sibling of the fourth under the third, pointing at what it answered.

=== FIX-30 ===
frontend/src/app/umbrellas/[id]/PageClient.tsx:385:
  <Notice>AI is looking for references…</Notice>

=== FIX-34 (server-rendered HTML of / against the seeded jury_size = 3) ===
  "3 neighbours check it over"
  "Before a ballot, 3 residents drawn at random look at what qualified. …"

=== FIX-35 (one real export run) ===
{"message":"job_start","job":"build_export","job_id":"9e50f840","export_id":1}
{"message":"job_end",  "job":"build_export","job_id":"9e50f840","export_id":1}
GET /me/export/1 -> 200, 4331 bytes
  civic_record keys: posts, solutions_you_started, amendments_you_proposed,
                     comments_you_wrote, workshop_votes, your_ballot_votes,
                     your_ballot_votes_note, jury_service
  own ballot votes: [{"cycle_id":1,"ballot_item_id":1,"solution_id":1,
                      "your_choice":"yes",
                      "your_verification_level_at_the_time":"unverified", …}]
```

### Every page in ARCHITECTURE §9, with the backend running

`next build` produced 25 routes; each was fetched from `next start` against the
live API.

```
route                                  | HTTP | <title>                                              | h1 | img
/                                      | 200  | Direct Democracy Cali                                |  1 |  0
/signup                                | 200  | Join your community · Direct Democracy Cali          |  1 |  0
/login                                 | 200  | Sign in · Direct Democracy Cali                      |  1 |  0
/verify-email                          | 200  | Confirming your email address · …                    |  1 |  0
/forgot-password                       | 200  | Reset your password · …                              |  1 |  0
/reset-password                        | 200  | Choose a new password · …                            |  1 |  0
/me                                    | 200  | Your account · …                                     |  1 |  0
/legal/privacy                         | 200  | Privacy policy · …                                   |  1 |  0
/legal/terms                           | 200  | Terms of service · …                                 |  1 |  0
/legal/cookies                         | 200  | Cookies · …                                          |  1 |  0
/settings                              | 200  | Every rule and its value · …                         |  1 |  0
/ai/actions                            | 200  | Everything AI has done here · …                      |  1 |  0
/admin/log                             | 200  | Everything an administrator has done · …             |  1 |  0
/admin                                 | 200  | Administrator controls · …                           |  1 |  0
/feed                                  | 200  | What people are working on · …                       |  1 |  0
/posts/new                             | 200  | Write down a problem · …                             |  1 |  0
/umbrellas/2                           | 200  | The workshop · …                                     |  1 |  0
/solutions/1                           | 200  | A solution · …                                       |  1 |  0
/ballot                                | 200  | The ballot · …                                       |  1 |  0
/jury                                  | 200  | Jury duty · …                                        |  1 |  0
/results                               | 200  | Results · …                                          |  1 |  0
/summaries/hashes                      | 200  | Every published fingerprint · …                      |  1 |  0
/summaries/city/408/1                  | 200  | Ballot results · …                                   |  1 |  0
/posts/1                               | 200  | A problem report · …                                 |  1 |  0
/cycles/1                              | 200  | A ballot cycle · …                                   |  1 |  0
```

**With images blocked:** the `img` column is the count of `<img>` and
`background-image` in each served page — zero everywhere;
`grep -rn "next/image" frontend/src` and `grep -n "url(" globals.css` are both
empty. Every page renders identically with images disabled because the platform
ships none.

Structure of a served page (`/settings`, trimmed):

```html
<a class="skip-link" href="#main">Skip to the main content</a>
<nav aria-label="Main" …>
<main id="main">
  <h1 class="text-2xl font-bold sm:text-3xl">Every rule, and the number it is set to</h1>
  <p role="status" …>Loading the rules…</p>
</main>
```

### Frontend toolchain

```
$ npm ci                        → 147 packages, found 0 vulnerabilities
$ npm audit --audit-level=high  → found 0 vulnerabilities
$ npx tsc --noEmit              → clean
$ npx eslint                    → clean
$ npx next build                → compiled successfully, 25 routes
```

### Secrets

```
$ git ls-files | grep -E "(^|/)\.env"
.env.example

$ git grep -nI -E "JWT_SECRET *= *[A-Za-z0-9]{16,}|password *= *['\"][^'\"]{8,}|api[_-]?key *= *['\"][A-Za-z0-9]{16,}" -- .
(no matches)
```

### The working tree at the end

```
$ git diff main...HEAD --stat
 HISTORY.md                 | <this run's paragraph>
 audits/demo-01-audit-5.md  | <this report>
 … plus the 236 files the build and the four fix runs already committed,
 unchanged by this run.

$ git status --porcelain
(empty — the only untracked files are .env, .venv/, var/ and __pycache__/,
 every one of them gitignored)
```

Nothing outside `audits/` and `HISTORY.md` was created, edited or deleted by
this audit.

---

## Document ambiguities

These are places where the auditor could not decide whether the code or the
document is right. They are for the director; nothing was resolved here.

1. **What an "edit" does to a permanent fingerprint.** DEMOCRACY §4.3 lets the
   author edit a solution before it is voted on, and §6 lets a comment author
   edit for fifteen minutes. CLAUDE Law 6 says a `content_hash` is "never
   modified", DATABASE §4.8 says `solution_versions` are "Immutable", and
   DATABASE §7 item 4 says a hash that does not recompute is "a critical alert,
   not a correction". Those four sentences cannot all hold while the two edit
   features exist. The code has picked a different answer in each place, which
   is what produced both `HIGH`s. Three coherent resolutions exist and the
   documents point at none of them: every edit creates a new hashed row; or an
   edited row's hash is recomputed and the rewrite recorded somewhere visible;
   or the edit features are withdrawn. The director's answer should land in
   Law 6 and in DATABASE §4.8 and §4.11, not only in the code.

2. **Whether "no logic in a router" covers composing a document's text.**
   ARCHITECTURE §2 says a router calls one service function and shapes the
   response, with no logic; `summaries.py::_mailto` composes the whole §11.5
   message inside the router. If assembling a documented, user-visible message
   body counts as shaping, the rule should say so, because `test_layering.py`
   is written to the narrower reading and will keep passing.

3. **Whether a whole-page endpoint may embed an unbounded list.**
   ARCHITECTURE §6 says every list endpoint paginates and names five
   exemptions; `GET /umbrellas/{id}` and `GET /results` are not list endpoints
   but do return lists that grow for ever. The build made the call
   deliberately and wrote it into `test_pagination.py`'s comments; it has never
   been written into a document. One sentence in §6 either way would settle it.

4. **Whether an amendment author may settle a similarity flag as
   "different".** DEMOCRACY §5.4 gives the author shortcut for "Same" only and
   says nothing about "Different"; the code grants both. Either the omission is
   deliberate — one author should not be able to block a merge two members
   want — or the sentence is simply incomplete.

5. **Whether `char(n)` in DATABASE §3.6 means what §1 now says it means for
   hashes.** §1's "read `VARCHAR(64)`" note was added for hash columns after
   audit run 4. `states.abbreviation`, `counties.fips` and `cities.fips` are
   `VARCHAR` for the same reason and are still documented as `char`. Almost
   certainly a document lag rather than a code fault, but the auditor cannot
   decide that for the director.

6. **Whether the style brief's "California photography in page headers" is
   still wanted.** ARCHITECTURE §9 asks for it; the build ships no image of any
   kind, which makes the images-off promise trivially true and the pages very
   fast. If the absence is now the intention, §9's style brief should say so;
   if not, I-28's `[~]` should name it.
