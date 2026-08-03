# Observability

`ActionGateInvocationLog` collects structured `ActionGateInvocationRecord`s, richer
than the framework's generic record:

`provider_id`, `provider_version`, `mapping_version`, `mode`, `compatible`,
`completed`, `outcome`, `trace_id`, `policy_version`, `error_class`,
`failure_class`, `fallback_provider_id`.

```python
from ugence_actiongate_provider.observability import ActionGateInvocationLog
log = ActionGateInvocationLog()
p = build_actiongate_provider(invocation_log=log); p.initialize()
p.authorize(ActionGovernanceRequest("OK"))
rec = log.all()[0]
print(rec.completed, rec.outcome, rec.mapping_version, rec.policy_version)
```

A completed authorization records its outcome, mapping version, policy version, and
trace; a failed one records `error_class` and `failure_class` (e.g. `RETRYABLE`).
**No secrets and no full vendor payloads are recorded** — records are distinct from
DGM kernel audit events.
