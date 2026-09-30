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
MAX_REPO_RETRIEVAL_CHUNKS = 6      # code chunks pulled from a repo index
FALLBACK_CHUNKS = 2                # chunks used when retrieval matches nothing
MAX_PROMPT_DIFF_CHARS = 100_000    # truncate oversized diffs before prompting
MAX_GRAPH_SYMBOLS = 40             # code-graph symbols included in agent context
MAX_FIX_GENERATIONS = 5            # findings that get generated fixes + tests

# ── LLM client ────────────────────────────────────────────── ────────────────
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ── Database ─────────────────────────────────────────────────────────────────
# Postgres (pgvector-enabled image in docker-compose) in production; SQLite
# fallback keeps local dev and CI zero-config. Embeddings are always stored as
# JSON in code_chunks; on Postgres an auxiliary `chunk_vectors` table with a
# native vector column accelerates similarity search when embeddings exist.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./codesentinal.db")
EMBEDDING_DIM = _int_env("EMBEDDING_DIM", 768)

# ── Auth ─────────────────────────────────────────────────────────────────────
# JWT (HS256). When JWT_SECRET is unset a random per-process secret is used —
# tokens then survive only one process lifetime. Set it in production.
JWT_EXPIRES_HOURS = _float_env("JWT_EXPIRES_HOURS", 12.0)

# ── Embeddings (optional; falls back to TF-IDF retrieval) ────────────────────
EMBEDDINGS_ENDPOINT = os.getenv("EMBEDDINGS_ENDPOINT", "").strip()
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "").strip()

# ── Model routing ────────────────────────────────────────────────────────────
# Two tiers: fast (cheap, routine reviews) and deep (complex diffs). Both
# default to LLM_MODEL unless overridden. Costs are USD per 1M tokens and are
# estimates used for observability only.
MODEL_FAST = os.getenv("MODEL_FAST", "").strip()
MODEL_DEEP = os.getenv("MODEL_DEEP", "").strip()
DEEP_TIER_THRESHOLD = _float_env("DEEP_TIER_THRESHOLD", 0.55)
MODEL_COST_FAST_IN = _float_env("MODEL_COST_FAST_IN", 0.10)
MODEL_COST_FAST_OUT = _float_env("MODEL_COST_FAST_OUT", 0.40)
MODEL_COST_DEEP_IN = _float_env("MODEL_COST_DEEP_IN", 1.25)
MODEL_COST_DEEP_OUT = _float_env("MODEL_COST_DEEP_OUT", 5.00)

# ── Repository indexing ──────────────────────────────────────────────────────
INDEX_MAX_FILES = _int_env("INDEX_MAX_FILES", 1500)
INDEX_MAX_FILE_BYTES = _int_env("INDEX_MAX_FILE_BYTES", 200_000)
CODE_CHUNK_LINES = _int_env("CODE_CHUNK_LINES", 60)
CODE_CHUNK_OVERLAP_LINES = _int_env("CODE_CHUNK_OVERLAP_LINES", 8)
CODE_CHUNK_MAX_CHARS = _int_env("CODE_CHUNK_MAX_CHARS", 4000)
INDEX_EMBED_BATCH = _int_env("INDEX_EMBED_BATCH", 64)

INDEX_SKIP_DIRS = {
    ".git", ".github", ".idea", ".vscode", "__pycache__", "node_modules",
    "venv", ".venv", "env", "dist", "build", "out", "target", "vendor",
    ".next", "coverage", ".tox", "site-packages", "migrations",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".rs", ".swift", ".kt",
    ".scala", ".sh", ".bash", ".sql", ".toml", ".yaml", ".yml", ".json",
    ".md", ".txt", ".cfg", ".ini", ".env", ".html", ".css", ".scss",
}

# ── Review pipeline ──────────────────────────────────────────────────────────
REVIEW_FETCH_CONTENT_FILES = _int_env("REVIEW_FETCH_CONTENT_FILES", 25)
REVIEW_MAX_FILE_BYTES = _int_env("REVIEW_MAX_FILE_BYTES", 100_000)
MAX_PR_COMMENT_CHARS = 6000

# ── Background worker ────────────────────────────────────────────────────────
WORKER_ENABLED = _bool_env("WORKER_ENABLED", True)
WORKER_POLL_SECONDS = _float_env("WORKER_POLL_SECONDS", 1.0)
WORKER_CONCURRENCY = _int_env("WORKER_CONCURRENCY", 2)
JOB_MAX_ATTEMPTS = _int_env("JOB_MAX_ATTEMPTS", 3)

# ── GitHub automation ────────────────────────────────────────────────────────
# GITHUB_TOKEN: optional bot/installation token used for webhook-triggered
# reviews and posting PR comments. GITHUB_WEBHOOK_SECRET: HMAC secret for the
# webhook endpoint; the endpoint fails closed when it is unset.
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
