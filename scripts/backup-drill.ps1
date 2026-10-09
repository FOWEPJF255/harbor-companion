# Run an isolated authored-synthetic recovery drill; no live database or API calls.
$ErrorActionPreference = 'Stop'
$backupProjectRoot = Split-Path -Parent $PSScriptRoot
$backupPython = Join-Path $backupProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backupPython)) {
    throw 'Project Python environment is missing. Complete the normal project setup first.'
}
$backupPreviousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $backupProjectRoot 'server'
    & $backupPython -m harbor.backup drill
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic backup/recovery drill did not pass.' }
}
finally {
    $env:PYTHONPATH = $backupPreviousPythonPath
}
