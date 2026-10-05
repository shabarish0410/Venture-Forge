$ErrorActionPreference = 'Stop'
$projectPath = Join-Path $PSScriptRoot 'venture-forge'
Set-Location -LiteralPath $projectPath
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment.' }
    & $pythonPath -m pip install -r requirements.lock -e .
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
& $pythonPath -c "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(name) for name in ('jwt', 'cryptography', 'email_validator')) else 1)"
if ($LASTEXITCODE -ne 0) {
    & $pythonPath -m pip install -r requirements.lock -e .
    if ($LASTEXITCODE -ne 0) { throw 'OAuth dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $projectPath 'node_modules\next'))) {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }
}
& $pythonPath scripts/run_local.py
