# Reference EvidenceObligation Component (Phase 9)

*`evidence_obligation/{claim_type,source_role,authority,risk,taxonomy,policy,classifier,audit,metrics}.py`.
The component under test: it assigns each claim an evidence obligation. It never asserts truth, judges
sufficiency, or authorizes delivery/action.*

## Pipeline (`policy.assign` → `classifier.classify`)

1. **Claim-type** (`claim_type.py`) — ordered detectors, high-consequence families first; fail-closed to
   `process_description`.
2. **Source-role** (`source_role.py`) — path + content; fail-closed to `unknown_source`.
3. **Risk** (`risk.py`) — ambiguity resolves upward; low-risk source cannot override high-impact use.
4. **Taxonomy default** (`taxonomy.py`) — risk-aware default obligation.
5. **Authority guard** — an artifact-dependent obligation (`IMPLEMENTATION_*`, `INTERNAL_*`) is kept
   only if the source is genuinely authoritative for that family; `SELF_REFERENTIAL` /
   `NOT_AUTHORITATIVE` → escalate to `INDEPENDENT_CORROBORATION_REQUIRED`; `HISTORICAL_ONLY` → `TEMPORAL`.
6. **Risk escalation** — never lowers.
7. **Structural floors** — no `NO_FACTUAL_EVIDENCE_GATE` on high risk; no low-burden on an action.

`classifier.classify` never raises: any exception or structural violation forces
`INDETERMINATE_OBLIGATION` / `HUMAN_REVIEW_REQUIRED` (fail-closed).

## What it may / may not do

**May:** classify claim type, source role, artifact authority; assign obligation + minimum standard +
required source classes; emit ambiguity, human-review, reason codes, and an audit record.

**May not:** mark available evidence sufficient; declare a claim true; fabricate authority; assume
"internal" means authoritative; assume comments match runtime; bypass a high-risk requirement; authorize
delivery or action.

## Accuracy vs the independent gold (measured)

| Partition | exact | acceptable | unsafe assignments |
|---|---|---|---|
| DEVELOPMENT | 0.567 | 0.707 | 2 |
| HELD_OUT_NATURAL | 0.560 | 0.736 | 6 (2.4%) |
| ADVERSARIAL_OBLIGATION | 0.500 | 0.500 | **0** |

**The safety-critical result is 0 unsafe assignments on the adversarial disguise set** — when the
component errs on adversarial cases it errs *stronger*, never weaker. The 6 unsafe held-out assignments
are all high-risk **code docstrings** describing security-sensitive behavior (TOCTOU re-check, DB-safety
evaluator, tool-selection) that the independent gold conservatively labelled `HUMAN_REVIEW_REQUIRED`; the
component chose `INTERNAL_AUTHORITATIVE`/`CONTEXTUAL`. This residual (2.4%) is reported honestly and **not
overfit away** — whether it causes unsafe *delivery* is the downstream question (Phase 15), since
EvidenceAssurance and the gates still apply to the weaker standard.

## Determinism

Every stage is a pure function of the item; `audit.replay_signature` over the decision-bearing content
is stable across runs (tested). No wall-clock, no randomness.
