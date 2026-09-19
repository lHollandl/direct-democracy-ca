# Evidence — demo-01 build run, 2026-09-14

The raw output of every check the build brief asks for, unabridged. HISTORY.md
summarises these and pastes the short ones in full; this directory holds the
originals, including the parts too long to put in the session log.

| File | What it is |
|---|---|
| `migrate.txt` | `alembic upgrade foundation@head && alembic upgrade iteration@head` against an empty database, and `alembic heads` |
| `verify_schema.txt` | `backend/scripts/verify_schema.py` — live vs models, a scratch database built from the migrations vs models, scratch vs live table by table, the two halves, and every foreign key indexed |
| `seed.txt` | `python -m backend.seed --apply` followed by `--dry-run`, which reports zero pending writes |
| `tests.txt` | the full test suite, every test named |
| `walkthrough.txt` | the manual full cycle through the API with `curl`, every request and every response |
| `pages.txt` | every frontend route in ARCHITECTURE.md §9 served by `next start` with the API running |
| `a11y.txt` | the images-off and accessibility checks (I-28) |
| `reconcile.json` | `backend/scripts/reconcile.py --dry-run` against the data the walkthrough produced |
| `restore-ballot-min-dominant-days.txt` | the settings change putting `ballot_min_dominant_days` back to 3 after the walkthrough, with the resulting public history and a read-only check that the rule bites again |

Two things these files cannot show, both recorded in HISTORY.md:

- **No screenshots.** No browser could be installed in the sandbox — the
  Chrome-for-Testing download host is not on the network allowlist. `pages.txt`
  records what the server actually returned for each route and what the API
  endpoint behind it answered, which is the closest honest substitute.
- **No containers.** The Docker Hub blob CDN is not on the allowlist either, so
  `infra/docker-compose.yml` could not be brought up in this sandbox. Postgres
  16.14 and a Redis-protocol server were run directly instead. The compose file
  is written and is what the director's workstation uses; it is untested by this
  run.
