"""CodeSentinal API entrypoint (v2 — SaaS edition).

Keeps the legacy demo routes (/api/health, /api/auth/login, /api/demo/*,
/api/github/import, /api/analyze, /api/settings/status) frozen in shape and
adds the SaaS surface: JWT auth, repositories, reviews, jobs, metrics,
evaluations, and GitHub webhooks. The legacy analyze flow runs in this module
with module-level names (call_llm, import_repository_review) so tests can
monkeypatch them at the `main` boundary.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from app.auth import get_auth_token, seed_demo_user, verify_credentials, get_current_user
from app.config import FALLBACK_CHUNKS, MAX_RETRIEVAL_CHUNKS
from app.database import get_db, init_db
from app.db_models import User
from app.github import import_repository_review  # noqa: F401 — monkeypatch target
from app.llm import LLMError, call_llm  # noqa: F401 — monkeypatch target
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    LoginRequest,
    ScreeningSuggestion,
)
from app.observability import configure_logging
from app.pipeline import build_screening_suggestions
from app.rag import build_index, search_index
from app.routers import auth as auth_router
from app.routers import evals as evals_router
from app.routers import jobs as jobs_router
from app.routers import metrics as metrics_router
from app.routers import repos as repos_router
from app.routers import reviews as reviews_router
from app.routers import webhooks as webhooks_router
from app.schemas import GitHubImportRequest, GitHubImportResponse
from app.utils import extract_code_snippets, parse_diff

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("codesentinal")

VERSION = "2.0.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        seed_demo_user(db)
    finally:
        db.close()
    from app.worker import start_worker

    start_worker()
    logger.info("CodeSentinal API %s started", VERSION)
    yield
    from app.worker import stop_worker

    stop_worker()


app = FastAPI(title="CodeSentinal API", version=VERSION, lifespan=lifespan)

# CORS — restrict to the frontend origin(s) via CORS_ORIGINS (comma-separated).
_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── SaaS routers ─────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(repos_router.router)
app.include_router(reviews_router.router)
app.include_router(jobs_router.router)
app.include_router(metrics_router.router)
app.include_router(evals_router.router)
app.include_router(webhooks_router.router)


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "codesentinal", "version": VERSION}


# ── Settings ────────────────────────────────────────────────────────────────
@app.get("/api/settings/status")
def settings_status(_user: User = Depends(get_current_user)):
    """Safe configuration metadata. Never exposes any API key itself."""
    llm_configured = (
        bool(os.getenv("LLM_API_KEY", "").strip())
        and bool(os.getenv("LLM_ENDPOINT", "").strip())
        and bool(os.getenv("LLM_MODEL", "").strip())
    )
    from app.database import is_postgres, pgvector_ready
    from app.llm import embeddings_configured
    from app.model_routing import routing_table

    return {
        "llm_configured": llm_configured,
        "llm_endpoint": os.getenv("LLM_ENDPOINT", "").strip(),
        "llm_model": os.getenv("LLM_MODEL", "").strip(),
        "embeddings_configured": embeddings_configured(),
        "database": "postgres" if is_postgres() else "sqlite",
        "pgvector_enabled": pgvector_ready(),
        "worker_running": os.getenv("WORKER_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off"),
        "routing": routing_table(),
    }


# ── Legacy auth (frozen shape; fails closed) ────────────────────────────────
@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Legacy demo login: {username, password} → {token} (static env token)."""
    if not verify_credentials(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"token": get_auth_token()}


# ── Demo fixtures ────────────────────────────────────────────────────────────
@app.get("/api/demo/diff")
def get_demo_diff(_user: User = Depends(get_current_user)):
    demo_path = Path(__file__).parent / "demo" / "sample_diff.diff"
    return {"diff": demo_path.read_text(encoding="utf-8")}


@app.get("/api/demo/rules")
def get_demo_rules(_user: User = Depends(get_current_user)):
    rules_path = Path(__file__).parent / "demo" / "sample_rules.md"
    return {"rules": rules_path.read_text(encoding="utf-8")}


# ── Legacy GitHub import ─────────────────────────────────────────────────────
@app.post("/api/github/import", response_model=GitHubImportResponse)
def github_import(req: GitHubImportRequest, _user: User = Depends(get_current_user)):
    """Import a PR (or latest commit comparison) and a repository security policy."""
    try:
        repository, diff, policy, policy_path = import_repository_review(
            req.repository, req.pull_number, req.access_token
        )
        return GitHubImportResponse(
            repository=repository, diff=diff, policy=policy, policy_path=policy_path
        )
    except ValueError as exc:
        return GitHubImportResponse(repository=req.repository, error=str(exc))
    except Exception:
        logger.exception("GitHub import failed unexpectedly for %s", req.repository)
        return GitHubImportResponse(
            repository=req.repository,
            error="The GitHub import failed unexpectedly. Check the backend logs.",
        )


# ── Legacy analyze (frozen shape; module-level names are monkeypatch targets) ─
@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, _user: User = Depends(get_current_user)):
    if not req.diff.strip():
        return AnalyzeResponse(
            error="No diff provided. Please paste a diff or upload a .diff file."
        )
    if not req.rules.strip():
        return AnalyzeResponse(
            error="No rules provided. Please upload your SECURITY.md, coding rules, "
            "or API documentation."
        )

    try:
        cleaned_diff = parse_diff(req.diff)

        chunks, _, index = build_index(req.rules)
        if not chunks or index is None:
            return AnalyzeResponse(
                error="Could not process the rules document. Please check the format."
            )

        relevant_chunks = search_index(
            cleaned_diff, chunks, index, top_k=MAX_RETRIEVAL_CHUNKS
        )

        # A second, more focused query using only the added lines.
        added_lines = extract_code_snippets(cleaned_diff)
        if added_lines.strip():
            seen = set(relevant_chunks)
            merged = list(relevant_chunks)
            for chunk in search_index(added_lines, chunks, index, top_k=3):
                if chunk not in seen:
                    seen.add(chunk)
                    merged.append(chunk)
            relevant_chunks = merged[:MAX_RETRIEVAL_CHUNKS]

        if not relevant_chunks:
            # Nothing in the policy matched the diff; fall back to the start of
            # the document so the review still has policy context.
            logger.info("Retrieval matched no rule chunks; using document preamble")
            relevant_chunks = chunks[:FALLBACK_CHUNKS]

        findings = call_llm(diff=cleaned_diff, rules_chunks=relevant_chunks)

        return AnalyzeResponse(
            findings=findings,
            screening_suggestions=build_screening_suggestions(findings),
            error=None,
        )

    except LLMError as exc:
        return AnalyzeResponse(error=str(exc))
    except ValueError as exc:
        return AnalyzeResponse(error=str(exc))
    except Exception:
        logger.exception("Analysis failed unexpectedly")
        return AnalyzeResponse(
            error="Analysis failed due to an internal error. Check the backend logs and try again."
        )


# ── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
