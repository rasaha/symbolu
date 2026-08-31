# ActionGate — Domain Generalization

**Status:** architecture study (documentation only). **[fact]** = code-grounded, **[interpretation]**
= architectural reading, **[speculative]** = not yet evidenced.

## 1. Universal core vs domain-specific data

The separation is visible directly in the code layering.

| layer | universal or domain-specific | grounding |
|---|---|---|
| canonicalization + domain-separated hashing | **universal** | `jcs.py`, `hashing.domain_digest`, `canon_profile.DOMAINS` (10 domain tags) — no cloud concept |
| envelope schema (24 fields) | **universal transaction envelope** | `schema.REQUIRED_FIELDS` — `agent_identity`, `delegator`, `delegation_chain`, `objective`, `tool`, `operation`, `target_resource`, `arguments`, `credential_scope`, `current_state_hash`, `state_freshness`, `reversibility`, `policy_version`, `correlation_id`, `sequence_id`, … — all generic transaction fields |
| operator evaluation engine | **universal** | `gate.evaluate` operator loop + `_SEVERITY` precedence — reads facts + policy only |
| evidence / approval / token / audit binding | **universal** | `evidence.py`, `approval.py`, `token.py`, `audit.py` — bind to `action_hash`/`policy_hash`, nothing cloud-specific |
| **operation vocabulary** (`IAM_GRANT_ADMIN`, `DEPLOY`, `DB_DELETE`, …) | **domain-specific DATA** | `schema.OPERATIONS`, `policy.DEFAULT_RULES` — a signed data bundle, not engine code |
| **fact extraction** (`extract_facts`) | **domain-specific ADAPTER** | `gate.extract_facts` — the one place `arguments` → domain facts; the gate calls it "the 'domain adapter' stub" |
| **policy rules** (which operators guard which operation) | **domain-specific DATA** | `policy.DEFAULT_RULES` R1–R10 — signed policy, swappable |

**[fact]** The current operations are Kubernetes/cloud-flavored, but they are **values in a signed
policy bundle and an enum**, not branches in the engine. The engine matches
`rule["operation"] == envelope["operation"]` (string equality) and evaluates generic operators.

**[interpretation]** Therefore three things are Kubernetes/cloud-specific and everything else is
universal:
1. the **operation names** (data),
2. the **fact adapter** that reads `arguments` (one function),
3. the **policy rules** (signed data).

The security model — canonical action identity, evidence/approval binding, non-compensatory
decision, replay-proof commit token, TOCTOU revalidation, hash-chained audit — is **domain-free**.

## 2. Kubernetes-specific vs cloud-specific vs general transaction semantics

- **Kubernetes-specific [fact]:** nothing in `action_gate_ref`. The K8s coupling lives only in a
  *transport adapter* package (`action_gateway_k8s/`), not in the decision core.
- **Cloud-specific [fact]:** the *example* operations/targets (IAM ARNs, `terraform apply`) and the
  example fact names (`sink_approved`, `admin_port`). These are policy/adapter data.
- **General transaction semantics [fact]:** action canonicalization + hashing, the six-outcome
  non-compensatory decision, evidence/approval binding, the execution token + nonce + TOCTOU
  commit check, and the audit chain. None of these mention a cloud concept.

## 3. Could the same engine authorize other domains without changing the security model?

For each: **reusable** (works unchanged), **adapter** (new data/fact-extraction only), **genuinely
new** (a requirement the current architecture does not cover). All rows are **[interpretation]**
built on the **[fact]** layering above; **[speculative]** where noted.

| domain | reusable (unchanged) | required adapter | genuinely new requirement |
|---|---|---|---|
| **ERP** (PO approval, invoice pay, vendor create) | full engine, binding, token, audit, approvals/SoD (native fit for four-eyes) | operation vocabulary + facts (amount, budget line, vendor risk) + policy rules | multi-step **workflow/saga** atomicity across several actions (engine governs one action at a time) |
| **Banking** (wire, freeze, limit change) | full engine; amount thresholds map to `MAX_COST`; dual-control to `REQUIRE_APPROVER`; TOCTOU to balance state | facts (amount, sanctions flag, KYC), operations, rules | **settlement finality / idempotency across external rails** (nonce covers replay into the gate, not exactly-once at the rail); regulatory **hold/clawback** windows |
| **Robotics** (arm payload, actuate, grasp) | full engine for **discrete** high-consequence actions; reversibility/`rollback_plan`; evidence = sensor attestations | facts (physical preconditions), operations, rules; a real state oracle for `current_state_hash` | **hard real-time latency bounds** and **continuous control** — the engine is discrete-action and synchronous-decision; continuous/streaming control is out of model **[speculative]** |
| **Enterprise SaaS** (provision user, export data, change plan) | full engine; export controls map to `FORBID`/`REQUIRE_APPROVER`; audit chain for compliance | facts (tenant, data class), operations, rules | **multi-tenancy isolation** of policy/audit per tenant (a deployment concern, not an engine change) |
| **Autonomous software agents** (tool calls) | **native fit** — envelope already carries `agent_identity`, `model_provider`, `delegator`, `delegation_chain`, `objective`; LLM already outside the trust boundary | operation vocabulary for the tool surface + facts | essentially **none** fundamental; this is the design center |
| **Multi-agent workflows** | per-action governance; `delegation_chain` models delegation; `correlation_id`/`sequence_id` model ordering | facts per tool | **cross-agent causal ordering + multi-action atomicity** (a composition/coordination layer above the single-action gate) |

## 4. The recurring "genuinely new" theme

**[interpretation]** Across domains, the engine reuses cleanly and the *new* requirements cluster
into two categories the current architecture deliberately does **not** cover:
1. **Multi-action atomicity / sagas** — ActionGate is a *single-action* commit gate; composing
   several authorized actions into an all-or-nothing unit needs a coordinator on top (it is not a
   distributed transaction manager). See `ACTIONGATE_TRANSACTION_ANALYSIS.md` §"Rollback".
2. **Continuous / hard-real-time control** — the decision is discrete and synchronous;
   streaming/continuous actuation is out of the current model.

Everything else is **adapter + policy data**, not an engine or security-model change.

## 5. Net assessment

**[interpretation]** ActionGate generalizes from "Kubernetes/DevOps authorization" to a
**general discrete-action transaction-authorization engine** without changing the security model,
provided each new domain supplies (a) an operation vocabulary, (b) a fact-extraction adapter, and
(c) signed policy rules — and provided the domain's actions are **discrete and synchronously
decidable**. Multi-action atomicity and continuous control are genuine extensions, not adapters.
**[speculative]** claims (robotics real-time, external-rail idempotency) require a prototype in
that domain before they can be asserted as facts.
