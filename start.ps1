Write-Host "=============================================="
Write-Host "        CodeSentinal Lite - Starting...       "
Write-Host "=============================================="

# ── Backend ──────────────────────────────────────────────────────────────────
Write-Host "Starting backend (FastAPI)..."
Set-Location -Path "backend"

if (-not (Test-Path ".env")) {
    Copy-Item -Path ".env.example" -Destination ".env"
    Write-Host "   Created backend/.env from .env.example"
    Write-Host "   Please edit backend/.env to set your LLM_API_KEY"
}

if (-not (Test-Path "venv")) {
    Write-Host "   Creating Python virtual environment..."
    python -m venv venv
}

.\venv\Scripts\pip install -q -r requirements.txt
$backendProcess = Start-Process -NoNewWindow -FilePath ".\venv\Scripts\uvicorn.exe" -ArgumentList "main:app","--reload","--host","0.0.0.0","--port","8000" -PassThru
Write-Host "   Backend started (PID: $($backendProcess.Id))"

Set-Location -Path ".."

Write-Host ""

# ── Frontend ─────────────────────────────────────────────────────────────────
Write-Host "Starting frontend (Next.js)..."
Set-Location -Path "frontend"

if (-not (Test-Path ".env.local")) {
    Copy-Item -Path ".env.local.example" -Destination ".env.local"
    Write-Host "   Created frontend/.env.local from .env.local.example"
}

if (-not (Test-Path "node_modules")) {
    Write-Host "   Installing npm dependencies..."
    npm install
}

$frontendProcess = Start-Process -NoNewWindow -FilePath "npm.cmd" -ArgumentList "run","dev" -PassThru
Write-Host "   Frontend started (PID: $($frontendProcess.Id))"

Set-Location -Path ".."

Write-Host ""
Write-Host "=============================================="
Write-Host "  CodeSentinal Lite is running!               "
Write-Host "                                              "
Write-Host "  Frontend:  http://localhost:3000            "
Write-Host "  Backend:   http://localhost:8000            "
Write-Host "  API Docs:  http://localhost:8000/docs       "
Write-Host "                                              "
Write-Host "  Login: admin / codesentinal                 "
Write-Host "                                              "
Write-Host "  Press Ctrl+C to stop the powershell window. "
Write-Host "  (You may need to kill the processes later)  "
Write-Host "=============================================="

try {
    Wait-Process -Id $backendProcess.Id, $frontendProcess.Id
} finally {
    Write-Host "Stopping processes..."
    Stop-Process -Id $backendProcess.Id, $frontendProcess.Id -ErrorAction SilentlyContinue
}
