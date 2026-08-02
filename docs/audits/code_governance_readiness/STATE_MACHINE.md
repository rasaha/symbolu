# State Machine — Code Governance Workflow

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§7, §13).
> The state machine is **PRODUCT_INTERNAL**, owned by the Workflow Service, distinct from Decision
> Authority's `DecisionCase` state machine.

## 1. Enforcement rungs (separate paths)

- **MVP 1A — Shadow.** Full pipeline runs and records; **no merge blocking, no execution.**
- **MVP 1B — Recommendation.** Publishes governance status (check-run + summary); humans keep the
  existing merge path; **no Ugence-driven merge.**
- **MVP 1C — Enforced authorization.** Requires the complete chain, live clearance, exact-artifact
  binding, and controlled dispatch.

## 2. Canonical states

```
CREATED → INGESTED → EVIDENCE_PENDING → EVIDENCE_ADMITTED → CLAIM_EVALUATED
        → DECISION_PENDING → APPROVED → AUTHORIZATION_ISSUED → CLEARANCE_PENDING
        → READY_TO_DISPATCH → DISPATCHING → MERGED → RECONCILED
```

Terminal / alternative states:
`DENIED · ESCALATED · REPAIR_REQUESTED · AUTHORIZATION_EXPIRED · CLEARANCE_DENIED ·
CHAIN_INCOMPLETE · SUPERSEDED · CANCELLED · FAILED · UNCERTAIN`.

`MERGED` (or `RECONCILED`) is a **terminal** state for the merge-governance workflow. Deployment is a
**separate, optional** workflow (MVP3) — `MERGED` does not imply `DEPLOYED`.

## 3. Transition ownership & fail-closed behavior

| Transition | Owner | Fail-closed rule |
|---|---|---|
| INGESTED → EVIDENCE_PENDING | Workflow Service (webhook) | invalid signature → reject, no state |
| EVIDENCE_PENDING → EVIDENCE_ADMITTED | TAP (via WS) | INDETERMINATE/UNSUPPORTED → not admitted |
| EVIDENCE_ADMITTED → CLAIM_EVALUATED | TAP | unsupported claims recorded; no advance on failure |
| CLAIM_EVALUATED → DECISION_PENDING | Workflow Service | missing mandatory evidence → hold |
| DECISION_PENDING → APPROVED / DENIED / ESCALATED / REPAIR_REQUESTED | **Decision Authority** | AI-as-decider / SoD violation → error, no APPROVED |
| APPROVED → AUTHORIZATION_ISSUED | **ActionGate** (via WS mapping) | DENIED/INDETERMINATE/EXPIRED → no issue |
| APPROVED → CHAIN_INCOMPLETE | Workflow Service | any missing chain link → terminal, no dispatch |
| AUTHORIZATION_ISSUED → AUTHORIZATION_EXPIRED | WS/ActionGate | CER/authz expiry → terminal |
| AUTHORIZATION_ISSUED → CLEARANCE_PENDING | Workflow Service | — |
| CLEARANCE_PENDING → READY_TO_DISPATCH / CLEARANCE_DENIED | **ACP** | HOLD / stale artifact / incident / freeze → CLEARANCE_DENIED |
| READY_TO_DISPATCH → DISPATCHING | Workflow Service | chain re-proof fails → CHAIN_INCOMPLETE |
| DISPATCHING → MERGED / FAILED / UNCERTAIN | **GitHub Execution Provider** | transport timeout → UNCERTAIN (never auto-MERGED) |
| MERGED → RECONCILED | DA reconciliation | mismatch/duplicate → MANUAL_REVIEW / compensation |
| any → SUPERSEDED | Workflow Service (re-entry) | patch/head/base/policy change → supersede |
| any → CANCELLED | Workflow Service / actor | — |

**Re-entry rule (§7):** any modification to the selected patch after validation returns the workflow
to an earlier state — to `CANDIDATES_GENERATED`/`INGESTED` if it creates a new candidate (different
`patch_commit_sha`/`diff_digest`), or to `EVIDENCE_PENDING`/`VALIDATION_COMPLETE` if it only re-runs
validation on the same candidate. A combined Patch C is always a **new candidate** (§8), never an
inheritor of A's or B's evidence refs.

## 4. Mode-specific behavior

- **1A Shadow:** the machine runs to a simulated `APPROVED`/`DENIED` and stops; no
  `AUTHORIZATION_ISSUED`/`DISPATCHING`. Produces the calibration corpus (false-block/escalation/
  override rates).
- **1B Recommendation:** advances to a published recommendation (check-run) and stops before any
  Ugence-driven merge.
- **1C Enforced:** the full path with `CHAIN_INCOMPLETE` fail-closed and one-time consumption at
  `DISPATCHING`.

## 5. Competitive & deployment separation

- Competitive Code Adjudication states (`ADJUDICATED → SELECT/REJECT/REPAIR/ESCALATE`) are **not
  forced into standard mode**; in standard mode the adjudicator stage is a trivial pass-through
  (single candidate). (design §7, §2.)
- Deployment remains optional and separate; `MERGED` may be terminal for merge governance.

## 6. Relationship to Decision Authority states

DA's `DecisionCase` machine (`CaseStatus`, terminal {SUPERSEDED, CANCELLED, CLOSED}; **no executed
state**) governs *the decision case only*. The product workflow **references** DA states but owns the
broader ingestion→execution→reconciliation lifecycle. Do not overload `DecisionCase` to carry
execution/clearance states.
