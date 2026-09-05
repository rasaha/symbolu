# Ugence data privacy and egress authority — scoping record and ratification

**Status:** ratified 2026-09-05 by the repository owner. Scoping only at the time
of ruling: this record amends no package ADR, port, test or manifest. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 4, line 60:
"contracts first; evaluates data use independently of action authorization").
The rulings below authorize the neutral label contract in governance-contracts
and the contracts-only package `packages/integration/data-use-admission`, and
nothing beyond them.

Evidence labels: `[V]` verified against this repository at commit `e2dfafb9`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Which package answers *may this data be used for this purpose, by this system, in
this place*, independently of whether an action is authorized? **Nothing does, and
the gap is declared, not inferred.** Context Minimization "does **not** decide
whether information was permitted to enter the context (that is *admission*, which
happens upstream)" `[V]` (`packages/capabilities/context-minimization/README.md:13-14`).
Nothing sits upstream of it for that question. Under DE-1 the first slice records
the declaration a caller would make at that seam; it does not itself admit.

## 2 — What the repository already fixed

| Finding | Where |
|---|---|
| The admission seam is declared below and owned by nothing above; no README or NEXT_PHASES under `packages/`, `products/`, `apps/`, `ugence_console_api/` or `Project_documentation/` reserves "egress", "privacy" or "data use" as a governance noun `[V]` `[G]` | `context-minimization/README.md:13-14` |
| ActionGate's MUST-NOT list never mentions data use `[V]` | `packages/providers/actiongate/docs/AUTHORIZATION_BOUNDARY.md:18-25` |
| Decision Authority's must-not list never mentions data use `[V]` | `packages/capabilities/decision-authority/README.md:26-29` |
| Residency is evaluated twice, each time as a property of something else: ActionGate's `allowed_region` is a **constraint on an authorized action** `[V]` | `actiongate/src/ugence_actiongate_provider/mapping/constraints.py:18` |
| Model Selection's `data_residency_allowed` is a fail-closed **eligibility** criterion for choosing a model `[V]` | `model-selection/README.md:88`; `src/ugence_model_selection/gate.py:139-145` |
| `governance-contracts` 0.5.0 has no data-classification, purpose or egress type `[V]` | `governance-contracts/src/ugence_governance_contracts/contracts/` |
| The identity to bind against exists: "Consumers re-export it; they never redefine it" `[V]` | `contracts/system_identity.py:9-11`, `:17-18` |
| The contracts-only shape has a wave 2 precedent `[V]` | `packages/integration/ai-system-registry/README.md:1-24` |

The sequencing ADR's prohibition (line 85) is satisfied. Residency is the only real
adjacency: two packages evaluate one fact for two different questions, and under
DE-2 both keep doing so.

## 3 — The first slice

By analogy to `ai-system-registry`: a `DataUseDeclaration` binding one
`AssessedSystemBinding` re-exported from governance-contracts, a
`DataClassificationLabel` re-exported from governance-contracts (DE-5), a declared
`purpose_label`, a `Validity` window and an optional `supersedes`. Refusal reasons
for a blank label, a missing binding, a mismatched tenant, or a window that never
opens. Pure selectors over a caller-held collection, in-force first. One read-only
Protocol, no implementation.

**Structurally unable:** no store, adapter, connector, redactor, proxy, classifier
or clock, held by a boundary test over module and symbol names. It records what an
administrator declared about data; it decides nothing about actions and admits
nothing into any context.

## 4 — Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| DE-1 | Admission only, or admission plus result egress? | **`ADMISSION_ONLY`.** The package governs the contract boundary before data enters a governed context — the seam at `context-minimization/README.md:14`. Result and output egress is a second, undeclared seam after model output; it remains explicitly deferred and must not appear in this slice. |
| DE-2 | Residency ownership | **`STAY_SPLIT`.** ActionGate retains `allowed_region` as an action constraint; Model Selection retains privacy, jurisdiction and residency compatibility as model eligibility. This package must not reinterpret, replace or import either mechanism. It may record declared data-residency metadata; it cannot evaluate or enforce residency. |
| DE-3 | Labels uninterpreted, as registry D-2, or ordered? | **`UNINTERPRETED`.** A classification label is a non-empty opaque value, following AI System Registry D-2. No enum, taxonomy, lattice, hierarchy, severity, ordering, dominance or implied compatibility. |
| DE-4 | Name and location | **`packages/integration/data-use-admission`**, distribution `ugence-data-use-admission`, namespace `ugence_data_use_admission`. No `…Authority` suffix: the contracts-only slice performs no decision and no admission itself. Not "privacy": the studio (`docs/p3e/LOGGING_AND_PRIVACY.md`) and dilchat mobile use that word for app-local hygiene. |
| DE-5 | Land a neutral data-classification type in governance-contracts first, as D-4 did for `AuditReference` (`contracts/audit.py:1-16`)? | **Yes.** `DataClassificationLabel` lands first in `packages/governance-contracts`: an immutable, non-empty, uninterpreted label with structural validation only. It grants no authority and performs no classification or comparison. |

## 5 — Out of scope, stated once

Three things this record does **not** authorize, and the package must not grow
into without a further ruling:

- **Result egress** (DE-1): nothing after model output.
- **Residency consolidation** (DE-2): no evaluation, enforcement or reinterpretation
  of `allowed_region` or `data_residency_allowed`; a recorded residency value is
  metadata, never a verdict.
- **Classification ordering** (DE-3): no comparison between labels beyond exact
  equality of the declared value.

## 6 — Next step

Implement `packages/integration/data-use-admission` 0.1.0 under the decisions
above, after `DataClassificationLabel` lands in governance-contracts.
