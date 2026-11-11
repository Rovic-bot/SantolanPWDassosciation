# Main development checkout on port 8000 and its retained fictional database.
# Its ignored local manifest pins the database; never fall back to .env.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$entry = Join-Path $projectRoot '.local/ronnel-development-20261026/start.py'
if (-not (Test-Path -LiteralPath $entry)) {
    throw 'The main development configuration is not provisioned on this computer. No ordinary database was used.'
}
Push-Location $projectRoot
try {
    & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B $entry
    if ($LASTEXITCODE -ne 0) { throw 'Current development startup failed. No fallback or database reset was performed.' }
} finally { Pop-Location }
