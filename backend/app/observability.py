"""Observability: metrics registry, Prometheus rendering, structured logging.

Hand-rolled on purpose — no extra dependencies. Counters and histograms are
thread-safe and renderable both as Prometheus text (`/api/metrics`) and as a
JSON snapshot for the dashboard. Log records are emitted as single-line JSON
so any log shipper can parse them without regexes.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

_MAX_SAMPLES = 512  # per named histogram — enough for p95 without growth


def _fmt_label_value(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_key(name: str, labels: dict[str, Any]) -> str:
    if not labels:
        return name
    inner = ",".join(f'{k}="{_fmt_label_value(v)}"' for k, v in sorted(labels.items()))
    return f"{name}{{{inner}}}"


class MetricsRegistry:
    """Process-wide counters + histogram samples with Prometheus output."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._help: dict[str, str] = {}
        self._started = time.time()

    def describe(self, name: str, help_text: str) -> None:
        self._help[name] = help_text

    def inc(self, name: str, value: float = 1.0, **labels: Any) -> None:
        with self._lock:
            self._counters[_render_key(name, labels)] += value

    def observe(self, name: str, value: float, **labels: Any) -> None:
        with self._lock:
            samples = self._histograms[_render_key(name, labels)]
            samples.append(float(value))
            if len(samples) > _MAX_SAMPLES:
                del samples[: len(samples) - _MAX_SAMPLES]

    @staticmethod
    def _quantile(sorted_samples: list[float], q: float) -> float:
        if not sorted_samples:
            return 0.0
        idx = min(len(sorted_samples) - 1, max(0, int(round(q * (len(sorted_samples) - 1)))))
        return sorted_samples[idx]

    def snapshot(self) -> dict[str, Any]:
        """JSON-friendly view for the dashboard: counters + histogram summaries."""
        with self._lock:
            counters = dict(self._counters)
            histograms: dict[str, Any] = {}
            for key, samples in self._histograms.items():
                if not samples:
                    continue
                ordered = sorted(samples)
                histograms[key] = {
                    "count": len(ordered),
                    "avg": round(sum(ordered) / len(ordered), 4),
                    "p50": round(self._quantile(ordered, 0.50), 4),
                    "p95": round(self._quantile(ordered, 0.95), 4),
                    "max": round(ordered[-1], 4),
                }
            return {
                "uptime_seconds": round(time.time() - self._started, 1),
                "counters": {k: round(v, 4) for k, v in sorted(counters.items())},
                "histograms": histograms,
            }

    def render_prometheus(self) -> str:
        with self._lock:
            counters = dict(self._counters)
            histograms = {k: list(v) for k, v in self._histograms.items()}
            help_texts = dict(self._help)
        lines: list[str] = [
            "# HELP codesentinal_uptime_seconds Process uptime in seconds.",
            "# TYPE codesentinal_uptime_seconds gauge",
            f"codesentinal_uptime_seconds {round(time.time() - self._started, 1)}",
        ]
        for key, value in sorted(counters.items()):
            base = key.split("{", 1)[0]
            if base in help_texts and f"# HELP {base}" not in "\n".join(lines):
                lines.append(f"# HELP {base} {help_texts[base]}")
                lines.append(f"# TYPE {base} counter")
            lines.append(f"{key} {round(value, 4)}")
        for key, samples in sorted(histograms.items()):
            if not samples:
                continue
            ordered = sorted(samples)
            lines.append(f"# TYPE {key} summary")
            for q in (0.5, 0.95):
                lines.append(
                    f"{key}{{quantile=\"{q}\"}} {round(self._quantile(ordered, q), 4)}"
                )
            lines.append(f"{key}_count {len(ordered)}")
            lines.append(f"{key}_sum {round(sum(ordered), 4)}")
        return "\n".join(lines) + "\n"


METRICS = MetricsRegistry()

METRICS.describe("http_requests_total", "HTTP requests processed by route and status.")
METRICS.describe("http_request_duration_seconds", "HTTP request latency in seconds.")
METRICS.describe("llm_calls_total", "LLM chat completion calls by model and outcome.")
METRICS.describe("llm_tokens_total", "LLM prompt/completion tokens by model.")
METRICS.describe("llm_cost_usd_total", "Estimated LLM spend in USD by model.")
METRICS.describe("llm_latency_seconds", "LLM call latency in seconds by model.")
METRICS.describe("embed_calls_total", "Embedding API calls by outcome.")
METRICS.describe("scanner_findings_total", "Deterministic scanner hits by scanner.")
METRICS.describe("agent_findings_total", "Agent findings by agent and severity.")
METRICS.describe("reviews_total", "Completed reviews by trigger and status.")
METRICS.describe("review_findings_total", "Persisted review findings by severity and source.")
METRICS.describe("jobs_total", "Background jobs by type and terminal status.")
METRICS.describe("routing_decisions_total", "Model routing decisions by tier and task.")
METRICS.describe("webhook_events_total", "GitHub webhook events by event and disposition.")


# ── Structured JSON logging ──────────────────────────────────────────────────

class JsonLogFormatter(logging.Formatter):
    """Single-line JSON logs; messages that are already JSON objects merge in."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        for key in ("event_code", "repo", "job_id", "review_id", "user_id", "model", "duration_ms"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(level: str | None = None) -> None:
    root = logging.getLogger()
    root.setLevel((level or "INFO").upper())
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers = [handler]
    for noisy in ("httpx", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger = logging.getLogger("codesentinal.events")
    extra = {"event_code": event, **fields}
    logger.log(level, event, extra=extra)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(math.ceil(q * len(ordered))) - 1))
    return ordered[idx]
