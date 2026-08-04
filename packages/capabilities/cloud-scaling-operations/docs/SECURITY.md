# Security

- **No secret logging.** Bearer tokens, credentials, private keys, and secret-bearing
  headers are never recorded; audit `extra` is redacted (`redact()`), and gate outcomes
  / exceptions never contain the token.
- **TLS:** ArgoCD calls verify TLS by default; `allow_insecure_tls` is rejected in
  LIVE mode. Base URLs must be allowlisted; malformed URLs are rejected.
- **Bounded egress:** explicit request timeout and bounded retries; no unbounded loops.
- **No credentials at import:** the Kubernetes client is injected; no kubeconfig or
  current-context loading occurs at import.
- **Fail closed:** every unauthorized or malformed action returns an explicit denial
  and a structured audit event — never a silent clamp.
- **Reference stores are not production-secure/durable:** `InMemoryIdempotencyStore`
  and `InMemoryAuditSink` are process-local references only.
