# Downstream Contract (Phase 9)

*`minimal_evidence_policy/adapters.py`. Maps an E-level obligation into the evidence_steer the **frozen**
EvidenceAssurance consumes. Meeting an obligation does not imply universal truth; no frozen threshold is
modified.*

## Separated representations

The steer carries these **distinct** fields so obligation is never confused with truth:

- `obligation_level` — E0…ER (what standard applies)
- `obligation_relative_verified` — True only for a met contextual/implementation standard
- `factual_truth_status` — always `not_independently_established` (the policy never asserts truth)
- `evidence_state` — what the frozen EA evaluates
- downstream `evidence`/`assertion`/`action` states — decided by the frozen gates

## Mapping (E-level × available evidence → EA state → delivery)

| Level | Available | EA state | Delivery |
|---|---|---|---|
| E0 (non-factual) | — | VERIFIED* | ALLOW |
| E1 (contextual) | context (always) | VERIFIED* | ALLOW |
| E2 (internal/impl) | impl or authoritative | VERIFIED* | ALLOW |
| E2 | absent | INSUFFICIENT | withhold |
| E3 (independent/measured) | external/telemetry absent | **INSUFFICIENT** | withhold |
| E4 (external + review) | — | **ESCALATE** | escalate (mandatory review) |
| ER | — | ESCALATE | escalate |

`*` obligation-relative VERIFIED (standard met, not truth). Verified in a smoke test: E2-met → ALLOW;
E3/E4/ER without independent evidence → INSUFFICIENT/ESCALATE.

## The safety asymmetry (unchanged from the concept)

A natural artifact carries no external/telemetry/policy evidence, so **E3 and E4 can never yield a clean
VERIFIED** — they withhold or escalate. Clean allows come only from E0/E1 and E2-with-artifact-evidence.
This is what lets the minimal policy raise utility (E0/E1/E2 met → allow) while holding safety (E3/E4
withheld). The error-propagation study (Phase 14) can inject `external`/`telemetry` overrides to test
misclassification.

## Non-modification

EvidenceAssurance still decides sufficiency from `evidence_state`; the adapter sets obligation-relative
adequacy, never a truth score, and touches no frozen threshold. AssertionGate and ActionGate (for action
claims) run frozen and read-only downstream.
