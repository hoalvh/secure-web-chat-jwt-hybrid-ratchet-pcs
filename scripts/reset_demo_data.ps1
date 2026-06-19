$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$DataFile = Join-Path $Root "data\demo_store.json"

if (Test-Path $DataFile) {
    Remove-Item -LiteralPath $DataFile -Force
    Write-Host "Removed $DataFile"
} else {
    Write-Host "No demo data file found."
}

Write-Host "Start the server again to recreate an empty demo store."
