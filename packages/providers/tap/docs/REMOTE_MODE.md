# Remote mode

TAP talks to its engine through a narrow client seam supporting **in-process** and
**remote** modes. The remote client is an abstraction: for deterministic testing it
delegates to a co-located engine while able to simulate transport-level failures
(timeout / unavailable) independently of the engine. A production model-backed
evaluator would sit behind this same seam.

- The default **in-process** path is minimal and **network-free**.
- Remote mode adds **no external HTTP dependency** — there is deliberately no
  `remote` extra, because no optional third-party code exists to gate.
- Remote operation in production requires **independently secured transport and
  authentication**; TAP does not provide these.
- Packaging verification performs **no live network calls**.
