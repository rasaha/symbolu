# Critical Transition Governance (OSGE) — governing state changes, not users

**Status:** a **possible later generalization / North-Star**, explicitly gated on validating the
beachhead. The **beachhead of record is `AGENT_ACTION_ADMISSIBILITY_MVP.md`** (a vendor-neutral
pre-commit admissibility gate at the autonomous-agent tool-invocation boundary, production-
infrastructure actions). This document reframes the problem from *authenticating identities* to
*authorizing consequential organizational state transitions*; it is pursued **only after** the
agent-action beachhead proves out, and it does **not** precede or replace it.
Companion to `ROADMAP.md` (§6), `AGENT_ACTION_ADMISSIBILITY_MVP.md`, `GAP_REGISTER.md`,
`COMBINED_ARCHITECTURE_BCVF2_USE_SCC.md`.

---

## 1. The reframe

Two different questions:

- **Authentication (all prior layers):** *is this the legitimate, live, trustworthy user?*
- **Governance (this layer):** *even if it is — should this organizational state transition
  happen, now, this way?*

The second is orthogonal to identity, and it catches a class the entire evidence stack
(behavioral, BCVF, USE, attestation) structurally **cannot**, because there is no attacker to
detect:

- insider threats and privileged misuse,
- compromised-but-authenticated privileged users,
- honest mistakes and misconfiguration,
- policy / compliance violations,
- **AI-agent errors** (an autonomous agent making a poorly-justified change).

## 2. The organization as a state machine

Enterprises have consequential states; **critical actions are the transitions between them**:

```
normal user → administrator
beneficiary absent → beneficiary added
model approved → model deployed
firewall rule absent → firewall rule active
database non-readable → database readable
funds held → funds transferred
```

These transitions are what matter; ordinary activity is not. The **critical transitions are
exactly the critical actions the Phase −1 threat model already enumerates** — so governance
reuses that artifact. Ordinary actions route to the lightweight risk-based flow; critical
transitions route to the governance handshake below.

## 3. The justification handshake

Before a critical transition is allowed, multiple independent pieces of evidence must agree —
richer than MFA, and required **even of legitimate administrators**:

```
identity  +  role  +  business justification  +  workflow approval
        +  policy compliance  +  device trust  +  timing/context
                         ↓
              handshake succeeds  →  transition allowed
```

Concretely, for e.g. a firewall change:

```
linked ticket exists?  → change request approved?  → required reviewers approved?
   → maintenance window active?  → requester owns the service?
      → deployment pipeline consistent?  → allow
```

This is the maker-checker / dual-authorization pattern that banks already apply to large wire
transfers (initiator + approver + second approver + treasury policy + business limits),
**generalized to every critical organizational state change.**

## 4. Where the AI wedge actually lives (and its hard boundary)

The differentiator is **AI reasoning over organizational *semantics*** — asking *"is this
request organizationally consistent?"* against the change request, ticket, project, prior
history, policy, and dependencies — which rigid rule engines cannot do. This is the clearest
expression of the one real wedge identified across this analysis, applied to the highest-value
problem (authorizing consequential change).

**Non-negotiable safety boundary** (more acute here than anywhere, because it's the authorize
path for the most consequential actions):

- AI is **advisory + escalate-only**: it may *raise* required assurance (add a reviewer, force
  human approval, require stronger proof) — **never lower it / auto-approve**.
- The allow/deny is a **deterministic, auditable policy evaluation**; **human approval** is
  required for top-stakes transitions.
- Treat the ticket/justification text as **attacker-controlled input** — prompt-injection with
  real stakes — so AI output is evidence, never authority.

## 5. Honest prior-art and differentiation

OSGE is a **synthesis of mature disciplines**, not a new primitive:

| Existing field | What it already does |
|---|---|
| Policy-as-code (OPA, Sentinel, Kyverno) | evaluate an action against org rules before allowing |
| ITIL change management (ServiceNow) | linked ticket / CR / reviewers / maintenance window |
| Maker-checker / segregation-of-duties | dual control on consequential actions |
| PAM / JIT (CyberArk, BeyondTrust) | justified, approved privileged transitions |
| Zero-trust policy decision point | context/policy-conditioned access decisions |

The differentiation is **not** the concept — it is the **AI semantic unification** across these
silos ("does this whole picture make organizational sense?"), executed safely (§4). Position
accordingly: this competes in GRC / policy-as-code / PAM / change-governance territory (all
incumbent-held), and the wedge is semantic reasoning the incumbents' rule engines lack.

## 6. Honest limits

1. **Integration cost.** The handshake reasons over systems-of-record (ITSM, IAM, CI/CD, HR,
   ticketing). This is a large, brittle, org-specific integration surface — the reason
   enterprise GRC is heavy. → OSGE is the **end-state layered on the MVP**, not the MVP.
2. **Collusion / fabricated justification.** A coordinated insider can create the ticket and
   enlist a colluding approver. The handshake **raises cost** (forge/collude across systems); it
   is not a guarantee. Enforce real segregation-of-duties, and give the **evidence/anomaly layer
   a renewed role**: flag when the *justification itself* is anomalous (ticket created seconds
   ago by the requester; approver never approves this class; out-of-window timing).
3. **AI-in-authorization risk** (§4) — mitigated by advisory + escalate-only + human approval +
   determinism + injection-resistance, never removed.

## 7. Where it fits the architecture

The four-layer model gains a governance decision-mode:

```
L1 Trust Evidence        → who is acting, how trustworthy is the session   (behavior, BCVF, USE, attestation)
L2 Consequence Model     → how damaging is this action                     (from the threat model)
L3 Decision Engine       → ordinary action: risk-based optimization
   └─ OSGE (governance)  → CRITICAL TRANSITION: justification handshake + AI-advisory consistency + human approval
L4 Action Orchestrator   → enact (with escalate-only agentic hints)
```

Evidence answers *who + how trustworthy*; OSGE answers *is this transition justified* — and the
final authorization requires **both**. The evidence layer also feeds OSGE by scoring whether the
justification is fabricated/anomalous.

## 8. Evaluation hook (operational, analogous to the MVP kill criterion)

> At a fixed rate of allowing legitimate critical transitions, does the governance handshake
> reduce **unjustified** critical transitions (insider misuse, mistakes, policy violations,
> agent errors) versus identity/risk-gating alone — at acceptable added latency and approver
> burden?

Baselines: identity+MFA only; consequence-gating only. Success is measured in *prevented
unjustified state changes vs approver/latency burden*, not in detector ROC. Like every other
component, OSGE and its AI-consistency reasoning must earn their place on this operational test
or be pared back to deterministic policy + human approval.
