"""Nightly reconciliation (DATABASE.md §7, ARCHITECTURE.md §7).

The denormalized counters are caches. The vote rows are authoritative. This job
recomputes every cached number from the rows, logs and corrects drift,
re-evaluates dominance against today's active-user count, checks that every
community reference resolves, and checks that every content hash still
recomputes to its stored value.

A hash mismatch is a critical alert, never a correction. The platform does not
quietly repair a fingerprint.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import session_scope
from backend.models import (
    Amendment,
    Comment,
    Cycle,
    Official,
    Post,
    PostCommunity,
    PostSolution,
    Solution,
    SolutionVersion,
    Summary,
    Umbrella,
)
from backend.repositories import solutions as solutions_repo
from backend.repositories import votes as votes_repo
from backend.services import community as community_service
from backend.services import hashing
from backend.services import rules
from backend.services import settings as settings_service

log = logging.getLogger(__name__)


async def reconcile_task(correct: bool = True) -> dict:
    job_id = uuid.uuid4().hex[:8]
    log.info("job_start", extra={"job": "reconcile", "job_id": job_id})
    try:
        async with session_scope() as session:
            report = await run(session, correct=correct)
        log.info("job_end", extra={"job": "reconcile", "job_id": job_id, **_counts(report)})
        return report
    except Exception:
        log.exception("job_failed", extra={"job": "reconcile", "job_id": job_id})
        return {"error": "reconcile failed; see the log"}


def _counts(report: dict) -> dict:
    return {
        "net_score_drift": len(report["net_score_drift"]),
        "dominance_changes": len(report["dominance_changes"]),
        "orphan_communities": len(report["orphan_communities"]),
        "hash_mismatches": len(report["hash_mismatches"]),
    }


async def run(session: AsyncSession, *, correct: bool = True) -> dict:
    before = await _table_counts(session)
    report: dict = {
        "started_at": datetime.now(timezone.utc),
        "corrected": correct,
        "net_score_drift": [],
        "dominance_changes": [],
        "orphan_communities": [],
        "hash_mismatches": [],
        "counts_before": before,
    }

    await _reconcile_scores(session, report, correct)
    await _reconcile_dominance(session, report, correct)
    await _check_communities(session, report)
    await _check_hashes(session, report)

    report["counts_after"] = await _table_counts(session)
    report["finished_at"] = datetime.now(timezone.utc)
    return report


async def _reconcile_scores(session: AsyncSession, report: dict, correct: bool) -> None:
    """1. Recompute `net_score` for every solution, amendment and comment."""
    for target_type, model in (
        ("solution", Solution),
        ("amendment", Amendment),
        ("comment", Comment),
    ):
        rows = (await session.execute(select(model))).scalars().all()
        tallies = await votes_repo.tallies(session, target_type, [r.id for r in rows])
        for row in rows:
            up, down = tallies.get(row.id, (0, 0))
            computed = rules.net_score(up, down)
            if computed != row.net_score:
                report["net_score_drift"].append(
                    {
                        "target_type": target_type,
                        "id": row.id,
                        "stored": row.net_score,
                        "computed": computed,
                    }
                )
                log.warning(
                    "net_score_drift",
                    extra={
                        "target_type": target_type,
                        "id": row.id,
                        "stored": row.net_score,
                        "computed": computed,
                    },
                )
                if correct:
                    row.net_score = computed
    await session.flush()


async def _reconcile_dominance(session: AsyncSession, report: dict, correct: bool) -> None:
    """2. Re-evaluate dominance — the active-user denominator changes without
    any vote (DEMOCRACY.md §7.1)."""
    values = await settings_service.all_values(session)
    umbrellas = {u.id: u for u in (await session.execute(select(Umbrella))).scalars().all()}
    active_cache: dict[tuple[str, int], int] = {}

    for solution in await solutions_repo.all_solutions(session):
        umbrella = umbrellas.get(solution.umbrella_id)
        if umbrella is None:
            continue
        key = (umbrella.community_level, umbrella.community_entity_id)
        if key not in active_cache:
            active_cache[key] = await community_service.active_user_count(session, *key)
        needed = rules.dominant_threshold(
            dominant_pct=values["dominant_pct"],
            dominant_min=values["dominant_min"],
            active_users=active_cache[key],
        )
        now_dominant = solution.net_score >= needed
        if now_dominant != solution.is_dominant:
            report["dominance_changes"].append(
                {
                    "solution_id": solution.id,
                    "was": solution.is_dominant,
                    "now": now_dominant,
                    "net_score": solution.net_score,
                    "threshold": needed,
                    "active_users": active_cache[key],
                }
            )
            log.info(
                "dominance_reconciled",
                extra={
                    "solution_id": solution.id,
                    "was": solution.is_dominant,
                    "now": now_dominant,
                    "net_score": solution.net_score,
                    "threshold": needed,
                    "active_users": active_cache[key],
                },
            )
            if correct:
                solution.is_dominant = now_dominant
                solution.dominant_since = (
                    datetime.now(timezone.utc) if now_dominant else None
                )
    await session.flush()


async def _check_communities(session: AsyncSession, report: dict) -> None:
    """3. Every `(community_level, community_entity_id)` pair must resolve."""
    checks = [
        ("umbrellas", Umbrella),
        ("cycles", Cycle),
        ("officials", Official),
        ("post_communities", PostCommunity),
    ]
    for table, model in checks:
        rows = (await session.execute(select(model))).scalars().all()
        for row in rows:
            try:
                await community_service.resolve(
                    session, row.community_level, row.community_entity_id
                )
            except Exception:
                identifier = getattr(row, "id", None) or getattr(row, "post_id", None)
                report["orphan_communities"].append(
                    {
                        "table": table,
                        "id": identifier,
                        "community": f"{row.community_level}:{row.community_entity_id}",
                    }
                )
                log.error(
                    "orphan_community_reference",
                    extra={"table": table, "id": identifier},
                )


async def _check_hashes(session: AsyncSession, report: dict) -> None:
    """4. Every `content_hash` and `summary_hash` must recompute to its stored
    value. A mismatch is a critical alert, not a correction."""
    for post in (await session.execute(select(Post))).scalars().all():
        computed = hashing.post_content_hash(
            problem_text=post.problem_text,
            author_id=post.author_id,
            created_at=post.created_at,
            ai_contribution_percentage=post.ai_contribution_percentage,
        )
        _compare(report, "posts", post.id, post.content_hash, computed)

    for row in (await session.execute(select(PostSolution))).scalars().all():
        computed = hashing.post_solution_content_hash(
            post_id=row.post_id,
            position=row.position,
            text=row.text_body,
            created_at=row.created_at,
        )
        _compare(report, "post_solutions", row.id, row.content_hash, computed)

    for row in (await session.execute(select(SolutionVersion))).scalars().all():
        computed = hashing.solution_version_content_hash(
            solution_id=row.solution_id,
            version=row.version,
            text=row.text_body,
            created_by=row.created_by,
            created_at=row.created_at,
        )
        _compare(report, "solution_versions", row.id, row.content_hash, computed)

    for row in (await session.execute(select(Amendment))).scalars().all():
        computed = hashing.amendment_content_hash(
            solution_id=row.solution_id,
            base_version=row.base_version,
            author_id=row.author_id,
            proposed_text=row.proposed_text,
            rationale=row.rationale,
            created_at=row.created_at,
        )
        _compare(report, "amendments", row.id, row.content_hash, computed)

    for row in (await session.execute(select(Comment))).scalars().all():
        computed = hashing.comment_content_hash(
            target_type=row.target_type,
            target_id=row.target_id,
            author_id=row.author_id,
            text=row.text_body,
            created_at=row.created_at,
        )
        _compare(report, "comments", row.id, row.content_hash, computed)

    for row in (await session.execute(select(Summary))).scalars().all():
        computed = hashing.summary_hash(row.data)
        _compare(report, "summaries", row.id, row.summary_hash, computed)


def _compare(report: dict, table: str, row_id: int, stored: str, computed: str) -> None:
    if stored != computed:
        report["hash_mismatches"].append(
            {"table": table, "id": row_id, "stored": stored, "computed": computed}
        )
        log.critical(
            "content_hash_mismatch",
            extra={"table": table, "id": row_id, "stored": stored, "computed": computed},
        )


async def _table_counts(session: AsyncSession) -> dict[str, int]:
    from sqlalchemy import func

    from backend.models import Base

    counts = {}
    for name, table in sorted(Base.metadata.tables.items()):
        counts[name] = int(
            (await session.execute(select(func.count()).select_from(table))).scalar_one()
        )
    return counts


async def main() -> None:
    """`python -m backend.jobs.reconcile` runs it on demand."""
    import json

    from backend.db import dispose_engine
    from backend.logging_config import configure_logging

    configure_logging("INFO")
    async with session_scope() as session:
        report = await run(session, correct=True)
    await dispose_engine()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
