@echo off
echo ======================================
echo  SoccerOracle - Starting Up
echo ======================================
echo.

if not exist ".venv" (
    echo [ERROR] Virtual environment not found. Please run start.ps1 to install dependencies first.
    pause
    exit /b 1
)

echo [Backend] Starting FastAPI on http://localhost:8000 ...
start "SoccerOracle Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000"

echo [Frontend] Starting React app on http://localhost:5173 ...
start "SoccerOracle Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ======================================
echo  SoccerOracle is RUNNING!
echo ======================================
echo.
echo  Web UI   : http://localhost:5173
echo  API Docs : http://localhost:8000/docs
echo.
echo  (Backend and Frontend are running in separate terminal windows)
echo.

timeout /t 3 >nul
start http://localhost:5173
