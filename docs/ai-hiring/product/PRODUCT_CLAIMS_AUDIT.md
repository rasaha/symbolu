# Product-Claims Audit

Every material claim the product documentation makes, mapped to the evidence that
substantiates it. A claim without evidence is a liability; this audit exists so that
no marketing or product statement outruns what the code actually does. Where a claim
could be misread as more than it is, the **precise** wording is stated.

Legend — evidence types: **T** test, **C** runnable command, **V** verification tool,
**D** design/enforcement in code.

## Capability claims

| # | Claim | Precise scope | Evidence |
|---|---|---|---|
| 1 | Runs the full governed lifecycle end to end | evidence→recommendation→TAP→human decision→ActionGate→execution→reconciliation | **T** `test_h6_product.py::test_run_case_reconstructs_end_to_end`; **C** `python -m ai_hiring.product demo` |
| 2 | Material claims are TAP-evaluated **before** human review | recommendation reaches review only after assertion evaluation | **T** `test_h5_scenarios.py::test_unsupported_material_claim_blocks_readiness` |
| 3 | Decisions are human-only | AI actor cannot record a binding decision | **T** `test_h5_scenarios.py::test_ai_cannot_make_binding_decision`; **D** grant denies `MAKE_DECISION` |
| 4 | No execution without authorization | ActionGate denial blocks execution | **T** `test_h5_scenarios.py::test_actiongate_denied_blocks_execution` |
| 5 | No action without a decision | proposal requires eligible recommendation + decision | **T** `test_h5_scenarios.py::test_execution_without_decision_is_impossible` |
| 6 | Mismatches surface as compensation-required, never silent success | reconciliation mismatch → `COMPENSATION_REQUIRED` | **T** `test_h5_scenarios.py::test_mismatch_requires_compensation` |
| 7 | End-to-end record is reconstructable with integrity checks | hash chain + link + tenant-scope verification | **T** `test_h6_product.py::test_demo_produces_sample_report`; `test_h5_scenarios.py::test_tampered_audit_chain_detected` |
| 8 | Accountability report is human- and machine-readable | `.render_text()` and `.to_dict()` | **T** `test_h6_product.py::test_accountability_report_is_json_serializable` |
| 9 | PII redaction is on by default and deterministic | subject/actor pseudonymized; stable | **T** `test_h6_product.py::test_accountability_redaction_masks_actor_and_subject` |
| 10 | Demo is reproducible | same inputs → same outputs | **T** `test_h6_product.py::test_demo_is_reproducible` |

## Safety / boundary claims

| # | Claim | Precise scope | Evidence |
|---|---|---|---|
| 11 | No production external effect | deterministic in-memory adapters only | **T** `test_h6_boundary.py::test_product_uses_no_production_transport`; **C** `python -m ai_hiring.product verify` |
| 12 | Production execution modes fail closed | config rejects them before wiring | **T** `test_h6_product.py::test_production_modes_fail_closed` |
| 13 | Config is fail-closed on unknown/invalid input | typed validation at construction | **T** `test_h6_product.py::test_unknown_key_rejected`, `test_invalid_values_rejected` |
| 14 | No vendor/integration SDKs imported | enforced by AST scan | **T** `test_h6_boundary.py::test_product_imports_no_vendor_sdks` |
| 15 | Packaging layer adds no new governance/lifecycle/authority | states/authorities unchanged; kernel untouched | **T** `test_h6_boundary.py::test_product_adds_no_new_lifecycle_states_or_authorities`, `test_product_does_not_import_kernel_internals`; **V** `python -m platform_freeze.verify` |
| 16 | Frozen platform unmodified | no frozen file changed | **V** `platform_freeze.verify` PASS; dependency report 0 violations |
| 17 | Cross-tenant reconstruction denied | tenant isolation enforced | **T** `test_h5_scenarios.py::test_cross_tenant_reconstruction_denied` |
| 18 | Analysis-only attributes never enter the pipeline | governed fingerprint invariant to group label | **T** H5 `counterfactual_invariance` (fairness module) |

## Packaging / install claims

| # | Claim | Precise scope | Evidence |
|---|---|---|---|
| 19 | Installs and runs in a clean environment | editable + wheel, from non-repo cwd | **C** clean-venv `pip install` + `python -m ai_hiring.product verify` → PASS (see [`PACKAGING.md`](PACKAGING.md)) |
| 20 | Two runtime deps only (`numpy`, `pydantic`) | product code imports only stdlib + first-party | **C** `pip freeze`; import scan in [`DEPENDENCY_REVIEW.md`](DEPENDENCY_REVIEW.md) |
| 21 | Pre-1.0, not production-certified | `production_certified == False` always | **T** `test_h6_product.py::test_version_is_pre_1_0_and_not_production_certified` |

## Claims we explicitly do **NOT** make

These are stated so no reader infers them:

- ❌ **Not** production-ready; **no** production integrations, offers, or rejections
  are issued (`ISSUE_OFFER`/`SEND_REJECTION` unimplemented).
- ❌ **No** scale, throughput, or latency-at-scale claim — performance is local and
  descriptive only.
- ❌ **No** fairness, bias-freeness, or regulatory-compliance certification — fairness
  analysis is read-only and descriptive, and never labels the system
  "fair"/"unfair"/"compliant".
- ❌ **No** claim of a whole-repository green build — the surrounding `symbolu` repo
  has pre-existing, unrelated failures (see [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md)).
- ❌ The deterministic providers are **not** production references — they are
  **deterministic provider implementations used only for validation**.

## Result

Every capability, safety, and packaging claim above is backed by a test, a runnable
command, or a verification tool. No claim in the product documentation was found to
exceed the implemented and verified behavior.
