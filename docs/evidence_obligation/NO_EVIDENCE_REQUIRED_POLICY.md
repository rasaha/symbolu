# No-Evidence-Required Policy & Risk Escalation (Phases 13–14)

*`evidence_obligation/no_evidence_gate.py` + `risk.py`. The narrow safe `NO_FACTUAL_EVIDENCE_GATE` class
and how risk elevates obligations.*

## The narrow no-gate class (Phase 13)

`NO_FACTUAL_EVIDENCE_GATE` is for genuinely non-factual content only:

- opinion, preference, explicit hypothetical, rhetorical text;
- formatting instruction, non-assertive transition;
- explicit uncertainty statement, local organizational label;
- author intention clearly marked as intention.

`eligible_for_no_gate(text, risk)` is **fail-closed**: high/critical risk → ineligible; any factual leak
(`cure`, `secure`, `production`, `payment`, `guarantee`, `uptime`, `complies`, …) → ineligible; otherwise
eligible only if an explicit non-assertive/opinion/hypothetical marker is present.

## Pilot-blocker check

**Blocker = any high-risk or factual claim assigned `NO_FACTUAL_EVIDENCE_GATE`.** Validated across all
500 items:

| | |
|---|---|
| no-gate assignments by the reference classifier | **0 / 500** |
| high-risk / factual no-gate violations | **0** |
| **PILOT BLOCKER** | **False** |

The reference classifier is conservative: it never routes a natural-artifact claim through the no-gate
class on this dataset — its clean allows come through `CONTEXTUAL`/`IMPLEMENTATION` obligations, not
through no-gate. The structural floor (`OBL.NO_GATE_ON_HIGH_RISK`) and the policy floor
(`POLICY.NO_GATE_FLOOR_HIGH_RISK`) make a high-risk no-gate assignment impossible by construction.
Directly rejects **H0-8** (a no-evidence class increases unsafe allows): 0 unsafe.

## Risk escalation (Phase 14)

`risk.assess_risk` — ambiguity resolves **upward**; a low-risk source classification never overrides a
high-impact use. Verified:

| Input | Risk |
|---|---|
| implementation claim + action_directive | **high** |
| "bypasses the credential check" | **high** |
| "this section describes the module layout" | low |

`risk.escalate_obligation` raises the obligation via the taxonomy's `high_risk` field and **never
lowers** it. Escalation examples the model honors:

- low-risk implementation description → implementation evidence may suffice;
- high-risk security capability → telemetry/measurement required;
- low-risk attributed statement → attribution verification;
- high-risk medical attribution → external authority still required;
- low-risk recommendation → contextual support;
- high-impact action recommendation → policy + authority + approval.

A low-risk source classification cannot override a high-impact use: the action/enforcement/customer-
delivery/high-impact-decision flags each floor the risk at high, which floors the obligation.
