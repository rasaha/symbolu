# Ugence third-party AI and vendor risk — scoping record and ratification

**Status:** ratified 2026-09-05 by the repository owner. Scoping only at the time
of ruling: this record amends no package ADR, port, test or manifest. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 4, line 62:
"contracts first, linked to Policy Authority"). The rulings below authorize the
neutral `VendorRiskLabel` in governance-contracts and the contracts-only package
`packages/integration/vendor-dependency`, and nothing beyond them.

Evidence labels: `[V]` verified against this repository at commit `38bfc255`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Which package answers *which external AI system or supplier does this organization
depend on, and under what declared risk posture*, without becoming a second
Policy Authority, a second system inventory, or a risk classifier? **Nothing does,
and no existing package reserves the noun.** The nearest neighbours each own a
different question, listed below. Under VR-1 the answer is a record of vendor
dependencies; it evaluates nothing.

## 2 — What the repository already fixed

| Finding | Where |
|---|---|
| No README or NEXT_PHASES under `packages/`, `products/`, `apps/`, `ugence_console_api/` or `Project_documentation/` reserves "vendor", "supplier" or "third-party" as an AI-governance noun; every hit is a dependency disclaimer, a fixture, or a different sense `[V]` `[G]` | repository-wide search over `README.md` and `NEXT_PHASES.md` |
| "Third-Party Gateway" is a **connector** milestone in the Risk Authority ladder (RA-5 → RA-8), roadmap text with no code; it names where an external effect source plugs in, not who the counterparty is `[V]` | `packages/risk_authority/README.md:32`; `docs/architecture/RISK_AUTHORITY_RA8_SPEC.md:54` |
| "Supplier" is taken in a **different sense** — the counterparty of a purchase in the procurement product, never an AI vendor `[V]` | `packages/products/procurement/README.md:3`; `docs/NEXT_PHASES.md:22` |
| `SystemRegistration` carries an `owner_ref` and an uninterpreted `classification_label`, and the README states there is no `severity`, `risk_level`, `tier` or `is_high_risk` on the record; it has no supplier field `[V]` | `ai-system-registry/src/ugence_ai_system_registry/registration.py:87-98`; `README.md:58` |
| Policy Authority declares itself the only one: "There is exactly **one** Policy Authority in Ugence; this is it" `[V]` | `packages/policy-authority/README.md:5` |
| The by-reference seam to a policy already exists in the neutral contracts: `policy_refs: tuple[str, ...]` on the action request `[V]` | `governance-contracts/.../contracts/action.py:35` |
| The identity to bind against exists and fixes the reuse direction: `AssessedSystemBinding` `[V]` | `contracts/system_identity.py:17-18` |
| The uninterpreted-label shape has a precedent landed this wave: `DataClassificationLabel` (0.6.0), `order=False`, structural validation only `[V]` | `contracts/data_classification.py` |
| The contracts-only shape has two precedents, the second shipped this wave `[V]` | `packages/integration/ai-system-registry`; `packages/integration/data-use-admission` |

The sequencing ADR's prohibition (line 85) is satisfied: the package is named for
what it records, and takes neither "gateway" nor "supplier".

## 3 — The first slice

Following `data-use-admission`: a `VendorDependencyDeclaration` binding one
`AssessedSystemBinding` re-exported from governance-contracts (VR-2), an opaque
package-local `vendor_ref` string (VR-5), a `VendorRiskLabel` re-exported from
governance-contracts as the declared risk posture (VR-3, VR-5), one opaque
`policy_ref` string (VR-4), a `Validity` window and an optional `supersedes`.
Refusal reasons for a blank reference, a look-alike binding or label, and a
mismatched tenant. Pure selectors, in-force first. One read-only Protocol, no
implementation.

**Structurally unable:** no store, connector, gateway, scorer, questionnaire
engine or clock; no resolution, verification or fetch of `policy_ref`; and no
import of Policy Authority, Risk Authority or AI System Registry.

## 4 — Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| VR-1 | The noun and package name | **`packages/integration/vendor-dependency`**, distribution `ugence-vendor-dependency`, namespace `ugence_vendor_dependency`. The package records vendor dependencies; it is not a gateway (Risk Authority's connector), a supplier system (procurement's counterparty), a registry, or an authority. |
| VR-2 | Does a vendor record bind to a registered system, to an `AssessedSystemBinding`, or to both? | **`BINDING_ONLY`.** Each `VendorDependencyDeclaration` binds directly to exactly one canonical `AssessedSystemBinding`. The package must not import or depend on AI System Registry; a registry registration is neither required nor accepted as an alternative identity. |
| VR-3 | Is risk an uninterpreted label, as DE-3? | **`SEPARATE_OPAQUE_RISK_LABEL`.** A distinct `VendorRiskLabel`, not `DataClassificationLabel`: data classification and vendor-risk posture are different dimensions. `VendorRiskLabel` is non-empty and uninterpreted — no grade, enum, taxonomy, ordering, severity, score, dominance or implied eligibility. |
| VR-4 | How is the link to Policy Authority expressed without importing it? | **`POLICY_REF_STRING`.** One non-empty opaque `policy_ref` string, matching the shape of `policy_refs` on the action request. The package must not resolve, verify, interpret or fetch it, and must not import Policy Authority. |
| VR-5 | Does the slice land any neutral type in governance-contracts first? | **Yes — `VendorRiskLabel`.** Landed first in `packages/governance-contracts` as a neutral immutable type with structural validation only; it grants no authority and makes no risk judgment. `vendor_ref` stays an opaque package-local string; no second neutral type without another ruling. |

## 5 — Maturity ceiling, stated once

**Contracts only.** The package records what a declarer asserted about a vendor
dependency. There is **no operational vendor-risk evaluation**: no scoring, no
grading, no questionnaire, no due-diligence workflow, no policy resolution, no
contact with any vendor, and nothing that proves a declared vendor exists, that
the declared posture is apt, or that the named system actually depends on it.
`ENFORCEMENT_ENABLED` is `False` and stays so until a further ruling authorizes an
engine. A declaration is a record, not a permission.

## 6 — Next step

Implement `packages/integration/vendor-dependency` 0.1.0 under the decisions
above, after `VendorRiskLabel` lands in governance-contracts.
