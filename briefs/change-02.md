# Build Brief — change/02-who-and-where

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — change-02 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is **change/02 — who
you are and where you post**: unincorporated residents, account editing,
the home-change rule, and a post form on which the AI labels the draft
**before** it is posted. It changes the Foundation schema for the first
time since Demo 1, so Foundation is under full rigor: real names and
real emails, as if real users exist.

Your branch is `change/02-who-and-where`: `git fetch origin && git switch
change/02-who-and-where && git merge --ff-only
origin/change/02-who-and-where`, then `git log --oneline -3` — the newest
commit must be the director's "change/02 brief". You cannot push to
`main` and must not try.

**Documents.** Part A is director-approved wording. Apply it
**verbatim**; do not improve, reflow, or reword anything else in those
files. If an anchor is not found exactly, stop that item, report the
file and anchor in HISTORY.md, and continue. Outside Part A you may not
edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md,
AUDIT.md, or SANDBOX.md.

**Silence and conflict.** CLAUDE.md wins, then this brief, then the
documents as amended. Where everything is silent, choose the smallest
thing that satisfies the constitution and record it under "Decisions
made". **Before building each item, ask of it: does this store, hash,
publish, or delete something the constitution says is resolved at read
time, immutable, or private?** (AUDIT.md §4.1.) If yes, stop the item
and report.

## Read first, in this order

1. `CLAUDE.md`, in full.
2. This brief, in full, **then apply Part A before writing any code.**
3. `DEMOCRACY.md` §2, §4.1, §7.4, §8.1, §9.1–9.2, §10.3 (as amended).
4. `DATABASE.md` §2, §3.1, §3.4, §3.10, §3.11, §4.3–4.7, §6; `ARCHITECTURE.md` §2, §3, §4, §6, §9, §10.
5. `AUDIT.md` §4.1; `HISTORY.md`, the last three entries; `TODO.md`.

## Step 0 — Pre-checks (paste each; stop if any fails)

1. `git branch --show-current`; `git log --oneline -3`.
2. `.env` from `.env.example`, `OLLAMA_BASE_URL` at the address SANDBOX.md §5 records, `BUILD_LABEL=change-02`; `curl -sS $OLLAMA_BASE_URL/api/tags` lists `llama3.2`, `llama3.1:8b`, and `EMBED_MODEL`.
3. Docker Compose up; both migration chains from empty; seed.
4. Full backend suite and `npm test` green **in a clean shell** before any change.

---

## Part A — Document changes (apply first, one commit: "change/02 documents")

### A1. DEMOCRACY.md

**§2.3** — replace the first paragraph (from `Every user has exactly one home city` through `are eligible to appear.`) with:

```
Every user has one home county and, unless they live in an
unincorporated area, one home city in that county, chosen at signup from
the geography tables: county first, then the city list for that county,
whose first choice is "Unincorporated — no city". A user with a city is
a member of three communities — city, county, California; an
unincorporated resident is a member of two — county and California —
and every page that lists "your communities" shows two and says why.
Membership determines what a user may vote on in a ballot and where
their posts are eligible to appear. One function answers "which
communities is this user a member of", and nothing else derives it:
`backend/services/communities.py::home_communities`.
```

**§2.3** — add at the end of the section (after the Minimum age paragraph):

```
**Changing home.** A user may change their home county and city from
the account page. The rules, each a plain refusal with its reason:

1. After a change, the next is allowed `home_change_cooldown_days`
   (Demo 1: 90) later. The first change after signup is always allowed —
   a wrong pick at signup is not penalised.
2. A user who is drawn or seated on a jury whose cycle is not yet
   published finishes that service first.
3. **A move never carries a vote into a ballot already under way.** A
   user may vote in a cycle only if their membership of that community
   began before the cycle was prepared (§10.3). Having left, they are no
   longer a member of the old community either, so a move during a
   ballot sits that ballot out in both places. California is unaffected;
   the county is unaffected by a move within it. The account page says
   all of this before the user confirms.

Workshop participation — posting, commenting, voting on solutions —
follows the new home at once. Everything already posted, said, or voted
stays where it was made (Law 6; CLAUDE §6). Every change is a row in
`user_home_changes` (DATABASE §3.12), which is the source for rules 1
and 3, belongs to the user's data export, and is deleted with the
account. Nobody reviews or flags accounts for moving: the rule is the
same for everyone and needs no judge (CLAUDE §3).
```

**§4.1** — replace the three bullets (from `- **Let AI decide** (default)` through `Demo 1 does not show this option.`) with:

```
- **The AI suggests, the author decides — before anything is posted**
  (default). When the author has written the problem and at least one
  solution and chosen their communities, they continue to "Where it
  goes" and the labeler runs at once on the draft (§9.1). For each
  chosen community the form shows the suggested umbrella — or "none of
  these fit" — and the author keeps it, changes it to another active
  umbrella, or chooses "None of these fit". Only then can they post.
  Editing the problem text or the communities afterwards marks the
  suggestion out of date, and it runs again. A community left at "none
  of these fit" is saved under the main category and is `needs_review`.
- **Choose myself** — the author skips the suggestion and browses the
  active umbrellas for their communities. Recorded as `author_selected`.
- **Post now, file later** — offered only when the AI cannot be reached:
  the post is saved and the background labeler files it when the AI is
  back, exactly as before this change.
- **Propose a new umbrella** — planned as its own change; it will sit
  beside "None of these fit".

**Governance levels on the form.** No community is pre-selected. A city
is shown by its name, a county as "<name> County", the state as
"California". An unincorporated author sees no city choice and the
note "You live in an unincorporated area, so you have no city
community. Your posts go to your county and California." A fourth
choice, "Federal — planned, not yet available", is shown disabled and
is never submitted.
```

**§4.1** — replace `A post is saved immediately. Labeling runs in the background; until it\ncompletes` with:

```
A post made from a suggestion or from the author's own choice is filed
the moment it is saved: its solutions are created in the same
transaction (below). A post made with "Post now, file later" is saved
immediately and labeled in the background; until that completes
```

**§7.4** — add two rows after `label_retry_minutes`:

```
| `home_change_cooldown_days` | §2.3 — days between changes of home county or city | 90 |
| `label_preview_max_per_hour` | §9.1 — suggestions one user may ask for in an hour; an abuse limit, public like every other number | 20 |
```

**§9.1** — replace the first paragraph (from `Assigns a post to a main category` through `and a\nconfidence in [0, 1].`) with:

```
Assigns a problem to a main category and, per selected community, to
the closest active umbrella — or to none, which is a correct answer
when no umbrella covers the problem, and the prompt says so. It runs on
Ollama, on the host GPU, in two places: on a **draft**, when the author
reaches "Where it goes" (§4.1), and in the background for a post saved
with "Post now, file later". Its prompt is a file:
`ai/prompts/labeler.md`. Its input is the problem text, the fixed
category list, and the umbrella names and statements for the relevant
communities. Its output is a main category, an umbrella id per
community (or none), and a confidence in [0, 1].

**A suggestion on a draft is an AI action like any other** (Law 7): the
row is written before the suggestion is shown, with subject
`label_preview`. The platform keeps the hash of the draft's problem
text and communities, never the text: a draft that is never posted
leaves no words behind, only the public fact that a suggestion was made
and not used. When the author posts, the label rows point at that same
action, and its human outcome is set once — `confirmed` if every
suggestion was kept, `corrected` otherwise. A user may ask for
`label_preview_max_per_hour` suggestions an hour; past that the form
says so and offers "Choose myself".
```

**§10.3** — replace `Eligibility: the voter's home community equals the cycle's\ncommunity.` with:

```
Eligibility: the voter is a member of the cycle's community **and
their membership of it began before the cycle's `prepared_at`** —
membership begins at signup, or at the user's latest home change that
changed that level's community (§2.3). A refused voter is told why in
one sentence.
```

**§14** — in the row beginning `| §3 one person, one vote |` (or, if no such row exists, add a new row after `| §3 identical ranking |`):

```
| §3 one vote, one community at a time | §2.3 Changing home: a public cooldown, and no vote in a ballot already under way; no account is judged or flagged |
```

### A2. DATABASE.md

**§3.1** — replace the `city_id` row with:

```
| `city_id` | int FK `cities` NULL | home city; NULL = unincorporated resident of `county_id` (DEMOCRACY §2.3); when set, must belong to `county_id` (checked in application); **kept** on deletion (CLAUDE §6) |
```

**Add after §3.11:**

```
### 3.12 `user_home_changes`

`id`, `user_id` FK `users` NOT NULL, `from_county_id` FK, `from_city_id`
FK NULL, `to_county_id` FK, `to_city_id` FK NULL, `changed_at`
timestamptz NOT NULL. Index `(user_id, changed_at)`. Insert-only. The
source for the cooldown and for ballot eligibility (DEMOCRACY §2.3,
§10.3). In the user's data export; **deleted** in the anonymization
transaction — a former member's past addresses are not part of the
civic record, their current community is.

### 3.13 `email_change_requests`

Same shape as §3.4 plus `new_email` citext NOT NULL: `id`, `user_id` FK,
`new_email`, `token_hash` UNIQUE, `expires_at` (`EMAIL_VERIFY_HOURS`),
`used_at` NULL, `created_at`. Single use; a newer request voids older
unused ones. `users.email` changes only when the token is used.
Deleted in the anonymization transaction.
```

**§3.10** — add at the end: `A suggestion on a draft (DEMOCRACY §9.1) has subject_type \`label_preview\` and subject_id = \`label_previews.id\` (§4.19).`

**§3.11** — in the export description, replace `(user, display settings, terms acceptances)` with `(user, display settings, terms acceptances, home changes, pending email changes)`.

**§4.3** — replace the `category_choice` row with:

```
| `category_choice` | enum (`ai`, `author_selected`, `preview`) NOT NULL | `preview` = filed from a suggestion the author reviewed (DEMOCRACY §4.1); `ai` = "Post now, file later" |
```

**Add after §4.18:**

```
### 4.19 `label_previews`

One row per suggestion asked for on a draft. `id`, `user_id` FK `users`
NOT NULL, `input_hash` char(64) NOT NULL (SHA-256 of canonical JSON
`{problem_text, communities}` with communities sorted), `communities`
jsonb NOT NULL, `ai_action_id` FK `ai_actions` NULL (set as soon as the
action row exists), `result` jsonb NULL (main category, umbrella id or
null per community, confidence), `consumed_post_id` FK `posts` NULL,
`created_at`. Index `(user_id, created_at)` — the rate limit's query.
**No draft text is stored.** Not a hashed record: `ai_action_id`,
`result`, and `consumed_post_id` are each set once.
```

### A3. ARCHITECTURE.md

**§3** — no new configuration keys.

**§6 "Auth and account (F)"** — replace the `POST /auth/signup` row and add rows after `PATCH /me/display`:

```
| `POST /auth/signup` | body per DATABASE §3.1; `city_id` may be null (unincorporated); returns user id |
```
```
| `PATCH /me/profile` | any of `real_name`, `display_name` (unique among live users), `gender`, `political_party`. Date of birth is never editable |
| `POST /me/email` | `new_email`, `password`. Sends a confirmation link to the new address and a notice to the old one; nothing changes until `POST /auth/confirm-email-change` (token) — which also revokes every other refresh token |
| `GET /me/home` | current home, the date the next change is allowed, and any reason a change is refused now |
| `POST /me/home` | `county_id`, `city_id` or null. DEMOCRACY §2.3 rules 1–3; one transaction: `users` row and `user_home_changes` row |
```

**§6 "Posts and labels (I)"** — replace the `POST /posts` row with:

```
| `POST /posts/label-preview` | auth, verified. `problem_text`, `communities[]`, validated as for a post. Rate-limited by `label_preview_max_per_hour` (429, plain message). Writes `label_previews`, then the `ai_actions` row, then calls the model; returns `preview_id`, main category, per community the suggested umbrella or null with confidence, and each community's active umbrellas for the chooser. AI unreachable → 503 with the three choices the form offers. One service call: `labels_service.preview` |
| `POST /posts` | problem, solutions[] (≥1), communities[], `category_choice`, per community `umbrella_id` or null, and with `preview` a `preview_id` and `main_category_id`. `preview`: the preview must be the caller's, unconsumed, and its `input_hash` must match the submitted text and communities (409 "Your text changed — run the suggestion again" otherwise); label rows are written with the preview's `ai_action_id` and outcome `confirmed_by_author` or `corrected_by_author` per community; the action's human outcome is set once; solutions are created in the same transaction. `ai`: as before, background. One transaction |
```

**§9 routes table** — replace the row beginning `| \`/me\` (display settings, export, delete)` with:

```
| `/me` — the account page: profile (name, display name, gender, party), email change, home change with the DEMOCRACY §2.3 warning and the next-allowed date, display settings, export, delete; `/confirm-email-change` (consumes the token); `/legal/privacy`, `/legal/terms`, `/legal/cookies` | Foundation |
```

and replace the row beginning `| \`/posts/new\` |` with:

```
| `/posts/new` | DEMOCRACY §4.1; one page, four steps: problem, solutions, communities, "Where it goes" — the AI's suggestion on the draft, kept or changed by the author before posting |
```

### A4. AUDIT.md §2 (director-approved)

Replace the `| After a fix run |` row with:

```
| After a fix run | Re-audit of the previously reported items only. A Foundation file in the fix run's diff does **not** by itself widen the re-audit when a reported finding named that file; any file no finding named — Foundation or Iteration — widens it to a full pass on that half |
```

---

## Part B — Work items, in order, one commit each

Every UI item's proof includes rendered HTML. F = Foundation, I = Iteration.

- **C2-01 (F) — schema.** One **new, appended** Foundation migration
  (`foundation` chain; never edit `25035d5b7ff5`): `users.city_id`
  nullable; `user_home_changes`; `email_change_requests`. Regenerate the
  single Iteration migration for `label_previews` and the
  `category_choice` value. Seed the two settings. Proof: upgrade from
  empty **and** upgrade from a database at the old Foundation head with
  a user in it; `verify_schema.py`; downgrade of the new migration.
- **C2-02 (F) — one source for "your communities".**
  `backend/services/communities.py::home_communities(user)` returns two
  or three pairs. Every place that derives membership uses it: feed
  scope, `GET /cycles/mine`, `/auth/me`, post validation, comment and
  vote checks, jury pool, active-user counts (an unincorporated resident
  counts in county and state only), officials, data export. Proof: `git
  grep -n 'city_id' backend/ -- ':!backend/tests' ':!backend/alembic'`
  with one line per hit saying why it is not a membership derivation; a
  test walking an unincorporated user through post → vote → comment →
  ballot in county and state, and being refused in any city.
- **C2-03 (F) — signup.** County first, then that county's cities with
  "Unincorporated — no city" first. Proof: API tests; HTML.
- **C2-04 (F) — profile and email.** A3 rows. Email: confirmation to the
  new address, notice to the old (both through the email client, console
  backend); a newer request voids older ones; the old address keeps
  working until the token is used; password required. Display names are
  resolved at read time everywhere — prove a rename shows on an existing
  post and **changes no hash**. Anonymization deletes both new tables'
  rows; export includes them. Tests for each refusal.
- **C2-05 (F+I) — changing home.** DEMOCRACY §2.3 rules 1–3 in
  `account_service.change_home`; `GET/POST /me/home`. Ballot eligibility
  per §10.3 in the ballot-vote service, with its one-sentence refusal.
  Tests: first change free; second inside the cooldown refused with the
  date; juror refused; move during an open ballot → refused in new and
  old city, accepted in California, accepted in the county when the
  county did not change; move before `prepared_at` → accepted; old votes
  and posts untouched; cooldown read from settings.
- **C2-06 (F) — the account page (`/me`).** A3 route row. The home-change panel shows
  the §2.3 consequences in plain words and the next-allowed date before
  the confirm button. Proof: HTML in each state.
- **C2-07 (I) — the labeler may answer "none".** `ai/prompts/labeler.md`
  states that "none" is correct when no umbrella covers the problem; the
  parser already accepts it. Keep the prompt a file; record its new hash.
- **C2-08 (I) — suggestion on a draft.** `POST /posts/label-preview` and
  `POST /posts` per A3 and DEMOCRACY §9.1. Order inside `preview`:
  insert `label_previews` → log the `ai_actions` row → call the model →
  store `result`. Tests: the action row exists even when the model call
  then fails; no draft text in any table or log line (grep the database
  dump and the backend log for a marker string used as the draft); rate
  limit from settings; another user's `preview_id` refused; consumed
  preview refused; changed text → 409; all-kept → `confirmed`, one
  changed → `corrected`, "none of these fit" → `needs_review` under the
  chosen main category; solutions exist immediately after `POST /posts`;
  `category_choice=ai` path unchanged.
- **C2-09 (I) — `/posts/new`.** One page, four steps, DEMOCRACY §4.1 as
  amended: nothing pre-selected; names per the governance-levels
  paragraph; unincorporated note; Federal shown disabled with
  `aria-disabled` and never submitted; on reaching step 4 the suggestion
  runs at once with a visible "The AI is reading your draft…" state; per
  community Keep · Change · None of these fit; "Choose myself"; AI
  unreachable → "Choose myself" or "Post now, file later"; editing text
  or communities marks the suggestion out of date; Post is disabled
  until every community has a decision. Keyboard-operable, labelled,
  WCAG 2.1 AA. `/ai/actions` and the post page show a preview-born label
  ("AI-suggested, kept by author" / "changed by author"); an unused
  suggestion shows in `/ai/actions` as "Suggestion on a draft — not
  posted". Proof: HTML of each state.
- **C2-10 (I) — test data.** The shipped `test_dataset.yaml` adds two
  unincorporated residents (`city: ~`) and two posts; the loader handles
  them and uses `category_choice=ai` for `file_under: ai` (so loading
  does not spend the preview rate limit). Do not edit the file's text.
- **C2-11 — housekeeping.** (a) `test_ip_hash_is_salted_and_the_secret_is_required`
  and any test constructing `Settings` clear the process environment
  first (audit change-01-2 LOW); prove by running the suite after `set
  -a; . ./.env; set +a`. (b) `frontend/next.config.ts`: stop Next.js
  generating `frontend/AGENTS.md` / `frontend/CLAUDE.md`; add both to
  `.gitignore`. (c) `.env.example`: `BUILD_LABEL=change-02`.
  (d) TODO Technical Debt: the `/tmp/uvicorn.log` entry names
  `load_test_data.py` too.
- **C2-12 — labeler comparison (evidence only; change no default).**
  From an empty database each time, `load_test_data.py --apply` with
  `OLLAMA_MODEL=llama3.2`, then again with `OLLAMA_MODEL=llama3.1:8b`.
  In HISTORY.md, one table: each `file_under: ai` post, the umbrella each
  model chose (or none), seconds per label, and any
  `repeated_or_unlisted_communities`. No recommendation — the director
  decides.
- **C2-13 — evidence.** Clean-shell full suite and `npm test`;
  `verify_schema.py`; seed `--dry-run`; test data loaded; through the
  API: an unincorporated signup → preview → post kept; a second post
  with one community changed and one "none of these fit"; a home change
  and the refused ballot vote; an email change end to end; one full
  cycle; `reconcile.py --dry-run`; hash round-trip; `npm run build`;
  `npm audit --audit-level=high`; `pip-audit` if available; `git status`.

## What you must not do

- Build "propose a new umbrella", Federal posting, account flagging, or
  any stored Home preference.
- Edit the first Foundation migration, a protected document outside
  Part A, `audits/`, or the text of `test_dataset.yaml`.
- Store draft text anywhere; log a real name, email, or draft in a log
  line; store, hash, or publish a rendered name; rewrite or delete a row
  carrying a `content_hash`; type a democratic number into code or copy.
- Let a router touch a table or an endpoint make two service calls; call
  `fetch` outside `api.ts`.
- Mark an item done with less than it says. Partial is `[~]` with the residue named.
- Push to `main`. Open a pull request. Ask for approval.

## At the end

1. Append the planning entry below to HISTORY.md **verbatim**, then your
   own: `## <date from the system clock> — Session N (Claude Code build —
   change/02-who-and-where)`, with every decision made where the
   documents were silent, the C2-12 table, and "Director to verify".
2. TODO.md: snapshot; section "Change 02 — who you are and where you
   post" with C2-01…C2-13; remove the debt item fixed by C2-11(a).
3. `git add -A && git commit -m "change/02-who-and-where complete" && git push origin change/02-who-and-where`.
4. No pull request.

**Browser-only checks for the director** (copy into your entry under
"Director to verify"): sign up as unincorporated and see two
communities on Home; change home on the account page (`/me`), read the warning, see
the next-allowed date; change display name and see it on an old post;
change email using the link from the backend log; on New post — nothing
pre-selected, Federal greyed out, the suggestion appears on reaching
step 4, Keep / Change / None of these fit each work, editing the text
marks it out of date; stop Ollama's route and see the two fallbacks;
the whole form by keyboard and at phone width.

### Planning entry to append verbatim (before your own)

```
## 2026-09-20 — Session 4 (Claude.ai planning session — change/01 merged; change/02 designed)

**Completed:**
- `audits/change-01-audit-2.md`: CRITICAL 0 · HIGH 0 · MEDIUM 0 · LOW 1 — CLEAN; all seven browser checks director-verified. `change/01-site-shell` merged to `main` by PR #6 (squash, `a85ccee`); branch deleted. First full cycle of the change method: build, director's test, two fix runs, two audits, merge, in two days.
- change/02 designed with the director; brief `briefs/change-02.md`; two unincorporated test residents and two posts added to `test_dataset.yaml`.

**Decisions made (director unless marked):**
1. **The AI labels the draft before it is posted** (director chose this over post-then-label): the suggestion runs as soon as the author reaches "Where it goes"; the author keeps, changes, or answers "none of these fit", then posts. Planning session's design for Law 7: each suggestion is a public AI action with subject `label_preview`; only a hash of the draft is kept, never its text; an abandoned draft leaves "a suggestion was made and not used". No Foundation table changes for this — `label_previews` is an Iteration table. A public hourly limit per user guards the GPU.
2. "None of these fit" is a first-class answer for the AI and the author; the post waits under its main category. Propose-a-new-umbrella (change/03) will sit beside it. Prompted by audit 2's note that the small model forces bad fits.
3. Moving during a ballot sits that ballot out in both the old and the new community; California and an unchanged county are unaffected. A juror finishes service before moving. The first home change is free; the cooldown (90 days, a setting) runs after it.
4. Email changes take effect only when the new address is confirmed; the old address is notified; a password is required. Real name is editable until identity verification exists; date of birth never.
5. Unincorporated residents have `city_id` NULL and two communities (closes the design of Director Decision #9).
6. AUDIT.md §2: a Foundation file named by a finding does not by itself widen a re-audit (answers audit 2's document ambiguity 1).
7. Evidence only: `llama3.2` and `llama3.1:8b` label the same test posts side by side; the director chooses the default afterwards.

**Issues encountered:**
- Audit 2 NOTE: with no fitting umbrella the 3B labeler picks the nearest poor one (street lights → "Pedestrian Safety Near Schools"). Decisions 2 and 7 respond.
- Next.js 16 generates `frontend/CLAUDE.md` on `next dev`; Claude Code reads any `CLAUDE.md` as instructions. C2-11(b) turns it off.
```

[[[ END BUILD BRIEF — change-02 ]]]
