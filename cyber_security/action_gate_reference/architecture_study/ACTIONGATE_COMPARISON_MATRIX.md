# ActionGate — Comparison Matrix

**Status:** architecture study (documentation only). No marketing language. ActionGate facts are
code-grounded **[fact]**; comparisons to external products are **[interpretation]** based on their
public design (not verified against their source). External products evolve; treat their columns
as "as commonly documented."

## 1. What each system fundamentally is

| system | fundamental role |
|---|---|
| **ActionGate** | deterministic, evidence-bound, commit-time **authorization of a specific action instance**, with a replay-proof execution token and hash-chained audit **[fact]** |
| CyberArk | privileged-access management + secrets vaulting + session isolation/recording |
| Okta | identity provider (authN) + SSO/MFA + lifecycle/SCIM |
| AWS IAM | cloud identity + coarse permission policy evaluation for a principal |
| HashiCorp Boundary | identity-aware session brokering/proxy to targets |
| Open Policy Agent (OPA) | general-purpose policy **decision** engine (Rego) returning allow/deny+data |
| LangGraph | agent/workflow **orchestration** graph runtime |
| CrewAI | multi-agent **orchestration** framework |
| OpenAI Agents SDK | agent loop + tool-calling **orchestration** SDK |

## 2. Capability matrix

Legend: ● present/native · ◐ partial/adjacent · ○ absent/out-of-scope · n/a not that kind of system.

| capability | ActionGate | CyberArk | Okta | AWS IAM | Boundary | OPA | LangGraph | CrewAI | OpenAI Agents |
|---|---|---|---|---|---|---|---|---|---|
| authenticate a principal (IdP) | ○ | ◐ | ● | ● | ◐ | ○ | ○ | ○ | ○ |
| coarse principal→permission decision | ◐ | ● | ◐ | ● | ◐ | ● | ○ | ○ | ○ |
| **per-action-instance authorization** | ● | ○ | ○ | ○ | ○ | ◐ | ○ | ○ | ○ |
| **canonical action identity (hash)** | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| **evidence bound to the exact action** | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| multi-party approval + SoD, bound to action | ● | ◐ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| **replay-proof execution token (nonce+expiry)** | ● | ◐ | ◐ | ○ | ◐ | ○ | ○ | ○ | ○ |
| **commit-time TOCTOU revalidation** | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| deterministic, reproducible decision | ● | ○ | ○ | ◐ | ○ | ● | ○ | ○ | ○ |
| non-compensatory severity precedence | ● | ○ | ○ | ○ | ○ | ◐ | ○ | ○ | ○ |
| general policy language | ○ | ○ | ○ | ◐ | ○ | ● | ○ | ○ | ○ |
| secrets vaulting / short-lived creds | ○ (broker abstraction only) | ● | ◐ | ◐ | ● | ○ | ○ | ○ | ○ |
| session proxy/recording | ○ | ● | ○ | ○ | ● | ○ | ○ | ○ | ○ |
| hash-chained, self-verifying audit | ● | ◐ | ◐ | ◐ | ◐ | ○ | ○ | ○ | ○ |
| agent/tool orchestration + planning | ○ (by design) | ○ | ○ | ○ | ○ | ○ | ● | ● | ● |
| LLM in the trust/decision path | ○ (excluded by design) | n/a | n/a | n/a | n/a | ○ | ● | ● | ● |
| reasons about reversibility/consequence | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| executes rollback/compensation | ○ | ○ | ○ | ○ | ○ | ○ | ◐ | ◐ | ◐ |

## 3. Overlap / missing / unique / fundamental difference

### vs identity & access stack (CyberArk, Okta, AWS IAM, Boundary)
- **Overlap [interpretation]:** approvals, credential scoping, and audit are shared concerns; a
  broker-issued short-lived credential (`broker.py`) resembles session/secret brokering.
- **Missing in ActionGate [fact]:** it is not an IdP, not a vault, not a session proxy — it assumes
  an authenticated principal and a broker; it issues no identities and stores no secrets.
- **Unique to ActionGate [fact]:** the decision binds to a **canonical action hash** with
  **evidence** and is revalidated at **commit time** against the actual call, including **TOCTOU**
  state. IAM systems authorize a *principal for a permission* (coarse, session-scoped, no evidence,
  no commit binding).
- **Fundamental difference [interpretation]:** IAM answers "may this identity do this class of
  thing?" ActionGate answers "may **this exact action instance**, with **this evidence** and
  **these approvals**, be **committed now** against **this state**?" — a per-instance commit gate,
  not a session grant.

### vs Open Policy Agent
- **Overlap [interpretation]:** both are deterministic policy decision points; both treat policy as
  data.
- **Missing in ActionGate [fact]:** a general policy language — the operator set is fixed
  (`policy.py`), not Rego.
- **Unique to ActionGate [fact]:** OPA returns a decision; ActionGate additionally **binds** that
  decision to a cryptographic action identity, mints a **replay-proof execution token**, enforces
  **commit-time revalidation + TOCTOU**, binds **evidence/approvals**, and **hash-chains** the
  record. OPA does none of these — they are a *protocol* around the decision, not the decision.
- **Fundamental difference [interpretation]:** OPA is a **decision function**; ActionGate is a
  **decision + commit protocol**. One could, in principle, use OPA *as* the decision core inside an
  ActionGate-style protocol; the protocol is the contribution.

### vs agent frameworks (LangGraph, CrewAI, OpenAI Agents SDK)
- **Overlap [interpretation]:** all sit around agent tool-calling.
- **Missing in ActionGate [fact]:** orchestration, planning, memory, and LLM integration — **by
  design**; the LLM is kept outside the trust boundary (R1/R1.5/R2 milestones).
- **Unique to ActionGate [fact]:** deterministic authorization + non-repudiable audit + replay-proof
  commit tokens for agent tool calls, with the planner excluded from the decision path.
- **Fundamental difference [interpretation]:** these frameworks **are the (untrusted) agent** — they
  produce actions. ActionGate **governs** which produced actions may commit. They are
  **complementary, not competing**: an agent framework emits an action envelope; ActionGate
  authorizes and commits it. (This is exactly the R1.5 integration boundary.)

## 4. Where ActionGate is weakest (honest)

- **[fact]** No IdP/vault/session-proxy — depends on surrounding infrastructure.
- **[fact]** Fixed operator set — less expressive than a general policy language for exotic rules.
- **[fact]** Single-action scope — no built-in multi-action atomicity/saga coordination.
- **[fact]** Reference crypto/audit — production PKI, key custody, and tamper-*proof* storage are
  out of scope in this reference.

## 5. One-sentence positioning (no marketing)

**[interpretation]** ActionGate is not a competitor to IAM, OPA, or agent frameworks; it is the
**missing per-action commit gate** between an (untrusted) agent/policy decision and an irreversible
external effect — the layer that binds a specific action to evidence and approvals and commits it
exactly once, deterministically, with an audit trail.
