"""Observability endpoints: JSON metrics snapshot + Prometheus exposition."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..db_models import Review, User
from ..observability import METRICS

router = APIRouter(prefix="/api", tags=["observability"])


@router.get("/metrics/snapshot")
def metrics_snapshot(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """JSON metrics + usage rollup for the dashboard."""
    reviews = db.query(Review).all()
    total_reviews = len(reviews)
    high_findings = sum((r.counts or {}).get("High", 0) for r in reviews)
    total_findings = sum(sum((r.counts or {}).values()) for r in reviews)
    estimated_cost = sum((r.metrics or {}).get("estimated_cost_usd", 0) for r in reviews)
    latencies = [(r.metrics or {}).get("latency_seconds", 0) for r in reviews]

    snapshot = METRICS.snapshot()
    snapshot["usage"] = {
        "total_reviews": total_reviews,
        "total_findings": total_findings,
        "high_findings": high_findings,
        "estimated_cost_usd": round(estimated_cost, 4),
        "avg_review_latency_seconds": (
            round(sum(latencies) / len(latencies), 3) if latencies else 0.0
        ),
    }
    return snapshot


@router.get("/metrics", response_class=Response, include_in_schema=False)
def metrics_prometheus():
    """Prometheus text exposition (open scraping; add auth at the proxy)."""
    return Response(content=METRICS.render_prometheus(), media_type="text/plain; version=0.0.4")
