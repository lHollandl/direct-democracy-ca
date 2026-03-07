# Direct Democracy Cali — TODO & Future Notes

> This document tracks known gaps, future tasks, and important technical notes 
> that need to be addressed before launch. Organized by priority.

---

## 🔴 Required Before Any Real Users Touch This

- [ ] **Email verification on signup** — right now anyone can sign up with a fake email. Need to send a confirmation link and keep the account inactive until clicked.
- [ ] **Password reset flow** — there is currently no way for a user to recover a forgotten password. Needs a "forgot password" email flow.
- [ ] **HTTPS / SSL certificates** — everything runs on http://localhost. Before deploying to a real server, SSL is mandatory. No exceptions.
- [ ] **Privacy Policy page** — legally required before real users. Must cover data collection, CCPA rights, and AI labeling disclosure.
- [ ] **Terms of Service page** — legally required before real users.
- [ ] **Cookie consent banner** — required for CCPA compliance.
- [ ] **Account deletion flow** — required by the constitution §6 (User Sovereignty). Must anonymize all posts (preserve civic record) but erase all PII. Not yet implemented.

---

## 🟡 Authentication — Phase 2 Tasks

- [ ] **Refresh tokens** — JWT access tokens currently expire after 30 minutes. This is the correct secure default but will frustrate real users who get logged out mid-session.
  - The fix: implement a second "refresh token" that lives 7–30 days and silently obtains a new 30-minute access token without forcing the user to log in again.
  - **Do NOT change the 30-minute expiry without building refresh tokens first.** Changing it alone just trades security for convenience with no proper solution.
  
- [ ] **Redis token blacklist for logout** — POST /auth/logout currently just tells the client to delete the token. A determined person could reuse the token for up to 30 minutes after logging out.
  - The fix: store invalidated tokens in Redis with a TTL matching the token expiry.
  - Already noted in the code comments as a Phase 3 task.

---

## 🟡 Database

- [ ] **Expand city seed data** — currently only 10 major California cities are seeded. Residents outside those cities can't select their city. Needs expansion before launch.

- [ ] **Running Alembic migrations** — Alembic is fully set up. Every future schema change (adding a column, renaming something, adding a table) must use this workflow:
  ```bash
  cd ~/direct-democracy-ca/backend
  pipenv run alembic revision --autogenerate -m "describe your change here"
  pipenv run alembic upgrade head
  ```
  Never modify the database directly. Never use create_all. Never edit existing migrations.

---

## 🟡 Features That Exist in the Schema But Aren't Implemented Yet

- [ ] **Influence score** — the `influence_score` column exists on the User model but nothing calculates or updates it. Needs a design decision: what actions earn influence? What does it affect?

- [ ] **Political party** — the `political_party` column exists on User but nothing uses it. Needs UI for users to set it and logic for how it affects the experience (if at all).

- ✅ **Umbrella issue assignment** — AI labeling pipeline now sets `umbrella_issue_id` on Solution and creates PostUmbrellaIssue rows. Labeling and umbrella assignment are the same action.

---

## 🟠 Constitution Requirements Not Yet Built

These are laws from CLAUDE.md that haven't been implemented yet:

- [ ] **§4 Small Voice — evolutionary/mutation algorithm** — the feed ranking algorithm needs to be designed *before* the feed is built out further. The visibility threshold for minority viewpoints must be a configurable public setting, never hardcoded. Do not build a complex feed UI before this is designed.

- [ ] **§3 Democratic Neutrality — sorting algorithm documentation** — when the feed sorting algorithm is written, it must be documented in plain English alongside the code. Not after. Not in a separate doc. Right next to the code itself.

- [ ] **§5 AI Accountability — Merkle tree hashing** — the `content_hash` column exists on Post and Solution but nothing populates it yet. When the AI labeling pipeline is complete, the Merkle tree hash requirement from the constitution kicks in for full transparency.

---

## 🟡 Frontend — Known Gaps After Prompt 3

- [ ] **Post creation form** — `/posts/new` is a placeholder. Full form needs: title, content, solution_title, solution_content, location picker (state → county → city cascade). To be built in Prompt 4 alongside AI labeling.
- [ ] **Author username on posts** — the feed shows `user_id` from the API but not the username. The backend `GET /posts` response doesn't include the username — either add it to `PostResponse` (preferred) or make a separate `/users/{id}` call per post (expensive). Should be fixed when post creation is built.
- [ ] **Location display** — the feed currently shows `City #1` instead of the actual city name. The `/states`, `/counties`, `/cities` endpoints are available — build a location lookup cache on the frontend when the post creation form is built.
- [ ] **useRouter.refresh() on logout** — calling `router.refresh()` after logout keeps the page but re-renders server components; client state (current user) is already cleared locally. Works correctly for now.

---

## 🟡 AI Labeling — Known Gaps After Prompt 4

- [ ] **Ollama must be running for live labeling** — if Ollama is not running, posts save but get "Unlabeled / Pending Review" labels. No retry mechanism exists yet. Consider a periodic retry job for posts with confidence=0 and category="Unlabeled".
- [ ] **ai/labeler.py is imported via sys.path manipulation** — `backend/routers/posts.py` adds the repo root to sys.path so it can import `ai.labeler`. This works but is fragile. A cleaner solution would be a proper Python package layout (pyproject.toml at repo root). Acceptable for now.
- [ ] **Test umbrella is manually seeded via raw SQL** — the "Road Damage and Pothole Repair" umbrella was inserted directly. The democratic proposal and approval system that will create future umbrellas is not yet built (see Future Features section).
- [ ] **No retry for failed labels** — if Ollama returns garbage JSON or times out, the post gets a fallback "Unlabeled" label. No background job exists to retry these. Add a periodic task (cron or Celery) to re-label posts with confidence=0 once the AI is back.
- [ ] **httpx added to Pipfile** — `httpx` was added to the backend Pipfile for Ollama HTTP calls. Pipfile.lock was updated.

---

## 🧠 Future Features — Designed but Not Yet Built

### Core Architecture — Category and Umbrella System

Categories and umbrella problems are the same thing,
structured in two layers:

MAIN CATEGORY = broad topic bucket controlled by the
platform and grown by community approval
(Examples: Roads and Infrastructure, Public Safety)

SUBCATEGORY = the umbrella problem itself. Every
subcategory IS an umbrella problem. Posts are assigned
to subcategories/umbrellas. Solutions aggregate inside
umbrellas. Votes happen inside umbrellas.

This means labeling a post and assigning it to an
umbrella problem are the same single action — not
two separate steps.

Three ways a post gets categorized:
1. AI automatically picks the closest matching main
   category and existing subcategory/umbrella —
   always assigns to highest similarity match,
   no matter the score
2. User manually selects from approved lists
3. User disagrees and proposes a brand new subcategory
   or main category — enters democratic approval pipeline

The AI is a sorting assistant, not a decision maker.
AI never creates new umbrella problems automatically.
Only humans create new umbrella problems through
the proposal and approval system.

### Democratic Category and Umbrella Proposal System

This is a core feature of the platform. Citizens propose
new main categories and new subcategories/umbrella problems.
Communities vote to approve them. The category taxonomy
is itself democratic.

Proposing a new subcategory/umbrella problem:
- User disagrees with AI label
- Browses existing subcategories under a main category
- Nothing fits — they propose a new subcategory name
- Must attach to an existing approved main category
- Subcategory cannot be placed under a proposed main
  category — main category must be approved first
- Selects which governance levels the proposal applies to
  (city, county, state, federal — checkboxes)
- Proposal enters Pending Approval for those governance levels

Proposing a new main category:
- User can also propose an entirely new main category
- Goes through the same approval process
- No subcategories can be added under it until it
  is fully approved

Similarity grouping of proposals — two layer approach:
- Layer 1: AI flags new proposals similar to existing
  pending proposals above a similarity threshold
- Layer 2: Users confirm or reject the suggested merge —
  AI suggests, humans decide
- This prevents duplicate umbrella problems from
  cluttering the system

Approval threshold (dynamic by governance level):
- City — 2% of active users OR 50 votes minimum,
  whichever is lower
- County — 1.5% of active users OR 100 votes minimum
- State — 1% of active users OR 500 votes minimum
- Federal — 0.5% of active users OR 1000 votes minimum
- Minimum 7 day window before anything can be approved
- Proposals with no new votes for 30 days go dormant
  (not deleted — revivable if someone new votes)

When a proposal is approved:
- It becomes an official subcategory/umbrella problem
  in the selected governance levels
- The AI labeling pipeline immediately starts routing
  new matching posts to it
- Users can immediately select it when submitting posts
- Posts previously assigned to a similar umbrella may
  be surfaced for re-review

Reputation points — early contribution model:
- Reputation is cosmetic only — classic clout, no spending
- Points awarded on time-decay curve when a proposal passes:
  Day 1 supporter = 100 points
  Day 7 supporter = 70 points
  Day 30 supporter = 30 points
  After approval = 5 points (for spreading awareness)
- Original proposer gets a founder bonus multiplier
- Failed proposals = 0 points for everyone
- The risk makes the reward meaningful
- If similar proposals are merged, all early supporters
  of both proposals earn points — first proposer of
  the winning name gets the founder bonus

Open design decisions still needed before building:
- Exact reputation point values and decay curve numbers
- AI similarity score threshold for proposal grouping
- Whether dormant proposals can be re-proposed by
  someone else
- What happens to posts assigned to an umbrella whose
  proposal is later rejected — revert to AI suggestion?
- Final fixed main category list

### Fixed Main Category List — Needs Design Work

The AI currently uses free text categories. Before
launch this needs to be replaced with a curated fixed list.

Plan:
- A config file at backend/config/categories.py holds
  the official list
- Every entry is a main category only — subcategories
  are umbrella problems created through the democratic
  proposal system
- The AI must choose a main category from this list
- The AI assigns to the closest existing approved
  subcategory/umbrella within that main category
- If no subcategories exist yet for a main category,
  AI assigns to main category only and flags for
  human review

Placeholder main categories to use until real list
is designed:
Roads and Infrastructure, Housing and Homelessness,
Public Safety, Environmental Issues, Education,
Public Transit, Water and Utilities, Parks and
Recreation, Economic Development,
Government Accountability

This list grows through the democratic proposal system
after launch. Platform owner controls the seed list.

### Post Creation Flow — Full Vision

When a user creates a post the UI should offer:

1. Write your problem description
2. Write your proposed solution
3. Select governance levels (city, county, state, federal)
4. Category assignment — three options:
   a. Let AI decide (default)
   b. Pick from existing approved categories yourself
   c. Propose a new category or umbrella problem

Option c launches the proposal flow inline. The post
still gets submitted immediately. The proposal enters
the approval pipeline separately.

This makes proposing new ideas feel fast and natural —
not like a bureaucratic side process.

---

## 🔵 Phase 3 Tasks (Blockchain / IPFS)

- [ ] IPFS content storage for posts
- [ ] Polygon blockchain trust layer
- [ ] Web3 transparency layer for AI impact tracking
- [ ] Redis token blacklist (also listed above under auth)
- [ ] Merkle tree hashing for post content

---

## 📋 Day 3 Remaining Prompts

If picking up development, these prompts still need to be run in Claude Code in order:

1. ✅ **Prompt 3 — Connect the Frontend** — signup page, login page, and feed page built and verified
2. ✅ **Prompt 4 — AI Labeling Pipeline** — labeler built in ai/labeler.py; background task wired into POST /posts; four verification tests passed

---

## 🛠️ Useful Commands

```bash
# Start everything for a dev session
cd ~/direct-democracy-ca/infra && docker compose up -d
cd ../backend && pipenv run uvicorn main:app --port 8000 &
cd ../frontend && npm run dev

# Shut everything down
pkill -f "uvicorn main:app"
cd ~/direct-democracy-ca/infra && docker compose down

# Run a database migration after a schema change
cd ~/direct-democracy-ca/backend
pipenv run alembic revision --autogenerate -m "your description"
pipenv run alembic upgrade head

# Check current Alembic migration version
pipenv run alembic current

# Check what's in the database
docker exec infra-postgres-1 psql -U ddcuser -d directdemocracy -c "\dt"
```

---

## 📍 Current Status

| Layer | Status |
|-------|--------|
| Database (PostgreSQL + Redis) | ✅ Running in Docker |
| Backend API (FastAPI) | ✅ 20+ endpoints live at localhost:8000 |
| Authentication (JWT) | ✅ Login, logout, /auth/me all working |
| Alembic migrations | ✅ Set up, create_all removed |
| Database indexes | ✅ 11 indexes in place |
| Rate limiting | ✅ On all write endpoints |
| Error handling | ✅ No stack traces leaked to client |
| California geography seed | ✅ 1 state, 58 counties, 10 cities |
| Frontend (Next.js) | ✅ Connected — signup, login, feed pages live at localhost:3000 |
| AI labeling pipeline | ✅ Live — ai/labeler.py; background task on POST /posts; Ollama llama3.2 |
| Category config | ✅ backend/config/categories.py — 10 main categories |
| Umbrella assignment | ✅ Labeling and umbrella assignment are the same action — PostUmbrellaIssue + Solution.umbrella_issue_id both set |
| Refresh tokens | ❌ Not built |
| Email verification | ❌ Not built |
| Account deletion | ❌ Not built |
| Feed algorithm | ❌ Not designed yet |

---

*Last updated: Day 3 — after completing Prompts 1, 2, 3, and 4*

## 📝 Session Log
Claude Code appends a one-line entry here after every 
completed prompt so there is a permanent record of what 
changed and when.

Format: [Day X — Prompt Y] Brief description of what was built

[Day 3 — Prompt 3] Connected Next.js frontend — signup, login, and feed pages built and verified; axios API client with JWT auth; root redirects to /feed
[Day 3 — Design Session] Finalized category + umbrella architecture. Subcategory = umbrella problem. AI always assigns to highest similarity existing umbrella, never creates new ones. Only humans create new umbrellas through proposal system. Full democratic proposal system designed and saved to TODO.md.
[Day 3 — Prompt 4] Built AI labeling + umbrella assignment pipeline. Subcategory = umbrella problem. AI always assigns to closest existing umbrella. Background task wired into POST /posts. Four verification tests passed.
