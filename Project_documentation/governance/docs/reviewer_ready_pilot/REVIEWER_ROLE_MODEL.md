# Reviewer Role Model (Phase 2)

*The reviewer roles needed when real reviewers are added later. No actual people are invented; these are
role definitions the recruitment plan (Phase 19) fills.*

## Roles

### 1. Technical Reviewer

| Field | Definition |
|---|---|
| Expertise | software engineering; reads code, tests, config, API/schema; understands implementation vs documentation |
| Allowed artifacts | implementation, API, code-behavior, performance, technical policy |
| Prohibited artifacts | those requiring a domain licence they lack (e.g. clinical) |
| Allowed actions | Stage-A blinded label, Stage-B post-reveal label, override with reason |
| Conflict of interest | may not review artifacts they authored |
| Qualification | passes the technical qualification items (impl≠operational, fixture≠telemetry) |
| Training | full guide + technical examples |
| May adjudicate | no (unless separately assigned as adjudicator on other artifacts) |
| May view system result | only at Stage B |

### 2. Policy / Risk Reviewer

| Field | Definition |
|---|---|
| Expertise | policy, risk, compliance, or operations; judges authority, actionability, risk, escalation |
| Allowed artifacts | policy, permission/prohibition, action proposals, risk-bearing claims |
| Prohibited artifacts | those requiring deep implementation reading beyond their skill |
| Conflict of interest | may not review policies they own or approve |
| Qualification | passes the policy/authority qualification items (draft≠approved, action needs approval) |
| May adjudicate | no (unless separately assigned) |
| May view system result | only at Stage B |

### 3. Domain Reviewer (optional specialist)

| Field | Definition |
|---|---|
| Expertise | legal, financial, medical, cybersecurity, or another regulated domain |
| Allowed artifacts | artifacts in their domain requiring specialist judgment (E4 cases) |
| Prohibited artifacts | outside their domain |
| Conflict of interest | domain-specific; declared per engagement |
| May adjudicate | domain disagreements only |
| May view system result | only at Stage B |

### 4. Adjudicator

| Field | Definition |
|---|---|
| Expertise | senior technical + policy judgment; resolves disagreements |
| Independence | **does not participate in the initial independent review of the artifacts they adjudicate** |
| Allowed actions | view the disagreeing reviewers' labels + evidence; record adjudicated reference or `UNRESOLVED` with rationale |
| Prohibited | forcing majority-rule; modifying the frozen policy |
| May adjudicate | yes (by definition) |
| May view system result | yes, during adjudication |

### 5. Pilot Administrator

| Field | Definition |
|---|---|
| Expertise | pilot operations |
| Allowed actions | manage assignments, access, stop controls, audit review; **never changes labels** |
| Prohibited | assigning a label, adjudicating, viewing reviewer identity mapping beyond what operations require |
| May adjudicate | no |
| May view system result | operationally, but never edits it |

## Cross-cutting rules

- **Every role** uses a pseudonymous ID; identity mapping is access-controlled (governance protocol).
- **No role** may see another reviewer's label before submitting its own, or the system result before
  Stage B (except adjudicator/administrator per their definitions).
- **No role** may modify the frozen policy, tune it on the reviewer set, or trigger enforcement.
- Role assignments and permissions are enforced by `access.py` (Phase 12).
