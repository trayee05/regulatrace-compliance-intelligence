$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Run start-regulatrace.ps1 once to create .venv, then retry."
}
Push-Location $projectRoot
try {
    & $python -m pip install --disable-pip-version-check -r (Join-Path $projectRoot "requirements-ml.txt")
    if ($LASTEXITCODE -ne 0) { throw "Legal-BERT dependency installation failed." }
    & $python -m backend.legalbert
    if ($LASTEXITCODE -ne 0) { throw "Legal-BERT checkpoint setup failed." }
} finally {
    Pop-Location
}
Write-Host "Restart RegulaTrace to activate the local Legal-BERT model." -ForegroundColor Green
