$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
    exit 1
}

& .\.venv\Scripts\python.exe -m pytest apps/server/tests
