"""Retrieval-Augmented Generation over the rules document.

Deterministic TF-IDF + cosine similarity with no heavy dependencies. Chunking
is section-aware: markdown headings start new chunks so a rule is never split
mid-section unless the section alone exceeds the chunk size. Identical chunks
are de-duplicated, and search returns nothing when no chunk shares any token
with the query (zero-similarity) instead of returning arbitrary chunks.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, List, Tuple

CHUNK_SIZE = 400
OVERLAP = 80

_HEADING_RE = re.compile(r"^#{1,6}\s+")


# ── Text helpers ─────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def _split_sections(text: str) -> List[str]:
    """Split text into sections at markdown headings and blank lines."""
    sections: List[str] = []
    current: List[str] = []

    for line in text.splitlines():
        if _HEADING_RE.match(line) and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current).strip())

    return [s for s in sections if s]


def _hard_split(section: str, chunk_size: int, overlap: int) -> List[str]:
    """Split an oversized section on sentence boundaries, hard-wrapping if needed."""
    sentences = re.split(r"(?<=[.!?])\s+", section)
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:chunk_size])
            sentence = sentence[chunk_size - overlap:]
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> List[str]:
    """Pack sections into chunks of at most `chunk_size` characters."""
    text = text.strip()
    if not text:
        return []

    chunks: List[str] = []
    current = ""
    for section in _split_sections(text):
        if len(section) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(section, chunk_size, overlap))
        elif len(current) + len(section) + 2 <= chunk_size:
            current = f"{current}\n\n{section}".strip()
        else:
            if current:
                chunks.append(current)
            current = section
    if current:
        chunks.append(current)

    # De-duplicate (whitespace-normalized) while preserving order.
    seen = set()
    deduped: List[str] = []
    for chunk in chunks:
        key = re.sub(r"\s+", " ", chunk).strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(chunk)
    return deduped


# ── TF-IDF index ─────────────────────────────────────────────────────────────

class TFIDFIndex:
    """Minimal TF-IDF index that supports cosine-similarity search."""

    def __init__(self, chunks: List[str]):
        self.chunks = chunks
        self._build(chunks)

    def _build(self, chunks: List[str]) -> None:
        n = len(chunks)
        tokenized = [_tokenize(c) for c in chunks]

        df: Counter = Counter()
        for tokens in tokenized:
            df.update(set(tokens))

        self.idf: dict[str, float] = {
            term: math.log((n + 1) / (count + 1)) + 1.0
            for term, count in df.items()
        }

        self.vectors: List[dict[str, float]] = []
        for tokens in tokenized:
            tf: Counter = Counter(tokens)
            total = len(tokens) or 1
            vec = {
                term: (count / total) * self.idf.get(term, 1.0)
                for term, count in tf.items()
            }
            self.vectors.append(vec)

    def _query_vec(self, query: str) -> dict[str, float]:
        tokens = _tokenize(query)
        tf: Counter = Counter(tokens)
        total = len(tokens) or 1
        return {
            term: (count / total) * self.idf.get(term, 1.0)
            for term, count in tf.items()
        }

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        dot = sum(a.get(k, 0.0) * v for k, v in b.items())
        norm_a = math.sqrt(sum(v * v for v in a.values())) or 1e-9
        norm_b = math.sqrt(sum(v * v for v in b.values())) or 1e-9
        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 5) -> List[str]:
        qv = self._query_vec(query)
        scores = [self._cosine(qv, dv) for dv in self.vectors]
        if not scores or max(scores) <= 0.0:
            return []
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i] for i in ranked[:top_k] if scores[i] > 0.0]


# ── Public API ────────────────────────────────────────────────────────────────

def build_index(text: str) -> Tuple[List[str], Any, Any]:
    """
    Chunk the rules text and build a TF-IDF index.

    Returns (chunks, embeddings_placeholder, index) to match the calling
    convention in main.py:
        chunks, _, index = build_index(rules_text)
    """
    chunks = _chunk_text(text)
    if not chunks:
        return [], None, None

    index = TFIDFIndex(chunks)
    return chunks, None, index


def search_index(query: str, chunks: List[str], index: Any, top_k: int = 5) -> List[str]:
    """Return the top-k most relevant chunks; [] when nothing is relevant."""
    if index is None or not chunks:
        return []
    return index.search(query, top_k=top_k)


# ── Repository code index: chunking + vector retrieval ───────────────────────
#
# Code chunks are larger and structure-aware: Python files chunk on top-level
# symbol boundaries (AST), other languages use overlapping line windows.
# Retrieval uses embeddings through pgvector when available, embeddings in
# process otherwise, and TF-IDF as the zero-config fallback.

import json as _json
import threading
from collections import OrderedDict

from sqlalchemy import text as _sql

from .config import (
    CODE_CHUNK_LINES,
    CODE_CHUNK_OVERLAP_LINES,
    CODE_CHUNK_MAX_CHARS,
    MAX_REPO_RETRIEVAL_CHUNKS,
)
from .database import is_postgres, pgvector_ready
from .llm import embed_texts


def chunk_code_file(path: str, content: str) -> List[dict]:
    """Split one source file into chunk dicts with line ranges.

    Returns [{path, start_line, end_line, content, language}].
    """
    from .code_graph import detect_language

    language = detect_language(path)
    lines = content.splitlines()
    if not lines:
        return []

    windows: List[Tuple[int, int]] = []
    if language == "python":
        try:
            from .code_graph import top_level_symbol_spans

            spans = top_level_symbol_spans(content)
        except Exception:
            spans = []
        if spans:
            cursor = 1
            for start, end in spans:
                if start > cursor:
                    windows.append((cursor, start - 1))
                windows.append((start, end))
                cursor = end + 1
            if cursor <= len(lines):
                windows.append((cursor, len(lines)))
        else:
            windows = _line_windows(len(lines))
    else:
        windows = _line_windows(len(lines))

    chunks: List[dict] = []
    for start, end in windows:
        text_block = "\n".join(lines[start - 1 : end])
        if not text_block.strip():
            continue
        if len(text_block) > CODE_CHUNK_MAX_CHARS:
            # Very long symbols fall back to hard line windows.
            for w_start, w_end in _line_windows(end - start + 1, base=start):
                block = "\n".join(lines[w_start - 1 : w_end])
                if block.strip():
                    chunks.append(
                        {"path": path, "start_line": w_start, "end_line": w_end,
                         "content": block, "language": language}
                    )
            continue
        chunks.append(
            {"path": path, "start_line": start, "end_line": end,
             "content": text_block, "language": language}
        )
    return chunks


def _line_windows(total_lines: int, base: int = 1) -> List[Tuple[int, int]]:
    step = max(CODE_CHUNK_LINES - CODE_CHUNK_OVERLAP_LINES, 1)
    windows = []
    start = 1
    while start <= total_lines:
        end = min(start + CODE_CHUNK_LINES - 1, total_lines)
        windows.append((base + start - 1, base + end - 1))
        if end >= total_lines:
            break
        start += step
    return windows


def store_chunk_vectors(session: Any, repo_id: int) -> int:
    """Mirror chunk embeddings into the pgvector table (Postgres only)."""
    if not (is_postgres() and pgvector_ready()):
        return 0
    rows = (
        session.execute(
            _sql("SELECT id, embedding FROM code_chunks WHERE repo_id = :rid AND embedding IS NOT NULL"),
            {"rid": repo_id},
        )
        .mappings()
        .all()
    )
    if not rows:
        return 0
    payload = [
        {
            "chunk_id": row["id"],
            "repo_id": repo_id,
            "vec": "[" + ",".join(f"{v:.6f}" for v in row["embedding"]) + "]",
        }
        for row in rows
        if isinstance(row["embedding"], (list, tuple))
    ]
    if not payload:
        return 0
    session.execute(
        _sql(
            """
            INSERT INTO chunk_vectors (chunk_id, repo_id, vec)
            VALUES (:chunk_id, :repo_id, CAST(:vec AS vector))
            ON CONFLICT (chunk_id) DO UPDATE SET repo_id = EXCLUDED.repo_id, vec = EXCLUDED.vec
            """
        ),
        payload,
    )
    session.commit()
    return len(payload)


def clear_chunk_vectors(session: Any, repo_id: int) -> None:
    if is_postgres() and pgvector_ready():
        session.execute(_sql("DELETE FROM chunk_vectors WHERE repo_id = :rid"), {"rid": repo_id})
        session.commit()


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na * nb) ** 0.5 + 1e-12)


class _TfidfRepoCache:
    """Small LRU cache of per-repo TF-IDF fallback indexes."""

    def __init__(self, capacity: int = 8):
        self.capacity = capacity
        self.entries: OrderedDict[Tuple[int, str], Any] = OrderedDict()
        self.lock = threading.Lock()

    def signature(self, session: Any, repo_id: int) -> Tuple[int, str]:
        row = session.execute(
            _sql("SELECT chunk_count, COALESCE(indexed_at, '') FROM repositories WHERE id = :rid"),
            {"rid": repo_id},
        ).first()
        if row is None:
            return (0, "")
        return (row[0] or 0, str(row[1]))

    def get(self, session: Any, repo_id: int) -> Any | None:
        key = (repo_id, self.signature(session, repo_id))
        with self.lock:
            cached = self.entries.get(key)
            if cached is not None:
                self.entries.move_to_end(key)
                return cached
        rows = (
            session.execute(
                _sql(
                    "SELECT id, path, start_line, end_line, content FROM code_chunks "
                    "WHERE repo_id = :rid ORDER BY path, start_line"
                ),
                {"rid": repo_id},
            )
            .mappings()
            .all()
        )
        if not rows:
            return None
        index = TFIDFIndex([row["content"] for row in rows])
        entry = (rows, index)
        with self.lock:
            self.entries[key] = entry
            self.entries.move_to_end(key)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
        return entry


_repo_cache = _TfidfRepoCache()


def repo_similarity_search(session: Any, repo_id: int, query: str, top_k: int = MAX_REPO_RETRIEVAL_CHUNKS) -> List[dict]:
    """Top-k code chunks for a query: pgvector → in-process cosine → TF-IDF."""
    from .llm import embeddings_configured

    query_vec = None
    if embeddings_configured():
        vectors = embed_texts([query[:8000]])
        if vectors:
            query_vec = vectors[0]

    if query_vec is not None and is_postgres() and pgvector_ready():
        try:
            rows = (
                session.execute(
                    _sql(
                        """
                        SELECT c.path, c.start_line, c.end_line, c.content,
                               1 - (v.vec <=> CAST(:qv AS vector)) AS score
                        FROM chunk_vectors v
                        JOIN code_chunks c ON c.id = v.chunk_id
                        WHERE v.repo_id = :rid
                        ORDER BY v.vec <=> CAST(:qv AS vector)
                        LIMIT :k
                        """
                    ),
                    {
                        "rid": repo_id,
                        "k": top_k,
                        "qv": "[" + ",".join(f"{v:.6f}" for v in query_vec) + "]",
                    },
                )
                .mappings()
                .all()
            )
            if rows:
                return [
                    {"path": r["path"], "start_line": r["start_line"], "end_line": r["end_line"],
                     "content": r["content"], "score": round(float(r["score"]), 4), "method": "pgvector"}
                    for r in rows
                ]
        except Exception:
            pass  # fall through to in-process search

    if query_vec is not None:
        rows = (
            session.execute(
                _sql(
                    "SELECT id, path, start_line, end_line, content, embedding FROM code_chunks "
                    "WHERE repo_id = :rid AND embedding IS NOT NULL"
                ),
                {"rid": repo_id},
            )
            .mappings()
            .all()
        )
        scored = []
        for row in rows:
            emb = row["embedding"]
            if not isinstance(emb, (list, tuple)) or len(emb) != len(query_vec):
                continue
            score = _cosine_similarity(query_vec, list(emb))
            if score > 0.05:
                scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        if scored:
            return [
                {"path": r["path"], "start_line": r["start_line"], "end_line": r["end_line"],
                 "content": r["content"], "score": round(s, 4), "method": "embedding_cosine"}
                for s, r in scored[:top_k]
            ]

    # TF-IDF fallback over the chunk corpus.
    entry = _repo_cache.get(session, repo_id)
    if entry is None:
        return []
    rows, index = entry
    matched = index.search(query, top_k=top_k)
    lookup = {row["content"]: row for row in rows}
    results = []
    seen = set()
    for chunk in matched:
        row = lookup.get(chunk)
        if row is None or row["id"] in seen:
            continue
        seen.add(row["id"])
        results.append(
            {"path": row["path"], "start_line": row["start_line"], "end_line": row["end_line"],
             "content": row["content"], "score": None, "method": "tfidf"}
        )
    return results
