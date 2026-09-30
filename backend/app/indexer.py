"""Repository indexing: fetch files, chunk, embed, store symbols + graph.

Runs as a background job. Uses the GitHub API when the repository is
reachable with a token; a local-directory walker provides an offline fallback
(used by the demo). Progress is recorded on Repository.index_status.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from . import github_service
from .code_graph import build_code_graph, parse_file
from .config import (
    INDEX_MAX_FILES,
    INDEX_MAX_FILE_BYTES,
    INDEX_SKIP_DIRS,
    TEXT_EXTENSIONS,
)
from .db_models import CodeChunk, CodeSymbol, Repository, Event
from .llm import embed_texts
from .observability import METRICS, log_event
from .rag import chunk_code_file, clear_chunk_vectors, store_chunk_vectors
from .scanners import scan_source_file

logger = logging.getLogger("codesentinal.indexer")


def _should_index(path: str, size: int) -> bool:
    if not path or path.endswith("/"):
        return False
    parts = path.split("/")
    if any(part in INDEX_SKIP_DIRS for part in parts[:-1]):
        return False
    suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if suffix not in TEXT_EXTENSIONS:
        return False
    if size > INDEX_MAX_FILE_BYTES:
        return False
    return True


def _files_via_github(
    owner: str, repo: str, ref: str, token: Optional[str]
) -> List[Dict[str, Any]]:
    """Fetch file contents via the GitHub API. Raises ValueError on failure."""
    tree = github_service.fetch_repo_tree(owner, repo, ref, token)
    blobs = [item for item in tree if item.get("type") == "blob"]
    blobs.sort(key=lambda item: item.get("path", ""))
    selected = [b for b in blobs if _should_index(b["path"], b.get("size", 0))][:INDEX_MAX_FILES]
    files: List[Dict[str, Any]] = []
    for blob in selected:
        content = github_service.fetch_blob(owner, repo, blob["sha"], token)
        if content is not None:
            files.append({"path": blob["path"], "content": content})
    return files


def _files_via_local_dir(root: str) -> List[Dict[str, Any]]:
    """Offline fallback: walk a local directory (demo / dev with a checkout)."""
    files: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in INDEX_SKIP_DIRS]
        for filename in filenames:
            path = os.path.relpath(os.path.join(dirpath, filename), root).replace("\\", "/")
            try:
                size = os.path.getsize(os.path.join(dirpath, filename))
            except OSError:
                continue
            if not _should_index(path, size):
                continue
            try:
                with open(os.path.join(dirpath, filename), "r", encoding="utf-8", errors="replace") as fh:
                    files.append({"path": path, "content": fh.read()})
            except OSError:
                continue
            if len(files) >= INDEX_MAX_FILES:
                return files
    return files


def index_repository(
    db: Session,
    repo: Repository,
    access_token: Optional[str] = None,
    local_root: Optional[str] = None,
) -> Repository:
    """Index one repository: chunks, embeddings, symbols, graph. Idempotent."""
    repo.index_status = "indexing"
    repo.last_error = None
    db.commit()
    log_event("index.started", repo=repo.full_name, repo_id=repo.id)

    files: List[Dict[str, Any]] = []
    error: Optional[str] = None
    try:
        if local_root:
            files = _files_via_local_dir(local_root)
        else:
            owner, name = repo.owner, repo.name
            ref = repo.default_branch or github_service.fetch_default_branch(
                owner, name, access_token
            )
            repo.default_branch = ref
            files = _files_via_github(owner, name, ref, access_token)
    except ValueError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001 — indexer must never crash the worker
        logger.exception("Indexing crashed for %s", repo.full_name)
        error = "Repository indexing failed unexpectedly."

    if error is not None or not files:
        repo.index_status = "failed"
        repo.last_error = error or "No indexable files were found in this repository."
        db.commit()
        METRICS.inc("jobs_total", type="index_repository", status="failed")
        return repo

    # Replace previous index atomically (single transaction per section).
    clear_chunk_vectors(db, repo.id)
    db.query(CodeChunk).filter(CodeChunk.repo_id == repo.id).delete()
    db.query(CodeSymbol).filter(CodeSymbol.repo_id == repo.id).delete()
    db.flush()

    parsed_files = []
    chunk_rows: List[Dict[str, Any]] = []
    scanner_findings = 0
    for file_info in files:
        path, content = file_info["path"], file_info["content"]
        parsed_files.append(parse_file(path, content))
        for chunk in chunk_code_file(path, content):
            chunk_rows.append(chunk)
        scanner_findings += len(scan_source_file(path, content))

    if chunk_rows:
        embeddings = embed_texts([chunk["content"] for chunk in chunk_rows])
        if embeddings and len(embeddings) == len(chunk_rows):
            for chunk, vector in zip(chunk_rows, embeddings):
                chunk["embedding"] = vector
        else:
            logger.info("Embeddings unavailable for %s; storing text-only chunks", repo.full_name)

    for chunk in chunk_rows:
        db.add(
            CodeChunk(
                repo_id=repo.id,
                path=chunk["path"],
                language=chunk.get("language", ""),
                start_line=chunk["start_line"],
                end_line=chunk["end_line"],
                content=chunk["content"],
                embedding=chunk.get("embedding"),
            )
        )

    symbol_count = 0
    for parsed in parsed_files:
        for symbol in parsed.symbols:
            db.add(
                CodeSymbol(
                    repo_id=repo.id,
                    path=parsed.path,
                    name=symbol.name,
                    qualname=symbol.qualname,
                    kind=symbol.kind,
                    language=parsed.language,
                    start_line=symbol.start_line,
                    end_line=symbol.end_line,
                    signature=symbol.signature[:1000],
                    docstring=symbol.docstring[:2000],
                )
            )
            symbol_count += 1

    graph = build_code_graph(parsed_files)
    db.flush()
    stored_vectors = store_chunk_vectors(db, repo.id)

    repo.index_status = "indexed"
    repo.indexed_at = datetime.now(timezone.utc)
    repo.chunk_count = len(chunk_rows)
    repo.symbol_count = symbol_count
    repo.file_count = len(files)
    repo.graph = graph.to_dict()
    repo.last_error = None
    db.add(
        Event(
            event="repo.indexed",
            user_id=repo.user_id,
            data={"repo_id": repo.id, "files": len(files), "chunks": len(chunk_rows),
                  "vectors": stored_vectors, "symbols": symbol_count},
        )
    )
    db.commit()
    METRICS.inc("jobs_total", type="index_repository", status="ok")
    log_event("index.completed", repo=repo.full_name, files=len(files), chunks=len(chunk_rows))
    return repo
