"""Vercel serverless entrypoint for the FastAPI backend.

Vercel's Python runtime looks for an ASGI callable named ``app`` inside a file
under ``api/``. The real application lives in the project root (``main.py``), so
this shim only fixes ``sys.path`` and re-exports it.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import app  # noqa: E402,F401  (imported for Vercel's ASGI discovery)
