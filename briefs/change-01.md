# Build Brief — change/01-site-shell

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — change-01 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is **change/01**, the
first change under the new method: `main` is the only long-lived branch,
every change is built on its own short-lived branch, and **the documents
change in the same run as the code**, so the branch always describes
itself. Both halves are touched; Foundation items are under full rigor.

Your branch is `change/01-site-shell`: run `git fetch origin && git
switch change/01-site-shell && git merge --ff-only
origin/change/01-site-shell`, then `git log --oneline -3`. The newest
commit must be the director's "change/01 brief, seed umbrellas, test
dataset". You cannot push to `main` and must not try.

**Documents.** Part A gives director-approved wording. Apply it
**verbatim**: where it gives replacement text, use it character for
character; where it says "add", place it where indicated. Do not
improve, reflow, or reword anything else in those files. If an anchor is
not found exactly, stop that item, report the file and anchor in
HISTORY.md, and continue. Outside Part A you may not edit CLAUDE.md,
PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md, AUDIT.md, or
SANDBOX.md.

**Silence and conflict.** Where this brief and a document disagree after
Part A is applied, CLAUDE.md wins, then this brief, then the document.
Where everything is silent, choose the smallest thing that satisfies the
constitution and record the choice under "Decisions made" in HISTORY.md.

## Read first, in this order

1. `CLAUDE.md`, in full.
2. This brief, in full, **then apply Part A before writing any code.**
3. `DEMOCRACY.md` §1, §2.3, §4.1, §7, §8, §10, §12, §13, §14 (as amended).
4. `ARCHITECTURE.md` §2, §3, §4, §6, §9, §10; `DATABASE.md` §2, §4.3, §4.4, §4.12, §4.14, §4.17, §6.
5. `AUDIT.md` §4.1 (the traps) and `HISTORY.md`, the last two entries.
6. `TODO.md`.

## Step 0 — Pre-checks (paste the output of each; stop if any fails)

1. `git branch --show-current`; `git log --oneline -3`.
2. `ls backend/config/test_dataset.yaml backend/config/seed_umbrellas.yaml` — both present; `grep -c 'community:' backend/config/seed_umbrellas.yaml` prints 16.
3. `.env` from `.env.example` with `OLLAMA_BASE_URL` set to the host LAN address (SANDBOX.md §5); `curl -sS $OLLAMA_BASE_URL/api/tags` lists `OLLAMA_MODEL` and `EMBED_MODEL`.
4. `docker compose --env-file .env -f infra/docker-compose.yml up -d`; `docker compose ps`.
5. Full test suite green **before** any change. Paste the summary line.

---

## Part A — Document changes (apply first, one commit: "change/01 documents")

### A1. The name — every document and the whole codebase

The platform is **Direct Democracy CA**. Replace every occurrence of
`Direct Democracy Cali` (any capitalisation) with `Direct Democracy CA`
in every tracked file **except** `HISTORY.md`, `audits/`, `briefs/`, and
`archive/`, which are historical records. In CLAUDE.md this is a
name-only edit. Proof: `git grep -il 'democracy cali'` lists only paths
under those four exceptions.

### A2. CLAUDE.md — "The Two Halves of the Codebase" (director-approved 2026-09-19)

**Replace** the paragraph beginning `**Iteration** is the civic machinery` with:

```
**Iteration** is the civic machinery — posts, umbrellas, the workshop,
the jury, the ballot, the summary document, and all of their UI. It is
improved continuously, never rebuilt: every change starts from `main`,
is built on its own short-lived branch, and returns to `main` together
with the documents that describe it, so the documents and the code
beside them always agree. Until the keeper, Iteration **data** is
disposable: the Iteration schema and database may be regenerated
whenever a change needs it. When the data becomes worth keeping, the
director declares the **keeper**, and from that point onward Iteration
is under the same rigor as Foundation.
```

### A3. PROJECT.md (director-approved 2026-09-19)

**Replace** the table header cell `Iteration — rebuilt per demo until a keeper` with
`Iteration — improved change by change; data disposable until the keeper`.

**Replace** the paragraph beginning `**Every demo teaches; only keepers are kept.**` with:

```
**Every change teaches; `main` keeps what passes.** The director uses
the site, and what it teaches becomes a change: one brief that carries
both the code revision and the exact document wording, run on its own
branch. A change the director likes is audited and merged; one the
director does not like is deleted, code and document edits together. A
demo is a tag on `main` (`demo-1`, `demo-2`, …), a named point the
director can always return to. When the data is worth keeping, the
director declares the keeper, the Iteration schema freezes, and
Iteration comes under full rigor.
```

**Replace** the paragraph beginning `**One branch per trial.**` with:

```
**`main` is the only long-lived branch.** It always holds the newest
audited code and the documents that describe it. Every change is a
`change/NN-short-name` branch cut from `main`, built in its own sandbox
with its own clone and its own database, and either merged back by pull
request after its audit or deleted. No branch outlives its change.
`demo/01` was the last trial branch; it merged whole on 2026-09-19 and
is tagged `demo-1`. Foundation changes follow the same path under full
rigor.
```

**In "Out of scope for Demo 1"**, replace the bullet beginning `- The democratic proposal system` with:

```
- The democratic proposal system (new categories and umbrellas). Post
  creation offers "let AI decide" and "pick an existing umbrella". The
  director decided on 2026-09-19 that "propose a new umbrella" comes out
  of the parking lot: without it, a resident of any community with no
  umbrellas can post but never reach a workshop. It is designed and built
  as its own change. → Parking lot, Proposal system, until then.
```

**In the Parking Lot**, add at the end:

```
### A name for posts
The third tab reads "New post" for now. The director wants a word of the
platform's own for a post, the way other platforms named theirs. Not
chosen.
```

### A4. DEMOCRACY.md

**§7.4** — add a row after `ballot_window_days`:

```
| `cycle_open_rule` | §10.1 — the calendar rule for when a community's ballot is expected to open | `first_sunday_of_month` (manual in Demo 1) |
```

**§10.1** — add after the paragraph ending `but do not fire.`:

```
**The rhythm.** A community's ballot is expected to open on the dates
given by `cycle_open_rule`. One rule exists: `first_sunday_of_month` —
the first Sunday of each calendar month, at the start of the day,
Pacific time (`America/Los_Angeles`). From it the platform computes two
dates per community and shows them on Home (§12.2): **next ballot
expected** — the first rule date on or after today on which the
community has not already opened a cycle; and **next jury draw
expected** — that date minus `jury_review_days`. They are expectations
and are always displayed with the word "expected": while transitions
are director controls nothing fires on these dates, and the page says
"During the demo, ballots are opened by the administrator." The
computation is `backend/services/rules.py::next_cycle_dates`, with its
plain-English explanation beside it. A value other than a known rule is
refused when the setting is changed.
```

**§4.1** — replace the sentence beginning `A post is saved immediately.` through `until it\nsucceeds.` with:

```
A post is saved immediately. Labeling runs in the background; until it
completes the post shows "Being filed — the AI is reading this now" and
appears in no umbrella. If labeling fails, the post is marked
`unlabeled`, shows "Not filed yet — the AI could not be reached. The
platform tries again every N minutes" (N = `label_retry_minutes`, Demo
1: 10), and is retried by a background job on that interval until it
succeeds. A `needs_review` post-community shows "Not filed — no umbrella
in <community> covers this yet. It is saved under <main category>."
When that community has no active umbrella at all, the "Is that the
right place?" control is replaced by "There are no umbrellas in
<community> yet. Proposing a new umbrella is planned." The three states
never share a sentence (CLAUDE §2, transparency about weakness).
```

**§12** — replace the whole section (heading through the paragraph ending `and the version increments.`) with:

```
## 12. Home

### 12.1 The feed

`/home` lists posts. **Scope:** by default the viewer's home
communities; the community filter narrows to one of them or widens to
"All of California" (users may read any community, §2.3); a signed-out
visitor sees all. The main-category filter is unchanged.

**Search.** `q` (2–100 characters) keeps only posts whose problem text,
or any of whose solution texts, match, using PostgreSQL full-text search
(`websearch_to_tsquery('english', q)`). Search filters; it never orders.
No AI is involved.

**Sort** — chosen by the user; the default is `newest`:

| Sort | Order |
|---|---|
| `newest` | `created_at` descending |
| `oldest` | `created_at` ascending |
| `most_votes` | votes(post) descending, then newest. votes(post) = the number of `votes` rows, up and down alike, whose target is a solution with that `post_id` |
| `most_comments` | comments(post) descending, then newest. comments(post) = the number of comments, not removed, whose target is one of those solutions |

Every card shows both counts, so the order can be checked by eye. The
page states the rule in force in one sentence (for example: "Most votes
first — the number of up and down votes on each post's solutions.
Nothing else affects the order."). There is no blended score, no
recency decay, and nothing personal beyond the viewer's own filter and
sort choices (CLAUDE §3). Version `feed-v1`; the explanation for each
sort lives beside the code in `backend/services/rules.py` (Law 9).

### 12.2 Ballot and jury on Home

Above the feed, a signed-in user sees two panels, each with one line per
home community, from `GET /cycles/mine`:

- **Ballot.** Cycle `open`: "Open — expected to close <opened_at +
  ballot_window_days>". Otherwise: "Next ballot expected <date>" (§10.1)
  and, when one exists, "Last ballot closed <date>". A button opens
  `/ballot`.
- **Jury.** "Last jury drawn <date>" or "No jury has been drawn yet";
  "Next draw expected <date>"; and the viewer's own status in the
  current cycle — not drawn, drawn and awaiting a reply (with the
  reply-by date), seated, declined, or no response. Shown only to the
  viewer; juror identities stay non-public (§8.5). A button opens
  `/jury`.

`/ballot` and `/jury` each carry a button, "How the ballot works" and
"How the jury works", that opens a plain-language explanation of what
the feature is, why it exists, and how it runs. Every number in those
explanations is read from the public settings at display time, never
typed into the text (Law 8).

**Ballot items on Home.** While a home community's ballot is open, its
items appear in a block pinned above the posts, "On your ballot now",
each with its frozen text and the same yes/no control as `/ballot`. The
block is pinned, never interleaved with posts, so the feed keeps exactly
one ordering rule. A switch, "Show ballot items here", is on by default,
belongs to the user, and is remembered in the browser; account-level
storage of Home preferences is a later change.

The smart feed is parked (PROJECT.md).
```

**§14** — replace the row beginning `| §3 identical ranking |` with:

```
| §3 identical ranking | §3.3 item 4 ordering; §12.1 feed-v1 — four sorts, each a plain count or a date, identical for every viewer who chooses it |
```

and replace the row beginning `| §4 minimum visibility for minority views |` with:

```
| §4 minimum visibility for minority views | The default view of Home is newest-first, which ranks nothing out of sight, and §3.3 item 4 shows every solution. `most_votes` and `most_comments` are views a user chooses for themselves and leaves with one click; they count up and down votes alike, so a downvoted post is not pushed down by its downvotes. The visibility rule and its §7.4 setting are owed the day the platform — rather than the user — chooses any ranking (PROJECT.md parking lot, Small Voice). Director's reading, 2026-09-19 |
```

### A5. DATABASE.md

**§2 table** — in the Iteration row, replace `Regenerated fresh per demo until the keeper.` with
`Until the keeper, regenerated as a single initial migration whenever a change alters the Iteration schema; the database is rebuilt from empty.`

**§4.3** — add after the table's index sentence (or, if none, after the table):
`GIN index on to_tsvector('english', problem_text) — Home search (DEMOCRACY §12.1).`

**§4.4** — likewise: `GIN index on to_tsvector('english', text) — Home search (DEMOCRACY §12.1).`

### A6. ARCHITECTURE.md

**§3 table** — add rows after `CORS_ORIGINS`:

```
| `NEXT_PUBLIC_API_BASE_URL` | the address the **browser** uses for the API. It must share its host name with `PUBLIC_BASE_URL` (both `localhost`, or both the same domain): the refresh cookie is `SameSite=Strict`, and a browser on `localhost:3000` calling `127.0.0.1:8000` is cross-site, so the cookie is never sent and every page load signs the user out (found by the director, 2026-09-19). When unset, the browser uses the page's own host name with port 8000 |
| `ALLOW_TEST_DATA` (`false`) | `true` only in a demo environment. Enables `load_test_data.py` / `remove_test_data.py` and lets signup accept `TEST_DATA_EMAIL_DOMAIN`; when `false` both scripts refuse to run and signup refuses that domain |
| `TEST_DATA_EMAIL_DOMAIN` (`test.example.com`), `TEST_DATA_PASSWORD` | the reserved domain that marks a test account; the one password the loader gives every test account |
```

and change the `CORS_ORIGINS` row's purpose cell to `default http://localhost:3000,http://127.0.0.1:3000`.

**§6 "Posts and labels"** — replace the `GET /feed…` row with:

```
| `GET /feed?scope=&community=&category=&q=&sort=&cursor=` | DEMOCRACY §12.1. `scope=all` widens a signed-in viewer to every community; `q` 2–100 chars; `sort` ∈ `newest` (default), `oldest`, `most_votes`, `most_comments`. Each item carries `vote_count` and `comment_count`. `cursor` is opaque: keyset on (`created_at`, `id`) for the date sorts and on (count, `id`) for the count sorts. Response includes `ranking: "feed-v1"`, the `sort` in force, and its `explanation` |
```

**§6 "Cycles, ballot, jury"** — add a row:

```
| `GET /cycles/mine` | auth. One entry per home community: `community`, `cycle` (`id`, `number`, `state`, `opened_at`, `expected_close`) or null, `last_closed_at`, `next_ballot_expected`, `last_jury_drawn_at`, `next_jury_draw_expected`, `my_jury_status` (`none`, `drawn`, `accepted`, `declined`, `no_response`) with `respond_by` when `drawn`. One service call: `cycles_service.mine` |
```

**§9 routes table** — replace the `/feed` row and the `/`, `/posts/[id]`, `/cycles/[id]` row with:

```
| `/home` | DEMOCRACY §12: the ballot and jury panels, ballot items pinned, then feed-v1 with search, sort, community and category filters. `/feed` redirects here |
| `/explained` | "Direct Democracy Explained" — how the platform works, in plain terms with diagrams; public |
| `/` | the landing page: what the platform offers, one large centred "Join" button, and "See what people are working on" → `/home`. A signed-in visitor is redirected to `/home` |
| `/posts/[id]`, `/cycles/[id]` | a post with its label status and created solutions; a cycle with its state, items, and every jury draw |
```

**§9** — add after the routes table:

```
**Navigation.** The top bar holds the site name and exactly three tabs —
"Direct Democracy Explained" (`/explained`), "Home" (`/home`), "New
post" (`/posts/new`) — plus "Admin" for administrators only, and the
account / sign-in controls on the right. Ballot and jury are reached
from Home (DEMOCRACY §12.2). The footer, on every page, links Results,
Settings, AI actions, Administrator log, Summary fingerprints, Privacy,
Terms, and Cookies, so every transparency page stays one click away
(CLAUDE §2).

**Signing in returns you to where you were.** A page that needs a
session sends the visitor to `/login?next=<path>`; after sign-in the
site goes to `next` when it is a same-site path (begins with a single
`/`), otherwise to `/home`. When a session ends while a page is open,
the page says "You have been signed out. Sign in again." with that link;
it never shows a signed-in page to a signed-out visitor.
```

### A7. AUDIT.md §2 (director-approved 2026-09-19)

**Replace** the table and the sentence after it (from `| Trigger | Scope |` through `zero\n\`CRITICAL\` and zero \`HIGH\` findings.`) with:

```
| Trigger | Scope |
|---|---|
| After a change run the director has tested and accepted, before its PR to `main` | **Change audit:** every file the run touched and every document section its brief named. Any Foundation file in the diff → Foundation audit, full. A diff that strays outside what the brief named → full pass on that half |
| At each demo tag | Both halves, full |
| Before declaring a keeper | Both halves, full, plus the keeper checklist (§7) |
| After a fix run | Re-audit of the previously reported items only, then a full pass if the fix run touched more than the reported items |

The director tests a change before it is audited; the sandbox and its
disposable database make that safe. Nothing reaches `main` untested or
unaudited: no pull request to `main` is merged until its audit report
has zero `CRITICAL` and zero `HIGH` findings.

Because the auditor has no browser, every change brief lists the
browser-only checks the director performs by hand (session survives a
reload; sign-in returns to the page; each new page renders), and the
audit report records that list as "director-verified" or "not yet
verified".
```

### A8. SANDBOX.md

**§6.1** — retitle the heading `### 6.1 Create the change branch (host)`, replace its code block with:

```
cd ~/direct-democracy-ca
git switch main && git pull
git switch -c change/NN-short-name
# add the brief (and any files it ships with), then:
git add -A && git commit -m "change/NN brief" && git push -u origin change/NN-short-name
```

and replace the two sentences after it (`The host checkout stays on \`main\`.` … `in its own clone.`) with:

```
The sandbox is started from this branch (§6.2); switch the host back to
`main` afterwards.
```

**§6.2** — replace the first code block's last two lines (`git switch demo/01 …` and `sbx run …`) with:

```
git switch change/NN-short-name && git pull
sbx run --clone --name ddc-change-NN claude . -- "$(cat briefs/change-NN.md)"
```

and add after that code block:

```
Keep `sbx run` on **one line**. The prompt argument often does not
arrive and the window opens empty; the director then **types**: "your
brief is briefs/change-NN.md, follow it exactly".
```

**§6.6** — replace the two bullets beginning `- **Foundation:**` and `- **Iteration:**` with:

```
- **Accepted:** change audit (AUDIT.md §2), then `gh pr create --base
  main --head change/NN-short-name --fill`, merge in the browser, then
  on the host `git switch main && git pull && git push origin --delete
  change/NN-short-name`. At a demo: `git tag demo-N && git push origin
  demo-N`.
- **Rejected:** `git push origin --delete change/NN-short-name`. The
  code and the document edits go together.
```

**Add a new §6.7:**

```
### 6.7 Start the site to use it (verified 2026-09-19)

In a fresh sandbox on the branch to be used, ask Claude Code to: create
`.env` from `.env.example` **with `OLLAMA_BASE_URL` set to the host LAN
address (§5) and `ALLOW_TEST_DATA=true`**; start Postgres and Redis;
run both migration chains and the seed; start the backend on
`0.0.0.0:8000` and the frontend on `0.0.0.0:3000` with the root `.env`
exported; optionally run `backend/scripts/load_test_data.py --apply`.
Then on the host: `sbx ports <name> --publish 3000:3000 --publish
8000:8000` and browse to `http://localhost:3000` (browser VPN off). Make
an administrator with `backend/scripts/grant_admin.py <email> --apply`,
then sign out and in. Leaving the placeholder Ollama address in `.env`
leaves every post "not filed yet".
```

---

## Part B — Work items, in order, one commit each

Every UI item's proof includes the **rendered HTML** of the page (curl
the running frontend), because the auditor has no browser. F =
Foundation, I = Iteration.

- **C1-01 (F) — the session survives a page load.**
  `frontend/src/lib/api.ts`: in the browser the API base is
  `NEXT_PUBLIC_API_BASE_URL` when set, otherwise
  `${location.protocol}//${location.hostname}:8000`; on the server
  (`serverGet`) it is `NEXT_PUBLIC_API_BASE_URL` or
  `http://127.0.0.1:8000`. `.env.example` gains
  `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`; `CORS_ORIGINS`
  default per A6. Add to the frontend check in `test_layering.py`: no
  host-name literal in the browser path of `api.ts`. Proof: the test
  failing before and passing after; `curl -i` of `/auth/login` from
  Origin `http://localhost:3000` showing the `Set-Cookie` attributes and
  the CORS headers, then `/auth/refresh` with that cookie returning 200.
- **C1-02 (F) — sign-in returns you to where you were; signed-out is said
  plainly.** A6 "Signing in returns you…". Reject any `next` that does
  not begin with exactly one `/`. Proof: HTML of `/login?next=/admin`;
  a unit-level test of the `next` guard (`//evil.example`, `https://…`,
  `/admin`).
- **C1-03 (F+I) — the name.** A1 across code, emails, legal text, API
  title, page titles. Proof: the `git grep` from A1.
- **C1-04 (F) — navigation and footer.** A6 "Navigation". Proof: HTML of
  the nav signed out, signed in, and as an administrator; HTML of the
  footer.
- **C1-05 (F) — landing page.** Copy below, verbatim. One large centred
  "Join" button (`/signup`), then "See what people are working on"
  (`/home`). Signed-in visitors are redirected to `/home`. The four
  "how it works" steps now on `/` move to `/explained`. Proof: HTML.
- **C1-06 (I) — `/explained`.** Content requirements below. Two diagrams
  as inline SVG, each with `<title>` and `<desc>` and an ordered-list
  equivalent directly beneath it, readable with images disabled and at
  320 px wide (CLAUDE §8, WCAG 2.1 AA). Every number from `/settings`.
  Proof: HTML; a list mapping each paragraph to its DEMOCRACY section.
- **C1-07 (I) — feed-v1.** `GET /feed` per A6 and DEMOCRACY §12.1, in
  `posts_service.feed` / `posts_repo` (one service call; repositories
  touch tables). Counts by query, no new columns. Regenerate the single
  Iteration migration with the two GIN indexes (A5), rebuild the database
  from empty, run `verify_schema.py`. `rules.py`: `FEED_VERSION =
  "feed-v1"` and one explanation per sort. Tests: each sort's order on a
  fixture with known counts; `most_votes` counts a downvote the same as
  an upvote; search matches problem text and solution text and changes no
  order; `scope=all`; pagination across two pages for a date sort and a
  count sort. Proof: tests; `curl` of each sort.
- **C1-08 (I) — the rhythm.** `cycle_open_rule` in `seed_settings.yaml`
  (`first_sunday_of_month`); `rules.py::next_cycle_dates(today, rule,
  jury_review_days, last_opened_dates)` with the explanation beside it;
  changing the setting to an unknown rule is refused with a plain
  message. Tests: a month whose 1st is a Sunday; today is the first
  Sunday and no cycle opened; today is the first Sunday and one opened;
  December → January; Pacific-time day boundary.
- **C1-09 (I) — `GET /cycles/mine`.** A6. `my_jury_status` comes from the
  current (not superseded) jury only. Tests for every status and for a
  community with no cycle yet. Must not reveal any other juror.
- **C1-10 (I) — `/home`.** DEMOCRACY §12.2: the two panels, the pinned
  ballot block with its switch (`localStorage` key `ddca.home.showBallot`,
  wrapped in try/catch, default on), then the feed with search box, sort
  selector, community filter (home communities + "All of California"),
  category filter, both counts on every card, and the rule-in-force
  sentence. `/feed` redirects to `/home`. Proof: HTML signed out, signed
  in with no cycle, and signed in with an open ballot.
- **C1-11 (I) — "How the ballot works" / "How the jury works".** A
  button on `/ballot` and `/jury` opening an accessible disclosure;
  text in `frontend/src/content/explainers.tsx`, reused on `/explained`.
  Content requirements below. Proof: HTML of both, opened; a grep
  showing no digit in the explainer source that is a setting's value.
- **C1-12 (I) — the jury draw is replayable (TODO D2-00; audit-6
  MEDIUM).** DEMOCRACY §8.1 as written: the sampler is seeded from the
  logged bytes. Test: pool + logged bytes reproduce the drawn ids. This
  must land before C1-11's text claims it.
- **C1-13 (I) — three honest filing messages.** DEMOCRACY §4.1 as
  amended: `backend/services/posts.py` status text, the Home card labels,
  and the post page, including the no-umbrellas-here case. Proof: HTML
  of a post in each of the three states and in the no-umbrellas case.
- **C1-14 (F+I) — test data that is easy to find and delete.**
  `ALLOW_TEST_DATA`, `TEST_DATA_EMAIL_DOMAIN`, `TEST_DATA_PASSWORD` in
  `settings_env.py` and `.env.example` (A6). Signup refuses the reserved
  domain with a plain message unless `ALLOW_TEST_DATA=true` (test both).
  `backend/scripts/load_test_data.py (--dry-run | --apply)` reads
  `backend/config/test_dataset.yaml` and works **through the HTTP API**
  the way `walkthrough_extended.py` does — signup, verify, sign in, post,
  vote, comment — following the file's header rules exactly; re-running
  it adds nothing; it prints what it created and what it skipped and why.
  `backend/scripts/remove_test_data.py (--dry-run | --apply)` deletes,
  through a service, every row authored by a reserved-domain account and
  everything that hangs from those rows, then the accounts; it lists
  first, and refuses without `--force`, any row by a **non-test** account
  that would be deleted with them; afterwards `reconcile.py --dry-run` is
  clean. Both refuse when `ALLOW_TEST_DATA` is not `true`. Do not edit
  the dataset's text. Proof: loader output; counts per table; remover
  dry-run; remover apply; reconcile.
- **C1-15 (F page, I controls) — the admin page explains itself.** Above
  each control, one or two plain sentences: what it does, when you would
  use it, and that it is written to the public administrator log. Under
  "Run a cycle", a short numbered path (prepare → jury review → open →
  close → publish) and a note that to try a full cycle the same day,
  `ballot_min_dominant_days` can be set to 0, with a reason, and set
  back. Proof: HTML.
- **C1-16 — evidence.** Full suite; `verify_schema.py`; seed `--dry-run`
  (16 umbrellas, `cycle_open_rule` present); `load_test_data.py --apply`
  against real Ollama, then `GET /feed` for each sort; one full cycle in
  a test community through the API; `reconcile.py --dry-run`; the greps;
  `npm audit --audit-level=high`; `npm run build`; `git status`.

### Landing page copy (C1-05) — verbatim

```
Title:  Your community decides. Your representatives hear it.
Lead:   Direct Democracy CA is a free public tool for California
        residents. Write down a problem, work out the fix with your
        neighbors, vote on it, and send the result to the people who
        represent you.
Button: Join                    Link: See what people are working on

1. Today's technology, working for democracy
   Writing to a representative used to mean one letter from one person.
   Here a whole community drafts a proposal, improves it, and votes on
   it together, and every step is on the public record.

2. More power to the people
   Every vote counts the same. What your community passes is published
   as one document with a fingerprint anyone can check, so it cannot be
   quietly changed — and officials can be held to it.

3. Every use of AI is visible
   AI sorts posts into topics and suggests sources. It does not write
   for you, vote, or decide anything. Every AI action is listed on a
   public page, and every post shows how much AI was involved.

4. Built for California residents
   Every account declares a California home city and county, and every
   published result reports how many voters were at each verification
   level. Stronger proof of residency is planned; until it exists, we
   say so.

5. Your name is yours to show or hide
   We ask for your real name to protect the integrity of the vote. You
   choose whether the public sees it or a display name, and you can
   delete your account and your personal information at any time.

Closing line: The rules, the settings, and every administrator action
are public. (links: Settings · AI actions · Administrator log)
```

### `/explained` content (C1-06)

1. **The short version** — the four steps now on the landing page
   (jury size still read from settings).
2. **Diagram 1, "The path of a problem"** — post → filed under an
   umbrella → workshop → jury review → ballot → published result → sent
   to representatives → back to the workshop (DEMOCRACY §1).
3. **Two clocks** — the workshop never closes; the ballot is expected on
   the first Sunday of each month. **Diagram 2, "A month"** — workshop
   across the whole month; jury draw expected `jury_review_days` before;
   ballot open for `ballot_window_days`; result published (§10.1).
4. **Where AI is, and is not** — CLAUDE §5 in plain words, linking
   `/ai/actions`.
5. **What is public** — links to Settings, AI actions, Administrator
   log, Results, Summary fingerprints, with one sentence each.
6. The two explainers from C1-11.

### Explainer content (C1-11) — every claim must be true of the code

**How the ballot works:** what qualifies (dominant, for
`ballot_min_dominant_days`, with the score threshold in plain words and
the live numbers); the text is frozen when the ballot is prepared; a
jury may hold an item back; one yes/no vote per member, changeable
until close; the pass rule and quorum; the result is one public document
with a fingerprint; when (the rule, `ballot_window_days`); "During the
demo, ballots are opened and closed by the administrator, so dates are
expectations." (§7.2, §10).

**How the jury works:** why — a check by ordinary residents before the
whole community's time is asked for; jurors cannot edit or reject, only
hold back, in public, with a reason; who can be drawn and who cannot
(authors and amenders of what is on the ballot, recent jurors per
`jury_no_repeat_cycles`, administrators); how — at random, with the pool
and the random bytes logged so anyone can replay the draw; `jury_size`;
reply within `jury_review_days`, a decline draws a replacement, no reply
means not seated; a hold-back needs more than half of the seated jurors;
every reason is published; jurors are "Juror 1 of N" to the public
(§8).

## What you must not do

- Build anything from change/02 or later: unincorporated residents,
  account editing, home-community changes, the Federal checkbox, AI
  labeling on the post form, proposing umbrellas.
- Edit a protected document outside Part A, or `audits/`, or the text of
  `test_dataset.yaml` / `seed_umbrellas.yaml`.
- Touch the Foundation migration chain. No Foundation schema change is
  needed; if you think one is, stop that item and report.
- Store, hash, or publish a rendered name (AUDIT §4.1); rewrite any row
  carrying a `content_hash` (Law 6); put a democratic number in copy or
  code (Law 8); add an ordering rule without its explanation beside it
  (Law 9); call `fetch` outside `api.ts`; let a router touch a table.
- Mark an item done with less than it says. Partial is `[~]` with the
  residue named.
- Push to `main`. Open a pull request. Ask for approval.

## At the end

1. Append the planning entry below to HISTORY.md **verbatim**, then your
   own: `## <date from the system clock> — Session N (Claude Code build —
   change/01-site-shell)`, with every decision you made where the
   documents were silent.
2. TODO.md: snapshot (branch, date, "change/01 built; awaiting director's
   test, then change audit"); replace the stale line "Nothing has been
   merged to `main`…" with "`demo/01` merged to `main` 2026-09-19 and
   tagged `demo-1`; work proceeds by `change/NN` branches"; new section
   "Change 01 — site shell" with C1-01…C1-16; mark **D2-00** done by
   C1-12 and **D2-09** done; Director Decisions: close **#9** ("decided
   2026-09-19: 'Unincorporated — no city' option; county and state
   communities only; builds in change/02") and reword **#10** to "When
   to declare the keeper and freeze the Iteration schema | not yet |
   AUDIT.md §7"; add sections "Change 02 — who you are and where you
   post" and "Change 03 — propose a new umbrella" with the items listed
   in the planning entry, unchecked; Technical Debt: remove the
   "Iteration code on `main` is Demo 1's" item (no longer true) and add
   "Home preferences (`ddca.home.showBallot`) live in the browser, not
   the account".
3. `git add -A && git commit -m "change/01-site-shell complete" && git push origin change/01-site-shell`.
4. No pull request.

**Browser-only checks for the director** (copy this list into your
HISTORY entry under "Director to verify"): sign in, reload the page,
still signed in; type `/admin` while signed out, sign in, land on
`/admin`; the three tabs and the footer on a phone-width window; the
landing page redirects to Home when signed in; search, each sort, and
"All of California" on Home; the ballot switch is remembered after a
reload; both "How it works" buttons open and close by keyboard.

### Planning entry to append verbatim (before your own)

```
## 2026-09-19 — Session 2 (Claude.ai planning session — the change method; Demo 1 use notes, part 1)

**Completed:**
- `demo/01` merged to `main` by PR #5 (squash, commit `1167888`), tagged `demo-1`; `demo/01` and two stale `docs/` branches deleted. `main` is the only branch.
- The iteration method redesigned with the director and written into CLAUDE.md (The Two Halves), PROJECT.md (two Working Principles), AUDIT.md §2, SANDBOX.md §6 — wording approved by the director in this session; applied by the change/01 run from `briefs/change-01.md`.
- The director used Demo 1 from a fresh sandbox and sent eleven annotated notes. They are split into change/01 (site shell, Home, explainers, fixes, test data — this brief), change/02 (who you are and where you post), and change/03 (propose a new umbrella).
- Written for change/01: six more seed umbrellas (Fremont ×3, Alameda County ×3) and `backend/config/test_dataset.yaml` (16 test accounts, 40 posts).

**Decisions made (director unless marked):**
1. `main` is the only long-lived branch; every change is a `change/NN` branch that merges after its audit or is deleted; a demo is a tag. Iteration code is improved, never rebuilt; Iteration data stays disposable until the keeper. This supersedes the 09-19 Session 1 decision that only the keeper merges.
2. Documents are edited in the same run as the code, from wording carried in the brief; CLAUDE.md wording is approved by the director before it enters a brief.
3. The director tests a change before its audit; a scoped change audit gates the PR; full audits at demo tags and before the keeper. Zero CRITICAL / zero HIGH applies to every PR to `main`.
4. The Claude.ai project-knowledge copies of the documents are retired; the planning session clones the repository and states the commit it read.
5. The name is "Direct Democracy CA".
6. Three tabs only — Direct Democracy Explained, Home, New post. Ballot and jury live on Home as panels; each has a "How it works" explainer; ballot items can appear pinned on Home, a user-owned switch, on by default.
7. Ballots are expected on the first Sunday of each month (`cycle_open_rule`, a setting); still opened by hand during the demo.
8. Home sorts are plain counts and dates — newest, oldest, most votes, most comments — never a blended score; keyword search filters and never orders. Planning session's reading, put to the director: a user-chosen count sort does not yet owe the Small Voice rule because the default view ranks nothing (DEMOCRACY §14).
9. The landing page sells what the platform offers; it may only claim what is true today. Residency is self-declared and verification is reported in aggregate, so the page says exactly that.
10. "Propose a new umbrella" leaves the parking lot (change/03); the dead end it fixes was found by the director's first post from Fremont.
11. Unincorporated residents: "Unincorporated — no city" at signup, county and state communities only (closes Director Decision #9; change/02).
12. Changing home city or county: once per a public number of days (default 90), and a move never lets a user vote in a ballot already under way (change/02). Flagging accounts was rejected: nobody holds the role of judging misuse.
13. Federal: a greyed-out checkbox, "planned", on the post form (change/02).
14. AI labeling moves onto the post form — suggest, accept or change, submit; background labeling stays as the fallback (change/02).
15. Test data is marked three ways (reserved email domain, "[TEST]" names, authorship) and has a loader and a remover that run only when `ALLOW_TEST_DATA=true`.

**Issues encountered:**
- TODO.md and PROJECT.md on `demo/01` said the branch had merged before it had; `main` sat 71 commits stale for a day. The documents now change in the run that makes them true.
- Starting the site from `.env.example` left the placeholder Ollama address, so every post sat "waiting to be filed"; the same sentence was shown for "AI unreachable" and "no umbrella here". SANDBOX.md §6.7 and DEMOCRACY §4.1 amended.
- **Every page load signed the director out**: the browser reached the API on `127.0.0.1` from a page on `localhost`, so the `SameSite=Strict` refresh cookie was never sent. Six audits could not see it — the auditor has no browser. AUDIT.md §2 now requires a director-verified list of browser-only checks per change.
- A `demo-1` tag was first placed on the unmerged `main`; moved after the merge.

**Queued for change/02:** unincorporated option at signup; account page edits (name, email with re-confirmation, party, gender, home city/county under decision 12); post form — no city pre-selected, no "(city)" suffix, no city box for unincorporated users, Federal greyed out, AI label suggestion on the form.
**Queued for change/03:** propose a new umbrella — design session first; the parked Proposal-system design in PROJECT.md is the starting point.
```

[[[ END BUILD BRIEF — change-01 ]]]
