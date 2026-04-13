@echo off
REM ---------------------------------------------------------------
REM alpaca-mcp-wrapper.cmd
REM
REM Launches the community alpaca-mcp-server with the environment
REM it needs:
REM   - PYTHONUTF8=1 so the server does not crash on Windows when
REM     loading its bundled trading-api OpenAPI spec (cp1252 bug)
REM   - working directory = repo root, so the relative path to
REM     .env resolves regardless of where Claude Code spawns us
REM
REM Registered as a user-scoped MCP server via
REM   scripts\register-alpaca-mcp.ps1
REM which sidesteps the project-scope trust approval flow that
REM silently skips .mcp.json servers in Claude Code 2.1.x.
REM ---------------------------------------------------------------
setlocal
set PYTHONUTF8=1
cd /d "%~dp0.."
uvx alpaca-mcp-server --env-file .env
