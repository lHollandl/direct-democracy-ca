"""`python backend/scripts/remove_test_data.py (--dry-run | --apply) [--force]`

Deletes every row authored by a reserved-domain test account, and the
accounts themselves, through backend/services/test_data.py (ARCHITECTURE.md
§3, change/01 C1-14). Refuses unless ALLOW_TEST_DATA=true.

Lists first what would change, including any row authored by a real (non-
test) account that would be deleted or orphaned as collateral — a real
reply to a test comment, a real vote on a test solution. `--apply` alone
refuses if any such row exists; add `--force` to delete them too.

Afterwards, `python backend/scripts/reconcile.py --dry-run` should be clean.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.db import dispose_engine, session_scope  # noqa: E402
from backend.logging_config import configure_logging  # noqa: E402
from backend.services import test_data as test_data_service  # noqa: E402


async def _run(apply: bool, force: bool) -> int:
    async with session_scope() as session:
        report = await test_data_service.impact_report(session)

    print(f"test accounts:  {report['test_accounts']}")
    print(f"posts:          {report['posts']}")
    print(f"solutions:      {report['solutions']}")
    print(f"comments:       {report['comments']}")
    print(f"amendments:     {report['amendments']}")

    if report["foreign_rows"]:
        print(
            f"\n{len(report['foreign_rows'])} row(s) authored by real accounts "
            "would be deleted or orphaned along with this:"
        )
        for line in report["foreign_rows"]:
            print(f"  - {line}")

    if report["test_accounts"] == 0:
        print("\nNothing to remove.")
        return 0

    if not apply:
        print("\nDRY RUN — nothing deleted. Pass --apply to delete.")
        if report["foreign_rows"] and not force:
            print("(--force will also be required — real accounts' rows are involved.)")
        return 0

    try:
        async with session_scope() as session:
            result = await test_data_service.purge(session, force=force)
    except Exception as exc:  # AppError from the service — printed, not raised
        print(f"\nREFUSED: {getattr(exc, 'message', str(exc))}")
        return 1

    print(f"\nDeleted: {result['deleted']}")
    if result["foreign_rows_deleted"]:
        print(f"Also deleted (--force), authored by real accounts:")
        for line in result["foreign_rows_deleted"]:
            print(f"  - {line}")
    await dispose_engine()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="also delete rows authored by real accounts that would otherwise block this",
    )
    args = parser.parse_args()
    configure_logging("WARNING")
    return asyncio.run(_run(apply=args.apply, force=args.force))


if __name__ == "__main__":
    raise SystemExit(main())
