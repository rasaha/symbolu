# Upstream bug: alpaca-mcp-server cp1252 crash on Windows

**Status:** Not yet filed. Draft ready to paste at
<https://github.com/alpacahq/alpaca-mcp-server/issues/new>.

**Workaround in this repo:** `scripts/alpaca-mcp-wrapper.cmd` sets
`PYTHONUTF8=1` before launching the server, and `.mcp.json` sets the
same env var. Both sidestep the bug. This draft exists so the upstream
fix can be tracked once filed.

---

## Title

```
UnicodeDecodeError on Windows loading bundled trading-api spec (server.py:35)
```

## Body

## Summary

On Windows with the default `cp1252` code page, `alpaca-mcp-server` crashes at
startup before the MCP handshake when loading its bundled `trading-api`
OpenAPI spec. Root cause is a missing `encoding="utf-8"` argument in
`alpaca_mcp_server/server.py:35`. One-character fix.

## Environment

- OS: Windows 11
- Python: 3.13 (CPython, 64-bit)
- Package: `alpaca-mcp-server` 3.2.3 (via FastMCP 3.2.3)
- Installer: `uv` 0.11.6, launched as `uvx alpaca-mcp-server --env-file .env`
- `PYTHONUTF8` env var: **not set** (system default cp1252 applies)

## Reproduction

```powershell
# Fresh Windows PowerShell, no PYTHONUTF8
uvx alpaca-mcp-server --env-file .env
```

Crashes immediately:

```
Traceback (most recent call last):
  File "...\alpaca_mcp_server\cli.py", line 48, in main
    server = build_server()
  File "...\alpaca_mcp_server\server.py", line 117, in build_server
    spec = _load_spec("trading-api")
  File "...\alpaca_mcp_server\server.py", line 35, in _load_spec
    return json.loads(path.read_text())
  File "...\pathlib\_local.py", line 546, in read_text
    return PathBase.read_text(self, encoding, errors, newline)
  File "...\encodings\cp1252.py", line 23, in decode
    return codecs.charmap_decode(input, self.errors, decoding_table)[0]
UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 8224:
character maps to <undefined>
```

## Root cause

`alpaca_mcp_server/server.py:35` calls `path.read_text()` without an explicit
encoding. `pathlib.Path.read_text()` defaults to
`locale.getpreferredencoding(False)`, which on Windows is `cp1252`. The
bundled `trading-api` spec is UTF-8 and contains bytes (e.g., `0x9d` at
offset 8224) that aren't valid in cp1252, so decoding fails.

On macOS/Linux the issue doesn't reproduce because
`locale.getpreferredencoding()` there is already UTF-8.

## Suggested fix

One-character change in `alpaca_mcp_server/server.py:35`:

```python
# before
return json.loads(path.read_text())

# after
return json.loads(path.read_text(encoding="utf-8"))
```

Worth grepping the rest of the codebase for other `.read_text()` /
`open(..., 'r')` calls that read bundled text assets — any of them will
fail the same way on Windows.

## Workaround (for anyone hitting this before the fix ships)

Set `PYTHONUTF8=1` in the process environment before launching the server:

```powershell
$env:PYTHONUTF8 = "1"
uvx alpaca-mcp-server --env-file .env
```

Or, when launching via Claude Code's MCP config, add it to the `env` block
in `.mcp.json`:

```json
{
  "mcpServers": {
    "alpaca": {
      "type": "stdio",
      "command": "uvx",
      "args": ["alpaca-mcp-server", "--env-file", ".env"],
      "env": {
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

## Impact

Every Windows user hits this on first launch unless they happen to have
`PYTHONUTF8` already set. The crash is particularly confusing when the
server is launched through a client like Claude Code, because the error
is buried in MCP startup logs that most clients don't surface clearly —
it looks like a client configuration problem when it's actually a
server-side encoding bug.
