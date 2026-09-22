$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location (Join-Path $repoRoot "backend")
try {
    python -m pip install .
    python -c "from app.core.migrations import upgrade_database; backup=upgrade_database(); print('Database upgraded; backup: ' + str(backup) if backup else 'Database is current.')"
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
}
finally {
    Pop-Location
}

Push-Location (Join-Path $repoRoot "frontend")
try {
    npm ci
    npm run build
}
finally {
    Pop-Location
}
