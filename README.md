<div align="center">

# 🛡️ CodeSentinal

### AI-Powered Pull Request Security Reviewer

Paste a diff, drop in your security rules, and get instant, LLM-backed security findings — before the PR ever reaches a human reviewer.

![Status](https://img.shields.io/badge/status-active--development-blue)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-Next.js%2014-black)
![RAG](https://img.shields.io/badge/retrieval-TF--IDF%20Cosine%20Similarity-orange)
![LLM](https://img.shields.io/badge/LLM-Gemini%20%2F%20OpenAI--compatible-purple)
![Tests](https://img.shields.io/badge/tests-pytest%20%2B%20CI-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
  - [High-Level System Diagram](#high-level-system-diagram)
  - [Request Lifecycle](#request-lifecycle)
  - [Retrieval Layer (RAG)](#retrieval-layer-rag)
- [Project Structure](#-project-structure)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Getting Started](#-getting-started)
- [Manual Setup (Step-by-Step)](#-manual-setup-step-by-step)
- [Configuration Reference](#-configuration-reference)
- [Using the App](#-using-the-app)
- [GitHub Import Mode](#-github-import-mode)
- [API Reference](#-api-reference)
- [Security Model](#-security-model)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## 🧭 Overview

**CodeSentinal** is a lightweight, self-hosted security review assistant for pull requests. Instead of manually cross-referencing a diff against a security policy document, CodeSentinal automates the first pass:

1. You provide a **code diff** (pasted, uploaded, or imported directly from a GitHub PR).
2. You provide a **security policy** (a `SECURITY.md`, internal coding standard, or any rules document).
3. CodeSentinal retrieves the policy sections most relevant to the changed code using a **retrieval-augmented generation (RAG)** pipeline.
4. An **LLM** (Gemini or any OpenAI-compatible model) reviews the diff against those retrieved rules and returns **structured, machine-readable findings**.
5. The frontend renders each finding with a severity badge, the exact file/line, the violated rule, a suggested fix, and a ready-to-use merge-screening checklist.

It is intentionally built on a **free-tier-friendly stack** — no vector database service, no GPU, no paid infrastructure. Everything runs locally with a single Python process and a single Node process.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔍 **Diff-aware analysis** | Understands unified diff format and isolates added/changed lines for focused review. |
| 📚 **Policy-grounded findings** | Every finding is backed by the actual rule text it violates (`source_chunk`), not a hallucinated policy. |
| 🌐 **GitHub PR import** | Pull a live PR diff and the repo's `SECURITY.md` directly by `owner/repo` and PR number — no manual copy-paste. |
| 🧠 **Pluggable LLM backend** | Works with any OpenAI-compatible chat completion endpoint — Gemini, OpenAI, local proxies, etc. |
| 🔑 **Server-side secrets** | The LLM API key lives only in the backend's environment — it never touches the browser, localStorage, or request payloads. |
| 🚧 **Fail-closed auth** | Login and protected routes refuse to work while any required credential is unset — there are no built-in default accounts. |
| 🪶 **Zero heavy dependencies** | Retrieval is done with a custom TF-IDF + cosine similarity engine — no FAISS, no PyTorch, no sentence-transformer downloads. |
| ✅ **Merge-screening checklist** | Auto-generates a prioritized, human-actionable checklist from the top findings. |
| 🧪 **Tested & CI-ready** | 90 pytest tests cover auth, parsing, RAG, LLM handling, and every API route; GitHub Actions runs them plus the frontend build on every push. |
| ⚙️ **One-command startup** | `start.ps1` / `start.sh` bootstrap both services, create env files, install dependencies, and launch everything. |

---

## 🏗 Architecture

### High-Level System Diagram

```
                         ┌────────────────────────────────────────────┐
                         │                 BROWSER                    │
                         │   Next.js 14 (React 18) — localhost:3000   │
                         │                                            │
                         │  ┌──────────┐  ┌───────────┐  ┌─────────┐  │
                         │  │ Login    │  │ Diff/Rules│  │Findings │  │
                         │  │ (Auth)   │  │ Input UI  │  │  Cards  │  │
                         │  └──────────┘  └───────────┘  └─────────┘  │
                         └───────────────────────┬────────────────────┘
                                                  │  HTTPS (Bearer token)
                                                  ▼
                         ┌────────────────────────────────────────────┐
                         │                FASTAPI BACKEND              │
                         │             localhost:8000 (uvicorn)         │
                         │                                              │
                         │  /api/auth/login   /api/analyze              │
                         │  /api/demo/*       /api/github/import        │
                         │  /api/health       /api/settings/status      │
                         │                                              │
                         │  ┌───────────┐  ┌──────────────┐  ┌────────┐ │
                         │  │ auth.py   │  │ utils.py     │  │github.py│ │
                         │  │ (login +  │  │ (diff parse, │  │ (PR /   │ │
                         │  │  token)   │  │ chunking)    │  │ policy  │ │
                         │  └───────────┘  └──────────────┘  │ fetch)  │ │
                         │                                    └────────┘ │
                         │  ┌────────────────────┐  ┌───────────────────┐│
                         │  │ rag.py             │  │ llm.py            ││
                         │  │ TF-IDF index +     │  │ builds prompt,    ││
                         │  │ cosine similarity  │  │ calls LLM, parses ││
                         │  │ over rule chunks   │  │ JSON findings     ││
                         │  └────────────────────┘  └─────────┬─────────┘│
                         └────────────────────────────────────┼──────────┘
                                                              │ OpenAI-compatible
                                                              │ chat.completions API
                                                              │ (API key stays here,
                                                              │  server-side only)
                                                              ▼
                                             ┌─────────────────────────────┐
                                             │   LLM Provider              │
                                             │   Gemini 2.0 Flash (default)│
                                             │   or OpenAI / any compatible│
                                             │   endpoint                  │
                                             └─────────────────────────────┘

                         ┌────────────────────────────────────────────┐
                         │              GitHub REST API                │
                         │  (optional — only for "Import GitHub" flow) │
                         │  Pulls PR diff + SECURITY.md via github.py  │
                         └────────────────────────────────────────────┘
```

### Request Lifecycle

The core `/api/analyze` flow, step by step:

1. **Input** — The frontend sends `{ diff, rules }` to the backend with a `Bearer <token>` header.
2. **Auth check** — `app/auth.py` validates the bearer token against `AUTH_TOKEN` in constant time (or the request is rejected with `401`).
3. **Validation** — Pydantic enforces non-empty payloads and hard size limits (≈500 KB of diff, ≈1 MB of rules) before any processing happens.
4. **Diff normalization** — `app/utils.py::parse_diff()` strips binary-file noise from the raw diff text.
5. **Indexing** — `app/rag.py::build_index()` chunks the rules document by section boundaries and builds an in-memory **TF-IDF index** over the chunks.
6. **Retrieval** — `search_index()` runs two passes:
   - The full cleaned diff is used as a query to retrieve the most relevant rule chunks.
   - The **added lines only** (via `extract_code_snippets()`) are used as a second, more focused query to retrieve additional chunks.
   - Results are merged and de-duplicated, capped at 5 chunks total. If retrieval finds nothing relevant, the highest-signal rule sections are used as a fallback so the LLM always has policy context.
7. **LLM call** — `app/llm.py::call_llm()` builds a system + user prompt containing the diff and the retrieved rule chunks, then calls the configured OpenAI-compatible endpoint (key read from the server's environment) requesting a strict JSON array response.
8. **Parsing** — The LLM's JSON response is parsed defensively (handles markdown code fences, stray text before/after the array, and provider error envelopes) into a list of `Finding` objects: `severity`, `file_line`, `risk`, `rule_violation`, `safer_code`, `source_chunk`. Unparseable output is logged server-side — never echoed to the client.
9. **Screening checklist** — `main.py::build_screening_suggestions()` sorts findings by severity (`High → Medium → Low`) and produces up to 3 prioritized, human-readable action items.
10. **Response** — The backend returns `{ findings, screening_suggestions, error }`, which the frontend renders as severity-tagged cards with the offending file/line, the risk explanation, the exact rule text it violates, and a suggested code fix. Unexpected server errors are returned as a generic message with details only in the server logs.

### Retrieval Layer (RAG)

> **Note:** the retrieval layer is implemented as a **pure-Python TF-IDF + cosine similarity engine** (see `backend/app/rag.py`). It does **not** use FAISS or `sentence-transformers` — this implementation was deliberately kept dependency-light so it runs anywhere Python does, with no model downloads and no native binary requirements. If you plan to swap in embedding-based retrieval later, `rag.py` is the only file you need to touch — `build_index()` and `search_index()` are the two functions the rest of the app depends on.

---

## 🧩 Project Structure

```
CodeSentinal/
├── backend/
│   ├── main.py                  # FastAPI app: routes, orchestration, screening logic
│   ├── requirements.txt         # Runtime dependencies (FastAPI, uvicorn, openai, dotenv)
│   ├── requirements-dev.txt     # Test dependencies (pytest)
│   ├── pytest.ini               # Pytest configuration
│   ├── .env.example             # Committed env template — copy to .env and fill in
│   ├── Dockerfile               # Backend container image (with HEALTHCHECK)
│   ├── tests/                   # pytest suite: auth, models, utils, rag, llm, github, api
│   ├── app/
│   │   ├── __init__.py
│   │   ├── auth.py              # Fail-closed login + constant-time bearer token verification
│   │   ├── config.py            # Centralized size limits and tuning knobs
│   │   ├── rag.py               # TF-IDF chunking + cosine-similarity search index
│   │   ├── llm.py               # Prompt construction, OpenAI-compatible call, defensive JSON parsing
│   │   ├── models.py            # Pydantic request/response schemas with strict validation
│   │   ├── utils.py             # Unified-diff parsing, text chunking, added-line extraction
│   │   └── github.py            # GitHub REST client: PR diff + policy file import
│   └── demo/
│       ├── sample_diff.diff     # Demo diff with intentionally vulnerable code
│       └── sample_rules.md      # Sample security policy used by the demo
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Login page (redirects to /analyze if authenticated)
│   │   │   ├── layout.tsx       # Root layout
│   │   │   ├── globals.css      # Tailwind globals
│   │   │   └── analyze/
│   │   │       └── page.tsx     # Main analysis workspace (composes the components below)
│   │   ├── components/
│   │   │   ├── LoginForm.tsx
│   │   │   └── analyze/
│   │   │       ├── AnalyzeHeader.tsx       # Title bar + demo loader + logout
│   │   │       ├── DiffEditor.tsx          # Paste/upload diff input
│   │   │       ├── PolicyPanel.tsx         # Paste/upload security rules
│   │   │       ├── GitHubImportModal.tsx   # GitHub PR / repo import dialog
│   │   │       ├── AnalysisResults.tsx     # Findings summary + list
│   │   │       ├── FindingCard.tsx         # Single severity-tagged finding
│   │   │       ├── ScreeningChecklist.tsx  # Auto-generated merge checklist
│   │   │       ├── KnowledgeBase.tsx       # Retrieved rule chunks viewer
│   │   │       └── SettingsPanel.tsx       # Server-side LLM configuration status
│   │   ├── lib/
│   │   │   ├── api.ts           # Typed fetch client for the backend API
│   │   │   ├── auth.tsx         # React auth context (token storage)
│   │   │   └── upload.ts        # Client-side file upload validation
│   │   └── types/
│   │       └── index.ts         # Shared TypeScript types
│   ├── Dockerfile               # Multi-stage frontend container image
│   ├── .eslintrc.json
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── .github/workflows/ci.yml     # CI: pytest + frontend typecheck/lint/build
├── docker-compose.yml           # Backend + frontend containers with healthchecks
├── start.ps1                    # ⭐ One-command startup for Windows / PowerShell
├── start.sh                     # One-command startup for macOS / Linux
├── package.json                 # Root workspace scripts (dev/build/start/backend)
└── README.md
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide icons |
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **Retrieval** | Custom TF-IDF + cosine similarity (`backend/app/rag.py`) — pure Python, no external index service |
| **LLM Client** | `openai` Python SDK pointed at an OpenAI-compatible endpoint (Gemini 2.0 Flash by default) |
| **GitHub Integration** | Standard library `urllib` REST client (`backend/app/github.py`) — no external HTTP dependency |
| **Auth** | Stateless bearer-token auth, no database |
| **Testing** | pytest (backend), TypeScript + ESLint + `next build` (frontend), GitHub Actions CI |

---

## ✅ Prerequisites

Before you start, make sure you have:

- **Python 3.10+** available on your `PATH`
- **Node.js 18+** and **npm**
- An **API key** for your LLM of choice:
  - **Gemini** (recommended, generous free tier) — get one from [Google AI Studio](https://aistudio.google.com/app/apikey)
  - Or any **OpenAI-compatible** API key (OpenAI, Groq, local proxy, etc.)

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/midhunkmadhu10/CodeSentinal.git
cd CodeSentinal
```

### 2. Configure the backend

Both env templates are committed to the repo. Copy the backend one and fill in **every required value** — the app fails closed until they are set:

```bash
cp backend/.env.example backend/.env
```

Then edit `backend/.env`:

```env
AUTH_USERNAME=your-username
AUTH_PASSWORD=your-strong-password
AUTH_TOKEN=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
LLM_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash
LLM_API_KEY=your-gemini-api-key
```

### 3. Run it

**Windows / PowerShell:**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # first time only
.\start.ps1
```

**macOS / Linux:**

```bash
chmod +x start.sh
./start.sh
```

The script creates `backend/.env` from the committed template (if missing), sets up a Python virtualenv, installs dependencies, and starts the backend on `:8000` and the frontend on `:3000`. Press **Ctrl+C** to stop both.

### 4. Open the app

- **Frontend:** http://localhost:3000
- **Backend docs (Swagger UI):** http://localhost:8000/docs
- **Login:** the `AUTH_USERNAME` / `AUTH_PASSWORD` values you set in `backend/.env`

---

## 🔧 Manual Setup (Step-by-Step)

If you prefer not to use the start scripts, or need to debug something in isolation:

### Backend

```bash
cd backend
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows (cmd)
.\venv\Scripts\Activate.ps1     # Windows (PowerShell)

pip install -r requirements.txt

# Create your .env (see Configuration Reference below)
cp .env.example .env            # then edit .env with your real values

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Then open **http://localhost:3000**.

### Docker

```bash
cp backend/.env.example backend/.env   # then edit .env with your real values
docker compose up --build
```

Both containers include healthchecks; the frontend waits for the backend to be healthy before starting.

---

## ⚙️ Configuration Reference

### Backend (`backend/.env`) — all `AUTH_*` and `LLM_API_KEY` variables are **required**

| Variable | Required | Description |
|---|---|---|
| `AUTH_USERNAME` | ✔ | Login username for the app — no default is provided |
| `AUTH_PASSWORD` | ✔ | Login password for the app — no default is provided |
| `AUTH_TOKEN` | ✔ | Bearer token issued on login and required on protected routes — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `LLM_ENDPOINT` | ✔ | Base URL of an OpenAI-compatible chat completions API |
| `LLM_API_KEY` | ✔ | Your API key for the configured LLM provider — **server-side only** |
| `LLM_MODEL` | ✔ | Model name to request from the endpoint |
| `LLM_TIMEOUT_SECONDS` | — | LLM request timeout in seconds (default `90`) |
| `LLM_MAX_TOKENS` | — | Max tokens requested from the LLM (default `4096`) |
| `CORS_ORIGINS` | — | Comma-separated frontend origins allowed by CORS (default `http://localhost:3000,http://127.0.0.1:3000`) |
| `LOG_LEVEL` | — | Python log level (default `INFO`) |

**Recommended values for Google Gemini (free tier):**

```env
LLM_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=your-gemini-api-key
LLM_MODEL=gemini-2.0-flash
```

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL the frontend uses to reach the FastAPI backend |

> The LLM endpoint, model, and API key are configured **only** on the server. The frontend's Settings panel shows whether the server-side LLM configuration is present (via `/api/settings/status`) — it never collects or transmits an API key from the browser.

---

## 🧪 Using the App

1. **Log in** with the credentials you set in `backend/.env`.
2. Click **Load Demo** to populate a sample diff and sample security rules instantly — no setup required to see it work.
3. Click **Analyze**. Findings stream in as severity-tagged cards with a per-severity count summary.
4. Alternatively:
   - Paste your **own diff**, or upload a `.diff` / `.patch` file.
   - Upload your own `SECURITY.md` or coding-standards document as the rules source.
5. Review each finding:
   - **Severity** — High / Medium / Low
   - **File & line** — exact location of the issue
   - **Risk** — plain-English description of the vulnerability
   - **Rule violated** — which policy rule applies, and why
   - **Suggested fix** — a corrected code snippet
   - **Source chunk** — the exact rule text the finding is grounded in
6. Use the auto-generated **merge-screening checklist** as a final human sign-off guide before approving the PR.

---

## 🌐 GitHub Import Mode

Instead of copy-pasting a diff, click **Import GitHub** and provide:

- A repository as `owner/repository` or a full `https://github.com/owner/repository` URL
- *(Optional)* a pull request number — if omitted, CodeSentinal compares the latest commit on the default branch against its parent commit

CodeSentinal will automatically look for and load one of these policy files from the repository, in order:

1. `SECURITY.md`
2. `.github/SECURITY.md`
3. `SECURITY_POLICY.md`

**Access & tokens:**
- Public repositories work with **no credentials**.
- Private repositories require a **fine-grained GitHub personal access token** with read access to that repository.
- The token is **request-scoped only** — it is sent with that single import request and is never written to disk, logged, or persisted by CodeSentinal (see `backend/app/github.py`).

---

## 📝 API Reference

All protected routes require `Authorization: Bearer <token>`, where `<token>` is the value returned by `/api/auth/login` (equal to `AUTH_TOKEN`).

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health` | No | Health check — returns service status |
| `GET` | `/api/settings/status` | Yes | Reports whether a server-side API key is configured, plus the configured endpoint/model (never the key itself) |
| `POST` | `/api/auth/login` | No | Body: `{ username, password }` → returns `{ token }`. Fails closed if credentials are unset on the server |
| `GET` | `/api/demo/diff` | Yes | Returns the bundled sample diff |
| `GET` | `/api/demo/rules` | Yes | Returns the bundled sample security rules |
| `POST` | `/api/github/import` | Yes | Body: `{ repository, pull_number?, access_token? }` → returns `{ repository, diff, policy, policy_path, error? }` |
| `POST` | `/api/analyze` | Yes | Body: `{ diff, rules }` → returns `{ findings[], screening_suggestions[], error? }` |

Full interactive documentation (Swagger UI) is available at **http://localhost:8000/docs** whenever the backend is running.

---

## 🔐 Security Model

- **Fail-closed auth** — if `AUTH_USERNAME`, `AUTH_PASSWORD`, or `AUTH_TOKEN` is missing from the environment, login and every protected route refuse to serve rather than falling back to default credentials. Credential comparisons use constant-time checks.
- **Secrets stay server-side** — the LLM API key is read only from the backend's environment. It is never sent from, stored in, or accepted from the browser, and it is not echoed back by `/api/settings/status`.
- **Request validation & limits** — all payloads are validated by strict Pydantic schemas with hard size caps (≈500 KB diff, ≈1 MB rules, bounded token and repository-field lengths).
- **No internal leakage** — unexpected errors return a generic `Internal server error` to clients; raw exception strings and unparsed LLM output go to the server logs only.
- **Request-scoped GitHub tokens** — access tokens supplied through the "Import GitHub" flow are used for that single request and never persisted or logged.
- **Known limitations** — this project ships plaintext, shared-secret authentication and **no database**. It is designed for local/personal use or trusted internal environments, not multi-tenant production deployment as-is. Change the credentials before exposing anything beyond localhost, and never commit a real `backend/.env` (it is git-ignored).

---

## 🧪 Testing

Backend (90 tests):

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

Frontend checks:

```bash
npm run typecheck --workspace=frontend
npm run lint --workspace=frontend
npm run build --workspace=frontend
```

GitHub Actions runs both suites on every push and pull request (`.github/workflows/ci.yml`).

---

## 🩹 Troubleshooting

| Symptom | Likely Cause / Fix |
|---|---|
| `start.ps1` fails with "cannot be loaded because running scripts is disabled" | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell session, then retry |
| Login always fails, even with the right password | One of `AUTH_USERNAME` / `AUTH_PASSWORD` / `AUTH_TOKEN` is missing or empty in `backend/.env` — auth fails closed until all are set. Restart the backend after editing |
| Analysis fails with `LLM_API_KEY is not configured` | Set a real key in `backend/.env` and restart the backend — the key can no longer be supplied from the browser |
| `Failed to parse LLM response as JSON` | The model didn't return valid JSON — try a different `LLM_MODEL`, lower the input size, or retry; `llm.py` already handles markdown-fenced responses defensively |
| Request rejected with a validation error about size | The diff exceeds ≈500 KB or the rules exceed ≈1 MB — split or trim the input |
| Frontend can't reach the backend (`CORS` or network errors) | Confirm the backend is running on port `8000` and `NEXT_PUBLIC_API_URL` in `frontend/.env.local` matches it; for non-localhost origins also check `CORS_ORIGINS` |
| GitHub import returns "GitHub could not access that repository" | Repository is private and needs a token, the PR number doesn't exist, or you've hit GitHub's unauthenticated rate limit |
| Windows: backend/frontend processes keep running after closing the window | Manually stop them with `Stop-Process -Id <PID>` using the PIDs printed by `start.ps1`, or use Task Manager to end the `python`/`node` processes |

---

## 🗺 Roadmap

Ideas for extending this project:

- Swap the TF-IDF retriever in `rag.py` for embedding-based retrieval (e.g., `sentence-transformers` + FAISS) for larger policy documents
- Persist findings/history in a lightweight database (SQLite) instead of being stateless per-request
- Support GitHub PR **check runs** / inline review comments instead of a standalone UI
- Multi-user auth (replace the single shared token with per-user accounts)

---

## 📄 License

MIT — built for hackathons, internal tooling, and security-review experimentation. Use, fork, and adapt freely.
