$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location (Join-Path $repoRoot "backend")
try {
    python -m pip install -r requirements.txt
    python -c "from app.core.migrations import upgrade_database; backup=upgrade_database(); print('Database upgraded; backup: ' + str(backup) if backup else 'Database is current.')"
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
