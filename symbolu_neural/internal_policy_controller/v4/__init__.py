"""internal_policy_controller v4 — high-fidelity translator.

v3 established a gate-valid result but its `translate()` was a BOTTLENECK: it compressed
the rich Symbol-U state into ~4.4 bits of generic English (distributions -> argmax,
continuous -> 2-3 buckets), so 66% of every prompt was identical to its label-scrambled
version. A quality null vs relabeled/generic controls therefore tested the *translator*,
not the *ontology*.

v4 keeps v3's state computation, controls, and the gate-validated pairwise harness, and
replaces ONLY the translator with one that preserves information:
  * full distributions verbalized as top-2/3 components WITH probabilities,
  * continuous resonance/aspect/valence-sign carried as actual numbers,
  * ontology-named, magnitude-graded policy text,
so that scrambling the labels changes far more than 34% of the prompt. Then we re-run
the same gate-valid pairwise test — now it speaks to Symbol-U, not to a lossy encoding.
"""
