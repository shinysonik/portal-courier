# Run the EnergoPlus portal on port 5001
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "Starting EnergoPlus portal on http://localhost:5001" -ForegroundColor Cyan
Write-Host "Login: anna / real_secret_123" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
uvicorn app:app --host 0.0.0.0 --port 5001 --reload