# Prior Artifacts & Scope (M1)

*Governed Inference Customer Shadow Pilot Readiness and Operational Hardening
(`customer_shadow_readiness`). A product-readiness and operational-hardening track — **not** a
component-discovery study and **not** a rebuild of the completed pilot. It begins where the completed
`governed_inference_pilot` (frozen at `ab237af`) stopped, and asks whether the runtime can safely enter
a **bounded external customer shadow pilot**.*

## Frozen baseline (must remain byte-identical)

`customer_shadow_readiness/verify_prior_artifacts.py` hash-pins **21** outcome-bearing artifacts: the
17 from the five completed research tracks **plus the 4 governed_inference_pilot frozen artifacts** at
`ab237af`. The guard fails on drift. In addition, all component source logic and the pilot's
orchestrator/adapters/corpus/audit/replay/MVC are treated as frozen and consumed **read-only**.

## What this track must NOT recreate

Governed request schemas, the end-to-end orchestrator, the deterministic GIP corpus, the existing
component adapters, the baseline evaluation, the audit/replay implementation, and the MVC analysis.
These exist in `governed_inference_pilot` and are consumed read-only.

## The principal limitation this track resolves first

The completed pilot's own honest note: **the integrated pipeline used a labelled ActionGate *shadow
mapping*** (a conservative authority/reversibility/risk heuristic) **rather than a validated read-only
invocation of the actual frozen ActionGate decision engine.** The real ActionGate
(`cyber_security/action_gate_reference/action_gate_ref/gate.py`) is a cryptographic decision engine
with a state machine, evidence/approval/attestation model, and a six-value outcome vocabulary. Before
any operational-readiness assessment, the real gate must be integrated read-only and compared against
the shadow mapping — the first mandatory task.

## Scope after real ActionGate integration

Operational-readiness dimensions, each addressed as an isolated addition: authentication/authorization
boundary; tenant isolation; data classification & permitted-use; redaction & minimization; secrets &
encryption interfaces; retention/deletion/export; secure artifact intake; non-enforcing pilot API;
observability; incident response; pilot-wide & tenant-level kill switches; secure deployment packaging;
rollback & recovery; tenant-scoped human-review workflow; pilot-readiness corpus; wall-clock latency;
bounded cost & storage; load & concurrency; security & isolation tests; operational fault injection;
pilot eligibility gate; bounded customer shadow-pilot plan.

## Non-negotiable constraints (enforced in code)

No enforcement. No external action execution. No real customer onboarding. No unrestricted provider
calls. No production-readiness claim. All new code under `customer_shadow_readiness/` and
`docs/customer_shadow_readiness/`; prior tracks and the pilot consumed read-only; frozen artifacts
byte-identical.

## Final decision (one of ten, chosen at the end)

READY FOR BOUNDED CUSTOMER SHADOW PILOT · READY FOR SINGLE-TENANT INTERNAL PILOT ONLY · FIX ACTIONGATE
INTEGRATION FIRST · FIX SECURITY OR TENANT ISOLATION FIRST · FIX DATA-HANDLING CONTROLS FIRST · FIX
OBSERVABILITY OR INCIDENT CONTROLS FIRST · FIX HUMAN-REVIEW WORKFLOW FIRST · FIX DEPLOYMENT OR ROLLBACK
FIRST · NOT ENOUGH EVIDENCE · DO NOT PROCEED.
