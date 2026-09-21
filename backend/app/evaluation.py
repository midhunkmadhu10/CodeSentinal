"""Evaluation suite for the review pipeline.

Golden cases pair a diff with the findings a correct review must produce.
Scores are precision/recall/F1 over (file, line-or-0, category) matches —
category may be a list of acceptable aliases. Results persist as EvalRun rows
and are exposed via /api/evals so quality can be tracked over time.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from .agents import AGENT_IDS, run_all_agents
from .db_models import EvalRun
from .llm import LLMError
from .observability import METRICS
from .scanners import scan_added_lines
from .utils import parse_unified_diff, ADDED

logger = logging.getLogger("codesentinal.evals")

MAX_EVAL_FINDINGS = 20

# Import golden cases from fixtures (in backend/evals/fixtures.py)
try:
    from ..evals.fixtures import ALL_CASES as GOLDEN_CASES
except ImportError:
    # Fallback: minimal golden cases if fixtures not available
    GOLDEN_CASES: List[Dict[str, Any]] = [
        {
            "id": "sqli_fstring",
            "description": "f-string SQL query is detected",
            "diff": """diff --git a/app/users.py b/app/users.py
--- a/app/users.py
+++ b/app/users.py
@@ -1,4 +1,4 @@
 def get_user(conn, user_id):
-    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
+    return conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
""",
            "expected": [{"file": "app/users.py", "line": 4, "categories": ["sql_injection"]}],
            "llm_optional": True,
        },
        {
            "id": "clean_diff",
            "description": "benign change produces no findings",
            "diff": """diff --git a/app/math.py b/app/math.py
--- a/app/math.py
+++ b/app/math.py
@@ -1,2 +1,4 @@
 def add(a, b):
-    return a + b
+    \"\"\"Return the sum of two numbers.\"\"\"
+    return a + b
""",
            "expected": [],
            "llm_optional": True,
        },
    ]


# ── Matching ─────────────────────────────────────────────────────────────────

def _added_lines(diff: str) -> Set[Tuple[str, int]]:
    result: Set[Tuple[str, int]] = set()
    for f in parse_unified_diff(diff):
        for hunk in f.hunks:
            for dl in hunk.lines:
                if dl.kind == ADDED and dl.new_lineno:
                    result.add((f.path, dl.new_lineno))
    return result


def _finding_key(finding: Dict[str, Any]) -> Tuple[str, int]:
    file_path = finding.get("file") or ""
    line = finding.get("line") or 0
    if not file_path:
        file_line = finding.get("file_line") or ""
        file_path = file_line.rsplit(":", 1)[0] if ":" in file_line else file_line
    return file_path, line


def score_case(
    produced: List[Dict[str, Any]], expected: List[Dict[str, Any]]
) -> Tuple[float, float, float, List[Dict[str, Any]]]:
    """Precision/recall/F1 for one case; returns (p, r, f1, misses)."""
    if not expected:
        precision = 1.0 if not produced else 0.0
        return precision, 1.0, precision, []
    added = _added_lines_from(produced)
    matched_expected: Set[int] = set()
    matched_produced: Set[int] = set()
    for ei, exp in enumerate(expected):
        for pi, finding in enumerate(produced):
            if pi in matched_produced:
                continue
            file_path, line = _finding_key(finding)
            if file_path != exp["file"]:
                continue
            categories = exp["categories"]
            category = (finding.get("category") or "").lower()
            # Agent findings matched by file + line on an added line count even
            # with a generic category; scanner findings must match category.
            line_ok = line == exp["line"] or (line == 0 and exp["line"] in added)
            if not line_ok:
                continue
            if category and category not in categories and finding.get("source") == "scanner":
                continue
            if not category and finding.get("source") != "agent":
                continue
            matched_expected.add(ei)
            matched_produced.add(pi)
            break
    precision = len(matched_produced) / len(produced) if produced else 0.0
    recall = len(matched_expected) / len(expected)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    misses = [
        {"case_miss": "unmatched_produced", "file": _finding_key(f)[0], "line": _finding_key(f)[1]}
        for i, f in enumerate(produced) if i not in matched_produced
    ]
    return round(precision, 4), round(recall, 4), round(f1, 4), misses


def _added_lines_from(produced: List[Dict[str, Any]]) -> Set[int]:
    lines: Set[int] = set()
    for finding in produced:
        line = finding.get("line")
        if line:
            lines.add(line)
    return lines


def _run_scan_only(diff: str) -> List[Dict[str, Any]]:
    return scan_added_lines(diff)


def _run_full(diff: str, depth: str = "standard") -> List[Dict[str, Any]]:
    scanner_hits = scan_added_lines(diff)
    runs = run_all_agents(diff, scanner_hits, depth=depth)
    findings: List[Dict[str, Any]] = [f.to_dict() for run in runs for f in run.findings]
    findings.extend({**hit, "title": hit.get("category", "")} for hit in scanner_hits)
    return findings[:MAX_EVAL_FINDINGS]


def run_evaluation(db: Session, *, use_llm: bool = True, notes: str = "") -> EvalRun:
    """Execute the golden cases and persist an EvalRun."""
    started = time.time()
    per_case: Dict[str, Any] = {}
    all_p: List[float] = []
    all_r: List[float] = []
    all_f1: List[float] = []
    llm_errors = 0

    for case in GOLDEN_CASES:
        try:
            produced = _run_full(case["diff"]) if use_llm else _run_scan_only(case["diff"])
        except LLMError as exc:
            logger.warning("Eval case %s LLM failure: %s", case["id"], exc)
            if not case.get("llm_optional"):
                produced = []
            else:
                produced = _run_scan_only(case["diff"])
                llm_errors += 1
        p, r, f1, misses = score_case(produced, case["expected"])
        per_case[case["id"]] = {
            "description": case["description"],
            "expected": len(case["expected"]),
            "produced": len(produced),
            "precision": p,
            "recall": r,
            "f1": f1,
            "misses": misses[:5],
        }
        all_p.append(p)
        all_r.append(r)
        all_f1.append(f1)

    macro = {
        "precision": round(sum(all_p) / len(all_p), 4) if all_p else 0.0,
        "recall": round(sum(all_r) / len(all_r), 4) if all_r else 0.0,
        "f1": round(sum(all_f1) / len(all_f1), 4) if all_f1 else 0.0,
        "cases": len(GOLDEN_CASES),
        "llm_errors": llm_errors,
        "use_llm": use_llm,
        "duration_seconds": round(time.time() - started, 2),
    }
    run = EvalRun(scores=macro, details={"cases": per_case}, notes=notes)
    db.add(run)
    db.commit()
    db.refresh(run)
    METRICS.inc("jobs_total", type="evaluation", status="ok")
    logger.info("Evaluation complete: F1=%.3f (llm=%s)", macro["f1"], use_llm)
    return run
