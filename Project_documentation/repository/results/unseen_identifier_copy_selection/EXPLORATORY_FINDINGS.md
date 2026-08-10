# Exploratory failure analysis — unseen identifiers (NON-FINAL, not preregistered)

**Status:** exploratory only. Development seeds 9071–9073 (already-authorized phase); no new seed
consumed; no frozen code changed. **Not** a capability verdict; the development phase remains
`DEVELOPMENT_SHORTCUT_BLOCKED`. Interpret as hypothesis-forming, not evidence.

## What was measured
Pooled over dev seeds 9071–9073, on answer-expected items (C1–C7), seen vs unseen cohort:
error categories; a memorize-vs-copy bucketing of every valid output; per-character-position
accuracy; and a live attention snapshot (seed 9071, regenerated deterministically).

## Findings
**1. It is NOT memorizing training codes, and NOT grabbing wrong codes from context.**
On unseen inputs, of all outputs: correct copy 2.4%, wrong-code-from-context 0.1%,
memorized-training-code 3.0%, **fabricated brand-new code 94.4%**, malformed 0.2%.
(Seen cohort: 51.2% correct, 48.0% fabricated-novel, 0.8% memorized, 0% wrong-from-context.)
→ The failure mode is **fabricating plausible-but-wrong novel codes**, not regurgitating memorized
identifiers and not mis-selecting a visible candidate.

**2. It partially copies — the first character survives, then it drifts.**
Per-position exact character accuracy (chance = 1/36 = 2.8%):
| cohort | char1 | char2 | char3 | char4 |
|---|---|---|---|---|
| seen | 91.6% | 79.5% | 66.7% | 58.2% |
| unseen | **48.7%** | 19.2% | 13.0% | 10.2% |
→ On unseen, char1 (48.7%) is ~17× chance — the copy mechanism engages — but faithfulness collapses
across the remaining characters.

**3. Attention is NOT the bottleneck — localization already works, equally on unseen.**
On C1 direct-copy, the output position concentrates **0.514 (seen) / 0.520 (unseen)** of its attention
mass on the exact target tokens it must copy — ~**5.7× uniform** (uniform ≈ 0.091 over a 44-token
prompt), and essentially **identical** for seen and unseen.
→ The model knows *where* to look on novel codes just as well as on familiar ones. The failure is
**downstream of attention**, in the readout/transcription pathway that turns "attending to these
tokens" into "emit these exact tokens."

## Interpretation (bounded)
The bottleneck is **faithful copy/readout of novel token sequences**, not retrieval (attention is
correct) and not raw memorization (it does not echo training codes). The output/value circuit
reproduces the *shape* of a valid identifier and often the first character, but cannot transcribe an
unseen 4-character identity exactly.

**Implication for the architecture decision:** because the hard part — localizing the answer in
context — already works, a **single bounded copy/pointer-style readout** (emit the attended token
directly) has a clear mechanistic rationale and is the natural first intervention to test. This is
*not* authorized here; per protocol-lock Decision 12 it would be a **separate, newly-preregistered,
separately-authorized program** (one intervention, then a fresh diagnostic), and only after the
shortcut gate is resolved (the queued "Option B" threshold fix).

This exploratory note authorizes nothing and changes no standing invariant.
