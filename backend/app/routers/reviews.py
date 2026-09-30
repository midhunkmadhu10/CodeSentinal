"""Review endpoints: create (synchronous pipeline), history, detail."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db_models import Review, User
from ..database import get_db
from ..pipeline import review_to_dict, run_review
from ..schemas import ReviewCreate, ReviewOut

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("", response_model=ReviewOut, status_code=201)
def create_review(
    req: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the full review pipeline (scanners → agents → corroboration → fixes)."""
    review = run_review(
        db,
        user_id=user.id,
        diff=req.diff,
        rules_text=req.rules,
        trigger="api",
        repository=req.repository,
        title=req.title,
        repo_id=req.repo_id,
        depth=req.depth,
    )
    return review_to_dict(review)


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: str = Query(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Review).filter(Review.user_id == user.id)
    if repository:
        query = query.filter(Review.repository == repository)
    reviews = (
        query.order_by(Review.id.desc()).offset(offset).limit(limit).all()
    )
    return [review_to_dict(review, include_findings=False) for review in reviews]


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(
    review_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.get(Review, review_id)
    if review is None or review.user_id != user.id:
        raise HTTPException(status_code=404, detail="Review not found")
    return review_to_dict(review)
