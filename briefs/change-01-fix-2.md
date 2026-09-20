# Build Brief — change/01-site-shell, fix run 2

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN BUILD BRIEF — change-01-fix-2 ]]]

## Who you are, where you are

You are Claude Code running unattended inside a Docker Sandbox with your
own clone of `lHollandl/direct-democracy-ca`. This is **change/01, fix
run 2**: the findings of `audits/change-01-audit-1.md` (HIGH 1, MEDIUM
2) and its two document ambiguities. Your branch is
`change/01-site-shell`: `git fetch origin && git switch
change/01-site-shell && git merge --ff-only origin/change/01-site-shell`,
then `git log --oneline -3` — the newest commit must be the director's
"change/01 fix-2 brief". You cannot push to `main` and must not try.

Narrow and exact. **Touch only the files each item names, plus their
tests** — the next audit is a re-audit only if the diff stays inside
them. Document wording here is director-approved; apply it verbatim.

## Read first

1. `audits/change-01-audit-1.md` — Findings and Document ambiguities, in full.
2. `ARCHITECTURE.md` §9 "Signing in returns you to where you were"; `DEMOCRACY.md` §4.1, §9, §10.1.

## Step 0 — Pre-checks (paste each)

1. `git branch --show-current`; `git log --oneline -3`.
2. Environment up per SANDBOX.md §6.7 (Ollama at the address §5 records).
3. Full backend suite and `npm test` green before any change.

## Work items, one commit each

- **FX-05 (F) — [HIGH] the `next` guard cannot be talked off-site.**
  `frontend/src/lib/nextPath.ts::safeNextPath`. Stop matching strings;
  let the URL parser decide, because the browser will: resolve with
  `new URL(next, "http://placeholder.invalid")`, accept only when the
  result's `origin` equals the placeholder's **and** the raw value
  begins with `/` and contains no backslash and no ASCII control
  character (tab, CR, LF — the parser strips those, turning `/\t/evil`
  into `//evil`); return the **parsed** `pathname + search + hash`, never
  the raw string. Anything else → `null` → `/home`.
  Tests in `nextPath.test.ts`, each asserted. **Rejected:**
  `/\evil.example`, `/\\evil.example`, `/<TAB>/evil.example`,
  `/<LF>/evil.example` (real tab and newline characters),
  `//evil.example`, `///evil.example`, ` //evil.example` (leading
  space), `https://evil.example`, `javascript:alert(1)`. **Accepted, and
  returned as parsed:** `/admin`, `/`, `/posts/12?x=1#s`, `/ballot`, and
  `/%09/evil.example` (percent-encoded, so it stays a path on this
  site). Proof: the first four failing on the old code and passing on
  the new; `npm test`; the function's output pasted for every case.
  Document edit, verbatim — `ARCHITECTURE.md` §9, replace
  `the\nsite goes to \`next\` when it is a same-site path (begins with a single\n\`/\`), otherwise to \`/home\`.` with:
    ```
    the site goes to `next` only when the browser's own URL parser
    resolves it to this site's origin (a path beginning with a single `/`,
    with no backslash and no control character — a browser reads `/\` as
    `//`); otherwise to `/home`. The guard is
    `frontend/src/lib/nextPath.ts::safeNextPath`.
    ```

- **FX-06 (F) — [MEDIUM] the old name, in the spellings a space-grep
  misses.** `frontend/package.json` `"name"` → `direct-democracy-ca-frontend`
  (regenerate `package-lock.json` with `npm install --package-lock-only`);
  `backend/routers/me.py::export_download` filename prefix →
  `direct-democracy-ca-export-`; and anything else this finds. Proof:
  `git grep -il 'democracy[-_ .]*cali'` lists only paths under
  `HISTORY.md`, `audits/`, `briefs/`, `archive/`; the export test asserts
  the filename; `npm run build` first line.

- **FX-07 (I) — [MEDIUM] `/explained` claims only what AI does.**
  `frontend/src/app/explained/PageClient.tsx`: replace
  `AI sorts posts into topics, suggests reference sources, and summarizes discussion.`
  with `AI sorts posts into topics and suggests reference sources.`
  Then read every sentence on `/explained`, the landing page, and
  `explainers.tsx` that says what AI does and paste each beside the
  DEMOCRACY §9 subsection that makes it true. Proof: that table;
  rendered HTML of the section.

- **FX-08 (I) — the rhythm is described from the setting, not typed.**
  (Audit ambiguity 1.) Wherever copy says when a ballot is expected
  (`explainers.tsx`, `/explained` "Two clocks" and Diagram 2, the Home
  panel if it words the rule), the words come from one map in
  `frontend/src/content/explainers.tsx`, `CYCLE_RULE_WORDS`, keyed by the
  live `cycle_open_rule` value from `/settings`
  (`first_sunday_of_month` → "the first Sunday of each month"). An
  unknown value renders "on the schedule published in Settings" with the
  link, never a stale sentence. A backend test asserts every key of
  `rules.py::CYCLE_OPEN_RULES` has an entry in the map (read the TS file
  as text, as `test_layering.py` already does for the frontend). Proof:
  the test failing with a second fake rule and passing without; HTML.

- **FX-09 — DEMOCRACY.md §4.1 records the Home-card decision** (audit
  ambiguity 2; build decision adopted). Add, verbatim, after the sentence
  ending `transparency about weakness).`:
    ```
    A Home card can span several communities in different states, so it
    carries one short line per state present ("Being filed", "Not filed
    yet — AI unreachable", "Not filed — no umbrella covers this yet");
    the full sentence, with the community named, is the post page's.
    ```
  No code change. Proof: `git diff` of the file.

- **FX-10 — evidence.** Full backend suite; `npm test`; `npm run build`;
  `verify_schema.py`; the two greps; `git diff --stat <audit-1 commit>...HEAD`
  showing only the files named above, their tests, the two documents,
  `package-lock.json`, `TODO.md`, `HISTORY.md`.

## What you must not do

- Touch any other file. Edit `audits/`. Edit a protected document beyond the verbatim text.
- Narrow an item when marking it done. Partial is `[~]` with the residue named.
- Push to `main`. Open a pull request. Ask for approval.

## At the end

1. Append the planning entry below to HISTORY.md **verbatim**, then your
   own: `## <date from the system clock> — Session N (Claude Code build —
   change/01-site-shell, fix run 2)`.
2. TODO.md: FX-05…FX-10 under "Change 01 — site shell"; snapshot:
   "change/01 fix run 2 done; re-audit next".
3. `git add -A && git commit -m "change/01 fix run 2 complete" && git push origin change/01-site-shell`.
4. No pull request.

### Planning entry to append verbatim (before your own)

```
## 2026-09-20 — Session 2 (Claude.ai planning session — change/01 audit 1 review)

**Completed:**
- Reviewed `audits/change-01-audit-1.md`: CRITICAL 0 · HIGH 1 · MEDIUM 2 · NOTE 2 — FIX REQUIRED. FX-01…FX-03 verified by the auditor. Fix brief `briefs/change-01-fix-2.md` written; `briefs/audit.md` Step 0.5 tightened.

**Decisions made:**
1. HIGH (open redirect through `/\evil.example`) stands and is fixed by letting the URL parser decide, not by adding one more string check — the brief's three test cases were the planning session's and were too few. ARCHITECTURE §9 now states the rule the way a browser reads it.
2. MEDIUM (old name in `package.json` and the data-export filename) fixed; the proof grep is widened to hyphen, underscore, and dot spellings.
3. MEDIUM ("summarizes discussion" on `/explained`) — the sentence is removed; no summarizing AI exists or is planned for this change. Every AI-capability sentence on the new pages is now traced to DEMOCRACY §9.
4. Audit ambiguity 1 adopted as a fix: the words for the ballot rhythm come from the live `cycle_open_rule`, so a second rule can never leave a stale sentence (Law 8 in spirit).
5. Audit ambiguity 2 adopted as built: a Home card uses one short line per filing state; DEMOCRACY §4.1 now says so.
6. Named question closed: "0 eligible jurors" in San Jose is correct — in a nine-person community every resident authored a qualifying solution, and §8.1 excludes authors. Already recorded as Technical Debt (tiny communities) and DEMOCRACY §15 Open Question 3. No change.

**Issues encountered:**
- Audit 1 ran **without Ollama**: the auditor guessed gateway addresses instead of reading SANDBOX.md §5, so labeling and the real-Ollama walkthrough were not exercised. **Put to the re-auditor by name:** reach Ollama at the address SANDBOX.md §5 records; load the test data; confirm the ten `file_under: ai` posts are labeled, and paste each one's umbrella.

**Director verified in the browser:** as in Session 1 of this date. Still to clear before merging: session survives a reload; phone width; landing redirect when signed in; search, sorts, and "All of California"; the ballot switch after a reload; explainers by keyboard.
```

[[[ END BUILD BRIEF — change-01-fix-2 ]]]
