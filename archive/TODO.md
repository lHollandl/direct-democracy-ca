# Direct Democracy Cali — Project Tracker

> **How to use this document:**
> This is the living task tracker for the project. Every task has a phase, a status, and a home.
> Design decisions live in `/docs/design/`. History lives in `HISTORY.md`. Constitution lives in `CLAUDE.md`.
> Claude Code reads this at the start of every session and updates it at the end.

---

## 📍 Current Status Snapshot

| Layer | Status | Notes |
|-------|--------|-------|
| Database (PostgreSQL + Redis) | ✅ Running | Docker |
| Backend API (FastAPI) | ✅ Live | 20+ endpoints at localhost:8000 |
| Authentication (JWT) | ✅ Working | Login, logout, /auth/me |
| Alembic migrations | ✅ Set up | create_all removed |
| Database indexes | ✅ 11 indexes | In place |
| Rate limiting | ✅ On | All write endpoints |
| Error handling | ✅ Clean | No stack traces to client |
| California geography seed | ✅ Partial | 1 state, 58 counties, 10 cities only |
| Frontend (Next.js) | ✅ Connected | localhost:3000 |
| Signup page | ✅ Live | Includes cascading county → city location |
| Login page | ✅ Live | JWT stored client-side |
| Feed page | ✅ Live | Shows posts with real city names |
| Post creation form | ✅ Live | Multi-solution, governance toggles, civic UI |
| Multi-solution posts | ✅ Live | solutions[] array per post |
| User location at signup | ✅ Live | county_id + city_id on User |
| Governance level selection | ✅ Live | City/County/State/Federal toggle cards |
| AI labeling pipeline | ✅ Live | ai/labeler.py + background task on POST /posts |
| Category config | ✅ Placeholder | 10 categories in backend/config/categories.py |
| Umbrella assignment | ✅ Live | PostUmbrellaIssue + Solution.umbrella_issue_id |
| Refresh tokens | ❌ Not built | Phase 1 priority |
| Email verification | ❌ Not built | Required before real users |
| Account deletion | ❌ Not built | Required before real users |
| Password reset | ❌ Not built | Required before real users |
| Feed algorithm | ❌ Not designed | Design doc needed first |
| Category list (final) | ❌ Not finalized | Design doc in progress |
| Umbrella AI Agent | ✅ Designed | Architecture locked — not yet built |
| AIAgentVote / AIAgentAction tables | ❌ Not built | Phase 2 |

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
pipenv run alembic revision --autogenerate -m "describe your change here"
pipenv run alembic upgrade head

# Check current migration version
pipenv run alembic current

# Inspect the database
docker exec infra-postgres-1 psql -U ddcuser -d directdemocracy -c "\dt"
```

---

## 🗂️ Document Index

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Developer constitution — rules that never change |
| `TODO.md` | This file — task tracker and current status |
| `HISTORY.md` | Session log — permanent record of every build session |
| `docs/design/CATEGORIES.md` | Fixed category list and subcategory design decisions |
| `docs/design/FEED_ALGORITHM.md` | Feed ranking and Small Voice system design |
| `docs/design/PROPOSAL_SYSTEM.md` | Democratic category proposal and approval flow |
| `docs/design/AI_AGENT.md` | Umbrella AI Agent architecture and behavior |
| `docs/design/USER_JOURNEY.md` | End-to-end citizen experience (to be created) |

---

## 🔴 Phase 0 — Design and Planning (Current Phase)

These decisions must be locked before more code is written.
Rushing code without these foundations causes expensive rework.

- [ ] **Finalize fixed main category list** — placeholder list exists. Real list needs deliberate design. See `docs/design/CATEGORIES.md`.
- [ ] **Design feed ranking algorithm** — must be designed before feed UI is built further. See `docs/design/FEED_ALGORITHM.md`.
- [ ] **Map full user journey** — what does a citizen actually experience from first load to government response? Write `docs/design/USER_JOURNEY.md`.
- [ ] **Lock open design decisions in proposal system** — reputation values, dormant proposal rules, rejection handling. See `docs/design/PROPOSAL_SYSTEM.md`.

---

## 🔴 Phase 1 — Required Before Any Real Users

Nothing in this section is optional. These are legal, security, and trust requirements.

### Legal
- [ ] **Privacy Policy page** — CCPA compliance, data collection disclosure, AI labeling disclosure
- [ ] **Terms of Service page** — user agreement, content rules, platform liability
- [ ] **Cookie consent banner** — CCPA required

### Security and Auth
- [ ] **Email verification on signup** — anyone can currently sign up with a fake email. Send confirmation link; keep account inactive until clicked.
- [ ] **Password reset flow** — no way to recover a forgotten password. Needs "forgot password" email flow.
- [ ] **Refresh tokens** — JWT tokens expire after 30 min. Without refresh tokens users get kicked out mid-session.
  - Build a refresh token (7–30 day lifetime) that silently obtains a new 30-min access token.
  - **Do NOT extend the 30-min expiry as a shortcut. Build the proper solution.**
- [ ] **HTTPS / SSL certificates** — mandatory before any real server deployment. Currently http://localhost only.

### User Rights (Constitution §6)
- [ ] **Account deletion flow** — delete all PII (name, email, password) but preserve civic record. Posts become "Former Community Member." Not yet implemented.

### Database
- [ ] **Expand city seed data** — only 10 cities seeded. Residents outside those cities can't select their city.

---

## 🟡 Phase 2 — Core Product Features

Features that make the platform usable and meaningful as a civic tool.

### Feed
- [ ] **Feed ranking algorithm** — implement the designed algorithm. Must be documented in plain English right next to the code (§3). Must include Small Voice minority viewpoint protection (§4).
- [ ] **Feed pagination** — infinite scroll or load-more for feeds with many posts

### Post System
- [ ] **Retry failed AI labels** — posts that get "Unlabeled" due to Ollama being offline need a background retry job. Target: posts with confidence=0.
- [ ] **Manual category selection** — UI for users to override the AI label and pick their own category + umbrella
- [ ] **Author username on posts** — currently shown. Verify correct across all edge cases.

### User Profiles
- [ ] **Influence score logic** — `influence_score` column exists but nothing calculates it. Design decision needed: what actions earn it? What does it affect? (Per constitution: cosmetic/rewards only, never ranking.)
- [ ] **Political party field** — `political_party` column exists but nothing uses it. Decide: show on profile? Affect anything?
- [ ] **User profile page** — no public profile exists yet

### Categories and Umbrellas
- [ ] **Replace placeholder category list** — once `docs/design/CATEGORIES.md` is finalized, update `backend/config/categories.py`
- [ ] **Democratic proposal system** — citizens propose new subcategories/umbrellas, communities vote to approve. Full design in `docs/design/PROPOSAL_SYSTEM.md`.
- [ ] **Similarity grouping for proposals** — AI flags duplicate proposals; users confirm or reject the merge

### Constitution Requirements
- [ ] **Merkle tree hashing** — `content_hash` column exists on Post and Solution but nothing populates it. Required by §5. Implement when AI labeling pipeline is considered complete.
- [ ] **Sorting algorithm documentation** — when feed algorithm is written, plain-English explanation must live right next to the code. Not in a separate doc. (§3)

---

## 🟠 Phase 3 — Advanced Platform Features

### Umbrella AI Agent System
Full design locked in `docs/design/AI_AGENT.md`. Build order:
- [ ] **UmbrellaAIAgent table** — one agent per umbrella. Fields: umbrella_issue_id, model_type, system_prompt, approval_rating, access_tier, lifetime_reward_score, total_actions_taken, created_at
- [ ] **AIAgentVote table** — community approval/disapproval votes on agents
- [ ] **AIAgentAction table** — permanent public transparency log of every agent action
- [ ] **Agent behavior implementation** — summarize solutions, flag duplicates, surface minority viewpoints
- [ ] **Access tier enforcement** — Full / Reduced / Minimal based on approval_rating

### Infrastructure
- [ ] **Redis token blacklist for logout** — POST /auth/logout currently just tells the client to delete the token. Determined users can reuse tokens up to 30 min. Fix: store invalidated tokens in Redis with TTL matching expiry.
- [ ] **Fix sys.path manipulation in labeler import** — `backend/routers/posts.py` uses sys.path hack to import `ai.labeler`. Clean solution: proper pyproject.toml package layout at repo root.

---

## 🔵 Phase 4 — Blockchain and Decentralization

- [ ] IPFS content storage for posts
- [ ] Polygon blockchain trust layer
- [ ] Web3 transparency layer for AI impact tracking
- [ ] Merkle tree hashing for post content (also listed in Phase 2 — can build the logic early, connect to chain here)

---

## 🧊 Backlog — Known Technical Debt

These are not urgent but must not be forgotten.

- [ ] **useRouter.refresh() on logout** — works correctly for now. Revisit if client state bugs appear.
- [ ] **httpx in Pipfile** — added for Ollama HTTP calls. Pipfile.lock updated. No action needed, just documented.
- [ ] **Test umbrella seeded via raw SQL** — "Road Damage and Pothole Repair" inserted directly. Will be replaced when the democratic proposal system is built.

---

*Last updated: Day 3 — reorganization session. Session log moved to HISTORY.md.*
