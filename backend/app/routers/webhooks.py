"""GitHub webhook endpoint: PR events enqueue automatic reviews.

Signature verification fails closed — when GITHUB_WEBHOOK_SECRET is unset the
endpoint rejects every delivery with 503. Duplicate deliveries for the same
head SHA are skipped.
"""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..db_models import Event, Review
from ..github_service import parse_pull_request_event, verify_webhook_signature
from ..observability import METRICS, log_event
from ..worker import enqueue_job

logger = logging.getLogger("codesentinal.webhooks")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/github", status_code=202)
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
):
    body = await request.body()

    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
    if not secret:
        METRICS.inc("webhook_events_total", event=x_github_event or "unknown", disposition="rejected_no_secret")
        raise HTTPException(
            status_code=503,
            detail="Webhook receiver is not configured. Set GITHUB_WEBHOOK_SECRET.",
        )
    if not verify_webhook_signature(body, x_hub_signature_256, secret):
        METRICS.inc("webhook_events_total", event=x_github_event or "unknown", disposition="rejected_bad_signature")
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        METRICS.inc("webhook_events_total", event=x_github_event, disposition="rejected_bad_payload")
        raise HTTPException(status_code=400, detail="Malformed webhook payload.")

    disposition = "ignored"
    result: dict = {}
    if x_github_event in ("pull_request",) and isinstance(payload, dict):
        parsed = parse_pull_request_event(payload)
        if parsed is not None:
            owner, name, number, action, head_sha = parsed
            if action in ("opened", "synchronize", "reopened"):
                # Skip duplicate reviews of the same commit.
                duplicate = (
                    db.query(Review)
                    .filter(
                        Review.repository == f"{owner}/{name}",
                        Review.pr_number == number,
                        Review.head_sha == head_sha,
                    )
                    .first()
                )
                if duplicate is not None:
                    disposition = "skipped_duplicate"
                else:
                    enqueue_job(
                        db,
                        type="review_pull_request",
                        payload={
                            "owner": owner,
                            "name": name,
                            "pull_number": number,
                            "trigger": "webhook",
                            "post_comment": True,
                        },
                    )
                    disposition = "enqueued"
                    result = {"repository": f"{owner}/{name}", "pull_number": number, "head_sha": head_sha}
                    db.add(
                        Event(
                            event="webhook.pr_enqueued",
                            data={"repository": f"{owner}/{name}", "pr": number, "action": action},
                        )
                    )
                    db.commit()
                    log_event("webhook.pr_enqueued", repo=f"{owner}/{name}", pr=number)

    METRICS.inc("webhook_events_total", event=x_github_event or "unknown", disposition=disposition)
    return {"status": "accepted", "event": x_github_event, "disposition": disposition, **result}
