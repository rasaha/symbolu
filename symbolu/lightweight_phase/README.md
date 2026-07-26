# Lightweight Phase Transformer — canonical research reference

A small, independently importable, auditable, dependency-light (torch only)
implementation of Phase attention. Built from scratch against
`docs/PHASE_QUAD_LOCAL_ATTENTION_ALGORITHM.md` and the production
`PhaseAttentionLayer` (reference only — never copied). **This is the canonical
research implementation; production layers must prove equivalence against it.**

Excluded by contract: quadratic attention, Top-K/Quad retrieval, the production
`BindingCacheQuadQuery`, controllers, governance, and ontological systems.

## Layout

```
config.py            typed frozen configuration + hashes
phase_core.py        LightweightPhaseAttention, PhaseState, PhaseOutput, step()
streaming.py         chunked scan + streaming-equivalence helpers
local_window.py      O(N·W) causal sliding window (no N×N)
phase_block.py       Phase Transformer block + LM (tied embeds, state cache)
binding_slots.py     bounded, streaming binding slots (O(M·D) state)
diagnostics.py       read-only metrics
invariants.py        runtime no-two-sequence-axis + O(D)-state contracts
equivalence.py       adapter to production PhaseAttentionLayer
training.py          Stage 7 A/B distant-recall harness
freeze.py            reproducibility command + freeze gate
reference_equations.md   frozen mathematics
frozen_manifest.json     source/config hashes, golden fingerprints, env
golden_vectors.pt        frozen golden tensors
reports/                 one report per stage
tests/                   98 tests
```

## Reproduce / verify the freeze

```
python -m symbolu.lightweight_phase.freeze          # verify goldens + source hashes
python -m pytest symbolu/lightweight_phase/tests    # 98 tests
```

## Stages (each independently frozen)

| Version | Stage | Status |
|---|---|---|
| v1.0 | Phase Core | FROZEN |
| v1.1 | Streaming Phase | FROZEN |
| v1.2 | Decay Phase | FROZEN |
| v1.3 | Phase Transformer | FROZEN |
| v1.4 | Local + Phase | FROZEN (Stage 6); Stage 7 A/B demonstrated, full study deferred |
| v1.5 | Phase + Binding | structure/complexity FROZEN; validation ladder deferred |

See `reports/FINAL_SUMMARY.md` for the consolidated result.

## Freeze discipline

Any change to frozen behavior requires: a version increment, a migration note, an
equivalence-impact statement, new golden vectors (`freeze --write`), and a re-run
of downstream experiments. Do not modify frozen behavior silently — the golden
gate (`tests/test_golden.py`) fails on drift.
