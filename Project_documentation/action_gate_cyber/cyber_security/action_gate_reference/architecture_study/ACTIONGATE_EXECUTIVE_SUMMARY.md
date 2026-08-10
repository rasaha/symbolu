# ActionGate — Executive Summary

**One line:** ActionGate is a **deterministic commit gate for autonomous-agent actions** — it
authorizes a *specific* high-consequence action, binds it to evidence and approvals, and commits it
**exactly once** with a tamper-evident audit trail, while keeping the AI/LLM **outside the trust
boundary**.

This summary is deliberately conservative: claims below are grounded in the reference
implementation and its tests. Where something is a projection or not yet built, it says so.

## The problem
Autonomous agents (LLM-driven or otherwise) increasingly take real actions — deploy, pay, delete,
grant access, actuate. The frameworks that *drive* those agents (LangGraph, CrewAI, agent SDKs) are
not designed to be the security authority, and traditional access control (IAM, Okta, CyberArk)
authorizes a *person or role for a class of permission* — not a *specific action instance* with the
evidence and approvals that should gate an irreversible effect. There is a missing layer between
"the agent decided to do X" and "X irreversibly happened."

## What ActionGate is
A per-action **commit protocol** with a deterministic decision core:
- **Canonical action identity** — every action reduces to a content hash; authority artifacts bind
  to *that exact hash*.
- **Deterministic decision** — a pure, reproducible function of (action, signed policy, evidence,
  approvals, state); six fixed outcomes; no probability, no learning, **no LLM in the decision
  path**.
- **Evidence & multi-party approval** bound to the action (separation-of-duties, freshness).
- **Replay-proof execution token** — single-use, expiring, revalidated at commit against the actual
  call and the live state (defeats replay and time-of-check/time-of-use drift).
- **Hash-chained audit** — an append-only, self-verifying record of every decision and execution.

## Why it is differentiated (evidence-backed)
- It authorizes **the exact action instance**, not a session or role — a capability IAM/OPA/agent
  frameworks do not provide (see the comparison matrix).
- The AI is **outside the trust boundary**; the security guarantee does not depend on model
  behavior. Three completed engineering milestones (R1/R1.5/R2) added *advisory* remediation and a
  **measured study** concluding that a deterministic remediation loop suffices and an autonomous LLM
  planner is **not** justified on current evidence — i.e., the design resists the temptation to put
  the model in charge.
- The reference implementation ships with a written spec and **24 passing conformance vectors**
  covering replay, time-of-use state drift, canonicalization, and hashing.

## Generalization thesis (the growth story)
The Kubernetes/DevOps flavor is **data, not engine**: the operation vocabulary, one fact-extraction
adapter, and the signed policy rules are domain-specific; the decision logic, hashing, binding,
token, and audit are domain-free. **[interpretation]** The *same engine and security model* can
authorize ERP approvals, banking transactions, enterprise SaaS operations, and (its native fit)
autonomous-agent and multi-agent tool calls by swapping policy + adapter — **not** the engine.
Two honest boundaries: composing *many* actions into one all-or-nothing unit (sagas), and
*continuous/real-time* control (e.g., robotics), are genuine extensions, not adapters.

## Most accurate category
Technically, a **deterministic action-commit protocol** whose core is an **authorization engine**.
"AI Transaction Manager" is *partly* accurate — the begin/validate/prepare/commit spine is real —
but overstates capabilities ActionGate does not implement (locking, distributed two-phase commit,
resource rollback). The defensible product framing is **"execution governance / AI action-commit
gate."**

## What exists vs. what is still required (no overstatement)
**Exists:** a working reference engine + runtime, a canonicalization/hashing spec, 24 conformance
vectors, deterministic pinned action hashes, and the R1/R1.5/R2 remediation work with a measured,
reproducible study and passing security invariants.

**Required before strong external claims:**
- production cryptography and key custody (current signing is a **reference HMAC** stand-in);
- a **formal safety model** of the commit protocol (determinism is tested; replay/TOCTOU
  impossibility is argued, not yet proven);
- **performance/scale** evidence under real concurrency;
- at least one **non-cloud domain** implemented end-to-end to substantiate the generalization
  thesis;
- audit **tamper-proofing** (today it is tamper-*evident*, explicitly not a blockchain).

## Research angle
There is a credible **security/systems-security** paper in the architecture plus the R2 evidence
(contingent on the formal model and threat model above). The transaction-processing angle is a
*framing*, publishable only if the missing transaction machinery is actually built. The
product-architecture case stands today.

## The investable insight
As agents move from suggestions to actions, the market needs a **deterministic, auditable authority
that sits between the agent and the irreversible effect** — one whose guarantees do **not** depend
on the model being well-behaved. ActionGate is a working reference for exactly that layer, with a
clear, data-driven path to generalize across domains without changing its security model. The near-
term investment is in **production hardening (crypto, formal model, scale)** and **one lighthouse
non-cloud domain**, not in re-architecting the core.

*(Supporting detail: `ACTIONGATE_ARCHITECTURAL_ABSTRACTION.md`, `ACTIONGATE_DOMAIN_GENERALIZATION.md`,
`ACTIONGATE_COMPARISON_MATRIX.md`, `ACTIONGATE_TRANSACTION_ANALYSIS.md`,
`ACTIONGATE_RESEARCH_POSITION.md`.)*
