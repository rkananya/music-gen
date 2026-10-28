$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $env:ACESTEP_BASE_URL) { $env:ACESTEP_BASE_URL = 'http://127.0.0.1:8001' }
$appPort = if ($env:APP_PORT) { $env:APP_PORT } else { '7860' }
$modelPython = Join-Path $PSScriptRoot 'ACE-Step-1.5\venv_xpu\Scripts\python.exe'
$python = if (Test-Path $modelPython) { $modelPython } else { (Get-Command python -ErrorAction Stop).Source }
Write-Host "Starting Verse / Voice at http://127.0.0.1:$appPort"
Write-Host "ACE-Step API: $env:ACESTEP_BASE_URL"
& $python server.py
