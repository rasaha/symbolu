# Deliverable 10 — Reference Architecture

The complete future ecosystem, with every responsibility and every ownership boundary. This consolidates the ownership matrices of the prior milestones into the CER-centered picture.

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION`.

---

## 1. The full ecosystem

```
┌────────────────────────── RUNTIME TIER (any vendor) ─────────────────────────────┐
│  OpenAI · LangGraph · CrewAI · AutoGen · ADK · Semantic Kernel · Claude Code ·    │
│  Ugence Agent Runtime · future                                                   │
│  OWNS: reasoning · planning · decomposition · tool selection · memory ·          │
│        reflection · uncertainty · Execution INTENT                                │
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                     │  native tool/API call (the actuation boundary)
                                     ▼
┌────────────────────────── ADAPTER TIER (thin, mostly declarative) ────────────────┐
│  toCER(native_action) · fromVerdict(verdict, token) · credential brokering         │
│  OWNS: translation only. The ONLY place runtime-specificity is allowed.            │
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                     │  Canonical Execution Request (open standard)
                                     ▼
═══════════════════════════════ CER (the contract) ═══════════════════════════════════
     identity · authorization(request) · execution(action + lifecycle) · evidence ·
     metadata(non-identity) · audit anchors    —    NO policy, NO world-model, NO reasoning
                                     │
                                     ▼
┌────────────────────────── AI CONTROL PLANE (governor) ────────────────────────────┐
│  Context Minimization  → owns: what the model may READ (optional; ActionGate-      │
│                          coupled; fail-loud on vacuous compression)                │
│  ActionGate            → owns: AUTHORIZATION — may this exact action commit, once?  │
│                          (hard policy, credential brokering, token, quorum, audit)  │
│  ACP                   → owns: OPERATIONAL SAFETY — safe vs live domain state now?  │
│                          (per-domain WorldStateProvider; readiness/blast/freeze)    │
│  Composition           → owns: link verdicts → one eligibility class; never override│
│  PULLS (not from CER):  enterprise policy (root-of-trust) · live world-state (domain)│
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                     │  verdict + single-use token/credential (the response)
                                     ▼
┌────────────────────────── EXECUTION LAYER / INFRASTRUCTURE ────────────────────────┐
│  APIs · DBs · Kubernetes · robots · cloud · external services                      │
│  KVPro (inference efficiency) · Cloud Scaling Controller (safe autoscale)          │
│  OWNS: performing the authorized action with the brokered credential               │
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                     │  result
                                     ▼
              observation ── returns to the RUNTIME TIER (the loop) ──────────┐
                                                                              ▲
      (the runtime observes, reflects, updates memory, and may emit the next CER)
```

**FACT — the return arrow is not decoration.** The prior milestone established the runtime owns the observe→reflect→memory return path (`../execution_proposal_engine/` F1; `agent.py:490–514`). The ecosystem is a **loop**, not a waterfall.

---

## 2. Ownership boundary table (one owner per responsibility)

| Responsibility | Owner | Evidence |
|---|---|---|
| Reasoning, planning, decomposition, tool selection, memory, reflection, uncertainty | **Runtime** | `FACT`: runtime-internal; CP reads none of it |
| Execution Intent → CER translation; credential brokering | **Adapter** | `RECOMMENDATION`: the only runtime-specific component |
| The request contract (identity, authority-requested, action, lifecycle) | **CER (open standard)** | this milestone |
| Context relevance for the decision (optional) | **Context Minimization** | `FACT`: ActionGate-coupled |
| Authorization, hard policy, token minting, credential custody, approver quorum, tamper-evident audit | **ActionGate** | `FACT`: `gate.py`, `broker.py` |
| Operational safety vs live state, readiness, blast, freeze, rollback-availability | **ACP** | `FACT`: `interfaces.py` |
| Verdict composition / eligibility | **Composition** | `FACT`: `composition.py` |
| Enterprise policy authorship | **Enterprise (root-of-trust)** | `FACT`: `policy.py:5–6` |
| Live world-state | **Domain WorldStateProvider** | `FACT`: `interfaces.py:24–36` |
| Performing the authorized action | **Execution Layer** | — |
| Inference efficiency / safe autoscale | **Infrastructure (KVPro / Cloud Controller)** | `FACT` |
| Observation, reflection, memory update | **Runtime** (return path) | `FACT`: F1 |

**No duplicated ownership:** each row has exactly one owner, and the CER field-partition *is* the ownership partition — the runtime supplies the action+authority-request; the enterprise supplies policy; the domain supplies world-state; the control plane decides; the execution layer acts. (`FACT`: the disjointness of the CP layers is source-verified, "duplicated-logic count 0," `acp/RESPONSIBILITY_MATRIX.md`.)

---

## 3. The three things CER deliberately keeps out of the middle

**INTERPRETATION — restating the design discipline as architecture:**
1. **Policy never enters CER** — it is pulled by ActionGate from the enterprise. (Keeps the standard neutral across governors; T8.)
2. **World-state never enters CER** — only a binding hash; live state is pulled by ACP from the domain. (Keeps the standard neutral across domains; T9.)
3. **Reasoning never enters CER** — the runtime keeps it. (Keeps the standard neutral across runtimes; the whole thesis.)

These three exclusions are what make the middle (CER + the Control Plane) a *shared, neutral* layer that any runtime, any enterprise policy, and any domain can compose against. The reference architecture is, at its core, the enforcement of those three exclusions.
