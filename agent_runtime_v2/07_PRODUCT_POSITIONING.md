# Deliverable 7 — Product Positioning

Rewritten positioning under the three-family portfolio the milestone specifies, and how the products interact. Grounded in the repo briefs for each product.

Labels: `FACT` (from the product's own brief) / `INTERPRETATION` / `RECOMMENDATION`.

---

## 1. The three families (as given)

| Family | Products | What the family sells |
|---|---|---|
| **Specialized AI Systems** | Hybrid LLM · CG LLM · **Agent Runtime** | Applied intelligence — models and agents that *do the work* |
| **AI Control Plane** | Context Minimization · ActionGate · Autonomous Control Plane (ACP) | Deterministic governance — *what is allowed, authorized, and safe* |
| **AI Infrastructure** | KVPro · Cloud Scaling Controller | Efficiency substrate — *making inference cheap, fast, and scalable* |

**FACT — each product, from its own brief:**
- **Hybrid LLM** (`HYBRID_LLM_VC_BRIEF.md`): `HybridPhaseTransformer` — algorithmic *fusion* of linear + sliding-window + binding-cache attention; a long-context attention substrate.
- **CG LLM / Conscious Generation** (`CONSCIOUS_GENERATION_LLM_VC_BRIEF.md`): a "model-agnostic semantic-control layer for LLMs that improves answer framing, reduces semantic drift, and audits generated responses — without modifying model weights" (C×R×S), with a deeper 32-D symbolic-generation research moat. (This subsumes the CSR/CRS steering engine.)
- **Agent Runtime** (this design): governed single-agent→hierarchical reasoning + workflow-execution runtime that proposes to the Control Plane.
- **Context Minimization** (`CONTEXT_MINIMIZATION_VC_BRIEF.md`): deterministic authorization-preserving context compression.
- **ActionGate** (`ACTIONGATE_VC_BRIEF.md`): deterministic pre-commit authorization; grants one exact action, once.
- **ACP** (`acp/…`): deterministic operational-safety decision runtime; cross-domain (robotics + cloud).
- **KVPro** (`KVPro_VC_brief.md`): quality-safe KV-cache compression; drop-in vLLM backend path.
- **Cloud Scaling Controller** (`docs/CLOUD_SCALING_CONTROLLER_VC_BRIEF.md`): read-only autoscaling safety interlock; causal HELPING/NOT_HELPING verdict per scale-out.

---

## 2. Positioning statements (rewritten, no buzzwords, evidence-anchored)

**RECOMMENDATION — per product:**

- **Agent Runtime** — *"The agent that proposes; the Control Plane disposes."* A model-agnostic runtime that turns a goal into a reasoned, reflected, tool-using workflow — and routes every consequential action through the AI Control Plane for authorization and safety. It owns intelligence and execution, never authority.
- **Hybrid LLM** — *"One attention mechanism that retrieves globally, attends locally, and scales linearly — by fusion, not stacking."* The long-context model substrate.
- **CG LLM** — *"Control the meaning-frame the model answers in, and audit every answer — on any model, no weight changes."* The generation-control + audit layer.
- **Context Minimization** — *"Remove only what the decision provably doesn't need."* Deterministic, authorization-preserving context reduction.
- **ActionGate** — *"Authorize one exact action, once."* The deterministic pre-commit authority.
- **ACP** — *"Is this safe against live state right now?"* The deterministic operational-safety runtime, cross-domain.
- **KVPro** — *"Near-full-precision quality at 2× KV density."* The KV-cache efficiency layer.
- **Cloud Scaling Controller** — *"A causal verdict for every scale-out."* The autoscaling safety interlock.

---

## 3. How the products interact — the platform data flow

```
                 ┌──────────────────── SPECIALIZED AI SYSTEMS ───────────────────┐
                 │                                                                │
   user goal ───▶│  AGENT RUNTIME  ── reasons/plans/reflects ──┐                 │
                 │        │                                     │ generation on   │
                 │        │ uses a model:                       ▼                 │
                 │        │   HYBRID LLM (long-context substrate)                 │
                 │        │   + CG LLM (frame control + answer audit)             │
                 │        │                                                       │
                 │        │ builds an Execution Proposal (+risk/uncertainty)      │
                 └────────┼───────────────────────────────────────────────────────┘
                          │  proposal + evidence
                          ▼
                 ┌──────────────────── AI CONTROL PLANE ─────────────────────────┐
                 │  CONTEXT MINIMIZATION → what the model may read                │
                 │  ACTIONGATE          → authorized? (token, credential, quorum) │
                 │  ACP                 → operationally safe now?                 │
                 └────────┬───────────────────────────────────────────────────────┘
                          │  verdict + single-use token
                          ▼
                 ┌──────────────────── AI INFRASTRUCTURE ────────────────────────┐
   runs on ─────▶│  KVPro (KV-cache efficiency)  ·  Cloud Scaling Controller     │
                 │  (serving cost/quality)          (safe autoscaling of it all)  │
                 └────────────────────────────────────────────────────────────────┘
```

**FACT-anchored interaction points:**
- **Runtime → Hybrid LLM / CG LLM.** The runtime is model-agnostic (FACT: `llm_adapters` for OpenAI/Anthropic/Mistral + `MistralCGAdapter`). It can run on Hybrid LLM (better long-context) and enrich generation with CG LLM (frame control + the 32-D signal — now *advisory* per the falsification finding, useful as evidence not governance).
- **Runtime → Control Plane.** The Execution Proposal (Deliverable 3) is the single seam. Context Minimization optionally compresses the runtime's context; ActionGate authorizes; ACP safety-checks.
- **Control Plane → Infrastructure.** ACP already *consumes* the Cloud Scaling Controller as its cloud operational-safety evaluator (FACT: `acp/AI_CONTROL_PLANE_ARCHITECTURE.md` — "ACP (frozen core + cloud_controller)"). KVPro sits under all model inference.
- **Infrastructure is beneath everything.** KVPro reduces serving cost for every model call the runtime makes; the Cloud Scaling Controller scales the serving fleet — itself governed by ACP.

**INTERPRETATION — the platform story in one line.** *Infrastructure makes AI cheap and fast; Specialized Systems do the applied work; the Control Plane makes the work safe and authorized.* The Agent Runtime is the demand-generator that ties the three together: it consumes models (Specialized/Infra), and it feeds the Control Plane.

---

## 4. Why the Agent Runtime belongs in Specialized AI Systems (not the other families)

**FACT-anchored:**
- **Not AI Infrastructure.** It is not compute/memory/attention/serving plumbing (that is KVPro / Hybrid LLM's substrate / Cloud Controller). It is an applied system built *on top of* infrastructure.
- **Not AI Control Plane.** The prior review established it is probabilistic, threshold-based, and its authorization parts duplicate ActionGate; reclassifying it there re-introduces the exact overlap the Control Plane forbids.
- **It is a Specialized AI System** — an applied, probabilistic system that produces intelligence and executes workflows, siblings to the two model products (Hybrid LLM, CG LLM). Where those two make *a better model*, the Agent Runtime makes *a better agent from any model*.

**INTERPRETATION.** The three Specialized AI Systems form a natural sub-stack: **Hybrid LLM** (the substrate) → **CG LLM** (generation control on the substrate) → **Agent Runtime** (agency on top). This mirrors the pitchbook's own vertical-composition claim (FACT: `docs/XOZENCE_PITCHBOOK.md` — "Hybrid LLM → Steering/CG → Agentic Framework consumes state for governance").

---

## 5. Naming discipline (carry-over from the prior review)

**RECOMMENDATION.** Reserve **"AI Control Plane"** for the ActionGate/ACP/Context-Min stack only. Rename the runtime's internal `policy_control_plane.py` to "agent behavior policy surface." Product name for the runtime: **Agent Runtime** (role) / codename **Sentinel** (legacy brand continuity) — avoid the generic "Agentic Framework," which every competitor also uses. One term, one owner, across the portfolio.
