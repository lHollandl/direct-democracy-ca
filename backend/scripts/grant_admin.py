"""`python backend/scripts/grant_admin.py <email>` — make an account an administrator.

There is deliberately no endpoint for this. An administrator can change the
rules every democratic outcome depends on, so the only way to become one is for
somebody with access to the machine to say so, in a script that says what it
did. The grant is written to the public admin action log like every other
administrator action (DEMOCRACY.md §13).

Re-runnable, with --dry-run (DATABASE.md §6).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.db import dispose_engine, session_scope  # noqa: E402
from backend.logging_config import configure_logging  # noqa: E402
from backend.repositories import admin as admin_repo  # noqa: E402
from backend.repositories import users as users_repo  # noqa: E402


async def _run(email: str, apply: bool, revoke: bool) -> int:
    async with session_scope() as session:
        user = await users_repo.by_email(session, email)
        if user is None:
            print(f"No account with the email {email}.", file=sys.stderr)
            return 2
        if user.deleted_at is not None:
            print(f"{email} belongs to a deleted account.", file=sys.stderr)
            return 2
        wanted = not revoke
        if user.is_admin == wanted:
            print(
                f"Nothing to do: {email} (user {user.id}) "
                f"{'is' if wanted else 'is not'} already an administrator."
            )
            return 0
        print(
            f"{'WOULD ' if not apply else ''}"
            f"{'GRANT' if wanted else 'REVOKE'} administrator on {email} (user {user.id})"
        )
        if apply:
            user.is_admin = wanted
            await admin_repo.add(
                session,
                admin_user_id=user.id,
                action="grant_admin" if wanted else "revoke_admin",
                subject_type="user",
                subject_id=user.id,
                old_value={"is_admin": not wanted},
                new_value={"is_admin": wanted},
                reason="Set from the machine by backend/scripts/grant_admin.py",
            )
        else:
            await session.rollback()
    await dispose_engine()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--revoke", action="store_true", help="take the administrator flag away instead"
    )
    args = parser.parse_args()
    configure_logging("WARNING")
    return asyncio.run(_run(args.email, apply=args.apply, revoke=args.revoke))


if __name__ == "__main__":
    raise SystemExit(main())
