# ============================================================
# SoccerOracle — One-Command Local Launcher (PowerShell)
# Usage: .\start.ps1
# ============================================================

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " SoccerOracle — Starting Up" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

$ProjectRoot = $PSScriptRoot
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

# ── Check Python ──
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python not found. Install Python 3.11+ and try again." -ForegroundColor Red
    exit 1
}

# ── Check/Create venv ──
$VenvPath = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "[Setup] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvPath
}

$PipExe  = Join-Path $VenvPath "Scripts\pip.exe"
$PyExe   = Join-Path $VenvPath "Scripts\python.exe"

# ── Install Python deps ──
Write-Host "[Setup] Installing backend dependencies..." -ForegroundColor Yellow
& $PipExe install -r "$BackendDir\requirements.txt" -q

# ── Check/Install Node ──
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js not found. Install Node 18+ and try again." -ForegroundColor Red
    exit 1
}

# ── Install frontend deps ──
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "[Setup] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    npm install --silent
    Pop-Location
}

Write-Host ""
Write-Host "✅ Dependencies ready. Starting services..." -ForegroundColor Green
Write-Host ""

# ── Start FastAPI backend ──
Write-Host "[Backend] Starting FastAPI on http://localhost:8000 ..." -ForegroundColor Cyan
$BackendJob = Start-Job -ScriptBlock {
    param($venv, $proj)
    $env:PYTHONPATH = $proj
    & "$venv\Scripts\uvicorn.exe" "backend.api.main:app" --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $VenvPath, $ProjectRoot

Start-Sleep -Seconds 4

# ── Start Vite frontend ──
Write-Host "[Frontend] Starting React app on http://localhost:5173 ..." -ForegroundColor Cyan
$FrontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npm run dev
} -ArgumentList $FrontendDir

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host " SoccerOracle is RUNNING!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host " 🌐 Frontend : http://localhost:5173" -ForegroundColor White
Write-Host " 🔧 API Docs : http://localhost:8000/docs" -ForegroundColor White
Write-Host " 📊 API Root : http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host " Press CTRL+C to stop all services." -ForegroundColor Gray

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"

# Wait and stream logs
try {
    while ($true) {
        $BackendJob  | Receive-Job
        $FrontendJob | Receive-Job
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`n[Shutdown] Stopping services..." -ForegroundColor Yellow
    Stop-Job  $BackendJob, $FrontendJob
    Remove-Job $BackendJob, $FrontendJob
    Write-Host "[Shutdown] Done." -ForegroundColor Green
}
