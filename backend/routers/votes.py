from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Vote, VoteType

router = APIRouter()


class VoteCreate(BaseModel):
    user_id: int
    post_id: int
    vote_type: VoteType


@router.post("/votes")
async def cast_vote(vote_data: VoteCreate, db: Session = Depends(get_db)):
    vote = Vote(
        user_id=vote_data.user_id,
        post_id=vote_data.post_id,
        vote_type=vote_data.vote_type,
    )
    db.add(vote)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint uq_vote_user_post prevents duplicate votes at the DB level
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already voted on this post")

    db.refresh(vote)
    return {"id": vote.id, "post_id": vote.post_id, "vote_type": vote.vote_type.value}


@router.get("/posts/{post_id}/votes")
async def get_post_votes(post_id: int, db: Session = Depends(get_db)):
    votes = db.query(Vote).filter(Vote.post_id == post_id).all()
    upvotes = sum(1 for v in votes if v.vote_type == VoteType.upvote)
    downvotes = sum(1 for v in votes if v.vote_type == VoteType.downvote)
    return {
        "post_id": post_id,
        "upvotes": upvotes,
        "downvotes": downvotes,
        "total": len(votes),
    }
