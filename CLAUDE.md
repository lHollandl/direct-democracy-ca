# CLAUDE.md — Direct Democracy Cali Constitution

> This document is the constitution. It holds the principles and universal
> laws that govern every design decision and every line of code.
>
> Constitutional principles are stable. They are not revised casually. Any
> change to this document requires explicit director approval.
>
> When CLAUDE.md and any other document conflict, CLAUDE.md wins. The
> other document is corrected.
>
> Read this first when reorienting on the project.

---

## The Mission

Direct Democracy Cali is a civic engagement platform that gives ordinary
California citizens the tools that only well-funded political
organizations currently have. Citizens document problems in their
communities, workshop solutions together, vote on the solutions that
earn broad agreement, and deliver the results to the people who
represent them.

The platform is built to maximize democratic output, not engagement:
real problems documented, real solutions debated, real pressure applied
to the right level of government. Where those two goals conflict, the
platform chooses democracy.

For the current scope, see PROJECT.md. For how a problem becomes
pressure, see DEMOCRACY.md.

---

## The Principles

**1. The platform serves the people.**
Every technical decision must ask: does this serve the community or
does this serve us? Features that extract value from users, manipulate
behavior, or prioritize engagement over wellbeing are forbidden. We are
not building an addictive app. We are building a civic tool. When in
doubt, build the version that gives the citizen more power.

**2. Radical transparency.**
Nothing on this platform is hidden from the people who use it. Every
algorithm that affects what users see is explainable in plain language
and publicly documented. Every AI action is disclosed and logged. Every
threshold, rule, and setting that shapes a democratic outcome is a
public value, printed wherever it is applied. Platform revenue and
expenses are publicly displayed. Moderation decisions are documented
and appealable. This constitution is published for the community to
read and challenge.

Transparency includes transparency about weakness. Where the platform
cannot verify something — that a voter is a resident, that text was
written without outside AI — it says so plainly rather than implying a
certainty it does not have.

**3. Democratic neutrality.**
The rules are identical. The experience is personal.

- Every vote carries equal weight regardless of who cast it. Account
  verification level is disclosed in aggregate and never used to weight
  a vote.
- The ranking formula is identical for all content. No post, solution,
  or comment receives a secret boost or penalty.
- Personalized feeds exist and are expected — users see different
  content based on their own chosen preferences, follows, and
  governance filters. All personalization settings are visible,
  adjustable, and owned by the user.
- The platform never personalizes based on demographics, inferred
  political identity, or behavioral profiling without the user's
  explicit knowledge and consent. Gender and political party are
  collected for aggregate public reporting only; they never influence
  what any individual sees.
- We do not accept advertising that could bias content.
- The one declared exception to equal ranking is the Small Voice
  protection (Principle 4). It is publicly stated and applies to all
  content equally.

**4. The Small Voice matters.**
Democracy fails when majority opinion silences all dissent. Minority
viewpoints receive a documented minimum visibility regardless of vote
count. This protection applies equally to all political directions — a
conservative minority in a liberal community gets the same protection
as a liberal minority in a conservative one. The exact visibility rule
is a public platform setting that the community can vote to adjust.
Downvotes lower a ranking; they never hide content.

**5. AI accountability.**
AI is a tool that serves human judgment, never the other way around.

- AI sorts, suggests, summarizes, and recommends. It never decides.
  AI never creates a category or umbrella, never casts or weights a
  vote, never advances a solution through any threshold, and never
  takes an action that affects the democratic weight of anything.
- Every AI action is labeled where it appears and recorded in a
  permanent public log: what acted, on what, when, and with what
  result.
- Every post and solution displays its AI-influence figure, defined in
  DEMOCRACY.md as the share of its text produced by AI the platform
  provided. Every umbrella displays the list of AI actions taken on it.
- AI-generated labels and suggestions can always be corrected by users,
  and every correction is recorded.
- AI impact data is cryptographically hashed and permanently recorded.
  Users have the right to know how much AI influenced civic discourse.

**6. User sovereignty.**
Users own their identity. The civic record belongs to the community.

- Real name is collected at signup for integrity. Users control what is
  shown publicly, including full anonymity. The public display is a
  setting, not an account type.
- Users can export all their personal data at any time.
- Users can delete their account at any time. All personal identifying
  information — name, email, password, location — is permanently
  erased. Posts, solutions, comments, votes, and AI-correction data are
  anonymized and attributed to "Former Community Member." The civic
  record is preserved; the identity is removed.
- Content hashes are never deleted. They are public cryptographic
  proofs, not personal data. Users are told this at signup.
- Solutions are community-owned once posted. Authorship is recorded;
  control is not retained.
- No dark patterns. Users control their own feed, and the platform
  cannot override their preferences without consent.

**7. Security as a civic duty.**
Real people will trust this platform with their political views. That
trust is sacred. Never store raw passwords. Never hardcode credentials.
Always sanitize input. Rate limit every write. When in doubt, choose
the more secure option even if it takes longer to build.

**8. Accessibility and inclusion.**
Democracy only works when everyone can participate. Every component is
accessible — ARIA labels, keyboard navigation, screen readers. Plain
language over jargon in all UI copy. The platform works on low-end
devices and slow connections, and every page works with images off.
Never assume the user is technical. Complex concepts — hashing, AI
influence, verification levels — are explained in plain language
wherever they appear.

---

## The Two Halves of the Codebase

The project is built in two halves that move on different clocks.
Every prompt states which half it belongs to.

**Foundation** is built once, kept, and evolved carefully. It holds
everything a real person trusts the platform with: infrastructure,
accounts, authentication, verification, user rights, legal pages,
email, geography, and deployment. Foundation is under full rigor from
the day this constitution is adopted: numbered immutable migrations,
pre-checks before every edit, evidence pasted for every claim.

**Iteration** is the civic machinery — posts, umbrellas, the workshop,
the jury, the ballot, the summary document, and all of their UI. It is
rebuilt freely, demo after demo, and each rebuild starts from the
documents rather than the previous code. Iteration schema is
regenerated fresh for each demo. When a demo build becomes worth
keeping, the director declares it the **keeper**, and from that build
onward Iteration is under the same rigor as Foundation.

The boundary rule: Iteration code may read Foundation tables but never
migrates them. Foundation prompts never touch Iteration tables. The
two halves share one repository and one database, and the split is
recorded table by table in DATABASE.md.

---

## The Universal Laws

The principles are the values. The laws are the operational rules that
follow from them. They apply to every line of code in the project.

**1. Every post has a solution.** A post cannot be saved without at
least one solution. Citizens propose what they want done; they do not
only complain. This is enforced in the application and reflected in
the schema.

**2. Schema changes are Alembic migrations.** Every change to the
database is a migration file, applied in order. No ad-hoc
`ALTER TABLE`, no `create_all` outside a test. Foundation migrations
are immutable once applied. Iteration migrations are immutable from
the keeper build onward.

**3. Columns are deprecated, never deleted.** Applies to every table
under rigor. A deprecated column is commented as such in `models.py`
and no new code writes to it. This protects historical civic data.

**4. Foreign keys and queried columns are indexed.** Always.

**5. Multi-table writes are transactions.** Always.

**6. `content_hash` is permanent.** Generated at creation for every
post, solution, and summary document from the content plus its AI
metadata. Never modified or deleted afterward.

**7. Every AI action is a row.** Labels, recommendations, groupings,
summaries — each one is recorded before its result is shown, with
model, input, output, and whether a user later confirmed or corrected
it. AI prompts are files under `ai/prompts/`, never strings in Python.

**8. Thresholds and rules are public settings.** Every number that
decides a democratic status — dominant, absorbed, qualified, active
user, jury size, ballot window — lives in the settings table, is
displayed on a public page, and is printed in every summary document
it produced. Never a constant in code. Any change is logged and
versioned.

**9. Ranking is documented beside the code.** Every ordering rule has
a plain-English explanation in the same file as the code, and a
version number. A/B testing on anything that affects ranking or vote
weight is permanently forbidden; on visual design and layout it is
permitted.

**10. Configuration is centralized.** Ports, URLs, model names,
secrets, and anything that differs between machines live in `.env` and
are read through `backend/config/`. No module reads the environment
directly. No `.env` file is ever committed.

**11. Async all the way down.** Every IO operation is `async`.
Database access is through SQLAlchemy's async session on asyncpg;
HTTP through httpx's async client. No blocking calls inside `async`
code.

**12. Errors are explicit.** Never swallowed, never exposed. Caught
where they can be handled, logged server-side with full detail,
returned to the client as a generic message. No `except: pass`. No
`TODO` or `FIXME` in committed code — open items belong in TODO.md.

**13. Input is validated and parameterized.** Every request body is a
Pydantic model. Every query is parameterized. Passwords are bcrypt
hashed, minimum 8 characters with an uppercase letter and a number.
Every endpoint that creates or modifies data is rate limited.

**14. The backend is independent of the frontend.** Every action is
invocable from the API alone. The UI is a view onto the backend and
never a venue for business logic. The frontend is TypeScript, always.

---

## The Stack

| Layer | Technology | Location |
|---|---|---|
| Frontend | Next.js + TypeScript + Tailwind | `/frontend` |
| Backend API | Python FastAPI, async SQLAlchemy | `/backend` |
| Database | PostgreSQL | Docker via `/infra` |
| Cache | Redis | Docker via `/infra` |
| Migrations | Alembic | `/backend/alembic` |
| Auth | JWT + refresh tokens + bcrypt | `/backend` |
| AI labeling and recommendation | Ollama on the local GPU | `/ai` |
| AI reference search | Web search API (provider is configuration) | `/ai` |
| Mobile | Expo (React Native) | Deferred |
| Content storage / trust layer | IPFS, Polygon | Deferred |

File structure: routes in `/backend/routers/`, models in
`/backend/models.py`, configuration in `/backend/config/`, AI code and
prompt files in `/ai/`, pages in `/frontend/src/app/`, components in
`/frontend/src/components/`, Docker in `/infra/`. `main.py` is for app
initialization and route registration only.

---

## Before Every Feature

1. Does this give users more power or less?
2. Is the AI's role transparent and correctable?
3. Could this be used to manipulate a democratic outcome?
4. Does this work on a slow phone in a low-income neighborhood?
5. If a bad actor abused this, what is the worst case?
6. Is this serving the community or an engagement metric?
7. Does this treat every political viewpoint identically?
8. If we disappeared tomorrow, could the community understand and audit
   everything this does?

---

## The Document Map

Seven documents define this project. Each has a single job. They do not
overlap.

| Document | Scope | Edit cadence | Approval |
|---|---|---|---|
| **CLAUDE.md** | Constitution. Principles and laws. | Rare. | Director required. |
| **PROJECT.md** | Mission, scope, the parking lot. | When scope changes. | Director required. |
| **DEMOCRACY.md** | The civic process. How a problem becomes pressure: umbrellas, workshop, thresholds, jury, ballot, summary document, AI roles. | When the process changes. | Director for process philosophy. |
| **ARCHITECTURE.md** | Backend shape, layer boundaries, external services. | When the durable layer evolves. | Director for design philosophy. |
| **DATABASE.md** | Schema, the Foundation/Iteration split, migration practice. | When schema evolves. | Director for design philosophy. |
| **TODO.md** | Phase-aligned task tracker and technical debt. | Per session. | Routine. |
| **HISTORY.md** | Append-only session log. | Per session. | Append-only — no edits. |

Plus **archive/** — superseded documents kept for reference, not
authoritative. `HOPES.md`, `DirectDemocracyCali_ProjectSummary_v2.md`,
and the pre-2026-09-05 `docs/design/` files live there once PROJECT.md
and DEMOCRACY.md have absorbed them.

---

## How HISTORY.md Works

HISTORY.md is the project's running journal. TODO holds the checklist
of what is to be done; HISTORY holds the narrative of what was decided,
encountered, and learned. Both Claude.ai planning sessions and Claude
Code build sessions produce entries. Build sessions are where the
highest-value detail lives — bugs, surprises, rejected approaches.

Every entry records, where applicable: completed work with paths and
function names; decisions made that the documents did not pre-resolve,
with rationale; issues encountered and how they were resolved;
deviations from the prompt and why; document changes flagged; open
follow-ups.

```
## YYYY-MM-DD — Session M (which half — Foundation or Iteration)

**Completed:**
**Decisions made:**
**Issues encountered:**
**Notes:**
**Document changes flagged:**
```

Sections with nothing to record are omitted.

Rules: append-only, never edit a past entry — a reversal is recorded in
the current entry. One entry per session. The director provides the
date; the session uses it as-is. The session drafts its own entry at the
end of its work; the director reviews and accepts it. The last two
entries are read at the start of every session.

---

## Session Law

At the start of every session:
1. Read CLAUDE.md fully.
2. Read TODO.md fully — the Current Status Snapshot says what state the
   project is actually in.
3. Read the last two entries of HISTORY.md.
4. Read the sections of PROJECT.md, DEMOCRACY.md, ARCHITECTURE.md, and
   DATABASE.md relevant to the task.
5. Confirm current status against the actual files before writing any
   code.

At the end of every completed prompt:
1. Update TODO.md — mark completed items, update the snapshot, record
   new technical debt.
2. Append the HISTORY.md entry.
3. Do not edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, ARCHITECTURE.md, or
   DATABASE.md unless the prompt explicitly asks. Flag needed changes in
   HISTORY.md instead.

---

## Editing This Document

CLAUDE.md changes only with explicit director approval. The proposed
change is described in a planning session; the director approves the
exact wording, requests revisions, or declines; only then does the
document change, and the change is recorded in HISTORY.md with its
rationale. If the change is structural — a new principle, a removed
law, a renumbering — every referring document is updated to match.
Typo fixes that don't change meaning may be made without ceremony but
are still noted in HISTORY.md.

---

## The North Star

When confused about what to build or how to build it, return to this:
we are giving ordinary California citizens the tools that only
well-funded political organizations currently have. Every feature
should feel like handing power to someone who did not have it before.
