# Ugence data privacy and egress authority — scoping record

**Status: SCOPED, NOT RULED — nothing here is implemented.** This record authorizes
no code change, creates no package, adds no dependency and amends no package ADR,
port, test or manifest. Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`
(wave 4, line 60: "contracts first; evaluates data use independently of action
authorization").

Evidence labels: `[V]` verified against this repository at commit `e2dfafb9`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Which package answers *may this data be used for this purpose, by this system, in
this place*, independently of whether an action is authorized? **Nothing does, and
the gap is declared, not inferred.** Context Minimization "does **not** decide
whether information was permitted to enter the context (that is *admission*, which
happens upstream)" `[V]` (`packages/capabilities/context-minimization/README.md:13-14`).
Nothing sits upstream of it for that question.

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
adjacency: two packages evaluate one fact for two different questions.

## 3 — The proposed first slice `[I]`

By analogy to `ai-system-registry`: a `DataUseDeclaration` binding one
`AssessedSystemBinding` re-exported from governance-contracts, a declared
`classification_label`, a declared `purpose_label`, a `Validity` window and an
optional `supersedes`. Refusal reasons for a blank label, a missing binding, or a
window that never opens. Pure selectors over a caller-held collection, in-force
first. One read-only Protocol, no implementation.

**Structurally unable:** no store, adapter, connector, redactor, proxy, classifier
or clock, held by a boundary test over module and symbol names. It records what an
administrator declared about data; it decides nothing about actions and admits
nothing into any context.

## 4 — Decisions to rule `[R]`

| # | Decision | What turns on it |
|---|---|---|
| **DE-1** | Admission only, or admission plus result egress? | Admission-only fills the seam at `context-minimization/README.md:14`. Result egress adds a second, undeclared seam after model output, owned today by nobody. |
| **DE-2** | Residency ownership. | Stay split and this package only *records* residency; or move here and both packages consume a declaration they no longer evaluate, reopening a frozen ActionGate mapping and a CRITICAL_GOV gate. |
| **DE-3** | Labels uninterpreted, as registry D-2, or ordered? | Ordering makes the package a classifier and needs a ratified data taxonomy first. |
| **DE-4** | Name and location under `packages/integration/`. | Not `…Authority` unless it decides. Not "privacy": the studio (`docs/p3e/LOGGING_AND_PRIVACY.md`) and dilchat mobile already use it for app-local hygiene. |
| **DE-5** | Land a neutral data-classification type in governance-contracts first, as D-4 did for `AuditReference` (`contracts/audit.py:1-16`)? | Yes puts the vocabulary where every engine can point at it; no keeps it engine-local until a second consumer appears. |

## 5 — Next step

Rule DE-1 to DE-5. Nothing is implemented by this record.
