# Configuration

## OperationsConfig
- `mode`: `DRY_RUN` (default) / `SIMULATION` / `SHADOW` / `LIVE`.
- `target_policy`: `TargetPolicy` (allowlists + bounds).
- `require_audit_sink` (default true), `require_readiness` (default true).
- `cooldown_seconds`, `rate_limit_per_minute`, `max_concurrent_executions`.
- `argocd_allowed_base_urls`, `allow_insecure_tls` (rejected in LIVE),
  `request_timeout_seconds`, `max_retries`.

## TargetPolicy
- `allowed_clusters` / `allowed_namespaces` / `allowed_resources` (empty = nothing
  allowed; wildcards/empty rejected unless `allow_wildcard`).
- `min_replicas` / `max_replicas` / `max_replica_delta`.
- `max_observation_age_seconds` (staleness window).

## Execution modes
| Mode | Mutates | Authorization | Credentials |
|------|---------|---------------|-------------|
| DRY_RUN | no (proposes) | no | no |
| SIMULATION | no (fakes) | yes | no |
| SHADOW | no (read-only) | no | read-only |
| LIVE | yes | yes | yes |
