$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $python = Join-Path $projectRoot '.venv/Scripts/python.exe'
    & $python scripts/local_mysql.py start
    if ($LASTEXITCODE -ne 0) { throw 'Project-local MySQL startup failed.' }
    & $python manage.py runlocal 127.0.0.1:8001 --settings=config.demo_settings
    if ($LASTEXITCODE -ne 0) { throw 'Fictional workspace startup failed.' }
} finally { Pop-Location }
