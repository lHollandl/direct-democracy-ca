# DEMOCRACY.md — The Civic Process

> How a problem becomes pressure on government. This document defines
> every rule, threshold, status, and role in the civic process precisely
> enough to build from. Where a rule is a number, the number is a
> setting (CLAUDE.md Law 8) and its Demo 1 default is given here.
>
> Tables and endpoints that implement this are in DATABASE.md and
> ARCHITECTURE.md. This document says *what the rules are*; those say
> *where they live*.
>
> Changes to process philosophy require director approval. Tuning a
> default is a settings change, logged, not a document change.

---

## 1. The Shape of the Process

Every problem lives in two phases on two clocks.

**The workshop** runs continuously. Inside an umbrella, citizens post
problems, propose solutions, amend them, discuss, and vote up or down.
Nothing in the workshop is binding. It is the drafting room, and its
purpose is to make solutions better *before* they are popular.

**The ballot** runs once per cycle per community, for one week. From
the workshop, a small number of solutions qualify by crossing a public
threshold and surviving a citizen jury. The whole community votes yes or
no on each. The ballot is the platform's output — the thing that carries
weight.

**The summary document** is published when the ballot closes: one per
community per cycle, identical for everyone in that community, hashed,
public. It goes to representatives and it feeds the next workshop
round, so no month's work is lost.

```
 post ──▶ labeled into umbrella ──▶ WORKSHOP (continuous)
                                       │  solutions, amendments,
                                       │  comments, up/down votes
                                       │  ─ thresholds ─▶ dominant
                                       │  ─ thresholds ─▶ qualified
                                       ▼
                                  PREPARE BALLOT (snapshot)
                                       │
                                  JURY REVIEW (hold back only)
                                       │
                                  BALLOT OPEN ── yes / no ── BALLOT CLOSED
                                       │
                                  SUMMARY DOCUMENT (hashed, public)
                                       │
                            user sends it to representatives
                                       │
                                  back into the workshop
```

---

## 2. Communities and Governance

### 2.1 Governance levels

| Level | Entity | Demo 1 |
|---|---|---|
| `city` | an incorporated California city | yes |
| `county` | one of 58 counties | yes |
| `state` | California | yes |
| `federal` | none yet | no — parked |

### 2.2 Community

A **community** is one governance level plus one entity: (`city`,
Vallejo), (`county`, Solano), (`state`, California). Every umbrella,
ballot cycle, jury, and summary document belongs to exactly one
community.

### 2.3 Home communities

Every user has exactly one home city and one home county, set at signup
from the geography tables, and is therefore a member of exactly three
communities: their city, their county, and California. Membership
determines what a user may vote on in a ballot and where their posts
are eligible to appear.

Users may *read* any community. Users may *post, comment, vote, and
serve on juries* only in their home communities.

**Minimum age.** Signup requires the user to be at least
`min_signup_age` (Demo 1: 17) on the day of signup, computed from the
date of birth. Younger applicants are refused at signup with a plain
message; nothing is stored. The age is checked once, at signup; a user
who was old enough then is a full member.

### 2.4 Active users

The denominator for every percentage threshold.

> An **active user** of a community is a member of that community whose
> email is verified, whose account is not deleted, and who has made at
> least one authenticated request in the last `active_user_window_days`
> (Demo 1: 30).

Computed on demand, never cached longer than one hour. The count is
displayed on each community's page with the definition beside it.

---

## 3. Main Categories and Umbrellas

### 3.1 Main categories

A fixed list held in `backend/config/categories.py`. The AI must choose
from it and cannot invent one. The community grows it through the
proposal system (parked — PROJECT.md). Demo 1 placeholder list:

Roads and Infrastructure · Housing and Homelessness · Public Safety ·
Environmental Issues · Education · Public Transit · Water and Utilities
· Parks and Recreation · Economic Development · Government Accountability

### 3.2 Umbrellas

An **umbrella** is a named problem inside a main category, scoped to
one community. "Pedestrian Safety" in (`city`, Vallejo) and "Pedestrian
Safety" in (`county`, Solano) are two umbrellas. Umbrella and
subcategory are the same thing.

An umbrella has: a name, a one-paragraph statement of the problem, a
main category, a community, a status (`active` / `retired`), and a
creation source (`seed` / `proposal`). AI never creates umbrellas (CLAUDE
§5).

**Demo 1:** umbrellas are seeded from `backend/config/seed_umbrellas.yaml`,
a file the director writes. The file lists, per test community, each
umbrella's name, statement, and main category. Claude Code does not
invent umbrellas; if the file is missing or empty, the build stops and
reports.

### 3.3 The umbrella page

The umbrella page is the workshop. Sections, in order:

1. **Problem** — the umbrella's name and statement; the community; the
   main category; the AI-influence action list (§9.4); the active user
   count for the community.
2. **Problem reports** — the problem texts of every post assigned to
   this umbrella, newest first, each with its author display and
   AI-label status ("AI-labeled, confirmed by author" / "AI-labeled,
   corrected by author" / "chosen by author").
3. **Problem discussion** — threaded comments on the problem (§6).
4. **Solutions** — every solution in the umbrella, ordered by net score
   descending, ties by creation time ascending. Each shows its current
   version text, author display, net score, status badge (`dominant` /
   `qualified` / `held back` / none), version number, and AI influence.
   Nothing is ever hidden; a solution at −20 shows at the bottom.
5. **Dominant solutions** — each dominant solution expanded with its
   **amendments** (§5) and its **solution discussion** (§6). Non-dominant
   solutions have neither: you upvote them, or you propose a better one.
6. **References** — external information attached to the umbrella (§8).

---

## 4. Posts and Solutions

### 4.1 Posts

A post is a citizen's problem report plus at least one proposed solution
(CLAUDE.md Law 1). Fields: problem text (required, 20–5,000 chars), one
or more solutions (each 20–5,000 chars), the governance levels the
author selects (one or more of the author's home communities), and the
category choice:

- **Let AI decide** (default) — the labeler assigns a main category and,
  for each selected community, the closest active umbrella. If a
  community has no umbrella under that main category, the post is
  assigned to the main category only and flagged `needs_review`.
- **Pick an existing umbrella** — the author browses active umbrellas
  for their selected communities and chooses. Recorded as
  `author_selected`.
- **Propose a new umbrella** — parked. Demo 1 does not show this option.

A post is saved immediately. Labeling runs in the background; until it
completes the post shows "being filed" and appears in no umbrella. If
labeling fails, the post is marked `unlabeled` and retried by a
background job every `label_retry_minutes` (Demo 1: 10) until it
succeeds.

The author may correct an AI label at any time from the post. Every
correction is recorded on the label row (§9.2).

**Where the solutions go.** A post's solution texts are stored with the
post at submission (`post_solutions`, DATABASE §4.4). A **solution**
(§4.3) exists only inside an umbrella, and an umbrella belongs to one
community, so the moment a post-community is assigned an umbrella —
by the labeler, by the author's pick, or by the author's correction —
one solution row is created in that umbrella for **each** of the post's
solution texts. A post going to three communities with two solution
texts therefore produces six solutions, each with its own votes and
amendments, because each community workshops it separately. Until a
post-community has an umbrella (`pending`, `needs_review`,
`unlabeled`), its solutions do not yet exist; the post page shows the
texts with "waiting to be filed". If the author later corrects a label
to a different umbrella, the solutions already created are **moved** to
the new umbrella only while they have zero votes and zero amendments;
otherwise they stay where they are and the correction is recorded but
creates nothing new.

**A post cannot be edited or deleted in Demo 1.** The problem text is
hashed at creation (Law 6) and is immutable; the post's solutions
evolve in the workshop. The `deleted_at` column exists for a future
moderation design.

### 4.2 Post title

Derived: the first 80 characters of the problem text, cut at a word
boundary. Not stored separately. Not editable.

### 4.3 Solutions

A solution belongs to one umbrella. It is created either from a post
when that post-community receives its umbrella (§4.1, "Where the
solutions go") or directly on an umbrella page by any member of the
community. A solution created from a post records the post and the
`post_solutions` row it came from, so the page can show "also proposed
in Solano County" links between the copies.

A solution has **versions**. Version 1 is the text as posted. Each
absorbed amendment (§5) creates version n+1. The solution's current text
is its highest version. Every version is kept, with its own
`content_hash` (Law 6), and the version history is visible on the
solution.

**Ownership.** Solutions are community-owned once posted (CLAUDE §6).
The author is recorded and displayed per their display settings; the
author has no special rights over amendments.

**Editing.** The author may edit a solution's text only while it has
zero votes and zero amendments. After that, changes happen only through
amendments.

### 4.4 Net score

> **Net score** of an item = (distinct upvotes) − (distinct downvotes).
> One vote per user per item; a user may change or remove their vote at
> any time until the item is frozen (§7.2).

Applies to solutions, amendments, and comments. Votes attach to the
solution, not the version, so support carries across amendments. Net
score is recomputed on every vote event; the denormalized column is
never authoritative — a nightly job reconciles it against the vote
rows and logs any drift.

### 4.5 Supporters

> The **supporters** of a solution are the distinct users with a current
> upvote on it.

Used as the denominator for amendments (§5.3).

---

## 5. Amendments

### 5.1 What an amendment is

An amendment is a proposed **complete replacement text** for a solution,
plus a one-line rationale (10–300 chars). The platform renders the diff
against the current version. Amendments can be proposed only on
**dominant** solutions (§7.1), by any member of the community except
the author of the solution's current version.

### 5.2 Amendment lifecycle

```
proposed ──▶ absorbed      (threshold met; new solution version created)
         ──▶ superseded    (the solution gained a new version; this
                            amendment's base is stale; it stays visible,
                            marked, and can no longer be absorbed)
         ──▶ merged_into   (grouped with a similar amendment; §5.4)
         ──▶ withdrawn     (by its author, only while net score < threshold)
```

Nothing is deleted.

### 5.3 Absorption threshold

> An amendment is **absorbed** when its net score ≥
> `threshold(amendment_pct, amendment_min, supporters of the solution)`.

Where, for every threshold in this document:

> `threshold(pct, min, denominator) = max(1, min(ceil(pct/100 ×
> denominator), min))`

That is: the percentage of the denominator, or the fixed minimum,
whichever is **lower**, and never less than 1.

Demo 1 defaults: `amendment_pct = 25`, `amendment_min = 3`. Denominator
is the solution's supporters (§4.5) at the moment of evaluation, not the
community.

On absorption: a new version is created with the amendment's text; the
amendment is marked `absorbed` with the version number; all other
`proposed` amendments on that solution become `superseded`; the event is
recorded in the solution's history and the AI action log is untouched
(this is a human action).

Evaluation happens on every vote event on the amendment.

### 5.4 Similar amendments

When several people propose nearly the same change, they should count
together.

- On creation, the AI similarity check (§9.3) compares the new amendment
  with every `proposed` amendment on the same solution. Any pair with
  similarity ≥ `similarity_threshold` (Demo 1: 0.85) is flagged.
- A flag is shown on both amendments: "Similar to amendment #N — are
  these the same change?" with **Same** / **Different** buttons visible
  to any member of the community.
- When `similarity_confirm_min` (Demo 1: 2) distinct users, or either
  amendment's author, press **Same**, the newer amendment is marked
  `merged_into` the older; its upvoters are counted as supporters of the
  older for the absorption threshold (a user who upvoted both counts
  once). When the same number press **Different**, the flag is
  dismissed and recorded.
- AI suggests; humans decide. The AI action and the human decision are
  both logged (§9.2).

---

## 6. Comments

Threaded discussion, Reddit-style, on two things only: an umbrella's
problem (§3.3 item 3) and each dominant solution (§3.3 item 5). No
comments on posts, non-dominant solutions, amendments, or references.

- Depth: a comment's `depth` is 0 for a top-level comment and grows by
  one per reply, up to `comment_max_depth` (Demo 1: 3 — so four visible
  levels, 0–3). A reply to a depth-3 comment is stored at depth 3 under
  the same parent, with `reply_to_comment_id` pointing at the comment it
  answered. The page renders "replying to @display" from that id **at
  read time**, through the author-display rule (DATABASE §3.2). The
  stored `text` is only what the person typed — never a name, which
  would freeze someone's identity into a permanent hash (CLAUDE §6,
  Law 6; audit demo-01 run 2).
- Length: 1–2,000 chars.
- Ordering within a thread: net score descending, ties oldest first.
- Up/down votes; net score; nothing hidden by score.
- Edit: within `comment_edit_minutes` (Demo 1: 15) of posting, marked
  "edited". After that, immutable.
- Delete: soft — the row stays, text replaced by "[removed by author]",
  replies remain.

Moderation is out of scope for Demo 1. Every comment carries the
author's display, timestamp, and AI influence (always 0% until the
writing assist exists).

---

## 7. Statuses and Thresholds

### 7.1 Dominant

> A solution is **dominant** when its net score ≥
> `threshold(dominant_pct, dominant_min, active users of the community)`.

Demo 1 defaults: `dominant_pct = 5`, `dominant_min = 3`.

Evaluated on every vote event on the solution and once nightly (because
the active-user denominator changes without any vote). On gaining the
status, `dominant_since` is set; on losing it, cleared. Dominant
solutions accept amendments and comments; losing the status does not
remove existing amendments or comments, it only stops new ones.

Open question, flagged for the director: whether to add hysteresis
(lose dominance only below some fraction of the threshold) to prevent
flapping at the boundary. Demo 1 has none; the audit should report how
often the status flips.

### 7.2 Qualified for the ballot

> A solution is **qualified** when all of the following hold at the
> moment the director prepares the ballot (§10.2):
> 1. It is dominant.
> 2. It has been dominant continuously for at least
>    `ballot_min_dominant_days` (Demo 1: 3).
> 3. Its net score ≥ `threshold(ballot_pct, ballot_min, active users of
>    the community)`. Demo 1: `ballot_pct = 10`, `ballot_min = 5`.
> 4. If it has ever been a ballot item — passed, failed, or held back —
>    its current version is greater than the version that was on that
>    ballot (`current_version > last_ballot_version`). A solution does
>    not return to the ballot unchanged; the way back is an amendment
>    (§5), which creates a new version (§8.4, §10.5).

Qualification is a **snapshot**, not a live status. Between snapshots
the page shows "on track for the ballot" when conditions 1–3 currently
hold, so people can see it coming.

On snapshot, each qualified solution's current version is **frozen** as
the ballot text: votes on it continue in the workshop, but the version
that appears on the ballot does not change even if an amendment is
absorbed later. The frozen version is what the summary document prints.

### 7.3 No ballot cap

Every qualified solution goes on the ballot. There is no per-umbrella
or per-ballot maximum. If ballots grow too long in practice, that is a
finding for the next rebuild, not a rule to add silently.

### 7.4 Settings table

Every value in this document that the community can adjust. All live in
the `settings` table with a public page. Every summary document prints
the values that were in force for that cycle.

| Key | Meaning | Demo 1 |
|---|---|---|
| `active_user_window_days` | window for "active user" | 30 |
| `dominant_pct` / `dominant_min` | §7.1 | 5 / 3 |
| `amendment_pct` / `amendment_min` | §5.3 | 25 / 3 |
| `ballot_pct` / `ballot_min` | §7.2 | 10 / 5 |
| `ballot_min_dominant_days` | §7.2 | 3 |
| `similarity_threshold` | §5.4, §9.3 | 0.85 |
| `similarity_confirm_min` | §5.4 | 2 |
| `jury_size` | §8.1 | 3 |
| `jury_no_repeat_cycles` | §8.1 | 0 |
| `jury_review_days` | §8.3 | 2 (manual in Demo 1) |
| `ballot_window_days` | §10.3 | 7 (manual in Demo 1) |
| `ballot_pass_rule` | §10.4 | `simple_majority` |
| `ballot_quorum_min` | §10.4 | 1 |
| `comment_max_depth` | §6 | 3 |
| `comment_edit_minutes` | §6 | 15 |
| `label_retry_minutes` | §4.1 | 10 |
| `references_ai_max_per_umbrella` | §9.4 | 5 |
| `reference_reject_min` | §9.4 — Not-useful presses that reject a reference | 2 |
| `min_signup_age` | §2.3 — minimum age at signup, in years | 17 |

`similarity_confirm_min` applies to amendment similarity only (§5.4);
reference rejection has its own key so the two can be tuned apart.
`min_signup_age` is read by Foundation signup; it lives here so it is
public and its history is kept like every other rule.

Changing a setting: admin only (Demo 1); logged in the admin action log
with old value, new value, and reason; a new row, never an update, so
the value in force at any past moment can be read back.

---

## 8. The Jury

### 8.1 Draw

When the director prepares a ballot for a community (§10.2), the
platform draws `jury_size` (Demo 1: 3) jurors at random from that
community's active users, excluding:

- users who authored any version of, or have a `proposed` amendment
  on, any qualified solution on this ballot;
- users who served on a jury for this community within the last
  `jury_no_repeat_cycles` cycles (Demo 1: 0 — no exclusion);
- users with `is_admin = true`.

(Active users are already email-verified and not deleted, §2.4, so
every drawn juror is able to accept.)

If fewer eligible users exist than `jury_size`, the jury is the number
available, and the summary document says so. If zero, the ballot
proceeds with no jury review and the summary says so.

The draw uses the platform's cryptographic random source. The draw is
**logged**: the eligible pool (user ids), the drawn ids, the timestamp,
and the random bytes used, so it can be inspected after the fact. A
re-draw (§13) creates a new draw and marks the old one superseded; no
draw is ever deleted.
Provably reproducible draws are parked (PROJECT.md).

### 8.2 Notification and acceptance

Drawn users are notified in-app (and by email — Foundation, when email
notifications exist; Demo 1: in-app only). Each accepts or declines
within `jury_review_days`. A decline draws a replacement from the
remaining pool immediately. A juror who has accepted is **seated**. A
juror who has not responded when the review window closes is marked
`no_response`, is **not seated**, and is not replaced; the jury is the
seated jurors, and the summary document states how many were drawn and
how many were seated.

The review window closes when the director opens the ballot (§10.3);
there is no separate "close review" action.

### 8.3 Review

Jurors see every qualified solution with its frozen text, its umbrella,
its net score, and its amendment history. For each, a juror may do
nothing, or **hold back** with a written public reason (20–1,000 chars)
chosen alongside one of a fixed set of categories:

`duplicate` · `not_actionable` · `incomplete` · `outside_governance_level`
· `other`

A hold-back takes effect when **more than half of the seated jurors**
(§8.2) have held back the same solution, counted when the ballot is
opened; their categories need not agree. Each juror's category and
reason are recorded and **every one is published**, whether or not it
reached a majority: on the solution's page under "Jury notes" from the
moment the ballot opens, and in the summary document (§11.2). A juror
is told exactly this when they submit. Jurors act independently; they
do not see each other's hold-backs until the ballot opens.

### 8.4 Effect of a hold-back

The solution does not appear on this ballot. It stays dominant and keeps
its votes. It appears in the summary document under "Held back" with
every seated juror's category and reason. The solution records
`last_ballot_result = held_back` and the version that was held back.

It returns to a later ballot under the same rule as a passed or failed
solution (§7.2 condition 4): only once it has a new version, which
means an amendment was absorbed. A hold-back is feedback; the response
is an amendment. The previous hold-back reasons are shown on the
solution page and to the next jury, which is free to hold the new
version back again for any reason.

### 8.5 Identity

Jurors are anonymous to the public — "Juror 1 of 3" — and their reasons
are public. Juror identities are in the database, visible to admins,
and in the user's own export.

---

## 9. AI Roles

Three AI functions exist in Demo 1. All are labeled where they appear,
all are logged, none decides anything (CLAUDE §5).

### 9.1 The labeler

Assigns a post to a main category and, per selected community, to the
closest active umbrella. Runs on Ollama, on the host GPU, after the
post is saved. Its prompt is a file: `ai/prompts/labeler.md`. Its
input is the post's problem text, the fixed category list, and the
umbrella names and statements for the relevant communities. Its output
is a main category, an umbrella id per community (or none), and a
confidence in [0, 1].

**Reading the answer.** Small models repeat communities or echo ones from
the prompt's example. For each selected community the labeler keeps the
first answer that names an umbrella actually active in that community
and ignores the rest; everything ignored is recorded on the AI action row
under `output.repeated_or_unlisted_communities`, so the public log shows
what the model said, not only what was used. The model runs at
temperature 0.

The author can confirm or correct. Confirm is one tap; correct opens the
"pick an existing umbrella" chooser. Either way the label row records
`confirmed_by_author` / `corrected_by_author` / `unreviewed`.

### 9.2 The AI action log

Every AI action is a row before its result is shown (Law 7):

| Field | Content |
|---|---|
| `action_type` | `label` / `similarity` / `reference_recommend` |
| `subject_type`, `subject_id` | what it acted on |
| `model` | e.g. `ollama:llama3.2` — the string, so swaps are data |
| `prompt_file`, `prompt_hash` | which prompt file, its hash |
| `input_hash` | hash of the exact input |
| `output` | the raw output, JSON |
| `confidence` | if applicable |
| `human_outcome` | `unreviewed` / `confirmed` / `corrected` / `accepted` / `rejected` |
| `human_outcome_by`, `human_outcome_at` | who and when |
| `created_at` | |

The log is public: `/ai/actions`, paginated, filterable by subject.
Rows are never deleted or edited except to set the `human_outcome_*`
fields once.

### 9.3 Similarity

Compares two texts and returns a score in [0, 1]. Used for amendments
(§5.4). Implementation: embeddings from Ollama (`nomic-embed-text` or
whatever `EMBED_MODEL` is set to) and cosine similarity. There is no
prompt file — an embedding call has no prompt text — and the log row says
so (DATABASE §3.10). The score and both input hashes are logged. The
threshold is a setting.

### 9.4 Reference recommendation

For each umbrella, the AI may recommend up to
`references_ai_max_per_umbrella` (Demo 1: 5) external references.
Procedure:

1. Ollama reads the umbrella statement and the current dominant
   solutions and produces 1–3 search queries (prompt file:
   `ai/prompts/reference_queries.md`).
2. Each query is sent to the web search provider named in configuration
   (`SEARCH_PROVIDER`, `SEARCH_API_KEY`). The provider, the exact query,
   and the raw result set are stored.
3. Ollama selects from the results and writes a one-sentence "why this
   is relevant" per pick (prompt file: `ai/prompts/reference_select.md`).
4. Each pick becomes a reference with `source = ai`, shown with the
   label "Recommended by AI" and the reason, and a **Useful** / **Not
   useful** pair. When `reference_reject_min` (Demo 1: 2) distinct
   users press Not useful, the reference is marked `rejected` (still visible under "rejected
   references", never deleted) and the log row records the outcome.

Triggered by the director in Demo 1 (a button on the umbrella page,
admin only) — not on a schedule.

User-added references: any member may add a URL with a one-line note.
`source = user`. Same Useful / Not useful; same rejection rule.

### 9.5 AI influence

**Post, solution version, comment, amendment:**

> `ai_contribution_percentage` = characters changed by platform-provided
> AI assistance ÷ total characters of the final text, × 100, rounded to
> an integer.

No platform AI assistance exists in Demo 1, so every value is 0 and the
label reads "AI assistance on this platform: 0%". The column and the
label exist now so that the promise is visible before it is non-trivial.
Text pasted from outside AI is not detectable and the label's wording
does not claim otherwise.

**Umbrella:** an **action list**, not a percentage:

> "AI on this umbrella: 14 of 20 problem reports were AI-labeled (11
> confirmed, 3 corrected, 0 unreviewed); 2 amendment pairs were flagged
> similar (1 confirmed same, 1 different); 4 of 9 references were
> AI-recommended (3 marked useful, 1 rejected)."

Generated from the AI action log at page render.

---

## 10. The Ballot Cycle

### 10.1 Cycle

A **cycle** belongs to one community and has a sequential number within
it. States:

```
workshop ──▶ prepared ──▶ jury_review ──▶ open ──▶ closed ──▶ published
                 └──────────── (zero items only) ─────────────────┘
```

Each transition is timestamped and recorded with who triggered it
(admin) and, when automatic, `system`. Demo 1: every transition is a
director control. The timers (`jury_review_days`,
`ballot_window_days`) exist as settings and are displayed as "would
close on …" but do not fire.

Exactly one cycle per community is in a non-`published` state at a
time. Preparing a new cycle requires the previous one to be `published`.

### 10.2 Prepare

Admin action. For the community:

1. Snapshot: evaluate §7.2 for every solution in every active umbrella;
   freeze each qualified solution's current version as a **ballot
   item**.
2. Record the settings in force (all keys in §7.4) on the cycle.
3. Draw the jury (§8.1).
4. Transition `workshop → prepared → jury_review`.

**Ballot order.** Items are numbered (`position`) by umbrella name
A–Z, then net score at snapshot descending, then solution id
ascending. The ballot page, the summary document, and the jury view
all use this order.

**Zero items.** If no solution qualifies, the cycle is prepared with
zero items and no jury is drawn. The only transition available from
`prepared` in that case is straight to `published` — the director
publishes an empty summary ("No solutions reached the ballot this
cycle") whenever ready, and the next cycle can then be prepared. A
zero-item cycle never enters `jury_review`, `open`, or `closed`.
Because prepare continues to `jury_review` in the same action whenever
any item qualifies, a cycle is only ever *observed* in `prepared` when it
is empty; the code's guard against publishing a non-empty `prepared`
cycle is therefore unreachable today and is kept for the case where
prepare is later split into two steps.

### 10.3 Open and close

Admin actions. On open: ballot items not held back become votable;
members of the community see the ballot tab. On close: no further
ballot votes are accepted; results are computed.

**Ballot vote:** `yes` / `no`, one per member per item, changeable
until close. Eligibility: the voter's home community equals the cycle's
community. Each vote row records the voter's verification level at the
time of voting.

### 10.4 Result

> Under `ballot_pass_rule = simple_majority`: an item **passes** when
> yes > no and (yes + no) ≥ `ballot_quorum_min`. Otherwise it **fails**.
> A tie fails.

Demo 1: `ballot_quorum_min = 1`. A real quorum is a director decision
before any real community votes.

### 10.5 After close

- The summary document is generated and published (§11).
- Passed, failed, and held-back items are recorded on their solutions
  (`last_ballot_result`, `last_ballot_cycle_id`, `last_ballot_version`),
  shown as badges in the workshop.
- All three stay in the workshop with their votes and return to a later
  ballot only under §7.2 condition 4 — after a new version. A rejected
  solution does not return unchanged; a passed solution is marked
  "Passed — cycle N" and returns only if the community refines it.

---

## 11. The Summary Document

### 11.1 What it is

One document per community per cycle. Same content for every reader.
Canonical form is a **web page** at a permanent public URL; a PDF is an
export of it. **Nothing personal in it**: no name, display name, user id,
or other identifier of any member appears in the document or its
canonical JSON. Jurors are "Juror n of m". Solutions are attributed to
the community, not to a person — authorship lives on the solution page,
where the display rule (DATABASE §3.2) resolves it at read time and
account deletion reaches it. The hashed document therefore never has to
change for anyone's sake (CLAUDE §6; audit demo-01 run 4).

### 11.2 Content, in order

1. **Header.** Community name and level. Cycle number. Ballot open and
   close timestamps. Active users at snapshot. Members who voted.
   Verification mix of voters ("142 voters: 142 unverified"). The
   sentence: "Residency is self-declared and unverified at this
   verification level." Jurors drawn and jurors seated, counting every
   person ever drawn including replacements ("4 drawn, 1 replaced, 2
   seated"), or "No jury was drawn" for a zero-item cycle.
2. **Results.** For each ballot item, in ballot order: umbrella name;
   the frozen solution text (version number, hash); yes count; no count;
   result (**Passed** / **Failed**); the solution's AI-influence figure;
   the line "Proposed and refined in the [community] workshop" with a
   link to the solution page (`PUBLIC_BASE_URL/solutions/{id}`). No
   author. Failed items are included. Under any
   item a juror held back without a majority: "Juror concerns (n of m
   seated)" with each category and reason, attributed "Juror n of m".
3. **Held back.** For each held-back solution: umbrella; text; the jury
   category and every juror's written reason, attributed "Juror n of
   m".
4. **How this was produced.** One paragraph each, plain English: what
   an active user is; how a solution becomes dominant; how it qualifies;
   how the jury was drawn and what it can do; how a vote passes. Each
   paragraph ends with the setting values in force for this cycle and
   the rule's version.
5. **Verify this document.** The document's hash; a link to the
   public hash list; a plain-language explanation ("This code is a
   fingerprint of everything above. If anyone changes one letter, the
   fingerprint will not match. You can check it at …").

### 11.3 Hashing

> `summary_hash` = SHA-256 of the canonical JSON of the document data
> (keys sorted, UTF-8, no whitespace), computed once at publish and
> stored on the cycle. The page renders from that JSON. The public hash
> list at `/summaries/hashes` shows every published summary's
> community, cycle, publish time, and hash.

A verifier endpoint `/summaries/{community}/{cycle}/verify` recomputes
the hash from stored data and reports match / mismatch. The JSON itself
is downloadable so anyone can recompute independently.

### 11.4 The user's view

`/results` shows the logged-in user their three communities' most
recent summaries (city, county, state) and past cycles. That is the
personalization: which three, not what's in them.

### 11.5 Send to representatives

On each summary page, **Send to my representatives** opens the user's
own mail client (`mailto:`) with: recipients = every officials-directory
entry for that community; subject = "Ballot results — [community],
cycle N"; body = a short note, the summary's **absolute** URL (built
from `PUBLIC_BASE_URL`, so the link works in a representative's inbox),
and the hash. The user sends it from their own address. The platform sends nothing and records
nothing about the send — it cannot know whether the user pressed send.

**Demo 1:** every directory entry is the director's test address.

### 11.6 PDF export

**Download PDF** renders the same content server-side. The PDF states
the summary hash and URL on every page footer. The PDF's own bytes are
not hashed; the web page is canonical.

---

## 12. The Feed

**Demo 1:** `/feed` shows posts from the user's home communities,
newest first, with a filter by community and by main category. That is
the entire ordering rule, and it is stated on the page: "Newest first.
No ranking." Version `feed-v0`.

The smart feed is parked (PROJECT.md). When it is designed, the
plain-English explanation lives in the same file as the ranking code
(Law 9) and the version increments.

---

## 13. Director Controls (Demo 1)

Available to users with `is_admin = true`, under `/admin`. Every action
writes an admin action log row (who, what, subject, old/new values,
reason if given).

- Prepare ballot for a community (§10.2)
- Re-draw jury (only while `jury_review`; logged with reason). The
  previous draw is **kept** — its pool, drawn ids, random bytes, and
  jurors' statuses stay inspectable, marked superseded (§8.1)
- Open ballot; close ballot; publish summary
- Trigger reference recommendation on an umbrella (§9.4)
- Change a setting (§7.4)
- Force a label retry on a post
- View any user's verification level and jury history (not their
  ballot votes — a ballot vote is visible only to the voter who cast
  it, on the ballot page and in their own export; admins and every
  other endpoint see counts only)

Admins are not exempt from any threshold and cannot vote twice, edit
others' content, or alter votes. The admin log is public at
`/admin/log` (read-only, no login required).

**Becoming an admin.** There is no endpoint, page, or setting that makes
an administrator. An admin is granted only by someone with access to the
machine running `backend/scripts/grant_admin.py`, and the grant is
written to the public admin log like any other admin action. An
administrator can change every rule a democratic outcome depends on;
that power must not be reachable from the web.

---

## 14. Rules That Exist Because of the Constitution

For the auditor. Each line is a constitutional requirement and where
this document satisfies it.

| CLAUDE.md | Satisfied by |
|---|---|
| §2 every rule public | §7.4 settings page; §11.2 item 4 |
| §2 transparency about weakness | §11.2 item 1 verification sentence |
| §3 equal vote weight | §10.3 one vote per member; verification recorded, never weighted |
| §3 identical ranking | §3.3 item 4 ordering; §12 feed-v0 |
| §4 downvotes never hide | §3.3 item 4; §6 |
| §4 minimum visibility for minority views | Met trivially in Demo 1: nothing ranks anything out of sight (§3.3 item 4 shows every solution; §12 feed-v0 has no ranking). The visibility rule and its §7.4 setting are owed the day any ranking feed exists (PROJECT.md parking lot, Small Voice) |
| §6 nothing personal in the permanent record | §11.1; §11.2 item 2; §8.5 |
| §5 AI never decides | §3.2 umbrellas; §5.4 humans confirm; §9.4 humans reject |
| §5 every AI action logged | §9.2 |
| §5 AI influence displayed | §9.5 |
| §5 labels correctable | §4.1, §9.1 |
| §6 community-owned solutions | §4.3 |
| §6 hashes never deleted | §4.3 versions; §11.3 |
| §6 ballot vote visible only to its voter | §10.3; §13 |
| Law 1 | §4.1 (`post_solutions` at insert; solutions per umbrella) |
| Law 6 | §4.1 post immutable; §4.3; §11.3 |
| Law 7 | §9.2; prompt files in §9.1, §9.4 |
| Law 8 | §7.4 |
| Law 9 | §12 |

---

## 15. Open Questions

Flagged for the director. Demo 1 proceeds with the default stated.

1. **Hysteresis on dominant status** (§7.1). Default: none.
2. **Real quorum** (§10.4). Default: 1. Must be decided before any real
   community votes.
3. **Jury for tiny communities** (§8.1). Default: proceed with fewer or
   none, and say so.
4. **Amendment on a solution with zero supporters** — threshold is
   `max(1, …)` = 1, so one upvote absorbs. Acceptable in Demo 1;
   revisit.
5. **Whether "strong" votes exist anywhere.** Default: no.
6. **Comment moderation.** None in Demo 1. Needed before friends beta.
