# Document Update Brief — 2026-09-19

Everything between the markers is your instructions. Ignore the markers.

[[[ BEGIN DOCUMENT UPDATE BRIEF — 2026-09-19 ]]]

## Who you are, where you are

You are Claude Code running inside a Docker Sandbox with your own clone
of `lHollandl/direct-democracy-ca`. This run edits **documents only** —
no code, no tests, no migrations. Your branch is `demo/01`: run `git
switch demo/01 && git fetch origin && git merge --ff-only origin/demo/01`
and confirm with `git log --oneline -3` (newest commit: the audit run 6
report). You cannot push to `main` and must not try.

The documents you will edit are normally off-limits to a build run.
For this run only, the director has approved the exact wording below,
and you apply it **verbatim**. Where this brief gives replacement text,
use it character for character. Where it says "add", place the text
where indicated. Do not improve, reflow, or reword anything else in
those files. If a "replace" anchor is not found exactly, stop, report
the file and anchor in HISTORY.md, and continue with the other items.

## 1. CLAUDE.md — "The Two Halves of the Codebase" (director-approved)

**Replace** the paragraph beginning `**Iteration** is the civic
machinery` with:

```
**Iteration** is the civic machinery — posts, umbrellas, the workshop,
the jury, the ballot, the summary document, and all of their UI. It is
revised freely, demo after demo, and the documents — not the previous
demo — are always the truth: each demo's brief names what changed in the
documents since the last one, and Claude Code rebuilds those parts, while
the Iteration **schema and data** are regenerated fresh for each demo.
Audited code that the documents still describe is carried forward, not
rewritten to prove a point. When a demo build becomes worth keeping, the
director declares it the **keeper**, and from that build onward Iteration
is under the same rigor as Foundation.
```

## 2. PROJECT.md — "Working Principles" (director-approved)

**Replace** the paragraph beginning `**Every demo teaches; only keepers
are kept.**` with:

```
**Every demo teaches; only keepers are kept.** A demo is used, audited,
and its lessons written into the documents. The next demo is built from
the improved documents: its brief names what changed, and Claude Code
revises those parts of the Iteration half while the Iteration schema and
data start fresh. When a demo is good enough that its data is worth
keeping, the director declares it the keeper, and Iteration comes under
full rigor.
```

**Replace** the paragraph beginning `**One branch per trial.**` with:

```
**One branch per trial.** `demo/NN` is branched from `main` and built in
its own sandbox with its own clone of the repository. `demo/01` was
merged to `main` whole on 2026-09-19 as a one-time exception, because it
carried the Foundation's first build and six audits had cleared it; the
Iteration code it left on `main` is the previous demo, not the truth.
From `demo/02` onward, a demo branch merges only when declared the
keeper. Foundation fixes discovered during a demo go to `main` by their
own pull request.
```

## 3. AUDIT.md — §4.1 Constitution (director-approved)

**Add** two bullets at the end of the "Specific traps" list, after the
vote-weight bullet:

```
- Any name, display name, or other rendered string stored, hashed, or
  published instead of resolved at read time from the user's display
  settings (DATABASE §3.2). Two of demo-01's CRITICALs came from this.
- Any edit that rewrites a row carrying a `content_hash` instead of
  inserting a new version or revision (Law 6).
```

## 4. SANDBOX.md

**§6.4** — replace the paragraph beginning `Inside the sandbox the app
listens on its ports.` with:

```
Inside the sandbox the app listens on its ports. **Confirmed 2026-09-19:**

    sbx ports <sandbox-name> --publish 3000:3000 --publish 8000:8000
    sbx ports <sandbox-name>            # lists the bindings

Publishing starts a stopped sandbox. The bindings are on `127.0.0.1` and
persist across `sbx stop`. The servers themselves must be started inside
the VM (bound to `0.0.0.0`), which the director does by reopening the
sandbox's Claude Code session — `sbx run --name <sandbox-name> claude .`
reopens a stopped sandbox without cloning again — and asking it to start
the stack. Claude Code inside a sandbox declines pasted instructions
that start services; the director types the confirmation.
```

**§9 Open Items** — replace the whole list with:

```
- Read-only filesystem policy for the audit sandbox (confirmed absent by
  default; the flag, if one exists, is still to be found). The auditor's
  closing diff and the host diff are the safeguard.
- `archive.ubuntu.com` and `security.ubuntu.com` are not on the
  allowlist, so `apt` does not work inside the VM (fix run 4 worked
  around it with `pip --break-system-packages`). Add both with `sbx
  policy allow network` if a run needs system packages.
- (resolved 2026-09-19) `sbx ports` syntax — §6.4.
- (resolved 2026-09-19) reopening a sandbox — §6.4.
- (resolved 2026-09-14) the clone starts on the host's current branch;
  sync the local `demo/NN` before every run — §6.2.
```

**§6.6** — replace the line beginning `- **Foundation:** open a PR from
`demo/01`` with:

```
- **Foundation:** Foundation changes reach `main` by pull request after
  a clean audit. (`demo/01` merged whole as the one-time exception
  recorded in PROJECT.md.)
```

## 5. DEMOCRACY.md — §8.1 (records the audit-6 finding's resolution)

**Replace** the sentence `The draw uses the platform's cryptographic
random source.` (and the rest of that paragraph up to and including
`no\ndraw is ever deleted.`) with:

```
The draw takes 32 bytes from the platform's cryptographic random source,
logs them, and **seeds the sampler from those bytes**, so the logged pool
plus the logged bytes reproduce the drawn ids exactly (`random.Random`
seeded from the bytes; `sample(pool_sorted_by_id, jury_size)`). The draw
is **logged**: the eligible pool (user ids), the drawn ids, the
timestamp, and the random bytes used. Anyone with the log can replay the
draw. A re-draw (§13) creates a new draw and marks the old one
superseded; no draw is ever deleted. (Demo 1 logged bytes that did not
drive the sampler — audit run 6; corrected in Demo 2. Seeding the bytes
from the previous summary's hash, so the draw is provably unmanipulable,
remains parked in PROJECT.md.)
```

## 6. TODO.md

- Snapshot: date `2026-09-19`; Documents row "Demo 1 documents final;
  Demo 2 brief pending director's use notes"; add a line under the
  table: "**Demo 1 status:** six audits, run 6 CLEAN (CRITICAL 0 · HIGH
  0 · MEDIUM 1). Merged to `main` 2026-09-19 as the one-time exception
  (PROJECT.md). Not the keeper; the director is using it."
- Phase 3 heading becomes "Phase 3 — Demo 2 (revise per CLAUDE.md 'The
  Two Halves')". Add at the top of its list:
  - `[ ] **D2-00** Jury draw seeded from the logged bytes (DEMOCRACY §8.1; audit-6 MEDIUM); test that pool + bytes replay the draw`
  - `[ ] **D2-09** Director's use notes from Demo 1 folded into the documents (the input to the Demo 2 brief)`
  - `[ ] **D2-10** California photography for page headers — director supplies images; ARCHITECTURE §9 — or the style brief drops it`
- Director Decisions Pending: add
  `| 10 | Keeper: is Demo 1 the keeper, or does Demo 2 become it? | Demo 2 | AUDIT.md §7 |`
- Technical Debt: add
  `- **Iteration code on \`main\` is Demo 1's.** Any session reading \`main\` must treat it as the previous demo; the documents are the truth (CLAUDE.md, The Two Halves). Bites if a brief says "match the existing code".`
- `*Last updated: 2026-09-19 — Demo 1 cleared and merged; documents final for Demo 1.*`

## 7. HISTORY.md — append this entry verbatim

```
## 2026-09-19 — Session 1 (Claude.ai planning session — audit run 6 review; Demo 1 cleared)

**Completed:**
- Reviewed `audits/demo-01-audit-6.md`: CRITICAL 0 · HIGH 0 · MEDIUM 1 · NOTE 2 — **CLEAN**. The auditor independently re-verified all 27 findings from runs 1–5; none present. The one MEDIUM (jury `random_bytes` not driving the sampler) goes to Demo 2 as D2-00.
- Demo 1 opened for the director's use from the fix-5 sandbox: `sbx ports` confirmed, both ports published, stack started inside the VM.
- Document updates applied by a document-only Claude Code run from `briefs/docs-update-2026-09-19.md`: CLAUDE.md "The Two Halves" (revise, not rewrite; schema and data fresh per demo); PROJECT.md "Every demo teaches" and "One branch per trial" (the `demo/01` merge exception; keeper-only merges from `demo/02`); AUDIT.md §4.1 (two new traps: names stored instead of resolved; edits that rewrite hashed rows); SANDBOX.md §6.4, §6.6, §9 (`sbx ports`, reopening a sandbox, apt blocked); DEMOCRACY.md §8.1 (seeded draw); TODO.md.

**Decisions made:**
1. **Director:** `demo/01` merges to `main` whole, as a one-time exception — it carries Foundation's first build and six audits cleared it. From `demo/02` onward only the keeper merges. Foundation fixes go to `main` by their own PR.
2. **Director:** Demo 2 revises Iteration from the documents rather than deleting and rebuilding it: the brief names what changed; audited code the documents still describe carries forward; Iteration schema and data are regenerated. CLAUDE.md and PROJECT.md amended with director-approved wording.
3. The audit-6 MEDIUM is a code fix (seed the sampler from the logged bytes), not a wording change; DEMOCRACY §8.1 now states the target.
4. Demo 1 is not declared the keeper. The director uses it first; the keeper question is Director Decision #10.

**Issues encountered:**
- Claude Code inside a sandbox refuses pasted instructions that start services or print credentials, asking for a typed confirmation. Recorded in SANDBOX.md §6.4 so the director types "yes, go ahead" rather than pasting.

**Notes:**
- Demo 1 by the numbers: one build run, five fix runs, six audit runs; 27 distinct findings, 4 CRITICAL, 5 HIGH, all closed; 218+ tests. Two CRITICALs and one HIGH pair traced to document sentences that told the builder to store what should be resolved or to edit what should be versioned — the planning session's, not the builder's.

**Document changes flagged:**
- The Demo 2 brief waits on the director's use notes (D2-09).
- P0-13 (search provider) still open; reference recommendation returns 503 until set.
```

## At the end

1. `git status` — only the seven documents and `briefs/docs-update-2026-09-19.md` changed.
2. `git add -A && git commit -m "Document updates 2026-09-19 (director-approved wording; Demo 1 cleared)" && git push origin demo/01`.
3. No pull request. Do not touch code.

[[[ END DOCUMENT UPDATE BRIEF — 2026-09-19 ]]]
