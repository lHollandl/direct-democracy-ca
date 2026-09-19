# Build Brief — demo-01, fix run 4

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — demo-01-fix-4 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is trial **demo-01**,
**fix run 4**, after audit run 4 returned `FIX REQUIRED` with one
CRITICAL. Your branch is `demo/01`: run `git switch demo/01 && git fetch
origin && git merge --ff-only origin/demo/01`, then `git log --oneline
-3` — the newest commit must be the director's "Post-audit-4 document
updates". You cannot push to `main` and must not try.

Narrow and exact, like fix run 3. Ten findings, each named by file and
function. Fix those, prove each, stop.

## Read first, in this order, in full

1. `CLAUDE.md` §6.
2. `audits/demo-01-audit-4.md` — every finding, "Previously reported, still present", and the six ambiguities (all settled in the documents; see below).
3. `HISTORY.md` — the last three entries.
4. `DEMOCRACY.md` §11.1, §11.2, §14; `DATABASE.md` §1, §3.11; `ARCHITECTURE.md` §3, §4, §9.
5. `TODO.md`.

How the ambiguities were settled, so you do not re-decide them:
summaries carry **no author at all** (§11.1, §11.2 item 2); hashes are
`VARCHAR(64)` and the document changed, not the models; the three
own-account endpoints stay `current_user` by design (ARCHITECTURE §4);
the export lifetime is `EXPORT_FILE_HOURS`; Small Voice is met by
"nothing hidden" in Demo 1 (DEMOCRACY §14); the four frontend routes are
now in ARCHITECTURE §9.

## Step 0 — Pre-checks (paste the output of each)

1. `git branch --show-current` and `git log --oneline -3`.
2. `docker compose --env-file .env -f infra/docker-compose.yml up -d`; `docker compose ps`.
3. `curl -sS $OLLAMA_BASE_URL/api/tags`.

## Work items, in order, one commit each

- **FIX-28 (CRITICAL) — no author in the summary.** Remove
  `author_display_at_snapshot` (and any user id or name) from
  `summaries_service.build_data`'s canonical JSON; add the fixed line and
  the absolute solution link per DEMOCRACY §11.2 item 2. Page, PDF, and
  JSON all change together. Test: publish a summary whose item's author
  displays their real name; assert the JSON, the page HTML, and the PDF
  text contain neither the real name nor the display name nor the user
  id; delete the account; assert the summary still verifies and the
  linked solution page now reads "Former Community Member". Paste the
  test and a published summary's Results section.
- **FIX-29 (MEDIUM) — over-cap replies.** `comments_service.create`:
  when `parent.depth >= max_depth`, set `parent_id = parent.parent_id`
  and `reply_to_comment_id = parent.id`. Test: five replies deep renders
  four levels with the fifth beside the fourth, "replying to @…" intact.
- **FIX-30 (MEDIUM) — "AI is looking for references…" on the page.**
  Render the `recommending` flag the API already exposes on
  `/umbrellas/[id]`. Correct TODO.md's FIX-22 note to say the UI half was
  missing until this run. Paste the rendered HTML with the flag true.
- **FIX-31 (MEDIUM) — blocking file calls in `export.py`.** Every
  `open`, `write`, `unlink`, `stat` in `async def` goes through
  `asyncio.to_thread` (or `aiofiles`). Add the pattern to
  `test_layering.py`'s AST checks: no `open(` / `os.*` / `pathlib` IO
  call directly inside an `async def` in `backend/services` or
  `backend/jobs`. Paste it failing before and passing after.
- **FIX-32 (MEDIUM) — `EXPORT_FILE_HOURS`.** In `settings_env.py` and
  `.env.example`, default 48; `expires_at` computed from it; startup
  refuses without it. Record it in your HISTORY entry as the audit asked.
- **FIX-33 (LOW) — password message.** "at most 72 bytes" not
  "characters", in the API message and the form.
- **FIX-34 (LOW) — jury size on the landing page** read from
  `GET /settings`, not a literal (Law 8).
- **FIX-35 (LOW) — export jobs log** start, end, counts, job id like every
  other job (ARCHITECTURE §7). Paste one job's log lines.
- **FIX-36 — `test_authorization.py` walks `app.routes`** the way
  `test_pagination.py` does, so every write endpoint is either in the
  verified-only set, the three own-account exceptions, or public, and the
  test fails on an unsorted route. (Ambiguity 5; adopt the auditor's
  suggestion.)
- **FIX-37 — evidence.** Full suite, `verify_schema.py`, seed dry-run,
  the greps, `npm audit --audit-level=high`, `git status`, pasted.

## What you must not do

- Edit CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md,
  SANDBOX.md, AUDIT.md, or `audits/`.
- Mark an item done with less than it says (FIX-01, FIX-11, FIX-22 were
  each caught). Partial is `[~]` with the residue named.
- Touch files the ten findings do not name, except tests, the frontend
  page in FIX-30, `.env.example`, and `settings_env.py`. Audit run 5
  compares your diff with the named files; stay inside them and it is a
  short re-audit.
- Push to `main`. Ask for approval.

## At the end

1. Append the director's planning entry below to HISTORY.md **verbatim**,
   then your own: `## <today> — Session N (Claude Code build — demo-01,
   fix run 4)`.
2. Update TODO.md: "Phase 2d — demo-01 fix run 4" with FIX-28…FIX-37;
   correct FIX-22's note; snapshot.
3. `git add -A && git commit -m "demo-01 fix run 4 complete" && git push origin demo/01`.
4. No pull request.

### Planning entry to append verbatim (before your own)

```
## 2026-09-15 — Session 3 (Claude.ai planning session — audit run 4 review)

**Completed:**
- Reviewed `audits/demo-01-audit-4.md` (CRITICAL 1 · HIGH 0 · MEDIUM 6 · LOW 3 · NOTE 3; FIX REQUIRED; full pass because fix run 3's paging reached `repositories/`). All six audit-3 findings confirmed fixed. Fix brief `briefs/demo-01-fix-4.md` written.
- Document changes: DEMOCRACY §11.1 and §11.2 item 2 (no author, name, or id of any kind in the summary; a fixed attribution line and a solution link instead); §14 (Small Voice met by "nothing hidden" in Demo 1; setting owed when a ranking feed exists; new row for §6 "nothing personal in the permanent record"); DATABASE §1 (`VARCHAR(64)` hashes), §3.11 (`EXPORT_FILE_HOURS`); ARCHITECTURE §3 (`EXPORT_FILE_HOURS`), §4 (the three own-account endpoints exempt from the verified-email gate), §9 (four routes added).

**Decisions made:**
1. **Director:** the summary document attributes solutions to the community, not to a person. Reason: DEMOCRACY §11.1 already said "nothing personal in it", §4.3 says solutions are community-owned, and CLAUDE §6 wins over §11.2's "author display as of snapshot", which was the sentence that caused the CRITICAL. This is the second CRITICAL from a display name stored where it should have been resolved; the planning session takes responsibility for the sentence.
2. Own-account writes (`PATCH /me/display`, `POST /me/export`, `DELETE /me`) do not require a verified email: a person's rights over their own data cannot depend on our email having arrived.
3. Hashes are `VARCHAR(64)`; the document changed, not the models.
4. Export file lifetime is configuration (`EXPORT_FILE_HOURS`, 48), not a settings-table value: it is an operational window, not a democratic rule.

**Issues encountered:**
- Fix run 3 marked FIX-22 done with the UI half unbuilt — the third time an id was closed with residue. The fix-4 brief lists each item's proof explicitly.
- Audit run 2's LOW on blocking file IO in `async def` was fixed in `seed.py` only and recurred in `export.py`; the layering test now covers the pattern so it cannot recur silently.

**Document changes flagged:**
- AUDIT.md §4.1 should gain the trap "any name or display string stored, hashed, or published instead of resolved at read time" — two CRITICALs came from it. Next planning pass; AUDIT.md is director-approval.
```

[[[ END BUILD BRIEF — demo-01-fix-4 ]]]
