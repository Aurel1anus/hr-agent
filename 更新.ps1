$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location (Join-Path $repoRoot "backend")
try {
    python -m pip install -r requirements.txt
    python -c "from app.core.migrations import upgrade_database; print('无需数据库升级。' if upgrade_database() is None else '已完成备份与数据库升级。')"
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
