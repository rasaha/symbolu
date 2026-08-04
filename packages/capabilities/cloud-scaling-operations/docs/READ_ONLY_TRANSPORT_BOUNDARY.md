# Read-Only Transport Boundary

`transport.ReadOnlyTransportBarrier` is the single method-checked chokepoint. It decides
**before** any transmission whether a method may proceed and records every attempt in an
append-only request-method ledger (redacted endpoints).

| Verb | Disposition |
|------|-------------|
| `GET`, `HEAD`, `WATCH`, `LIST` | allowed (read-only) |
| `POST`, `PUT`, `PATCH`, `DELETE`, `DELETECOLLECTION`, `CONNECT`, `OPTIONS` | blocked before transmission |
| lowercase / unknown / empty | blocked (fail closed) |

The barrier does **not** rely on remote RBAC — a blocked method raises
`ReadOnlyViolation` and the underlying transport is never invoked. `ReadOnlyHTTPClient`
wraps an injected transport and exposes only `get`/`head`; there is deliberately no
`post`/`put`/`patch`/`delete`.

The ledger's `transmitted_write_methods()` must always be empty. The mutation-canary
suite drives Kubernetes scale patches, ArgoCD syncs, generic HTTP writes, and legacy
actuators through barrier-guarded / tripwired transports and asserts zero transmitted
write methods and zero real network egress.
