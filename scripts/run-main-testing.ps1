param([switch]$Restore)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $python = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if ($Restore) {
        & $python scripts/main_testing.py restore
        if ($LASTEXITCODE -ne 0) { throw 'Fictional baseline restore failed; previous database retained.' }
    }
    & $python scripts/main_testing.py start
    if ($LASTEXITCODE -ne 0) { throw 'Main testing startup failed.' }
} finally { Pop-Location }
