# Agentic Framework — Founder Notes (internal companion to the VC brief)

*Version 1.10.0 — June 2026. Internal. Candid companion to `AGENTIC_FRAMEWORK_VC_BRIEF.md`.*

This document is for us, not investors. It records what the signal experiments taught us, why
the company no longer depends on the CG (sovereign-state) thesis succeeding, and a claim-by-claim
audit of the external brief so every external sentence is backed by evidence.

---

## 1. Lessons learned from the falsification experiments

We began with a moat thesis: **model-internal "sovereign-state" signals (the 32-D CG state —
entropy/vritti/JEPA) would let governance "see inside cognition" in a way wrappers on closed APIs
cannot.** We tested it honestly, and it did not survive contact with evidence. Three experiments:

1. **Real CG checkpoint pilot.** Trained a real CG head (Mistral-7B backbone + sovereign-state
   head) and ran it through the signal harness. **Vritti was dead** (standalone AUROC 0.500);
   the combined internal-signal config barely edged the confidence baseline.
2. **Fair-baseline pilot.** The earlier edge was partly an artifact: C3 used a *constant 0.5
   placeholder* for verbalized confidence. With a **real** verbalized-confidence baseline, the
   internal signals' advantage collapsed to **ΔAUROC ≈ +0.02, p ≈ 0.18 (n.s.)**. The model's own
   verbalized safety judgment already captured most of the signal.
3. **Fastest falsification.** In the *best-case* regime for internal signals (confident-but-unsafe
   fabrication, scored on the fooled subset), **raw next-token entropy won (AUROC 0.857)** while
   the trained **32-D CG-state entropy was anti-predictive (0.457)**. Verdict:
   `DEPRIORITIZE_CG_PROJECTION`.

**Methodological lessons (the transferable ones):**
- **Score conditionally, not marginally.** The marginal AUROC hid the truth; restricting to the
  subset where verbalized confidence is *fooled* exposed it. The +0.02 average was the wrong number.
- **Fair baselines or nothing.** A placeholder baseline inflated the apparent moat. The single
  most important fix was making C3 a *real* baseline.
- **"CG entropy" ≠ predictive entropy.** The CG architecture computes entropy over a 32-D semantic
  state — a different object from next-token predictive entropy. The hallucination signal lives in
  the latter; the CG metric measures the former. A category error baked into the design.
- **The working signal was free in the logits the CG head wraps.** Raw entropy needs no training,
  no 32-D state, no framework. The CG projection *destroyed* a signal that was already free.

**Honest one-liner:** across two independent experiments, the CG apparatus does not earn its
complexity; it was beaten by a one-line `entropy(logits)` in its best-case regime.

---

## 2. Why the company no longer depends on CG signals succeeding

We **decoupled the company from the signal bet** — deliberately, and it is the right call:

- **The durable business is the governance control plane**, not CG: pinned `cancel → budget →
  approve → execute` enforcement, per-tool risk classification, runtime approvals, hard budget
  caps, and a replayable `AgentRunTrace` the customer owns. These are tested, real, and the
  compliance buy-reason — **independent of any model-internal signal.**
- **We shipped the cheap signal that works.** Raw next-token entropy + the confidence-risk gap are
  live in the execution path (provider-agnostic, no proprietary claim). That is a real feature on
  the control-plane foundation.
- **CG is now a research track with a hard promotion gate.** It returns to product positioning
  *only* if it beats risk taxonomy + verbalized confidence + raw entropy on a held-out
  confident-unsafe benchmark — and adds value *over* raw entropy specifically, not by re-deriving
  it. (See `AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md`.)

**The asymmetry that makes this safe:**
- If CG **never** works → we lose a *differentiation story*, not a product. The control plane stands.
- If CG **does** work → genuine upside (a security moat: catching attacks output-inspection misses).
  But it is **option value, not foundation.**

So the company's value no longer rides on whether entropy-from-a-32D-state beats verbalized
confidence by 0.02 vs 0.10. That is the point of the rewrite.

---

## 3. Full claim audit of the external brief

Every external claim, classified: **MEASURED** (repo/CI or our experiments) · **DIRECTIONAL**
(plausible, reasoned, not established at power) · **RESEARCH** (open question, off product path).

| # | Claim in the brief | Class | Backing / note |
|---|---|---|---|
| 1 | Agent frameworks made tool-calling easy; the governance seam is the hard part | DIRECTIONAL | Market observation + design-partner reports |
| 2 | Enterprise pilots stall on trust/audit/approval/spend, not model quality | DIRECTIONAL | Design-partner anecdote; not a survey |
| 3 | `cancel → budget → approve → execute` is a runtime invariant pinned by tests | **MEASURED** | Test suite |
| 4 | SafetyGate (turn) + SafeMCPGateway (per-call) two-layer governance | **MEASURED** | Implemented + tested |
| 5 | Per-tool risk levels enforced at call time; LLM cannot route around | **MEASURED** | Gateway + tests |
| 6 | Raw next-token entropy ingested in the execution path (confidence-risk gap) | **MEASURED** (wiring) | End-to-end validated + unit tests + negative control |
| 7 | The gap *improves governance outcomes* | **DIRECTIONAL** | Mechanism validated; operational value not yet powered |
| 8 | CG 32-D sovereign-state signals (entropy/vritti/JEPA) | **RESEARCH** | Off by default; falsified vs raw entropy this cycle |
| 9 | Raw entropy is the strongest measured uncertainty signal | **MEASURED** | Fooled-subset AUROC 0.857 > all alternatives |
| 10 | Vritti / JEPA / coherence are validated governance signals | **REMOVED** | Vritti 0.500 dead; JEPA/coherence no value over raw entropy |
| 11 | `build_agent()` composes the full stack; mock↔real swap, no rewiring | **MEASURED** | Repo + live-adapter validation |
| 12 | Competitive positioning vs each family (guardrails, observability, etc.) | **DIRECTIONAL** | Reasoned, not third-party benchmarked |
| 13 | Feature comparison table (our column) | **MEASURED** | We ship these primitives |
| 14 | Feature comparison table (competitor columns) | **DIRECTIONAL** | Public-knowledge characterization |
| 15 | Primary moat: control plane / enforcement / audit-SoR / portability | **MEASURED** | Tested runtime properties |
| 16 | Secondary optionality: model-internal signals (raw entropy today) | **MEASURED** (feature) | Shipped; explicitly *not* a moat |
| 17 | Secondary optionality: CG sovereign-state as future upside | **RESEARCH** | Gated on held-out promotion test |
| 18 | 1,550+ tests, primitive test counts, live-adapter 3/3, 2 pilots | **MEASURED** | Repo/CI snapshots |
| 19 | Three internal signal experiments completed; results as stated | **MEASURED** | Pilot + fair-baseline + falsification artifacts |
| 20 | 12-month roadmap items (pilots, console, managed, multi-agent, SOC 2) | **DIRECTIONAL** | Plans, not commitments |

**Removed / downgraded this cycle (do not reintroduce without evidence):**
- "Signal enrichment from model-internal state is a *category of one* / *differentiated*."
- "CG signals enable signal-enriched governance *by default*."
- Any wording implying **vritti is validated**, **JEPA/coherence outperform** simpler signals, or
  the CG sovereign-state is a **proven** or **proprietary** commercial moat.

**Standing rule:** a claim ships externally only at **MEASURED**, or at **DIRECTIONAL** with hedge
language ("we observe", "design partners report"). **RESEARCH** items are described as research,
off by default, gated — never as product differentiation.

---

## 4. What this buys us with investors

The narrative is *stronger*, not weaker, because it is defensible under diligence:
- We can show the tested invariant, the audit trace, and a working raw-entropy escalation **today**.
- We pre-empt the "is the AI-moat real?" question by having *already run the falsification ourselves*
  and priced the company so it doesn't depend on the answer.
- CG becomes a credible **moonshot with a hard gate** — upside an investor can underwrite without
  betting the round on it.
