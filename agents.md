# CodeSentinal agent guide

## Project layout

- `frontend/`: Next.js 14 application (`frontend/src`).
- `backend/`: FastAPI service (`backend/main.py`, `backend/app/`).
- `docker-compose.yml`: local deployment (backend + frontend + pgvector Postgres).
- `backend/demo/`: tracked demo fixtures used by the UI.

## ⚠️ WORK IN PROGRESS — READ THIS FIRST (handoff context)

The repository is being transformed from a single-user, stateless "AI PR
security reviewer" demo into a **production-grade AI code-intelligence SaaS**.
A previous session surveyed the whole codebase and is partway through the
backend rebuild. This section is the source of truth for that effort.

### Goal (the full feature list being built)

1. **GitHub connection** — repo connections, PR import, **webhook-triggered
   automatic PR review** that posts review comments back to GitHub.
2. **Repo understanding** — AST/code-graph analysis (Python `ast`, regex
   heuristics for other languages) + **embedding-based RAG with pgvector**
   over indexed repositories (chunk code, embed, store, similarity search).
3. **Deterministic scanners** combined with **specialized LLM agents**
   (security, bug, code-quality) that **corroborate scanner hits** and emit
   structured findings, plus **fix and test generation**.
4. **Model routing** — complexity-scored routing between a `fast` and a
   `deep` cost tier, with token/cost accounting surfaced as metrics.
5. **Platform** — evaluation metrics, observability (Prometheus-style
   metrics + JSON logs), **review history persistence**, **multi-user JWT
   authentication**, and a **polished SaaS dashboard** frontend.

### Architecture decisions (already locked in)

- **Database**: SQLAlchemy 2.0 (`app/database.py`, `app/db_models.py`).
  `DATABASE_URL` Postgres in production (docker-compose ships the
  `pgvector/pgvector:pg16` image); **SQLite fallback** (`sqlite:///./codesentinal.db`)
  keeps local dev and CI zero-config. `init_db()` is idempotent, thread-safe,
  and on Postgres enables the `vector` extension and creates an auxiliary
  `chunk_vectors` table (native `vector(EMBEDDING_DIM)` column + ivfflat
  cosine index). Embeddings are ALSO stored as JSON on `code_chunks` so
  in-process cosine works without pgvector; TF-IDF is the final fallback.
- **Auth**: JWT (HS256, PyJWT) with PBKDF2 password hashing in
  `app/auth.py`. Legacy compat is REQUIRED to keep tests/demo working:
  `AUTH_USERNAME`/`AUTH_PASSWORD` seed a demo user (role=admin) at startup
  and the static `AUTH_TOKEN` is still accepted, resolving to that user.
- **LLM**: `app/llm.py` keeps the legacy `call_llm(diff, rules_chunks)` API
  untouched (tests depend on it) and ADDS `llm_chat(messages, model=...) ->
  ChatResult` (usage tokens, estimated cost via `model_routing.estimate_cost`,
  latency metrics) and `embed_texts(texts) -> list[list[float]] | None`
  (never raises; returns None to signal TF-IDF fallback). Config:
  `LLM_ENDPOINT`/`LLM_MODEL`/`LLM_API_KEY` + optional
  `EMBEDDINGS_ENDPOINT`/`EMBEDDINGS_MODEL`.
- **Routing**: `app/model_routing.py` — `complexity_score()` (0–1 from diff
  size/breadth/scanner hits), `route(task, ...) -> RoutingDecision` (tier
  fast/deep vs `DEEP_TIER_THRESHOLD`), `routing_table()`, metric
  `routing_decisions_total`.
- **Observability**: `app/observability.py` — hand-rolled `METRICS` registry
  (counters + histograms, Prometheus text + JSON `snapshot()`), JSON log
  formatter, `log_event()`. Registered metric names listed there; reuse them.
- **ORM models** (`app/db_models.py`): `User`, `Repository` (index_status,
  graph JSON, counts), `CodeChunk` (path/lines/content/embedding JSON),
  `CodeSymbol`, `Job` (background queue row: type/status/payload/result/
  attempts), `Review` (trigger manual|api|webhook, counts JSON, metrics JSON),
  `ReviewFinding` (source scanner|agent, agent/scanner names, category,
  severity, file/line, description, rule, cwe, snippet, fix_code, tests JSON,
  confidence, corroborated), `Event` (activity feed), `EvalRun`.

### Backend work DONE so far

Rewritten: `app/config.py` (all new env knobs). `app/main.py` is NOT yet
rewritten (still legacy single-file app — must be replaced by routers).
Extended in place: `app/llm.py` (appended typed chat + embeddings sections),
`app/rag.py` (appended repo code-index section: `chunk_code_file`,
`store_chunk_vectors`, `clear_chunk_vectors`, `repo_similarity_search` with
pgvector → in-process cosine → TF-IDF fallback, plus `_TfidfRepoCache` LRU).

Created new: `app/database.py`, `app/db_models.py`, `app/observability.py`,
`app/model_routing.py`, `app/auth.py` (JWT rewrite).

### Backend work REMAINING (build in this order)

1. `app/code_graph.py` — `detect_language(path)`, `top_level_symbol_spans(source)`
   (Python `ast`; other langs regex), `parse_file()` → symbols + imports,
   `build_code_graph(files)` → nodes/edges (call/import edges), capped sizes.
2. `app/scanners.py` — deterministic regex/AST scanners: secrets/hardcoded
   creds, SQL injection patterns, dangerous calls (`eval`/`exec`/`pickle.loads`/
   `shell=True`), weak crypto, path traversal, insecure defaults (debug=True,
   verify=False). Each hit: category, severity, file, line, snippet, rule,
   cwe, suggestion. Metric `scanner_findings_total`.
3. `app/agents.py` — `run_security_agent`, `run_bug_agent`, `run_quality_agent`,
   `generate_fixes(findings)` (fix_code + tests via `llm_chat`), each with
   JSON-mode prompts + `parse_json_object` parsing, routing via
   `model_routing.route`, per-agent context from scanners + repo RAG chunks.
4. `app/pipeline.py` — orchestrator `run_review(...)`: parse diff → scanners →
   routing decision → agents → corroboration (scanner+agent agreement sets
   `corroborated=True`, bumps confidence) → fix/test generation → screening
   suggestions → persist Review + ReviewFindings → metrics. Also a
   legacy-compatible `analyze_sync()` for `POST /api/analyze` (keep old
   request/response shape exactly).
5. `app/github_service.py` — extend existing `app/github.py` (urllib client,
   keep it dependency-free): `fetch_repo_tree`, `fetch_blob`, `post_pr_comment`
   (POST /repos/{o}/{r}/issues/{n}/comments), `fetch_pr_files`,
   `verify_webhook_signature` (HMAC-SHA256, constant-time). Keep the
   user-safe ValueError mapping style.
6. `app/indexer.py` — `index_repository(db, repo)`: fetch tree via API (or
   walk local dir fallback for demo), filter by `config.TEXT_EXTENSIONS` /
   `INDEX_SKIP_DIRS` / size caps, chunk via `rag.chunk_code_file`, batch
   `embed_texts`, upsert CodeChunks + CodeSymbols, `store_chunk_vectors`,
   update Repository counts/status, `build_code_graph` → Repository.graph.
7. `app/worker.py` — in-process background worker thread started at app
   startup (`WORKER_ENABLED`), claims `Job` rows (status queued → running,
   attempts < JOB_MAX_ATTEMPTS), handlers: `index_repository`,
   `review_pull_request` (webhook/manual PR review incl. posting GitHub
   comment), `reindex_repository`. Mark Event rows for the activity feed.
8. `app/schemas.py` — Pydantic API schemas: RegisterRequest, TokenResponse,
   RepositoryOut, ReviewOut, ReviewFindingOut, JobOut, MetricsSnapshot,
   EvalScore, plus legacy AnalyzeRequest/Response, Finding, ScreeningSuggestion,
   GitHubImportRequest/Response (KEEP old field names exactly — the current
   frontend and 60+ tests use them).
9. Routers (`app/routers/`): `auth.py` (register/login/me), `repos.py`
   (CRUD + index trigger + status), `reviews.py` (list/detail/create manual
   review), `jobs.py` (list/detail), `metrics.py` (JSON snapshot +
   `/api/metrics` Prometheus text), `evals.py` (run eval suite + history),
   `webhooks.py` (POST /api/webhooks/github — HMAC verify, PR events → Job).
10. Rewrite `backend/main.py` — create app, `configure_logging`, CORS
    (keep GET/POST + add PATCH/DELETE), include routers, startup: `init_db()`
    + `seed_demo_user` + start worker; keep legacy routes working:
    `/api/health`, `/api/auth/login`, `/api/demo/diff`, `/api/demo/rules`,
    `/api/github/import`, `/api/analyze`, `/api/settings/status` (extended
    with db/routing info). App version "2.0.0".
11. Requirements: add `sqlalchemy>=2.0`, `pyjwt>=2.8` to
    `backend/requirements.txt` (keep pinned style). Fix the `httpx2` typo in
    `requirements-dev.txt` → `httpx`.
12. Tests: existing `backend/tests/` must keep passing (they mock LLM/GitHub
    and use TestClient with legacy env vars — conftest sets
    AUTH_USERNAME/AUTH_PASSWORD/AUTH_TOKEN/LLM_*). Disable the worker in
    tests (env `WORKER_ENABLED=false`). Add tests for auth/JWT, scanners,
    code graph, routing, webhook signature, pipeline corroboration.
13. `backend/evals/` + `app/evaluation.py` — evaluation fixtures: sample
    vulnerable diffs + expected findings; precision/recall/F1 over
    (file_line, category) matching, persisted as EvalRun rows; endpoints to
    trigger + view.

### Frontend work REMAINING

- `lib/api.ts`: add register, repos CRUD, reviews list/detail, jobs, metrics,
  evals; keep JWT in localStorage (same `codesentinal_token` key).
- Auth: `/register` page + login page update (email+password).
- Dashboard: `/dashboard` overview (stat cards: reviews, findings by
  severity, cost estimate, uptime), `/dashboard/reviews` history list,
  `/dashboard/reviews/[id]` detail (findings with agent/scanner badges,
  corroborated badge, fix_code + tests blocks), `/dashboard/repositories`
  (connect repo, index trigger, status), `/dashboard/settings` (routing
  table, model status, metrics link). Upgrade `/analyze` to show scanner +
  agent sources.
- Keep the existing glassmorphism dark theme (tailwind.config.ts,
  globals.css) — polish, don't replace.

### Infra/docs REMAINING

- `docker-compose.yml`: add `db` service (`pgvector/pgvector:pg16`, env
  POSTGRES_USER/PASSWORD/DB, volume, healthcheck pg_isready) + backend
  `depends_on db healthy` + `DATABASE_URL` env wiring.
- `backend/.env.example`: add DATABASE_URL, JWT_SECRET, EMBEDDINGS_*,
  MODEL_FAST/MODEL_DEEP + cost knobs, GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET,
  WORKER_*.
- CI: keep `pytest` green; add `python -m compileall backend`.
- README: document new architecture. Root `package.json` scripts fine.

### Verified facts about the legacy code (do not break)

- `app/utils.py` diff parser and `app/rag.py` TF-IDF are battle-tested by
  60+ unit tests; keep their behavior identical.
- `main.py` analyze flow: parse_diff → build_index → two retrieval passes →
  call_llm → screening suggestions; response shape
  `{findings[], screening_suggestions[], error}` where Finding has
  severity/file_line/risk/rule_violation/safer_code/source_chunk.
- `app/github.py` raises ValueError with user-safe messages; max diff 5 MB;
  separate 500 KB request limit in config (intentional).
- Tests never hit network; LLM and GitHub are mocked at module boundary.
- Legacy bearer token (AUTH_TOKEN) must remain accepted for old clients.

## Local setup

1. Copy `backend/.env.example` to `backend/.env` and set credentials, JWT
   secret, `LLM_API_KEY` (and `DATABASE_URL` when using Postgres).
2. Copy `frontend/.env.local.example` to `frontend/.env.local` if the API is
   not available at `http://localhost:8000`.
3. Run `npm install` at the repository root.
4. Run `npm run dev` and `npm run backend`, or use `docker compose up --build`.

## Checks before handoff

- Backend: `python -m compileall backend` and `pytest` (in `backend/`).
- Frontend: `npm run typecheck --workspace=frontend`, `npm run lint --workspace=frontend`,
  and `npm run build --workspace=frontend`.
- Compose: `docker compose config`; verify `/api/health` after startup.

## Contribution rules

- Never commit credentials, `.env` files, virtual environments, dependencies,
  Next build output, or TypeScript build metadata.
- Never log access tokens or include them in client-facing errors.
- Keep API changes synchronized between Pydantic models and the frontend client.
- Use `UVICORN_RELOAD=true` only for local development.
- Keep changes focused and preserve the demo flow.
