from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from limiter import limiter
from models import Post, Solution, SolutionVote, UmbrellaIssue, User

router = APIRouter()


class SolutionVoteCreate(BaseModel):
    # user_id comes from the authenticated token, not the request body
    solution_id: int


class PostSummary(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SolutionResponse(BaseModel):
    id: int
    post_id: int
    umbrella_issue_id: int | None
    user_id: int
    title: str
    content: str
    upvote_count: int
    created_at: datetime
    ai_contribution_percentage: int
    content_hash: str | None

    model_config = {"from_attributes": True}


class SolutionDetailResponse(SolutionResponse):
    """Full solution view including the original problem post."""
    post: PostSummary


@router.get(
    "/umbrella-issues/{umbrella_issue_id}/solutions",
    response_model=list[SolutionResponse],
)
async def get_umbrella_solutions(
    umbrella_issue_id: int, db: Session = Depends(get_db)
):
    """
    Returns all solutions grouped under this umbrella, ranked by upvote_count.
    This powers the democratic ranking panel — the solution with the most votes
    rises to the top as the community's preferred response to a civic problem.
    """
    if not db.query(UmbrellaIssue).filter(UmbrellaIssue.id == umbrella_issue_id).first():
        raise HTTPException(status_code=404, detail="Umbrella issue not found")

    return (
        db.query(Solution)
        .filter(Solution.umbrella_issue_id == umbrella_issue_id)
        .order_by(Solution.upvote_count.desc())
        .all()
    )


@router.post("/solution-votes", status_code=201)
@limiter.limit("10/minute")
async def vote_on_solution(
    request: Request,
    vote_data: SolutionVoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upvote a solution in an umbrella panel. One vote per user per solution.
    Also increments the denormalized upvote_count on the solution for ranking.
    Constitution law: AI cannot influence vote weight — this endpoint is
    user-only and records no AI contribution.
    """
    solution = db.query(Solution).filter(Solution.id == vote_data.solution_id).first()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    vote = SolutionVote(user_id=current_user.id, solution_id=vote_data.solution_id)
    db.add(vote)
    try:
        db.flush()
    except IntegrityError:
        # The unique constraint uq_solution_vote_user_solution prevents duplicates
        db.rollback()
        raise HTTPException(
            status_code=409, detail="You have already voted on this solution"
        )

    # Keep the denormalized count in sync — used for democratic ranking
    solution.upvote_count += 1
    db.commit()

    return {"solution_id": solution.id, "upvote_count": solution.upvote_count}


@router.get("/solutions/{solution_id}", response_model=SolutionDetailResponse)
async def get_solution(solution_id: int, db: Session = Depends(get_db)):
    """Returns a single solution with its vote count and the original problem post."""
    solution = db.query(Solution).filter(Solution.id == solution_id).first()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    # solution.post is lazy-loaded from the relationship while the session is open
    return solution
