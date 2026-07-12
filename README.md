# CodeSentinal 

> **AI-Powered PR Security Reviewer** — Paste a diff, upload your rules, get instant security findings.

![CodeSentinal Lite](https://img.shields.io/badge/status-beta-blue)
![Stack](https://img.shields.io/badge/stack-Next.js%20%2B%20FastAPI%20%2B%20FAISS-purple)

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ and **npm**
- **Python** 3.10+
- A **Gemini API key** or any OpenAI-compatible API key

### 1. Clone & Install

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure

```bash
# Backend — add your API key
cp backend/.env.example backend/.env
# Edit backend/.env and set:
#   LLM_API_KEY=your-actual-api-key
#   LLM_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai/
#   LLM_MODEL=gemini-2.0-flash

# Frontend
cp frontend/.env.local.example frontend/.env.local
```

### 3. Run

```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

Or use the unified start script:

```bash
chmod +x start.sh && ./start.sh
```

### 4. Open

- **Frontend**: http://localhost:3000
- **Login**: `admin` / `codesentinal`
- **Backend API**: http://localhost:8000/docs

## 🧪 Try It Out

1. Log in with `admin` / `codesentinal`
2. Click **Load Demo** — sample diff and rules are populated
3. Click **Analyze** — findings appear instantly
4. Or paste your own diff and upload your own SECURITY.md
5. Or click **Import GitHub** to load a pull-request diff and the repository's security policy

## 🏗 Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Next.js 14  │────▶│  FastAPI     │────▶│  OpenAI API  │
│  (Frontend)  │     │  (Backend)   │     │  (Gemini)    │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐
                     │  FAISS +     │
                     │  MiniLM-L6   │
                     │  (RAG)       │
                     └──────────────┘
```

### Flow

1. **User** pastes a diff + uploads security rules
2. **Backend** chunks the rules, embeds them with `sentence-transformers`, indexes in FAISS
3. **RAG** retrieves the top-5 most relevant rule chunks for the diff
4. **LLM** analyzes the diff + rule chunks, returns structured JSON findings
5. **Frontend** renders the findings with severity badges, file references, source chunks, and a merge-screening checklist

### GitHub import

Use **Import GitHub** to connect a repository by its `owner/repository` name or GitHub URL. Enter a pull request number to scan that PR, or leave it empty to compare the latest commit with its parent. The importer automatically loads one of these policy files when present:

- `SECURITY.md`
- `.github/SECURITY.md`
- `SECURITY_POLICY.md`

Public repositories need no credentials. For a private repository, provide a fine-grained GitHub token with read access to that repository. The token is used only for the import request and is not stored by CodeSentinal.

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_USERNAME` | `admin` | Login username |
| `AUTH_PASSWORD` | `codesentinal` | Login password |
| `AUTH_TOKEN` | `codesentinal-token-123` | Bearer token for API calls |
| `LLM_ENDPOINT` | — | OpenAI-compatible API endpoint |
| `LLM_API_KEY` | — | Your API key |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend API proxy target |

### Gemini Configuration

For **Google Gemini**, use:

```
LLM_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=your-gemini-api-key
LLM_MODEL=gemini-2.0-flash
```

## 🧩 Project Structure

```
codesentinal-lite/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Env template
│   ├── app/
│   │   ├── auth.py           # Token auth
│   │   ├── rag.py            # Chunking, embedding, FAISS
│   │   ├── llm.py            # LLM API call + parsing
│   │   ├── models.py         # Pydantic schemas
│   │   └── utils.py          # Diff parsing, text splitting
│   └── demo/
│       ├── sample_diff.diff  # Demo diff with vulnerabilities
│       └── sample_rules.md   # Sample security rules
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js pages (login, analyze)
│   │   ├── components/       # React components
│   │   ├── lib/              # API client, auth context
│   │   └── types/            # TypeScript types
│   └── ...
├── start.sh                  # Unified start script
└── README.md
```

## 📝 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | No | Health check |
| POST | `/api/auth/login` | No | Login, returns token |
| GET | `/api/demo/diff` | Yes | Get sample diff |
| GET | `/api/demo/rules` | Yes | Get sample rules |
| POST | `/api/analyze` | Yes | Analyze diff against rules |

## 🛠 Tech Stack

- **Frontend**: Next.js 14, React 18, Tailwind CSS, Lucide Icons
- **Backend**: FastAPI, Python 3.11+
- **RAG**: sentence-transformers (all-MiniLM-L6-v2), FAISS
- **LLM**: OpenAI-compatible API (Gemini, OpenAI, etc.)
- **Auth**: Simple token-based (no database)

## 📄 License

MIT — built for hackathons and security tooling exploration.
