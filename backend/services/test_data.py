"""Finding and removing test data (ARCHITECTURE.md §3, change/01 C1-14).

Every test account's email is at `TEST_DATA_EMAIL_DOMAIN`. This is the only
place in the codebase that hard-deletes rows a person authored — CLAUDE.md's
"never delete a `content_hash` row" and "accounts are anonymized, never
erased" laws protect the real civic record; a reserved-domain test account
is not part of it. Both entry points refuse unless `ALLOW_TEST_DATA` is
`true` (backend/config/settings_env.py).

A row authored by a **real** (non-test) account that would be deleted or
orphaned as collateral — a real reply to a test comment, a real vote on a
test solution, a real amendment on a test solution — is never removed
silently. `impact_report` lists every one; `purge` refuses unless `force`
is passed, and even then reports exactly what it took with it.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings_env import get_env_settings
from backend.errors import Conflict
from backend.repositories import test_data as test_data_repo

log = logging.getLogger(__name__)


def _require_allowed() -> None:
    if not get_env_settings().ALLOW_TEST_DATA:
        raise Conflict(
            "ALLOW_TEST_DATA is not true. Test-data tools are disabled "
            "(ARCHITECTURE.md §3).",
            code="test_data_disabled",
        )


async def test_account_ids(session: AsyncSession) -> list[int]:
    """Every account at the reserved test-data domain — the one, permanent
    mark test accounts carry (their content also starts with "[TEST] ", but
    the email domain is what a script can query)."""
    domain = get_env_settings().TEST_DATA_EMAIL_DOMAIN.lower()
    return await test_data_repo.account_ids_at_domain(session, domain)


async def _owned_ids(session: AsyncSession, test_ids: list[int]) -> dict[str, list[int]]:
    """Everything test accounts authored, computed once and reused by both
    the report and the purge so they never disagree."""
    return {
        "posts": await test_data_repo.posts_by_authors(session, test_ids),
        "solutions": await test_data_repo.solutions_by_authors(session, test_ids),
        "comments": await test_data_repo.comments_by_authors(session, test_ids),
        "amendments": await test_data_repo.amendments_by_authors(session, test_ids),
    }


async def _foreign_rows(session: AsyncSession, test_ids: list[int], owned: dict) -> list[str]:
    """Rows authored by a **non-test** account that would be deleted or
    orphaned if `owned`'s rows were removed. Each entry is a plain sentence,
    ready to print."""
    foreign: list[str] = []

    for comment_id, author_id in await test_data_repo.comments_replying_to(
        session, owned["comments"], excluding_authors=test_ids
    ):
        foreign.append(
            f"comment {comment_id} (by non-test user {author_id}) replies to a "
            "test comment that would be deleted"
        )

    for comment_id, author_id in await test_data_repo.comments_on_solutions(
        session, owned["solutions"], excluding_authors=test_ids
    ):
        foreign.append(
            f"comment {comment_id} (by non-test user {author_id}) is on a test "
            "solution that would be deleted"
        )

    for amendment_id, author_id in await test_data_repo.amendments_on_solutions(
        session, owned["solutions"], excluding_authors=test_ids
    ):
        foreign.append(
            f"amendment {amendment_id} (by non-test user {author_id}) is on a "
            "test solution that would be deleted"
        )

    for vote_id, user_id, target_type in await test_data_repo.votes_on_solutions_or_amendments(
        session,
        solution_ids=owned["solutions"],
        amendment_ids=owned["amendments"],
        excluding_users=test_ids,
    ):
        foreign.append(
            f"vote {vote_id} (by non-test user {user_id}) is on a test "
            f"{target_type} that would be deleted"
        )

    for vote_id, user_id in await test_data_repo.votes_on_comments(
        session, owned["comments"], excluding_users=test_ids
    ):
        foreign.append(
            f"vote {vote_id} (by non-test user {user_id}) is on a test comment "
            "that would be deleted"
        )

    for juror_id, user_id in await test_data_repo.jurors_among(session, test_ids):
        foreign.append(
            f"juror {juror_id} (test user {user_id}) served on a jury — jury "
            "and ballot records are not touched by this tool"
        )

    for ballot_item_id, solution_id in await test_data_repo.solutions_on_ballots(
        session, owned["solutions"]
    ):
        foreign.append(
            f"solution {solution_id} appears on ballot item {ballot_item_id} — "
            "jury and ballot records are not touched by this tool"
        )

    return foreign


async def impact_report(session: AsyncSession) -> dict:
    """What `remove_test_data.py` would do, without doing it."""
    test_ids = await test_account_ids(session)
    owned = await _owned_ids(session, test_ids)
    foreign = await _foreign_rows(session, test_ids, owned)
    return {
        "test_accounts": len(test_ids),
        "posts": len(owned["posts"]),
        "solutions": len(owned["solutions"]),
        "comments": len(owned["comments"]),
        "amendments": len(owned["amendments"]),
        "foreign_rows": foreign,
    }


async def purge(session: AsyncSession, *, force: bool) -> dict:
    """Delete every row a reserved-domain test account authored, and the
    accounts themselves. One transaction. Refuses if a non-test row would be
    deleted or orphaned, unless `force` is passed — in which case those rows
    are deleted too, and named in the return value."""
    _require_allowed()
    test_ids = await test_account_ids(session)
    if not test_ids:
        return {"test_accounts": 0, "deleted": {}, "foreign_rows_deleted": []}

    owned = await _owned_ids(session, test_ids)
    foreign = await _foreign_rows(session, test_ids, owned)
    jury_blocking = [f for f in foreign if "jury and ballot records" in f]
    other_blocking = [f for f in foreign if f not in jury_blocking]

    if jury_blocking:
        raise Conflict(
            "Refusing: " + "; ".join(jury_blocking) + ". Resolve jury/ballot "
            "participation by hand before removing these accounts.",
            code="jury_participation_present",
        )
    if other_blocking and not force:
        raise Conflict(
            "Refusing: removing test data would also remove or orphan "
            f"{len(other_blocking)} row(s) authored by real accounts. Pass "
            "--force to delete them too, or resolve them by hand. "
            + "; ".join(other_blocking),
            code="foreign_rows_present",
        )

    # Comments: the test accounts' own, plus (under --force) any comment on a
    # test solution or a reply to a test comment — walked to a fixed point
    # since comment_max_depth is small and bounded.
    comment_ids = set(owned["comments"])
    comment_ids.update(
        cid for cid, _ in await test_data_repo.comments_on_solutions(session, owned["solutions"])
    )
    changed = True
    while changed:
        more = await test_data_repo.comment_ids_replying_to(session, list(comment_ids))
        new_ids = set(more) - comment_ids
        changed = bool(new_ids)
        comment_ids.update(new_ids)

    # Amendments: the test accounts' own, plus any amendment on a test
    # solution (deleted explicitly so it is counted, even though the
    # solution delete below would cascade it anyway).
    amendment_ids = set(owned["amendments"])
    amendment_ids.update(
        aid for aid, _ in await test_data_repo.amendments_on_solutions(session, owned["solutions"])
    )

    counts: dict[str, int] = {}
    counts["votes"] = await test_data_repo.delete_votes(
        session,
        user_ids=test_ids,
        solution_ids=owned["solutions"],
        amendment_ids=list(amendment_ids),
        comment_ids=list(comment_ids),
    )
    counts["comments"] = await test_data_repo.delete_comments(session, list(comment_ids))
    counts["amendments"] = await test_data_repo.delete_amendments(session, list(amendment_ids))
    counts["solutions"] = await test_data_repo.delete_solutions(session, owned["solutions"])
    counts["posts"] = await test_data_repo.delete_posts(session, owned["posts"])
    counts["accounts"] = await test_data_repo.delete_accounts(session, test_ids)

    await session.flush()
    log.info("test_data_purged", extra={"test_accounts": len(test_ids), **counts})
    return {
        "test_accounts": len(test_ids),
        "deleted": counts,
        "foreign_rows_deleted": foreign if force else [],
    }
