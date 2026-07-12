"""
Lightweight RAG (Retrieval-Augmented Generation) module.
Uses TF-IDF + cosine similarity so no heavy ML deps (FAISS/torch) are needed.
The public API matches what main.py expects:
    build_index(text: str) -> (chunks, embeddings, index)
    search_index(query: str, chunks, index, top_k=5) -> List[str]
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple, Any


# ── Text helpers ─────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
    """Split text into overlapping chunks of roughly `chunk_size` characters."""
    text = text.strip()
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap

    return [c for c in chunks if c]


# ── TF-IDF index ─────────────────────────────────────────────────────────────

class TFIDFIndex:
    """Minimal TF-IDF index that supports cosine-similarity search."""

    def __init__(self, chunks: List[str]):
        self.chunks = chunks
        self._build(chunks)

    def _build(self, chunks: List[str]) -> None:
        n = len(chunks)
        tokenized = [_tokenize(c) for c in chunks]

        # Document frequency
        df: Counter = Counter()
        for tokens in tokenized:
            df.update(set(tokens))

        self.idf: dict[str, float] = {
            term: math.log((n + 1) / (count + 1)) + 1.0
            for term, count in df.items()
        }

        # TF-IDF vectors (sparse dicts)
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
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i] for i in ranked[:top_k]]


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
    """Return the top-k most relevant chunks for the given query."""
    if index is None or not chunks:
        return []
    return index.search(query, top_k=top_k)
