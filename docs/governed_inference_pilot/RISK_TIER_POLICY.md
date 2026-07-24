# Risk-Tier Policy (Phase 14)

*`governed_inference_pilot/orchestrator.py::CONFIGS`. Four configurations. The full stack is **not**
assumed necessary for every request; the minimum-viable study (Phase 23) tests which components each
tier actually needs.*

## Configurations

| Config | Stages |
|---|---|
| **A. FULL_STACK_HIGH_RISK** | ExecutionGate → ModelPolicy → ClaimIntegrity → ScopeIntegrity → EvidenceAssurance → AssertionGate → ActionGate |
| **B. ASSERTION_GOVERNANCE** | ExecutionGate → ModelPolicy → ClaimIntegrity → EvidenceAssurance → AssertionGate |
| **C. ACTION_GOVERNANCE** | ExecutionGate → ModelPolicy → ClaimIntegrity → ActionGate |
| **D. MINIMUM_VIABLE_CONTROL_PLANE** | ExecutionGate → ModelPolicy → AssertionGate |

## Intended use

- **A (full stack)** for high/critical-risk requests that both assert and act — the maximal governance
  surface.
- **B (assertion governance)** for high-risk *informational* requests (no action) — drops ActionGate
  and ScopeIntegrity.
- **C (action governance)** for requests whose risk is in the *action*, not the assertion — a
  lightweight claim binding plus ActionGate.
- **D (minimum viable)** for low-risk requests — execution eligibility, model routing, and a single
  assertion check, with audit.

## The safety cost of a smaller tier (measured)

Running the corpus through each configuration shows the trade directly. The minimum-viable
configuration (D) produces **192 `WOULD_ALLOW`** outcomes versus the full stack's **64** — because it
omits EvidenceAssurance and ActionGate, so evidence failures and action-policy failures are delivered
as supported. This is the central risk-tier finding: **a smaller configuration is cheaper and faster
but leaks the failure classes its dropped stages were catching.** The minimum-viable study (Phase 23)
quantifies exactly which failure classes each tier catches and which it leaks, so a tier can be chosen
per risk with eyes open.

## Rule

The configuration is selected by the request's `risk_tier` and whether it carries an action, but the
selection is **explicit and audited** — never inferred silently. A low-risk request may omit
EvidenceAssurance; a high-risk request may not. The evaluation reports safety by configuration so the
tier policy rests on evidence, not assertion.
