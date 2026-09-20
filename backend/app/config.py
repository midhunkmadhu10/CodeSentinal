"""Centralized application configuration and request limits.

This module is the single source of truth for size limits and tuning knobs so
that models, routes, and the LLM client all agree on the same values.
"""

import os

# ── Request size limits (UTF-8 bytes) ────────────────────────────────────────
MAX_DIFF_BYTES = 500 * 1024        # ~500 KB of diff text per analysis request
MAX_RULES_BYTES = 1024 * 1024      # ~1 MB of rules / policy text
MAX_GITHUB_TOKEN_CHARS = 256
MAX_REPOSITORY_FIELD_CHARS = 200

# ── Analysis behavior ────────────────────────────────────────────────────────
MAX_FINDINGS = 50                  # cap on findings accepted from the LLM
MAX_RETRIEVAL_CHUNKS = 5           # rule chunks sent to the LLM
FALLBACK_CHUNKS = 2                # chunks used when retrieval matches nothing
MAX_PROMPT_DIFF_CHARS = 100_000    # truncate oversized diffs before prompting

# ── LLM client ───────────────────────────────────────────────────────────────
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
