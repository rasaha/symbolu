# Architectural Decision (Phase 24)

*Where does EvidenceAssurance belong, if anywhere? Decided against the frozen decision rules
(`EVALUATION_PROTOCOL.md`) and the falsification outcomes (`LIMITATIONS_AND_FALSIFICATION.md`). One
option is chosen; the rest are recorded with why they were not.*

## The eight options considered

| # | Option | Verdict |
|---|---|---|
| 1 | Ship as a standalone product / 11th canonical platform module | **No** |
| 2 | Merge wholesale into AssertionGate | **No** |
| 3 | Adopt as an **upstream evidence-verification stage feeding AssertionGate**, high-risk-gated | **Chosen** |
| 4 | Adopt the full stack everywhere, always-on | **No** |
| 5 | Adopt independence-checking only; drop the other layers | **No** |
| 6 | Keep as research only; do not adopt | **No** |
| 7 | Fold into the Model Selection / control-plane policy layer | **No** |
| 8 | Replace grounding/entailment scoring with EvidenceAssurance | **No** |

## Decision: Option 3 — an upstream, high-risk-gated evidence-verification stage feeding AssertionGate

EvidenceAssurance is adopted as a **cross-cutting evidence-verification stage that runs before
AssertionGate on high/critical-risk claims**, emitting an evidence-state disposition that the thin gate
routes on (the Phase-14 contract). It is **not** a product, **not** an 11th canonical module, and
**not** merged into AssertionGate.

This mirrors the Model Selection Policy placement decision (ADR): a cross-cutting policy/verification
service, not a new headline component — keeping the canonical ten-component platform taxonomy intact.

### Why Option 3

- **It is the safety frontier the evaluation licensed.** 0.000 correlated-failure escape at a
  noise-floor false-block, beating every signal-only baseline and the learned comparator — the exact
  bar the frozen decision rules set.
- **The contract keeps AssertionGate thin.** Evidence reasoning lives in one place; the gate stays a
  policy router (delivery-level escape 0 end-to-end). Merging (Option 2) would duplicate the
  correlated-failure logic and let it drift.
- **High-risk gating matches where the value and the cost land.** The stack costs 18 probes and its
  distinctive power (independence/provenance/counterevidence) matters most for medical/legal/financial/
  security claims. Running it always-on (Option 4) pays full cost on low-risk descriptive claims that a
  cheap check already handles.

### Deliberately scoped conditions (from the limits, not marketing)

1. **Bounded claim only.** It catches correlated failures that leave an observable tell. The no-tell
   ceiling (S23 escape = 1.000) is a shipped-with disclosure, not a footnote. It must never be sold as
   "solving correlated failure."
2. **Shadow-mode first, enforcement off.** Adoption starts in shadow (as this whole track ran):
   disposition logged, delivery unaffected, until the false-block and abstention rates are validated on
   real traffic.
3. **Missing-metadata abstention is a data-quality alarm.** Phase 16 shows abstention rising to 0.34 at
   70% missingness with escape held at 0. Rising `INDETERMINATE` must page a data pipeline, not silently
   tank availability.
4. **The full stack is the high-risk configuration; independence-first is the default elsewhere.** The
   defense-in-depth result says the extra layers buy adversarial robustness. Where provenance metadata
   is trustworthy and risk is low, independence-checking plus the non-correlated-failure layers
   (alignment/freshness) is the honest cheaper configuration — not the full 18-probe stack.
5. **No-tell residual routes to human/external verification.** The failures the component cannot see
   (H0-12) are explicitly handed to out-of-band verification, not absorbed silently.

## Why not the others

- **(1) Standalone product / 11th module** — the evaluation supports a *verification stage*, not a
  category. Inventing a module would inflate the taxonomy the platform work deliberately fixed at ten.
- **(2) Merge into AssertionGate** — breaks the thin-gate contract; duplicates evidence logic; the
  ablation shows the layers are a coherent unit better kept together upstream.
- **(4) Full stack always-on** — pays 18 probes on low-risk claims for no safety gain there; Phase 19
  shows the cheap subset suffices when metadata is trusted.
- **(5) Independence-only** — matches the headline on *this* benign corpus but escapes 0.500 under
  fabricated provenance and misses non-correlated failure states (overall escape 0.366). Adopting it
  would ship the exact trap the protocol warned against.
- **(6) Research only** — understates a real, reproduced safety gain over the deployed signal-only
  baselines; the bounded claim is deployable in shadow mode today.
- **(7) Fold into model-selection/control-plane policy** — category error; model selection chooses a
  model, EvidenceAssurance verifies evidence for a claim. Different inputs, different decision.
- **(8) Replace grounding/entailment** — those signals still do useful work on aligned-and-correct
  claims; EvidenceAssurance *layers over* them (it consumes the alignment signal), it does not replace
  them. And on its own the passage signal's 10% noise is the component's entire false-block.

## One-line statement

> Adopt EvidenceAssurance as an upstream, high-risk-gated evidence-verification stage feeding a thin
> AssertionGate — in shadow mode, with a bounded claim, an abstention-as-alarm contract, and the
> no-tell residual routed to external verification. Not a product, not an 11th module, not a merge.
