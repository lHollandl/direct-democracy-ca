"""Nightly reconciliation (DATABASE.md §7, ARCHITECTURE.md §7).

The denormalized counters are caches. The vote rows are authoritative. This
service recomputes every cached number from the rows, logs and corrects
drift, re-evaluates dominance against today's active-user count, checks that
every community reference resolves, and checks that every content hash still
recomputes to its stored value.

A hash mismatch is a critical alert, never a correction. The platform does
not quietly repair a fingerprint.

`backend/jobs/reconcile.py` calls only `run` here — a job may call services
only (ARCHITECTURE.md §2), never a repository or the session directly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories import comments as comments_repo
from backend.repositories import cycles as cycles_repo
from backend.repositories import officials as officials_repo
from backend.repositories import posts as posts_repo
from backend.repositories import reconcile as reconcile_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import votes as votes_repo
from backend.services import community as community_service
from backend.services import hashing
from backend.services import rules
from backend.services import settings as settings_service

log = logging.getLogger(__name__)


async def run(session: AsyncSession, *, correct: bool = True) -> dict:
    before = await reconcile_repo.table_counts(session)
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

    report["counts_after"] = await reconcile_repo.table_counts(session)
    report["finished_at"] = datetime.now(timezone.utc)
    return report


async def _reconcile_scores(session: AsyncSession, report: dict, correct: bool) -> None:
    """1. Recompute `net_score` for every solution, amendment and comment."""
    for target_type, rows in (
        ("solution", await solutions_repo.all_solutions(session)),
        ("amendment", await solutions_repo.all_amendments(session)),
        ("comment", await comments_repo.all_comments(session)),
    ):
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
    umbrellas = {u.id: u for u in await umbrellas_repo.all_umbrellas(session)}
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
    checks = (
        ("umbrellas", await umbrellas_repo.all_umbrellas(session)),
        ("cycles", await cycles_repo.all_cycles(session)),
        ("officials", await officials_repo.all_officials(session)),
        ("post_communities", await posts_repo.all_post_communities(session)),
    )
    for table, rows in checks:
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
    for post in await posts_repo.all_posts(session):
        computed = hashing.post_content_hash(
            problem_text=post.problem_text,
            author_id=post.author_id,
            created_at=post.created_at,
            ai_contribution_percentage=post.ai_contribution_percentage,
        )
        _compare(report, "posts", post.id, post.content_hash, computed)

    for row in await posts_repo.all_post_solutions(session):
        computed = hashing.post_solution_content_hash(
            post_id=row.post_id,
            position=row.position,
            text=row.text_body,
            created_at=row.created_at,
        )
        _compare(report, "post_solutions", row.id, row.content_hash, computed)

    for row in await solutions_repo.all_versions(session):
        computed = hashing.solution_version_content_hash(
            solution_id=row.solution_id,
            version=row.version,
            text=row.text_body,
            created_by=row.created_by,
            created_at=row.created_at,
        )
        _compare(report, "solution_versions", row.id, row.content_hash, computed)

    for row in await solutions_repo.all_amendments(session):
        computed = hashing.amendment_content_hash(
            solution_id=row.solution_id,
            base_version=row.base_version,
            author_id=row.author_id,
            proposed_text=row.proposed_text,
            rationale=row.rationale,
            created_at=row.created_at,
        )
        _compare(report, "amendments", row.id, row.content_hash, computed)

    # A comment's `content_hash` is revision 1's hash and never moves, even
    # once later revisions exist (CLAUDE.md Law 6; DATABASE.md §4.11) — so it
    # is checked against revision 1's *original* text, not the comment's
    # current (cached) text.
    comments_by_id = {row.id: row for row in await comments_repo.all_comments(session)}
    first_revision_text: dict[int, str] = {}
    for revision_row in await comments_repo.all_revisions(session):
        comment = comments_by_id.get(revision_row.comment_id)
        computed = hashing.comment_revision_content_hash(
            comment_id=revision_row.comment_id,
            revision=revision_row.revision,
            text=revision_row.text_body,
            author_id=comment.author_id if comment else None,
            created_at=revision_row.created_at,
        )
        _compare(report, "comment_revisions", revision_row.id, revision_row.content_hash, computed)
        if revision_row.revision == 1:
            first_revision_text[revision_row.comment_id] = revision_row.text_body

    for row in comments_by_id.values():
        computed = hashing.comment_content_hash(
            target_type=row.target_type,
            target_id=row.target_id,
            parent_id=row.parent_id,
            reply_to_comment_id=row.reply_to_comment_id,
            author_id=row.author_id,
            text=first_revision_text.get(row.id, row.text_body),
            created_at=row.created_at,
        )
        _compare(report, "comments", row.id, row.content_hash, computed)

    for summary in await cycles_repo.all_summaries(session):
        computed = hashing.summary_hash(summary.data)
        _compare(report, "summaries", summary.id, summary.summary_hash, computed)


def _compare(report: dict, table: str, row_id: int, stored: str, computed: str) -> None:
    if stored != computed:
        report["hash_mismatches"].append(
            {"table": table, "id": row_id, "stored": stored, "computed": computed}
        )
        log.critical(
            "content_hash_mismatch",
            extra={"table": table, "id": row_id, "stored": stored, "computed": computed},
        )
