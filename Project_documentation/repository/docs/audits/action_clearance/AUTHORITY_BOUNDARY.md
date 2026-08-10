# ACP Authority Boundary

## The boundary this audit holds

```text
Decision Authority   : who may make the binding decision, and was it validly recorded?
ActionGate           : is THIS exact proposed action authorized under the decision + policy?
ACP (clearance)      : is the already-authorized action still clear to execute NOW?
Execution provider   : performs the already-authorized, cleared operation.
```

Intended sequence:
`DecisionRecord → ContextEnvelopeRecord → ActionGovernanceRequest → ActionGovernanceResult → ACP clearance
→ execution dispatch → observation & reconciliation`.

ACP must **not** silently become the decision maker, an action-authorization engine, an execution provider,
a workflow orchestrator, a provider router, a repo-specific policy engine, an incident-management system, or
a retry controller.

## Live-code verdict: PARTIALLY PRESERVED, PARTIALLY CONTRADICTED

### Preserved — the cloud/console framing

- **Never authorizes, never executes.** `ugence_console_api/…/operational_safety.py:11-12`: *"It never
  authorizes — ActionGate already decided whether the action may run; ACP decides whether now."*
  `symbolu_robotics/…/cloud/adapter.py:14-16,25`: *"Never actuates… ACP never mints a real execution
  credential — that is ActionGate's job."* `Project_documentation/control_plane/acp/RESPONSIBILITY_MATRIX.md:12-13` splits *authorization*
  (ActionGate, sole) from *operational safety* (ACP, sole; "never authorizes").
- **Narrow-only, never broaden.** Two hard invariants in `cloud/composition.py`: an ActionGate `DENY` ⇒
  `BLOCKED_BY_AUTHORIZATION` (ACP cannot override, `:98-102`); a permissive ACP result on a denied/pending
  action mints nothing — proceed requires **both** layers (`:111-120`), asserted by
  `tests/test_acp_cloud.py:172-196`. The robotics `ControlAuthorization` is likewise narrowing-only: a grant
  is produced *only* for EXECUTE/EXECUTE_WITH_CONSTRAINTS; revalidation can only reject, never widen
  (`authorization.py:105-125`).

### Contradicted — the robotics V1 framing

- `Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md:20`: ACP is the *"deterministic **decision-and-authorization** runtime."*
  `:28-31`: *"it does not do the work, it decides **and authorizes** what work is allowed to happen."*
  Stage 9 *"mint[s] a one-shot execution grant"* (`:110`). The code does mint `ControlAuthorization`
  (`authorization.py:34`) with a `grant_id`.
- This makes robotics ACP, in its own framing, an **action-authorization engine** — one of the roles the
  boundary says ACP must not silently become. (It is still narrowing-only and never executes, so it is not a
  decision maker or executor; but "authorizes" vs "clears" is exactly the distinction the boundary draws
  between ActionGate and ACP.)

## Roles ACP does NOT assume (verified)

| Forbidden role | Assumed? | Evidence |
|---|---|---|
| Original decision maker | No | Consumes candidates; does not originate the mission/decision |
| Execution provider | No | Never actuates; no k8s/actuator client (`cloud/adapter.py:14-16`) |
| Workflow orchestrator | No | Pure per-request evaluation; the console orchestrator is a separate consumer |
| Provider router | No | No provider selection (that is Model Selection) |
| Repo-specific policy engine | No (core) | Core is neutral; target-specific checks live in adapters |
| Incident-management system | No | No incident client; `acp_db` has a `NO_MIGRATION_CONFLICT` flag only |
| Retry controller | No | No retry engine; `SIMULATE_AND_RETRY` is an opaque ActionGate token |
| **Action-authorization engine** | **Yes, in robotics V1** | mints `ControlAuthorization` grant (`authorization.py`) |

## Implication

The single unresolved authority question — *does ACP authorize (robotics V1) or only clear (cloud/console)?*
— must be settled **before** any packaging. Packaging the robotics core as `ugence_action_clearance` while
it mints authorization grants would ship an authorization engine under a clearance name, blurring the
ActionGate/ACP boundary the platform depends on. This is the leading reason for the **NOT READY** verdict
and the first **MIGRATION_BLOCKER** in `RISK_REGISTER.md`.
