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





# Direct Democracy Cali — Project History

> **Purpose:** This is the permanent record of every build session, design decision, and milestone for the project.
> It exists so that future team members can understand how the project evolved, why decisions were made,
> and what was built in what order. Claude Code appends to this document at the end of every session.
>
> **Format for new entries:**
> ```
> ## [Day X — Session Name] YYYY-MM-DD
> **What was built or decided:**
> One or more lines describing the work.
> **Why:**
> The reasoning behind the decision (optional but encouraged for design sessions).
> ```

---

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
