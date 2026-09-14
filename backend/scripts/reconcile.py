"""`python backend/scripts/reconcile.py` — the nightly job, on demand.

DATABASE.md §7. Pass `--dry-run` to report drift without correcting it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.db import dispose_engine, session_scope  # noqa: E402
from backend.jobs import reconcile as reconcile_job  # noqa: E402
from backend.logging_config import configure_logging  # noqa: E402


async def _run(correct: bool) -> int:
    async with session_scope() as session:
        report = await reconcile_job.run(session, correct=correct)
    await dispose_engine()
    print(json.dumps(report, indent=2, default=str))
    critical = len(report["hash_mismatches"]) + len(report["orphan_communities"])
    return 1 if critical else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile caches against the rows.")
    parser.add_argument(
        "--dry-run", action="store_true", help="report drift without correcting it"
    )
    args = parser.parse_args()
    configure_logging("INFO")
    return asyncio.run(_run(correct=not args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
