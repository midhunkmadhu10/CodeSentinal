"""Evaluation endpoints: run the golden-case suite, list history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..db_models import EvalRun, User
from ..evaluation import run_evaluation
from ..schemas import EvalOut

router = APIRouter(prefix="/api/evals", tags=["evals"])


def _eval_to_out(run: EvalRun) -> EvalOut:
    return EvalOut(
        id=run.id,
        created_at=run.created_at.isoformat() if run.created_at else None,
        scores=run.scores or {},
        details=run.details or {},
        notes=run.notes or "",
    )


@router.get("", response_model=list[EvalOut])
def list_evals(
    limit: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = db.query(EvalRun).order_by(EvalRun.id.desc()).limit(limit).all()
    return [_eval_to_out(run) for run in runs]


@router.post("/run", response_model=EvalOut, status_code=201)
def trigger_eval(
    use_llm: bool = Query(default=True),
    notes: str = Query(default=""),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute the evaluation suite (LLM calls included unless use_llm=false)."""
    run = run_evaluation(db, use_llm=use_llm, notes=notes)
    return _eval_to_out(run)
