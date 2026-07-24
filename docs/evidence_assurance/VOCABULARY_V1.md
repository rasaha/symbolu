# EvidenceAssurance Disposition Vocabulary — v1 (FROZEN)

*Phase 11. This freezes the EvidenceAssurance evidence-state vocabulary **before** final
evaluation. Implemented in `evidence_assurance/taxonomy.py` (`EvidenceState`). These are
**evidence-state** dispositions — they describe the state of the *evidence for a claim*. They are
kept deliberately **separate** from AssertionGate **delivery** dispositions (ALLOW / QUALIFY /
REJECT / ESCALATE / INDETERMINATE): EvidenceAssurance determines the evidence state; AssertionGate
determines what is delivered. The mapping between the two is a contract (Phase 14), not an identity.*

Frozen: v1. Any change to the eleven states, their semantics, or the delivery-effect mapping is a
**v2** and requires a new doc + re-freeze. Downstream code and evaluation reference v1 by name.

## The eleven states

| State | Meaning | Supported delivery? |
|---|---|---|
| `VERIFIED` | Supported by aligned, independent, authoritative, fresh evidence. | **yes** |
| `VERIFIED_WITH_LIMITATIONS` | Supported, but with a caveat (single-source, narrower scope, minor staleness). | **yes, qualified** |
| `CONFLICTED` | Credible counterevidence or an authoritative conflict exists. | no |
| `INSUFFICIENT` | Not enough independent support to certify. | no |
| `STALE` | Evidence is outdated or superseded. | no (qualify/escalate) |
| `MISALIGNED` | The cited passage does not support **this** claim (scope / population / time / jurisdiction). | no |
| `DEPENDENT` | Apparent corroboration is **not** independent (single underlying source). | no (qualify) |
| `AUTHORITY_MISMATCH` | The source is not authoritative for this domain / decision. | no |
| `INDETERMINATE` | Cannot decide — unknown provenance or missing metadata. | no |
| `REJECT_EVIDENCE_STATE` | Evidence **contradicts** the claim, or is fabricated. | no |
| `ESCALATE` | Needs human / external verification before any delivery. | no |

Only `VERIFIED` and `VERIFIED_WITH_LIMITATIONS` deliver a claim as positively supported
(`delivered_as_supported()`). Every other state is in `UNSUPPORTED_STATES` — delivering it as
supported is an **escape** (the primary safety endpoint of this study).

## Delivery-effect contract (EvidenceState → AssertionGate)

`DELIVERY_EFFECT` in `taxonomy.py`. This is the **adapter contract** consumed in Phase 14; it is not
a re-labeling. `high_risk` cases raise `INSUFFICIENT` / `STALE` / `DEPENDENT` toward `ESCALATE`
(handled in the adapter, not baked into the map).

| EvidenceState | AssertionGate delivery |
|---|---|
| `VERIFIED` | ALLOW |
| `VERIFIED_WITH_LIMITATIONS` | QUALIFY |
| `CONFLICTED` | ESCALATE |
| `INSUFFICIENT` | INDETERMINATE |
| `STALE` | QUALIFY |
| `MISALIGNED` | REJECT |
| `DEPENDENT` | QUALIFY *(claim may be fine; corroboration is single-source)* |
| `AUTHORITY_MISMATCH` | ESCALATE |
| `INDETERMINATE` | INDETERMINATE |
| `REJECT_EVIDENCE_STATE` | REJECT |
| `ESCALATE` | ESCALATE |

## Conservatism ordering (for two-annotator adjudication)

`CONSERVATISM` in `taxonomy.py` orders states from least to most restrictive so that
`more_conservative(a, b)` can pick the safer disposition when annotators diverge. The ordering
(0 = permissive → 5 = most restrictive):

```
0  VERIFIED
1  VERIFIED_WITH_LIMITATIONS
2  DEPENDENT, STALE
3  INSUFFICIENT, INDETERMINATE
4  MISALIGNED, AUTHORITY_MISMATCH, CONFLICTED
5  ESCALATE, REJECT_EVIDENCE_STATE
```

`DEPENDENT` and `STALE` sit together (the soft tail where the two annotators legitimately disagree —
see `GROUND_TRUTH_PROTOCOL.md`). The safety-critical states (`MISALIGNED`, `AUTHORITY_MISMATCH`,
`CONFLICTED`, `REJECT_EVIDENCE_STATE`) are shared by both annotators via hard precedence and never
disagreed on.

## Why evidence state is kept separate from delivery state

A single collapsed label would conflate two questions that fail independently:

1. **What is the evidence?** (aligned? independent? authoritative? fresh? contradicted?) —
   EvidenceAssurance.
2. **What should we deliver?** (allow / qualify / reject / escalate) — AssertionGate, which also
   weighs risk tier, policy, and cost.

Keeping them separate is what lets `DEPENDENT` (correct claim, single source) map to QUALIFY while
`REJECT_EVIDENCE_STATE` (contradicted / fabricated) maps to REJECT — even though **both look like a
single underlying source** at the independence layer. The distinction is recovered by alignment +
counterevidence, not by the delivery label. Collapsing the vocabularies would lose exactly the
correlated-failure discrimination this study exists to test.
