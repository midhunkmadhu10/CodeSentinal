#!/bin/bash
# CodeSentinal Lite — Start Script
# Starts both the FastAPI backend and Next.js frontend.
# Usage: ./start.sh

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║        CodeSentinal Lite — Starting...       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Backend ──────────────────────────────────────────────────────────────────
echo "🔧 Starting backend (FastAPI)..."
cd backend

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "   Created backend/.env from .env.example"
    echo "   ⚠️  Edit backend/.env to set your LLM_API_KEY"
fi

# Install Python deps if needed
if [ ! -d "venv" ]; then
    echo "   Creating Python virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

# Start backend in background
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "   Backend running on http://localhost:8000 (PID: $BACKEND_PID)"
deactivate
cd ..

echo ""

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "🎨 Starting frontend (Next.js)..."
cd frontend

# Create .env.local from example if it doesn't exist
if [ ! -f .env.local ]; then
    cp .env.local.example .env.local
    echo "   Created frontend/.env.local from .env.local.example"
fi

# Install npm deps if needed
if [ ! -d "node_modules" ]; then
    echo "   Installing npm dependencies..."
    npm install
fi

# Start frontend
npm run dev &
FRONTEND_PID=$!
echo "   Frontend running on http://localhost:3000 (PID: $FRONTEND_PID)"
cd ..

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅ CodeSentinal Lite is running!            ║"
echo "║                                              ║"
echo "║  Frontend:  http://localhost:3000             ║"
echo "║  Backend:   http://localhost:8000             ║"
echo "║  API Docs:  http://localhost:8000/docs        ║"
echo "║                                              ║"
echo "║  Login: admin / codesentinal                 ║"
echo "║                                              ║"
echo "║  Press Ctrl+C to stop all services.          ║"
echo "╚══════════════════════════════════════════════╝"

# Trap Ctrl+C and kill both processes
trap "echo ''; echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Wait for both
wait