<div align="center">

# 🛡️ CodeSentinal

### AI-Powered Pull Request Security Reviewer

Paste a diff, drop in your security rules, and get instant, LLM-backed security findings — before the PR ever reaches a human reviewer.

![Status](https://img.shields.io/badge/status-active--development-blue)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-Next.js%2014-black)
![RAG](https://img.shields.io/badge/retrieval-TF--IDF%20Cosine%20Similarity-orange)
![LLM](https://img.shields.io/badge/LLM-Gemini%20%2F%20OpenAI--compatible-purple)
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
- [Getting Started (Windows / PowerShell)](#-getting-started-windows--powershell)
- [Getting Started (macOS / Linux)](#-getting-started-macos--linux)
- [Manual Setup (Step-by-Step)](#-manual-setup-step-by-step)
- [Configuration Reference](#-configuration-reference)
- [Using the App](#-using-the-app)
- [GitHub Import Mode](#-github-import-mode)
- [API Reference](#-api-reference)
- [Security Notes](#-security-notes)
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
| 🪶 **Zero heavy dependencies** | Retrieval is done with a custom TF-IDF + cosine similarity engine — no FAISS, no PyTorch, no sentence-transformer downloads. |
| ✅ **Merge-screening checklist** | Auto-generates a prioritized, human-actionable checklist from the top findings. |
| 🔐 **Simple token auth** | No database required; a single shared username/password protects the instance. |
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
                         │  │ Login    │  │ Diff/Rules│  │ Results │  │
                         │  │ (Auth)   │  │ Input UI  │  │  Table  │  │
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
                         │  │ (token    │  │ (diff parse, │  │ (PR /   │ │
                         │  │ verify)   │  │ chunking)    │  │ policy  │ │
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

1. **Input** — The frontend sends `{ diff, rules, llm_endpoint?, llm_model?, llm_api_key? }` to the backend with a `Bearer <token>` header.
2. **Auth check** — `app/auth.py` validates the bearer token against `AUTH_TOKEN` (or the request is rejected with `401`).
3. **Diff normalization** — `app/utils.py::parse_diff()` strips binary-file noise from the raw diff text.
4. **Indexing** — `app/rag.py::build_index()` chunks the rules document (≈400 characters per chunk, 80-character overlap) and builds an in-memory **TF-IDF index** over the chunks.
5. **Retrieval** — `search_index()` runs two passes:
   - The full cleaned diff is used as a query to retrieve the top-5 most relevant rule chunks.
   - The **added lines only** (via `extract_code_snippets()`) are used as a second, more focused query to retrieve up to 3 additional chunks.
   - Results are merged and de-duplicated, capped at 5 chunks total.
6. **LLM call** — `app/llm.py::call_llm()` builds a system + user prompt containing the diff and the retrieved rule chunks, then calls the configured OpenAI-compatible endpoint requesting a strict JSON array response.
7. **Parsing** — The LLM's JSON response is parsed defensively (handles markdown code fences, stray text before/after the array) into a list of `Finding` objects: `severity`, `file_line`, `risk`, `rule_violation`, `safer_code`, `source_chunk`.
8. **Screening checklist** — `main.py::build_screening_suggestions()` sorts findings by severity (`High → Medium → Low`) and produces up to 3 prioritized, human-readable action items.
9. **Response** — The backend returns `{ findings, screening_suggestions, error }`, which the frontend renders as severity-tagged cards with the offending file/line, the risk explanation, the exact rule text it violates, and a suggested code fix.

### Retrieval Layer (RAG)

> **Note:** the retrieval layer is implemented as a **pure-Python TF-IDF + cosine similarity engine** (see `backend/app/rag.py`). It does **not** use FAISS or `sentence-transformers`, despite those sometimes being referenced as the "target" stack for this class of project — this implementation was deliberately kept dependency-light so it runs anywhere Python does, with no model downloads and no native binary requirements. If you plan to swap in embedding-based retrieval later, `rag.py` is the only file you need to touch — `build_index()` and `search_index()` are the two functions the rest of the app depends on.

---

## 🧩 Project Structure

```
CodeSentinal/
├── backend/
│   ├── main.py                  # FastAPI app: routes, orchestration, screening logic
│   ├── requirements.txt         # Python dependencies (FastAPI, uvicorn, openai, dotenv)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── auth.py              # Username/password login + bearer token verification
│   │   ├── rag.py               # TF-IDF chunking + cosine-similarity search index
│   │   ├── llm.py                # Prompt construction, OpenAI-compatible LLM call, JSON parsing
│   │   ├── models.py             # Pydantic request/response schemas
│   │   ├── utils.py              # Diff cleaning, text chunking, added-line extraction
│   │   └── github.py             # GitHub REST client: PR diff + SECURITY.md import
│   └── demo/
│       ├── sample_diff.diff      # Demo diff with intentionally vulnerable code
│       └── sample_rules.md       # Sample security policy used by the demo
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx          # Login page (redirects to /analyze if authenticated)
│   │   │   ├── layout.tsx        # Root layout
│   │   │   ├── globals.css       # Tailwind globals
│   │   │   └── analyze/
│   │   │       └── page.tsx      # Main analysis workspace
│   │   ├── components/
│   │   │   ├── LoginForm.tsx
│   │   │   ├── DiffInput.tsx     # Paste/upload diff + GitHub import UI
│   │   │   ├── RulesUpload.tsx   # Upload/paste security rules
│   │   │   ├── DemoButton.tsx    # One-click demo data loader
│   │   │   ├── ResultsTable.tsx  # Renders findings
│   │   │   ├── SeverityBadge.tsx # High/Medium/Low badge styling
│   │   │   └── SourceChunk.tsx   # Displays the exact rule text a finding cites
│   │   ├── lib/
│   │   │   ├── api.ts            # Typed fetch client for the backend API
│   │   │   ├── auth.tsx          # React auth context (token storage)
│   │   │   └── settings.ts       # Local LLM key/endpoint/model preferences
│   │   └── types/
│   │       └── index.ts          # Shared TypeScript types
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── start.ps1                     # ⭐ One-command startup for Windows / PowerShell
├── start.sh                      # One-command startup for macOS / Linux
├── package.json                  # Root workspace scripts (dev/build/start/backend)
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

---

## ✅ Prerequisites

Before you start, make sure you have:

- **Windows with PowerShell** (for `start.ps1`) — or macOS/Linux with `bash` (for `start.sh`)
- **Python 3.10+** available on your `PATH` as `python`
- **Node.js 18+** and **npm**
- An **API key** for your LLM of choice:
  - **Gemini** (recommended, generous free tier) — get one from [Google AI Studio](https://aistudio.google.com/app/apikey)
  - Or any **OpenAI-compatible** API key (OpenAI, Groq, local proxy, etc.)

---

## 🚀 Getting Started (Windows / PowerShell)

Since `.\start.ps1` is the script you'll use day-to-day, here's exactly what it does and how to run it.

### 1. Clone the repository

```powershell
git clone https://github.com/midhunkmadhu10/CodeSentinal.git
cd CodeSentinal
```

### 2. Create your backend environment file (first run only)

`start.ps1` expects `backend\.env.example` to exist so it can copy it to `backend\.env`. Since `.env*` files are git-ignored, create `backend\.env.example` once:

```powershell
@"
AUTH_USERNAME=admin
AUTH_PASSWORD=codesentinal
AUTH_TOKEN=codesentinal-token-123
LLM_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=your-actual-gemini-api-key
LLM_MODEL=gemini-2.0-flash
"@ | Out-File -Encoding utf8 backend\.env.example
```

Similarly, create `frontend\.env.local.example` if it doesn't already exist:

```powershell
"NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File -Encoding utf8 frontend\.env.local.example
```

> You only need to do this once per machine. `start.ps1` will copy these into the real `.env` / `.env.local` files automatically on first run and will not overwrite them on subsequent runs.

### 3. Allow the script to run (first time only)

PowerShell blocks unsigned scripts by default. If you haven't relaxed this already:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Run it

```powershell
.\start.ps1
```

**What `start.ps1` does automatically, in order:**

1. Enters `backend\`, copies `.env.example` → `.env` if missing.
2. Creates a Python virtual environment at `backend\venv` if missing.
3. Installs backend dependencies from `requirements.txt` via `venv\Scripts\pip`.
4. Launches `uvicorn main:app --reload --host 0.0.0.0 --port 8000` in the background and prints its PID.
5. Enters `frontend\`, copies `.env.local.example` → `.env.local` if missing.
6. Runs `npm install` if `node_modules` is missing.
7. Launches `npm run dev` in the background and prints its PID.
8. Prints the running URLs and default login credentials.
9. Waits on both processes — press **Ctrl+C** in the PowerShell window to stop everything.

### 5. Open the app

- **Frontend:** http://localhost:3000
- **Backend docs (Swagger UI):** http://localhost:8000/docs
- **Login:** `admin` / `codesentinal` (unless you changed `AUTH_USERNAME` / `AUTH_PASSWORD`)

### 6. ⚠️ Set your real API key

`start.ps1` only creates `backend\.env` from the template — it does **not** know your API key. After the first run:

1. Stop the script (**Ctrl+C**).
2. Open `backend\.env` and set `LLM_API_KEY` to your real Gemini/OpenAI key.
3. Run `.\start.ps1` again.

---

## 🐧 Getting Started (macOS / Linux)

The equivalent one-command flow using `start.sh`:

```bash
git clone https://github.com/midhunkmadhu10/CodeSentinal.git
cd CodeSentinal
chmod +x start.sh
./start.sh
```

`start.sh` mirrors `start.ps1` exactly: it creates `.env` / `.env.local` from their example files, sets up a Python virtualenv, installs npm dependencies, and launches both services (backend on `:8000`, frontend on `:3000`). Press **Ctrl+C** to stop both processes cleanly (handled via a `trap`).

You'll need the same `backend/.env.example` and `frontend/.env.local.example` files described in step 2 above, since these are also git-ignored on Linux/macOS clones.

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

---

## ⚙️ Configuration Reference

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `AUTH_USERNAME` | `admin` | Login username for the app |
| `AUTH_PASSWORD` | `codesentinal` | Login password for the app |
| `AUTH_TOKEN` | `codesentinal-token-123` | Static bearer token issued on login and required on protected routes |
| `LLM_ENDPOINT` | `https://api.example.com/v1/chat/completions` | Base URL of an OpenAI-compatible chat completions API |
| `LLM_API_KEY` | *(none — required)* | Your API key for the configured LLM provider |
| `LLM_MODEL` | `gpt-4o-mini` | Model name to request from the endpoint |
| `PORT` | `8000` | Port used when running `python main.py` directly |

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

> The frontend also allows overriding the LLM key/endpoint/model per-browser via **Settings** in the UI (stored in `localStorage`, sent per-request as `llm_api_key` / `llm_endpoint` / `llm_model`) — useful if you don't want to store a key server-side at all.

---

## 🧪 Using the App

1. **Log in** with your configured credentials (`admin` / `codesentinal` by default).
2. Click **Load Demo** to populate a sample diff and sample security rules instantly — no setup required to see it work.
3. Click **Analyze**. Findings stream in as severity-tagged cards.
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
| `GET` | `/api/settings/status` | Yes | Reports whether a server-side API key is configured, plus the configured endpoint/model |
| `POST` | `/api/auth/login` | No | Body: `{ username, password }` → returns `{ token }` |
| `GET` | `/api/demo/diff` | Yes | Returns the bundled sample diff |
| `GET` | `/api/demo/rules` | Yes | Returns the bundled sample security rules |
| `POST` | `/api/github/import` | Yes | Body: `{ repository, pull_number?, access_token? }` → returns `{ repository, diff, policy, policy_path, error? }` |
| `POST` | `/api/analyze` | Yes | Body: `{ diff, rules, llm_endpoint?, llm_model?, llm_api_key? }` → returns `{ findings[], screening_suggestions[], error? }` |

Full interactive documentation (Swagger UI) is available at **http://localhost:8000/docs** whenever the backend is running.

---

## 🔐 Security Notes

- This project ships with **plaintext, shared-secret authentication** (`AUTH_USERNAME` / `AUTH_PASSWORD` / `AUTH_TOKEN`) and **no database** — it is designed for local/personal use or trusted internal environments, not multi-tenant production deployment as-is.
- **Change the default credentials** (`admin` / `codesentinal`) before exposing this beyond localhost.
- Never commit a real `backend/.env` file — it's already git-ignored, but double-check before pushing.
- GitHub access tokens supplied through the "Import GitHub" flow are used only for that single request and are not persisted anywhere in the backend.

---

## 🩹 Troubleshooting

| Symptom | Likely Cause / Fix |
|---|---|
| `start.ps1` fails with "cannot be loaded because running scripts is disabled" | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell session, then retry |
| `Copy-Item : Cannot find path '...\.env.example'` | You haven't created `backend\.env.example` / `frontend\.env.local.example` yet — see [step 2](#2-create-your-backend-environment-file-first-run-only) |
| Analysis fails with `LLM_API_KEY is not configured` | Set a real key in `backend\.env` (or provide one via the in-app Settings panel) and restart the backend |
| `Failed to parse LLM response as JSON` | The model didn't return valid JSON — try a different `LLM_MODEL`, lower the input size, or retry; `llm.py` already handles markdown-fenced responses defensively |
| Frontend can't reach the backend (`CORS` or network errors) | Confirm the backend is running on port `8000` and `NEXT_PUBLIC_API_URL` in `frontend/.env.local` matches it |
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
