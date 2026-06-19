param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
    exit 1
}

if (-not $env:JWT_SECRET) {
    $env:JWT_SECRET = "change-this-for-local-demo"
}

if (-not $env:SECURE_CHAT_DATA_DIR) {
    $env:SECURE_CHAT_DATA_DIR = Join-Path $Root "data"
}

$UvicornArgs = @(
    "-m", "uvicorn",
    "apps.server.main:app",
    "--host", $HostName,
    "--port", "$Port"
)

if (-not $NoReload) {
    $UvicornArgs += "--reload"
}

Write-Host "Starting Secure Web Chat at http://$HostName`:$Port"
& .\.venv\Scripts\python.exe @UvicornArgs
