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
