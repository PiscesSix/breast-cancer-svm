# Windows equivalent of the Makefile (make is usually not installed on Windows).
# Usage:  .\tasks.ps1 <install|train|evaluate|sample|test|lint|run|smoke|tex|all> [-Url https://...]
param(
    [Parameter(Position = 0)][string]$Task = "help",
    [string]$Url = "http://127.0.0.1:8000"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

function Run([string[]]$cmd) {
    Write-Host ">> $($cmd -join ' ')" -ForegroundColor Cyan
    & $py @cmd
    if ($LASTEXITCODE -ne 0) { throw "Lệnh thất bại: $($cmd -join ' ')" }
}

switch ($Task) {
    "install"  { if (-not (Test-Path ".venv")) { python -m venv .venv; $script:py = ".venv\Scripts\python.exe" }
                 Run @("-m", "pip", "install", "-r", "requirements-dev.txt") }
    "train"    { Run @("scripts/train.py") }
    "evaluate" { Run @("scripts/evaluate.py") }
    "sample"   { Run @("scripts/make_sample_request.py") }
    "test"     { Run @("-m", "pytest") }
    "lint"     { Run @("-m", "ruff", "check", ".") }
    "run"      { Run @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") }
    "smoke"    { Run @("scripts/smoke_test.py", $Url) }
    "tex"      { Run @("docs/latex/make_tex_data.py"); Run @("docs/latex/build_overleaf.py") }
    "all"      { foreach ($t in "train", "evaluate", "sample", "test", "lint", "tex") { & $PSCommandPath $t } }
    default    { Write-Host "Các lệnh: install, train, evaluate, sample, test, lint, run, smoke [-Url ...], tex, all" }
}
