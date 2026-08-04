# Scaffold-withdrawal analysis (the headline finding)

The Stage-1 screen falsifies the simplest form of the working hypothesis and localizes the problem.

## Hypothesis tested

*Aggregate write-read overlap is too weak a scaffold objective; requiring read probability on the
specific written slot (O1) or an explicit read-logit margin (O2) will produce causally
address-dependent, retained routing.*

## Result: the objective works during the scaffold but the routing is not retained

O1/O2 successfully induce correct-slot routing **during** the scaffold window (correct-slot
probability rises to 0.5–0.97 by step 600, the end of the λ window). After withdrawal (λ = 0 for
steps > 600) that routing **decays** (→ 0.14–0.28 by step 1200), while needle retrieval **stays at
1.0**. The address-specific circuit the objective builds is **not retained** across withdrawal — the
*same* post-scaffold retention instability that afflicts retrieval, now observed one level deeper, at
the routing itself.

```
O1 correct-slot prob   step: 300   600   900   1200      needle@1200
   seed 21                   0.74  0.97  0.29  0.28          1.00
   seed 18                   0.81  0.54  0.18  0.14          0.94
```

## Consequence: needle survives via an address-independent shortcut

Because needle stays high while correct-slot routing decays, retrieval must be flowing through a path
that does **not** depend on correct addressing. The frozen causal ablations confirm it: **slots-off
collapses** retrieval (the slots are used) but **randomized-addressing does not** (0.96–1.00 on 4/5 O1
seeds; the slot memory is read diffusely, robust to address permutation). This is exactly the seed-16
impurity mode from the confirmatory phase — and the address-specific objective made it *more*
prevalent (4/5 vs 1/5), not less, by making needle formation more reliable through the shortcut.

## Two proxy dissociations, now stacked

1. **Confirmatory (PR #1324):** aggregate overlap dissociates from retrieval (seeds 13/14: overlap
   retained, needle 0).
2. **This phase:** the correct-slot *probability* the objective optimizes dissociates from causal
   *address-dependence* at evaluation — the proxy is optimized during the window, then decays, and the
   function (needle) is carried by an address-independent path.

## What this localizes

The crux is **retention of the routing circuit across scaffold withdrawal**, not the within-window
objective. A better within-window addressing signal alone does not suffice, because it is not
maintained after the scaffold is removed. The indicated levers are the **deferred** ones aimed at
*persistence* through/after withdrawal:

- a **standing** (non-decaying, small) address-dependence term (the deferred O1R residual);
- a **functional teacher / consolidation** that carries the scaffold-era routing across the handoff
  (deferred H2 / H1);
- possibly a **combination** of an address objective with a consolidation mechanism (deferred C1).

The gradual handoff (H3) tested here targets the *distribution* shift, not routing persistence, and
did not help — consistent with the crux being routing retention rather than the handoff sharpness.

## Conservative framing

These are single-trajectory reads on five seeds. "The routing decays after withdrawal and needle is
carried by an address-independent shortcut" is well-supported by the prob trajectories + the
randomized-address ablation, but the precise cause of the diffuse-read attractor is not established.
No claim is made that address-dependent routing is *unattainable* — only that the tested within-window
objectives do not *retain* it under the frozen protocol.
