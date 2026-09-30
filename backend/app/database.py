"""Database engine and session management.

Postgres is the production target (the docker-compose stack ships a
pgvector-enabled image); SQLite is the zero-config fallback for local runs
and tests. `init_db()` is idempotent and safe to call from any thread — it
creates tables and, on Postgres, the pgvector extension plus an auxiliary
`chunk_vectors` table used for accelerated nearest-neighbor search.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL, EMBEDDING_DIM

logger = logging.getLogger("codesentinal.database")

_is_postgres = DATABASE_URL.startswith(("postgres://", "postgresql://"))
_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {"pool_pre_ping": True}
if _is_sqlite:
    # The background worker and request handlers share the engine.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


_init_lock = threading.Lock()
_initialized = False
_pgvector_ready = False


def is_postgres() -> bool:
    return _is_postgres


def _try_enable_pgvector() -> bool:
    """Create the vector extension and chunk_vectors table; False if unavailable."""
    global _pgvector_ready
    if not _is_postgres:
        return False
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS chunk_vectors (
                        chunk_id INTEGER PRIMARY KEY,
                        repo_id  INTEGER NOT NULL,
                        vec      vector({EMBEDDING_DIM}) NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chunk_vectors_repo
                    ON chunk_vectors USING ivfflat (vec vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
        _pgvector_ready = True
        logger.info("pgvector enabled (dim=%d)", EMBEDDING_DIM)
    except Exception as exc:  # noqa: BLE001 — missing extension/image is expected
        logger.warning(
            "pgvector unavailable (%s: %s); falling back to in-process similarity",
            type(exc).__name__,
            exc,
        )
        _pgvector_ready = False
    return _pgvector_ready


def pgvector_ready() -> bool:
    return _pgvector_ready


def init_db() -> None:
    """Create tables if missing. Idempotent; called at startup and lazily."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        from . import db_models  # noqa: F401 — register mappings before create_all

        Base.metadata.create_all(bind=engine)
        _try_enable_pgvector()
        _initialized = True
        logger.info("Database initialized (%s)", "postgres" if _is_postgres else "sqlite")


def ensure_init() -> None:
    if not _initialized:
        init_db()


def get_db():
    """FastAPI dependency yielding a scoped session."""
    ensure_init()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
