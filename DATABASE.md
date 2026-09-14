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
- **Hashes** are `CHAR(64)` hex SHA-256.
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
| **Iteration** | `main_categories` (config-mirrored), `umbrellas`, `posts`, `post_communities`, `labels`, `solutions`, `solution_versions`, `amendments`, `amendment_similarity`, `comments`, `votes`, `references`, `reference_feedback`, `cycles`, `ballot_items`, `ballot_votes`, `juries`, `jurors`, `jury_holdbacks`, `summaries` | Alembic chain `iteration/`. Regenerated fresh per demo until the keeper. |

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
| `date_of_birth` | date NOT NULL | COPPA; erased on deletion |
| `gender` | enum `users_gender_enum` (`woman`, `man`, `nonbinary`, `other`, `prefer_not_to_say`) NOT NULL | aggregate reporting only; erased on deletion |
| `political_party` | enum `users_political_party_enum` (`democratic`, `republican`, `green`, `libertarian`, `american_independent`, `peace_and_freedom`, `no_party_preference`, `other`, `prefer_not_to_say`) NOT NULL | California's qualified parties; aggregate only; erased on deletion |
| `county_id` | int FK `counties` NOT NULL | home county; nulled on deletion |
| `city_id` | int FK `cities` NOT NULL | home city; must belong to `county_id` (checked in application); nulled on deletion |
| `verification_level` | enum `users_verification_level_enum` (`unverified`, `phone`, `address`, `voter`) NOT NULL DEFAULT `unverified` | disclosed in aggregate; never weights a vote |
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
`prefer_not_to_say`, `county_id`/`city_id` → kept (needed so past votes
still count in the right community — location is not identifying at
city granularity; director decision recorded 2026-09-07), `deleted_at`
set, all `refresh_tokens` revoked, `user_display_settings` reset. Posts,
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
`accepted_at`, `ip_hash` char(64). Never deleted (legal record; contains
no PII beyond the user link, which anonymization severs by erasing the
user).

### 3.6 Geography: `states`, `counties`, `cities`

`states`: `id`, `name`, `abbreviation` char(2) UNIQUE.
`counties`: `id`, `state_id` FK, `name`, `fips` char(5) UNIQUE.
`cities`: `id`, `county_id` FK, `name`, `incorporated` bool, `fips`
char(7) UNIQUE NULL.

Seed: California, 58 counties, all incorporated cities, from
`backend/config/seed_geography.yaml` (director-placed; the build stops
if absent). Unique `(county_id, name)` on cities.

### 3.7 `officials`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `community_level` | enum `community_level_enum` (`city`, `county`, `state`, `federal`) NOT NULL | |
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

Because Iteration ids restart per demo, `subject_id` alone is ambiguous
across demos. Column `demo_build` text NOT NULL (e.g. `demo-01`, from
configuration `BUILD_LABEL`) disambiguates; the keeper build's label is
frozen thereafter.

### 3.11 `data_exports`

`id`, `user_id` FK, `requested_at`, `completed_at` NULL, `file_path`
text NULL, `expires_at`. Export JSON contains the user's row, display
settings, terms acceptances, and every Iteration row they authored or
voted on, assembled by `backend/services/export.py`.

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
| `deleted_at` | | soft |

### 4.4 `post_communities`

One row per community the author selected: `post_id` FK,
`community_level`, `community_entity_id`, `umbrella_id` FK NULL (set by
label or author), `main_category_id` FK NULL. PK `(post_id,
community_level, community_entity_id)`. Index `umbrella_id`.

### 4.5 `labels`

One row per labeling attempt per post-community: `id`, `post_id` FK,
`community_level`, `community_entity_id`, `ai_action_id` FK
`ai_actions` NULL, `main_category_id` FK NULL, `umbrella_id` FK NULL,
`confidence` numeric(4,3) NULL, `outcome` enum (`unreviewed`,
`confirmed_by_author`, `corrected_by_author`, `author_selected`) NOT
NULL, `corrected_umbrella_id` FK NULL, `created_at`. Never updated
except `outcome` and `corrected_umbrella_id`, once.

### 4.6 `solutions`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `umbrella_id` | int FK NOT NULL | |
| `post_id` | int FK NULL | null when created directly on the umbrella |
| `author_id` | int FK `users` NOT NULL | version-1 author |
| `current_version` | int NOT NULL DEFAULT 1 | |
| `net_score` | int NOT NULL DEFAULT 0 | cache |
| `is_dominant` | bool NOT NULL DEFAULT false | cache of DEMOCRACY §7.1 |
| `dominant_since` | timestamptz NULL | |
| `last_ballot_cycle_id` | int FK `cycles` NULL | |
| `last_ballot_result` | enum (`passed`, `failed`, `held_back`) NULL | |
| `last_ballot_version` | int NULL | version that was on that ballot |
| `created_at`, `updated_at`, `deleted_at` | | |

Index `umbrella_id`, `author_id`, `(umbrella_id, net_score DESC,
created_at)`.

### 4.7 `solution_versions`

`id`, `solution_id` FK, `version` int, `text` text, `created_by` FK
`users` (v1: author; later: the amendment's author), `amendment_id` FK
NULL, `ai_contribution_percentage` smallint DEFAULT 0, `content_hash`
char(64) NOT NULL (canonical JSON `{solution_id, version, text,
created_by, created_at}`), `created_at`. Unique `(solution_id,
version)`. Immutable.

### 4.8 `amendments`

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
| `content_hash` | char(64) NOT NULL | |
| `created_at`, `updated_at` | | |

Index `solution_id`, `(solution_id, status)`.

### 4.9 `amendment_similarity`

`id`, `amendment_a_id` FK, `amendment_b_id` FK (a < b), `score`
numeric(4,3), `ai_action_id` FK `ai_actions`, `decision` enum
(`pending`, `same`, `different`) DEFAULT `pending`, `decided_at` NULL,
`created_at`. Unique `(amendment_a_id, amendment_b_id)`.

`amendment_similarity_votes`: `similarity_id` FK, `user_id` FK, `choice`
enum (`same`, `different`), `created_at`; PK `(similarity_id, user_id)`.

### 4.10 `comments`

`id`, `target_type` enum (`umbrella`, `solution`), `target_id` int,
`parent_id` FK `comments` NULL, `depth` smallint NOT NULL, `author_id`
FK, `text` text (1–2,000), `edited_at` NULL, `removed_at` NULL,
`net_score` int DEFAULT 0, `ai_contribution_percentage` smallint DEFAULT
0, `content_hash` char(64), `created_at`. Index `(target_type,
target_id, parent_id)`, `author_id`.

### 4.11 `votes`

Workshop votes, one table: `id`, `user_id` FK, `target_type` enum
(`solution`, `amendment`, `comment`), `target_id` int, `direction`
smallint CHECK IN (1, −1), `created_at`, `updated_at`. Unique
`(user_id, target_type, target_id)`. Index `(target_type, target_id)`.
Changing a vote updates `direction` and `updated_at`; removing a vote
deletes the row (the only hard delete in Iteration; the net-score
history is not a civic record, and the ballot votes — which are — are a
separate table that is never deleted).

### 4.12 `references`, `reference_feedback`

`references`: `id`, `umbrella_id` FK, `url` text, `title` text, `note`
text (the "why"), `source` enum (`user`, `ai`), `added_by` FK `users`
NULL, `ai_action_id` FK NULL, `status` enum (`active`, `rejected`)
DEFAULT `active`, `created_at`. Index `umbrella_id`.

`reference_feedback`: `reference_id` FK, `user_id` FK, `useful` bool,
`created_at`; PK `(reference_id, user_id)`.

`ai_actions.output` for `reference_recommend` stores the queries, the
provider, and the raw result set (DEMOCRACY §9.4).

### 4.13 `cycles`

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

### 4.14 `ballot_items`

`id`, `cycle_id` FK, `solution_id` FK, `solution_version` int (frozen),
`umbrella_id` FK, `net_score_at_snapshot` int, `position` int,
`held_back` bool DEFAULT false, `yes_count` int NULL, `no_count` int
NULL, `result` enum (`passed`, `failed`, `held_back`) NULL,
`created_at`. Unique `(cycle_id, solution_id)`.

### 4.15 `ballot_votes`

`id`, `ballot_item_id` FK, `voter_id` FK `users`, `choice` enum (`yes`,
`no`), `voter_verification_level` (same enum as users), `created_at`,
`updated_at`. Unique `(ballot_item_id, voter_id)`. **Never deleted;
never exposed per-voter through any endpoint, including admin.** Counts
only.

### 4.16 `juries`, `jurors`, `jury_holdbacks`

`juries`: `id`, `cycle_id` FK UNIQUE, `size_requested` int,
`eligible_pool` jsonb (user ids), `random_bytes` char(64), `drawn_at`,
`redrawn_reason` text NULL.

`jurors`: `id`, `jury_id` FK, `user_id` FK, `seat` smallint ("Juror n"),
`status` enum (`drawn`, `accepted`, `declined`, `replaced`,
`no_response`), `replaced_by_id` FK `jurors` NULL, `created_at`,
`updated_at`. Unique `(jury_id, user_id)`.

`jury_holdbacks`: `id`, `jury_id` FK, `juror_id` FK, `ballot_item_id` FK,
`reason_category` enum (`duplicate`, `not_actionable`, `incomplete`,
`outside_governance_level`, `other`), `reason_text` text (20–1,000),
`created_at`. Unique `(juror_id, ballot_item_id)`. A hold-back takes
effect when rows for a `ballot_item_id` exceed half of seated jurors
(`status = accepted`), computed at review close.

### 4.17 `summaries`

`id`, `cycle_id` FK UNIQUE, `data` jsonb NOT NULL (the canonical
document data, DEMOCRACY §11.2), `summary_hash` char(64) NOT NULL,
`published_at`, `pdf_path` text NULL. Immutable after publish.

---

## 5. Seed Files (director-placed)

| File | Fills | Build behavior if missing |
|---|---|---|
| `backend/config/seed_geography.yaml` | states, counties, cities | stop and report |
| `backend/config/seed_officials.yaml` | officials | stop and report |
| `backend/config/seed_umbrellas.yaml` | umbrellas for test communities | stop and report |
| `backend/config/seed_settings.yaml` | settings defaults (DEMOCRACY §7.4) | stop and report |
| `backend/config/categories.py` | main_categories | exists; code |

Seeding is `python -m backend.seed --dry-run` / `--apply`. Re-runnable:
a second run reports what already holds and writes nothing. Reports
coverage both ways: rows in file not in DB, rows in DB not in file.

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
