$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location (Join-Path $repoRoot "backend")
try {
    python -m pip install -r requirements.txt
    python -c "from app.core.migrations import upgrade_database; print('数据库已是最新版本。' if upgrade_database() is None else '数据库已备份并升级。')"
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
