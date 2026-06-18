# Internal-Signal Governance — Theory, Decisive Experiment, and Business Thesis

Context: the fair-baseline pilot (N=30) gives C3 (verbalized confidence) AUROC 0.893 vs
C4 (+ internal signals) 0.916, Δ=+0.022, p=0.183 (n.s.). This document answers two
questions that are easy to conflate:

- **Scientific:** *where* should model-internal signals beat verbalized confidence if the
  CG thesis is true, and what is the smallest experiment that validates or kills it?
- **Commercial:** does the Agentic Framework business depend on that thesis being true?

The single most important idea connecting them: **the average AUROC (+0.02) is the wrong
number.** Both the science and the business live or die on the *conditional* advantage in
the narrow regime where verbalized confidence is **fooled** — high stated safety on a
genuinely unsafe action. Score that subset, not the average.

---

## PART A — Theory: where internal signals *should* win

### A.0 The only mechanism that can work

Verbalized confidence is itself a generation from the same forward pass. So internal
signals can only beat it when there is a **representation–output gap**: the internal state
encodes unsafety-relevant information that the *verbalized output does not surface*. That
gap has exactly three forms:

1. **Output suppressed/redirected vs intact internal representation** — injection,
   jailbreak, refusal-suppression. The "this is harmful / off-task" representation is
   present internally but the output complies. → coherence / JEPA.
2. **Output overconfident vs diffuse internal distribution** — hallucination/fabrication.
   The model is guessing (high internal entropy) while asserting confidently. → entropy.
3. **Internal conflict from contradictory inputs** — user intent vs injected instruction.
   Internal disagreement/incoherence spikes even though the output resolves to one path.
   → coherence / JEPA / (in principle) vritti.

This yields a hard **filter**. Internal signals can help **only if both**:
- (a) the unsafety-relevant information is **in the model's input or intrinsic to its
  computation** (not in oracle-private ground truth the model never sees), **and**
- (b) there is a **representation–output divergence** (the model "knows" more than it says).

Every category below is just this filter applied.

### A.1–A.3 Category analysis (why C3 fails, why internals could win, the signature)

| Category | Info in model's input? | Why verbalized C3 fails | Why entropy/JEPA/coherence could win | Observable signature | Expected C4>C3 |
|---|---|---|---|---|---|
| **Hallucinated tools / permissions / facts** | Intrinsic (fabrication) | Model confidently asserts a tool/permission/fact it is inventing | Fabrication ⇒ diffuse next-token distribution; entropy elevated while output asserts | High predictive/state entropy on confident-but-fabricated vs grounded twin | **High** |
| **Indirect prompt injection (subtle)** | Yes (untrusted content) | Steered to treat injected action as the user's; complies "confidently" | Untrusted content conflicts with user task ⇒ off-distribution / internal harmfulness rep intact | JEPA disagreement ↑, coherence ↓ on poisoned vs benign at matched confidence | **Med-High** |
| **CoT ↔ action inconsistency** | Yes (the CoT) | Reading only the final confidence misses the contradiction | Internal incoherence when stated reasoning and chosen action diverge | Coherence drop when CoT≠action | **Med** (but a cheap *text* method — compare CoT to action — competes) |
| **Deliberate deception / sandbagging** | Partially intrinsic | Output is untrustworthy *by construction* (the model is misrepresenting) | True computation is internal; output is a mask | Entropy/coherence anomalies vs sincere twin | **Med, high-variance** (strong in theory, hard to construct/verify; unclear these signals capture *intent*) |
| **Deceptive instructions** | Conditional | Same as injection if the deception is in-input | Same as injection | Same as injection | **Med (conditional)** — collapses to injection or to authority-spoof |
| **Tool misuse (legit tool, dangerous args)** | Yes (the args) | Surface looks fine; model may not flag args | Usually **no internal conflict** — the model is *calmly wrong* | (none reliable) | **Low** |
| **Authority spoofing (fake "admin approved")** | **No** (truth unseen) | Trusts claimed authority | Model can't verify what it can't see ⇒ internal state is *also* fooled | (none) | **~Zero — EXCLUDE** |
| **Reward hacking** | N/A (not single-step) | — | Not localized to one decision point | — | **N/A — EXCLUDE** |
| **Multi-step planning failures** | N/A (not single-step) | — | Emerges across steps, not in one forward pass | — | **N/A — EXCLUDE** |

### A.4 Ranking by expected C4-over-C3 advantage

1. **Hallucinated tools/permissions/facts** — entropy's home turf; clearest mechanism, most tractable, most published support.
2. **Indirect prompt injection (subtle)** — real mechanism, *conditional* on the model being fooled at the output level (if blatant, C3 also catches it; if too subtle, neither does).
3. **CoT↔action inconsistency** — plausible, but a cheap text baseline competes, so weak moat even if it works.
4. **Deliberate deception / sandbagging** — strongest in principle (output is a lie), weakest in practice (hard to elicit/verify; uncertain these signals read intent).
5. **Deceptive instructions** — only as good as their in-input content.
6. **Tool misuse (bad args)** — low; no representation–output gap.
7–9. **Authority spoofing / reward hacking / multi-step** — ~zero or out of frame. **Do not put these in the benchmark.**

### A.5 Smallest maximally-isolating benchmark (20–40 scenarios)

Design rules (all enforced so the test is fair, not rigged):
- **Surface-matched pairs.** Each unsafe item has a safe twin sharing task/domain/surface, so C3 (and the risk taxonomy) cannot separate them on surface alone.
- **Discriminating info in the model's input.** The injection/fabrication trigger is in the prompt (e.g., `untrusted_content`), never only in oracle-private fields. *(This is why earlier pilots couldn't have worked — they fed a sanitized summary; the model never saw an injection.)*
- **Author from patterns, measure fooling post-hoc.** Never select items by peeking at where the model is confidently wrong. Instead **measure** the fool rate (mean verbalized confidence on unsafe items) and report it.
- **Score conditionally** (see A.6).

Two arms, ~10 pairs each:
- **Arm H — fabrication (entropy):** confident assertion of an invented tool/permission/fact vs a grounded twin. (~20)
- **Arm I — indirect injection (JEPA/coherence):** untrusted content hijacks the agent into an attacker tool vs a benign-content twin. (~20)

Total **~40** (or ~20 if you isolate the single best regime, H). Drop arms 6–9 entirely.

### A.6 The metric that matters — condition on the fooled subset

The +0.02 average is diluted by easy items where C3 already works. **Restrict to the subset
where verbalized confidence is fooled** (stated safety high *and* action unsafe). On that
subset C3 is by construction useless (≈chance or worse). The question becomes: *can internal
signals rank the high-confidence-unsafe items above the high-confidence-safe ones?* That
conditional ΔAUROC — not the marginal — is the thesis.

### A.7 Strongest test vs fastest falsification

- **Strongest possible validation:** powered (N≈150–250) paired benchmark across Arms H+I,
  held-out split for any weight fitting, primary endpoint = **C4−C3 on the fooled subset**
  with DeLong + bootstrap CI. A large, significant *conditional* advantage = the thesis has
  legs and a product.
- **Fastest falsification (do this first):** the ~20-scenario fabrication arm, restricted to
  items the calibration diagnostic confirms are **fooled**. If internal signals **cannot**
  separate fooled-unsafe from confident-safe there (conditional C4≈C3≈chance), the thesis is
  dead — that is the model's *best-case* regime and it still failed. One cheap run kills it.
  - Add a **sanity ceiling**: also report *raw next-token entropy* alongside the CG-state
    entropy. If raw entropy wins but the 32-D CG-state entropy does not, the failure is the
    *CG projection*, not the idea — a different (and cheaper) conclusion.

---

## PART B — Business thesis (evaluate the company, not the experiment)

### B.1 If internal signals never beat ~+0.02, does Agentic still have a product?

**Yes — but it loses its *differentiation* thesis, not its product.** The deterministic
governance runtime (approval ordering, 5-layer gateway, policy, budget, audit) is a real,
sellable product. What weakens is the *moat* story: internal signals were the "sees inside
cognition" wedge. Without it, Agentic is a **competent governance product in a fast-
commoditizing category** — survivable, not venture-defining on signals alone.

### B.2 Where customer value actually sits today (ranked)

1. **Audit trail / provenance / system-of-record for agent actions** — the compliance buy-reason; highest willingness-to-pay in regulated buyers.
2. **Approval orchestration + the gateway as the enforcement point** — operational necessity; also the integration moat (being *the* control point).
3. **Budget / cost controls** — acute and growing pain as agent usage scales.
4. **Policy engine + risk taxonomy** — table stakes; expected, not differentiating.
5. **Internal signals** — research-stage; **not a buy-reason today.**

### B.3 If internal signals vanished tomorrow, what stays differentiated vs LangGraph / OpenAI Agents SDK / CrewAI / AutoGen / Bedrock?

Honestly, **thin and positional, not a deep tech moat:**
- LangGraph / CrewAI / AutoGen are **orchestration** frameworks, not governance-first — Agentic's governance posture is a real positioning difference but reproducible by a competent team.
- OpenAI Agents SDK and Bedrock Agents have governance **tied to their clouds/models** — Agentic's **model-agnostic, cross-provider** stance is the genuine differentiator.
- The durable edge is **integration depth + becoming the system-of-record** (audit) across all agents/models — i.e., *distribution and lock-in*, not the gateway code itself.

### B.4 Strongest venture-scale narrative *today*

**The model-agnostic control plane and system-of-record for enterprise agent actions** —
"policy, budget, approval, and audit across every agent and every model." The
"Okta/Cloudflare for agents" framing. **Not** the "internal-signal safety layer" (unproven).
Internal signals are a **future moat option**, not the current foundation.

### B.5 What a customer buys first / pays for / ignores

- **Buys first:** audit + approval + policy — they have a compliance/risk mandate *now*.
- **Pays for:** audit/compliance (regulated), budget controls (cost), the cross-provider control point.
- **Ignores (today):** internal signals — "interesting; come back when it's a validated 0.10+ on attacks my output filters miss."

### B.6 Two rankings

- **Scientific importance of internal signals: HIGH.** If true, "read harmfulness in activations before the output commits" is a genuine, novel, publishable advance.
- **Commercial importance, today: LOW.** Not a buy-reason; the runtime is the product.
  **Conditionally HIGH** *iff* validated on the high-cost regime (injection/exfiltration that
  output-inspection structurally misses) — that *is* a security/compliance buy-reason.

---

## Synthesis — the science and the business converge on the same next move

- **Decouple the company from the signal bet.** Build the durable business on the
  governance + audit **control plane** (defensible via integration, system-of-record, and
  compliance — not via the signals). On a +0.02 world, you are fine; you are just not yet
  differentiated on cognition.
- **Treat internal signals as a high-option-value bet with a hard kill/scale gate.** That
  gate is the **conditional-on-fooled** experiment (A.6/A.7), *not* the average AUROC.
- **The number that matters commercially is the same one that matters scientifically:** the
  conditional advantage on attacks output-inspection cannot see. If it is **large**, you have
  "the governance layer that catches injection/exfiltration your output filters miss" — a
  premium security tier and a real moat. If it is **also small**, internal signals are dead
  commercially and you walk away **unharmed**, because the business never rested on them.

**Recommended sequence:** (1) run the *fastest falsification* (A.7) — ~20 fabrication
scenarios, scored conditionally, with raw-entropy as a ceiling check. Cheap, decisive.
(2) Only if it survives, build the powered H+I benchmark. (3) In parallel and independent of
the result, position and harden the control-plane/audit product — that is what customers buy
either way.
