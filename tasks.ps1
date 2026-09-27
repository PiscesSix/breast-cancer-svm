# Windows equivalent of the Makefile (make is usually not installed on Windows).
# Usage:  .\tasks.ps1 <install|train|compare|evaluate|sample|seed|test|lint|run|run-split|smoke|tex|all> [-Url https://...]
param(
    [Parameter(Position = 0)][string]$Task = "help",
    [string]$Url = "http://127.0.0.1:8000"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$env:PYTHONIOENCODING = "utf-8"

function Run([string[]]$cmd) {
    Write-Host ">> $($cmd -join ' ')" -ForegroundColor Cyan
    & $py @cmd
    if ($LASTEXITCODE -ne 0) { throw "Lệnh thất bại: $($cmd -join ' ')" }
}

# .env with a shared JWT_SECRET: the database API issues tokens, the model API verifies them.
function Ensure-Env {
    if (-not (Test-Path ".env")) {
        $secret = & $py -c "import secrets; print(secrets.token_urlsafe(48))"
        (Get-Content ".env.example" -Encoding UTF8) -replace "^JWT_SECRET=$", "JWT_SECRET=$secret" |
            Set-Content ".env" -Encoding UTF8
        Write-Host "Đã tạo .env (JWT_SECRET mới)" -ForegroundColor Green
    }
}

switch ($Task) {
    "install"   { if (-not (Test-Path ".venv")) { python -m venv .venv; $script:py = ".venv\Scripts\python.exe" }
                  Run @("-m", "pip", "install", "-r", "requirements-dev.txt") }
    "train"     { Run @("scripts/train.py") }
    "compare"   { Run @("scripts/train_comparison.py") }
    "evaluate"  { Run @("scripts/evaluate.py") }
    "sample"    { Run @("scripts/make_sample_request.py") }
    "seed"      { Ensure-Env; Run @("seed.py") }
    "test"      { Run @("-m", "pytest") }
    "lint"      { Run @("-m", "ruff", "check", ".") }
    # One process, like Render: dashboard at http://127.0.0.1:8000/
    "run"       { $env:SERVICE_MODE = "single"; Run @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") }
    # Three modules on three ports: web :8080, model API :8000, database API :8001
    "run-split" {
        Ensure-Env
        $env:SERVICE_MODE = "split"
        Run @("seed.py")
        $model = Start-Process $py -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -PassThru -NoNewWindow
        $db = Start-Process $py -ArgumentList "-m uvicorn db_api.main:app --host 127.0.0.1 --port 8001" -PassThru -NoNewWindow
        Write-Host "Web: http://127.0.0.1:8080  ·  API mô hình: http://127.0.0.1:8000/docs  ·  API CSDL: http://127.0.0.1:8001/docs" -ForegroundColor Green
        try { & $py -m uvicorn web.server:app --host 127.0.0.1 --port 8080 }
        finally { Stop-Process -Id $model.Id, $db.Id -ErrorAction SilentlyContinue }
    }
    "smoke"     { Run @("scripts/smoke_test.py", $Url) }
    "tex"       { Run @("docs/latex/make_tex_data.py"); Run @("docs/latex/build_overleaf.py") }
    "all"       { foreach ($t in "train", "compare", "evaluate", "sample", "test", "lint", "tex") { & $PSCommandPath $t } }
    default     { Write-Host "Các lệnh: install, train, compare, evaluate, sample, seed, test, lint, run, run-split, smoke [-Url ...], tex, all" }
}
