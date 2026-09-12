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
