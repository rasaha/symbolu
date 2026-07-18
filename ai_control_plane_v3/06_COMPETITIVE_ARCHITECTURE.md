# Part 6 — Competitive Architecture

Architectural comparison only (not features, not marketing) across ten capability categories. Where Ugence is stronger, weaker, or equivalent.

Labels: `FACT` (Ugence, repo-verified) · `EXTERNAL KNOWLEDGE` (competitor architectures, general knowledge as of a Jan-2026 cutoff — directional, not verified against current releases). The two are kept strictly separate per the milestone constraint.

Compared: OpenAI Agents SDK, LangGraph, CrewAI, Microsoft AutoGen, Google ADK, Amazon Bedrock Agents. "Ugence" here = Agent Runtime V2 + the AI Control Plane.

---

## 1. Category-by-category

Legend: **S** = Ugence stronger · **=** equivalent · **W** = Ugence weaker (all vs the competitor field as a whole).

| Category | Ugence position | Assessment |
|---|---|---|
| **Planning** | `=` | FACT: `goal_decomposition` (LLM plan + rule fallback). EXTERNAL: LangGraph's explicit graphs and AutoGen/ADK planning are at least as capable; Ugence is not differentiated here. |
| **Memory** | `W` | FACT: `memory_store` (working + episodic, retrieval, retention pending M3). EXTERNAL: LangGraph checkpointer + persistent stores and Bedrock managed memory are more mature. |
| **Workflow** | `W`→`=` | FACT: single-agent per-turn loop; `reasoning_workflows` standalone/unwired. EXTERNAL: LangGraph's durable graph is the state of the art. Ugence weaker today; the V2 design closes toward `=`. |
| **Execution** | `=` | FACT: tool dispatch via `mcp_gateway`. EXTERNAL: all have solid tool execution; parity. |
| **Authorization** | **`S`** (decisive) | FACT: ActionGate — deterministic, non-compensatory, single-use token, credential brokering (`gate.py`, `broker.py`). EXTERNAL: none of the six has action-level deterministic authorization; Bedrock has IAM-role scoping (standing role, not per-action). **Ugence uniquely strong.** |
| **Operational Safety** | **`S`** (decisive) | FACT: ACP — live-state readiness/blast/capacity/freeze/rollback, cross-domain (`acp/`). EXTERNAL: no competitor has a separate operational-safety layer that must *also* pass. **Ugence uniquely strong.** |
| **Context Governance** | **`S`** (qualified) | FACT: Context Minimization — decision-invariant compression, but ActionGate-coupled (`compressor.py:36–58`). EXTERNAL: competitors do RAG/truncation with no decision-preservation proof. Ugence stronger *in kind*, but bundled with ActionGate, not standalone. |
| **Infrastructure Awareness** | **`S`** | FACT: ACP consumes live `cloud_controller` state; the Cloud Scaling Controller is itself a safety-gated infra product. EXTERNAL: agent frameworks are infra-agnostic; Bedrock is AWS-aware but not action-safety-aware. |
| **Recovery** | `=`→`S` | FACT: ACP deterministic failure-state machine + `NO_SAFE_ACTION`; runtime-side retries partial. EXTERNAL: LangGraph ret/checkpoint recovery is strong at the workflow level. Ugence stronger on *action* recovery, comparable on *workflow* recovery. |
| **Auditability** | **`S`** | FACT: ActionGate tamper-evident hash-chained authorization audit; deterministic replay. EXTERNAL: LangSmith and cloud logging are strong *observability*, but not *tamper-evident deterministic decision records*. Ugence stronger on the governance-grade audit specifically. |

---

## 2. The shape of the comparison

**INTERPRETATION.** The pattern is stark and consistent:

- **On runtime categories (Planning, Memory, Workflow, Execution): Ugence is weaker-to-equivalent.** The competitors have more mature orchestration, durable state, and ecosystems (EXTERNAL KNOWLEDGE; corroborated by the prior review's FACT that Ugence is late-prototype with one CLI entry point and no CI gate).
- **On governance categories (Authorization, Operational Safety, Context Governance, Infrastructure Awareness, Auditability): Ugence is uniquely strong** — and the strength is *architectural*, not incremental. These are categories the competitor frameworks **do not have as first-class layers at all**, because they sit outside the runtime.

**This is the whole strategic point.** Ugence should not try to win the runtime race (it is behind and the field is strong). It wins by owning the layer the runtimes structurally cannot own.

---

## 3. The re-framing this enables

**INTERPRETATION (strategy).** Because the governance categories are architecturally external to any runtime (Part 5), the competitors are not only rivals — they are **candidate consumers** of the Ugence Control Plane. A LangGraph deployment at a regulated enterprise has excellent workflow orchestration and *no* deterministic action authorization; a Ugence Control Plane in front of it supplies exactly the missing categories. This is the basis for Part 9's positioning recommendation and Part 8's multi-runtime deployment.

**FACT caveats (honesty):**
- The competitor assessments are EXTERNAL KNOWLEDGE at a Jan-2026 cutoff; specific feature claims should be re-checked against current releases. The *category-level* gaps (no deterministic action authorization, no operational-safety layer) are structural and slow-moving, but a competitor could add a governance layer.
- Ugence's governance strength is currently **shadow-only / pre-transport** (FACT: no production, ActionGate transport in-process/planned, only K8s connector validated). The *architecture* is stronger; the *deployment readiness* is behind. Part 10's roadmap and Part 11's risks address this.
