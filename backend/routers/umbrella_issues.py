"""
Umbrella issue endpoints — the central democratic arena where all civic
complaints about a category are gathered, solutions are ranked by votes,
and collective pressure is applied to the right level of government.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import LocationType, Post, PostUmbrellaIssue, Solution, UmbrellaIssue

router = APIRouter()


class UmbrellaIssueResponse(BaseModel):
    id: int
    title: str
    location_type: LocationType
    location_id: int | None
    created_at: datetime
    upvote_count: int

    model_config = {"from_attributes": True}


class SolutionSummary(BaseModel):
    id: int
    title: str
    upvote_count: int

    model_config = {"from_attributes": True}


class UmbrellaIssueDetailResponse(UmbrellaIssueResponse):
    post_count: int
    total_vote_count: int
    # Top 5 solutions by democratic vote — shown in the umbrella panel header
    top_solutions: list[SolutionSummary]


class SolutionInPost(BaseModel):
    id: int
    title: str
    content: str
    upvote_count: int
    ai_contribution_percentage: int

    model_config = {"from_attributes": True}


class PostInUmbrellaResponse(BaseModel):
    """
    Post as it appears inside an umbrella panel — includes the citizen's
    proposed solution so voters can evaluate both the problem and the fix.
    """
    id: int
    user_id: int
    title: str
    content: str
    created_at: datetime
    ai_contribution_percentage: int
    solution: SolutionInPost | None

    model_config = {"from_attributes": True}


@router.get("/umbrella-issues", response_model=list[UmbrellaIssueResponse])
async def get_umbrella_issues(
    location_type: LocationType | None = None,
    location_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    List umbrella issues for a governance level page. The frontend calls this
    to populate the issue categories visible at a specific city, county, or state.
    """
    query = db.query(UmbrellaIssue)
    if location_type is not None:
        query = query.filter(UmbrellaIssue.location_type == location_type)
    if location_id is not None:
        query = query.filter(UmbrellaIssue.location_id == location_id)
    return query.order_by(UmbrellaIssue.upvote_count.desc()).all()


@router.get("/umbrella-issues/{umbrella_issue_id}", response_model=UmbrellaIssueDetailResponse)
async def get_umbrella_issue(umbrella_issue_id: int, db: Session = Depends(get_db)):
    """
    Full umbrella issue detail: post count, aggregate vote total across all
    solutions, and the top 5 solutions by democratic vote. Used to render
    the umbrella panel header.
    """
    umbrella = db.query(UmbrellaIssue).filter(UmbrellaIssue.id == umbrella_issue_id).first()
    if not umbrella:
        raise HTTPException(status_code=404, detail="Umbrella issue not found")

    post_count = (
        db.query(func.count(PostUmbrellaIssue.id))
        .filter(PostUmbrellaIssue.umbrella_issue_id == umbrella_issue_id)
        .scalar()
    )

    # Sum of all solution upvote_counts — represents total democratic engagement
    total_vote_count = (
        db.query(func.coalesce(func.sum(Solution.upvote_count), 0))
        .filter(Solution.umbrella_issue_id == umbrella_issue_id)
        .scalar()
    )

    top_solutions = (
        db.query(Solution)
        .filter(Solution.umbrella_issue_id == umbrella_issue_id)
        .order_by(Solution.upvote_count.desc())
        .limit(5)
        .all()
    )

    return UmbrellaIssueDetailResponse(
        id=umbrella.id,
        title=umbrella.title,
        location_type=umbrella.location_type,
        location_id=umbrella.location_id,
        created_at=umbrella.created_at,
        upvote_count=umbrella.upvote_count,
        post_count=post_count,
        total_vote_count=total_vote_count,
        top_solutions=top_solutions,
    )


@router.get(
    "/umbrella-issues/{umbrella_issue_id}/posts",
    response_model=list[PostInUmbrellaResponse],
)
async def get_umbrella_posts(umbrella_issue_id: int, db: Session = Depends(get_db)):
    """
    All posts grouped under this umbrella with their solutions.
    This is the main content of the umbrella panel — every citizen complaint
    in this category paired with the solution they proposed. Citizens vote on
    solutions here to surface the community's preferred government action.
    """
    if not db.query(UmbrellaIssue).filter(UmbrellaIssue.id == umbrella_issue_id).first():
        raise HTTPException(status_code=404, detail="Umbrella issue not found")

    post_ids = [
        row.post_id
        for row in (
            db.query(PostUmbrellaIssue.post_id)
            .filter(PostUmbrellaIssue.umbrella_issue_id == umbrella_issue_id)
            .all()
        )
    ]

    if not post_ids:
        return []

    return (
        db.query(Post)
        .filter(Post.id.in_(post_ids))
        .order_by(Post.created_at.desc())
        .all()
    )
