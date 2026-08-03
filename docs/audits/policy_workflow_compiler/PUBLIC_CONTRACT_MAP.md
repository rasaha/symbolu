# Public-contract map

The compiler targets capability **public contracts** by stable identifier and
resolves them through the capability registry's metadata. It does **not** import
any runtime provider to emit an IR. The public-contract module recorded per
capability:

| Capability | Public contract module | Owned authority | Advisory/Authoritative |
|---|---|---|---|
| TAP | `ugence_tap_provider.api` | assertion-support / evidence admissibility | ADVISORY |
| Decision Authority | `ugence_decision_authority.api` | binding-decision governance, authority checks, SoD, override, decision record | AUTHORITATIVE |
| ActionGate | `ugence_actiongate_provider.api` | exact-action authorization | AUTHORITATIVE |
| Action Clearance | `ugence_action_clearance.api` | commit-time operational clearance | AUTHORITATIVE |
| StoryGraph | `ugence_storygraph.api` | sequence-risk analysis (OBSERVE/ESCALATE/UNAVAILABLE) | ADVISORY |
| Model Selection | `ugence_model_selection.api` | model eligibility (mandatory) + selection (advisory) | ADVISORY |
| Optional orchestrator | — (bypassable) | workflow composition | ADVISORY |

## Node-kind → capability authority table (enforced)

The synthesized IR must satisfy this table or compilation fails
(`AUTHORITY_BOUNDARY_VIOLATION`, FATAL):

| Node kind | Required owner | Required disposition |
|---|---|---|
| EVIDENCE_REQUIREMENT | COMPILER | ADVISORY |
| EVIDENCE_ADMISSIBILITY | TAP | ADVISORY |
| DECISION_RULE / AUTHORITY_CHECK / APPROVAL_GATE / SEGREGATION_OF_DUTIES_GATE / PROHIBITED_CONDITION / EXCEPTION_BRANCH / OVERRIDE_GATE | DECISION_AUTHORITY | AUTHORITATIVE |
| ACTION_CONSTRAINT | ACTION_GATE | AUTHORITATIVE |
| SEQUENCE_RISK_CHECK | STORYGRAPH | ADVISORY |
| ACTION_CLEARANCE_REQUIREMENT | ACTION_CLEARANCE | AUTHORITATIVE |
| AUDIT_EMISSION / TERMINAL_OUTCOME | COMPILER | ADVISORY |

This is the wiring the compiler may emit; it never lets one module self-authorize
another module's decision.
