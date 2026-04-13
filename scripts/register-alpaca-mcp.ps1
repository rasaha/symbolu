# ---------------------------------------------------------------
# register-alpaca-mcp.ps1
#
# Registers the Alpaca MCP server at USER scope so Claude Code
# always loads it, without needing the project-scope trust
# approval flow (which silently skips .mcp.json servers in
# some Claude Code 2.1.x builds on Windows).
#
# The server is pointed at scripts\alpaca-mcp-wrapper.cmd, which
# hardcodes PYTHONUTF8=1 and cds into the repo root so --env-file
# .env resolves correctly.
#
# Run from the repo root (or anywhere — the script resolves paths
# on its own):
#
#     powershell -ExecutionPolicy Bypass -File scripts\register-alpaca-mcp.ps1
#
# Safe to re-run: it removes any prior alpaca registration at
# user and local scope before adding the new one. Errors from
# "remove" calls are swallowed on purpose — they fire when there
# is nothing to remove, which is the normal case on first run.
# ---------------------------------------------------------------

# Don't halt on native command stderr. The "claude mcp remove" calls
# below intentionally error out when the server hasn't been registered
# yet; we want to ignore those.
$ErrorActionPreference = "Continue"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$wrapper  = Join-Path $repoRoot "scripts\alpaca-mcp-wrapper.cmd"

if (-not (Test-Path $wrapper)) {
    Write-Host "ERROR: Wrapper script not found: $wrapper" -ForegroundColor Red
    exit 1
}

$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "WARNING: .env not found at $envFile" -ForegroundColor Yellow
    Write-Host "         The server will crash at runtime until you create it." -ForegroundColor Yellow
    Write-Host "         See docs/mcp-alpaca-setup.md for the expected contents." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Write-Host "=== Removing any prior alpaca MCP registrations ==="
Write-Host "(errors here are expected and ignored)"
foreach ($scope in @("user", "local")) {
    Write-Host "  scope=$scope ..." -NoNewline
    try {
        & claude mcp remove alpaca -s $scope 2>&1 | Out-Null
        Write-Host " done"
    } catch {
        Write-Host " (ignored)"
    }
}

Write-Host ""
Write-Host "=== Registering alpaca at user scope ==="
Write-Host "  wrapper: $wrapper"
# Options (--scope user) must come BEFORE the positional name.
& claude mcp add --scope user alpaca $wrapper
$addExit = $LASTEXITCODE
if ($addExit -ne 0) {
    Write-Host ""
    Write-Host "ERROR: claude mcp add failed with exit code $addExit" -ForegroundColor Red
    Write-Host "Likely causes:" -ForegroundColor Red
    Write-Host "  - alpaca already registered at user scope — rerun this script" -ForegroundColor Red
    Write-Host "  - claude CLI not on PATH — run 'claude --version' to verify" -ForegroundColor Red
    exit $addExit
}

Write-Host ""
Write-Host "=== Verifying ==="
& claude mcp get alpaca

Write-Host ""
Write-Host "Done. Relaunch Claude Code and the alpaca tools should load."
Write-Host "Test with: /mcp  (inside Claude Code) or send a chat prompt asking"
Write-Host "Claude to call the alpaca account info tool."
