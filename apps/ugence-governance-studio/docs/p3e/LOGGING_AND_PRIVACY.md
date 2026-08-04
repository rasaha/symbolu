# Logging and Privacy (P3E)

Structured JSON logs on stdout with an allowlisted field set: timestamp, level, event,
method, normalized route, status, duration, correlation id, deployment version, integrity
result. Never logged: Authorization headers, passwords/hashes, request bodies, full query
strings, scenario evidence/exports, TLS key material, cookies. Correlation ids are
generated when absent and sanitized (bounded length; injection-safe). Response-body access
logging is disabled by default. Errors are logged without tracebacks/paths/secrets.
