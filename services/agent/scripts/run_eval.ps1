# PowerShell script to run model evaluation

Write-Host "=== AgentShield Model Evaluation ===" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is running
Write-Host "Checking Ollama..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "✓ Ollama is running" -ForegroundColor Green
}
catch {
    Write-Host "ERROR: Ollama not running" -ForegroundColor Red
    Write-Host "Start Ollama from the Start Menu or run 'ollama serve'" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Available models:" -ForegroundColor Yellow
$tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags"
$tags.models | ForEach-Object { Write-Host "  - $($_.name)" }

Write-Host ""
Write-Host "Running evaluation..." -ForegroundColor Yellow
Write-Host ""

# Run Python evaluation
python eval/model_eval.py

Write-Host ""
Write-Host "✓ Evaluation complete" -ForegroundColor Green
Write-Host "Results should be reviewed in console output" -ForegroundColor Cyan
