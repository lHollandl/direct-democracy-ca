from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Label, User

router = APIRouter()


class LabelCorrection(BaseModel):
    user_correction: str


class LabelResponse(BaseModel):
    id: int
    post_id: int
    category: str
    subcategory: str | None
    confidence_score: int
    created_by_ai: bool
    confirmed_by_user: bool
    user_correction: str | None

    model_config = {"from_attributes": True}


@router.patch("/labels/{label_id}/correct", response_model=LabelResponse)
async def correct_label(
    label_id: int,
    correction: LabelCorrection,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Citizens use this to correct AI labels they disagree with.
    The correction is stored in user_correction and becomes training data
    for improving the AI's understanding of California civic issues over time.
    """
    label = db.query(Label).filter(Label.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    label.user_correction = correction.user_correction
    label.confirmed_by_user = True
    db.commit()
    db.refresh(label)
    return label


@router.get("/posts/{post_id}/labels", response_model=list[LabelResponse])
async def get_post_labels(post_id: int, db: Session = Depends(get_db)):
    return db.query(Label).filter(Label.post_id == post_id).all()
