# Operational Readiness Checklist

Operational procedures for running AI Hiring `0.6.0` during a controlled pilot. These
describe **existing behavior only** — the product runs deterministic simulation with
no production external effect. Complements
[`../product/OPERATIONS_RUNBOOK.md`](../product/OPERATIONS_RUNBOOK.md).

## Deployment checklist

- `[ ]` Target environment is isolated from any production hiring/HR system.
- `[ ]` Python `>=3.10` available; `numpy` and `pydantic>=2` installable.
- `[ ]` Artifact installed from the recorded wheel (hash matches
  [`RELEASE_MANIFEST.md`](RELEASE_MANIFEST.md)): `45b2d935…`.
- `[ ]` Durable repository/audit storage adapters wired (if the pilot requires
  persistence); no frozen-platform code modified to do so.
- `[ ]` `execution_mode == DETERMINISTIC_SIMULATION` (any production mode fails closed).

## Startup checklist

- `[ ]` `python -m ai_hiring.product verify` → `RESULT: PASS`.
- `[ ]` `python -m ai_hiring.product version` shows `0.6.0`, `production certified: False`.
- `[ ]` A smoke case runs end to end and reconstructs
  (`build_accountability_report(...).integrity["reconstructed"] is True`).
- `[ ]` Audit storage is writable and readable; a written event is reconstructable.

## Shutdown checklist

- `[ ]` No case is mid-lifecycle without a recorded terminal or fail-safe state.
- `[ ]` Audit/evidence persisted per retention policy.
- `[ ]` Accountability reports for the session exported (redacted) for the evidence
  bundle.
- `[ ]` Process stopped; no background external effect exists to drain (there are none).

## Rollback checklist

- `[ ]` Identify the target prior version.
- `[ ]` Reinstall the prior recorded artifact (hash-verified).
- `[ ]` Re-run the startup checklist.
- `[ ]` Because there is no in-process persistent state coupling, rollback is
  reinstall-and-restart; durable audit storage is retained and remains reconstructable.

## Incident response

1. Contain: stop the affected process; do not attempt a production action (none is
   possible).
2. Classify: correctness / security / packaging / pilot-blocking / other.
3. Preserve evidence: export the affected case's accountability report (JSON + text)
   and the audit chain.
4. Escalate per [`CONTROLLED_PILOT_PLAN.md`](CONTROLLED_PILOT_PLAN.md) escalation
   criteria.
5. Only freeze-exception changes may be applied during the pilot (see
   [`FREEZE_DECLARATION.md`](FREEZE_DECLARATION.md)).

## Provider outage (assertion/action governance provider)

- Symptom: TAP or ActionGate provider unavailable/timing out.
- Expected behavior: the lifecycle **fails safe** — a recommendation cannot pass
  review without assertion evaluation; an action cannot execute without authorization.
  No unsafe progression occurs.
- Action: confirm the fail-safe stop in the case's status; restore the provider;
  re-drive affected cases. Do not bypass the provider.

### ActionGate outage
- Authorization cannot be obtained → no execution. Proposals wait or are marked
  not-authorized. Confirmed correct; restore and re-authorize.

### TAP outage
- Assertion evaluation cannot complete → recommendation does not reach human review
  (or is held). Confirmed correct; restore and re-evaluate.

## Reconstruction failure

- Symptom: `integrity.reconstructed == False` or `hiring_hash_chain_valid == False`
  with `issues`.
- Action: treat the record as **untrusted**; do not rely on its outcome. Capture the
  issues list. If not a deliberate drill, escalate as an integrity incident.

## Audit verification (routine drill)

- Periodically reconstruct a sample of cases and confirm: hash chain valid, links
  intact, tenant scope consistent.
- Injected-tamper drill: alter a stored audit event in a **test** copy and confirm
  reconstruction reports the break (as validated in `test_h5_scenarios.py`).

## Configuration validation

- All config is built through `load_config` / `ProductConfig` (fail-closed).
- Confirm: unknown keys rejected, invalid values rejected, production modes rejected.
- `redact_pii` is `True` for any report leaving the pilot environment.

## Readiness sign-off

- `[ ]` All checklists above are exercised and pass in the pilot environment.
- Technical owner: __________________  Date: __________
