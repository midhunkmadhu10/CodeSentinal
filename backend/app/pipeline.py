"""Review orchestration: scanners → routed agents → corroboration → fixes.

`run_review` is the full production pipeline behind manual, API, and webhook
reviews; it persists a Review with findings, metrics, and a summary.
`analyze_sync` is the legacy-compatible synchronous path used by
POST /api/analyze (its request/response shape is frozen by tests).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .agents import (
    AgentFinding,
    AgentRun,
    corroborate,
    generate_fixes,
    run_all_agents,
)
from .config import FALLBACK_CHUNKS, MAX_RETRIEVAL_CHUNKS
from .db_models import Event, Review, ReviewFinding, utcnow
from .llm import LLMError, call_llm  # noqa: F401 — legacy analyze path
from .model_routing import routing_table
from .observability import METRICS, log_event
from .rag import build_index, search_index, repo_similarity_search
from .scanners import scan_added_lines, scanner_summary
from .utils import extract_code_snippets, parse_diff

logger = logging.getLogger("codesentinal.pipeline")


def _counts(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for finding in findings:
        severity = finding.get("severity")
        if severity in counts:
            counts[severity] += 1
    return counts


def build_summary(findings: List[Dict[str, Any]], counts: Dict[str, int]) -> str:
    if not findings:
        return "No issues found by scanners or review agents."
    parts = [
        f"{counts['High']} high, {counts['Medium']} medium, {counts['Low']} low "
        f"severity findings from {len(findings)} total."
    ]
    top = sorted(
        findings,
        key=lambda f: {"High": 0, "Medium": 1, "Low": 2}.get(f.get("severity", "Low"), 3),
    )[:3]
    for finding in top:
        label = finding.get("file_line") or finding.get("file") or "unknown location"
        source = finding.get("agent") or finding.get("scanner") or "scanner"
        parts.append(f"- [{finding.get('severity')}] {label}: {finding.get('title', '')} ({source})")
    return "\n".join(parts)


def _persist_review(
    db: Session,
    *,
    user_id: int,
    trigger: str,
    repository: str,
    title: str,
    pr_number: Optional[int],
    head_sha: str,
    repo_id: Optional[int],
    job_id: Optional[int],
    findings: List[Dict[str, Any]],
    counts: Dict[str, int],
    metrics: Dict[str, Any],
    summary: str,
    status: str = "completed",
) -> Review:
    review = Review(
        user_id=user_id,
        repo_id=repo_id,
        trigger=trigger,
        repository=repository,
        title=title,
        pr_number=pr_number,
        head_sha=head_sha,
        status=status,
        summary=summary,
        counts=counts,
        metrics=metrics,
        finished_at=None if status == "failed" else utcnow(),
    )
    db.add(review)
    db.flush()
    for finding in findings:
        db.add(
            ReviewFinding(
                review_id=review.id,
                source=finding.get("source", "agent"),
                agent=finding.get("agent"),
                scanner=finding.get("scanner"),
                category=finding.get("category", ""),
                severity=finding.get("severity", "Low"),
                file=finding.get("file", ""),
                line=finding.get("line"),
                file_line=finding.get("file_line", ""),
                title=finding.get("title", ""),
                description=finding.get("description", ""),
                rule=finding.get("rule", ""),
                cwe=finding.get("cwe", ""),
                snippet=finding.get("snippet", ""),
                fix_code=finding.get("fix_code", ""),
                tests=finding.get("tests", []),
                confidence=finding.get("confidence"),
                corroborated=bool(finding.get("corroborated")),
            )
        )
    db.commit()
    db.refresh(review)
    return review


def _repo_context(db: Session, repo_id: Optional[int], diff: str) -> str:
    """Code-graph + RAG context from the indexed repository (empty when absent)."""
    if not repo_id:
        return ""
    from .code_graph import CodeGraph
    from .db_models import Repository

    repo = db.get(Repository, repo_id)
    if repo is None:
        return ""
    parts: List[str] = []
    graph = CodeGraph(**{k: repo.graph.get(k, []) for k in ("nodes", "edges")}) if repo.graph else None
    if graph and graph.nodes:
        from .code_graph import graph_summary

        parts.append(graph_summary(graph))
    chunks = repo_similarity_search(db, repo_id, extract_code_snippets(diff)[:4000] or diff[:4000])
    if chunks:
        lines = [
            f"- {c['path']}:{c['start_line']}-{c['end_line']}\n```{c.get('language', '')}\n{c['content'][:600]}\n```"
            for c in chunks
        ]
        parts.append("Similar code from this repository:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def run_review(
    db: Session,
    *,
    user_id: int,
    diff: str,
    rules_text: str = "",
    trigger: str = "manual",
    repository: str = "",
    title: str = "",
    pr_number: Optional[int] = None,
    head_sha: str = "",
    repo_id: Optional[int] = None,
    job_id: Optional[int] = None,
    depth: str = "standard",
    generate_fixes_enabled: bool = True,
) -> Review:
    """Full review pipeline; persists and returns a Review row."""
    started = time.time()
    cleaned = parse_diff(diff)
    scanner_hits = scan_added_lines(cleaned)
    logger.info("Pipeline start (trigger=%s, scanner_hits=%d, diff_chars=%d)",
                trigger, len(scanner_hits), len(cleaned))

    # Rules RAG (same chunker/retriever as the legacy path).
    rules_context = ""
    if rules_text.strip():
        chunks, _, index = build_index(rules_text)
        if chunks and index is not None:
            relevant = search_index(cleaned, chunks, index, top_k=MAX_RETRIEVAL_CHUNKS)
            added = extract_code_snippets(cleaned)
            if added.strip():
                seen = set(relevant)
                for chunk in search_index(added, chunks, index, top_k=3):
                    if chunk not in seen:
                        seen.add(chunk)
                        relevant.append(chunk)
            relevant = relevant[:MAX_RETRIEVAL_CHUNKS] or chunks[:FALLBACK_CHUNKS]
            rules_context = "\n\n---\n\n".join(relevant)

    repo_context = _repo_context(db, repo_id, cleaned)
    agent_context = "\n\n".join(x for x in (rules_context, repo_context) if x)

    agent_runs: List[AgentRun] = run_all_agents(
        cleaned, scanner_hits, repo_context=agent_context, depth=depth
    )

    agent_findings: List[AgentFinding] = []
    for run in agent_runs:
        if run.error:
            logger.warning("Agent %s failed: %s", run.agent, run.error)
        agent_findings.extend(run.findings)
    agent_findings = corroborate(agent_findings, scanner_hits)

    findings: List[Dict[str, Any]] = [f.to_dict() for f in agent_findings]
    findings.extend({**hit, "title": hit.get("title", hit.get("category", ""))} for hit in scanner_hits)

    # Fix + test generation for top findings (merged into findings dicts).
    if generate_fixes_enabled and findings:
        generate_fixes(findings, diff=cleaned, depth=depth)

    counts = _counts(findings)
    latency = round(time.time() - started, 3)
    total_cost = sum(run.cost_usd for run in agent_runs)
    models_used = sorted({run.model for run in agent_runs if run.model})
    tiers_used = sorted({run.decision.tier for run in agent_runs})
    review_metrics = {
        "latency_seconds": latency,
        "estimated_cost_usd": round(total_cost, 6),
        "models": models_used,
        "tiers": tiers_used,
        "routing": [
            {
                "task": run.decision.task,
                "tier": run.decision.tier,
                "model": run.decision.model,
                "complexity": run.decision.complexity,
                "reason": run.decision.reason,
            }
            for run in agent_runs
        ],
        "scanner_hits": len(scanner_hits),
        "agent_findings": len(agent_findings),
        "routing_table": routing_table(),
    }

    summary = build_summary(findings, counts)
    review = _persist_review(
        db,
        user_id=user_id,
        trigger=trigger,
        repository=repository,
        title=title,
        pr_number=pr_number,
        head_sha=head_sha,
        repo_id=repo_id,
        job_id=job_id,
        findings=findings,
        counts=counts,
        metrics=review_metrics,
        summary=summary,
    )

    METRICS.inc("reviews_total", trigger=trigger, status="completed")
    for finding in findings:
        METRICS.inc(
            "review_findings_total", severity=finding.get("severity", "Low"),
            source=finding.get("source", "agent"),
        )
    db.add(
        Event(
            event="review.completed",
            user_id=user_id,
            data={"review_id": review.id, "trigger": trigger, "repository": repository,
                  "findings": len(findings), "high": counts["High"]},
        )
    )
    db.commit()
    log_event("review.completed", review_id=review.id, duration_ms=int(latency * 1000))
    return review


def review_to_dict(review: Review, include_findings: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": review.id,
        "user_id": review.user_id,
        "repo_id": review.repo_id,
        "job_id": review.job_id,
        "trigger": review.trigger,
        "repository": review.repository,
        "title": review.title,
        "pr_number": review.pr_number,
        "head_sha": review.head_sha,
        "status": review.status,
        "summary": review.summary,
        "counts": review.counts,
        "metrics": review.metrics,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "finished_at": review.finished_at.isoformat() if review.finished_at else None,
    }
    if include_findings:
        data["findings"] = [
            {
                "id": f.id,
                "source": f.source,
                "agent": f.agent,
                "scanner": f.scanner,
                "category": f.category,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "file_line": f.file_line,
                "title": f.title,
                "description": f.description,
                "rule": f.rule,
                "cwe": f.cwe,
                "snippet": f.snippet,
                "fix_code": f.fix_code,
                "tests": f.tests or [],
                "confidence": f.confidence,
                "corroborated": f.corroborated,
            }
            for f in review.findings
        ]
    return data


# ── Legacy synchronous analyze (frozen response shape) ───────────────────────

def analyze_sync(diff: str, rules: str) -> Dict[str, Any]:
    """Legacy /api/analyze flow: TF-IDF RAG + single LLM call. Response shape
    (findings / screening_suggestions / error) is frozen by tests."""
    from .models import Finding, ScreeningSuggestion

    cleaned = parse_diff(diff)
    chunks, _, index = build_index(rules)
    if not chunks or index is None:
        return {"findings": [], "screening_suggestions": [],
                "error": "Could not process the rules document. Please check the format."}

    relevant = search_index(cleaned, chunks, index, top_k=MAX_RETRIEVAL_CHUNKS)
    added = extract_code_snippets(cleaned)
    if added.strip():
        seen = set(relevant)
        for chunk in search_index(added, chunks, index, top_k=3):
            if chunk not in seen:
                seen.add(chunk)
                relevant.append(chunk)
        relevant = relevant[:MAX_RETRIEVAL_CHUNKS]
    if not relevant:
        relevant = chunks[:FALLBACK_CHUNKS]

    findings: List[Finding] = call_llm(diff=cleaned, rules_chunks=relevant)
    suggestions = build_screening_suggestions(findings)
    return {
        "findings": findings,
        "screening_suggestions": suggestions,
        "error": None,
    }


def build_screening_suggestions(findings: List[Finding]) -> List:
    """Convert findings into a short, actionable human screening checklist."""
    from .models import ScreeningSuggestion

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
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity.value, 3))
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
