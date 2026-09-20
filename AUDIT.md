# AUDIT.md — Audit Runs

> After every long build run, a separate Claude Code session audits the
> result. The auditor reads the documents and the code and reports
> every discrepancy. It fixes nothing. Fixes come in a following build
> run, then another audit, until the audit is clean.
>
> This is where the rigor lives in a documents-first, long-run method.
> The build run is trusted to be fast; the audit run is trusted to be
> skeptical.

---

## 1. Why a Separate Run

A session that wrote the code will defend the code. A fresh session
with a fresh context reads the documents as a stranger would and
notices what the builder rationalized. The auditor's only loyalty is to
CLAUDE.md, DEMOCRACY.md, DATABASE.md, and ARCHITECTURE.md.

The auditor has **no write access to source files**. Its sandbox mounts
the trial read-only except for `audits/`, where it writes its report.

---

## 2. When

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

---

## 3. The Auditor's Reading Order

1. CLAUDE.md, fully.
2. The build brief for this run (`briefs/demo-NN.md`) — what was
   supposed to be built.
3. HISTORY.md, the entry the build run wrote — what it says it built and
   every decision it recorded.
4. TODO.md — the ids it marked done.
5. DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md — in full for a full
   audit; the referenced sections for a re-audit.
6. The code. Every file the build run touched, per `git diff
   main...demo/NN --stat` (Iteration) or the PR diff (Foundation), then
   the surrounding modules they call.

The auditor does not read the previous audit's findings before forming
its own list; it reads them afterwards to check nothing was silently
dropped.

---

## 4. What the Auditor Checks

Each check produces findings with a severity (§5) and a location cited
as `path::symbol` (never a line number).

### 4.1 Constitution
For every CLAUDE.md principle and law, find where the code honors it or
where it does not. DEMOCRACY.md §14 is the map; the auditor verifies the
map against the code, not the document against itself. Specific traps:

- AI writing a row *after* showing its result (Law 7 order).
- A threshold, window, or size that is a literal in code (Law 8).
- Ranking code without its plain-English docstring or `RULES_VERSION`
  (Law 9).
- `os.environ` read outside `settings_env.py` (Law 10).
- A synchronous database or HTTP call inside `async def` (Law 11).
- `except: pass`, bare `except:`, `TODO`, `FIXME` (Law 12).
- A router touching a repository, a client, or the session directly
  (ARCHITECTURE §2).
- Any endpoint that returns a ballot vote to anyone other than the
  voter who cast it, or returns a voter id with any vote
  (DATABASE §4.16) — always `CRITICAL`.
- Any code path that changes a vote's weight or count based on
  verification level, admin status, or anything but the voter's choice
  — always `CRITICAL`.
- Any name, display name, or other rendered string stored, hashed, or
  published instead of resolved at read time from the user's display
  settings (DATABASE §3.2). Two of demo-01's CRITICALs came from this.
- Any edit that rewrites a row carrying a `content_hash` instead of
  inserting a new version or revision (Law 6).

### 4.2 Specification conformance
- Every table and column in DATABASE.md exists with the stated type,
  nullability, default, index, and constraint; nothing exists that is
  not in DATABASE.md (or is, and is reported as "undocumented").
- Every endpoint in ARCHITECTURE.md §6 exists with the stated method,
  path, auth dependency, and pagination; nothing undocumented.
- Every rule in DEMOCRACY.md has an implementation, and the
  implementation matches the formula — the auditor re-derives
  `threshold()` by hand for three cases and compares with the code's
  output.
- Every setting in DEMOCRACY.md §7.4 is seeded, readable, and actually
  consulted by the code that the section says depends on it.
- Every state transition in DEMOCRACY.md §5.2, §10.1 is enforced —
  the auditor lists transitions the code allows that the document does
  not.

### 4.3 Security
- Password hashing, token storage (hashed, never raw), refresh rotation
  and reuse revocation, blacklist on logout.
- Every write endpoint behind `verified_user` and the rate limiter.
- Input length limits enforced server-side, not only in the UI.
- No secret in any committed file, log line, error response, or
  `ai_actions.output`.
- Anonymization erases every column DATABASE §3.1 lists and nothing it
  does not.
- `mailto:` bodies do not include anything but the summary URL, hash,
  and fixed text (no user data).

### 4.4 Evidence
- Every acceptance claim in the build's HISTORY entry is backed by
  pasted output. A claim without output is a finding (`MEDIUM`,
  "unverified claim") and the auditor runs the check itself.
- The auditor runs: the test suite; `verify_schema.py`; `reconcile.py
  --dry-run`; the seed runner `--dry-run` (must report zero pending
  writes); a full-cycle walkthrough through the API with `curl` or the
  test client, pasting every response.
- Hash round-trip: fetch a summary's JSON, recompute SHA-256 locally,
  compare with the stored hash.

### 4.5 Frontend
- Every page in ARCHITECTURE §9 exists and renders with the backend
  running.
- Every page renders with images blocked (CLAUDE §8).
- Keyboard-only traversal of signup, post creation, voting, and the
  ballot.
- No page contains business logic that duplicates or overrides the
  backend (Law 14) — the auditor looks for thresholds, eligibility, or
  status computed client-side.
- AI labels visible everywhere DEMOCRACY.md says they are.

### 4.6 Documents
- TODO.md marks done only what is actually done; the auditor lists ids
  marked done that fail any check above.
- The HISTORY entry records every decision the build made that the
  documents did not pre-resolve. The auditor lists decisions it can see
  in the code that are not in the entry.
- Any document the build edited that it was not allowed to edit
  (CLAUDE.md, PROJECT.md, DEMOCRACY.md, DATABASE.md, ARCHITECTURE.md
  without the brief saying so) — `HIGH`.

---

## 5. Severity

| Level | Meaning | Blocks |
|---|---|---|
| `CRITICAL` | Constitutional violation affecting votes, AI accountability, or PII; secret exposure | Merge, demo use, keeper |
| `HIGH` | Law violation; spec mismatch that changes behavior; missing security control | Merge, keeper |
| `MEDIUM` | Spec mismatch without behavior change; unverified claim; undocumented decision | Keeper |
| `LOW` | Style, naming, docstring, comment quality | Nothing; recorded |
| `NOTE` | Observation, suggestion, or a document ambiguity the auditor hit | Nothing; goes to the next planning session |

---

## 6. The Report

Written to `audits/demo-NN-audit-K.md` (K increments per audit of the
same trial). Structure:

```
# Audit — demo-NN, run K, YYYY-MM-DD

## Summary
One paragraph. Counts by severity. Verdict: CLEAN / FIX REQUIRED.

## Findings
### [SEVERITY] short title
- Where: path::symbol
- Document: DOCUMENT.md §n
- What the document requires:
- What the code does:
- Evidence: (pasted output, diff excerpt, query result)
- Suggested fix: (one sentence; the auditor does not implement)

## Evidence log
Every command the auditor ran and its output, in order.

## Checks passed
The list of §4 checks with no findings, so silence is not ambiguity.

## Document ambiguities
Places where the auditor could not decide whether the code or the
document was right. These go to the director.
```

The auditor's HISTORY entry is one paragraph: report path, counts,
verdict. Findings live in the report, not in HISTORY.

---

## 7. The Keeper Checklist

Before a demo build is declared the keeper and Iteration comes under
full rigor, in addition to a clean audit:

- [ ] The Iteration Alembic chain has been squashed to one initial
      migration, applied cleanly from empty, and `verify_schema.py`
      matches.
- [ ] Every `content_hash` and `summary_hash` in the database
      recomputes.
- [ ] Every open item in TODO's "Director Decisions Pending" has either
      a decision or a written reason it can stay open.
- [ ] `RULES_VERSION` is `1.0.0` or the director has chosen the number.
- [ ] The summary document has been read, end to end, by the director,
      as a citizen would read it.
- [ ] The director has used the demo through one full cycle with at
      least three accounts.

---

## 8. What the Auditor Does Not Do

- Fix anything. Not a typo. A fix by the auditor is a `HIGH` finding
  against the auditor.
- Rewrite documents. Ambiguities go in the report's last section.
- Approve merges. The director merges after reading the summary and
  verdict.
- Rely on the build run's tests alone. The auditor runs its own cycle
  walkthrough.
