"""Specialized LLM review agents.

Three agents (security, bug, code-quality) analyze a diff given deterministic
scanner hits and optional repository context (code-graph + RAG chunks). Each
agent returns structured findings via JSON-mode chat. A separate fix generator
proposes concrete fixes and regression tests for the top findings. Every call
is routed through model_routing so cost tracks complexity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .llm import LLMError, llm_chat, parse_json_object
from .model_routing import RoutingDecision, route
from .observability import METRICS

logger = logging.getLogger("codesentinal.agents")

MAX_DIFF_CHARS_FOR_AGENTS = 60_000
MAX_AGENT_FINDINGS = 20
MAX_FIX_FINDINGS = 5

AGENT_IDS = ("security", "bug", "quality")


@dataclass
class AgentFinding:
    agent: str
    severity: str          # High | Medium | Low
    category: str
    title: str
    description: str
    file: str = ""
    line: Optional[int] = None
    file_line: str = ""
    rule: str = ""
    cwe: str = ""
    snippet: str = ""
    fix_code: str = ""
    tests: List[str] = field(default_factory=list)
    confidence: float = 0.5
    corroborated: bool = False
    matched_scanners: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": "agent",
            "agent": self.agent,
            "scanner": None,
            "category": self.category,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "file_line": self.file_line or (f"{self.file}:{self.line}" if self.line else self.file),
            "title": self.title,
            "description": self.description,
            "rule": self.rule,
            "cwe": self.cwe,
            "snippet": self.snippet,
            "fix_code": self.fix_code,
            "tests": self.tests,
            "confidence": self.confidence,
            "corroborated": self.corroborated,
        }


@dataclass
class AgentRun:
    agent: str
    decision: RoutingDecision
    findings: List[AgentFinding]
    error: Optional[str] = None
    model: str = ""
    cost_usd: float = 0.0


_SEVERITY = {"high", "medium", "low"}


def _normalize_severity(value: Any, default: str = "Medium") -> str:
    text = str(value or "").strip().capitalize()
    return text if text in {"High", "Medium", "Low"} else default


def _coerce_agent_finding(agent: str, item: Any) -> Optional[AgentFinding]:
    if not isinstance(item, dict):
        return None
    title = str(item.get("title", "")).strip()[:300]
    description = str(item.get("description", item.get("risk", ""))).strip()[:2000]
    if not description and not title:
        return None
    line_raw = item.get("line")
    try:
        line = int(line_raw) if line_raw not in (None, "", 0) else None
    except (TypeError, ValueError):
        line = None
    file_path = str(item.get("file", item.get("file_line", ""))).strip()[:500]
    tests_raw = item.get("tests")
    tests = [str(t)[:4000] for t in tests_raw if str(t).strip()] if isinstance(tests_raw, list) else []
    try:
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    return AgentFinding(
        agent=agent,
        severity=_normalize_severity(item.get("severity")),
        category=str(item.get("category", "general")).strip()[:64],
        title=title or description.split("\n")[0][:120],
        description=description or title,
        file=file_path,
        line=line,
        file_line=str(item.get("file_line", "")).strip()[:300],
        rule=str(item.get("rule", "")).strip()[:2000],
        cwe=str(item.get("cwe", "")).strip()[:32],
        snippet=str(item.get("snippet", item.get("source_chunk", ""))).strip()[:4000],
        fix_code=str(item.get("fix_code", item.get("safer_code", ""))).strip()[:4000],
        tests=tests[:5],
        confidence=confidence,
    )


def _agent_messages(agent: str, diff: str, scanner_context: str, repo_context: str) -> List[dict]:
    profiles = {
        "security": (
            "You are the SecurityAgent of the CodeSentinal code review platform. "
            "You find exploitable vulnerabilities and policy violations: injection, "
            "broken auth, secrets, insecure crypto/TLS, access-control flaws.",
            "Report concrete security issues on the ADDED lines. Prefer precision over volume: "
            "only report issues you are confident about. Use 'correlates_with_scanner' hints when a "
            "deterministic scanner hit matches your finding.",
        ),
        "bug": (
            "You are the BugAgent of the CodeSentinal code review platform. "
            "You find functional defects: logic errors, unhandled edge cases, race conditions, "
            "resource leaks, error-handling gaps, breaking API changes.",
            "Report real defects that would cause incorrect behavior or crashes in production. "
            "Do not report style issues.",
        ),
        "quality": (
            "You are the QualityAgent of the CodeSentinal code review platform. "
            "You find maintainability problems: dead code, duplication, missing tests, "
            "unclear naming, risky refactors needed, performance footguns.",
            "Report only quality issues worth blocking or commenting on in review; keep it actionable.",
        ),
    }
    persona, instructions = profiles[agent]

    system = f"""{persona}
{instructions}

Return ONLY a JSON object: {{"findings": [...]}}. Each finding object must have:
- "severity": "High" | "Medium" | "Low"
- "category": short tag (e.g. "sql_injection", "error_handling")
- "title": one-line summary
- "description": what is wrong and why it matters
- "file": file path, "line": line number in the new file version (integer or null)
- "rule": the rule or best practice violated (may be empty)
- "cwe": CWE id when applicable (may be empty)
- "snippet": the problematic code
- "fix_code": suggested corrected code (may be empty)
- "confidence": 0.0-1.0"""
    if scanner_context:
        system += (
            "\n\nDeterministic scanner hits (pre-computed, high signal):\n"
            + scanner_context
            + "\nCorroborate these where your analysis agrees, and look for what they missed."
        )
    if repo_context:
        system += "\n\nRepository context (code graph + similar code from the indexed repo):\n" + repo_context

    user = f"## Diff to review\n```diff\n{diff}\n```\n\nReturn the findings JSON now."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_agent_response(agent: str, content: str) -> List[AgentFinding]:
    data = parse_json_object(content)
    if isinstance(data, dict):
        data = data.get("findings", data.get("results", []))
    if not isinstance(data, list):
        return []
    findings = []
    for item in data[:MAX_AGENT_FINDINGS]:
        finding = _coerce_agent_finding(agent, item)
        if finding:
            findings.append(finding)
    return findings


def run_agent(
    agent: str,
    diff: str,
    scanner_hits: Optional[List[Dict[str, Any]]] = None,
    repo_context: str = "",
    depth: str = "standard",
) -> AgentRun:
    """Run one specialized agent over the diff."""
    from .scanners import scanner_summary

    scanner_hits = scanner_hits or []
    if len(diff) > MAX_DIFF_CHARS_FOR_AGENTS:
        diff = diff[:MAX_DIFF_CHARS_FOR_AGENTS] + "\n... [diff truncated]"

    decision = route(
        f"{agent}_review",
        diff_text=diff,
        files_count=len({h.get("file") for h in scanner_hits if h.get("file")}),
        scanner_hits=len(scanner_hits),
        depth=depth,
    )

    if agent not in AGENT_IDS:
        return AgentRun(agent=agent, decision=decision, findings=[], error=f"Unknown agent {agent}")

    messages = _agent_messages(
        agent, diff, scanner_summary(scanner_hits) if scanner_hits else "", repo_context
    )
    try:
        result = llm_chat(messages, model=decision.model, temperature=0.1)
    except LLMError as exc:
        METRICS.inc("agent_findings_total", agent=agent, severity="error")
        return AgentRun(agent=agent, decision=decision, findings=[], error=str(exc), model=decision.model)

    findings = _parse_agent_response(agent, result.content)
    for finding in findings:
        METRICS.inc("agent_findings_total", agent=agent, severity=finding.severity)
    return AgentRun(
        agent=agent,
        decision=decision,
        findings=findings,
        model=result.model,
        cost_usd=result.cost_usd,
    )


def run_all_agents(
    diff: str,
    scanner_hits: List[Dict[str, Any]],
    repo_context: str = "",
    depth: str = "standard",
    agents: Optional[List[str]] = None,
) -> List[AgentRun]:
    """Run the agent fleet sequentially (the LLM client is synchronous)."""
    selected = agents or list(AGENT_IDS)
    return [
        run_agent(agent, diff, scanner_hits, repo_context, depth)
        for agent in selected
        if agent in AGENT_IDS
    ]


# ── Corroboration ────────────────────────────────────────────────────────────

def _overlap(agent_finding: AgentFinding, hit: Dict[str, Any]) -> bool:
    """A finding corroborates a scanner hit when file matches and either the
    line matches or the scanner category appears in the finding's text."""
    hit_file = hit.get("file", "")
    if agent_finding.file and hit_file and agent_finding.file != hit_file:
        return False
    if agent_finding.line and hit.get("line") and agent_finding.line == hit["line"]:
        return True
    category = (hit.get("category") or "").replace("_", " ")
    text = f"{agent_finding.category} {agent_finding.title} {agent_finding.description}".lower()
    return bool(category) and category in text


def corroborate(
    agent_findings: List[AgentFinding], scanner_hits: List[Dict[str, Any]]
) -> List[AgentFinding]:
    """Mark agent findings confirmed by scanner hits; boost their confidence."""
    if not scanner_hits:
        return agent_findings
    for finding in agent_findings:
        matched = [h.get("scanner", "") for h in scanner_hits if _overlap(finding, h)]
        if matched:
            finding.corroborated = True
            finding.matched_scanners = [m for m in matched if m][:3]
            finding.confidence = min(1.0, finding.confidence + 0.25)
    return agent_findings


# ── Fix + test generation ────────────────────────────────────────────────────

FIX_SYSTEM_PROMPT = """You are the FixAgent of the CodeSentinal code review platform.
Given code findings, produce minimal, correct fixes and regression tests.

Return ONLY a JSON object: {"fixes": [...]}. Each item must have:
- "file": the file path
- "line": the primary line number (integer or null)
- "fix_code": complete corrected code snippet (not a description)
- "tests": array of 0-2 regression test snippets (pytest or the file's test framework)
- "explanation": one or two sentences on the approach
Only include fixes you can make correct and self-contained."""


def generate_fixes(
    findings: List[Dict[str, Any]],
    diff: str = "",
    depth: str = "standard",
    max_findings: int = MAX_FIX_FINDINGS,
) -> List[Dict[str, Any]]:
    """Generate fix_code + tests for the highest-priority findings.

    Accepts and returns plain dicts (ReviewFinding-compatible). Never raises:
    on LLM failure the findings pass through with generated_fix=False.
    """
    targets = [
        f for f in findings
        if (f.get("severity") == "High" or f.get("corroborated"))
        and not f.get("fix_code")
    ][:max_findings]
    if not targets:
        return []

    decision = route(
        "fix_generation",
        diff_text=diff,
        files_count=len({f.get("file") for f in targets if f.get("file")}),
        scanner_hits=len(targets),
        depth=depth,
    )
    findings_block = "\n".join(
        f"{i + 1}. [{f.get('severity')}] {f.get('file_line') or (str(f.get('file')) + ':' + str(f.get('line')))}: "
        f"{f.get('title', '')} — {f.get('description', '')[:300]}\n   snippet: {f.get('snippet', '')[:200]}"
        for i, f in enumerate(targets)
    )
    context = f"\n\nDiff for reference:\n```diff\n{diff[:15000]}\n```" if diff else ""
    messages = [
        {"role": "system", "content": FIX_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"## Findings to fix\n{findings_block}{context}\n\nReturn the fixes JSON now.",
        },
    ]
    try:
        result = llm_chat(messages, model=decision.model, temperature=0.2)
    except LLMError as exc:
        logger.warning("Fix generation failed: %s", exc)
        return []

    data = parse_json_object(result.content)
    if isinstance(data, dict):
        data = data.get("fixes", [])
    if not isinstance(data, list):
        return []

    fixes: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("file", "")).strip()[:500]
        line_raw = item.get("line")
        try:
            line = int(line_raw) if line_raw not in (None, "", 0) else None
        except (TypeError, ValueError):
            line = None
        fix_code = str(item.get("fix_code", "")).strip()[:4000]
        tests = [str(t).strip()[:4000] for t in item.get("tests", []) if str(t).strip()][:2]
        if not fix_code:
            continue
        fixes.append(
            {
                "file": file_path,
                "line": line,
                "fix_code": fix_code,
                "tests": tests,
                "explanation": str(item.get("explanation", "")).strip()[:1000],
                "generated_fix": True,
            }
        )

    # Attach fixes back onto the matching findings by file (+line when given).
    for fix in fixes:
        for finding in targets:
            if fix["file"] and finding.get("file") == fix["file"]:
                if fix["line"] is None or finding.get("line") in (None, fix["line"]):
                    finding["fix_code"] = fix["fix_code"]
                    if fix["tests"]:
                        finding["tests"] = fix["tests"]
                    finding["generated_fix"] = True
                    break
    METRICS.inc("routing_decisions_total", tier=decision.tier, task="fix_generation")
    return fixes
