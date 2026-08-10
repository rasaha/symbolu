# Execution Proposal Universality — Verdict & Falsification

**Milestone:** architecture-first, evidence-first. No production code, no implementation changes, no marketing.
**Hypothesis under test:** *Any modern agent runtime can produce the same canonical Execution Proposal.* If true → the Agent Runtime is replaceable and the AI Control Plane is runtime-independent. If false → locate the runtime-specific coupling.
**Method:** attempt to **falsify** before supporting. Study each runtime's actual action model; do not assume.

Labels on every claim: `FACT` · `INTERPRETATION` · `RECOMMENDATION` · `SPECULATION` · `EXTERNAL KNOWLEDGE`.
Supporting files: `01_CANONICAL_PROPOSAL_FIELDS.md` (del. 1), `02_RUNTIME_AUDIT_AND_ADAPTERS.md` (del. 2, 3), `03_OPEN_STANDARD.md` (del. 6), `04_REPOSITORY_IMPACT.md` (del. 8), `05_EXTERNAL_VALIDATION_PLAN.md` (del. 9). This file carries deliverables 4, 5, 7, 10, 11.

---

## 0. Falsification first — where the hypothesis actually breaks

I attacked the word **"same"** and the word **"any."** The hypothesis has two halves; they do not have the same truth value.

- **Half A — "any runtime can produce the *same* canonical proposal."** Partly **FALSIFIED as literally stated.** It is true only under a precise, achievable condition (a shared *actuation* surface), and false at the level of a runtime's *native action representation*.
- **Half B — "the AI Control Plane becomes runtime-independent."** **NOT falsified — strongly evidenced.** `FACT`: the Control Plane imports nothing from the Ugence runtime and already abstracts the producer as a generic "reader" (`04_REPOSITORY_IMPACT.md`).

The five falsification findings:

### FF1 — "Same action" is defined over ACTUATION, not INTENT → the naive claim is false
**INTERPRETATION, grounded in `FACT`.** The canonical action identity is a hash over `{tool, operation, targets, arguments}` (`01_...`; `FACT`: ActionGate hashes the action's own bytes, `projection.py`). Two runtimes achieving the *same effect* through *different tools* — `kubectl scale` vs a k8s-python client vs `terraform apply` — produce **different** proposals, and that is **correct**: from the gate's view they *are* different actions (different credential scope, reversibility, blast computation). So "identical intent → identical proposal" is **false**. "Identical actuation → identical proposal" is **true** (after excluding provenance, del. 5). The hypothesis holds only if runtimes converge on a **common actuation surface**.

### FF2 — Free-form / opaque action runtimes cannot be canonicalized at their native level → coupling is real but relocatable
**FACT + EXTERNAL KNOWLEDGE.** Runtimes that emit **arbitrary code** (AutoGen `UserProxyAgent`) or **opaque shell strings** (Claude Code `Bash("...")`) do not expose a structured action; the effect is unknown until executed. Canonicalizing such an action *pre-execution* is undecidable in general (you cannot statically determine what arbitrary code does). **This falsifies "any runtime at its native representation."** The fix relocates the boundary: intercept at the **actuation layer** (the actual API/syscall the code makes), not the runtime's plan. Then even AutoGen is canonicalizable — but only at the point of the concrete call, which requires a lower interception point than the runtime's action object.

### FF3 — Managed/closed runtimes emit a PRE-COMMIT proposal only with a return-control hook → PARTIAL for Bedrock
**EXTERNAL KNOWLEDGE.** Amazon Bedrock Agents execute action groups *inside AWS*. A pre-commit Execution Proposal exists only if the agent uses the **"return control"** path (hand the action back to the caller instead of executing). Without it, you get post-hoc traces, not a governable proposal. **This falsifies "any runtime" for closed runtimes without a return-control seam** — governance would be observe-after, not decide-before.

### FF4 — Operational identity is the weakest equivalence → depends on runtime state-visibility
**FACT.** ACP needs `state_binding` (world_state_hash + freshness) to evaluate operational safety, and it pulls live state from a domain `WorldStateProvider`, not the runtime (`interfaces.py:24–36`). But whether two runtimes *bind the same state* depends on each observing the same world at the same time. Two runtimes proposing the identical action against differently-observed state produce identical **authorization** identity but potentially different **operational** identity. So the four identities (proposal / authorization / operational / execution) do **not** all equilibrate equally across runtimes — operational is the loosest.

### FF5 — The Control Plane genuinely does not assume "our runtime" → Half B holds
**FACT.** Grep shows the Control Plane (ACP, ActionGate, Context Min) imports nothing from `agentic_framework`; the pipeline abstracts the producer as a generic "LLM stage (reader)" implemented by a `MockReaderClient` stand-in (`04_REPOSITORY_IMPACT.md`; `experiments/actiongate_context_ablation/llm_client.py:138`). The only runtime-shaped seam is a placeholder, and the only real coupling is *domain*-shaped (the reader emits a `KubernetesOperation`), not runtime-shaped.

**Net:** the hypothesis is **not unconditionally true** (FF1–FF4) but its failure modes are **interception-boundary and actuation-surface conditions, not Control-Plane couplings**, and its second half (runtime-independence of the Control Plane) is **proven** (FF5).

---

## Deliverable 4 — Universality Audit (hidden assumptions)

Does the proposal depend on any runtime internal? Tested each; `FACT` unless noted.

| Assumed dependency | Present? | Fundamental or removable? | Evidence |
|---|---|---|---|
| **Prompt format** | No | — | Control Plane reads no prompt; grep-clean decision paths (`../ai_control_plane_v3/02`) |
| **Memory** | No | — | proposal carries an action, not memory |
| **Reflection** | No | — | reflection is pre-proposal runtime work; not in the schema |
| **Reasoning traces / CoT** | No | — | MUST-NEVER-EXIST fields (`01_...`); grep-clean |
| **Tool framework** | **Partial** | **Removable via adapter** | the *representation* differs (function call vs shell vs code); the adapter normalizes to `{tool, operation, targets, args}` (FF1/FF2) |
| **Model vendor** | No (identity) / metadata only | Removable | `model` is provenance, excluded from identity (del. 5) |
| **Runtime identity** | Metadata only | Removable | `runtime` is provenance, excluded from identity (del. 5); FF5 |
| **Session format** | No | — | `correlation_id` is optional metadata |
| **Workflow engine** | No (decision) | — | graph/crew/conversation state never crosses the boundary |
| **Planner** | No | — | "ACP consumes a planner, is not one" (`FACT`) |
| **Actuation surface** | **YES** | **Fundamental (but enforceable)** | FF1 — same-ID requires same tool/API. This is the one real, irreducible dependency. |

**INTERPRETATION.** Eleven candidate couplings; ten are absent or removable-by-adapter. The **one fundamental dependency is the actuation surface** (FF1): the proposal's *identity* depends on *which tool/API* the runtime actuates through, not on how it reasoned. This is not a defect — it is the correct semantics (a scale via kubectl and a scale via Terraform are genuinely different actions to authorize). But it means universality is conditional on a shared actuation surface, which an enterprise can enforce precisely *because* ActionGate brokers credentials per-action (agents can't act except through the broker — see del. 7).

---

## Deliverable 5 — Identity Audit

**Should identical actions from different runtimes produce the same Execution Proposal ID?**

**RECOMMENDATION — YES, for identical *actuations*; and the ID must be a pure function of the action, excluding all provenance.** `FACT`-grounded (this fixes the R3 finding from `../ai_control_plane_v3/`).

**Must NOT participate in the ID hash:**
- `provenance.runtime` (e.g., "langgraph" vs "openai-agents") — else the same action from two runtimes gets two IDs (`FACT`: ActionGate currently hashes this, breaking portability, `projection.py:44–46`).
- `provenance.model`, `provenance.objective`, `provenance.correlation_id` — producer metadata, control-inert (`FACT`: `objective` is "Tier-3 advisory only").
- `principal.signature`, `action_id`/submission timestamp — per-attempt, not per-action (`FACT`: already excluded, `projection.py:31–36`).
- `evidence.*` (risk/uncertainty) — a runtime's *opinion* about the action, not the action.

**Must participate in the ID hash:**
- `action.{tool, operation, targets, arguments}` — the actuation.
- `authority.credential_scope` — the privilege requested (a read and a write of the same target are different actions).
- `reversibility`, `policy_ref` — consequence class and the policy in force.

**Why not "same ID for same intent":** because intent is not governable — only actuation is. Two runtimes that *mean* "scale web" but call different tools are proposing different governed actions; giving them the same ID would hide a real difference in credential scope and blast radius. So the identity boundary is **actuation-equivalence, not intent-equivalence** — and identical actuations *do* and *should* collide to one ID once provenance is excluded.

**Falsifiable consequence:** if, after excluding provenance, two runtimes emit the same actuation and still get different IDs, there is a residual coupling (a hidden field in the hash). The del. 9 experiment tests exactly this.

---

## Deliverable 7 — Competitive Impact

**Suppose every runtime emits this proposal. What remains differentiated?**

# Answer: the **Control Plane** (and the *standard itself*), not the runtime.

`INTERPRETATION`, from the falsification:
- **Runtime — commoditizes toward the interface, but NOT toward equal value.** If all runtimes emit the same proposal format, the *interface* is commodity — but the *quality* of the proposals differs enormously. A weak runtime emits a *valid, well-formed, badly-reasoned* proposal (wrong tool, wrong args, high uncertainty). So "replaceable at the interface" ≠ "equivalent in value." The runtime still competes on **proposal quality** (reasoning, planning, tool selection, uncertainty calibration) — Ugence's actual strength axis (raw-entropy AUROC 0.857, `FACT`). But this is a *converging* race (`EXTERNAL KNOWLEDGE`).
- **Control Plane — differentiates and compounds.** It is runtime-independent (FF5), structurally external (a boundary the agent controls is not a boundary, `FACT`: `ACTIONGATE_VC_BRIEF.md`), and no competitor has it as a first-class layer. Every runtime that adopts the proposal *increases the Control Plane's reach without Ugence building the runtime.*
- **The standard is the deepest moat.** `RECOMMENDATION`: whoever owns the interface contract that runtimes emit into owns the governance chokepoint. If Ugence defines and stewards the Execution Proposal standard (del. 6), the moat is not a product but a *position* — the OAuth/OpenAPI of agent governance.

**So: Control Plane B, plus the standard.** Not "both runtime and control plane" — the runtime is a necessary, converging product; the durable differentiation is the governed boundary and the contract that funnels into it.

---

## Deliverable 10 — Risks (attempt to destroy the architecture)

| # | Risk | Type | Severity | Detail / mitigation |
|---|---|---|---|---|
| K1 | **Heterogeneous actuation surfaces** | INTERPRETATION | high | FF1 — if enterprise agents actuate through different tools/APIs, IDs don't collide and cross-runtime equivalence fails. Mitigation: ActionGate credential-brokering forces a common surface (agents can't act except through the broker); enterprises standardize the tool layer. |
| K2 | **Free-form code / opaque actions** | FACT+EXTERNAL | high | FF2 — AutoGen/Claude-Code can't be canonicalized at plan level. Mitigation: intercept at the actuation layer (syscall/API), not the plan; `SIMULATE_AND_RETRY` for classification. Cost: a lower, per-tool interception. |
| K3 | **Managed runtimes without a pre-commit hook** | EXTERNAL | high | FF3 — Bedrock without return-control gives only post-hoc governance. Mitigation: require the return-control seam; otherwise the runtime is observe-only, not governable. |
| K4 | **Standard-adoption failure** | SPECULATION | high (strategic) | The moat (del. 7) needs runtimes to *adopt* the proposal. If MCP (or a hyperscaler) grows its own governance contract, Ugence's is bypassed. Mitigation: lead with an MCP adapter (adopt where runtimes already are), publish early (del. 6). |
| K5 | **Operational-identity divergence** | FACT | medium | FF4 — runtimes bind different state; operational verdicts may differ for the "same" action. Mitigation: standardize the `WorldStateProvider` per domain; treat state_binding as authoritative from the domain, not the runtime. |
| K6 | **Empirical undemonstration** | FACT | medium | No external runtime has been run end-to-end (only `MockReader`). Mitigation: the del. 9 experiment. Until then, universality is *architecturally supported, not shown*. |
| K7 | **Transport/maturity** | FACT | medium | Shadow-only; in-process transport; one validated connector. Mitigation: `../ai_control_plane_v3/10` roadmap. |
| K8 | **Provenance-in-identity (current bug)** | FACT | low-medium | ActionGate hashes runtime/model/objective → same action, different IDs across runtimes (`projection.py:44–46`). Mitigation: demote to metadata (del. 5). Small, load-bearing. |
| K9 | **Competitor bundles governance into the runtime** | EXTERNAL | medium | A hyperscaler could add deterministic authorization to its managed agent. Ugence's lead is depth (cross-domain ACP, non-compensatory determinism), not permanence. |

**Most dangerous assumption:** that "same intent" yields "same proposal" (FF1). It does not; only "same actuation" does. Any positioning that promises intent-level equivalence will be falsified in the first real deployment with heterogeneous tools. The honest claim is **actuation-level equivalence on a shared surface** — which is achievable and is what to promise.

---

## Deliverable 11 — Executive Verdict

# `PARTIALLY_SUPPORTED`

**Why not STRONGLY/SUPPORTED:** the hypothesis *as literally stated* — "any runtime, the *same* proposal, unconditionally" — is falsified by FF1 (same-ID needs same actuation, not same intent), FF2 (free-form code isn't canonicalizable at plan level), and FF3 (managed runtimes need a return-control seam). These are real, named limits, not hand-waving.

**Why not REJECT/PARTIALLY-only-negative:** every limit is an **interception-boundary or actuation-surface condition**, not a coupling *inside* the Control Plane — and the second half of the hypothesis (the Control Plane is runtime-independent) is **strongly proven** by repository evidence (FF5: zero runtime imports, generic reader seam, cross-domain reuse). The conditioned form — *"any runtime can emit an equivalent proposal via an adapter at the actuation boundary, and the Control Plane governs it identically"* — holds.

**Would I recommend making Execution Proposal the official interface contract between every AI runtime and the Ugence AI Control Plane?**

**RECOMMENDATION — YES, adopt it — with three non-negotiable disciplines baked into the spec:**
1. **Actuation-boundary interception, not plan-level.** The proposal is produced at the tool/API call the runtime actually makes (del. 3), so free-form and managed runtimes are handled at the point of a concrete call.
2. **Actuation-identity, provenance-excluded.** The ID is a pure function of the action; runtime/model/objective are metadata (del. 5, K8).
3. **Honest scope in the promise.** Market "equivalence at the actuation boundary on a shared surface," never "same proposal for same intent" (K1/FF1).

The alternative — per-runtime bespoke governance — is strictly worse: it forfeits the runtime-independence the code already exhibits and forgoes the standard-ownership moat (del. 7). The contract is the right bet; the milestone's job was to ensure it is adopted with its true conditions stated, not with a false universality claim. **PARTIALLY_SUPPORTED, adopt with conditions, and run the del. 9 experiment to move it to SUPPORTED.**
