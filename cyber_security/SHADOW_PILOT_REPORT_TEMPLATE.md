# Shadow-Pilot Report — Composite Sequence-Risk Analyzer

**Phase constraint:** shadow mode only. No action is blocked or executed
differently. This template records the outcome of a bounded shadow evaluation.
A general "production ready" verdict is **not permitted** in this phase.

Every reported figure MUST carry an evidence-discipline label (spec §17):
`Measured — unit/integration test` · `Measured — synthetic corpus` ·
`Measured — historical replay` · `Measured — live shadow pilot` ·
`Modeled — operational projection` · `NOT RUN` · `REQUIRES ENTERPRISE DATA`.

---

## 1. Scope

| Field | Value |
|-------|-------|
| Workflow(s) evaluated | _…_ |
| Tenant(s) | _…_ |
| Environment | _…_ |
| Evaluation mode | synthetic corpus / historical replay / live shadow |
| Code commit | _…_ |
| Freeze digest | _… (from `cli freeze`)_ |
| Recipe versions | _…_ |
| Linkage schema | _ctd.linkage/1.0.0_ |
| Policy version | _…_ |

## 2. Volume

| Metric | Value | Evidence label |
|--------|-------|----------------|
| Events processed | _…_ | |
| Encoded recipes active | _…_ | |
| Escalations produced | _…_ | |
| `UNAVAILABLE` occurrences | _…_ | |
| Alerts / 1,000 events | _…_ | |

## 3. Human review outcomes

| Metric | Value | Evidence label |
|--------|-------|----------------|
| Reviews recorded | _…_ | |
| Review agreement rate | _…_ | |
| False-escalation reviews | _…_ | |
| Top false-escalation causes | _…_ | |
| Duplicate-alert burden | _…_ | |
| Noisiest recipe | _…_ | |
| Mean time to disposition | _…_ | |

## 4. Quality of context & linkage

| Metric | Value | Evidence label |
|--------|-------|----------------|
| Purpose-verification success | _…_ | |
| Incorrect benign-neutralization rate | _…_ | |
| Entity-linkage accuracy | _NOT RUN / …_ | |
| Ordering ambiguities | _…_ | |
| Conflicting-order events | _…_ | |

## 5. Safety & resource behavior

| Metric | Value | Evidence label |
|--------|-------|----------------|
| State-limit events | _…_ | |
| Evictions (audited) | _…_ | |
| `UNAVAILABLE` fail-visible confirmed | yes / no | |
| Audit chain valid | yes / no | |

## 6. Coverage

| Metric | Value | Evidence label |
|--------|-------|----------------|
| Mean lead time before completion | _REQUIRES ENTERPRISE DATA / …_ | |
| Missed known incidents (where available) | _…_ | |
| Unknown-threat detection | _~0 (not encoded)_ | |

## 7. Recommended rule changes

_List recipe/threshold/linkage changes suggested by review — to be applied only
AFTER this frozen run, never during it (§12)._

## 8. Enforcement-readiness verdict

Select exactly one (a general "production ready" verdict is not allowed here):

- [ ] `NOT READY — excessive false escalations`
- [ ] `NOT READY — insufficient threat coverage`
- [ ] `NOT READY — entity linkage unreliable`
- [ ] `NOT READY — trusted context unavailable`
- [ ] `NOT READY — state limits unsafe`
- [ ] `CONTINUE — synthetic evaluation only`
- [ ] `CONTINUE — historical replay justified`
- [ ] `CONTINUE — live shadow pilot justified`
- [ ] `READY — narrowly scoped hold policy candidate`

**Rationale:** _…_
