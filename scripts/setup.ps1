$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path '.venv/Scripts/python.exe')) { python -m venv .venv }
    & '.venv/Scripts/python.exe' -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Push-Location 'web'
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
} finally { Pop-Location }
