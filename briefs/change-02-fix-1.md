# Build Brief — change/02-who-and-where, fix run 1

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — change-02-fix-1 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is **change/02, fix
run 1**: what the director found using the change, two document gaps the
build flagged, and two director decisions. Branch
`change/02-who-and-where`: `git fetch origin && git switch
change/02-who-and-where && git merge --ff-only
origin/change/02-who-and-where`; `git log --oneline -3` — the newest
commit must be the director's "change/02 fix-1 brief". You cannot push to
`main` and must not try. Foundation is under full rigor.

Document wording here is director-approved: apply it **verbatim** and
edit no other line of a protected document. Before each item ask: does
this store, hash, publish, or delete something the constitution says is
resolved at read time, immutable, or private? (AUDIT.md §4.1.)

## Read first

1. `CLAUDE.md` §2, §5, §6, Law 7; `HISTORY.md`, the last two entries.
2. `DEMOCRACY.md` §4.1, §9.1; `ARCHITECTURE.md` §3, §4, §6, §9; `DATABASE.md` §2.

## Step 0 — Pre-checks (paste each)

1. `git branch --show-current`; `git log --oneline -3`.
2. Environment per SANDBOX.md §6.7; `curl -sS $OLLAMA_BASE_URL/api/tags` lists `llama3.1:8b`.
3. Clean-shell full suite and `npm test` green before any change (expect 287 / 15).

## Part A — Document changes (first commit: "change/02 fix-1 documents")

**DEMOCRACY.md §4.1** — replace the three bullets from `- **The AI suggests, the author decides — before anything is posted**` through `back, exactly as before this change.` with:

```
- **The AI suggests, the author decides — before anything is posted**
  (default). When the author has written the problem and at least one
  solution and chosen their communities, they continue to "Where it
  goes" and the labeler runs at once on the draft (§9.1). For each
  chosen community the form shows the suggested umbrella under that
  umbrella's own main category — or says the AI found none that fits —
  with two buttons: **Choose myself**, which opens that community's
  active umbrellas, and **None of these fit**. Posting without touching
  either keeps the suggestion; there is no "keep" button, because
  posting is the decision. After a change, "Use the AI's suggestion"
  undoes it. Editing the problem text or the communities afterwards
  marks the suggestion out of date, and it runs again. A community left
  at "none of these fit" is saved under the main category and is
  `needs_review`; "propose a new umbrella" will sit at this button when
  it is built.
- **Choose myself, without a suggestion** — offered only when the AI
  cannot be reached or the hourly limit is spent: the author browses the
  active umbrellas for their communities. Recorded as `author_selected`.
- **Post now, file later** — offered in the same two cases only: the
  post is saved and the background labeler files it when the AI is
  back, exactly as before this change.
```

**DATABASE.md §2** — in the Foundation row replace `` `ai_actions`, `data_exports` | `` with `` `ai_actions`, `data_exports`, `user_home_changes`, `email_change_requests` | ``; in the Iteration row replace `` `jury_holdbacks`, `summaries` | `` with `` `jury_holdbacks`, `summaries`, `label_previews` | ``.

**ARCHITECTURE.md §3** — add a row after `ALLOW_TEST_DATA`:

```
| `VERIFY_RESEND_MINUTES` (`5`) | the least time between two verification emails to one account |
```

**ARCHITECTURE.md §4** — replace `**except the three\n  that act only on the caller's own account**: \`PATCH /me/display\`,\n  \`POST /me/export\`, \`DELETE /me\`.` with:

```
**except those that act only on the caller's own account**:
  `PATCH /me/display`, `PATCH /me/profile`, `POST /me/email`,
  `POST /me/resend-verification`, `POST /me/export`, `DELETE /me` — a
  mistyped signup address can never receive its link, so correcting it
  cannot require one.
```

and add, as a new paragraph directly after the paragraph that contains that sentence:

```
**Demo mail.** Only when `EMAIL_BACKEND=console` **and**
`ALLOW_TEST_DATA=true`, the responses of signup, resend-verification,
and email-change carry a `demo_link`, and the page shows "Demo mode — no
email was sent. Confirm here." In every other configuration the field is
absent. A confirmation link handed to whoever asked for it would let
anyone confirm an address they do not own, so this must be unreachable
on a real site: a test asserts the field's absence for each of the three
other combinations of the two settings, and the link is never written
to a log line beyond the console email itself.
```

**ARCHITECTURE.md §6 "Auth and account (F)"** — add after the `POST /me/email` row:

```
| `POST /me/resend-verification` | auth, unverified accounts only. Voids older unused tokens, issues a new one, sends the email; at most one per `VERIFY_RESEND_MINUTES` (429 with the wait in plain words); 409 if already verified |
```

**§6 "Posts and labels (I)"** — add after the `GET /posts/{id}` row:

```
| `GET /posts/mine?cursor=` | auth. The caller's own posts, newest first, each with its communities' filing words and links; standard pagination. Declared before `/posts/{id}` |
```

and append to the purpose cell of the `POST /posts/label-preview` row this sentence: ` Two commits by design: the \`ai_actions\` row is committed before the model is called, so it survives a failed call (Law 7) — the one exception to one transaction per service call.`

**§9 routes table** — in the `/me` row replace `display settings, export, delete;` with `display settings, "Your posts" (an Iteration section, as on \`/admin\`), export, delete;` and in the `/posts/new` row append: ` An unverified author is told at step 1, with "Send me a new link", not at step 4.`

## Part B — Work items, one commit each

- **FX-01 (I) — step 4 as the director redesigned it.**
  `frontend/src/app/posts/new/PageClient.tsx`, per DEMOCRACY §4.1 as
  amended: no Keep control; per community "Suggested: <umbrella>" shown
  as "<umbrella's main category> › <umbrella>" (the AI's own main
  category is shown only where it suggested no umbrella — today the form
  prints the AI's category above an umbrella from a different one); two
  buttons, **Choose myself** (opens that community's umbrella list) and
  **None of these fit**; the current choice always visible in words
  ("Filed under … — the AI's suggestion" / "— your choice" / "None of
  these fit — saved under <category>"); "Use the AI's suggestion" after
  a change; the page-level "Choose myself instead" is removed when a
  suggestion is shown. Post is enabled as soon as a suggestion has
  arrived. The API contract of `POST /posts` does not change: untouched
  → `confirmed_by_author`. "Choose myself, without a suggestion" and
  "Post now, file later" appear **only** on 503 or 429 from the preview —
  never on 403. Proof: `npm test` cases for the decision-to-payload
  mapping extracted into a pure function; rendered HTML; walkthrough
  output for kept / changed / none.
- **FX-02 (F+I) — an unverified author is told at step 1.** `/posts/new`
  shows the confirm-your-email notice and "Send me a new link" before
  any field, and disables Continue. Same notice component on the banner.
- **FX-03 (F) — resend verification.** A Part A rows. Through the email
  client; older unused tokens voided; rate limit from
  `VERIFY_RESEND_MINUTES`; `backend/services/auth.py` message "Ask for a
  new one from the sign-in page" now true — reword to "Sign in and choose
  'Send me a new link'." Tests: each refusal; old token dead after
  resend; verified account 409.
- **FX-04 (F) — demo mail.** ARCHITECTURE §4 "Demo mail". `demo_link` in
  the three responses; signup-done page, banner resend, and the
  email-change panel show the box. Tests: present only when both
  settings are demo values; absent in the other three combinations for
  all three endpoints; never in a log record other than the console
  email (caplog).
- **FX-05 (I) — "Your posts".** `GET /posts/mine`; section on `/me`
  between "Your communities" and "Your profile". One service call;
  repository touches tables; pagination test; authorization test (never
  another user's list).
- **FX-06 — the labeling model is `llama3.1:8b`** (director's decision on
  the C2-12 evidence). `.env.example` `OLLAMA_MODEL=llama3.1:8b`; any
  test or script that names the model reads it from configuration (Law
  10). No document names a model. Proof: `git grep -n 'llama3'`.
- **FX-07 — evidence.** Clean-shell full suite; `npm test`; `npm run
  build`; `verify_schema.py` (no schema change is expected — if you need
  one, stop and report); `walkthrough_change02.py` against real Ollama
  with the new model; `reconcile.py --dry-run`; `git status`.

## What you must not do

- Build what "None of these fit" will do next, or any part of propose-a-new-umbrella.
- Add an administrator power to confirm someone's email.
- Change keyboard behaviour of native controls (Space checks a box; arrows move in a list — the director confirmed these work).
- Edit a protected document beyond Part A; edit `audits/`; touch either migration chain.
- Narrow an item when marking it done. Push to `main`. Open a pull request. Ask for approval.

## At the end

1. Append the planning entry below to HISTORY.md **verbatim**, then your own (`… — change/02-who-and-where, fix run 1`) with "Director to verify".
2. TODO.md: FX-01…FX-07 under "Change 02"; snapshot: "change/02 fix run 1 done; director's look, then full Foundation audit".
3. `git add -A && git commit -m "change/02 fix run 1 complete" && git push origin change/02-who-and-where`. No pull request.

**Director to verify:** step 4 shows Suggested + two buttons and posts without a Keep; "Use the AI's suggestion" undoes a change; the category line matches the umbrella; sign up and confirm from the on-page demo box with no terminal; "Send me a new link" works and refuses a second click within five minutes; the account page lists your posts; an unverified account is stopped at step 1.

### Planning entry to append verbatim (before your own)

```
## 2026-09-20 — Session 5 (Claude.ai planning session — change/02 review; director's test)

**Completed:**
- Reviewed the change/02 build entry: C2-01…C2-13 built as specified; 287 tests; build decisions 1–8 adopted (notably: own-account edits do not require a verified email; the draft-suggestion action row is committed before the model call so it survives a failure — now documented in ARCHITECTURE §6).
- The director tested change/02 in the build sandbox after a host power loss (sandbox and database survived). Fix brief `briefs/change-02-fix-1.md`.

**Decisions made (director):**
1. **The labeling model is `llama3.1:8b`.** On the C2-12 evidence: one poor fit against three, far fewer stray answers, the same speed.
2. **Step 4 has no Keep button** — posting without a change is keeping. "Change" and "Choose myself" are one button. "None of these fit" stays beside it and, for now, saves the post under its main category; what it opens is decided with propose-a-new-umbrella.
3. **Demo mail:** in a demo environment the page shows the confirmation link itself, so testing needs no terminal. Rejected: an administrator button that confirms an email — a verified address is part of what makes a vote count, and no administrator should be able to mint one.
4. The account page lists the user's own posts.
5. Keyboard behaviour of native controls stays standard (Space, arrows); the planning session's check wording ("Tab and Enter only") was wrong, not the form.

**Issues encountered:**
- The site told users to "ask for a new verification link" and had no way to ask. Found when the power cut destroyed the log holding the director's link. FX-03.
- An unverified author could fill in all four steps before being refused, and was then offered the AI-unreachable fallbacks, which could not work. FX-01, FX-02.
- The form printed the AI's main category above a suggested umbrella belonging to a different category; stored data was already correct.
- The build flagged two document gaps outside its authority (DATABASE §2 table lists; ARCHITECTURE §4 "the three"). Corrected here.

**Director verified in the browser (2026-09-20, sandbox `ddc-change-02`):** unincorporated signup shows two communities; New post has nothing pre-selected, Federal greyed out, the suggestion appears on reaching step 4, change and none-of-these-fit work, editing marks it out of date; with Ollama stopped the two fallbacks appear; on the account page a display-name change shows on an earlier post, the home change shows its warning and next-allowed date, and the email change completes from its link; the forms work by keyboard (Tab, Space, arrows, Enter on buttons) and at phone width.
```

[[[ END BUILD BRIEF — change-02-fix-1 ]]]
