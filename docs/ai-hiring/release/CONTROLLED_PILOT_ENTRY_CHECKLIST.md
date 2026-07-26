# Controlled Pilot — Entry Checklist

**No pilot may begin until every mandatory item below is acknowledged in writing by
the named owner.** This checklist gates entry into a bounded controlled pilot of AI
Hiring `0.6.0` (frozen at `b9a0e3a`). It confirms existing conditions; it does not
grant any production capability — the product performs simulated external effects only.

Each item: `[ ]` unmet → `[x]` acknowledged, with **owner** and **date**.

## 1. Governance — named accountable roles

| Role | Responsibility | Name | Date |
|---|---|---|---|
| `[ ]` Pilot owner | Overall accountability for the pilot | | |
| `[ ]` Technical owner | Deployment, operation, evidence collection | | |
| `[ ]` Security owner | Security posture, incident authority | | |
| `[ ]` Hiring authority | The human authority for any decision reviewed | | |
| `[ ]` Named reviewer(s) | Human reviewers who record decisions | | |
| `[ ]` Named approver(s) | Sign-off on entry and on exit | | |

> Decisions in AI Hiring are **human-only**; the named reviewers/authority are the
> `HUMAN_APPROVER` actors. This is enforced by the platform, but the *people* must be
> named here.

## 2. Data

| Item | Confirmed | Owner | Date |
|---|---|---|---|
| `[ ]` Data is **synthetic** or **approved de-identified** only | | | |
| `[ ]` The approved pilot dataset is documented and version-referenced | | | |
| `[ ]` Data exclusions are documented (what must never be ingested) | | | |
| `[ ]` No real candidate PII enters the process without approved de-identification | | | |

## 3. Platform / infrastructure

| Item | Confirmed | Owner | Date |
|---|---|---|---|
| `[ ]` Persistent repositories configured (pilot does not rely on in-memory only) | | | |
| `[ ]` Audit storage configured and durable (hash-chained audit preserved) | | | |
| `[ ]` End-to-end reconstruction verified against the configured storage | | | |
| `[ ]` Provider configuration verified (assertion + action governance providers) | | | |

> The shipped package uses in-memory repositories and static identity. A pilot that
> needs to retain evidence across process restarts must supply durable adapters for
> the platform's repository/audit ports. Those adapters are **not** part of this
> release (see [`../product/DEPLOYMENT.md`](../product/DEPLOYMENT.md)); providing them
> is a pilot-infrastructure task, not a product change, and must not alter frozen code.

## 4. Safety — no production external effects

| Item | Confirmed | Owner | Date |
|---|---|---|---|
| `[ ]` **No** production HRIS/ATS adapter is connected | | | |
| `[ ]` **No** production email/communication path is connected | | | |
| `[ ]` **No** production offer issuance (`ISSUE_OFFER` remains unimplemented) | | | |
| `[ ]` **No** production rejection communication (`SEND_REJECTION` remains unimplemented) | | | |
| `[ ]` **Simulated execution only** — `execution_mode == DETERMINISTIC_SIMULATION` | | | |
| `[ ]` `python -m ai_hiring.product verify` returns `RESULT: PASS` in the pilot env | | | |

## 5. Operations

| Item | Confirmed | Owner | Date |
|---|---|---|---|
| `[ ]` Incident contact identified and reachable | | | |
| `[ ]` Rollback procedure documented and tested | | | |
| `[ ]` Shutdown procedure documented | | | |
| `[ ]` Backup strategy for audit/evidence documented | | | |
| `[ ]` Log retention policy set | | | |
| `[ ]` Audit retention policy set | | | |

See [`OPERATIONAL_READINESS_CHECKLIST.md`](OPERATIONAL_READINESS_CHECKLIST.md).

## 6. Governance approvals

| Approval | Confirmed | Reviewer | Date |
|---|---|---|---|
| `[ ]` Privacy review complete | | | |
| `[ ]` Legal review complete | | | |
| `[ ]` Employment-policy review complete | | | |
| `[ ]` Security review complete (see [`../product/SECURITY_REVIEW.md`](../product/SECURITY_REVIEW.md)) | | | |

## Entry decision

- `[ ]` **All mandatory items above are acknowledged.**
- Pilot owner sign-off: __________________  Date: __________
- Approver sign-off: __________________  Date: __________

> If any mandatory item is unmet, the pilot does **not** begin. This checklist is the
> gate; the freeze declaration ([`FREEZE_DECLARATION.md`](FREEZE_DECLARATION.md)) is
> the standing constraint for the pilot period.
