# ci/run_local.ps1 — run the CRIE CI regression guards locally on Windows.
#
# Runs the SAME checks as .github/workflows/ci.yml:
#   1. Workflow static validation (ACTIVE/shipped set)
#   2. Migration replay: bootstrap roles -> apply chain twice (idempotency) -> verify
#
# Prerequisites:
#   - Python 3.x on PATH            (python --version)
#   - psql on PATH                  (psql --version)
#   - A reachable PostgreSQL 16 with pgvector available. Easiest:
#       docker run --rm -d --name crie-ci -e POSTGRES_PASSWORD=postgres `
#         -e POSTGRES_DB=crie_ci -p 5432:5432 pgvector/pgvector:pg16
#
# Usage (from repo root):
#   $env:PGURL = "postgres://postgres:postgres@localhost:5432/crie_ci"   # optional
#   ./ci/run_local.ps1
#
# The replay DB should be empty on first run; re-running is safe (the chain is
# idempotent — that is exactly what pass 2 proves).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $env:PGURL) { $env:PGURL = "postgres://postgres:postgres@localhost:5432/crie_ci" }

# Resolve a real Python (reject the Windows Store alias stubs under WindowsApps).
$py = $null
foreach ($c in 'python', 'python3', 'py') {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { $py = $cmd.Source; break }
}
if (-not $py) { throw "No usable Python interpreter found on PATH (the WindowsApps alias stubs do not count). Install Python 3.x." }

# The active workflow set is configuration-driven: with no path args the validator
# reads ci/active_workflows.txt (the single source of truth for what CI validates).
Write-Host "== 1/3  Workflow static validation ==" -ForegroundColor Cyan
& $py "$root/ci/validate_workflows.py"
if ($LASTEXITCODE -ne 0) { throw "workflow validation FAILED" }

Write-Host "== 2/3  Migration replay (bootstrap + chain x2) ==" -ForegroundColor Cyan
psql $env:PGURL -v ON_ERROR_STOP=1 -f "$root/ci/replay/bootstrap.sql"
if ($LASTEXITCODE -ne 0) { throw "bootstrap FAILED" }
foreach ($pass in 1, 2) {
    Write-Host "-- apply pass $pass --"
    Get-ChildItem "$root/migrations/*.sql" | Sort-Object Name | ForEach-Object {
        psql $env:PGURL -v ON_ERROR_STOP=1 -f $_.FullName | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "migration FAILED: $($_.Name)" }
    }
}

Write-Host "== 3/3  Post-replay verification ==" -ForegroundColor Cyan
psql $env:PGURL -v ON_ERROR_STOP=1 -f "$root/ci/replay/verify.sql"
if ($LASTEXITCODE -ne 0) { throw "verification FAILED" }

Write-Host "`nALL GUARDS PASSED" -ForegroundColor Green
