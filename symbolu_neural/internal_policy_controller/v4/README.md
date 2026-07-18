# Internal Policy Controller v4 — high-fidelity translator

v4 exists to answer the question v3 could not: **does the Symbol-U ontology improve
answers, or did the v3 translator just throw the ontology away?** v3 produced a
gate-valid null, but its `translate()` compressed the rich state into ~4.4 bits of
generic English (distributions → argmax, continuous → 2–3 buckets), so 66% of every
prompt was identical to its label-scrambled version and 88% identical to a generic
policy. That null tested the *translator*, not the *ontology*.

v4 keeps v3's state computation, controls, and **gate-validated pairwise harness**
(independent judge, position-debias, validity gate, bounded concurrency) and replaces
**only** the translator with one that preserves information:

- **Full distributions** (`dynamic_state`, `guna`, `kosha`) verbalized as their
  components *with probabilities* and *raw ontology names* — the distribution shape
  survives, instead of collapsing to a single argmax.
- **Continuous values** (`aspect_balance`, `guna_resonance`, `kosha_resonance`,
  `valence_sign`) carried into the prompt as the actual signed numbers, graded
  continuously — no 2–3 bucket collapse.
- **Ontology-named, magnitude-graded policy** text, so a label scramble rewrites much
  more of the prompt.

## Measured improvement (offline, `cli_v4 bottleneck`)

| metric | v3 | v4 |
|---|---|---|
| distinct prompts (of 36) | 24 | **36** |
| relabel **field** divergence (analog of v3's 34%) | 34% | **43%** |
| relabel **token** divergence (how much prompt text moves) | 10% | **21%** |
| divergence from a FIXED generic policy (higher = less generic) | 12% | **60%** |

The headline is the last row: v4 prompts are **~5× less generic** than v3's — that is
the bottleneck genuinely loosening. Relabel divergence rises too, but is **honestly
capped**: ~30% of the v4 policy is driven by continuous magnitudes (resonance/aspect)
that a label scramble *correctly* leaves unchanged. So v4 is a **fairer, not perfect**,
test of the ontology.

## Commands

```bash
export PYTHONPATH=$(pwd)
python -m symbolu_neural.internal_policy_controller.v4.cli_v4 bottleneck   # v3-vs-v4 fidelity
python -m symbolu_neural.internal_policy_controller.v4.cli_v4 state        # the rich prompts
# the real re-test (gate-valid, independent judge):
export MISTRAL_API_KEY=... ; export ANTHROPIC_API_KEY=...
python -m symbolu_neural.internal_policy_controller.v4.cli_v4 pairwise \
    --backend mistral --judge-backend anthropic --seeds 1
python symbolu_neural/internal_policy_controller/v4/tests/test_v4.py
```

## How to read the re-test

The decisive comparison is still **symbolu vs relabeled_symbolu** (does the *specific*
ontology matter?) under a **PASS**ing validity gate. Because v4 prompts now carry real
ontology-specific content (60% divergent from generic) and relabel moves more of the
prompt, this comparison finally has enough power to be informative:

- **symbolu significantly beats relabeled** → evidence the specific ontology helps.
- **tie** → even with the information preserved, the ontology adds nothing detectable —
  a much stronger null than v3's, because it is no longer confounded by the translator.

Either outcome is a real result. v4 is built so the answer is about Symbol-U, not about
a lossy encoding of it.
