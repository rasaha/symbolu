# Test & Validation Plan — Code Governance

> Documentation only. Verified at commit `3ec11e4e`.

## 1. Baseline (reproduced this audit — see main audit doc §2)

| Suite | Command | Result |
|---|---|---|
| Terminology validator | `python scripts/validate_terminology.py` | PASS |
| Terminology test | `python -m pytest tests/test_terminology_validation.py -q` | (fixed doc-list; governed docs present) |
| Documentation-link checker | `python scripts/check_doc_links.py` | PASS (21 links) |
| Platform freeze verifier | `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` | PASS (6 checks incl. `dependency_direction`) |
| Dependency-direction validators | `pytest packages/.../boundaries/test_dependency_boundaries.py packages/.../test_platform_boundaries.py packages/.../packaging/test_leaf_dependency.py` | 15 passed |
| Governance Contracts | `pytest packages/governance-contracts/tests` | 45 passed |
| Governance Provider Framework | `pytest packages/governance-provider-framework/tests` | 84 passed |
| Decision Authority | `pytest packages/capabilities/decision-authority/tests` | 79 passed |
| StoryGraph | `pytest packages/capabilities/storygraph/tests` | 316 passed |
| TAP provider | `pytest tap_provider/tests` | 38 passed |
| ActionGate provider | `pytest actiongate_provider/tests` | 30 passed |
| ACP (closest approved validation) | `pytest robotics_reliability_bench/acp_control_plane/test_control_plane.py` | 20 passed (requires numpy) |
| Control-plane smoke | `pytest control_plane/tests/test_control_plane.py` | 65 passed |

Environment: Python 3.11.15; deps installed for the run: `pytest`, `pydantic`, `numpy`. No canonical
package test suite exists for ACP (it is shadow-only design + robotics/K8s shadow code); the
control-plane and robotics acp_control_plane suites are the closest approved validations.

### Known pre-existing / environment notes (not fixed — unrelated)
- Freeze verifier and DA import require `pydantic`; robotics ACP suite requires `numpy` — these are
  environment dependencies, installed for the run, not code defects.
- ACP has no canonical package tests (documentation + shadow implementations only).

## 2. Per-phase acceptance tests (future implementation)

- **A:** state-machine transition coverage; reference-propagation; `CHAIN_INCOMPLETE` fail-closed sim.
- **B:** webhook-signature verification (valid/invalid/replay); installation-token scoping; immutable
  evidence-ref generation; shadow (no writes).
- **C:** claim-manifest → TAP `evaluate` mapping; `DecisionRecord` construction incl. SoD/roles;
  policy-pack loading from base branch; recommendation check-run render.
- **D:** merge identity tuple binding; CER bind + ActionGate authorize; envelope fingerprint;
  no-dispatch assertion.
- **E:** ACP pre-merge signal evaluation; expiry; stale-artifact rejection; durable clearance ref
  (shadow).
- **F:** GitHub execution conformance suite (execution family); single exact merge; idempotency;
  duplicate/timeout → safe states; reconciliation; §4.7 chain-proof enforcement.
- **G:** merge-group re-validation + derived authorization + clearance; reconcile.
- **H:** adjudicator advisory-only (no path to `DecisionRecord`); §9.2 integrity controls
  (blind, order-bias, evidence-tier, ambiguity escalation, no synthesis).

## 3. Governance guardrail tests to run on every implementation PR

- Dependency-direction validators + freeze verifier `dependency_direction` check.
- Provider conformance (`_no_kernel_internal_imports`, deterministic fingerprint) for new providers.
- Boundary tests barring GitHub types in neutral contracts and forbidding `cer_v0_*` imports.
- Fail-safe normalization tests (provider exception → `INDETERMINATE`/`UNKNOWN`, never "authorized").

## 4. Validation of THIS audit (§26)

Re-run terminology validator, doc-link checker, dependency-direction validators, platform freeze
verifier, and confirm the diff is **documentation + machine-readable audit evidence only** (no
runtime, package, contract, provider, API snapshot, or freeze change). New audit docs live under
`docs/audits/code_governance_readiness/` and are outside the validators' fixed doc lists, so the
validators remain green. Relative links inside the audit set are self-contained. Results recorded in
the main audit document and the completion report.
