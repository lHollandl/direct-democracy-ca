# PROJECT.md — Direct Democracy Cali

> Mission, scope, boundaries, and the parking lot. Read this first when
> reorienting. For principles and laws, see CLAUDE.md. For how the civic
> process works, see DEMOCRACY.md.
>
> Changes to this document require director approval.

---

## Mission

Direct Democracy Cali gives ordinary California citizens the tools that
only well-funded political organizations currently have: a place to
document problems in their community, workshop solutions with their
neighbors, vote on the solutions that earn broad agreement, and deliver
the result to the people who represent them — in a form those
representatives cannot ignore and cannot dispute.

The core insight: an extreme version of democracy would consume our
lives with meetings and review boards. But if everyone helps a tiny bit,
easily, from a phone, then everyone working together can solve the
common problems. The platform's job is to make that tiny bit of help
count.

The platform is the people's tool, not a separate thing. Its own
development is meant to be governed the same way — feature requests are
posts, and the developers work for the users. That self-governance is a
future phase; the mechanism it will use is the same one the platform
gives every community.

---

## What Success Looks Like

A resident of Vallejo opens the site on her phone. She posts a problem —
the intersection near the school has no crosswalk — and one solution.
The AI files it into the "Pedestrian Safety" umbrella for Vallejo, and
tells her so. Over the next weeks, other residents add solutions, amend
hers, and discuss. By the end of the month, two solutions in that
umbrella have broad enough support to qualify for the ballot; three
random residents check them over and let both through. Ballot week: 140
Vallejo residents vote. One solution passes 98–42. A results page is
published with a hash anyone can verify. She presses one button, and an
email with that page's link goes from her own address to every member of
the Vallejo city council. So do 60 others.

That is the full cycle. Demo 1 proves it end to end.

---

## The Two Halves

The project is built in two halves on two clocks (CLAUDE.md, "The Two
Halves of the Codebase"). This table is the authoritative assignment.

| Foundation — built once, kept, full rigor | Iteration — rebuilt per demo until a keeper |
|---|---|
| Infrastructure: Docker, Postgres, Redis, configuration, logging | Posts, problems, solutions, versions, amendments, comments |
| Accounts: signup, login, JWT + refresh tokens, password reset, email verification | Umbrellas and the umbrella page |
| Identity: real name, display settings, anonymity | AI labeling and correction |
| Verification levels and everything built on them | Feed |
| User rights: data export, account deletion and anonymization | Votes on workshop items; net score; statuses |
| Legal: privacy policy, terms of service, cookie consent, terms versioning | Similarity grouping of amendments |
| Outbound email (verification and reset only) | Jury: draw, review, hold-back |
| California geography: state, counties, cities | Ballot: cycle, items, yes/no votes, results |
| Officials directory (schema and seed) | Summary document: generation, hashing, public pages, PDF export |
| Admin role and admin action log | Director controls for the cycle |
| Settings table and the public settings page | References: user-added and AI-recommended |
| AI action log (table) | AI influence display |
| Deployment (deferred) | All UI for the above |

Iteration code may read Foundation tables but never migrates them.
Foundation prompts never touch Iteration tables. DATABASE.md records
the split table by table.

---

## Demo 1 — Scope

Demo 1 is the first full-cycle build. It runs locally, on the director's
machine, with a handful of test accounts. It is a throwaway on the
Iteration side and a first real version on the Foundation side.

### In scope

**Foundation**
- Docker Compose: Postgres, Redis. Fresh secrets.
- FastAPI backend on async SQLAlchemy + asyncpg. Alembic from a fresh
  initial migration for Foundation tables.
- Signup: email, password, real name, display name, date of birth, city,
  county, gender, political party, terms agreement with version. Email
  verification required before any write action. Verification level
  starts at `unverified`.
- Login, logout, refresh tokens, password reset by email.
- Display settings: show real name / show display name / anonymous.
- Data export (JSON) and account deletion with anonymization
  ("Former Community Member").
- Privacy policy, terms of service, cookie consent — placeholder legal
  text clearly marked as draft.
- Geography seed: California, all 58 counties, all incorporated cities.
- Officials directory table, seeded with the director's test address
  for every office in the test communities.
- Settings table with every value DEMOCRACY.md names, and a public page
  that displays them.
- Admin flag on users; admin action log.
- AI action log table.

**Iteration**
- Everything in DEMOCRACY.md marked "Demo 1".
- Umbrellas seeded from `backend/config/seed_umbrellas.yaml` for the
  test communities.
- The full cycle, driven by director controls: workshop → prepare ballot
  → jury → ballot open → ballot close → summary published → send button.

### Out of scope for Demo 1

Named here so nothing is built by accident. Each has a home below.

- The democratic proposal system (new categories and umbrellas). Post
  creation offers "let AI decide" and "pick an existing umbrella"; the
  third option, "propose a new one," is Demo 2. → Parking lot, Proposal
  system.
- Smart feed, clusters, Small Voice. → Parking lot.
- Any verification method beyond `unverified`. → Parking lot,
  Verification.
- Real representative addresses. → Parking lot, Delivery.
- Reputation points, influence score. → Parking lot.
- AI writing assist on the post form (AI influence reads 0%). → Parking
  lot.
- Federal governance level. → Parking lot.
- Platform self-governance community. → Parking lot.
- Umbrella AI Agents. → Parking lot.
- Mobile app, IPFS, blockchain. → Parking lot.
- Hosting and HTTPS. → Parking lot, Deployment.

---

## Boundaries — What This Project Is Not

- **Not a social network.** No follows, no likes for their own sake, no
  feed tuned for time-on-site. Every interaction exists to move a
  problem toward a solution.
- **Not a petition site.** A petition is a complaint with signatures.
  Here, nothing can be posted without a proposed solution, and nothing
  reaches a representative until a community has voted on it.
- **Not a government system.** The platform has no authority. Its
  output is a document and the pressure of the people who send it.
- **Not a polling company.** The platform does not claim its votes are
  representative. It reports exactly who voted, at what verification
  level, and lets the reader judge.
- **Not an AI product.** AI sorts, suggests, and recommends, and is
  labeled every time it does. The people decide.

---

## Working Principles

**The documents are the build.** Claude Code builds each demo from
these documents in long unattended runs. What is vague in the documents
will be decided by Claude Code, and discovered afterwards. Precision
here is cheaper than surprise later.

**Every demo teaches; only keepers are kept.** A demo is used, audited,
and its lessons written into the documents. The next demo is built
from the improved documents, not from the previous code. When a demo is
good enough that its data is worth keeping, the director declares it
the keeper, and Iteration comes under full rigor.

**Audit runs are separate from build runs.** After every long run, a
fresh Claude Code session reads the documents and the code and reports
every discrepancy, security issue, and constitutional violation without
fixing anything. Fixes come in a following run. AUDIT.md defines the
procedure.

**The sandbox is the safety model.** Every run happens inside a Docker
Sandbox microVM with its own Docker daemon, its own copy of the trial
branch, a scoped GitHub credential that cannot reach `main`, and
network access only to the host's Ollama, Anthropic's API, and the
package registries. Claude Code can build anything inside a trial and
cannot touch anything outside it. SANDBOX.md defines the setup.

**One branch per trial.** `demo/NN` is branched from `main`, checked
out as a git worktree into its own directory, built in its own sandbox.
Foundation improvements merge to `main` by pull request. Demo branches
never merge unless declared a keeper.

**The director's time is the constraint.** Claude Code's runtime is
cheap; the director's attention is not. Documents, briefs, and audits
are all designed so the director reads a summary and makes a decision,
rather than reading code.

---

## Hardware

Director's workstation: Ubuntu, RTX 5090, Threadripper 7970X, 96 GB
RAM. Ollama runs on the host GPU and is reached from the sandbox over
the network. No cloud inference.

---

## Parking Lot

Ideas recorded so they are not lost. Not scheduled. Each entry says
what it is and what it depends on.

### Proposal system (Demo 2 candidate)
Citizens propose new umbrellas under an existing main category, or new
main categories. Governance-level thresholds (city 2% / 50, county 1.5%
/ 100, state 1% / 500, federal 0.5% / 1,000, whichever lower), 7-day
minimum window, 30-day dormancy, revivable. AI flags similar pending
proposals; humans confirm merges. On approval the labeler starts routing
to it. Launched inline from the post form ("Option C") without blocking
the post. Full design in HISTORY 2026 (Day 3 — Design Session 1). Open:
whether dormant proposals can be re-proposed; what happens to posts
under a rejected umbrella.

### Verification
Ways to establish that a voter is a California resident: phone (SMS),
mailed postcard with a code, voter-file matching (registered California
voters; legal terms to check), third-party ID verification (strong, but
hands IDs to a vendor). Each becomes a new verification level. Never
weights a vote; always disclosed in aggregate. Research item: watch for
new approaches.

### Smart feed and clusters
HOPES §5: users see more from people whose problems and solutions they
upvote; random "shortcuts" mix in posts from unlike-minded people to
build connections between clusters. Constitutional only as opt-in,
visible, user-adjustable personalization (CLAUDE §3). Design after two
demos of use. Must be documented beside the code with a version.

### Small Voice
CLAUDE §4 promises a visibility floor for minority viewpoints. Routes:
(a) score-based — the lowest-scored N solutions in an umbrella rotate
through a guaranteed slot in the visible section; (b) embedding-based —
cluster solutions by meaning and guarantee each cluster a representative.
Start with (a). Demo 1 shows all solutions, so the floor is trivially
met.

### Delivery
Officials directory populated with real mayors, councils, supervisors,
and state legislators per community; user-correctable through the
proposal-and-confirm pattern. Platform still sends nothing itself. Terms
of service must cover the user-send flow. Postal mail export of the PDF.

### Political party pages
Provide users with a dedicated page for their political party. Their party
page will display posts from other users who identify with that party. The 
party page will all those users to collaborate on those posts with like 
minded people to develop solutions. The party page will allow for filtering
based on governance level (city, county, state, federal). New political 
parties should be easy to start, allowing for people to organize and develop 
new ideas. This will also allow political parties to present solutions that
were largely worked on by those party members. Similar to how government 
currently works. Just made easier for regular people. 


### Reputation and influence score
Cosmetic only, never affects ranking (CLAUDE §3). Time-decay points for
early supporters of proposals that pass (100 / 70 / 30 / 5 by day;
founder bonus; 0 for failed). `influence_score` column exists and is
unused. Open: what else earns it; what it displays.

### AI writing assist
One button on the post form: "improve my writing," Ollama, before/after
diff. Makes `ai_contribution_percentage` non-zero and real. Small;
schedule when the post form stabilizes.

### Umbrella AI Agents (Phase 3 design, locked)
One agent per umbrella; community approval rating; access tiers Full
(>60%) / Reduced (30–60%) / Minimal (<30%, observes only); demoted
agents can earn back; every action logged; `model_type` as a string;
reward on government deployment; high-performing agents' history becomes
fine-tuning data. This is where HOPES' "AI solution" for each umbrella
lives — the agent summarizes and merges, humans vote. Open: tier
thresholds; how the community amends an agent's prompt; what counts as
"deployed by government"; visibility of a suspended agent's past.

### California AI model
A model fine-tuned on California civic history and problems, trained on
platform data with full training-data documentation, reproducible
runs, several base models, and community-visible competition between
them. Depends on the agents and on data. From docs/design/
GENERALNOTES.md.

### Embedding-based sub-grouping
Within an umbrella, group posts and solutions by meaning using
embeddings, so that "potholes on Main St" and "potholes on 5th" cluster
without becoming separate umbrellas. Reuses the similarity machinery.
From GENERALNOTES.md.

### Platform self-governance
A "Platform" community alongside city/county/state with the same
umbrellas, workshop, and ballot. Feature requests are posts; the
director is the representative. HOPES §7. Depends on nothing but
priority.

### Federal governance level
Exists as an enum value with no entity behind it. Needs a US entity, a
federal officials directory, and thresholds. Deferred.

### Provably random jury draw
Seed the draw from the previous cycle's summary hash with a published
algorithm, so anyone can re-run it. Demo 1 logs the draw instead.

### Deployment
Friends beta. Options: home machine + tunnel (Cloudflare Tunnel or
Tailscale — free, keeps the GPU local, machine must stay on); small VPS
with AI calling home. Needs HTTPS, an invite gate, and the legal pages
in final form. Decide after two demos.

### Follow-through obligation
HOPES §6: cap concurrent involvement to discourage post-and-vanish. In
tension with "everyone helps a tiny bit." Not designed. May be
unnecessary once the workshop exists.

### Content and trust layers
IPFS content storage; Polygon trust layer; Merkle proofs on chain. The
`content_hash` column is the bridge. Phase 4.

### Links and art
HOPES §10: links to useful civic sites (e.g. AP tracker); art and
photography on the site. Style brief handles the second; the first is a
Platform-community post.

### Retired documents
HOPES.md, DirectDemocracyCali_ProjectSummary_v2.md, and the pre-
2026-09-05 docs/design/ files are archived in `archive/`. This document
and DEMOCRACY.md supersede them.
