$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Run scripts/setup.ps1 first.' }
    if (-not (Test-Path 'web/dist/index.html')) { throw 'Build the frontend first: cd web; npm run build.' }
    & '.venv/Scripts/python.exe' -m uvicorn harbor.main:app --host 127.0.0.1 --port 8765
} finally { Pop-Location }
