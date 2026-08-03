# Fail-Closed Behavior

> Uncertainty or infrastructure failure is **never** promoted to AUTHORIZED.

## Outcome mapping (frozen)

| Native ActionGate outcome | Neutral outcome |
|---|---|
| `ALLOW` | `AUTHORIZED` |
| `ALLOW_WITH_CONSTRAINTS` | `AUTHORIZED_WITH_CONSTRAINTS` |
| `DENY` | `DENIED` |
| `UNKNOWN` | `INDETERMINATE` |
| *any unmapped outcome* | `INDETERMINATE` |

## Two failure layers

1. **Provider boundary.** A native ActionGate failure (timeout / unavailable /
   malformed / config) is translated to a classified framework `ProviderError` and
   raised — **no native exception crosses the boundary**, and a provider exception is
   never locally converted into AUTHORIZED.
2. **Framework control-plane boundary.** The `ActionGovernanceControlPlaneAdapter`
   normalizes a classified `ProviderError` to a fail-safe `INDETERMINATE`
   authorization. A normalized failure never authorizes, dispatches, executes, or
   reconciles; the failure classification remains traceable in the reason codes.

## Release gates

Unknown / unmapped / malformed / timeout / unavailable / protocol failure never
authorize; missing authority never defaults to authorization; DENIED stays distinct
from INDETERMINATE; AUTHORIZED_WITH_CONSTRAINTS stays distinct from unrestricted
AUTHORIZED; constraints/obligations are never silently dropped while keeping an
authorized outcome. Enforced by `tests/authority/test_outcome_safety.py` and
`tests/test_control_plane_lifecycle.py` (DENIED/INDETERMINATE never dispatch).
