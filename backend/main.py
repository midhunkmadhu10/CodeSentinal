import logging
import os
import sys
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from app.auth import get_auth_token, verify_credentials, verify_token
from app.config import FALLBACK_CHUNKS, MAX_RETRIEVAL_CHUNKS
from app.github import import_repository_review
from app.llm import LLMError, call_llm
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Finding,
    GitHubImportRequest,
    GitHubImportResponse,
    LoginRequest,
    LoginResponse,
    ScreeningSuggestion,
)
from app.rag import build_index, search_index
from app.utils import extract_code_snippets, parse_diff

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("codesentinal")

app = FastAPI(title="CodeSentinal API", version="1.1.0")

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
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "codesentinal"}


@app.get("/api/settings/status")
def settings_status(_=Depends(verify_token)):
    """Safe configuration metadata. Never exposes the API key itself."""
    return {
        "llm_configured": bool(os.getenv("LLM_API_KEY", "").strip())
        and bool(os.getenv("LLM_ENDPOINT", "").strip())
        and bool(os.getenv("LLM_MODEL", "").strip()),
        "llm_endpoint": os.getenv("LLM_ENDPOINT", "").strip(),
        "llm_model": os.getenv("LLM_MODEL", "").strip(),
    }


# ── Auth ────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if not verify_credentials(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(token=get_auth_token())


# ── Demo ────────────────────────────────────────────────────────────────────
@app.get("/api/demo/diff")
def get_demo_diff(_=Depends(verify_token)):
    demo_path = Path(__file__).parent / "demo" / "sample_diff.diff"
    return {"diff": demo_path.read_text(encoding="utf-8")}


@app.get("/api/demo/rules")
def get_demo_rules(_=Depends(verify_token)):
    rules_path = Path(__file__).parent / "demo" / "sample_rules.md"
    return {"rules": rules_path.read_text(encoding="utf-8")}


# ── GitHub import ───────────────────────────────────────────────────────────
@app.post("/api/github/import", response_model=GitHubImportResponse)
def github_import(req: GitHubImportRequest, _=Depends(verify_token)):
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


def build_screening_suggestions(findings: list[Finding]) -> list[ScreeningSuggestion]:
    """Convert findings into a short, actionable human screening checklist."""
    if not findings:
        return [
            ScreeningSuggestion(
                priority="Low",
                title="Complete a targeted review",
                action="No policy violations were found. Review authentication, "
                "authorization, and secret handling before merge.",
            )
        ]

    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_findings = sorted(
        findings, key=lambda finding: severity_order.get(finding.severity.value, 3)
    )
    suggestions = []
    for finding in sorted_findings[:3]:
        suggestions.append(
            ScreeningSuggestion(
                priority=finding.severity,
                title=f"Screen {finding.file_line}",
                action=f"Validate the suggested fix, add a regression test, and confirm "
                f"the change meets the referenced security policy. {finding.risk}",
            )
        )
    return suggestions


# ── Analyze ─────────────────────────────────────────────────────────────────
@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, _=Depends(verify_token)):
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
