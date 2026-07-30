param(
    [int]$Port = 8000,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot "backend"
$venvPath = Join-Path $backendPath ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Host "Creating Python virtual environment..."
    py -3.12 -m venv $venvPath
}

if (-not (Test-Path $pythonPath)) {
    throw "Python 3.12 was not found. Install Python 3.12+ and try again."
}

if (-not $SkipInstall) {
    Write-Host "Installing backend dependencies..."
    & $pythonPath -m pip install -e "$backendPath[dev]"
}

$env:DATABASE_URL = "sqlite:///./paradox_cast.db"
$env:AUTO_CREATE_SCHEMA = "true"
$env:LOCAL_BOOTSTRAP_ENABLED = "true"
$env:CORS_ORIGINS = "http://localhost:5173"

Set-Location $backendPath
Write-Host "Starting Paradox Cast backend at http://localhost:$Port"
Write-Host "Press Ctrl+C to stop."
& $pythonPath -m uvicorn app.main:app --reload --port $Port
