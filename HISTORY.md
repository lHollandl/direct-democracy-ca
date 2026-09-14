# HISTORY.md — Session Log

> The project's running journal: what was decided, encountered, and
> learned, session by session. TODO.md holds the checklist; this holds
> the narrative. Append-only. Never edit a past entry — a reversal goes
> in the current entry. Format and rules: CLAUDE.md, "How HISTORY.md
> Works". The last two entries are read at the start of every session.

---

## Legacy Log (before 2026-09-05)

*The entries below are the original session log, kept verbatim. They
use the old "Day X — Prompt Y" format and describe the legacy code on
`main` (commit 263d4c6). Design decisions recorded here that survive
were carried into DEMOCRACY.md and PROJECT.md; the rest are in the
parking lot.*

## Project Origin

Direct Democracy Cali is a civic engagement platform built to give California communities the tools to document problems, propose solutions, and apply democratic pressure to government. The platform is designed around radical transparency, democratic neutrality, and AI accountability. Every algorithmic decision is public. Every AI action is logged. The community governs the category taxonomy through a democratic proposal system.

Full principles and technical laws are in `CLAUDE.md`.

---

## Day 3 — Prompt 3
**What was built:**
Connected Next.js frontend — signup, login, and feed pages built and verified. Axios API client with JWT auth. Root path redirects to /feed.

---

## Day 3 — Design Session 1
**What was decided:**
Finalized the category and umbrella architecture.

**Key decisions:**

**Category and umbrella architecture:**
- Subcategory = umbrella problem. They are the same thing, not two separate concepts.
- Main category = broad topic bucket (e.g. "Roads and Infrastructure") — controlled by the platform, grown through community approval.
- Subcategory = the umbrella problem itself. Posts are assigned to subcategories/umbrellas. Solutions aggregate inside umbrellas. Votes happen inside umbrellas.
- Labeling a post and assigning it to an umbrella are one action, not two separate steps.
- Three ways a post gets categorized: (1) AI auto-assigns to closest existing umbrella, (2) user manually selects, (3) user proposes a new category/umbrella via the proposal pipeline.
- AI is a sorting assistant, never a decision-maker. AI never creates new umbrella problems. Only humans do, through the proposal system.

**Democratic proposal system — full detail:**

*Proposing a new subcategory/umbrella:*
- User disagrees with AI label → browses existing subcategories → nothing fits → proposes a new name
- Must attach to an existing approved main category (cannot attach to a pending/proposed main category)
- User selects which governance levels the proposal applies to (city / county / state / federal)
- Proposal enters Pending Approval status for those governance levels

*Proposing a new main category:*
- User proposes an entirely new main category
- Goes through same approval process
- No subcategories can be added under it until it is fully approved

*Similarity grouping (duplicate prevention):*
- Layer 1: AI flags new proposals similar to existing pending proposals above a similarity threshold
- Layer 2: Users confirm or reject the AI-suggested merge — AI suggests, humans decide
- Prevents duplicate umbrella problems from cluttering the system

*Voting thresholds (dynamic by governance level):*
- City — 2% of active users OR 50 votes minimum, whichever is lower
- County — 1.5% of active users OR 100 votes minimum
- State — 1% of active users OR 500 votes minimum
- Federal — 0.5% of active users OR 1,000 votes minimum
- Minimum 7-day window before anything can be approved
- Proposals with no new votes for 30 days go dormant (not deleted — revivable if someone new votes)

*When a proposal is approved:*
- Becomes an official subcategory/umbrella in the selected governance levels
- AI labeling pipeline immediately starts routing new matching posts to it
- Users can immediately select it when submitting posts
- Posts previously assigned to a similar umbrella may be surfaced for re-review

*Reputation points — early contribution model:*
- Reputation is cosmetic only (clout, no spending power — per §3 Democratic Neutrality, influence never affects ranking)
- Points awarded on a time-decay curve when a proposal passes:
  - Day 1 supporter = 100 points
  - Day 7 supporter = 70 points
  - Day 30 supporter = 30 points
  - After approval = 5 points (for spreading awareness)
- Original proposer gets a founder bonus multiplier
- Failed proposals = 0 points for everyone (the risk makes the reward meaningful)
- If similar proposals are merged, all early supporters of both proposals earn points; first proposer of the winning name gets the founder bonus

*Open design decisions at time of lock — not yet resolved:*
- Exact reputation point values and decay curve numbers
- AI similarity score threshold for proposal grouping
- Whether dormant proposals can be re-proposed by someone else
- What happens to posts assigned to an umbrella whose proposal is later rejected (revert to AI suggestion?)
- Final fixed main category list

**Fixed category list architecture:**
- A config file at `backend/config/categories.py` holds the official list
- Every entry is a main category only — subcategories are created through the democratic proposal system
- The AI must choose a main category from this fixed list (no free-text categories)
- The AI assigns to the closest existing approved subcategory/umbrella within that main category
- If no subcategories exist yet for a main category, AI assigns to main category only and flags for human review
- Current placeholder list (10 categories, to be replaced before launch):
  Roads and Infrastructure, Housing and Homelessness, Public Safety, Environmental Issues, Education, Public Transit, Water and Utilities, Parks and Recreation, Economic Development, Government Accountability
- This list grows through the democratic proposal system after launch. Platform owner controls the seed list.

**Why:** Keeping AI as a sorting tool (not a decision-maker) is a constitutional requirement (§5). The democratic proposal system ensures the category taxonomy is itself democratic and community-owned. Fixed main categories give the AI a bounded, auditable choice set while still allowing the community to expand the taxonomy over time.

---

## Day 3 — Design Session 1b (Post Creation Flow Vision)
**What was decided:**
The full intended UX for post creation was designed alongside the category architecture.

**The four-step post creation flow:**
1. Write your problem description
2. Write your proposed solution
3. Select governance levels (city / county / state / federal)
4. Category assignment — three options:
   - **Option A:** Let AI decide (default — fastest path for most users)
   - **Option B:** Pick from existing approved categories yourself
   - **Option C:** Propose a new category or umbrella problem

**Key UX decision on Option C:**
Option C launches the proposal flow inline within the post creation screen. The post still submits immediately. The category proposal enters the approval pipeline separately and asynchronously. This makes proposing new ideas feel fast and natural — not like a bureaucratic side process that blocks the user from posting.

**Why this matters:** If proposing a new category required the user to leave the post creation flow, complete a separate process, wait for approval, and then come back to submit their post — most users would never do it. Keeping it inline removes that friction while preserving the democratic integrity of the approval system.

---

## Day 3 — Prompt 4
**What was built:**
AI labeling and umbrella assignment pipeline.

**Details:**
- `ai/labeler.py` — standalone labeler module using Ollama/llama3.2
- Background task wired into `POST /posts` — labeling runs after post saves, non-blocking
- Subcategory = umbrella problem confirmed in code
- AI always assigns to closest existing umbrella (never creates new ones)
- Four end-to-end verification tests passed

---

## Day 3 — Design Session 2
**What was decided:**
Locked the Umbrella AI Agent architecture.

**Key decisions:**
- Two distinct AI roles: Labeler AI (background utility, no personality) and Umbrella AI Agent (active participant with reputation)
- Each umbrella gets its own dedicated AI agent
- Agents have an approval rating voted on by the community
- Access tier system based on approval: Full (>60%), Reduced (30–60%), Minimal (<30% — suspended from output, observes only)
- Demoted agents are not deleted — they can earn their way back
- Every agent action is permanently logged in a public AIAgentAction table (satisfies §5 AI Accountability)
- `model_type` stored as a string — allows swapping models via database update, not code change
- Agents start with a platform default system prompt + constitution; community can propose amendments via the proposal system
- Reward system: when a championed solution is deployed by government, agent's `lifetime_reward_score` is incremented
- High-performing agents' post + outcome history becomes future fine-tuning training data

**Open decisions remaining at time of lock:**
- Exact approval thresholds for tier transitions (proposed: 60% / 30%)
- How the community amends an agent's system prompt — proposal system or direct vote?
- What formally qualifies a solution as "deployed by government" for reward triggering
- Whether a Minimal-tier suspended agent's past actions remain visible

---

## Day 3 — Prompt 5
**What was built:**
Post creation form at `/posts/new`.

**Details:**
- Four sections: problem description, proposed solution, location/governance, category
- Cascading county → city dropdowns
- Manual category selection stores a Label row
- Auth guard with `getMe()` validation — unauthenticated users redirected
- Inline error handling
- Tailwind dark theme consistent with rest of frontend

---

## Day 3 — Prompt 5 Fix
**What was fixed:**
Feed display bugs.

**Details:**
- `username` added to `PostResponse` schema on backend; displayed as "Posted by [username]" on feed cards
- City name lookup cache built on feed mount using `GET /cities` — replaces "City #1" with real city name

---

## Day 3 — Prompt 6 (Schema Migration 1)
**Migration:** `9ad861d88d23`

**Changes:**
- `solutions.title` → nullable (deprecated, stop writing to it)
- `solutions.governance_levels` ARRAY(String) nullable — added
- `users.county_id` and `users.city_id` FK columns added with indexes

---

## Day 3 — Prompt 6 (Schema Migration 2)
**Migration:** `b9f42abdbef8`

**Changes:**
- Dropped unique constraint `solutions_post_id_key`
- Added `ix_solutions_post_id` index
- Allows multiple solutions per post (one-to-many relationship)

---

## Day 3 — Prompt 6 (API Changes)
**What was changed:**

- `PostCreate` schema: `solution_title` / `solution_content` replaced by `solutions[]` array (`SolutionInput`: content + governance_levels)
- `POST /posts` now creates one Solution row per item in the array
- `UserCreate` accepts `county_id` and `city_id`
- `GET /auth/me` now returns `county_id`, `city_id`, `county_name`, `city_name`

---

## Day 3 — Prompt 6 (Frontend Changes)
**What was changed:**

- Signup page: cascading county → city dropdowns added (optional, conversational copy)
- `api.ts`: `UserProfile` updated with location fields; `signup()` accepts `countyId` / `cityId`; `Post.solution` → `solutions[]`; `SolutionSummary` updated
- Feed: `post.solution` → `post.solutions[0]`

---

## Day 3 — Prompt 6 (Post Form Redesign)
**What was redesigned:**
`/posts/new` rebuilt as civic conversation UI.

**Details:**
- Three rounded panel layout: problem textarea, dynamic solutions list (add/remove), governance toggle cards
- Governance toggle cards display user's real city and county name
- Auto-generates post title from problem content
- `createPost()` updated to submit `solutions[]` array

---

## Day 3 — Prompt 6 (Complete)
**Full Prompt 6 summary:**
Multi-solution posts, governance level selection, user location at signup, `/auth/me` with county_name/city_name, and civic conversation post form fully integrated. All four end-to-end checks passed.

---

## Day 3 — Reorganization Session
**What was decided:**
Paused feature development to improve project organization before building further.

**Changes made:**
- `TODO.md` restructured as a clean phase-based task tracker. Long design prose removed and moved to dedicated design docs.
- `HISTORY.md` created (this document) — session log extracted from TODO.md and given its own permanent home.
- Document index established. Design decisions will live in `docs/design/` folder.
- Next step: create `docs/design/CATEGORIES.md` to finalize the fixed main category list and subcategory structure before any more code is written.

**Why:** The project was accumulating design decisions, technical debt notes, and future feature prose inside a single TODO file. Separating concerns makes the project easier to audit, easier to hand off to new team members, and ensures Claude Code always reads clean, focused documents at the start of each session.

---

## New Format Log (2026-09-05 onward)

## 2026-09-05 — Session 1 (Claude.ai planning session — framework migration and concept design)

**Completed:**
- Decided to migrate the project documents to the AnimationDirector seven-document framework: CLAUDE.md (rewrite), PROJECT.md (new), DEMOCRACY.md (new — the civic process; absorbs docs/design/*), ARCHITECTURE.md (new), DATABASE.md (new), TODO.md (restructure), HISTORY.md (this format).
- Defined the scope of Demo 1: the full cycle from signup to summary document emailed to a representative.

**Decisions made:**
1. Two development modes. **Demo mode** (now): throwaway builds, fresh database each build, one large prompt per rebuild, documents carry the design forward. **Keeper mode** (later): full rigor — numbered immutable migrations, Step 0 pre-checks, pasted evidence — begins when a build's data is worth keeping. To be written into CLAUDE.md.
2. No solution, no post — confirmed constitutional.
3. Two-stage lifecycle per problem: continuous **workshop** inside umbrellas; monthly one-week **ballot** per governance level.
4. Ballot qualification: public support threshold (same shape as the proposal thresholds), then a randomly drawn citizen **jury that can only hold back**, with a written public reason. Never adds.
5. Ballot vote: yes / no on deployment.
6. Amendments attach to a solution and are absorbed only on strong support or when many similar amendments are grouped (AI groups, humans confirm). Absorption creates a new solution version; prior versions kept.
7. Solutions are community-owned once posted.
8. Summary document: one per governance level per ballot cycle, identical for everyone in that community, hashed and public. Each user receives the set for their city, county, and state. Reconciles the HOPES PDF-cadence conflict.
9. Signup collects real name, city, county, gender, political party. Gender and party are for aggregate reporting only, never personalization — CLAUDE.md to state this. Users control public display; anonymous posting allowed. Real name is erased on account deletion per §6.
10. Account **verification level** (`unverified` / `phone` / `address` / `voter`): disclosed in aggregate, never used to weight votes. Method choice open — parking lot research item. Summary documents state the verification mix honestly.
11. Demo 1 feed: newest first, filtered by governance level. Smart feed designed after use.
12. Jury: random draw from users at the governance level, even in the demo.
13. Umbrella page: problem → problem discussion → solutions (ranked) → dominant solutions, each with amendments and solution discussion → references. "Dominant" is a public support threshold.
14. Comments on problems and on dominant solutions; up/down everywhere (solutions, amendments, comments). Downvotes never hide content.
15. References: user-added and AI-recommended, both in Demo 1. AI source is a web search API; provider is configuration; every AI reference records query, provider, and raw results. Umbrella displays an AI-influence score.
16. Demo director controls: manual ballot open/close (real timer is configuration); summary emails go to a director-controlled address.
17. Street name and area code from HOPES §11 are dropped.

**Issues encountered:**
- CLAUDE.md Session Law directs session logs to the bottom of TODO.md; the reorganization moved them to HISTORY.md. Fix in the rewrite.
- TODO.md indexes four `docs/design/*.md` files that were not uploaded; existence unconfirmed.
- HOPES §5 cluster mechanics are behavioral profiling and can only be constitutional as opt-in, visible, user-adjustable personalization (§3). Must be stated when the smart feed is designed.
- Whether voting code exists (`routers/solutions.py` is described as "Solution voting") is unverified until the repo is read.

**Parked (to PROJECT.md parking lot):**
smart feed / cluster mechanics; Small Voice implementation; real representative lookup and ToS implications; verification methods; AI-merged umbrella solution (Umbrella AI Agent, Phase 3); reputation points; platform self-governance page; blockchain layer; whether "strong" votes apply anywhere.

**Document changes flagged:**
- CLAUDE.md rewrite requires director approval of wording before it is applied.
- HOPES.md and DirectDemocracyCali_ProjectSummary_v2.md to be retired to `archive/` once PROJECT.md and DEMOCRACY.md exist.





---

## 2026-09-05 — Session 2 (Claude.ai planning session — concept design, continued)

**Decisions made (continuing the numbering from Session 1):**
18. Foundation / Iteration split. Foundation (infrastructure, accounts, identity, verification, user rights, legal, email, geography, officials, settings, admin log, AI action log, deployment) is built once, kept, and under full rigor from adoption of the new CLAUDE.md. Iteration (the civic machinery and its UI) is rebuilt per demo until a keeper build. Boundary rule: Iteration reads Foundation tables, never migrates them; Foundation never touches Iteration tables.
19. Hosting deferred; local only. Deployment is a Foundation task with no design yet.
20. Foundation and Iteration advance in parallel; in practice alternating runs. Each brief states which half it belongs to.
21. Summary document is a web page, canonical, hashed; PDF is an export.
22. Failed ballot items appear in the summary with counts.
23. Voter comments are not in the summary; the website holds them.
24. Amendment absorption is measured against the solution's own supporters, not the community.
25. AI influence on a post or solution = diff-based share of text produced by platform-provided AI; reads 0% until a writing assist exists; label says "on this platform".
26. Umbrella AI influence is an action list, not a percentage.
27. Jurors anonymous ("Juror n of m"); reasons public; printed in the summary.
28. Jury draw is platform random and logged (pool, drawn ids, random bytes). Provable reproducibility parked.
29. Delivery is user-send only (`mailto:` from the summary page). The platform maintains an officials directory and sends nothing itself. Iteration therefore sends no email at all.
30. Threshold demo defaults accepted: dominant 5% / 3; amendment 25% / 3; ballot 10% / 5 with 3 days dominant; no ballot cap.
31. Small Voice, self-governance, and the California AI model recorded as parking-lot entries with a design direction each.
32. Look and feel: a short style brief (mobile-first, plain language, one accent, California photography, works with images off); UI iterated between demos rather than designed up front.

**Notes:**
- The user asked for plain-English versions of several questions during the session. Recorded so future sessions ask decisions in the director's terms, with a concrete example, not in framework jargon.

---

## 2026-09-06 — Session 1 (Claude.ai planning session — development method and sandbox)

**Decisions made:**
1. Development method differs from AnimationDirector: the documents are the build. Claude Code runs long, unattended, against the documents; the Claude.ai project's role becomes document writer, brief writer, and demo reviewer rather than prompt writer. Each demo gets a one-page build brief.
2. Sandbox: Docker Sandboxes (microVM with its own Docker daemon) on the director's Ubuntu workstation, per Anthropic's guidance for unattended `--dangerously-skip-permissions` runs. The built-in Bash sandbox alone is insufficient for unattended work.
3. Trial isolation: one git branch per trial (`demo/NN`) from `main`, checked out as a git worktree into its own directory, built in its own sandbox with its own database. Foundation merges to `main` by PR; demo branches never merge unless declared a keeper.
4. Sandbox access model: the trial directory, network to host Ollama, `api.anthropic.com`, and package registries; a GitHub credential that cannot reach `main`. Nothing else.
5. Foundation is also built by long runs. Rigor moves to the documents, the tests, and separate audit runs (AUDIT.md — an eighth document).

**Issues encountered:**
- Rapid rebuilds and the "never delete a column" law were in tension; resolved by the Foundation / Iteration split (2026-09-05 decision 18) plus keeper-mode timing, now written into CLAUDE.md.

---

## 2026-09-07 — Session 1 (Claude.ai planning session — security cleanup and document drafting)

**Completed:**
- CLAUDE.md rewrite drafted and **approved by the director as written**. Eight principles kept with additions from the design sessions; Technical Laws consolidated into 14 numbered Universal Laws; new sections: The Two Halves of the Codebase, Document Map, How HISTORY.md Works, Editing This Document; Session Law now points to HISTORY.md.
- PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md drafted at specification grade.

**Issues encountered:**
- **Security:** the repository's git remote URL contained a GitHub personal access token (classic, `repo` scope, no expiration) in plain text; it was present in the zip shared for review. Director revoked the token, installed the GitHub CLI, authenticated with `gh auth login` + `gh auth setup-git`, and reset the remote to the plain URL. History was checked: no `.env` ever committed; zero tokens and zero database-password occurrences in the full history. Repository made public; a `main` ruleset (require PR, block force push, restrict deletions) is now enforced. Local `infra/.env` Postgres password was visible in a screenshot during the session; it is a local-only Docker credential and will be regenerated in Demo 1 along with the JWT secret.
- Repo contains stray AnimationDirector documents in `files(2)`, `files(3)`, `files(4)` — to be deleted (TODO P0-14).
- `docs/design/CATEGORIES.md` is an unfilled template; `DEFINITIONS.md` is three lines; `GENERALNOTES.md` holds ideas now in the parking lot (California AI model, embedding sub-grouping).
- Legacy code has voting partly built (`Vote`, `SolutionVote`) — more than TODO.md's snapshot recorded.

**Decisions made (recorded in the documents):**
- Proposal system out of Demo 1; umbrellas seeded from a director-written file.
- Amendments only on dominant solutions; an amendment is a full replacement text plus rationale.
- Failed or passed ballot items need a new version before they can qualify again.
- Ballot votes are never exposed per voter, to anyone; workshop votes are per-user in storage, totals only in display.
- One home city and county per user; act only in the three home communities; read anywhere.
- Author may edit a solution only while it has no votes and no amendments.
- `threshold(pct, min, denominator) = max(1, min(ceil(pct% × denominator), min))` — one rule shape for dominant, absorbed, qualified. Director expects it to iterate.
- Home city/county kept on deleted accounts so past votes still count in the right community.
- Removing a workshop vote is a hard delete (the sole Iteration exception); ballot votes never deleted.
- Two Alembic branch labels (`foundation`, `iteration`); `ai_actions` and `settings` are Foundation tables stamped with `BUILD_LABEL`.
- Email backend `console` in Demo 1; background work is asyncio tasks, no Celery.
- Database layer goes async (asyncpg) in the first rebuild; Iteration migration chain regenerated fresh per demo.

---

## 2026-09-11 — Session 1 (Claude.ai planning session — tracker, history, audit)

**Completed:**
- TODO.md restructured: status snapshot by layer and half; Phase 0 migration checklist; Phase 1 Foundation tasks F-01…F-23; Phase 2 Iteration Demo 1 tasks I-01…I-31; Phase 3 Demo 2 candidates; Director Decisions Pending table; Technical Debt with what makes each bite.
- HISTORY.md converted: new header, legacy entries preserved verbatim under "Legacy Log", new-format entries from 2026-09-05.
- AUDIT.md written: the audit-run procedure for both halves.

**Document changes flagged:**
- SANDBOX.md, the Demo 1 build brief, and the new Claude.ai project instructions remain (TODO P0-09…P0-11).
- Director actions before Demo 1 can run: seed files (P0-12), search provider and key (P0-13), repo housekeeping PR (P0-14), sandbox verified (P0-15).

---

## 2026-09-11 — Session 2 (Claude.ai planning session — sandbox, brief, instructions, seeds)

**Completed:**
- SANDBOX.md written from Docker Sandboxes documentation dated 2026-09-10: `sbx` on Ubuntu 24.04+ with KVM, no Docker Desktop; clone mode (`--clone`) so the host checkout is never written and the host sees sandbox commits as a `sandbox-<name>` remote; `sbx policy allow/deny network` allowlist; seven boundary checks. Six setup facts the docs do not settle are marked "confirm on first setup" and listed in §9.
- `briefs/demo-01.md` written — the prompt for the first long run, both halves, Step 0 stop conditions, evidence-based definition of done.
- PROJECT_INSTRUCTIONS.md written for the Claude.ai project: document writer, brief writer, run reviewer; decisions asked in the director's terms.
- Seed files drafted in `seeds/`: `seed_geography.yaml` (California + 58 counties with FIPS 06001–06115), `seed_settings.yaml` (every DEMOCRACY §7.4 key at its Demo 1 default), `seed_officials.yaml` (test communities, `${OFFICIALS_TEST_EMAIL}` placeholder), `seed_umbrellas.yaml` (ten placeholder umbrellas across San Jose / Santa Clara County / California), `env.example`.

**Decisions made:**
- Cities are seeded from a separate `seed_cities.csv` the director exports from the California Department of Finance E-1 list, rather than hand-written into YAML. DATABASE.md §5 and §3.6 updated. Reason: 482 incorporated cities from memory would be unreliable; the DOF list is authoritative and free.
- Test communities are (city, San Jose), (county, Santa Clara), (state, California) — the director's location. Changeable by editing the seed.
- Officials seed uses a `${OFFICIALS_TEST_EMAIL}` placeholder the seed runner substitutes from `.env`, so no address is committed.

**Document changes flagged:**
- The seed runner must support the `${VAR}` substitution and the CSV input; ARCHITECTURE.md does not yet say so explicitly — add to §7 or DATABASE §5 in the next planning pass, or let the build record it.

---

## 2026-09-12 — Session 1 (Director + Claude.ai — sandbox setup and verification)

**Completed:**
- Docker Engine 29.8.0 and `sbx` installed on the workstation; `sbx login` done; KVM confirmed.
- Ollama bound to all interfaces (`OLLAMA_HOST=0.0.0.0`); models present: `llama3.2`, `llama3.1:8b`, `nomic-embed-text`, `qwen2.5vl:7b`, `qwen2.5vl:32b`.
- Network policy initialized `deny-all`; twelve allow rules added (Anthropic, GitHub ×4, PyPI ×2, npm, Docker Hub ×3, host Ollama at `192.168.1.165:11434`).
- GitHub fine-grained token `ddc-sandbox` (repo-scoped, Contents + Pull requests, 30 days, expires 2026-10-12) stored as `sbx secret set github`.
- All seven boundary checks passed (SANDBOX.md §7). Push to `main` from the sandbox rejected by ruleset GH013; push to `demo/boundary-test` accepted and the branch deleted.
- PR #1 merged: the eight documents, `briefs/demo-01.md`, seed files, `.env.example`, `archive/`, stray folders removed.
- `seed_cities.csv` generated from the CA Department of Finance E-1 2026 list: 483 incorporated cities, 58 counties; "El Paso de Robles (Paso Robles)" → Paso Robles, "San Buenaventura (Ventura)" → Ventura; San Francisco added as a city under its county; Alpine, Mariposa, Trinity have none (correct).

**Decisions made:**
- `sbx --version` is not a flag; the bare `sbx` prints help. SANDBOX.md corrected.
- The GitHub token is a proxy-attached service secret and never enters the sandbox; SANDBOX.md updated to say so.

**Issues encountered:**
- First allowlist attempt failed with 412 because no base policy existed; `sbx policy init deny-all` resolved it. Recorded in SANDBOX.md §5.
- Gap found while building the city seed: residents of unincorporated areas have no city to choose and signup requires one. Added as Director Decision Pending #9.

**Document changes flagged:**
- Follow-up PR: full `seed_cities.csv`, remove `PROJECT_INSTRUCTIONS.md` from the repo, updated SANDBOX.md / TODO.md / HISTORY.md.
- Remaining before Demo 1: search provider (optional), Anthropic `/login` inside the first sandbox, project instructions installed in Claude.ai.

**Addendum (same session, later):** Claude Code warm-up inside the sandbox succeeded: `whoami` → `agent`, `example.com` blocked, subscription login persisted to a second sandbox with no prompt. `sbx --help` confirmed `ls`, `rm`, `stop`, `prune`, `ports`, `version`. With `--clone` the host folder mounts read-only at `/run/sandbox/source` and the working clone mounts at the host path; default VM size 64 CPU / 32 GiB. SANDBOX.md updated. Warm-up sandboxes removed. Phase 0 complete except the optional search provider.

---

## 2026-09-13 — Session 1 (Claude.ai planning session — document consistency audit)

**Completed:**
- Second-opinion audit of all nine documents against each other. Thirteen findings put to the director; all decided the same session and applied. Changed: CLAUDE.md (§6, Document Map — director-approved), PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md, AUDIT.md, TODO.md. SANDBOX.md unchanged.

**Decisions made:**
1. Seed files move from `seeds/` to `backend/config/` (the documented paths) in the follow-up PR; the documents were not changed to match the repo.
2. Solutions on multi-community posts: solution texts are stored on the post (`post_solutions`, DATABASE §4.4) and one workshop solution is created per text per umbrella when each post-community receives its umbrella; each copy has its own votes and amendments. A label correction moves the copies only while unvoted and unamended. Posts are immutable and undeletable in Demo 1 (DEMOCRACY §4.1, DATABASE §4.7).
3. One rule for returning to the ballot: passed, failed, and held-back solutions all need a new version (`current_version > last_ballot_version`) — DEMOCRACY §7.2 condition 4. The "different reason category" hold-back mechanic is removed; §8.4 rewritten.
4. `references` renamed `umbrella_references` (PostgreSQL reserved word). Reserved words banned as identifiers (DATABASE §1).
5. CLAUDE §6 amended, director-approved: home city and county are retained on deletion; name, email, password, DOB, gender, party erased. Resolves the constitutional conflict with the 2026-09-07 decision; TODO Decision #6 closed. DATABASE §3.1 column notes corrected ("kept", not "nulled"); `last_active_at` nulled on deletion.
6. A ballot vote is visible to exactly one person, its voter (ballot page, own export). DATABASE §4.16, AUDIT §4.1, DEMOCRACY §13 reworded so the ballot endpoint is not a CRITICAL finding.
7. Data export respects the boundary rule via a contributor registry: Foundation `export.py` calls Iteration's registered `export_iteration.py::contribute` (ARCHITECTURE §2, DATABASE §3.11; TODO I-32).
8. Jury majority is over seated (accepted) jurors; a `no_response` juror is not seated and not replaced; `juries.seated_count` set when the ballot opens; review closes on ballot open (DEMOCRACY §8.2–8.3).
9. Zero-item cycle: `prepared → published` is the only transition, no jury drawn (DEMOCRACY §10.1–10.2, DATABASE §4.14).
10. Minimum signup age 17 — setting `min_signup_age`, checked once at signup, 422 `too_young`, nothing stored (DEMOCRACY §2.3, §7.4; ARCHITECTURE §4).
11. Ballot order: umbrella name A–Z, net score at snapshot descending, solution id ascending — `ballot_items.position`.
12. Transparency pages (`/settings`, `/ai/actions`, `/admin/log`, `/admin` settings change) are Foundation (new F-24); only the cycle controls on `/admin` are Iteration (I-27).
13. Active users exclude unverified-email and deleted accounts (DEMOCRACY §2.4), so every drawn juror can serve.
- Housekeeping without a decision: CLAUDE Document Map lists nine documents; PROJECT.md clone mode replaces worktree; one root `.env` replaces `infra/.env` + `backend/.env`; refresh token is cookie-only; `/legal/cookies` route; `reference_reject_min` (2) split from `similarity_confirm_min`; shared enums `community_level_enum` and `verification_level_enum` declared as the two exceptions to the naming convention; `amendment_similarity_votes` added to the §2 list; `${VAR}` substitution and CSV header documented for the seed runner; TODO snapshot brought to 2026-09-13.

**Notes:**
- The demo brief (`briefs/demo-01.md`, written 2026-09-11) predates these changes and must be re-checked before the run — in particular the seed-file paths, `post_solutions`, the export contributor, and F-24/I-32.
- Reminder for the brief: `ballot_min_dominant_days = 3` means nothing qualifies in a same-day walkthrough; the director lowers it with a logged settings change during the demo.

**Document changes flagged:**
- Director must move the seed files (P0-12) before Demo 1 can pass Step 0.
- New technical-debt entry: solutions duplicated per community may surprise users; observe during demo use.

**Addendum (same session, later):** `briefs/demo-01.md` re-checked and updated for the day's changes (five seed files, one root `.env`, F-24/I-32, the manual cycle now covering the age refusal, two-community post, logged threshold change, seated jury, held-back return rule, zero-item cycle, and export-then-delete). `briefs/audit.md` was found never to have been written despite SANDBOX.md §6.5 referring to it; written now from AUDIT.md (P0-16). Director moved the seed files to `backend/config/`; P0-12 closed. Phase 0 is complete except the optional search provider; Demo 1 can run.

---

## 2026-09-14 — Session 1 (Claude Code build — demo-01, Foundation + Iteration)

Unattended run on `demo/01` inside a Docker Sandbox, from the build brief
`briefs/demo-01.md`. Both halves built front to back. The full cycle runs: three
residents sign up, one writes down a problem, the platform files it, the others
support and amend it, a juror holds one item back with a written reason, the
community votes, and a results document is published with a fingerprint anyone
can recompute. Nothing was merged to `main`.

The raw output of every check below is committed unabridged at
`briefs/evidence/demo-01/`.

---

**Notes:** Step 0 — pre-checks

```
$ git branch --show-current
demo/01

$ ls backend/config/
__init__.py  categories.py  seed_cities.csv  seed_geography.yaml
seed_officials.yaml  seed_settings.yaml  seed_umbrellas.yaml
```

All five director-placed seed files are present, so the run proceeded.

```
$ cat .env.example
(the file committed in PR #1; SEARCH_PROVIDER, SEARCH_API_KEY and
SEARCH_BASE_URL are all empty, and no .env existed)
```

`SEARCH_API_KEY` is unset, so the reference-recommendation trigger answers 503
`search_not_configured` (ARCHITECTURE §8.2). No provider was stubbed.

```
$ docker compose version
Docker Compose version v5.5.0
```

Ollama took three attempts to find:

```
$ curl -sS http://host.docker.internal:11434/api/tags
Blocked by network policy: domain localhost:11434
  detail: no matching allow rule — blocked by default deny policy

$ curl -sS http://192.168.1.165:11434/api/tags
{"models":[{"name":"nomic-embed-text:latest",…},{"name":"qwen2.5vl:32b",…},
{"name":"qwen2.5vl:7b",…},{"name":"llama3.1:8b",…},{"name":"llama3.2:latest",…}]}
```

The host address in SANDBOX.md (`192.168.1.165:11434`) is the one on the
allowlist; the Docker-style aliases are not. `llama3.2` and `nomic-embed-text`
are both present, so **the labeler and the similarity check in this build ran
against the real model on the host GPU**, not a mock. `.env` was written with
that address.

---

**Notes:** two things the sandbox could not do

Both are recorded as technical debt in TODO.md. Neither was worked around
dishonestly.

**Containers.** `docker compose up` fails. The Docker Hub registry and auth
hosts are on the allowlist but the blob CDN is not:

```
$ docker compose --env-file .env -f infra/docker-compose.yml up -d
 Image postgres:16 Pulling
 Image redis:7 Pulling
unknown: failed to copy: httpReadSeeker: failed open: unexpected status from GET
request to https://production.cloudfront.docker.com/registry-v2/…: 403 Forbidden

$ curl -sS https://production.cloudfront.docker.com/
Blocked by network policy: domain production.cloudfront.docker.com:443
  detail: no matching allow rule — blocked by default deny policy
```

`infra/docker-compose.yml` was still rewritten to what the documents ask for —
postgres:16, the single root `.env` through `--env-file`, healthchecks — but it
**has never been started**. To have a database to build against, PostgreSQL
16.14 (with `citext`) was run directly from binaries fetched through the npm
registry, and a Redis-protocol server was run in process from `fakeredis`. The
application code never knew the difference: it speaks asyncpg and RESP over TCP
either way. The director's workstation, where the pulls work, is where the
compose file gets its first real run.

**A browser.** The Chrome-for-Testing download host is blocked too, so there are
no screenshots and no automated accessibility audit. What `pages.txt` records
instead is what the server actually returned for each route, what the API
endpoint behind it answered, and a description of what the page puts on screen.

---

**Completed:**

Everything was replaced, not patched. The legacy `backend/` (sync sessions in
async handlers, routers touching the ORM, the inline prompt string, the
`sys.path` hack, `create_all` at startup) is gone, as ARCHITECTURE §12 asks.

**Foundation (F-01 … F-24).** Layered async backend on asyncpg with typed
errors and one handler, structured logging with a request id on every line,
Redis-backed write rate limiting that falls open with a warning. Signup with the
`min_signup_age` gate and a console verification email, login with a `jti`
access token, refresh-token rotation with reuse detection, a logout blacklist,
password reset. Display settings, data export through the contributor registry,
account deletion running the anonymization procedure exactly as DATABASE §3.1
states it. Geography, officials, settings with a 60-second cache, the admin and
AI action logs with their public pages. A seed runner with two-way coverage
reporting. `verify_schema.py`. Placeholder legal text marked DRAFT and recorded
as a terms version at signup.

**Iteration (I-01 … I-32).** Posts with their solution texts and communities in
one transaction; the labeler on the host GPU; one workshop solution per solution
text per umbrella; confirm and correct, both recorded on the AI action. Votes,
dominance, amendments with absorption and supersession and a word-level diff,
similarity from embeddings that only ever asks a question, threaded comments,
references. The umbrella page assembling every section of DEMOCRACY §3.3. The
cycle: prepare, draw and log a jury, open, close, publish. The summary document
as canonical JSON, hashed once, with a verifier, a hash list, a PDF and a
`mailto:` the user sends themselves. `reconcile.py`.

**Frontend.** Every route in ARCHITECTURE §9.

---

**Completed:** the evidence, pasted

#### Both migration chains, from an empty database

```
=== alembic upgrade foundation@head ===
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 25035d5b7ff5, Foundation initial schema — DATABASE.md §3.

=== alembic upgrade iteration@head ===
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> b4b4da0b6e54, Iteration schema — Demo 1 (DATABASE.md §4).

=== alembic heads ===
25035d5b7ff5 (foundation) (head)
b4b4da0b6e54 (iteration) (head)
```

#### `backend/scripts/verify_schema.py`

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

#### Seeding, and the re-run that reports zero pending writes

```
=== python -m backend.seed --apply ===
=== backend.seed — APPLY ===
[settings (DEMOCRACY.md §7.4)]
  to write:            22
  already present:     0
  in database only:    0
    + active_user_window_days = 30
    + dominant_pct = 5
    + dominant_min = 3
    + amendment_pct = 25
    + amendment_min = 3
    + ballot_pct = 10
    + ballot_min = 5
    + ballot_min_dominant_days = 3
    + similarity_threshold = 0.85
    + similarity_confirm_min = 2
    + ... and 12 more
[geography: state]
  to write:            1
  already present:     0
  in database only:    0
    + California (CA)
[geography: counties]
  to write:            58
  already present:     0
  in database only:    0
    + Alameda (06001)
    + Alpine (06003)
    + Amador (06005)
    + Butte (06007)
    + Calaveras (06009)
    + Colusa (06011)
    + Contra Costa (06013)
    + Del Norte (06015)
    + El Dorado (06017)
    + Fresno (06019)
    + ... and 48 more
[geography: cities]
  to write:            483
  already present:     0
  in database only:    0
    + Alameda, Alameda
    + Albany, Alameda
    + Berkeley, Alameda
    + Dublin, Alameda
    + Emeryville, Alameda
    + Fremont, Alameda
    + Hayward, Alameda
    + Livermore, Alameda
    + Newark, Alameda
    + Oakland, Alameda
    + ... and 473 more
[legal: terms version]
  to write:            1
  already present:     0
  in database only:    0
    + 2026-09-draft-1
[officials directory]
  to write:            5
  already present:     0
  in database only:    0
    + Mayor — San Jose, Santa Clara County
    + City Council (all districts) — San Jose, Santa Clara County
    + Board of Supervisors — Santa Clara County
    + State Assembly Member — California
    + State Senator — California
[main categories (config mirror)]
  to write:            10
  already present:     0
  in database only:    0
    + Roads and Infrastructure
    + Housing and Homelessness
    + Public Safety
    + Environmental Issues
    + Education
    + Public Transit
    + Water and Utilities
    + Parks and Recreation
    + Economic Development
    + Government Accountability
[umbrellas (Iteration)]
  to write:            10
  already present:     0
  in database only:    0
    + Road Damage and Pothole Repair — San Jose, Santa Clara County
    + Pedestrian Safety Near Schools — San Jose, Santa Clara County
    + Encampments Along Creeks and Trails — San Jose, Santa Clara County
    + Park Maintenance and Restroom Access — San Jose, Santa Clara County
    + Bus and Light Rail Frequency — Santa Clara County
    + Affordable Housing Supply — Santa Clara County
    + Wildfire Smoke and Air Quality Response — Santa Clara County
    + Electricity Costs and Reliability — California
    + Public Access to Government Records — California
    + Teacher Retention and Classroom Funding — California
---
pending writes: 590

=== python -m backend.seed --dry-run  (re-run after seeding) ===
=== backend.seed — DRY RUN ===
[settings (DEMOCRACY.md §7.4)]
  to write:            0
  already present:     22
  in database only:    0
[geography: state]
  to write:            0
  already present:     1
  in database only:    0
[geography: counties]
  to write:            0
  already present:     58
  in database only:    0
[geography: cities]
  to write:            0
  already present:     483
  in database only:    0
[legal: terms version]
  to write:            0
  already present:     1
  in database only:    0
[officials directory]
  to write:            0
  already present:     5
  in database only:    0
[main categories (config mirror)]
  to write:            0
  already present:     10
  in database only:    0
[umbrellas (Iteration)]
  to write:            0
  already present:     10
  in database only:    0
---
pending writes: 0
Nothing to do: every seed row is already in the database.
```

#### The test suite

```
$ python -m pytest backend/tests/
…
backend/tests/test_workshop.py::test_votes_drive_dominance_and_downvotes_never_hide PASSED [ 94%]
backend/tests/test_workshop.py::test_one_vote_per_person_per_item PASSED [ 94%]
backend/tests/test_workshop.py::test_amendments_need_a_dominant_solution_and_a_different_author PASSED [ 95%]
backend/tests/test_workshop.py::test_an_amendment_is_absorbed_and_supersedes_the_others PASSED [ 95%]
backend/tests/test_workshop.py::test_an_amendment_can_be_withdrawn_only_before_it_has_support PASSED [ 96%]
backend/tests/test_workshop.py::test_similar_amendments_are_flagged_and_people_decide PASSED [ 96%]
backend/tests/test_workshop.py::test_comments_nest_to_the_depth_cap PASSED [ 97%]
backend/tests/test_workshop.py::test_a_comment_can_be_edited_briefly_and_removed_softly PASSED [ 97%]
backend/tests/test_workshop.py::test_a_solution_is_editable_only_while_untouched PASSED [ 98%]
backend/tests/test_workshop.py::test_the_feed_states_its_ordering_rule PASSED [ 98%]
backend/tests/test_workshop.py::test_posts_cannot_be_edited_or_deleted PASSED [ 99%]
backend/tests/test_workshop.py::test_the_post_content_hash_never_changes PASSED [100%]

================= 199 passed, 2 deselected in 95.59s (0:01:35) =================
```

The two live checks are opt-in (`pytest -m live`) and hit the real Ollama, to
confirm the prompt files still return the shape the parser expects:

```
collecting ... collected 201 items / 199 deselected / 2 selected

backend/tests/test_live_ollama.py::test_the_labeler_prompt_still_produces_the_shape_the_code_parses PASSED [ 50%]
backend/tests/test_live_ollama.py::test_embeddings_come_back_the_same_length_and_compare_sensibly PASSED [100%]

====================== 2 passed, 199 deselected in 3.45s =======================
```

#### `backend/scripts/reconcile.py --dry-run`, against the data the walkthrough produced

```
{
  "started_at": "2026-09-14 02:05:59.435030+00:00",
  "corrected": false,
  "net_score_drift": [],
  "dominance_changes": [],
  "orphan_communities": [],
  "hash_mismatches": [],
  "counts_before": {
    "admin_actions": 7,
    "ai_actions": 1,
    "amendment_similarity": 0,
    "amendment_similarity_votes": 0,
    "amendments": 1,
    "ballot_items": 2,
    "ballot_votes": 3,
    "cities": 483,
    "comments": 3,
    "counties": 58,
    "cycles": 2,
    "data_exports": 1,
    "email_verifications": 3,
    "juries": 1,
    "jurors": 1,
    "jury_holdbacks": 1,
    "labels": 1,
    "main_categories": 10,
    "officials": 5,
    "password_resets": 0,
    "post_communities": 1,
    "post_solutions": 2,
    "posts": 1,
    "reference_feedback": 0,
    "refresh_tokens": 5,
    "settings": 23,
    "solution_versions": 4,
    "solutions": 3,
    "states": 1,
    "summaries": 1,
    "terms_acceptances": 3,
    "terms_versions": 1,
    "umbrella_references": 1,
    "umbrellas": 10,
    "user_display_settings": 3,
    "users": 3,
    "votes": 5
  },
  "counts_after": {
    "admin_actions": 7,
    "ai_actions": 1,
    "amendment_similarity": 0,
    "amendment_similarity_votes": 0,
    "amendments": 1,
    "ballot_items": 2,
    "ballot_votes": 3,
    "cities": 483,
    "comments": 3,
    "counties": 58,
    "cycles": 2,
    "data_exports": 1,
    "email_verifications": 3,
    "juries": 1,
    "jurors": 1,
    "jury_holdbacks": 1,
    "labels": 1,
    "main_categories": 10,
    "officials": 5,
    "password_resets": 0,
    "post_communities": 1,
    "post_solutions": 2,
    "posts": 1,
    "reference_feedback": 0,
    "refresh_tokens": 5,
    "settings": 23,
    "solution_versions": 4,
    "solutions": 3,
    "states": 1,
    "summaries": 1,
    "terms_acceptances": 3,
    "terms_versions": 1,
    "umbrella_references": 1,
    "umbrellas": 10,
    "user_display_settings": 3,
    "users": 3,
    "votes": 5
  },
  "finished_at": "2026-09-14 02:05:59.545158+00:00"
}
```

#### The greps the brief asks for

```
$ grep -rn "TODO\|FIXME" backend/ frontend/src/
(nothing)

$ grep -rn "os.environ" backend/ | grep -v settings_env.py
(nothing)
```

#### Every page in ARCHITECTURE §9, with the backend running

```
==============================================================
 Every page in ARCHITECTURE.md §9, served by `next start`
 with the API running. Client pages fetch their data from the
 endpoint named on each line.
==============================================================

/                                              HTTP 200
   title : Direct Democracy Cali
   h1    : The tools that only well-funded political organisations have had
   lead  : Write down a problem in your community. Propose what should be done about it. Work on it with your neighbours,…
   shows : what the platform is, in four steps, and what it cannot promise

/signup                                        HTTP 200
   title : Direct Democracy Cali
   h1    : Join your community
   lead  : One account per person, under your real name. What other people see is up to you — you can show your real na…
   shows : the signup form: county and city pickers, gender and party with their 'totals only' note, the terms box
   data  : /geo/counties -> HTTP 200

/login                                         HTTP 200
   title : Direct Democracy Cali
   h1    : Sign in
   shows : email and password, links to reset and to signup

/verify-email                                  HTTP 200
   title : Direct Democracy Cali
   h1    : Confirming your email address
   shows : confirms the token in the link and says what happened

/forgot-password                               HTTP 200
   title : Direct Democracy Cali
   h1    : Reset your password
   shows : one field, and the note that the answer is the same either way

/reset-password                                HTTP 200
   title : Direct Democracy Cali
   h1    : Choose a new password
   shows : one field for the new password, with the rule stated

/me                                            HTTP 200
   title : Direct Democracy Cali
   shows : communities, verification level, display-name setting, data export, account deletion

/legal/privacy                                 HTTP 200
   title : Direct Democracy Cali
   shows : the privacy policy, marked DRAFT with the warning at the top
   data  : /legal/privacy -> HTTP 200

/legal/terms                                   HTTP 200
   title : Direct Democracy Cali
   shows : the terms of service, marked DRAFT
   data  : /legal/terms -> HTTP 200

/legal/cookies                                 HTTP 200
   title : Direct Democracy Cali
   shows : the one cookie this platform sets
   data  : /legal/cookies -> HTTP 200

/settings                                      HTTP 200
   title : Direct Democracy Cali
   shows : every rule, its value, what it means, and when it last changed
   data  : /settings -> HTTP 200

/ai/actions                                    HTTP 200
   title : Direct Democracy Cali
   shows : every AI action with model, prompt file, fingerprints and what a person did about it
   data  : /ai/actions -> HTTP 200

/admin/log                                     HTTP 200
   title : Direct Democracy Cali
   shows : every administrator action, with what changed and why
   data  : /admin/log -> HTTP 200

/admin                                         HTTP 200
   title : Direct Democracy Cali
   shows : change a rule; prepare, open, close and publish a cycle; ask AI for references; refile a post

/feed                                          HTTP 200
   title : Direct Democracy Cali
   h1    : What people are working on
   lead  : Every problem someone has written down, with what they think should be done about it.…
   shows : posts newest first with the ranking rule printed on the page
   data  : /feed -> HTTP 200

/posts/new                                     HTTP 200
   title : Direct Democracy Cali
   shows : problem, solutions, communities, and how it gets filed

/posts/1                                       HTTP 200
   title : Direct Democracy Cali
   shows : one problem, its solution texts with fingerprints, and where it was filed
   data  : /posts/1 -> HTTP 200

/umbrellas/2                                   HTTP 200
   title : Direct Democracy Cali
   shows : the workshop: problem, reports, discussion, solutions, dominant solutions with amendments, references
   data  : /umbrellas/2 -> HTTP 200

/solutions/1                                   HTTP 200
   title : Direct Democracy Cali
   shows : one solution, every version with its fingerprint, its amendments, its discussion
   data  : /solutions/1 -> HTTP 200

/ballot                                        HTTP 200
   title : Direct Democracy Cali
   shows : the current ballot for each home community, with the privacy note

/cycles/1                                      HTTP 200
   title : Direct Democracy Cali
   shows : one cycle: state, jury, timings, and the settings recorded on it
   data  : /cycles/1 -> HTTP 200

/jury                                          HTTP 200
   title : Direct Democracy Cali
   shows : jury duty: accept or decline, and hold an item back with a written reason

/results                                       HTTP 200
   title : Direct Democracy Cali
   shows : the three home communities' most recent published documents

/summaries/city/408/1                          HTTP 200
   title : Direct Democracy Cali
   shows : the published results document, its fingerprint, and the send button
   data  : /summaries/city/408/1 -> HTTP 200

/summaries/hashes                              HTTP 200
   title : Direct Democracy Cali
   shows : every published document's fingerprint
   data  : /summaries/hashes -> HTTP 200
```

Each page's browser-tab title, set from the page itself:

```
/                                              Direct Democracy Cali · Direct Democracy Cali
/admin                                         Administrator controls · Direct Democracy Cali
/admin/log                                     Everything an administrator has done · Direct Democracy Cali
/ai/actions                                    Everything AI has done here · Direct Democracy Cali
/ballot                                        The ballot · Direct Democracy Cali
/cycles/[id]                                   A ballot cycle · Direct Democracy Cali
/feed                                          What people are working on · Direct Democracy Cali
/forgot-password                               Reset your password · Direct Democracy Cali
/jury                                          Jury duty · Direct Democracy Cali
/legal/cookies                                 Cookies · Direct Democracy Cali
/legal/privacy                                 Privacy policy · Direct Democracy Cali
/legal/terms                                   Terms of service · Direct Democracy Cali
/login                                         Sign in · Direct Democracy Cali
/me                                            Your account · Direct Democracy Cali
/posts/[id]                                    A problem report · Direct Democracy Cali
/posts/new                                     Write down a problem · Direct Democracy Cali
/reset-password                                Choose a new password · Direct Democracy Cali
/results                                       Results · Direct Democracy Cali
/settings                                      Every rule and its value · Direct Democracy Cali
/signup                                        Join your community · Direct Democracy Cali
/solutions/[id]                                A solution · Direct Democracy Cali
/summaries/[level]/[entityId]/[number]         Ballot results · Direct Democracy Cali
/summaries/hashes                              Every published fingerprint · Direct Democracy Cali
/umbrellas/[id]                                The workshop · Direct Democracy Cali
/verify-email                                  Confirming your email address · Direct Democracy Cali
```

#### Images off, and the accessibility checks (I-28)

```

1. Images off — the platform ships no <img>, no background-image, and no icon font.
   none found: every page is text, CSS colour and gradient only

2. Every form control has a label bound to it by id.
   every control is labelled

3. Interactive elements are native and therefore keyboard reachable.
src/app/umbrellas/[id]/page.tsx:338:                                    onClick={async () => {
src/app/umbrellas/[id]/page.tsx:394:                            onClick={async () => {
src/app/ballot/page.tsx:141:                            onClick={() => void vote(ballot.cycle_id, item.ballot_item_id, choice)}
src/app/admin/page.tsx:161:                        onClick={() => void run(`/admin/cycles/${live.id}/${step.action}`)}
src/app/admin/page.tsx:170:                        onClick={() => {
   every onClick above sits on a <button>; there are no clickable <div>s

4. Landmarks, skip link, and live regions.
   landmark and ARIA attributes in the source: 14
   skip link present in the served HTML: class=skip-link
   main landmark present: <main id=main>
   navigation landmark present: <nav aria-label=Main

5. Focus is never removed, and tap targets are at least 44px.
56::focus-visible {
113:  min-height: 44px; /* a comfortable target on a phone */
135:  min-height: 44px;

6. Nothing depends on colour alone: every badge and status also carries words.
   badges, all of which render text: 3

7. Reduced motion is respected.
165:@media (prefers-reduced-motion: reduce) {

8. Every page declares its language and its own name.
    <html lang=en>
   pages that set their own browser-tab title: 24
```

#### The manual full cycle through the API

Every request and every response, in order. Responses longer than 420 characters
are cut here with the remaining length marked; the untruncated transcript is
committed at `briefs/evidence/demo-01/walkthrough.txt`.

```


################################################################
# STEP 1 — signup. An under-age applicant is refused and nothing is stored (DEMOCRACY §2.3)
################################################################

$ curl -X POST http://127.0.0.1:8000/auth/signup   (date of birth 2014 — age 12)
{"error":"too_young","message":"You need to be at least 17 to join. Nothing you entered has been saved."}
HTTP 422

$ curl -X POST http://127.0.0.1:8000/auth/signup   (weak password)
{"error":"weak_password","message":"Your password needs to contain a capital letter, and contain a number."}
HTTP 422

$ curl -X POST http://127.0.0.1:8000/auth/signup   (Maria Delgado, democratic)
{"id":1,"message":"Account created. Check your email and use the confirmation link before posting, voting or commenting."}
HTTP 201

$ curl -X POST http://127.0.0.1:8000/auth/signup   (Andre Whitfield, republican)
{"id":2,"message":"Account created. Check your email and use the confirmation link before posting, voting or commenting."}
HTTP 201

$ curl -X POST http://127.0.0.1:8000/auth/signup   (Priya Raman, no_party_preference)
{"id":3,"message":"Account created. Check your email and use the confirmation link before posting, voting or commenting."}
HTTP 201


################################################################
# STEP 2 — the confirmation links, read from the console email log (EMAIL_BACKEND=console)
################################################################
maria@example.com: http://localhost:3000/verify-email?token=P6DV1VInBjVGs-t-y0ZTCwDJIEIQyrptPcHX6SJYpGk
andre@example.com: http://localhost:3000/verify-email?token=CfKBMKHZ4JVfO8uI9Opxf1GZ8SYClA7TT4IDPrZzPvw
priya@example.com: http://localhost:3000/verify-email?token=iDO1QQIcaoh8AyPIBhZUa7fmB7XLlE339CGX6RL6PEQ

--- a write attempted before the email is confirmed ---

$ curl -X POST http://127.0.0.1:8000/posts   (Priya, email not yet confirmed)
{"error":"email_not_verified","message":"Confirm your email address before posting, voting or commenting. Check your inbox for the link we sent when you signed up."}
HTTP 403

$ curl -X POST http://127.0.0.1:8000/auth/verify-email -d '{"token":"<from the log>"}'   (maria)
{"message":"Email confirmed. You can now post, vote and comment."}
HTTP 200

$ curl -X POST http://127.0.0.1:8000/auth/verify-email -d '{"token":"<from the log>"}'   (andre)
{"message":"Email confirmed. You can now post, vote and comment."}
HTTP 200

$ curl -X POST http://127.0.0.1:8000/auth/verify-email -d '{"token":"<from the log>"}'   (priya)
{"message":"Email confirmed. You can now post, vote and comment."}
HTTP 200

--- the same link a second time ---

$ curl -X POST http://127.0.0.1:8000/auth/verify-email   (already used)
{"error":"verification_invalid","message":"That confirmation link is no longer valid. Ask for a new one from the sign-in page."}
HTTP 422


################################################################
# STEP 3 — sign in. Access token in the body, refresh token in an httpOnly SameSite=Strict cookie
################################################################

$ curl -X POST http://127.0.0.1:8000/auth/login   (maria)
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiaWF0IjoxNzg5MzUxNTM5LCJleHAiOjE3ODkzNTMzMzksImp0aSI6IjU1YWNmYTZhOWE3NDQ4YmI5N2Q3MDBiMTgyMmM4OGFiIn0.zRSnh0IXfH9ykkzzfBnipBd_HE90QTIxYD4Tu_mm55g","token_type":"bearer","user_id":1,"email_verified":true}
HTTP 200

$ curl -X POST http://127.0.0.1:8000/auth/login   (andre)
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiaWF0IjoxNzg5MzUxNTQwLCJleHAiOjE3ODkzNTMzNDAsImp0aSI6Ijc3NDQwOGI2NmFiNzQxOWZiYTE4ZTExMzJiYjMxNDcyIn0.O-0cG-lx6YXxp0boF-NIDNeQCX7if9zkQ4Uc9xg1dao","token_type":"bearer","user_id":2,"email_verified":true}
HTTP 200

$ curl -X POST http://127.0.0.1:8000/auth/login   (priya)
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzIiwiaWF0IjoxNzg5MzUxNTQwLCJleHAiOjE3ODkzNTMzNDAsImp0aSI6ImEwM2I1YzlmMzk0MzRlNGI5OTQyMzM5OGI4N2VlZWY5In0.IOCY0YvvPrqda-aM6yLOUAvv_172W8VaCrw0LxjeHpw","token_type":"bearer","user_id":3,"email_verified":true}
HTTP 200

--- the cookie jar for maria (the token itself is not printed) ---
#HttpOnly_127.0.0.1	FALSE	/	FALSE	1790561139	refresh_token	<opaque token, never shown>

$ curl -X GET http://127.0.0.1:8000/auth/me   (Maria)
{"id":1,"email":"maria@example.com","real_name":"Maria Delgado","display_name":"MariaD","public_name_mode":"display_name","verification_level":"unverified","verification_explanation":"Unverified means the platform has confirmed your email address and nothing else. Your residency is self-declared. Your vote counts exactly as much as everyone else's — verification level is reported in totals and never changes the weigh …[+308 chars]
HTTP 200


################################################################
# STEP 4 — the director's account becomes an administrator, from the machine, with no endpoint for it
################################################################
$ python backend/scripts/grant_admin.py maria@example.com --dry-run
WOULD GRANT administrator on maria@example.com (user 1)
$ python backend/scripts/grant_admin.py maria@example.com --apply
GRANT administrator on maria@example.com (user 1)
$ python backend/scripts/grant_admin.py maria@example.com --dry-run   (re-runnable)
Nothing to do: maria@example.com (user 1) is already an administrator.


################################################################
# STEP 5 — a logged settings change: ballot_min_dominant_days 3 -> 0 so a one-day walkthrough can reach a ballot
################################################################

$ curl -X POST http://127.0.0.1:8000/admin/settings   (Maria, administrator)
{"key":"ballot_min_dominant_days","old_value":3,"new_value":0,"message":"Changed. The new value is on the public settings page and the change is in the public admin log."}
HTTP 200

$ curl -X POST http://127.0.0.1:8000/admin/settings   (Andre, not an administrator)
{"error":"not_admin","message":"That is an administrator action."}
HTTP 403

$ curl -X GET http://127.0.0.1:8000/settings/history?key=ballot_min_dominant_days   (public, no login)
[{"key":"ballot_min_dominant_days","value":"0","effective_from":"2026-09-14T02:05:41.310828Z","changed_by":"MariaD","reason":"This walkthrough runs inside a single day, and the three-day dominance requirement would make a ballot unreachable. Restore it to 3 before any real community uses this."},{"key":"ballot_min_dominant_days","value":"3","effective_from":"2026-09-14T02:03:40.563309Z","changed_by":"the platform see …[+30 chars]
HTTP 200


################################################################
# STEP 6 — Maria posts a problem with two proposed solutions and lets the platform file it
################################################################

$ curl -X POST http://127.0.0.1:8000/posts
{"id":1,"label_status":"pending","message":"Posted. It is being filed into an umbrella now — that usually takes a moment. You can confirm or correct where it lands."}
HTTP 201

--- waiting for the labeler (Ollama on the host GPU, llama3.2) ---
label_status after 6s: labeled

$ curl -X GET http://127.0.0.1:8000/posts/1
{"id":1,"title":"The intersection of Bird Avenue and West Virginia Street has no marked…","problem_text":"The intersection of Bird Avenue and West Virginia Street has no marked crosswalk, and children walking to Washington Elementary cross four lanes of traffic there twice a day. Drivers routinely take the turn at speed during drop-off and pick-up hours. Two near misses were reported to the city last spring and nothi …[+1731 chars]
HTTP 200
umbrella the platform chose: 2

$ curl -X GET http://127.0.0.1:8000/ai/actions   (the public AI action log — the row exists before the result was shown)
{"explanation":"Every action any AI takes on this platform is written down here before its result is shown to anyone: what it was, what it acted on, which model and which prompt file, a fingerprint of exactly what it was given, what it answered, and whether a person later confirmed or corrected it. AI never decides anything here.","items":[{"id":1,"action_type":"label","subject_type":"post","subject_id":1,"demo_build …[+638 chars]
HTTP 200


################################################################
# STEP 7 — Maria confirms the filing; the correction is offered and recorded either way
################################################################

$ curl -X POST http://127.0.0.1:8000/posts/1/label/confirm
{"message":"Thank you — 1 filing confirmed. That is recorded in the public AI log."}
HTTP 200

$ curl -X GET http://127.0.0.1:8000/ai/actions   (human_outcome is now recorded)
{"explanation":"Every action any AI takes on this platform is written down here before its result is shown to anyone: what it was, what it acted on, which model and which prompt file, a fingerprint of exactly what it was given, what it answered, and whether a person later confirmed or corrected it. AI never decides anything here.","items":[{"id":1,"action_type":"label","subject_type":"post","subject_id":1,"demo_build …[+662 chars]
HTTP 200


################################################################
# STEP 8 — the umbrella page: the workshop
################################################################
HTTP 200
{
  "problem": {
    "name": "Pedestrian Safety Near Schools",
    "community": {
      "level": "city",
      "entity_id": 408,
      "name": "San Jose",
      "label": "San Jose (city)"
    },
    "main_category": "Public Safety",
    "active_users": 3,
    "dominant_threshold": 1,
    "ballot_threshold": 1
  },
  "ai_action_list": "AI on this umbrella: 1 of 1 problem report was AI-labeled (1 confirmed, 0 corrected, 0 unreviewed); 0 amendment pairs were flagged similar (0 confirmed same, 0 different); 0 of 0 references were AI-recommended (0 still listed, 0 rejected).",
  "problem_reports": [
    {
      "post_id": 1,
      "label_shown_as": "AI-labeled, confirmed by author",
      "author": "MariaD"
    }
  ],
  "solutions": [
    {
      "id": 1,
      "net_score": 0,
      "status_badge": null,
      "text": "Paint a high-visibility continental crosswalk across West Virginia Str..."
    },
    {
      "id": 2,
      "net_score": 0,
      "status_badge": null,
      "text": "Station a crossing guard at the intersection during school drop-off an..."
    }
  ],
  "ordering": {
    "version": "solutions-v0",
    "explanation": "Highest net score first; where two solutions have the same score, the older one is shown first. Nothing is ever hidden \u2014 a solution with a negative score appears at the bottom of the list."
  }
}
solution A = 1 (crosswalk and refuge island); solution B = 2 (crossing guard)


################################################################
# STEP 9 — Andre and Priya upvote both solutions; the first vote makes each dominant
################################################################

$ curl -X PUT http://127.0.0.1:8000/votes   (Andre, +1 on solution 1)
{"target_type":"solution","target_id":1,"net_score":1,"upvotes":1,"downvotes":0,"is_dominant":true,"dominant_since":"2026-09-14T02:05:44.782236Z","dominance_changed":true,"dominant_threshold":1,"active_users":3,"on_track_for_ballot":true,"ballot_threshold":1}
HTTP 200

$ curl -X PUT http://127.0.0.1:8000/votes   (Andre, +1 on solution 2)
{"target_type":"solution","target_id":2,"net_score":1,"upvotes":1,"downvotes":0,"is_dominant":true,"dominant_since":"2026-09-14T02:05:44.843326Z","dominance_changed":true,"dominant_threshold":1,"active_users":3,"on_track_for_ballot":true,"ballot_threshold":1}
HTTP 200

$ curl -X PUT http://127.0.0.1:8000/votes   (Priya, +1 on solution 1)
{"target_type":"solution","target_id":1,"net_score":2,"upvotes":2,"downvotes":0,"is_dominant":true,"dominant_since":"2026-09-14T02:05:44.782236Z","dominance_changed":false,"dominant_threshold":1,"active_users":3,"on_track_for_ballot":true,"ballot_threshold":1}
HTTP 200

$ curl -X PUT http://127.0.0.1:8000/votes   (Priya, +1 on solution 2)
{"target_type":"solution","target_id":2,"net_score":2,"upvotes":2,"downvotes":0,"is_dominant":true,"dominant_since":"2026-09-14T02:05:44.843326Z","dominance_changed":false,"dominant_threshold":1,"active_users":3,"on_track_for_ballot":true,"ballot_threshold":1}
HTTP 200

--- a downvote lowers the ranking and hides nothing (CLAUDE.md §4) ---

$ curl -X PUT http://127.0.0.1:8000/votes   (Maria, -1 on solution 2, then removed)
{"target_type":"solution","target_id":2,"net_score":1,"upvotes":2,"downvotes":1,"is_dominant":true,"dominant_since":"2026-09-14T02:05:44.843326Z","dominance_changed":false,"dominant_threshold":1,"active_users":3,"on_track_for_ballot":true,"ballot_threshold":1}
HTTP 200

$ curl -X DELETE http://127.0.0.1:8000/votes   (Maria takes it back)
{"target_type":"solution","target_id":2,"net_score":2,"upvotes":2,"downvotes":0,"is_dominant":true,"dominant_since":"2026-09-14T02:05:44.843326Z","dominance_changed":false,"dominant_threshold":1,"active_users":3,"on_track_for_ballot":true,"ballot_threshold":1}
HTTP 200


################################################################
# STEP 10 — Andre amends the dominant solution; Priya backs it; it is absorbed as version 2
################################################################

$ curl -X POST http://127.0.0.1:8000/solutions/1/amendments   (Andre)
{"id":1,"message":"Proposed. It becomes the solution's text once enough of the people who support that solution back your change.","absorption_threshold":1}
HTTP 201

--- the author of the current version cannot amend their own text ---

$ curl -X POST http://127.0.0.1:8000/solutions/1/amendments   (Maria wrote version 1)
{"error":"author_of_current_version","message":"You wrote the text that is in place now, so you cannot amend it. Someone else in the community can."}
HTTP 403

--- amendments are only possible on dominant solutions — checked on a fresh, unsupported solution ---

$ curl -X POST http://127.0.0.1:8000/umbrellas/2/solutions   (Priya adds a third solution)
{"id":3,"message":"Posted. It belongs to the community now: anyone here can propose a change to it once it becomes dominant."}
HTTP 201

$ curl -X POST http://127.0.0.1:8000/solutions/3/amendments   (not dominant yet)
{"error":"solution_not_dominant","message":"Amendments can only be proposed on dominant solutions. Upvote this one to help it get there, or propose a better solution of your own."}
HTTP 409

$ curl -X GET http://127.0.0.1:8000/solutions/1/amendments   (threshold and supporters shown)
{"solution_id":1,"current_version":1,"absorption_threshold":1,"supporters":2,"amendments":[{"id":1,"author":"AndreW","proposed_text":"Paint a high-visibility continental crosswalk across West Virginia Street at Bird Avenue, install a pedestrian refuge island in the median, and add a rectangular rapid-flashing beacon on both approaches, using the safe-routes-to-school funds the city already holds. Report the completio …[+802 chars]
HTTP 200

$ curl -X PUT http://127.0.0.1:8000/votes   (Priya backs amendment 1)
{"target_type":"amendment","target_id":1,"net_score":1,"upvotes":1,"downvotes":0,"absorbed":true,"absorption_threshold":1,"solution_supporters":2,"effective_net_score":1,"new_version":2,"status":"absorbed"}
HTTP 200
HTTP 200
{
  "id": 1,
  "current_version": 2,
  "text": "Paint a high-visibility continental crosswalk across West Virginia Street at Bird Avenue, install a pedestrian refuge island in the median, and add a rectangular rapid-flashing beacon on both approaches, using the safe-routes-to-school funds the city already holds. Report the completion date publicly.",
  "net_score": 2,
  "supporters": 2,
  "is_dominant": true,
  "absorption_threshold": 1,
  "on_track_for_ballot": true
}
versions:
[
  {
    "version": 1,
    "text": "Paint a high-visibility continental crosswalk across West Virginia Street at Bird Avenue and install a pedestrian refuge island in the median, using the safe-routes-to-school funds the city already holds.",
    "written_by": "MariaD",
    "from_amendment_id": null,
    "content_hash": "a09da0f23cb1e911cbe233dc9138a5f0740c4b3b8463f8e9e7521c2c0442c91e",
    "created_at": "2026-09-14T02:05:42.252113Z"
  },
  {
    "version": 2,
    "text": "Paint a high-visibility continental crosswalk across West Virginia Street at Bird Avenue, install a pedestrian refuge island in the median, and add a rectangular rapid-flashing beacon on both approaches, using the safe-routes-to-school funds the city already holds. Report the completion date publicly.",
    "written_by": "AndreW",
    "from_amendment_id": 1,
    "content_hash": "0462dbf68fdf68ae7ccc51720475504ca3ca2b82928c86d271b811ac5bb35635",
    "created_at": "2026-09-14T02:05:45.390050Z"
  }
]
amendments:
[
  {
    "id": 1,
    "status": "absorbed",
    "absorbed_as_version": 2,
    "net_score": 1,
    "rationale": "A crosswalk alone does not slow drivers; a flashing beacon does, and a public date stops it slipping."
  }
]


################################################################
# STEP 11 — discussion on a dominant solution and on the umbrella's problem
################################################################

$ curl -X POST http://127.0.0.1:8000/comments   (Priya, on the umbrella problem)
{"id":1,"depth":0,"message":"Posted."}
HTTP 201

$ curl -X POST http://127.0.0.1:8000/comments   (Andre replies)
{"id":2,"depth":1,"message":"Posted."}
HTTP 201

$ curl -X POST http://127.0.0.1:8000/comments   (Maria, on the dominant solution)
{"id":3,"depth":0,"message":"Posted."}
HTTP 201

--- discussion is not open on a solution that is not dominant ---

$ curl -X POST http://127.0.0.1:8000/comments   (on the third solution)
{"error":"solution_not_dominant","message":"Discussion opens once a solution becomes dominant. Until then you can upvote it, or propose a better one."}
HTTP 409

$ curl -X GET http://127.0.0.1:8000/umbrellas/2/comments
{"ordering":{"version":"comments-v0","explanation":"Within each thread, highest net score first; ties oldest first. Nothing is hidden by score."},"comments":[{"id":1,"author":"PriyaR","text":"I walk my daughter across this intersection every morning. The turning traffic from Bird is the worst part.","depth":0,"net_score":0,"my_vote":null,"created_at":"2026-09-14T02:05:45.464666Z","edited":false,"removed":false,"ai_in …[+982 chars]
HTTP 200


################################################################
# STEP 12 — a member adds a reference; the AI recommender is unconfigured and says so
################################################################

$ curl -X POST http://127.0.0.1:8000/umbrellas/2/references   (Andre)
{"id":1,"message":"Added."}
HTTP 201

$ curl -X POST http://127.0.0.1:8000/admin/umbrellas/2/recommend-references   (no search provider configured)
{"error":"search_not_configured","message":"Reference recommendation needs a web search provider, and none is configured on this platform yet."}
HTTP 503

$ curl -X GET http://127.0.0.1:8000/umbrellas/2/references
{"active":[{"id":1,"url":"https://www.sanjoseca.gov/your-government/departments-offices/transportation/safety/vision-zero","title":"San Jose Vision Zero","why":"The city already has a Vision Zero programme with a priority safety corridor list; this intersection should be checked against it.","source":"user","label":"Added by AndreW","status":"active","useful":0,"not_useful":0,"rejections_needed":2,"added_at":"2026-09 …[+146 chars]
HTTP 200


################################################################
# STEP 13 — the feed (DEMOCRACY §12): newest first, no ranking, and it says so
################################################################

$ curl -X GET http://127.0.0.1:8000/feed
{"ranking":"feed-v0","explanation":"Newest first. No ranking. Every reader of the same filters sees the same posts in the same order.","items":[{"id":1,"title":"The intersection of Bird Avenue and West Virginia Street has no marked…","problem_text":"The intersection of Bird Avenue and West Virginia Street has no marked crosswalk, and children walking to Washington Elementary cross four lanes of traffic there twice a  …[+777 chars]
HTTP 200


################################################################
# STEP 14 — the director prepares the ballot: a snapshot, frozen text, and a jury draw
################################################################

$ curl -X POST http://127.0.0.1:8000/admin/cycles/prepare
{"cycle_id":1,"number":1,"state":"jury_review","community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"active_users_at_prepare":3,"items":[{"solution_id":1,"version":2,"umbrella":"Pedestrian Safety Near Schools","net_score":2},{"solution_id":2,"version":1,"umbrella":"Pedestrian Safety Near Schools","net_score":2}],"considered":[{"solution_id":1,"umbrella":"Pedestrian Safety Near Scho …[+801 chars]
HTTP 200

$ curl -X GET http://127.0.0.1:8000/cycles/1
{"id":1,"number":1,"state":"jury_review","community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"active_users_at_prepare":3,"settings_in_force":{"jury_size":3,"ballot_min":5,"ballot_pct":10.0,"dominant_min":3,"dominant_pct":5.0,"amendment_min":3,"amendment_pct":25.0,"min_signup_age":17,"ballot_pass_rule":"simple_majority","jury_review_days":2,"ballot_quorum_min":1,"comment_max_depth" …[+697 chars]
HTTP 200

$ curl -X GET http://127.0.0.1:8000/cycles/1/ballot   (frozen text, in ballot order)
{"cycle_id":1,"cycle_number":1,"state":"jury_review","community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"you_can_vote":false,"ordering":{"version":"ballot-order-v0","explanation":"Ballot items are numbered by umbrella name A-Z, then by net score at the snapshot (highest first), then by solution id (lowest first)."},"privacy_note":"Your ballot votes are shown to you and to nobody  …[+1231 chars]
HTTP 200


################################################################
# STEP 15 — jury duty: the drawn juror accepts and holds one solution back with a written reason
################################################################
HTTP 200
[]
HTTP 200
[]
HTTP 200
[
  {
    "juror_id": 1,
    "seat": 1,
    "status": "drawn",
    "cycle_state": "jury_review",
    "items": 0
  }
]
the drawn juror is Priya, juror id 1

$ curl -X POST http://127.0.0.1:8000/jurors/1/accept
{"juror_id":1,"status":"accepted","message":"Thank you. You can now look at every solution that qualified and hold any of them back with a written reason."}
HTTP 200

$ curl -X GET http://127.0.0.1:8000/juries/mine   (Priya, now seated — she sees the frozen texts)
{"duties":[{"juror_id":1,"seat":1,"status":"accepted","cycle_id":1,"cycle_number":1,"cycle_state":"jury_review","community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"what_you_can_do":"You can look at every solution that qualified and, for any of them, hold it back with a written reason that will be published. You cannot change anything, and you cannot add anything. Doing nothing is …[+1645 chars]
HTTP 200
holding back the crossing-guard solution: ballot item 2

$ curl -X POST http://127.0.0.1:8000/ballot-items/2/holdback   (Priya)
{"ballot_item_id":2,"note":"Recorded. Jurors do not see each other's hold-backs until the ballot opens. Your reason will be published with the results."}
HTTP 200

--- someone who is not a juror cannot hold anything back ---

$ curl -X POST http://127.0.0.1:8000/ballot-items/2/holdback   (Andre, using Priya's seat)
{"error":"not_your_seat","message":"That jury seat is not yours."}
HTTP 403


################################################################
# STEP 16 — the director opens the ballot; the hold-back takes effect over the seated jurors
################################################################

$ curl -X POST http://127.0.0.1:8000/admin/cycles/1/open
{"cycle_id":1,"state":"open","opened_at":"2026-09-14T02:05:46.195916Z","would_close_on":"2026-09-21T02:05:46.195916Z","jurors_drawn":1,"jurors_seated":1,"items_votable":1,"items_held_back":1,"note":"In this build the ballot closes when the director closes it. The window shown is what the setting says it would be."}
HTTP 200

$ curl -X GET http://127.0.0.1:8000/cycles/1/ballot   (Andre)
{"cycle_id":1,"cycle_number":1,"state":"open","community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"you_can_vote":true,"ordering":{"version":"ballot-order-v0","explanation":"Ballot items are numbered by umbrella name A-Z, then by net score at the snapshot (highest first), then by solution id (lowest first)."},"privacy_note":"Your ballot votes are shown to you and to nobody else. No …[+1228 chars]
HTTP 200


################################################################
# STEP 17 — all three residents vote
################################################################

$ curl -X PUT http://127.0.0.1:8000/cycles/1/ballot/1/vote   (Maria: yes)
{"ballot_item_id":1,"your_vote":"yes","note":"You can change this until the ballot closes. Only you can see it."}
HTTP 200

$ curl -X PUT http://127.0.0.1:8000/cycles/1/ballot/1/vote   (Andre: no, then changed to yes)
{"ballot_item_id":1,"your_vote":"no","note":"You can change this until the ballot closes. Only you can see it."}
HTTP 200

$ curl -X PUT http://127.0.0.1:8000/cycles/1/ballot/1/vote   (Andre changes his mind)
{"ballot_item_id":1,"your_vote":"yes","note":"You can change this until the ballot closes. Only you can see it."}
HTTP 200

$ curl -X PUT http://127.0.0.1:8000/cycles/1/ballot/1/vote   (Priya: no)
{"ballot_item_id":1,"your_vote":"no","note":"You can change this until the ballot closes. Only you can see it."}
HTTP 200

--- voting on the item the jury held back ---

$ curl -X PUT http://127.0.0.1:8000/cycles/1/ballot/2/vote   (Maria)
{"error":"item_held_back","message":"The jury held this one back, so it is not being voted on this cycle."}
HTTP 409

--- each voter sees their own vote and nobody else's ---

$ curl -X GET http://127.0.0.1:8000/cycles/1/ballot   (Priya — my_vote is hers alone)
{"cycle_id":1,"cycle_number":1,"state":"open","community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"you_can_vote":true,"ordering":{"version":"ballot-order-v0","explanation":"Ballot items are numbered by umbrella name A-Z, then by net score at the snapshot (highest first), then by solution id (lowest first)."},"privacy_note":"Your ballot votes are shown to you and to nobody else. No …[+1228 chars]
HTTP 200

--- an administrator asking about a user gets jury history, never a ballot vote ---

$ curl -X GET http://127.0.0.1:8000/admin/users/3   (Maria, administrator, looking at Priya)
{"id":3,"display_name":"PriyaR","verification_level":"unverified","email_verified":true,"deleted":false,"is_admin":false,"last_active_at":"2026-09-14T02:05:40.197967Z","jury_history":[{"cycle_id":1,"cycle_number":1,"community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"seat":1,"status":"accepted"}],"ballot_votes":"Not available to anyone but the voter. This endpoint never returns th …[+35 chars]
HTTP 200


################################################################
# STEP 18 — the director closes the ballot and publishes the summary document
################################################################

$ curl -X POST http://127.0.0.1:8000/admin/cycles/1/close
{"cycle_id":1,"state":"closed","closed_at":"2026-09-14T02:05:46.586927Z","results":[{"ballot_item_id":1,"yes":2,"no":1,"result":"passed"},{"ballot_item_id":2,"result":"held_back"}]}
HTTP 200

$ curl -X POST http://127.0.0.1:8000/admin/cycles/1/publish
{"summary_hash":"861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1","published_at":"2026-09-14T02:05:46.647169Z","document":{"document_version":"summary-v1","rules_version":"rules-v1","header":{"community_name":"San Jose","community_level":"city","community_label":"San Jose (city)","cycle_number":1,"ballot_opened_at":"2026-09-14T02:05:46.195916+00:00","ballot_closed_at":"2026-09-14T02:05:46.586927+00:0 …[+5991 chars]
HTTP 200
published hash: 861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1


################################################################
# STEP 19 — verifying the document
################################################################

$ curl -X GET http://127.0.0.1:8000/summaries/city/408/1/verify   (public, no login)
{"cycle_id":1,"stored_hash":"861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1","recomputed_hash":"861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1","match":true,"verdict":"This document is unchanged since it was published.","explanation":"This code is a fingerprint of everything above. It is made by running a standard calculation called SHA-256 over this document's data. If anyone chan …[+227 chars]
HTTP 200

$ curl -X GET http://127.0.0.1:8000/summaries/hashes
{"explanation":"Every document this platform has published, with its fingerprint. Download any document's JSON, run SHA-256 over it, and compare.","summaries":[{"community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"cycle_number":1,"published_at":"2026-09-14T02:05:46.647169Z","summary_hash":"861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1","url":"/summaries/city/408 …[+6 chars]
HTTP 200

--- the JSON the fingerprint was computed over, re-hashed locally ---
$ sha256sum summary.json
861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1  /tmp/claude-1000/-home-kees-soares-direct-democracy-ca/ce9aba90-f3ba-4216-92cb-c8e2e0b3e5b4/scratchpad/summary.json
stored hash:  861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1
recomputed locally: 861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1
stored on the cycle: 861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1
MATCH

$ curl -X GET http://127.0.0.1:8000/summaries/city/408/1   (the document)
{"summary_hash":"861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1","published_at":"2026-09-14T02:05:46.647169Z","document":{"header":{"jury":"1 drawn, 1 seated","build":"demo-01","cycle_number":1,"jurors_drawn":1,"jurors_seated":1,"community_name":"San Jose","residency_note":"Residency is self-declared and unverified at this verification level.","community_label":"San Jose (city)","community_level":"c …[+6621 chars]
HTTP 200


################################################################
# STEP 20 — the PDF, the results page, and the send-to-representatives link
################################################################
$ file summary.pdf
5162 bytes
0000000   %   P   D   F   -   1   .   4  \n   % 223 214 213 236       R
0000020   e   p   o   r

$ curl -X GET http://127.0.0.1:8000/results   (Priya's three communities)
{"communities":[{"community":{"level":"city","entity_id":408,"name":"San Jose","label":"San Jose (city)"},"most_recent":{"cycle_number":1,"published_at":"2026-09-14T02:05:46.647169Z","summary_hash":"861f5ecd3b9971240fecb0d9d5aaa6bcb59d838c66299793074a794898bee9d1","url":"/summaries/city/408/1","item_count":2},"past_cycles":[],"current_cycle_state":"published"},{"community":{"level":"county","entity_id":43,"name":"San …[+361 chars]
HTTP 200

--- the mailto: link the Send button opens (the platform sends nothing itself) ---
mailto:director@example.com,director@example.com?subject=Ballot%20results%20%E2%80%94%20San%20Jose%20%28city%29%2C%20cycle%201&body=I%20am%20a%20resident%20of%20this%20community.%20These%20are%20the%20results%20of%20our%20ballot%20this%20cycle%2C%20voted%20on%20by%20residents%20and%20published%20in%20full%3A%0A%0A%2Fsummaries%2Fcity%2F408%2F1%0A%0ADocument%20fingerprint%20%28SHA-256%29%3A%20861f5e


################################################################
# STEP 21 — the held-back solution cannot return to a ballot unchanged (DEMOCRACY §7.2 condition 4)
################################################################
HTTP 200
{
  "cycle_id": 2,
  "number": 2,
  "state": "prepared",
  "items": [],
  "zero_item_note": "No solution qualified. Publish this cycle when ready and the next one can be prepared; no jury is drawn for an empty ballot.",
  "considered": [
    {
      "solution_id": 3,
      "umbrella": "Pedestrian Safety Near Schools",
      "net_score": 0,
      "conditions": {
        "dominant": false,
        "dominant_long_enough": false,
        "score_at_or_above_ballot_threshold": false,
        "newer_than_last_ballot_version": true
      }
    },
    {
      "solution_id": 1,
      "umbrella": "Pedestrian Safety Near Schools",
      "net_score": 2,
      "conditions": {
        "dominant": true,
        "dominant_long_enough": true,
        "score_at_or_above_ballot_threshold": true,
        "newer_than_last_ballot_version": false
      }
    },
    {
      "solution_id": 2,
      "umbrella": "Pedestrian Safety Near Schools",
      "net_score": 2,
      "conditions": {
        "dominant": true,
        "dominant_long_enough": true,
        "score_at_or_above_ballot_threshold": true,
        "newer_than_last_ballot_version": false
      }
    }
  ]
}


################################################################
# STEP 22 — the public transparency pages
################################################################

$ curl -X GET http://127.0.0.1:8000/admin/log   (public, no login)
{"explanation":"Everything an administrator does on this platform is recorded here, with what changed and why. You do not need an account to read it.","items":[{"id":7,"administrator":"MariaD","action":"prepare_ballot","subject_type":"cycle","subject_id":2,"old_value":null,"new_value":{"items":0,"community":"city:408","active_users":3},"reason":null,"at":"2026-09-14T02:05:46.814468Z"},{"id":6,"administrator":"MariaD" …[+1680 chars]
HTTP 200

$ curl -X GET http://127.0.0.1:8000/ai/actions   (public, no login)
{"explanation":"Every action any AI takes on this platform is written down here before its result is shown to anyone: what it was, what it acted on, which model and which prompt file, a fingerprint of exactly what it was given, what it answered, and whether a person later confirmed or corrected it. AI never decides anything here.","items":[{"id":1,"action_type":"label","subject_type":"post","subject_id":1,"demo_build …[+662 chars]
HTTP 200


################################################################
# STEP 23 — the user's own data, and account deletion
################################################################

$ curl -X POST http://127.0.0.1:8000/me/export   (Andre)
{"id":1,"status":"requested","message":"We are putting your data together. Come back to this link in a moment to download it."}
HTTP 202
$ head of Andre's export
{
  "account": {
    "id": 2,
    "email": "andre@example.com",
    "real_name": "Andre Whitfield",
    "display_name": "AndreW",
    "date_of_birth": "1979-11-02",
    "gender": "man",
    "political_party": "republican",
    "home_city": "San Jose",
    "home_county": "Santa Clara",
    "home_state": "California",
    "verification_level": "unverified",
    "email_verified_at": "2026-09-14 02:05:39.482174+00:00",
    "is_admin": false,
    "created_at": "2026-09-14 02:05:38.760605+00:00",
    "deleted_at": null
  },
  "display_settings": {
    "public_name_mode": "display_name"
  }
}
civic_record keys: ['posts', 'solutions_you_started', 'amendments_you_proposed', 'comments_you_wrote', 'workshop_votes', 'your_ballot_votes', 'your_ballot_votes_note', 'jury_service']
his own ballot votes: [
  {
    "cycle_id": 1,
    "ballot_item_id": 1,
    "solution_id": 1,
    "your_choice": "yes",
    "your_verification_level_at_the_time": "unverified",
    "cast_at": "2026-09-14 02:05:46.342382+00:00",
    "last_changed_at": "2026-09-14 02:05:46.401894+00:00"
  }
]
amendments he proposed: [1]

--- an export belongs to one person ---

$ curl -X GET http://127.0.0.1:8000/me/export/1   (Priya asking for Andre's export)
{"error":"export_not_yours","message":"That export belongs to someone else."}
HTTP 403

--- Andre deletes his account; the civic record stays, the identity goes ---

$ curl -X DELETE http://127.0.0.1:8000/me   (wrong password)
{"error":"bad_credentials","message":"That password is not right. Your account has not been changed."}
HTTP 401

$ curl -X DELETE http://127.0.0.1:8000/me   (Andre)
{"message":"Your account is deleted. Your name, email, password, date of birth, gender and political party are erased. What you wrote stays in the civic record as Former Community Member."}
HTTP 200
HTTP 200
amendment 1 -> Former Community Member | status absorbed
comment by PriyaR
   reply by Former Community Member

$ curl -X POST http://127.0.0.1:8000/auth/login   (Andre, after deletion)
{"error":"bad_credentials","message":"Email or password is incorrect."}
HTTP 401


################################################################
# STEP 24 — refresh-token rotation and reuse detection
################################################################

$ curl -X POST http://127.0.0.1:8000/auth/refresh   (Priya, valid cookie — rotates)
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzIiwiaWF0IjoxNzg5MzUxNTUwLCJleHAiOjE3ODkzNTMzNTAsImp0aSI6IjUwNTAxYjc3ZDQwMzRmODdhMGY2MmE5MTAyYzhhNzVhIn0.kjW4PEh-IGaEVSNTu1-tdnyyDOEzPPgXkA2jR8drAd8","token_type":"bearer","user_id":3,"email_verified":true}
HTTP 200

$ curl -X POST http://127.0.0.1:8000/auth/refresh   (the same old token again — reuse detected)
{"error":"refresh_reused","message":"For your safety we signed you out of every device. Please sign in again."}
HTTP 401

$ curl -X POST http://127.0.0.1:8000/auth/refresh   (the rotated token — the whole chain was revoked)
{"error":"refresh_reused","message":"For your safety we signed you out of every device. Please sign in again."}
HTTP 401

--- logout blacklists the access token's jti ---

$ curl -X POST http://127.0.0.1:8000/auth/logout   (Maria)
{"message":"Signed out."}
HTTP 200

$ curl -X GET http://127.0.0.1:8000/auth/me   (the same access token after logout)
{"error":"token_revoked","message":"That session has been signed out."}
HTTP 401


################################################################
# WALKTHROUGH COMPLETE
################################################################
```

#### `git log --oneline` and `git status`

```
$ git log --oneline
e5357fc Retry posts stuck at 'being filed'; evidence for the demo-01 run
948afe6 F-22/F-24/I-25..I-28 frontend: every route in ARCHITECTURE §9
3629236 I-01..I-24 Iteration backend: the whole civic process
3720843 F-04..F-21 Foundation: accounts, auth, rights, geography, settings, logs, legal
054b800 F-01/F-02/F-03 package layout, configuration, async engine, Alembic branches
812341c docs/fix document versions (#4)
67bee97 Document consistency audit 2026-09-13; audit brief; seed files to backend/config (#3)
8fc2b76 Merge pull request #2 from lHollandl/docs/sandbox-verified
3eda08f Sandbox verified; full city seed; docs updated
a73be87 Merge pull request #1 from lHollandl/docs/framework-migration
6fa4c0c Migrate project documents to the new framework
263d4c6 Day 3 complete — auth, frontend, AI labeling pipeline, umbrella assignment
b8ed3d6 Replace passlib with direct bcrypt calls for password hashing
a79fb33 Add CORS, startup table creation, and models import to main.py
0713291 Add API routers for users, posts, votes, and labels
ab1d639 Add database session factory and get_db dependency
d0e9429 Add COPPA, consent, and user sovereignty fields to User model
03c1e6c Add SQLAlchemy ORM models for core civic data layer
4e82394 Add backend dependencies for auth, database, and security
5272db4 Add Docker Compose infra for PostgreSQL and Redis
b806689 Add Developer Constitution (CLAUDE.md)
f5257eb Scaffold FastAPI backend with health check
354971c Scaffold Next.js frontend with placeholder homepage
6e470d9 Initial project structure
de8d74c Initial commit
```

```
$ git status --short
(clean)
```

---

**Decisions made:**

1. **Two settings were missing from `seed_settings.yaml`.** DEMOCRACY §7.4
   lists `reference_reject_min` (2) and `min_signup_age` (17); the director's
   seed file stopped at `references_ai_max_per_umbrella`. Without
   `min_signup_age` nobody could sign up at all. They were transcribed from the
   §7.4 table into the seed file with a comment saying so — not invented. The
   seed runner now refuses to run if any §7.4 key is absent, so this cannot
   pass silently again.
2. **How an account becomes an administrator.** No document says. There is
   deliberately no endpoint: an administrator can change every rule a democratic
   outcome depends on, so the only way in is `backend/scripts/grant_admin.py`,
   run by somebody with access to the machine. The grant writes a row to the
   public admin log like any other administrator action.
3. **Prompt files declare the JSON shape they expect back.** `llama3.2` first
   answered the labeler with malformed JSON — an object where an array belonged
   — and the strict parser correctly called it a failure. Rather than loosening
   the parser, each prompt file now carries a JSON Schema in its header block
   and the client hands it to Ollama, which constrains the model's output. The
   shape is still written in prose in the same file, because the file is the
   contract (Law 7); the schema only stops a small model wrapping it in
   commentary. Prompt versions went to 4, 2 and 2.
4. **A model that answers for communities it was never given.** `llama3.2`
   repeated a community and echoed communities from the prompt's example. The
   labeler keeps the first answer that names an umbrella actually present in
   that community, ignores the rest, and records what it ignored in the public
   AI log under `repeated_or_unlisted_communities`. Temperature is 0, so the
   same post files the same way twice.
5. **The similarity check has no prompt file.** It uses an embedding model, and
   there is no prompt text to hash. Its `ai_actions` rows say
   `prompt_file = "(embeddings: no prompt file)"` and `prompt_hash` = 64 zeros
   rather than citing a file that does not exist.
6. **Hash shapes for amendments and comments.** DATABASE §4.9 and §4.11 require
   a `content_hash` but do not fix its fields. Both use the same shape as every
   other hash on the platform: the content, who wrote it, and when.
7. **Ballot-vote privacy in the repository layer.** `cycles.py` has exactly one
   function that reads a ballot vote with a voter id (`my_ballot_votes`) and one
   that reads a person's own rows for their export. Everything else returns
   counts. `GET /admin/users/{id}` returns a sentence saying so instead of a
   field.
8. **`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` added to `.env`.**
   ARCHITECTURE §3 says one root `.env` is passed to Compose with `--env-file`,
   and Compose needs those three. They are in `.env.example` with a comment
   saying they must match the credentials inside `DATABASE_URL`.
9. **Passwords are capped at 72 bytes**, because that is bcrypt's limit and
   anything longer would be silently truncated. The signup form says so in
   plain words rather than cutting it quietly.
10. **The page headers are a CSS gradient, not a photograph.** The style brief
    asks for California photography; the director has not supplied images, and
    inventing them would be worse than leaving the slot. The gradient keeps every
    page identical with images off and light on a slow connection, and a
    photograph drops into the same rule later.

---

**Issues encountered:**

**Two real bugs, both found by driving the platform rather than by a test.**

1. **Background jobs were cancelled when the poster closed the tab.** Labeling
   was a FastAPI `BackgroundTasks` entry, which is attached to the response;
   `curl` disconnecting after reading the body cancelled it mid-flight, and
   because `asyncio.CancelledError` is not an `Exception`, nothing was logged.
   The post simply sat at "being filed" forever. Jobs are now independent
   asyncio tasks with a strong reference held in `backend/jobs/runner.py`, and
   they are started from a SQLAlchemy `after_commit` hook so they never open a
   session before the row they need exists.
2. **Detecting refresh-token reuse did not actually revoke anything.** The chain
   was revoked and then `Unauthorized` was raised — which rolled the request's
   transaction back, taking the revocation with it. In the first walkthrough the
   rotated token still worked after the platform had announced it had signed the
   person out everywhere. The revocation now happens in its own committed
   transaction before the 401 is raised, and a test asserts that the newest
   token in the chain is dead.

**A third gap, found while writing the technical-debt list.** `label_retry` only
re-queued posts marked `unlabeled`, which means an attempt that failed. A post
whose job never started at all — the process restarted between the commit and
the scheduling — stayed `pending` forever, telling its author it was still being
filed. The retry now also sweeps `pending` posts older than the retry window,
and leaves newer ones to the job that is still running.

**Smaller things.**

- A blanket edit gave `post_communities.community_entity_id` a
  `GENERATED ALWAYS AS IDENTITY`, so every post failed with a 500. Caught on the
  first real post. The Iteration migration was regenerated, which DATABASE §6
  allows during a demo.
- `logging`'s `extra=` refuses a key that shadows a `LogRecord` attribute, and
  `extra={"created": …}` raised `KeyError` **inside** the labeling job, killing
  it silently. Renamed, and `logging_config.safe_extra()` now exists so a log
  line can never again be the reason a job dies.
- Alembic's `env.py` overrode the URL `verify_schema.py` had set, so the scratch
  database was built empty and every table looked like drift. `env.py` now only
  sets the URL when a caller has not.
- Next.js 16.1.6 did not apply nested-layout `metadata` to the server-rendered
  head, so every page served the same `<title>`. Each page now sets its own
  title from the client, which is what a person and a screen reader get.
- The React 19 lint rule `react-hooks/set-state-in-effect` flagged the
  fetch-on-mount pattern on five pages. Rather than disable it, the pages now
  share `useLoader`, which sets state from the promise callback and drops a
  result that arrives after the reader has left.

**Surprises worth recording.**

- The labeler is fast: 2–6 seconds end to end against `llama3.2` on the host
  GPU, including model load.
- With three active users every threshold collapses to 1
  (`threshold(5, 3, 3) = 1`), so a single upvote makes a solution dominant and a
  single upvote absorbs an amendment. The arithmetic is right and the tests
  cover the boundaries properly, but the demo itself proves nothing about
  behaviour at scale.
- The jury draw excludes the authors of every qualified solution and every
  administrator, so a three-person community produced a **one**-person jury.
  DEMOCRACY §8.1 anticipates this and the summary prints "1 drawn, 1 seated",
  which is exactly what a reader needs to judge it.

---

**Notes:** deviations from the brief

- **Postgres and Redis were not run in containers**, and `infra/docker-compose.yml`
  was never started. The blob CDN is not on the sandbox allowlist. Details above.
- **No screenshots.** No browser could be installed. `pages.txt` records what
  each route actually returned instead.
- **The walkthrough transcript is truncated in this entry** at 420 characters per
  response, with the remaining length marked. The complete transcript is
  committed at `briefs/evidence/demo-01/walkthrough.txt`.
- **The test database is a throwaway database, not a throwaway container**
  (ARCHITECTURE §10 says container). It is created and dropped by the test
  session and its schema comes from both migration chains, never `create_all`.

---

**Notes:** places a document looked wrong

Reported, not silently resolved.

1. **`seed_settings.yaml` is missing two of the keys DEMOCRACY §7.4 requires.**
   Fixed in the seed file by transcription; the director should confirm the
   values are the ones intended.
2. **DATABASE §3.11 says the export contains "every Iteration row they authored
   or voted on".** Jury service is listed separately in the same paragraph, so
   it is included; the sentence would read better naming all three.
3. **DEMOCRACY §10.2 lets a prepared cycle publish only with zero items, and
   §10.1's diagram shows `prepared → published`.** Because prepare moves
   straight to `jury_review` whenever items exist, a cycle can only ever be
   observed in `prepared` when it is empty. The guard against publishing a
   non-empty `prepared` cycle is therefore unreachable in this build. It was
   kept, because it protects the invariant if prepare is ever split.
4. **ARCHITECTURE §6 lists `GET /auth/me`, while §9's frontend expects display
   settings under `/me`.** Both exist: `/auth/me` reads, `PATCH /me/display`
   writes. Worth one sentence in §6 to say so.
5. **ARCHITECTURE §10 asks for a throwaway Postgres container in the test
   session.** In a sandbox that cannot pull images that is impossible; a
   throwaway database is the nearest equivalent. The document may want to say
   "database or container".
6. **No document says how the first administrator is made.** Decision 2 above.

---

**Notes:** open follow-ups

- `ballot_min_dominant_days` is **0** in the demo database, lowered by a logged
  settings change so a one-day walkthrough could reach a ballot. It must go back
  to 3 before anybody reads this build's output as a real result.
- P0-13 is still open: no web search provider, so the reference recommender has
  never run against a real one.
- `infra/docker-compose.yml` needs its first real run on the workstation.
- The audit run comes next (AUDIT.md, `briefs/audit.md`). Nothing from this
  branch has been merged to `main`; the Foundation half goes by pull request
  only after the audit passes.

---

**Document changes flagged:**

None of the five protected documents were edited. The six observations above are
for the director to decide on. TODO.md was updated as the session law requires:
every F and I id marked, the status snapshot rewritten, and nine new
technical-debt entries added with what makes each of them bite.


**Addendum (same session, later) — `ballot_min_dominant_days` restored to 3.**
The open follow-up above is closed. The build lowered the setting to 0 so the
walkthrough could reach a ballot inside one day; it is back to 3, changed the
same way it was lowered — through `POST /admin/settings`, by an administrator,
with a reason written for the community rather than for the build. The settings
table is append-only, so the public history now reads **3 → 0 → 3** with all
three reasons attached, and the change is row 8 of the public administrator log.
Nothing in code was touched; the value only ever lived in the `settings` table
(Law 8).

The last block below is a read-only check, and it is the part that matters: it
reads the live setting through `services/settings.py` and asks `rules.py` what
would qualify now. Solutions 1 and 2 are still dominant and still above the
ballot threshold, but `dominant_long_enough` is **NOT met** for either — they
became dominant today. Under 0 that condition passed. The rule is genuinely
back in force, not merely a different number on a page.

```
$ curl -X POST http://127.0.0.1:8000/admin/settings   (Maria, administrator)
{"key":"ballot_min_dominant_days","old_value":0,"new_value":3,"message":"Changed. The new value is on the public settings page and the change is in the public admin log."}
HTTP 200

--- the public settings history, no login needed: 3 -> 0 -> 3 ---
$ curl http://127.0.0.1:8000/settings/history?key=ballot_min_dominant_days
[
    {
        "key": "ballot_min_dominant_days",
        "value": "3",
        "effective_from": "2026-09-14T02:50:56.593978Z",
        "changed_by": "MariaD",
        "reason": "Restoring the Demo 1 default. It was lowered to 0 so the build walkthrough could reach a ballot inside a single day; that walkthrough is finished and its results are published, so the three-day dominance requirement is back in force. No result published while it was 0 should be read as one a real community could have produced."
    },
    {
        "key": "ballot_min_dominant_days",
        "value": "0",
        "effective_from": "2026-09-14T02:05:41.310828Z",
        "changed_by": "MariaD",
        "reason": "This walkthrough runs inside a single day, and the three-day dominance requirement would make a ballot unreachable. Restore it to 3 before any real community uses this."
    },
    {
        "key": "ballot_min_dominant_days",
        "value": "3",
        "effective_from": "2026-09-14T02:03:40.563309Z",
        "changed_by": "the platform seed",
        "reason": "Demo 1 default"
    }
]

--- the value now in force ---
$ curl http://127.0.0.1:8000/settings
{
  "key": "ballot_min_dominant_days",
  "value": 3,
  "raw_value": "3",
  "meaning": "How many days a solution must have been dominant before it can go on a ballot.",
  "defined_in": "DEMOCRACY.md \u00a77.2",
  "effective_from": "2026-09-14T02:50:56.593978Z",
  "changed_by_user_id": 1,
  "reason": "Restoring the Demo 1 default. It was lowered to 0 so the build walkthrough could reach a ballot inside a single day; that walkthrough is finished and its results are published, so the three-day dominance requirement is back in force. No result published while it was 0 should be read as one a real community could have produced.",
  "set_by": "an administrator"
}

--- the public administrator log, no login needed ---
$ curl http://127.0.0.1:8000/admin/log?limit=2
[
  {
    "id": 8,
    "administrator": "MariaD",
    "action": "change_setting",
    "subject_type": "setting",
    "subject_id": null,
    "old_value": {
      "key": "ballot_min_dominant_days",
      "value": 0
    },
    "new_value": {
      "key": "ballot_min_dominant_days",
      "value": 3
    },
    "reason": "Restoring the Demo 1 default. It was lowered to 0 so the build walkthrough could reach a ballot inside a single day; that walkthrough is finished and its results are published, so the three-day dominance requirement is back in force. No result published while it was 0 should be read as one a real community could have produced.",
    "at": "2026-09-14T02:50:56.593978Z"
  },
  {
    "id": 7,
    "administrator": "MariaD",
    "action": "prepare_ballot",
    "subject_type": "cycle",
    "subject_id": 2,
    "old_value": null,
    "new_value": {
      "items": 0,
      "community": "city:408",
      "active_users": 3
    },
    "reason": null,
    "at": "2026-09-14T02:05:46.814468Z"
  }
]

--- the restored rule, evaluated read-only against the solutions in the demo database ---
$ python  (reads the live setting through services/settings.py and asks rules.py)
ballot_min_dominant_days in force: 3

solution 3: would qualify now = False
    NOT met  dominant
    NOT met  dominant_long_enough
    NOT met  score_at_or_above_ballot_threshold
    met      newer_than_last_ballot_version
solution 1: would qualify now = False
    met      dominant
    NOT met  dominant_long_enough
    met      score_at_or_above_ballot_threshold
    NOT met  newer_than_last_ballot_version
solution 2: would qualify now = False
    met      dominant
    NOT met  dominant_long_enough
    met      score_at_or_above_ballot_threshold
    NOT met  newer_than_last_ballot_version
```

Full output at `briefs/evidence/demo-01/restore-ballot-min-dominant-days.txt`.

One loose end is deliberately left alone: cycle 2 in San Jose sits in
`prepared` with zero items, where the walkthrough left it after demonstrating
that nothing returns to the ballot unchanged. Publishing it is a director
control (DEMOCRACY §13), and the next cycle cannot be prepared until it is
published, so the director may want to do that before using the demo. This run
did not, because it is their action to take, not the build's.

---

## 2026-09-14 — Session 2 (Claude Code audit — demo-01, run 1)

Report: `audits/demo-01-audit-1.md`. Counts: CRITICAL 0 · HIGH 1 · MEDIUM 0 ·
LOW 3 · NOTE 2. Verdict: **FIX REQUIRED**. Findings live in the report, not
here.
