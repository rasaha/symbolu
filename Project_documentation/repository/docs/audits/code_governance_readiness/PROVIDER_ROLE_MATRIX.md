# Provider-Role Matrix — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§0, §1, §11).
> Verified against live code at commit `3ec11e4e`. Machine-readable form: `provider_role_map.json`.

## The corrected GitHub model (v0.2) — confirmed against live contracts

The Governance Provider Framework defines exactly **three peer capability families**
(`ProviderKind`, `metadata.py:19`): `ASSERTION_GOVERNANCE`, `ACTION_GOVERNANCE`,
`EXTERNAL_EXECUTION`. They are "peers — never conflated." Adding a fourth is a **MAJOR**
freeze change (`platform/PLATFORM_FREEZE_V1.json:21`, "new provider families").

**Conclusion: GitHub is not three governance providers.** It decomposes into a product
connector, a product mapping layer, and exactly one execution provider. The rejected
"three-GitHub-provider" model is **not reopened**.

| GitHub piece | Layer | Family / role | Live anchor | Maturity |
|---|---|---|---|---|
| GitHub Evidence Connector | product connector (no authority) | **none** — emits immutable evidence refs | net-new product code; feeds `AssertionGovernanceRequest.evidence_refs` | MISSING |
| Action mapping layer | product (in Workflow Service) | builds `ActionGovernanceRequest` | `contracts/action.py:29`; consumed by ActionGate | MISSING (product) |
| GitHub Execution Provider | provider | **`EXTERNAL_EXECUTION`** | `contracts/execution.py:66`; model on `actiongate_provider/` | MISSING |

## Family → capability mapping (verified)

| Family | Capability (provider) | Protocol | Request / Result | Live package | Verified |
|---|---|---|---|---|---|
| `ASSERTION_GOVERNANCE` | **TAP** | `AssertionGovernanceProvider.evaluate` | `AssertionGovernanceRequest` → `AssertionGovernanceResult` | `tap_provider/` (`provider.py:50`, `kind=ASSERTION_GOVERNANCE`) | ✅ `tap_provider/tests/test_end_to_end.py` (38 pass) |
| `ACTION_GOVERNANCE` | **ActionGate** | `ActionGovernanceProvider.authorize` | `ActionGovernanceRequest` → `ActionGovernanceResult` | `actiongate_provider/` | ✅ 30 tests pass; bridged via GPF `adapters/action_to_control_plane.py:65` → kernel `ActionControlPlanePort` |
| `EXTERNAL_EXECUTION` | **GitHub Execution Provider (new)** | `ExternalExecutionProvider.dispatch/observe` | `ExecutionDispatchRequest` → `ExecutionDispatchResult`/`ExecutionObservation` | proposed `providers/github-execution` | ❌ MISSING — only the framework `reference/execution.py` `DeterministicExecutionProvider` test-double exists |

## Fixed boundaries — verification verdicts

| Design boundary | Verdict | Evidence |
|---|---|---|
| GitHub evidence ingestion is **not** an assertion-governance provider | CONFIRMED | Ingestion produces refs; TAP (`tap_provider`) is the sole `ASSERTION_GOVERNANCE` impl; connector performs no `evaluate()` |
| TAP **is** the assertion-governance provider | CONFIRMED | `provider.py:44-47` declares `ASSERTION_GOVERNANCE` |
| GitHub action construction is **not** an action-governance provider | CONFIRMED | Building an `ActionGovernanceRequest` is product mapping; ActionGate (`actiongate_provider`) authorizes it |
| ActionGate **is** the action-governance provider | CONFIRMED | `actiongate_provider` implements `ActionGovernanceProvider.authorize` |
| GitHub merge execution is an `EXTERNAL_EXECUTION` provider | CONFIRMED (as design target) | `contracts/execution.py`; provider not yet built |
| Governance Provider Framework owns no authority | CONFIRMED | GPF only registers/resolves/adapts; no ALLOW/DENY logic; freeze invariants `PLATFORM_FREEZE_V1.json:171-186` |
| Workflow Service coordinates, owns no authority | CONFIRMED (design) | §4A; product component to be built |
| Competitive Code Adjudication recommends only | CONFIRMED (design) | §4.2; structurally no path to a `DecisionRecord`/CER/`ActionGovernanceResult` |
| StoryGraph is advisory | CONFIRMED | emits `OBSERVE/ESCALATE/UNAVAILABLE` only (`storygraph/signals.py:10,28`) |
| ACP performs live clearance, not the original binding decision | CONFIRMED | ACP shadow verdict `CLEAR/HOLD`; binding decision is `DecisionRecord` |
| Model Selection may pick a model, does not govern the change | CONFIRMED | separate capability `packages/capabilities/model-selection`; `execution_gate/` is its legacy namespace |
| No new `ProviderKind` expected | CONFIRMED | three families sufficient; new family = MAJOR freeze change |

## GitHub Evidence Connector disposition

**Disposition: normal product connector / adapter (option 1), packaged outside the GPF.**
- It is **not** a provider of any family (it makes no governance judgment).
- There is **no existing evidence-provider abstraction** to reuse: the evidence subsystem
  (`evidence_assurance/`, `claim_integrity/`, …) is neutral research code with **no durable
  store** and no ingestion service (see `EVIDENCE_AND_TAP_MAPPING.md`).
- Do **not** create a new provider family to register a connector — that would be a MAJOR
  freeze change and would conflate the connector with an authority.
