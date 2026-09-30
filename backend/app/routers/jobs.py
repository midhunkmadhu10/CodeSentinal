"""Job endpoints: list and detail (background work visibility)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..db_models import Job, User
from ..schemas import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        type=job.type,
        status=job.status,
        payload=job.payload or {},
        result=job.result,
        error=job.error,
        attempts=job.attempts,
        created_at=job.created_at.isoformat() if job.created_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


@router.get("", response_model=list[JobOut])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(Job)
        .filter((Job.user_id == user.id) | (Job.user_id.is_(None)))
        .order_by(Job.id.desc())
        .limit(limit)
        .all()
    )
    return [_job_to_out(job) for job in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None or (job.user_id is not None and job.user_id != user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_out(job)
