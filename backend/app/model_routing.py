"""Complexity-based model routing between cost tiers.

Every agent task is classified with a 0–1 complexity score (diff size, file
count, scanner hit density) and routed to either the *fast* tier (cheap model,
routine work) or the *deep* tier (premium model, complex diffs). Routing
decisions are recorded as metrics so cost/quality tradeoffs are observable.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any

from .config import (
    DEEP_TIER_THRESHOLD,
    MODEL_COST_DEEP_IN,
    MODEL_COST_DEEP_OUT,
    MODEL_COST_FAST_IN,
    MODEL_COST_FAST_OUT,
    MODEL_DEEP,
    MODEL_FAST,
)
from .observability import METRICS

# Cost per 1M tokens (USD), keyed by tier.
_TIER_COSTS: dict[str, tuple[float, float]] = {
    "fast": (MODEL_COST_FAST_IN, MODEL_COST_FAST_OUT),
    "deep": (MODEL_COST_DEEP_IN, MODEL_COST_DEEP_OUT),
}


def get_model_for_tier(tier: str) -> str:
    default = os.getenv("LLM_MODEL", "").strip()
    return {"fast": MODEL_FAST or default, "deep": MODEL_DEEP or default}.get(tier, default)


def tier_costs(model: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens for a model; tier table by selection."""
    if model and model == get_model_for_tier("deep") and get_model_for_tier("deep") != get_model_for_tier("fast"):
        return _TIER_COSTS["deep"]
    return _TIER_COSTS["fast"]


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    cost_in, cost_out = tier_costs(model)
    return (tokens_in * cost_in + tokens_out * cost_out) / 1_000_000


@dataclass
class RoutingDecision:
    task: str
    tier: str
    model: str
    complexity: float
    reason: str
    signals: dict[str, Any] = field(default_factory=dict)


def complexity_score(
    diff_text: str = "",
    files_count: int = 0,
    scanner_hits: int = 0,
    depth: str = "standard",
) -> float:
    """Weighted 0–1 score: diff volume, breadth, and scanner signal density."""
    chars = len(diff_text or "")
    size_component = min(1.0, math.log10(max(chars, 1)) / math.log10(200_000))
    breadth_component = min(1.0, files_count / 40)
    signal_component = min(1.0, scanner_hits / 10)
    score = 0.45 * size_component + 0.25 * breadth_component + 0.30 * signal_component
    if depth == "deep":
        score = min(1.0, score + 0.25)
    return round(score, 4)


def route(
    task: str,
    *,
    diff_text: str = "",
    files_count: int = 0,
    scanner_hits: int = 0,
    depth: str = "standard",
) -> RoutingDecision:
    score = complexity_score(diff_text, files_count, scanner_hits, depth)
    if score >= DEEP_TIER_THRESHOLD:
        tier, reason = "deep", f"complexity {score:.2f} >= threshold {DEEP_TIER_THRESHOLD}"
    elif task in ("fix_generation",) and depth == "deep":
        tier, reason = "deep", "fix generation on a deep review"
    else:
        tier, reason = "fast", f"complexity {score:.2f} below threshold {DEEP_TIER_THRESHOLD}"

    model = get_model_for_tier(tier)
    METRICS.inc("routing_decisions_total", tier=tier, task=task)
    return RoutingDecision(
        task=task,
        tier=tier,
        model=model,
        complexity=score,
        reason=reason,
        signals={"chars": len(diff_text or ""), "files": files_count, "scanner_hits": scanner_hits},
    )


def routing_table() -> dict[str, Any]:
    return {
        "threshold": DEEP_TIER_THRESHOLD,
        "tiers": {
            "fast": {
                "model": get_model_for_tier("fast"),
                "cost_per_1m_tokens_usd": {
                    "input": MODEL_COST_FAST_IN,
                    "output": MODEL_COST_FAST_OUT,
                },
            },
            "deep": {
                "model": get_model_for_tier("deep"),
                "cost_per_1m_tokens_usd": {
                    "input": MODEL_COST_DEEP_IN,
                    "output": MODEL_COST_DEEP_OUT,
                },
            },
        },
        "tasks": [
            {"task": "security_review", "default_tier": "routed by complexity"},
            {"task": "bug_review", "default_tier": "routed by complexity"},
            {"task": "quality_review", "default_tier": "fast"},
            {"task": "fix_generation", "default_tier": "routed; deep on deep reviews"},
        ],
    }
