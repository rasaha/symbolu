# Authorized fidelity correction — H2 loop mask handling

## Defect

The H2 arm uses a dedicated training loop (it cannot be a single-function swap because it needs a
step-600 teacher snapshot + an added distillation term). That loop was intended to copy the frozen
reference loop (`stabilize.run_arm`) byte-for-byte through step 600. It **omitted one line**: the
`if mask is None:` branch that the reference loop has at `stabilize.py:138`. In curriculum phase 3
(steps ≥ 700, the ABC_MIX handoff), `curriculum_batch` returns `mask=None`, so H2 crashed at the
handoff:

```
persistence_arms.py: sel = mask.reshape(-1)  ->  AttributeError: 'NoneType' object has no attribute 'reshape'
```

## Discovery

Discovered when the adaptive driver reached **H2 seed23** (order 16), after the mandatory reference
block (A+ ×5, R0 ×5) and the futile candidates **O1R** (1 clean, 2 quality-failed) and **H1** (1
clean, 1 causally-unclean, 1 quality-failed) had all completed validly. The crash occurred **before**
any H2 artifact was persisted, so **no H2 output existed** and **nothing was discarded**.

## Protocol handling

Merged protocol §6 requires stopping with `PERSISTENCE_PROTOCOL_VIOLATED` on a behavior-affecting
implementation defect discovered after reserved-seed execution begins, and prohibits patch-and-continue
**without a separate authorization**. The defect was surfaced to the authorizing user, who **explicitly
authorized** a scoped fidelity correction + resume (option "Authorize corrected H2 resume").

## The correction

Add the `mask=None` branch to the H2 loop, identical to the frozen reference loop:

```python
if mask is None:
    main = F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1))
else:
    sel = mask.reshape(-1)
    main = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
```

- **Restores byte-fidelity** to the reference loop the H2 arm was meant to copy; it does **not** change
  any intended H2 scientific behavior — it removes a crash.
- **Scope proven minimal:** only `run_h2` changed. `run_aplus/run_r0/run_o1/run_o1r/run_h1` and the
  classifier are byte-identical between the pre-correction harness (`execution_code_commit 5cc392e1`)
  and the corrected harness (verified by `git diff`).
- **No frozen scientific-definition file changed** (arm/classifier/O1R/H1/H2 definition JSONs and their
  pinned hashes are untouched).

## Validation before resume

The corrected H2 loop was run on a **non-reserved fixture seed (3)** past the crash point (steps=705,
exercising the step-600 teacher snapshot, the 601+ distillation window, and the step-700 `mask=None`
handoff) with no crash, before any reserved H2 seed was run.

## Provenance

- Runs A+/R0/O1R/H1 (16 runs): `execution_code_commit = 5cc392e1` (pre-correction harness).
- Runs H2 (and O1 if reached): the corrected `execution_code_commit` (recorded in their per-seed
  manifests and the aggregate). The two-code-commit provenance is recorded honestly; the corrected
  commit differs from `5cc392e1` only in `run_h2`'s mask branch.

The reserved seeds, arm definitions, classifier, gates, thresholds, coefficients, and the adaptive
controller are unchanged.
