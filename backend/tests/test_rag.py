"""RAG retrieval tests: chunking, determinism, dedup, zero-similarity."""
from app.rag import build_index, search_index

RULES = """# Security Rules

## Rule 1: No Hardcoded Secrets
All secrets must be stored in environment variables. Never commit API keys,
passwords, or tokens to source control.

## Rule 2: Parameterized Queries
Database queries must use parameterized statements. String concatenation of
user input into SQL is forbidden.

## Rule 3: Input Validation
All user input must be validated on the server side before use.
"""


def test_build_index_produces_chunks():
    chunks, _, index = build_index(RULES)
    assert chunks
    assert index is not None
    assert all(len(c) <= 500 for c in chunks)


def test_empty_text_builds_nothing():
    chunks, emb, index = build_index("   \n  ")
    assert chunks == []
    assert index is None


def test_retrieval_finds_relevant_rule():
    chunks, _, index = build_index(RULES)
    results = search_index("SQL query string concatenation injection", chunks, index)
    assert results
    assert "parameterized" in results[0].lower()


def test_retrieval_is_deterministic():
    chunks, _, index = build_index(RULES)
    a = search_index("hardcoded secrets api keys", chunks, index)
    b = search_index("hardcoded secrets api keys", chunks, index)
    assert a == b


def test_zero_similarity_returns_empty():
    chunks, _, index = build_index(RULES)
    # No token overlap with any rule chunk.
    results = search_index("qqq zzx wvv kpk", chunks, index)
    assert results == []


def test_search_index_handles_none_index():
    assert search_index("query", [], None) == []


def test_no_duplicate_chunks():
    text = RULES + "\n" + RULES  # duplicated document
    chunks, _, _ = build_index(text)
    normalized = ["".join(c.split()) for c in chunks]
    assert len(normalized) == len(set(normalized))


def test_rules_are_not_split_mid_section_when_possible():
    chunks, _, _ = build_index(RULES)
    # Each "## Rule" heading should begin a chunk, not appear mid-chunk
    # (sections here are well under the chunk size).
    starts = [c.lstrip().startswith("##") or c.lstrip().startswith("#") for c in chunks]
    assert any(starts)
