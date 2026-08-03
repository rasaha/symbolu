# Remote Mode

The provider talks to ActionGate through a narrow client seam
(`ActionGateClient`) supporting two modes:

- **`in_process`** (default) — runs the `ActionGateEngine` in the current process.
  Fully offline; no third-party dependency.
- **`remote`** — a remote-service **client abstraction**. It carries no concrete
  network implementation and adds **no third-party HTTP dependency**; for
  deterministic testing it delegates to a co-located engine while able to simulate
  transport-level failures (timeout / unavailable) independently of the engine.

```python
from ugence_actiongate_provider.configuration import ActionGateSettings, build_actiongate_provider
p = build_actiongate_provider(settings=ActionGateSettings(mode="remote"))
p.initialize()
```

Because remote mode is an abstraction, **no live remote service is required** for
packaging verification, and there is no `remote` extra with third-party
requirements. A real deployment supplying a concrete transport must independently
secure that transport and its authentication — see `SECURITY.md`.
