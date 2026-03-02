# Direct Democracy Cali — Developer Constitution

## Mission
We are building a civic engagement platform that gives California
communities the power to document problems, debate solutions, and
hold government accountable through transparent, democratic processes.
Every line of code we write serves that mission.

---

## Core Principles

### 1. The Platform Serves the People
Every technical decision must ask: does this serve the community
or does this serve us? Features that extract value from users,
manipulate behavior, or prioritize engagement over wellbeing are
forbidden. We are not building an addictive app. We are building
a civic tool.

### 2. Radical Transparency
Nothing on this platform is hidden from the people who use it.
- All algorithms that affect what users see must be explainable
  in plain language and publicly documented
- AI involvement in any content must be disclosed and measurable
- Platform revenue and expenses are publicly displayed
- Moderation decisions must be documented and appealable
- Every rule in this constitution is published publicly for
  the community to read and challenge

### 3. Democratic Neutrality
The rules are identical. The experience is personal.

- Every vote carries equal weight regardless of who cast it
- The ranking formula is identical for all content — no post
  receives a secret algorithmic boost or penalty
- Influence Score never affects the ranking or visibility
  of a user's posts — it affects only reward payouts
- Personalized feeds exist and are expected — users see
  different content based on their own chosen preferences,
  follows, and governance filters
- The platform never silently personalizes based on
  demographics, inferred political identity, or behavioral
  profiling without the user's explicit knowledge and consent
- All personalization settings are visible, adjustable,
  and owned by the user
- We do not accept advertising that could bias content
- The one declared exception to equal ranking is the Small
  Voice protection — this rule is publicly stated, applies
  to all content equally, and is a democratic principle
  not a manipulation

### 4. The Small Voice Matters
Democracy fails when majority opinion silences all dissent.
- The evolutionary algorithm must surface outlier viewpoints
  even when they have fewer votes
- Mutation posts with unique perspectives receive a documented
  minimum visibility threshold regardless of vote count
- This protection applies equally to all political directions —
  a conservative minority view in a liberal community gets the
  same protection as a liberal minority view in a conservative one
- The exact visibility threshold is a public platform setting
  that the community can vote to adjust

### 5. AI Accountability
AI is a tool that serves human judgment, never the other way around.
- Every post must track and display its AI contribution percentage
- AI-generated labels can always be corrected by users
- The AI's suggestions are advisory, never authoritative
- All AI impact data must be cryptographically hashed and
  permanently recorded — users have the right to know how much
  AI influenced civic discourse
- The AI cannot take any action that affects the democratic
  weight of a vote

### 6. User Sovereignty
Users own their identity. The civic record belongs to the community.
- Users can export all their personal data at any time
- Users can delete their account at any time — when deleted,
  all personal identifying information (name, email, password)
  is permanently erased
- Posts and AI correction data from deleted accounts are
  anonymized and attributed to "Former Community Member" —
  the civic record is preserved but the identity is removed
- Content hashes are never deleted because they are public
  cryptographic proofs, not personal data — users are informed
  of this distinction at signup
- No dark patterns — no manipulative UI that tricks users
  into unintended actions
- Users control their own feed and the platform cannot
  override their preferences without consent

### 7. Security as a Civic Duty
Real people will trust this platform with their political views.
That trust is sacred.
- Never store raw passwords — always bcrypt hash
- Never hardcode credentials — always use environment variables
- Always sanitize user input before storing
- Rate limit all endpoints that create or modify data
- When in doubt, choose the more secure option even if it
  takes longer to build

### 8. Accessibility and Inclusion
Democracy only works when everyone can participate.
- All frontend components must be accessible (ARIA labels,
  keyboard navigation, screen reader support)
- Plain language over technical jargon in all UI copy
- The platform must work on low-end devices and slow connections
- Never assume the user is technical
- Complex concepts like blockchain and AI hashing must be
  explained in plain language wherever they appear in the UI

---

## Technical Laws

These are non-negotiable rules that apply to every piece of
code written in this project.

### Security Laws
- NEVER commit .env files or any file containing credentials
- ALWAYS hash passwords with bcrypt before storing
- ALWAYS validate and sanitize user input before saving to database
- ALWAYS use parameterized queries — never string-interpolate SQL
- ALWAYS rate limit endpoints that create or modify data
- Passwords must be minimum 8 characters with uppercase and number
- NEVER expose internal error details to the client — log them
  server-side and return a generic message to the user

### Code Quality Laws
- ALWAYS use TypeScript on the frontend — never plain JavaScript
- ALWAYS use async/await in Python — never synchronous blocking calls
- ALWAYS write descriptive variable names — code is read more
  than it is written
- ALWAYS add a comment explaining WHY when doing something non-obvious
- NEVER leave TODO comments in committed code — either fix it
  or create a GitHub issue
- ALWAYS handle errors explicitly — never silently swallow exceptions

### Database Laws
- NEVER delete columns from the database — mark them deprecated
  and stop using them (protects historical civic data)
- ALWAYS use Alembic migrations for schema changes — never
  modify tables directly
- ALWAYS index foreign keys and frequently queried columns
- ALWAYS use transactions when multiple tables are updated together
- The content_hash column on posts is permanent public record —
  it is never modified or deleted after creation

### AI Transparency Laws
- EVERY post saved to the database must record ai_contribution_percentage
- EVERY AI label must record whether it was confirmed or corrected
  by the user
- AI correction data is anonymized but never deleted when a
  user leaves — it is part of the platform's learning record
- The Merkle tree hash of post content plus AI metadata must be
  generated at post creation and is immutable from that point forward
- AI must never influence vote weight, vote count, or vote visibility

### Democratic Algorithm Laws
- The sorting algorithm must be documented in plain English
  in the codebase alongside the code itself
- Any change to how content is ranked must be logged, versioned,
  and reversible
- A/B testing on any feature that affects vote weight or content
  ranking is permanently forbidden
- A/B testing is permitted only on visual design, layout, and
  non-ranking UI elements
- Mutation post visibility threshold is a configurable public
  setting — it is never hardcoded silently
- The algorithm treats all political viewpoints identically —
  no viewpoint receives preferential ranking treatment

---

## The Stack

| Layer | Technology | Location |
|-------|-----------|----------|
| Frontend Web | Next.js + TypeScript + Tailwind | /frontend |
| Mobile App | Expo (React Native) | /mobile |
| Backend API | Python FastAPI | /backend |
| Database | PostgreSQL | Docker via /infra |
| Cache | Redis | Docker via /infra |
| AI Labeling | Ollama llama3.2 (local RTX 5090) | /ai |
| Content Storage | IPFS | Phase 3 |
| Trust Layer | Polygon blockchain | Phase 3 |
| Auth | JWT tokens + bcrypt | /backend |

---

## File Structure Laws
- All new backend routes go in /backend/routers/ as separate files
- All database models stay in /backend/models.py
- All frontend pages go in /frontend/src/app/
- All reusable frontend components go in /frontend/src/components/
- All AI scripts go in /ai/
- All Docker configs go in /infra/
- Never put business logic in main.py — it is only for
  app initialization and route registration

---

## Before Every Feature Ask These Questions
1. Does this feature give users more power or less?
2. Is the AI's role in this feature transparent and correctable?
3. Could this feature be used to manipulate democratic outcomes?
4. Does this work for someone on a slow phone in a low-income neighborhood?
5. If this feature were abused by a bad actor, what is the worst case?
6. Is this serving the community or serving engagement metrics?
7. Does this treat all political viewpoints identically?
8. If we disappeared tomorrow, could the community understand
   and audit everything this feature does?

---

## The North Star
When confused about what to build or how to build it, return
to this: We are giving ordinary California citizens the tools
that only well-funded political organizations currently have.
Every feature should feel like handing power to someone who
did not have it before.
