"""LLM client: calls an OpenAI-compatible endpoint and parses findings.

The API key, endpoint, and model come exclusively from server-side environment
variables — never from the request. Raw model output and secrets are never
logged; diagnostics are limited to sizes, counts, and exception types.
"""

import json
import logging
import os
from typing import Any, List, Tuple

from openai import OpenAI

from .config import LLM_MAX_TOKENS, LLM_TIMEOUT_SECONDS, MAX_FINDINGS, MAX_PROMPT_DIFF_CHARS
from .models import Finding, Severity

logger = logging.getLogger("codesentinal.llm")


class LLMError(ValueError):
    """LLM provider failure; the message is safe to return to clients."""


def get_llm_config() -> Tuple[str, str, str]:
    endpoint = os.getenv("LLM_ENDPOINT", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    missing = [
        name
        for name, value in (
            ("LLM_ENDPOINT", endpoint),
            ("LLM_MODEL", model),
            ("LLM_API_KEY", api_key),
        )
        if not value
    ]
    if missing:
        raise LLMError(
            "LLM is not configured. Set " + ", ".join(missing) + " in the backend environment."
        )
    return endpoint, model, api_key


def build_analysis_prompt(diff: str, rules_chunks: List[str]) -> Tuple[str, str]:
    """Build the system + user prompt for the LLM."""
    rules_context = "\n\n---\n\n".join(
        f"Rule Chunk {i + 1}:\n{chunk}" for i, chunk in enumerate(rules_chunks)
    )

    system_prompt = """You are a security code reviewer. Analyze the provided code diff against the given security rules.

Return your analysis as a JSON object with a single "findings" key whose value is an array. Each object in the array must have exactly these fields:
- "severity": "High", "Medium", or "Low"
- "file_line": the file path and line number where the issue is found (e.g. "src/auth.ts:42")
- "risk": a clear description of what the security risk is
- "rule_violation": which rule is violated and why
- "safer_code": a code snippet showing how to fix the issue
- "source_chunk": the exact text from the rule chunks that applies to this finding

If no issues are found, return {"findings": []}.

IMPORTANT: You MUST output ONLY valid JSON. No extra text, no markdown formatting, no explanation outside the JSON."""

    user_prompt = f"""## Code Diff to Review
```
{diff}
```

## Relevant Security Rules
{rules_context}

Analyze the diff against these rules and return the findings as JSON."""

    return system_prompt, user_prompt


def _provider_error(exc: Exception) -> LLMError:
    """Map an OpenAI SDK exception to a safe, client-facing LLMError."""
    import openai

    if isinstance(exc, openai.APITimeoutError):
        return LLMError("The LLM provider timed out. Please try again.")
    if isinstance(exc, openai.APIConnectionError):
        return LLMError("Could not reach the LLM provider. Check LLM_ENDPOINT and network connectivity.")
    if isinstance(exc, openai.RateLimitError):
        return LLMError("The LLM provider rate limit was reached. Please wait a moment and retry.")
    if isinstance(exc, openai.AuthenticationError):
        return LLMError("The LLM provider rejected the configured API key. Check LLM_API_KEY on the backend.")
    if isinstance(exc, openai.BadRequestError):
        return LLMError("The LLM provider rejected the request. Check LLM_MODEL and LLM_ENDPOINT configuration.")
    if isinstance(exc, openai.APIStatusError):
        return LLMError(f"The LLM provider returned an error (HTTP {exc.status_code}).")
    logger.warning("Unexpected LLM error: %s: %s", type(exc).__name__, exc)
    return LLMError("The LLM request failed unexpectedly. Check the backend logs.")


def _extract_json(content: str) -> Any:
    """Extract JSON from model output, handling markdown fences and stray text."""
    stripped = content.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        last_fence = stripped.rfind("```")
        if last_fence > first_newline:
            stripped = stripped[first_newline + 1:last_fence].strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Look for a JSON object or array embedded in surrounding prose.
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = stripped.find(start_char)
        end = stripped.rfind(end_char)
        if 0 <= start < end:
            try:
                return json.loads(stripped[start:end + 1])
            except json.JSONDecodeError:
                continue

    return None


def _coerce_finding(item: Any) -> Finding | None:
    """Validate one finding from the model; returns None for unusable items."""
    if not isinstance(item, dict):
        return None

    raw_severity = str(item.get("severity", "")).strip().capitalize()
    try:
        severity = Severity(raw_severity)
    except ValueError:
        return None

    def _text(key: str, limit: int) -> str:
        return str(item.get(key, "")).strip()[:limit]

    return Finding(
        severity=severity,
        file_line=_text("file_line", 300) or "unknown",
        risk=_text("risk", 2000) or "No description provided.",
        rule_violation=_text("rule_violation", 2000) or "No rule reference provided.",
        safer_code=_text("safer_code", 4000) or "No suggestion provided.",
        source_chunk=_text("source_chunk", 4000) or "No source provided.",
    )


def _parse_findings(content: str) -> List[Finding]:
    data = _extract_json(content)
    if data is None:
        # Log shape only — never the raw model output, which may embed diff text.
        logger.warning("LLM response was not parseable as JSON (length=%d)", len(content))
        raise LLMError("The model response could not be parsed. Please try again.")

    if isinstance(data, dict):
        data = data.get("findings", data.get("results", []))
    if not isinstance(data, list):
        logger.warning("LLM response JSON was not a findings array (type=%s)", type(data).__name__)
        raise LLMError("The model response could not be parsed. Please try again.")

    findings: List[Finding] = []
    dropped = 0
    for item in data[:MAX_FINDINGS]:
        finding = _coerce_finding(item)
        if finding is None:
            dropped += 1
        else:
            findings.append(finding)
    if dropped:
        logger.info("Dropped %d malformed finding(s) from LLM response", dropped)
    if len(data) > MAX_FINDINGS:
        logger.info("Truncated findings from %d to %d", len(data), MAX_FINDINGS)
    return findings


def call_llm(diff: str, rules_chunks: List[str]) -> List[Finding]:
    """Call the configured OpenAI-compatible API and return validated findings."""
    endpoint, model, api_key = get_llm_config()

    if len(diff) > MAX_PROMPT_DIFF_CHARS:
        logger.warning("Diff truncated for prompt: %d -> %d chars", len(diff), MAX_PROMPT_DIFF_CHARS)
        diff = diff[:MAX_PROMPT_DIFF_CHARS] + "\n... [diff truncated]"

    client = OpenAI(
        base_url=endpoint,
        api_key=api_key,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=1,
    )
    system_prompt, user_prompt = build_analysis_prompt(diff, rules_chunks)

    # Prefer structured output (JSON mode); retry without it for providers
    # that reject the response_format parameter.
    content = None
    for use_json_mode in (True, False):
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": LLM_MAX_TOKENS,
        }
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = client.chat.completions.create(**kwargs)
            content = (response.choices[0].message.content or "").strip()
            break
        except Exception as exc:
            if use_json_mode and type(exc).__name__ == "BadRequestError":
                logger.info("Provider rejected response_format; retrying without JSON mode")
                continue
            raise _provider_error(exc) from None

    if not content:
        logger.warning("LLM returned an empty response (model=%s)", model)
        raise LLMError("The model returned an empty response. Please try again.")

    logger.info("LLM response received (chars=%d, model=%s)", len(content), model)
    return _parse_findings(content)


# ── Typed chat API used by agents (with usage/cost accounting) ───────────────

import time
from dataclasses import dataclass

from .config import EMBEDDINGS_ENDPOINT, EMBEDDINGS_MODEL, INDEX_EMBED_BATCH
from .model_routing import estimate_cost
from .observability import METRICS


@dataclass
class ChatResult:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        return estimate_cost(self.model, self.prompt_tokens, self.completion_tokens)


def llm_chat(
    messages: List[dict],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int | None = None,
    json_mode: bool = True,
) -> ChatResult:
    """One chat completion with automatic usage/cost/latency accounting."""
    endpoint, configured_model, api_key = get_llm_config()
    model = model or configured_model
    client = OpenAI(
        base_url=endpoint, api_key=api_key, timeout=LLM_TIMEOUT_SECONDS, max_retries=1
    )

    started = time.time()
    content = None
    usage = None
    for use_json_mode in ((True, False) if json_mode else (False,)):
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or LLM_MAX_TOKENS,
        }
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = client.chat.completions.create(**kwargs)
            content = (response.choices[0].message.content or "").strip()
            usage = getattr(response, "usage", None)
            break
        except Exception as exc:
            if use_json_mode and type(exc).__name__ == "BadRequestError":
                logger.info("Provider rejected response_format; retrying without JSON mode")
                continue
            METRICS.inc("llm_calls_total", model=model, outcome="error")
            raise _provider_error(exc) from None

    latency = time.time() - started
    METRICS.observe("llm_latency_seconds", latency, model=model)
    if not content:
        METRICS.inc("llm_calls_total", model=model, outcome="empty")
        raise LLMError("The model returned an empty response. Please try again.")

    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    cost = estimate_cost(model, prompt_tokens, completion_tokens)
    METRICS.inc("llm_calls_total", model=model, outcome="ok")
    if prompt_tokens or completion_tokens:
        METRICS.inc("llm_tokens_total", prompt_tokens, model=model, direction="input")
        METRICS.inc("llm_tokens_total", completion_tokens, model=model, direction="output")
        METRICS.inc("llm_cost_usd_total", round(cost, 6), model=model)

    logger.info(
        "LLM chat complete (model=%s, chars=%d, tokens=%d/%d, cost=$%.6f, %.1fs)",
        model, len(content), prompt_tokens, completion_tokens, cost, latency,
    )
    return ChatResult(
        content=content,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def parse_json_object(content: str) -> Any:
    """Public defensive JSON extraction (markdown fences, embedded objects)."""
    return _extract_json(content)


# ── Embeddings (optional; enables vector RAG when configured) ────────────────

def embeddings_configured() -> bool:
    return bool(EMBEDDINGS_MODEL.strip()) and bool(
        EMBEDDINGS_ENDPOINT.strip() or os.getenv("LLM_ENDPOINT", "").strip()
    )


def embed_texts(texts: List[str]) -> List[List[float]] | None:
    """Embed texts via an OpenAI-compatible /embeddings endpoint.

    Returns None when embeddings are not configured or the call fails —
    callers fall back to TF-IDF retrieval. Never raises.
    """
    if not embeddings_configured() or not texts:
        return None
    from openai import OpenAI as _OpenAI

    client = _OpenAI(
        base_url=EMBEDDINGS_ENDPOINT or os.getenv("LLM_ENDPOINT", "").strip(),
        api_key=os.getenv("LLM_API_KEY", "").strip() or "missing",
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=1,
    )
    vectors: List[List[float]] = []
    try:
        for start in range(0, len(texts), INDEX_EMBED_BATCH):
            batch = [t[:8000] or " " for t in texts[start:start + INDEX_EMBED_BATCH]]
            response = client.embeddings.create(model=EMBEDDINGS_MODEL, input=batch)
            batch_vectors = sorted(response.data, key=lambda item: item.index)
            vectors.extend([list(item.embedding) for item in batch_vectors])
        METRICS.inc("embed_calls_total", outcome="ok")
        return vectors
    except Exception as exc:
        METRICS.inc("embed_calls_total", outcome="error")
        logger.warning(
            "Embedding call failed (%s: %s); falling back to TF-IDF retrieval",
            type(exc).__name__,
            exc,
        )
        return None
