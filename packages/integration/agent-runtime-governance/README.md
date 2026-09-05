# Ugence Agent Runtime Governance

**Compose, then project. Mint nothing.**

Agent Runtime ships three governance hooks: `UnconfiguredGovernanceHook` (BLOCK — the
default), `AllowAllGovernanceHook` (an explicitly unsafe test helper), and a deprecated
alias. This package adds the fourth: the one a deployment actually uses.

It obtains a `GovernedExecutionDecision` from the ratified
`RiskAuthorityCompositionEngine` and projects it onto the runtime's
`GovernanceEvaluation`, bound to the exact proposal. It contains **no composition logic**,
**no authority**, and **no credentials**.

Scoped by [`ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md`](../../../docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md);
sequenced as GAS-3 in the Ugence productization roadmap §11.

---

## Maturity

**Core implemented.** Not pilot-validated. Not production-certified.

```python
>>> from ugence_agent_runtime_governance import maturity
>>> maturity()["stage"]
'Core implemented'
```

What stays blocked, regardless of this package:

- Risk Authority `production_mode` still raises `ProductionContainmentError`.
- **HOLD, DEFER, ESCALATE and MANUAL_REVIEW still have no sink.** This package emits HOLD
  and ESCALATE correctly and the runtime parks on them correctly — and then there is
  nowhere for a human to see the parked instance. The hook makes the disposition
  faithful; it does not make it actionable.
- No credential broker: cloud-scaling Phase 5X is unbuilt, and nothing here substitutes
  for it.

## The projection

One table, and it is the whole safety argument:

| `FinalDisposition` | `GovernanceDisposition` | Runtime directive |
|---|---|---|
| `GRANT` | `CLEAR` | CONTINUE |
| `DENY` | `BLOCK` | STOP |
| `HOLD_NON_EXECUTABLE` | `HOLD`, or `ESCALATE` when an approval is required | WAIT / PAUSE |
| `ERROR_NON_EXECUTABLE` | `BLOCK` | STOP |
| anything else | `BLOCK` | STOP |

Three refusals close the ways this could be widened, each with a test:

1. **A str-enum look-alike is refused.** `FinalDisposition` subclasses `str`, so the bare
   string `"GRANT"` compares equal to `FinalDisposition.GRANT` *and hashes identically* —
   a dict lookup or an `==` check would accept it from a malformed or spoofed object.
   `isinstance` is checked first.
2. **A self-reported `executable` is never the basis.** CLEAR requires the disposition to
   be GRANT *and* `executable` to be true, so an object claiming `executable = True`
   beside a DENY is refused.
3. **Wreckage is not permission.** `getattr(obj, name, default)` only swallows
   `AttributeError`; an object whose `__getattr__` raises something else would propagate
   into the runtime's hot path, where a raising hook is indistinguishable from one that
   was never asked. Every read of a decision is guarded, and the hook never raises.

HOLD and ESCALATE are equally non-executable; the choice between them selects which
stable boundary the runtime parks at, and ESCALATE is used where the composition recorded
a required approval — that is what "pending external authority or review" means.

## What a CLEAR carries

The runtime acts on a CLEAR only if it is bound to the exact proposal fingerprint, carries
a non-empty governance-produced reference, and matches the proposal's correlation id. This
hook supplies all three, and takes the reference from Risk Authority's own `envelope_id`.

**A GRANT with no envelope id is refused**, not given a minted identifier: there would be
nothing to bind the clearance to, and inventing one would make an unbindable permission
look bindable.

`valid_until` is projected onto epoch seconds — the same base as the durable deployment's
injected wall clock (ADR §6.4). A naive datetime is read as UTC rather than local time,
because guessing the host zone could move an expiry hours in the permissive direction.

## The last-mile recheck

This package **does not implement a recheck.** Risk Authority's status runtime already
ships `make_pre_effect_recheck`, and it already returns exactly the
`(evaluation, proposal, now) -> (ok, reasons)` shape Agent Runtime's `authority_recheck`
seam expects. Rebuilding it would duplicate authority-critical logic outside the package
that owns it.

What was missing is the *resolver* — mapping a neutral proposal back to the envelope its
CLEAR rested on. Only the hook knows that, so the hook records
`fingerprint -> (envelope, tier)` when it clears, and `build_authority_recheck` wires that
into Risk Authority's own recheck.

```python
recheck = build_authority_recheck(
    hook=hook, reader=cache, policy=StalenessPolicy.fail_closed_defaults(),
    key_ring=key_ring, clock=lambda: datetime.now(timezone.utc),
    sync=cache.sync,          # observe revocations that land after the CLEAR
)
config = AgentRuntimeConfig(governance_hook=hook, authority_recheck=recheck, clock=wall_clock)
```

Pass `sync`. Without it the recheck can re-verify against a snapshot as stale as the
clearance it is checking, which makes the mechanism decorative. ADR §8 row 6 proved that
an unset recheck does not notice revocation at all; `tests/test_recheck_wiring.py` proves
this wiring catches a real revocation and a real epoch advance, against genuine
Ed25519-signed envelopes.

## Boundaries

```
    ugence-agent-runtime  (leaf — UNTOUCHED)   risk_authority  (leaf)
        ▲                                          ▲
    ugence-risk-authority-runtime (RA-4.5 composition — used, never re-implemented)
    ugence-risk-authority-status-runtime (RA-6 — supplies the recheck)
        ▲
    ugence-agent-runtime-governance  (this package)
```

Asserted by `tests/test_boundaries.py`: Agent Runtime gains no import from here and stays
concrete-free; no composition symbol is restated in this package's code; nothing
constructs an envelope, a machine result or a decision; no credential or live-execution
token appears.

## Tests

```bash
pytest packages/integration/agent-runtime-governance/tests -q
```

The adversarial suite is exhaustive over the veto vocabulary rather than sampled — every
combination of Decision Authority and ActionGate dispositions except the all-clear one
must come back restrictive. A single combination slipping through to CLEAR is the failure
mode this package exists to prevent.
