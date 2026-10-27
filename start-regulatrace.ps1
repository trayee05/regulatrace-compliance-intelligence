param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$stateDirectory = Join-Path $projectRoot ".regulatrace"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$requirements = Join-Path $projectRoot "requirements.txt"
$requirementsMarker = Join-Path $projectRoot ".venv\.requirements.sha256"
$pidFile = Join-Path $stateDirectory "server.pid"
$url = "http://127.0.0.1:8000"

New-Item -ItemType Directory -Force -Path $stateDirectory | Out-Null

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        Write-Host "RegulaTrace is already running at $url" -ForegroundColor Green
        if (-not $NoBrowser) { Start-Process $url }
        exit 0
    }
}

if (-not (Test-Path $venvPython)) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if ($python) {
        & $python.Source -m venv (Join-Path $projectRoot ".venv")
    } elseif ($pyLauncher) {
        & $pyLauncher.Source -3 -m venv (Join-Path $projectRoot ".venv")
    } elseif (Test-Path $codexPython) {
        & $codexPython -m venv (Join-Path $projectRoot ".venv")
    } else {
        throw "Python 3.11+ was not found. Install Python, then run this launcher again."
    }
}

$requirementsHash = (Get-FileHash $requirements -Algorithm SHA256).Hash
$installedHash = if (Test-Path $requirementsMarker) { Get-Content $requirementsMarker } else { "" }
if ($requirementsHash -ne $installedHash) {
    & $venvPython -c "import fastapi, uvicorn, pydantic, pytest, httpx, pypdf, multipart, z3, neo4j" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Preparing the RegulaTrace runtime (first launch only)..." -ForegroundColor Cyan
        & $venvPython -m pip install --disable-pip-version-check -r $requirements
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    }
    Set-Content -Path $requirementsMarker -Value $requirementsHash
}

$stdout = Join-Path $stateDirectory "server.out.log"
$stderr = Join-Path $stateDirectory "server.err.log"
$process = Start-Process -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Set-Content -Path $pidFile -Value $process.Id

for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 1
        if ($health.status -eq "ok") {
            Write-Host "RegulaTrace Presentation Edition is live at $url" -ForegroundColor Green
            Write-Host "API documentation: $url/api/docs" -ForegroundColor DarkGray
            if (-not $NoBrowser) { Start-Process $url }
            exit 0
        }
    } catch { Start-Sleep -Milliseconds 250 }
}

throw "The server did not become ready. Review $stderr for diagnostics."
