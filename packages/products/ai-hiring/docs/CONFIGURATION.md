# Configuration

The package is designed to run deterministically and offline. There is very
little to configure, by design.

## Deterministic simulation mode

The core operates in a deterministic simulation mode: given the same inputs it
produces the same outputs, with no reliance on wall-clock randomness, network
calls, or external model inference. This makes runs reproducible and auditable.

## Adapters

**Only offline, in-memory adapters ship** with the package. There are no
production adapters in the distribution:

- No production HRIS/ATS adapters.
- No offer, payroll, or candidate-contact adapters.
- No database driver, no web framework in the core.

The composition root wires exactly these in-memory adapters:

```python
from ugence_ai_hiring import build_in_memory_platform

platform = build_in_memory_platform()
```

## ExecutionMode

Execution is governed by an `ExecutionMode` boundary. The package **may** prepare
governed action requests, bind context, request authorization, and record
authorization outcomes. It **must not** execute downstream enterprise actions.
Authorization is never treated as execution.

Because only in-memory adapters ship, action requests are prepared and their
authorization outcomes are recorded, but no downstream enterprise system is
contacted. See [GOVERNANCE_BOUNDARIES.md](GOVERNANCE_BOUNDARIES.md) and
[DEPLOYMENT.md](DEPLOYMENT.md).

## Optional integrations

The optional `api` extra installs FastAPI and Uvicorn for an HTTP surface. This
is opt-in packaging only and does not change the deterministic, offline behavior
of the core.
