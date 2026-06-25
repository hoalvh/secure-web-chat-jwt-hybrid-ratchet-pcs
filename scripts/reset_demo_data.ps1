$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

# Files the local demo can create. The JSON store is from the old storage layer;
# secure_chat.db (+ WAL/SHM) is the current SQLite store. Postgres deploys are
# reset on the database side, not here.
$Targets = @(
    "data\demo_store.json",
    "data\secure_chat.db",
    "data\secure_chat.db-wal",
    "data\secure_chat.db-shm"
)

$removed = $false
foreach ($relative in $Targets) {
    $path = Join-Path $Root $relative
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Force
        Write-Host "Removed $path"
        $removed = $true
    }
}

if (-not $removed) {
    Write-Host "No local demo data found."
}

Write-Host "Start the server again to recreate an empty demo store."
