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
# project and user scope before adding the new one.
# ---------------------------------------------------------------

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$wrapper  = Join-Path $repoRoot "scripts\alpaca-mcp-wrapper.cmd"

if (-not (Test-Path $wrapper)) {
    Write-Error "Wrapper script not found: $wrapper"
    exit 1
}

$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Warning ".env not found at $envFile"
    Write-Warning "The server will crash at runtime until you create it."
    Write-Warning "See docs/mcp-alpaca-setup.md for the expected contents."
}

Write-Host "Removing any prior alpaca MCP registrations..."
# Both calls are allowed to fail (server not yet registered at that scope).
& claude mcp remove alpaca -s project 2>$null | Out-Null
& claude mcp remove alpaca -s user    2>$null | Out-Null
& claude mcp remove alpaca -s local   2>$null | Out-Null

Write-Host "Registering alpaca at user scope..."
Write-Host "  wrapper: $wrapper"
& claude mcp add alpaca --scope user $wrapper
if ($LASTEXITCODE -ne 0) {
    Write-Error "claude mcp add failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Verifying..."
& claude mcp get alpaca

Write-Host ""
Write-Host "Done. Relaunch Claude Code and the alpaca tools should load."
