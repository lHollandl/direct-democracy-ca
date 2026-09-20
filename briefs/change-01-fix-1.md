# Build Brief — change/01-site-shell, fix run 1

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — change-01-fix-1 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is **change/01, fix
run 1** — two items found by the planning session and the director
before the change audit. Your branch is `change/01-site-shell`: run `git
fetch origin && git switch change/01-site-shell && git merge --ff-only
origin/change/01-site-shell`, then `git log --oneline -3` — the newest
commit must be the director's "change/01 fix-1 and audit briefs". You
cannot push to `main` and must not try.

Narrow and exact. Fix, prove, stop. Document wording in this brief is
director-approved; apply it **verbatim**, and edit no other line of a
protected document.

## Read first

1. `CLAUDE.md` Law 6 and §6.
2. `HISTORY.md` — the last two entries (the change/01 build, Decision 5 in particular).
3. `DEMOCRACY.md` §10.2; `ARCHITECTURE.md` §3; `AUDIT.md` §6.

## Step 0 — Pre-checks (paste each)

1. `git branch --show-current`; `git log --oneline -3`.
2. `.env` from `.env.example` with `OLLAMA_BASE_URL` at the host LAN address (SANDBOX.md §5, §6.7); Docker Compose up; both migration chains; seed.
3. Full suite green before any change (expect 259 passed).

## Work items, one commit each

- **FX-01 (F+I) — no code path deletes a hashed row.** CLAUDE.md Law 6
  says a `content_hash` row is "never modified or deleted afterward" and
  names no exception; the change/01 brief asked for a test-data remover
  that hard-deletes posts, solutions, versions, and comments. The brief
  was wrong, not the law. **Delete** `backend/scripts/remove_test_data.py`,
  `backend/services/test_data.py`, `backend/repositories/test_data.py`,
  and `backend/tests/test_test_data.py` (keep any test in it that covers
  the loader or the signup domain rule by moving it to the file where it
  belongs). Keep everything else from C1-14: the loader, the three marks
  of a test account, `ALLOW_TEST_DATA`, signup refusing the reserved
  domain. Test data is removed by rebuilding the database from empty,
  which the documents already allow until the keeper.
  Document edits, verbatim:
  - `ARCHITECTURE.md` §3 — replace the purpose cell of the `ALLOW_TEST_DATA` row with:
    ```
    `true` only in a demo environment. Enables `backend/scripts/load_test_data.py` and lets signup accept `TEST_DATA_EMAIL_DOMAIN`; when `false` the loader refuses to run and signup refuses that domain, so test accounts and real users never share a database. There is no remover: Law 6 allows no deletion of a hashed row, test data included. Test data is cleared by rebuilding the database from empty (DATABASE §2), which is possible only until the keeper — and a keeper database never has `ALLOW_TEST_DATA=true`
    ```
  - `backend/config/test_dataset.yaml` header — replace the line beginning `# Removed by` with
    `# Removed by  rebuilding the database from empty. There is no remover: Law 6 allows no deletion of a hashed row.`
    and the line beginning `#   3. everything a test account authored` with
    `#   3. everything a test account authored is test data`
  Proof: `git grep -n 'remove_test_data\|test_data_repo\|services.test_data'` returns nothing outside `HISTORY.md`, `briefs/`, `audits/`; `git grep -n -i 'session.delete\|\.delete(\|DELETE FROM' backend/ -- ':!backend/tests'` pasted, with one line per hit saying which table it touches and why that table carries no `content_hash` (DATABASE §4.12 votes is the documented one); full suite.

- **FX-02 (I) — an empty ballot says why it is empty.** Found by the
  director: `/ballot` for a zero-item cycle shows a heading and nothing
  under it. On `/ballot`, `/cycles/[id]`, and the Home ballot panel line,
  a cycle with zero items shows:
  "Nothing qualified for this ballot. To reach a ballot, a solution must
  stay dominant for D days and reach the support threshold — P% of the
  community's active users, or M supporters if that is fewer."
  D, P, M are `ballot_min_dominant_days`, `ballot_pct`, `ballot_min`
  **from that cycle's `settings_snapshot`** (the values in force when it
  was prepared), never typed into the text (Law 8). The Home panel line
  for a zero-item `prepared` cycle reads "Nothing qualified this cycle —
  next ballot expected <date>".
  Document edit, verbatim — `DEMOCRACY.md` §10.2, add after the sentence
  ending `or \`closed\`.` in the "Zero items" paragraph:
    ```
    Wherever a zero-item cycle is shown — the ballot page, the cycle
    page, the Home panel — the page says that nothing qualified and
    states the rule in plain words with the numbers from that cycle's
    settings snapshot, so an empty ballot never looks like a broken page
    (CLAUDE §2).
    ```
  Proof: rendered HTML of all three for a zero-item cycle; the sentence
  after changing `ballot_min_dominant_days` and preparing a second empty
  cycle shows each cycle's own numbers; test at the API level that the
  cycle payload carries the snapshot values the page needs.

- **FX-03 — `AUDIT.md` §6 names change reports** (director-approved).
  Replace `Written to \`audits/demo-NN-audit-K.md\` (K increments per audit of the\nsame trial).` with:
    ```
    Written to `audits/change-NN-audit-K.md` (or `audits/demo-N-audit-K.md`
    for a full audit at a demo tag); K increments per audit of the same
    change.
    ```
  and in the report template replace `# Audit — demo-NN, run K, YYYY-MM-DD` with `# Audit — change-NN, run K, YYYY-MM-DD`.

- **FX-04 — evidence.** Full suite; `verify_schema.py`; seed `--dry-run`;
  `load_test_data.py --apply` then a zero-item prepare in one community
  and a non-empty cycle in another (`ballot_min_dominant_days` to 0 with
  a reason, and back); `reconcile.py --dry-run`; `npm run build`; `npm
  test`; `git status`.

## What you must not do

- Touch any file the items do not name, except tests and the three
  frontend pages in FX-02.
- Edit a protected document beyond the verbatim text above; edit `audits/`.
- Narrow an item when marking it done. Partial is `[~]` with the residue named.
- Push to `main`. Open a pull request. Ask for approval.

## At the end

1. Append the planning entry below to HISTORY.md **verbatim**, then your
   own: `## <date from the system clock> — Session N (Claude Code build —
   change/01-site-shell, fix run 1)`.
2. TODO.md: under "Change 01 — site shell" add FX-01…FX-04; amend the
   C1-14 line to drop `remove_test_data.py`; snapshot: "change/01 fix run
   1 done; change audit next".
3. `git add -A && git commit -m "change/01 fix run 1 complete" && git push origin change/01-site-shell`.
4. No pull request.

### Planning entry to append verbatim (before your own)

```
## 2026-09-20 — Session 1 (Claude.ai planning session — change/01 review; director's first test)

**Completed:**
- Reviewed the change/01 build entry: C1-01…C1-16 built as specified, 259 tests, evidence complete. Build decisions 1–4 and 6 adopted as made.
- The director ran change/01 from the build sandbox with the test data loaded, signed up in Fremont, was granted admin, and prepared a Fremont cycle.
- Fix brief `briefs/change-01-fix-1.md` and the reusable change-audit brief `briefs/audit.md` written.

**Decisions made:**
1. **The test-data remover is withdrawn.** The change/01 brief asked for a script that hard-deletes hashed rows; Law 6 allows no deletion and names no exception. The build noticed (its Decision 5, and the docstring in `services/test_data.py`) and drew the line at ballot items; the planning session draws it at the law. Test data is cleared by rebuilding the database, and `ALLOW_TEST_DATA` keeps test accounts and real users from ever sharing one. The constitution is unchanged. This is the third time a planning-session instruction quietly overrode a general rule (HANDOFF 2026-09-19 §5); the check "does this store, hash, publish — or delete — something the constitution protects?" is now asked of every brief item.
2. A zero-item cycle must explain itself on every page that shows it, with the numbers from its own settings snapshot (DEMOCRACY §10.2).
3. Audit reports for changes are `audits/change-NN-audit-K.md` (AUDIT.md §6).

**Issues encountered:**
- The director's first prepared ballot was empty because every test solution had been dominant for minutes, not the `ballot_min_dominant_days` the rule requires. The rule worked; the page said nothing. FX-02.
- The build's own evidence cycle in San Jose reported "0 eligible jurors" with eight test residents loaded. Possibly correct (authors of ballot items and administrators are excluded; activity window), possibly not — put to the auditor as a named question.

**Director verified in the browser (2026-09-20):** the three tabs plus Admin for an administrator; the footer's transparency links; `/admin` reachable after sign-out and sign-in; `/ballot` renders with the "How the ballot works" control. **Not yet reported:** session survives a reload; `/login?next=` return; phone width; landing redirect when signed in; search, sorts, and "All of California"; the ballot switch after a reload; explainers by keyboard.
```

[[[ END BUILD BRIEF — change-01-fix-1 ]]]
