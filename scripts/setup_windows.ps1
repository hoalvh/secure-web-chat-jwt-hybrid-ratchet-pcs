param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Creating virtual environment..."
& $Python -m venv .venv

Write-Host "Upgrading pip..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "Installing dependencies..."
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run the app with:"
Write-Host "  .\scripts\run_dev.ps1"
