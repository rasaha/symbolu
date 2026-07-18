# CG Research Plan — Fix-or-Falsify the Sovereign-State Signal

> **Product path moved.** The Agentic Framework governance product path is now
> [`AGENTIC_FRAMEWORK_TRUST_OBSERVABLE_ARCHITECTURE.md`](AGENTIC_FRAMEWORK_TRUST_OBSERVABLE_ARCHITECTURE.md)
> (supervised, evidence-gated trust observables). This document remains the **research track**.
> Current CG read-outs (Vritti/Guna/Kosha/JEPA) are **research-only / off by default**, and any
> future CG-derived signal must pass that doc's **evidence gate** before entering the product.

**Status:** CG (the 32-D "sovereign-state" model-internal signal) is **demoted to research-only**
and is OFF the product decision path (`SignalConfig.enable_cg_state_signals=False`). This
document is the plan to either make CG *earn* its way back, or kill it cleanly. It is **not** a
product dependency. Ship raw entropy + the governance control plane now (see §6); pursue CG as a
moonshot in parallel.

**What we know (two independent experiments, same direction):**
- Fair-baseline pilot: with a real verbalized-confidence baseline, C4 (internal signals) ≈ C3
  (Δ=+0.022, p=0.18); `vritti_risk` standalone AUROC = 0.500 (dead).
- Fastest falsification (confident-but-unsafe fabrication, fooled subset, N=12): **raw
  next-token entropy AUROC = 0.857**, but the **32-D CG-state entropy = 0.457 (anti-predictive)**
  and `internal_risk` = 0.600. Verdict: `DEPRIORITIZE_CG_PROJECTION` — the *idea* (internal
  uncertainty catches confident hallucination) holds via **free raw entropy**; the **CG
  apparatus destroys the signal that is free in the logits it wraps.**

---

## 1. Failure hypothesis — which layer failed

The signal that works (raw next-token predictive entropy) is present at the **logit** level and
is destroyed somewhere on the way to a governance decision. Ranked by likelihood:

| Layer | Verdict | Why |
|---|---|---|
| **raw logits** | **Not the failure** | Raw predictive entropy = 0.857 on the fooled subset. The signal is here. |
| **hidden states** | Probably intact | Hidden → logits via the LM head, so the final hidden carries the predictive-uncertainty signal. Unprobed — diagnostic D1 confirms. |
| **hidden → 32-D projection** (`SovereignStateProjector`, `mistral_wrapper.py`) | **PRIME SUSPECT** | A 4096→32 semantic-categorical bottleneck (Bhava-12 softmax + Vritti-5 softmax + Guna-6 sigmoid + reserved). Trained on LM + CG-internal losses that **never reward preserving predictive uncertainty**. Step-500 diagnostics showed **mode collapse** (Bhava one-hot, entropy 0.009/2.485). A collapsed, governance-blind bottleneck cannot carry the signal. |
| **CG entropy** (`entropy_from_sovereign_state`) | **PRIME SUSPECT (conceptual)** | This computes entropy **over the 32-D semantic state**, which is a *different quantity* from predictive entropy over the vocabulary. Even a perfect projector could yield a state-entropy orthogonal to next-token uncertainty. The −0.04-from-chance (0.457) is consistent with "measuring the wrong thing." **"CG entropy" was never predictive entropy.** |
| **vritti mapping** (`vritti_from_sovereign_state`) | **Dead** | Near-uniform (1.556/1.609) and AUROC 0.500 in every run. Either the projector never learns a discriminative vritti, or vritti does not map to a governance-relevant axis, or there is no supervision tying it to safe/unsafe. |
| **JEPA / coherence** | Partial signal | Pilot standalone: jepa 0.700, coherence 0.684 — these carry *some* info, then get diluted. Not the primary failure. |
| **gateway weighting** | Amplifier, not root cause | Equal-weight averaging dilutes the 1–2 informative components with the dead ones (vritti/coherence). Real fix needs fitted weights, but weighting cannot rescue a dead state. |

**Primary hypothesis:** the 32-D semantic bottleneck **plus** the state-entropy *definition*
jointly destroy the predictive-uncertainty signal — the projection compresses it away and is
mode-collapsed, and "CG entropy" measures semantic-state spread, not next-token uncertainty. The
state is trained with **no governance-discriminative objective**, so it never learns to separate
safe from confident-unsafe.

---

## 2. Diagnostic plan — isolate the failure

All diagnostics reuse the **paired confident-unsafe benchmark** (`experiments/signal_gov/`,
fabrication + injection arms) and **conditional-on-fooled** scoring. Build them as a read-only
probe study over cached forward passes (no retraining).

- **D1 — Signal-survival ladder (the decisive diagnostic).** For each scenario cache: raw logits,
  hidden states (all layers), the 32-D state. On the **fooled subset**, report AUROC of:
  (a) raw predictive entropy [ceiling ≈ 0.857]; (b) a *linear probe* on the final hidden state;
  (c) a linear probe on the 32-D state; (d) `entropy_from_sovereign_state`; (e) vritti / coherence
  / jepa standalone. **The AUROC drop localizes the failure:** if (b)≈0.85 but (c)≪0.85 → the
  *projection* destroys it; if (c)≈0.85 but (d)≪0.85 → the *entropy definition* is wrong (info is
  in the state, the metric doesn't extract it).
- **D2 — Layerwise hidden probes.** Probe predictive-uncertainty decodability at early/mid/late
  layers → which layer the projector *should* read from (it may be reading the wrong depth).
- **D3 — State-dimension sweep.** Re-fit probes on 32-D vs 64-D vs 128-D states. If 128≫32, the
  bottleneck is too tight; if all ≪ raw, dimension is not the issue (objective is).
- **D4 — Vritti collapse analysis.** Per-component (Bhava/Vritti/Guna) distribution entropy across
  the benchmark and **across safe vs unsafe twins**. Quantify mode collapse and whether *any*
  component varies *informatively* between twins.
- **D5 — Entropy-definition correlation.** Direct correlation of predictive entropy vs
  `entropy_from_sovereign_state`. Confirm/quantify the near-zero/negative correlation. If
  near-zero, the metric is conceptually wrong, not just undertrained.
- **D6 — JEPA/coherence standalone, conditional.** Re-measure jepa/coherence on the fooled subset;
  do they add *over raw entropy* (the only thing that matters for promotion)?

**Exit:** D1 alone decides whether the fault is the *projection* (fix with training/dimension) or
the *entropy definition* (fix by reading predictive uncertainty into the state, not state spread).

---

## 3. Retraining plan — make the state carry governance signal

The root cause is an **objective problem**: the CG head is trained on LM + CG-internal losses,
none of which reward governance-discriminativeness. Add *supervised, governance-targeted*
objectives (only pursue the ones D1–D6 implicate):

- **R1 — Raw-entropy preservation (auxiliary loss).** Supervise a state dimension / readout head
  to **regress the true next-token predictive entropy**. Guarantees the working signal survives
  into the state. Directly targets the "projection destroys it" failure. *Cheapest, highest-value.*
- **R2 — Contrastive safe-vs-confident-unsafe (the key objective).** Using surface-matched twins,
  a contrastive/triplet loss that pushes the state (and governance signals) of **unsafe twins away
  from safe twins**. This is what is missing: the state is never trained to separate the
  governance axis, only to be LM-coherent.
- **R3 — Fabrication/hallucinated-permission supervision.** Explicit labels + a head supervised to
  fire on hallucinated-tool / fabricated-capability cases (entropy's home turf).
- **R4 — Escalation calibration loss.** A proper scoring rule on the escalate/not-escalate decision
  vs the oracle on a held-out split → calibrated, not just ranked.
- **R5 — Vritti: supervise or remove.** Either give vritti *explicit* supervision (a defensible
  target distribution per scenario) **or remove it from the governance path.** It is dead in every
  experiment; do not keep a dead 5-D subsystem in any product-facing path.
- **R6 — Anti-collapse regularization** (entropy reg on Bhava; earlier gate unfreeze; higher
  CG-loss weight) — **only** alongside R1/R2; regularizing a governance-blind state just preserves
  noise.

Sequencing: **R1 + R2 first** (preserve the signal + train discriminativeness), re-run the
falsification conditionally, then add R3/R4 and revisit R5/R6 based on D4.

---

## 4. Promotion gate — when CG returns to product positioning

CG re-enters product positioning **iff**, on a **held-out, powered (N≥150), paired
confident-unsafe benchmark**, the CG-derived governance signal **beats**

> risk taxonomy + verbalized confidence + **raw next-token entropy**

on the **fooled-subset conditional AUROC**, with:
1. **DeLong p < 0.05, replicated** on a second independent draw;
2. **Marginal value over raw entropy specifically** — CG must catch what predictive entropy
   *misses* (a hidden-state fabrication/injection signature), not merely re-derive raw entropy
   through a 32-D detour. *Re-deriving the cheap signal is not promotion.*
3. **Operational lift** — higher catch@budget at equal or lower over-blocking, not just AUROC.

Until all three hold, `enable_cg_state_signals` stays `False` and CG stays research-only.

---

## 5. Stop / Keep

**Stop doing:**
- Treating "CG entropy" as if it were predictive entropy — they are different objects.
- Equal-weight averaging that dilutes 1–2 informative signals with dead ones.
- Training the CG head with **no** governance-discriminative supervision.
- Carrying the dead **vritti** subsystem on any product path without real supervision.
- **Blocking product on CG.** It is off by default; keep it off until §4 is met.

**Keep:**
- **Raw next-token entropy** as the first-class product signal (it works).
- The **confidence-risk gap** + the governance **control plane** (the product).
- The CG **architecture as a research substrate** (frozen backbone + trainable head is a fine
  scaffold; the *objective* was wrong, not necessarily the scaffold).
- The **conditional-on-fooled methodology** and the **paired confident-unsafe benchmark** (correct
  evaluation + test bed).
- **JEPA/coherence** as candidate signals worth checking for value *over* raw entropy (D6).
- The **option value**: if CG ever clears §4, it is a real moat. Worth a moonshot, not a blocker.

---

## 6. Product roadmap stays separate

- **Now (product):** raw next-token entropy as the default uncertainty signal; the confidence-risk
  gap in the execution path; risk taxonomy + approvals + audit + budget — the model-agnostic
  governance/audit control plane. No CG dependency.
- **Parallel (research):** D1–D6 → R1/R2 → re-falsify → §4 gate. CG returns to the product story
  *only* by clearing the gate, on the evidence, against the cheap baseline.

---

## Appendix — next-session kickoff prompt

> CG is research-only and off the product path. Per `AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md`,
> start the **fix-or-falsify** work. First, implement **Diagnostic D1 — the signal-survival
> ladder** as an isolated, read-only probe study reusing `experiments/signal_gov/` (the paired
> confident-unsafe benchmark + conditional-on-fooled scoring): for each scenario, cache raw
> logits, all-layer hidden states, and the 32-D sovereign state from one forward pass; then on the
> **fooled subset** report AUROC for (a) raw predictive entropy, (b) a linear probe on the final
> hidden state, (c) a linear probe on the 32-D state, (d) `entropy_from_sovereign_state`, (e)
> vritti/coherence/jepa standalone. Localize where AUROC falls from ~0.857 to ~0.46. Do not retrain
> yet, do not touch the product gateway path, and make no success claim — the output is a
> localization verdict (projection vs entropy-definition) that selects R1/R2. Then propose the
> minimal training change (R1 raw-entropy-preservation and/or R2 contrastive safe-vs-unsafe) and
> the held-out promotion test from §4.
