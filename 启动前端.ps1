$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location (Join-Path $repoRoot "frontend")
try {
    npm ci
    npm run dev -- --host 127.0.0.1
}
finally {
    Pop-Location
}
