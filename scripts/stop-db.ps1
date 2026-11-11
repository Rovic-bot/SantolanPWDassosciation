$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
& "$projectRoot/.venv/Scripts/python.exe" "$PSScriptRoot/local_mysql.py" stop
if ($LASTEXITCODE -ne 0) { throw 'MySQL shutdown failed.' }
