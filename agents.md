# CodeSentinal agent guide

## Project layout

- `frontend/`: Next.js 14 application (`frontend/src`).
- `backend/`: FastAPI service (`backend/main.py`).
- `docker-compose.yml`: local two-service deployment.
- `backend/demo/`: tracked demo fixtures used by the UI.

## Local setup

1. Copy `backend/.env.example` to `backend/.env` and set a unique password,
   token, and `LLM_API_KEY`.
2. Copy `frontend/.env.local.example` to `frontend/.env.local` if the API is
   not available at `http://localhost:8000`.
3. Run `npm install` at the repository root.
4. Run `npm run dev` and `npm run backend`, or use `docker compose up --build`.

## Checks before handoff

- Frontend: `npm run typecheck --workspace=frontend`, `npm run lint --workspace=frontend`,
  and `npm run build --workspace=frontend`.
- Backend: `python -m compileall backend`.
- Compose: `docker compose config`; verify `/api/health` after startup.

## Contribution rules

- Never commit credentials, `.env` files, virtual environments, dependencies,
  Next build output, or TypeScript build metadata.
- Never log access tokens or include them in client-facing errors.
- Keep API changes synchronized between Pydantic models and the frontend client.
- Use `UVICORN_RELOAD=true` only for local development.
- Keep changes focused and preserve the demo flow.
