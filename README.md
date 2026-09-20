# CodeSentinal

CodeSentinal is a security-focused code review assistant. It compares a diff
with security rules, retrieves optional GitHub diffs and policies, and returns
structured findings through a Next.js frontend and FastAPI backend.

## Requirements

- Node.js 18+
- Python 3.11+
- Docker and Docker Compose (recommended for deployment)
- An OpenAI-compatible LLM endpoint and API key

## Local development

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.local.example frontend\.env.local
# Edit backend\.env: use unique AUTH_PASSWORD and AUTH_TOKEN values and set LLM_API_KEY
npm install
npm run backend
# In another terminal:
npm run dev
```

The frontend runs at `http://localhost:3000`; the API and Swagger docs run at
`http://localhost:8000` and `http://localhost:8000/docs`.

## Docker deployment

Create `backend/.env` from the example and replace every placeholder. Set
`CORS_ORIGINS` to the exact browser origin(s) that will host the frontend.
Then configure the public API URL and start both services:

```powershell
$env:NEXT_PUBLIC_API_URL = "https://api.example.com"
docker compose up --build -d
```

The backend health endpoint is `/api/health`. Compose waits for this endpoint
before starting the frontend. The production containers run without reload and
the backend process uses a non-root user.

## Environment variables

### Backend

| Variable | Required | Description |
| --- | --- | --- |
| `AUTH_USERNAME` | Yes | Login username |
| `AUTH_PASSWORD` | Yes | Strong login password |
| `AUTH_TOKEN` | Yes | Long random bearer token |
| `CORS_ORIGINS` | Yes | Comma-separated allowed frontend origins |
| `LLM_ENDPOINT` | Yes | OpenAI-compatible API base URL |
| `LLM_MODEL` | Yes | Model name |
| `LLM_API_KEY` | Yes | LLM provider key |
| `UVICORN_RELOAD` | No | Set `true` only for local development |

### Frontend

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | API base URL, inlined at frontend build time |

## Quality checks

```powershell
python -m compileall backend
npm run typecheck --workspace=frontend
npm run lint --workspace=frontend
npm run build --workspace=frontend
docker compose config
```

## Repository guidance

See [`agents.md`](agents.md) for the project layout, safe contribution rules,
and the expected handoff checks. Demo fixtures in `backend/demo/` are
intentional. Credentials, environment files, dependencies, build output, and
TypeScript build metadata must not be committed.
