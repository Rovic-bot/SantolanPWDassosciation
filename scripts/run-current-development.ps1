# Main development uses the fresh database. Startup never seeds or resets data.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath (Join-Path $projectRoot '.local/development')) {
        & $pythonPath -B scripts/current_development.py start
    } else {
        # Fresh checkout: the operator provisions .env/MySQL first. Do not
        # create, seed, reset, or silently migrate a database during startup.
        & $pythonPath -B manage.py check --database default
        if ($LASTEXITCODE -ne 0) { throw 'Configure this checkout using docs/FRESH_CHECKOUT.md first.' }
        & $pythonPath -B manage.py migrate --check
        if ($LASTEXITCODE -ne 0) { throw 'Pending migrations: follow docs/FRESH_CHECKOUT.md before starting.' }
        Write-Host 'Fresh checkout: http://127.0.0.1:8013/ — press Ctrl+C in this window to stop.'
        & $pythonPath -B manage.py runserver 127.0.0.1:8013
    }
    if ($LASTEXITCODE -ne 0) { throw 'Development startup failed. No database reset or fallback was performed.' }
} finally { Pop-Location }
