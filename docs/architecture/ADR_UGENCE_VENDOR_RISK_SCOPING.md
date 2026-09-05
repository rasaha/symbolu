# Ugence third-party AI and vendor risk — scoping record

**Status: SCOPED, NOT RULED — nothing here is implemented.** This record authorizes
no code change, creates no package, adds no dependency and amends no package ADR,
port, test or manifest. Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`
(wave 4, line 62: "contracts first, linked to Policy Authority"). It maps what
already borders the noun, what a first slice could record, and the five owner
decisions to rule before any code.

Evidence labels: `[V]` verified against this repository at commit `38bfc255`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Which package answers *which external AI system or supplier does this organization
depend on, and under what declared risk posture*, without becoming a second
Policy Authority, a second system inventory, or a risk classifier? **Nothing does,
and no existing package reserves the noun.** The nearest neighbours each own a
different question, listed below.

## 2 — What the repository already fixed

| Finding | Where |
|---|---|
| No README or NEXT_PHASES under `packages/`, `products/`, `apps/`, `ugence_console_api/` or `Project_documentation/` reserves "vendor", "supplier" or "third-party" as an AI-governance noun; every hit is a dependency disclaimer, a fixture, or a different sense `[V]` `[G]` | repository-wide search over `README.md` and `NEXT_PHASES.md` |
| "Third-Party Gateway" is a **connector** milestone in the Risk Authority ladder (RA-5 → RA-8), roadmap text with no code; it names where an external effect source plugs in, not who the counterparty is `[V]` | `packages/risk_authority/README.md:32`; `docs/architecture/RISK_AUTHORITY_RA8_SPEC.md:54` |
| "Supplier" is taken in a **different sense** — the counterparty of a purchase in the procurement product, never an AI vendor `[V]` | `packages/products/procurement/README.md:3`; `docs/NEXT_PHASES.md:22` |
| `SystemRegistration` carries an `owner_ref` and an uninterpreted `classification_label`, and the README states there is no `severity`, `risk_level`, `tier` or `is_high_risk` on the record; it has no supplier field `[V]` | `ai-system-registry/src/ugence_ai_system_registry/registration.py:87-98`; `README.md:58` |
| Policy Authority declares itself the only one: "There is exactly **one** Policy Authority in Ugence; this is it" `[V]` | `packages/policy-authority/README.md:5` |
| The by-reference seam to a policy already exists in the neutral contracts: `policy_refs: tuple[str, ...]` on the action request `[V]` | `governance-contracts/.../contracts/action.py:35` |
| The identity and the label to bind against exist and fix the reuse direction: `AssessedSystemBinding` and `DataClassificationLabel` `[V]` | `contracts/system_identity.py:17-18`; `contracts/data_classification.py` (0.6.0) |
| The contracts-only shape has two precedents, the second shipped this wave `[V]` | `packages/integration/ai-system-registry`; `packages/integration/data-use-admission` |

The sequencing ADR's prohibition (line 85) is satisfied, provided the package is not
named "gateway" or "supplier".

## 3 — A first slice, by analogy `[I]`

Following `data-use-admission`: a `VendorDependencyDeclaration` binding one
`AssessedSystemBinding` re-exported from governance-contracts, an opaque
`vendor_ref` in the caller's spelling, a `DataClassificationLabel` re-exported as
the declared risk posture, a `policy_ref` string naming a Policy Authority version
by reference, a `Validity` window and an optional `supersedes`. Refusal reasons for
a blank reference, a look-alike binding or label, and a mismatched tenant. Pure
selectors, in-force first. One read-only Protocol, no implementation.

**Structurally unable:** no store, connector, gateway, scorer, questionnaire engine
or clock, and no import of Policy Authority, Risk Authority or the registry.

## 4 — Decisions to rule `[R]`

| # | Decision | What turns on it |
|---|---|---|
| **VR-1** | The noun and package name. | Not "gateway" (Risk Authority's connector), not "supplier" (procurement's counterparty), not `…Authority` (it decides nothing). |
| **VR-2** | Does a vendor record bind to a registered system, to an `AssessedSystemBinding`, or to both? | Binding only keeps the package independent of the registry; registration only makes the registry a hard dependency; both risks two spellings of one identity. |
| **VR-3** | Is risk an uninterpreted label, as DE-3? | Reusing `DataClassificationLabel` means no risk taxonomy is minted; a separate `RiskLabel` would be a second opaque type, and a graded one needs a ratified scale first. |
| **VR-4** | How is the link to Policy Authority expressed without importing it? | A `policy_ref` string, matching `policy_refs` on the action request, keeps the "exactly one" rule; anything resolving or verifying the reference would need the authority itself. |
| **VR-5** | Does the slice land any neutral type in governance-contracts first? | A neutral `VendorReference` would follow D-4 and DE-5; reusing the existing binding and label lands nothing new. |

## 5 — Next step

Rule VR-1 to VR-5. Nothing is implemented by this record.
