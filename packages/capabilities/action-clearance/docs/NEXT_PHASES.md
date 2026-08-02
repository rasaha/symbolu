# Next Phases (out of scope for the v0.1 core)

Per the merged implementation sequence (design §31, phases A–I), the core
(phases A–B) is implemented here. The following are **not** implemented and must
not be started under this phase:

| Phase | Item | Owner |
|---|---|---|
| C | in-memory reference **adapters** (signal producers) | product/integration |
| D | ActionGate integration (shadow) | product |
| E | durable `ClearanceReceipt` persistence + lifecycle | Workflow Service |
| F | GitHub exact-merge **profile** (shadow) | profile/adapter |
| G | execution-ledger integration: atomic one-time **reservation**, replay protection | execution ledger |
| H | Code Governance **enforced** direct+squash merge | product |
| I | merge queue + rebase | profile |

Invariants every later phase must preserve: no new `ProviderKind`; no neutral
governance-contract change; the evaluator never creates authority, broadens
authorization, persists, reserves, or dispatches; `CLEAR` is never execution; the
bare acronym "ACP" never appears in package/type/reason names; no alias or object
identity with `symbolu_robotics.autonomous_control_plane`.
