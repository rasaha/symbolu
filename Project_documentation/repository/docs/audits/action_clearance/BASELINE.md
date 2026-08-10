# ACP Audit — Baseline (reproduced directly)

Captured directly from the live repository at the verified default HEAD `3ec11e4e`, from a clean worktree.
This is an audit-only phase: no source moved, no package created, no behavior/contract/API-snapshot/freeze
changed.

## 1. Repository state (verified)

| Item | Value |
|---|---|
| Default branch (remote `HEAD branch`) | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD | `3ec11e4ecbc209eabc69d3c0d8a75ecaa10f6def` — *Merge PR #1273* (Code Governance design spec) |
| Audit branch | `claude/acp-product-core-separation-audit-qrwlxv` (harness-mandated), based on `3ec11e4e` |
| Working tree | clean |
| Python | 3.11.15 (Linux) |
| Dependency gaps at start | `pytest`, `pydantic`, `numpy` — pip-installed to run the baseline; **no repo file changed** |
| Model Selection migration integrated | **Yes** (PR #1271, `952d8fe2`, ancestor of default) |
| Code Governance design/competitive docs integrated | **Yes** (PR #1273 = default HEAD) |
| ACP-related open PRs | **none** |
| ACP-related recent branches | **none** |

## 2. Validators (all PASS)

| Check | Command | Result |
|---|---|---|
| Platform freeze verifier | `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` | **PASS** — substantive digest `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6` |
| Terminology validator | `python scripts/validate_terminology.py` | **PASS** (8 governed docs) |
| Documentation-link checker | `python scripts/check_doc_links.py` | **PASS** (21 links, 9 docs) |
| Dependency-direction | `platform_freeze.dependencies.dependency_report()` | **passed=True, 0 violations** |

## 3. Test suites (integrated baseline)

| Suite | Command | Result |
|---|---|---|
| Governance Contracts | `pytest packages/governance-contracts/tests` | **45 passed** |
| Governance Provider Framework | `pytest packages/governance-provider-framework/tests` | **84 passed** |
| Decision Authority | `pytest packages/capabilities/decision-authority/tests` | **79 passed** |
| ActionGate provider | `pytest actiongate_provider` | **30 passed** |
| **ACP** (Autonomous Control Plane) | `pytest symbolu_robotics/autonomous_control_plane/tests` | **112 passed** |
| control_plane | `pytest control_plane/tests` | **65 passed** |
| ACP shadow/pilot benches | `pytest robotics_reliability_bench` | **47 passed** |
| Console (clearance consumer) | `pytest ugence_console_api/tests` | **4 passed** |
| execution_gate / execution_gate_shadow | `pytest execution_gate execution_gate_shadow` | **25 / 23 passed** |
| Freeze self-tests | `pytest platform_freeze/tests` | 19 passed, **2 pre-existing failures** |
| bounded_shadow_pilot | `pytest bounded_shadow_pilot` | 44 passed, **1 pre-existing failure** |

There is **no CI job** that runs the ACP tests or `control_plane` tests; they are run manually here.

## 4. Pre-existing failures (recorded separately; NOT caused by this audit; NOT ACP-attributable)

1. `platform_freeze/tests/test_freeze.py::test_classify_change_reports_evidence` — freeze *tooling* returns
   `UNCLASSIFIED` for an empty diff; test expects a class. Same failure documented in the Model-Selection
   audit baseline.
2. `platform_freeze/tests/test_freeze.py::test_hiring_baseline_discovery` — asserts
   `uses_provider_framework is False`; hiring was wired to the provider framework earlier. Same as above.
3. `bounded_shadow_pilot/tests/test_foundations.py::test_ground_truth_two_class_and_deterministic` — a
   shadow-pilot ground-truth determinism assertion in the cyber-ActionGate pilot; unrelated to ACP.

The freeze **verifier** (`platform_freeze.verify`) itself PASSES. These must remain the same failures after
the audit, since this phase changes no code.

## 5. ACP freeze digest — verified byte-accurate against live code

The ACP V1 local freeze (`acp/ACP_V1_FREEZE.md`) asserts per-module `SHA-256[:16]` digests. Recomputed
directly from the live modules in `symbolu_robotics/autonomous_control_plane/`, **all 13 match**:

```
errors.py            15fb05aaf80a693d   identity.py        e156ce50993f191e
world_state.py       ec9fb4df86118e25   constraints.py     a6d07621689e84a5
envelopes.py         6f1e5af0a3c2e75a   authorization.py   f3975bb0aeeeba8b
action_selection.py  e3b6c4edcdd80199   decision_trace.py  fe43773d0ef9a734
failure_state.py     d60013db0ce150bd   interfaces.py      d4e8a588ad1a640c
predictor_evidence.py 49b32162624155eb  physical_evidence.py 6d4c0b57d8d57ec3
__init__.py          56938a4a4de42611
```

Combined digest of the 10 reusable-core modules: `8f8660e293308cf94c983a26a2ae69c9` (per
`acp/ACP_V1_FREEZE.md:34`). The freeze is real and current; see `FREEZE_IMPLICATIONS.md`.

## 6. Conclusion

The integrated baseline reproduces green with exactly the three documented pre-existing failures and no new
failures. **The audit may proceed.**
