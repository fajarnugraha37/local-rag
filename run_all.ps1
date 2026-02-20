# run_all.ps1 - run smoke tests and evaluation
# Usage: .\run_all.ps1

Write-Host "Running pytest smoke tests..."
python -m pytest -q
$pytestExit = $LASTEXITCODE
if ($pytestExit -ne 0) {
    Write-Host "pytest failed with exit code $pytestExit" -ForegroundColor Yellow
    exit $pytestExit
}

Write-Host "Running eval runner..."
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results.json
$evalExit = $LASTEXITCODE
if ($evalExit -ne 0) {
    Write-Host "eval runner failed with exit code $evalExit" -ForegroundColor Yellow
    exit $evalExit
}

Write-Host "All tasks completed successfully." -ForegroundColor Green
