# DATABASE.md — Schema and Data Practice

> The database is the platform's permanent memory. Foundation tables
> are permanent from the adoption of CLAUDE.md; Iteration tables are
> permanent from the keeper build. This document names every table,
> every column, and which half it belongs to.
>
> Rules of the road are in CLAUDE.md Laws 2–6. This document says what
> those laws apply to.
>
> Changes to design philosophy require director approval. Adding a
> column to an Iteration table during a demo is routine and is recorded
> in HISTORY.md by the build session.

---

## 1. Conventions

- **PostgreSQL 16**, accessed through SQLAlchemy 2.x async ORM on
  asyncpg. Models in `backend/models.py`, grouped by half.
- **Primary keys**: `id INTEGER GENERATED ALWAYS AS IDENTITY` for
  Foundation tables (stable, short, appear in URLs). Iteration tables
  use the same; ids restart with each demo's fresh schema.
- **Timestamps**: `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` on
  every table. `updated_at` only where rows are mutable. All times UTC.
- **Soft delete**: `deleted_at TIMESTAMPTZ NULL` where deletion is
  possible. Rows are never physically deleted except by the account-
  anonymization procedure, which erases columns, not rows.
- **Enums** are PostgreSQL `ENUM` types named `<table>_<column>_enum`.
  Adding a value is a migration; removing one is forbidden (Law 3).
  Two enums are shared across tables and named for what they are, not
  where they live: `community_level_enum` (`city`, `county`, `state`,
  `federal`) and `verification_level_enum` (`unverified`, `phone`,
  `address`, `voter`). No other enum is shared.
- **Reserved words** are never table or column names (`references`,
  `order`, `user`, …); hence `umbrella_references`, not `references`.
- **Hashes** are `VARCHAR(64) NOT NULL` lowercase hex SHA-256 (not
  `CHAR`, which would space-pad); the application guarantees the length.
  Wherever this document writes `char(n)` — hashes, `abbreviation`,
  `fips` — read `VARCHAR(n)`; `CHAR` is never used.
- **Foreign keys** are always indexed (Law 4). Composite uniqueness is
  a named `UNIQUE` constraint: `uq_<table>_<cols>`.
- **Code citation**: documents refer to code as
  `backend/models.py::Solution`, never by line number.
- **Denormalized counters** (`net_score`, `upvote_count`) are caches.
  The vote rows are authoritative; a nightly job reconciles and logs
  drift.

---

## 2. The Two Halves

| Half | Tables | Migration practice |
|---|---|---|
| **Foundation** | `users`, `user_display_settings`, `refresh_tokens`, `email_verifications`, `password_resets`, `terms_versions`, `terms_acceptances`, `states`, `counties`, `cities`, `officials`, `settings`, `admin_actions`, `ai_actions`, `data_exports` | Alembic chain `foundation/`. Immutable once applied. |
| **Iteration** | `main_categories` (config-mirrored), `umbrellas`, `posts`, `post_solutions`, `post_communities`, `labels`, `solutions`, `solution_versions`, `amendments`, `amendment_similarity`, `amendment_similarity_votes`, `comments`, `comment_revisions`, `votes`, `umbrella_references`, `reference_feedback`, `cycles`, `ballot_items`, `ballot_votes`, `juries`, `jurors`, `jury_holdbacks`, `summaries` | Alembic chain `iteration/`. Until the keeper, regenerated as a single initial migration whenever a change alters the Iteration schema; the database is rebuilt from empty. |

Two Alembic branches in one `alembic/versions/` directory, labeled
`foundation` and `iteration`, so `alembic upgrade foundation@head` and
`alembic upgrade iteration@head` are independent. Iteration migrations
may declare foreign keys **to** Foundation tables; Foundation migrations
never reference Iteration tables.

`ai_actions` and `settings` are Foundation even though only Iteration
writes to them, because their contents are permanent record (CLAUDE §5,
Law 8) that must survive a demo teardown.

---

## 3. Foundation Tables

### 3.1 `users`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `email` | citext UNIQUE NOT NULL | lowercased; erased on deletion |
| `password_hash` | text NOT NULL | bcrypt; erased on deletion |
| `real_name` | text NOT NULL | erased on deletion |
| `display_name` | text NOT NULL | unique among live users (`uq_users_display_name` partial where `deleted_at IS NULL`); erased on deletion |
| `date_of_birth` | date NOT NULL | signup refuses if age on the signup date < `min_signup_age` (settings, DEMOCRACY §2.3); erased on deletion |
| `gender` | enum `users_gender_enum` (`woman`, `man`, `nonbinary`, `other`, `prefer_not_to_say`) NOT NULL | aggregate reporting only; erased on deletion |
| `political_party` | enum `users_political_party_enum` (`democratic`, `republican`, `green`, `libertarian`, `american_independent`, `peace_and_freedom`, `no_party_preference`, `other`, `prefer_not_to_say`) NOT NULL | California's qualified parties; aggregate only; erased on deletion |
| `county_id` | int FK `counties` NOT NULL | home county; **kept** on deletion (CLAUDE §6) |
| `city_id` | int FK `cities` NOT NULL | home city; must belong to `county_id` (checked in application); **kept** on deletion (CLAUDE §6) |
| `verification_level` | enum `verification_level_enum` (shared, §1) NOT NULL DEFAULT `unverified` | disclosed in aggregate; never weights a vote |
| `email_verified_at` | timestamptz NULL | write actions require non-null |
| `is_admin` | bool NOT NULL DEFAULT false | |
| `last_active_at` | timestamptz NULL | updated at most once per minute per user on authenticated requests; the "active user" source |
| `influence_score` | int NOT NULL DEFAULT 0 | deprecated until reputation is designed; not written |
| `created_at`, `updated_at`, `deleted_at` | | |

Indexes: `email`, `county_id`, `city_id`, `last_active_at`,
`(county_id, last_active_at)`, `(city_id, last_active_at)`.

**Anonymization procedure** (`backend/services/account.py::anonymize`),
one transaction: `email` → `deleted+<id>@invalid`, `password_hash` →
`'!'`, `real_name` → `''`, `display_name` → `Former Community Member`,
`date_of_birth` → `1900-01-01`, `gender` and `political_party` →
`prefer_not_to_say`, `county_id`/`city_id` → kept (CLAUDE §6: the
civic record stays in the right community), `last_active_at` → NULL
(a deleted account is never an active user), `deleted_at` set, all
`refresh_tokens` revoked, `user_display_settings` reset. Posts,
solutions, comments, votes, jury service, and AI outcomes are untouched
(CLAUDE §6).

### 3.2 `user_display_settings`

| Column | Type | Notes |
|---|---|---|
| `user_id` | int PK FK `users` | |
| `public_name_mode` | enum (`real_name`, `display_name`, `anonymous`) NOT NULL DEFAULT `display_name` | |
| `updated_at` | | |

**Author display** everywhere = per this row at render time:
`real_name` / `display_name` / "Anonymous Community Member". Deleted
users render "Former Community Member" regardless.

### 3.3 `refresh_tokens`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `user_id` | int FK `users` NOT NULL | |
| `token_hash` | char(64) UNIQUE NOT NULL | SHA-256 of the opaque token; raw token never stored |
| `expires_at` | timestamptz NOT NULL | now + `REFRESH_TOKEN_DAYS` |
| `revoked_at` | timestamptz NULL | |
| `replaced_by_id` | int FK `refresh_tokens` NULL | rotation chain; reuse of a replaced token revokes the whole chain |
| `created_at` | | |

Index: `user_id`, `expires_at`.

### 3.4 `email_verifications`, `password_resets`

Same shape: `id`, `user_id` FK, `token_hash` UNIQUE, `expires_at`,
`used_at NULL`, `created_at`. Verification tokens live
`EMAIL_VERIFY_HOURS`; reset tokens `PASSWORD_RESET_MINUTES`. Single use.

### 3.5 `terms_versions`, `terms_acceptances`

`terms_versions`: `id`, `version` text UNIQUE (e.g. `2026-09-draft-1`),
`privacy_policy_md` text, `terms_of_service_md` text, `published_at`.

`terms_acceptances`: `id`, `user_id` FK, `terms_version_id` FK,
`accepted_at`, `ip_hash` char(64) — SHA-256 of `IP_HASH_SECRET` +
address (a secret from `.env`, ARCHITECTURE §3), so the hash cannot be
reversed by enumerating addresses. Never deleted (legal record; contains
no PII beyond the user link, which anonymization severs by erasing the
user).

### 3.6 Geography: `states`, `counties`, `cities`

`states`: `id`, `name`, `abbreviation` char(2) UNIQUE.
`counties`: `id`, `state_id` FK, `name`, `fips` char(5) UNIQUE.
`cities`: `id`, `county_id` FK, `name`, `incorporated` bool, `fips`
char(7) UNIQUE NULL.

Seed: California and 58 counties from `backend/config/seed_geography.yaml`;
cities from `backend/config/seed_cities.csv` (both director-placed; the
build stops if either is absent or the CSV has no data rows). Unique
`(county_id, name)` on cities.

### 3.7 `officials`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `community_level` | enum `community_level_enum` (shared, §1) NOT NULL | |
| `community_entity_id` | int NOT NULL | id in `cities` / `counties` / `states` per level |
| `office` | text NOT NULL | "Mayor", "Council Member, District 3" |
| `holder_name` | text NULL | |
| `email` | text NOT NULL | |
| `source` | enum (`seed`, `user_correction`) NOT NULL | |
| `active` | bool NOT NULL DEFAULT true | |
| `created_at`, `updated_at` | | |

Index: `(community_level, community_entity_id)`. Seed from
`backend/config/seed_officials.yaml`. Demo 1: every email is
`OFFICIALS_TEST_EMAIL` from configuration.

**Community reference convention.** Anywhere a row belongs to a
community, it carries the pair `(community_level, community_entity_id)`
with the same enum. A database `CHECK` cannot enforce the polymorphic FK;
`backend/services/community.py::resolve` validates it, and the nightly
reconciliation job checks for orphans.

### 3.8 `settings`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `key` | text NOT NULL | one of DEMOCRACY.md §7.4 |
| `value` | text NOT NULL | parsed per key by `backend/services/settings.py` |
| `effective_from` | timestamptz NOT NULL DEFAULT now() | |
| `changed_by` | int FK `users` NULL | null = seed |
| `reason` | text NULL | |

Append-only. Current value = latest `effective_from` per key. Index
`(key, effective_from DESC)`. Seeded with every Demo 1 default on first
migration of the Foundation chain (a seed script, not a migration —
migrations are schema-only).

### 3.9 `admin_actions`

`id`, `admin_user_id` FK, `action` text, `subject_type` text,
`subject_id` int NULL, `old_value` jsonb NULL, `new_value` jsonb NULL,
`reason` text NULL, `created_at`. Append-only. Public read.

### 3.10 `ai_actions`

Exactly DEMOCRACY.md §9.2. `action_type` enum (`label`, `similarity`,
`reference_recommend`); `subject_type` text; `subject_id` int;
`model` text; `prompt_file` text; `prompt_hash` char(64); `input_hash`
char(64); `output` jsonb; `confidence` numeric(4,3) NULL;
`human_outcome` enum (`unreviewed`, `confirmed`, `corrected`,
`accepted`, `rejected`) NOT NULL DEFAULT `unreviewed`;
`human_outcome_by` FK `users` NULL; `human_outcome_at` NULL;
`created_at`. Index `(subject_type, subject_id)`, `created_at`. Only
`human_outcome_*` are ever updated, once.

For `similarity` actions there is no prompt file (DEMOCRACY §9.3):
`prompt_file` is the literal `(embeddings: no prompt file)` and
`prompt_hash` is 64 zeros. `model` still names the embedding model. No
other action type may use the sentinel.

Because Iteration ids restart per demo, `subject_id` alone is ambiguous
across demos. Column `demo_build` text NOT NULL (e.g. `demo-01`, from
configuration `BUILD_LABEL`) disambiguates; the keeper build's label is
frozen thereafter.

### 3.11 `data_exports`

`id`, `user_id` FK, `requested_at`, `completed_at` NULL, `file_path`
text NULL, `expires_at` (= `completed_at` + `EXPORT_FILE_HOURS`,
configuration, Demo 1: 48 — the window a person has to collect their
own data). Export JSON contains three things: the user's
Foundation rows (user, display settings, terms acceptances); their jury
service; and every Iteration row they authored or voted on, including
their own ballot votes.

The exporter respects the boundary rule. `backend/services/export.py`
(Foundation) gathers the Foundation data and then calls every
registered **export contributor**: a function `contribute(user_id) ->
dict` that Iteration registers at startup
(`backend/services/export_iteration.py::contribute`). Foundation code
never names an Iteration table; when no contributor is registered the
export contains only Foundation data and says so.

---

## 4. Iteration Tables

### 4.1 `main_categories`

Mirror of `backend/config/categories.py` so foreign keys exist: `id`,
`slug` UNIQUE, `name`, `active` bool. Synced from config at startup
(insert missing; never delete; mark inactive if removed from config).

### 4.2 `umbrellas`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `main_category_id` | int FK NOT NULL | |
| `community_level`, `community_entity_id` | | §3.7 convention |
| `name` | text NOT NULL | |
| `statement` | text NOT NULL | one paragraph |
| `status` | enum (`active`, `retired`) NOT NULL DEFAULT `active` | |
| `source` | enum (`seed`, `proposal`) NOT NULL | |
| `created_at`, `updated_at` | | |

Unique `(community_level, community_entity_id, main_category_id, name)`.
Index on the community pair.

### 4.3 `posts`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `author_id` | int FK `users` NOT NULL | |
| `problem_text` | text NOT NULL | 20–5,000 chars |
| `category_choice` | enum (`ai`, `author_selected`) NOT NULL | |
| `label_status` | enum (`pending`, `labeled`, `needs_review`, `unlabeled`) NOT NULL DEFAULT `pending` | |
| `ai_contribution_percentage` | smallint NOT NULL DEFAULT 0 | Law: every post records it |
| `content_hash` | char(64) NOT NULL | SHA-256 of canonical JSON `{problem_text, author_id, created_at, ai_contribution_percentage}`; immutable |
| `created_at` | | |
| `deleted_at` | | soft; no endpoint sets it in Demo 1 |

GIN index on to_tsvector('english', problem_text) — Home search (DEMOCRACY §12.1).

No column of `posts` is updated after insert except `label_status`.
A post is inserted in the same transaction as its `post_solutions`
rows, and the service refuses a post with zero solution texts (Law 1).

### 4.4 `post_solutions`

The author's solution texts as submitted, one row each, in order. The
staging record from which workshop solutions are created (DEMOCRACY
§4.1).

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `post_id` | int FK `posts` NOT NULL | |
| `position` | smallint NOT NULL | 1-based order in the post |
| `text` | text NOT NULL | 20–5,000 chars |
| `ai_contribution_percentage` | smallint NOT NULL DEFAULT 0 | |
| `content_hash` | char(64) NOT NULL | canonical JSON `{post_id, position, text, created_at}` |
| `created_at` | | |

GIN index on to_tsvector('english', text) — Home search (DEMOCRACY §12.1).

Unique `(post_id, position)`. Immutable.

### 4.5 `post_communities`

One row per community the author selected: `post_id` FK,
`community_level`, `community_entity_id`, `umbrella_id` FK NULL (set by
label or author), `main_category_id` FK NULL. PK `(post_id,
community_level, community_entity_id)`. Index `umbrella_id`.

### 4.6 `labels`

One row per labeling attempt per post-community: `id`, `post_id` FK,
`community_level`, `community_entity_id`, `ai_action_id` FK
`ai_actions` NULL, `main_category_id` FK NULL, `umbrella_id` FK NULL,
`confidence` numeric(4,3) NULL, `outcome` enum (`unreviewed`,
`confirmed_by_author`, `corrected_by_author`, `author_selected`) NOT
NULL, `corrected_umbrella_id` FK NULL, `created_at`. Never updated
except `outcome` and `corrected_umbrella_id`, once.

### 4.7 `solutions`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `umbrella_id` | int FK NOT NULL | |
| `post_id` | int FK `posts` NULL | null when created directly on the umbrella |
| `post_solution_id` | int FK `post_solutions` NULL | the text it was created from; one solution per (`post_solution_id`, `umbrella_id`) |
| `author_id` | int FK `users` NOT NULL | version-1 author (the post's author when created from a post) |
| `current_version` | int NOT NULL DEFAULT 1 | |
| `net_score` | int NOT NULL DEFAULT 0 | cache |
| `is_dominant` | bool NOT NULL DEFAULT false | cache of DEMOCRACY §7.1 |
| `dominant_since` | timestamptz NULL | |
| `last_ballot_cycle_id` | int FK `cycles` NULL | |
| `last_ballot_result` | enum (`passed`, `failed`, `held_back`) NULL | |
| `last_ballot_version` | int NULL | version that was on that ballot |
| `created_at`, `updated_at`, `deleted_at` | | |

Index `umbrella_id`, `author_id`, `post_id`, `post_solution_id`,
`(umbrella_id, net_score DESC, created_at)`. Unique
`(post_solution_id, umbrella_id)` where `post_solution_id IS NOT NULL`.

**Creation from a post** (`backend/services/solutions.py::create_from_post_community`):
in the same transaction that sets `post_communities.umbrella_id`, one
`solutions` row and one version-1 `solution_versions` row are inserted
per `post_solutions` row of that post. **Label correction** to a
different umbrella moves those solutions (updates `umbrella_id`) only
if every one of them has zero `votes` and zero `amendments`; otherwise
they are left in place (DEMOCRACY §4.1).

### 4.8 `solution_versions`

`id`, `solution_id` FK, `version` int, `text` text, `created_by` FK
`users` (v1: author; later: the amendment's author, or the author again
for a pre-vote edit — DEMOCRACY §4.3), `amendment_id` FK NULL,
`ai_contribution_percentage` smallint DEFAULT 0, `content_hash`
char(64) NOT NULL (canonical JSON `{solution_id, version, text,
created_by, created_at}`), `created_at`. Unique `(solution_id,
version)`. **Immutable: no column of an existing row is ever updated.**
`PATCH /solutions/{id}` inserts version n+1 and bumps
`solutions.current_version`; it never touches version n.

### 4.9 `amendments`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `solution_id` | int FK NOT NULL | |
| `base_version` | int NOT NULL | version it was written against |
| `author_id` | int FK `users` NOT NULL | |
| `proposed_text` | text NOT NULL | full replacement |
| `rationale` | text NOT NULL | 10–300 chars |
| `status` | enum (`proposed`, `absorbed`, `superseded`, `merged_into`, `withdrawn`) NOT NULL DEFAULT `proposed` | |
| `absorbed_as_version` | int NULL | |
| `merged_into_id` | int FK `amendments` NULL | |
| `net_score` | int NOT NULL DEFAULT 0 | cache |
| `ai_contribution_percentage` | smallint DEFAULT 0 | |
| `content_hash` | char(64) NOT NULL | canonical JSON `{solution_id, base_version, proposed_text, rationale, author_id, created_at}` |
| `created_at`, `updated_at` | | |

Index `solution_id`, `(solution_id, status)`.

### 4.10 `amendment_similarity`

`id`, `amendment_a_id` FK, `amendment_b_id` FK (a < b), `score`
numeric(4,3), `ai_action_id` FK `ai_actions`, `decision` enum
(`pending`, `same`, `different`) DEFAULT `pending`, `decided_at` NULL,
`created_at`. Unique `(amendment_a_id, amendment_b_id)`.

`amendment_similarity_votes`: `similarity_id` FK, `user_id` FK, `choice`
enum (`same`, `different`), `created_at`; PK `(similarity_id, user_id)`.

### 4.11 `comments`

`id`, `target_type` enum (`umbrella`, `solution`), `target_id` int,
`parent_id` FK `comments` NULL, `reply_to_comment_id` FK `comments`
NULL (set only when the reply was re-attached at the depth cap; the
comment it actually answered — DEMOCRACY §6), `depth` smallint NOT NULL
(0-based), `author_id` FK, `text` text (1–2,000; exactly what the
author typed, never a rendered name — the **current** revision's text,
a cache of the latest `comment_revisions` row), `current_revision`
smallint NOT NULL DEFAULT 1, `edited_at` NULL, `removed_at` NULL,
`net_score` int DEFAULT 0, `ai_contribution_percentage` smallint
DEFAULT 0, `content_hash` char(64) (the hash of revision 1 — immutable,
Law 6), `created_at`. Index `(target_type, target_id, parent_id)`,
`author_id`, `reply_to_comment_id`.

`comment_revisions`: `id`, `comment_id` FK, `revision` smallint, `text`,
`ai_contribution_percentage` smallint DEFAULT 0, `content_hash` char(64)
(canonical JSON `{comment_id, revision, text, author_id, created_at}`),
`created_at`. Unique `(comment_id, revision)`. Immutable. Revision 1 is
written with the comment in the same transaction; an edit inside
`comment_edit_minutes` inserts revision n+1 and updates `comments.text`,
`current_revision`, and `edited_at`. `reconcile.py` recomputes every
revision's hash and `comments.content_hash` against revision 1.

### 4.12 `votes`

Workshop votes, one table: `id`, `user_id` FK, `target_type` enum
(`solution`, `amendment`, `comment`), `target_id` int, `direction`
smallint CHECK IN (1, −1), `created_at`, `updated_at`. Unique
`(user_id, target_type, target_id)`. Index `(target_type, target_id)`.
Changing a vote updates `direction` and `updated_at`; removing a vote
deletes the row (the only hard delete in Iteration; the net-score
history is not a civic record, and the ballot votes — which are — are a
separate table that is never deleted).

### 4.13 `umbrella_references`, `reference_feedback`

`umbrella_references` (not `references` — a PostgreSQL reserved word):
`id`, `umbrella_id` FK, `url` text, `title` text, `note`
text (the "why"), `source` enum (`user`, `ai`), `added_by` FK `users`
NULL, `ai_action_id` FK NULL, `status` enum (`active`, `rejected`)
DEFAULT `active`, `created_at`. Index `umbrella_id`.

`reference_feedback`: `reference_id` FK `umbrella_references`, `user_id` FK, `useful` bool,
`created_at`; PK `(reference_id, user_id)`.

`ai_actions.output` for `reference_recommend` stores the queries, the
provider, and the raw result set (DEMOCRACY §9.4).

### 4.14 `cycles`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `community_level`, `community_entity_id` | | |
| `number` | int NOT NULL | sequential per community |
| `state` | enum (`workshop`, `prepared`, `jury_review`, `open`, `closed`, `published`) NOT NULL | |
| `settings_snapshot` | jsonb NOT NULL | every §7.4 key and value at prepare |
| `active_users_at_prepare` | int NULL | |
| `prepared_at`, `jury_review_started_at`, `opened_at`, `closed_at`, `published_at` | timestamptz NULL | |
| `transitioned_by` | jsonb NOT NULL DEFAULT '[]' | list of `{state, at, by}` |
| `created_at` | | |

Unique `(community_level, community_entity_id, number)`. Partial unique
index: at most one row per community with `state <> 'published'`.
Allowed transitions are exactly DEMOCRACY §10.1, including `prepared →
published` when and only when the cycle has zero ballot items; the
service refuses any other jump.

### 4.15 `ballot_items`

`id`, `cycle_id` FK, `solution_id` FK, `solution_version` int (frozen),
`umbrella_id` FK, `net_score_at_snapshot` int, `position` int (ballot
order per DEMOCRACY §10.2: umbrella name A–Z, net score at snapshot
descending, solution id ascending; 1-based), `held_back` bool DEFAULT
false, `yes_count` int NULL, `no_count` int NULL, `result` enum
(`passed`, `failed`, `held_back`) NULL, `created_at`. Unique
`(cycle_id, solution_id)`, unique `(cycle_id, position)`.

### 4.16 `ballot_votes`

`id`, `ballot_item_id` FK, `voter_id` FK `users`, `choice` enum (`yes`,
`no`), `voter_verification_level` `verification_level_enum` (shared,
§1), `created_at`, `updated_at`. Unique `(ballot_item_id, voter_id)`.
**Never deleted. A vote row is exposed to exactly one person: the voter
who cast it**, on `GET /cycles/{id}/ballot` (their own choices) and in
their own data export. No endpoint, admin or otherwise, returns another
user's vote or any vote with a voter id; everything else is counts.

### 4.17 `juries`, `jurors`, `jury_holdbacks`

`juries`: `id`, `cycle_id` FK (not unique — one row per draw),
`size_requested` int, `eligible_pool` jsonb (user ids), `random_bytes`
char(64), `drawn_at`, `superseded_at` timestamptz NULL, `redrawn_reason`
text NULL (on the **superseded** row: why it was replaced). Partial
unique index: at most one row per `cycle_id` with `superseded_at IS
NULL` — the current jury. Rows are never deleted; a re-draw sets
`superseded_at` on the old row and inserts a new one. Jurors of a
superseded jury keep their rows and statuses.

`jurors`: `id`, `jury_id` FK, `user_id` FK, `seat` smallint ("Juror n"),
`status` enum (`drawn`, `accepted`, `declined`, `replaced`,
`no_response`), `replaced_by_id` FK `jurors` NULL, `created_at`,
`updated_at`. Unique `(jury_id, user_id)`.

Two different things happen to jurors and the columns are used
differently for each. **Per-seat replacement** (DEMOCRACY §8.2): a juror
declines → their row keeps `status = declined` and `replaced_by_id`
points at the newly drawn juror's row. **Whole-jury supersession**
(DEMOCRACY §13 re-draw): every juror of the superseded jury gets
`status = replaced` and `replaced_by_id` stays NULL — the replacement is
the new `juries` row, not a seat. The summary header's "r replaced"
(DEMOCRACY §11.2) counts `declined` jurors on the **current** jury; it
never counts the `replaced` status.

`jury_holdbacks`: `id`, `jury_id` FK, `juror_id` FK, `ballot_item_id` FK,
`reason_category` enum (`duplicate`, `not_actionable`, `incomplete`,
`outside_governance_level`, `other`), `reason_text` text (20–1,000),
`created_at`. Unique `(juror_id, ballot_item_id)`. A **seated** juror
is one with `status = accepted`; `no_response` jurors are not seated
and not replaced (DEMOCRACY §8.2). A hold-back takes effect when rows
for a `ballot_item_id` from seated jurors exceed half the number of
seated jurors, computed once when the ballot is opened. `juries` also
records `seated_count` int (set at open) so the summary can print
"drawn / seated".

### 4.18 `summaries`

`id`, `cycle_id` FK UNIQUE, `data` jsonb NOT NULL (the canonical
document data, DEMOCRACY §11.2), `summary_hash` char(64) NOT NULL,
`published_at`, `pdf_path` text NULL. Immutable after publish.

---

## 5. Seed Files (director-placed)

| File | Fills | Build behavior if missing |
|---|---|---|
| `backend/config/seed_geography.yaml` | state and 58 counties | stop and report |
| `backend/config/seed_cities.csv` | incorporated cities (county, city, incorporated, fips) — director exports from the CA Department of Finance E-1 list | stop and report if it contains no data rows |
| `backend/config/seed_officials.yaml` | officials | stop and report |
| `backend/config/seed_umbrellas.yaml` | umbrellas for test communities | stop and report |
| `backend/config/seed_settings.yaml` | settings defaults (DEMOCRACY §7.4) | stop and report |
| `backend/config/categories.py` | main_categories | exists; code |

Seeding is `python -m backend.seed --dry-run` / `--apply`. Re-runnable:
a second run reports what already holds and writes nothing. Reports
coverage both ways: rows in file not in DB, rows in DB not in file.

The runner substitutes `${NAME}` in any YAML string value with the
configuration value of that name (read through `settings_env.py`, never
`os.environ`), and stops with the name in the error if it is unset.
Demo 1 uses this for `${OFFICIALS_TEST_EMAIL}` in
`seed_officials.yaml`. The cities CSV has a header row `county,city,
incorporated,fips`; county names must match `seed_geography.yaml`
exactly or the runner stops and lists the mismatches.

The seed files live in `backend/config/` — the director moves them
there from `seeds/` in the follow-up PR (TODO P0-12); the build stops
if they are not found at these paths.

---

## 6. Migration Practice

- Two Alembic branch labels, `foundation` and `iteration`
  (`alembic revision --branch-label foundation -m "..."`).
- Migrations are schema-only. No `INSERT`, no `UPDATE`, no backfill.
  Seeds and data fixes are scripts under `backend/scripts/`, each
  re-runnable with `--dry-run`.
- `backend/scripts/verify_schema.py` builds a scratch database from
  both chains and diffs it against the live database and against the
  ORM metadata. Run after every migration; output pasted into HISTORY.
- Foundation chain: never edited after `alembic upgrade`. Iteration
  chain: during demos, the build may delete the chain and regenerate a
  single initial migration; from the keeper build, immutable.
- Applying to a demo database: `alembic upgrade foundation@head &&
  alembic upgrade iteration@head`.

---

## 7. Nightly Reconciliation

`backend/scripts/reconcile.py` (also runnable on demand):

1. Recompute `net_score` for every solution, amendment, comment from
   `votes`; log and correct drift.
2. Re-evaluate `is_dominant` for every solution against the current
   active-user count (DEMOCRACY §7.1); log every status change with the
   numbers that caused it.
3. Check every `(community_level, community_entity_id)` pair resolves.
4. Check every `content_hash` and `summary_hash` recomputes to its
   stored value; any mismatch is a critical alert, not a correction.
5. Report counts per table as a before/after snapshot.

---

## 8. What Is Deliberately Not Here

- Reputation / influence: column exists, unused.
- Proposal tables (`proposals`, `proposal_votes`): Demo 2.
- Notification tables: Demo 1 is in-app flags only, derived on read.
- Federal entity.
- Any per-user personalization table: feed-v0 has none.
