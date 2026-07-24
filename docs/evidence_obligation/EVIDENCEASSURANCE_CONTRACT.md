# Obligation → EvidenceAssurance Contract (Phase 10)

*`evidence_obligation/adapters.py`. Translates an obligation + available evidence into the
`evidence_steer` the **frozen** EvidenceAssurance consumes. EvidenceAssurance still judges sufficiency;
this adapter only expresses, honestly, whether the *applicable* standard is met.*

## The cardinal rule

**"No external evidence required" is never transformed into "claim is verified true."** A
low-external-burden obligation whose standard is met by the artifact maps to an **obligation-relative
`VERIFIED`**, reason-coded `OBLIGATION_RELATIVE` — "standard met by context/implementation; factual truth
not independently established." A **high-external-burden** obligation without external evidence **never**
maps to `VERIFIED` (stays `INSUFFICIENT`). This single asymmetry is what lets utility rise while safety
holds.

## Mapping (obligation × available evidence → EA state → delivery)

| Obligation | Available? | EA state | Delivery |
|---|---|---|---|
| NO_FACTUAL_EVIDENCE_GATE | (non-factual) | VERIFIED* | ALLOW |
| CONTEXTUAL_SUPPORT_SUFFICIENT | context (always) | VERIFIED* | ALLOW |
| IMPLEMENTATION_EVIDENCE_SUFFICIENT | impl inspectable | VERIFIED* | ALLOW |
| IMPLEMENTATION_EVIDENCE_SUFFICIENT | not inspectable | INSUFFICIENT | withhold |
| INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT | authoritative artifact | VERIFIED* | ALLOW |
| EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | external absent | **INSUFFICIENT** | withhold |
| INDEPENDENT_CORROBORATION_REQUIRED | external absent | **INSUFFICIENT** | withhold |
| TELEMETRY_OR_MEASUREMENT_REQUIRED | telemetry absent | **INSUFFICIENT** | withhold/escalate |
| POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED | policy+approval absent | **INSUFFICIENT** | withhold |
| ATTRIBUTION_VERIFICATION_REQUIRED | unverified | VERIFIED_WITH_LIMITATIONS | qualify |
| TEMPORAL_VERIFICATION_REQUIRED | not current-verified | INSUFFICIENT | withhold |
| LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED | unchecked | VERIFIED_WITH_LIMITATIONS | qualify |
| QUALIFY_BY_DEFAULT | — | VERIFIED_WITH_LIMITATIONS | qualify |
| HUMAN_REVIEW_REQUIRED | — | ESCALATE | escalate |
| INDETERMINATE_OBLIGATION | — | INDETERMINATE | withhold |

`*` = obligation-relative VERIFIED (standard met, not a truth claim). Verified in a smoke test:
CONTEXTUAL/IMPLEMENTATION → ALLOW; TELEMETRY/EXTERNAL without evidence → INSUFFICIENT.

## Three things kept separate (again)

- The adapter sets `evidence_state` and obligation-relative `adequacy`/`grounding` — **not** truth.
- **EvidenceAssurance (frozen)** decides whether the state clears its own delivery contract.
- **AssertionGate / ActionGate (frozen)** decide delivery. No frozen threshold is touched.

## Available-evidence model

For a natural artifact, `available_evidence_for` reflects what the artifact intrinsically provides:
`implementation` iff the source is inspectable code/test; `internal_authoritative` iff artifact
authority is high; `context` always; and **`external`/`telemetry`/`policy`/`approval` = False** (a
natural artifact carries none). The error-propagation study (Phase 16) injects overrides to test what
happens when these are misclassified.

## Safety invariant (tested)

A high-external-burden obligation with no external/telemetry/policy evidence never yields `VERIFIED`.
This is the structural guarantee that the contract cannot manufacture a clean allow for a claim that
genuinely needs independent evidence.
