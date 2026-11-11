# Restart only the identity-verified main development website and database.
[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.local/development'))) {
        if ($CheckOnly) {
            & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B manage.py check --database default
            if ($LASTEXITCODE -ne 0) { throw 'Fresh checkout configuration check failed.' }
        } else {
            Write-Host 'For a fresh checkout, stop its running server with Ctrl+C before restarting.'
            & (Join-Path $PSScriptRoot 'run-current-development.ps1')
        }
        return
    }
    $action = if ($CheckOnly) { 'status' } else { 'restart' }
    & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B scripts/current_development.py $action
    if ($LASTEXITCODE -ne 0) { throw 'Development restart failed. No unrelated server or database was changed.' }
} finally { Pop-Location }
