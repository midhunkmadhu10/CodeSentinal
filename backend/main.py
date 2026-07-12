import os
import sys
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.auth import verify_credentials, verify_token
from app.models import (
    LoginRequest, LoginResponse, AnalyzeRequest, AnalyzeResponse, Finding,
    ScreeningSuggestion, GitHubImportRequest, GitHubImportResponse,
)
from app.rag import build_index, search_index
from app.llm import call_llm
from app.utils import parse_diff, extract_code_snippets
from app.github import import_repository_review

app = FastAPI(title="CodeSentinal Lite API", version="1.0.0")

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "codesentinal-lite"}


@app.get("/api/settings/status")
def settings_status(_=Depends(verify_token)):
    return {
        "backend_api_key_configured": bool(os.getenv("LLM_API_KEY", "").strip()),
        "llm_endpoint": os.getenv("LLM_ENDPOINT", "https://api.example.com/v1/chat/completions"),
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }


# ── Auth ────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if not verify_credentials(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(token=os.getenv("AUTH_TOKEN", "codesentinal-token-123"))


# ── Demo ────────────────────────────────────────────────────────────────────
@app.get("/api/demo/diff")
def get_demo_diff(_=Depends(verify_token)):
    demo_path = Path(__file__).parent / "demo" / "sample_diff.diff"
    return {"diff": demo_path.read_text()}


@app.get("/api/demo/rules")
def get_demo_rules(_=Depends(verify_token)):
    rules_path = Path(__file__).parent / "demo" / "sample_rules.md"
    return {"rules": rules_path.read_text()}


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
        return GitHubImportResponse(repository=req.repository, diff="", error=str(exc))


def build_screening_suggestions(findings: list[Finding]) -> list[ScreeningSuggestion]:
    """Convert findings into a short, actionable human screening checklist."""
    if not findings:
        return [ScreeningSuggestion(
            priority="Low", title="Complete a targeted review",
            action="No policy violations were found. Review authentication, authorization, and secret handling before merge."
        )]

    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_findings = sorted(findings, key=lambda finding: severity_order.get(finding.severity, 3))
    suggestions = []
    for finding in sorted_findings[:3]:
        suggestions.append(ScreeningSuggestion(
            priority=finding.severity,
            title=f"Screen {finding.file_line}",
            action=f"Validate the suggested fix, add a regression test, and confirm the change meets the referenced security policy. {finding.risk}"
        ))
    return suggestions


# ── Analyze ─────────────────────────────────────────────────────────────────
@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, _=Depends(verify_token)):
    # Validate inputs
    if not req.diff.strip():
        return AnalyzeResponse(findings=[], error="No diff provided. Please paste a diff or upload a .diff file.")
    if not req.rules.strip():
        return AnalyzeResponse(findings=[], error="No rules provided. Please upload your SECURITY.md, coding rules, or API documentation.")

    try:
        # 1. Parse and prepare the diff
        cleaned_diff = parse_diff(req.diff)

        # 2. Build FAISS index from rules
        chunks, _, index = build_index(req.rules)
        if not chunks or index is None:
            return AnalyzeResponse(findings=[], error="Could not process the rules document. Please check the format.")

        # 3. Search for relevant chunks using the diff as query
        relevant_chunks = search_index(cleaned_diff, chunks, index, top_k=5)

        # Also search using just the added lines for more precise matching
        added_lines = extract_code_snippets(cleaned_diff)
        if added_lines.strip():
            extra_chunks = search_index(added_lines, chunks, index, top_k=3)
            # Merge, deduplicate
            seen = set()
            merged = []
            for c in relevant_chunks + extra_chunks:
                if c not in seen:
                    seen.add(c)
                    merged.append(c)
            relevant_chunks = merged[:5]

        # 4. Call LLM
        findings = call_llm(
            diff=cleaned_diff,
            rules_chunks=relevant_chunks,
            endpoint=req.llm_endpoint,
            model=req.llm_model,
            api_key=req.llm_api_key,
        )

        return AnalyzeResponse(
            findings=findings,
            screening_suggestions=build_screening_suggestions(findings),
            error=None,
        )

    except ValueError as e:
        return AnalyzeResponse(findings=[], error=str(e))
    except Exception as e:
        return AnalyzeResponse(
            findings=[],
            error=f"Analysis failed: {str(e)}. Please try again or check your API key and endpoint."
        )


# ── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
