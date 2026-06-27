# Capacity-Matched Controls — Do the Active Symbol-U Mechanisms Learn Anything a Plain Transformer Cannot?

**Research question (adversarial; not a benchmark, not the patent):** do the three
active Symbol-U mechanisms learn a computational behavior that a standard
Transformer cannot reproduce with the **same parameters and FLOPs**?

**Design.** Each Symbol-U mechanism is trained in its *earned-best* config
(combined mode: contribution + residual-reg + entropy-cal) and compared to a
control with ≈equal params **and** FLOPs, identical dataset/optimizer/lr/batch/
seed/steps:

| Symbol-U mechanism | Capacity-matched control | What it isolates |
|---|---|---|
| Recursive refinement (entropy-gated block ×3) | `RecurrentPlainRefine`: the **same shared block applied 3×**, no entropy / halting / gated-delta | only the gating machinery |
| Deferred-Insight memory (causal prefix-summary) | `PointwiseMemoryControl`: pointwise residual FFN, params ≈ d² | cross-time summary vs plain pointwise capacity |
| Full Symbol-U (refine + memory) | `recur_plain` + `mem_control` together | the whole stack vs equal capacity |

Reproduce: `python -m symbolu_neural.clean_softmax.run_capacity_study --steps 300
--block 96` (and `--seed 1`). CPU, char-level, d=128, 2 layers.

## Results — two seeds (val loss; lower is better)

Params and FLOPs are matched to within ~0.4 % per pair (e.g. refine 825k/1.46
MFLOP vs control 822k/1.46 MFLOP).

| Mechanism | Symbol-U (s0 / s1) | Control (s0 / s1) | Δ(S−C) s0 / s1 | Verdict |
|---|---|---|---|---|
| Recursive refinement | 2.936 / 2.902 | **2.857 / 2.793** | **+0.078 / +0.109** | control wins **both** |
| Deferred-Insight memory | 2.944 / 2.894 | 2.925 / 2.897 | +0.020 / −0.003 | tie-to-worse |
| Full Symbol-U | 2.855 / **3.069** | 2.881 / **2.796** | −0.026 / **+0.273** | high-variance; avg worse |

Full per-run summary (seed 0):

| run | val_loss | ppl | ece | params | MFLOP/tok | ms/step |
|---|---|---|---|---|---|---|
| baseline | 2.947 | 19.05 | 0.022 | 560k | 0.60 | 45 |
| refine_symbolu | 2.936 | 18.83 | 0.028 | 825k | 1.46 | 121 |
| refine_control | **2.857** | 17.42 | 0.040 | 822k | 1.46 | 87 |
| memory_symbolu | 2.944 | 18.99 | 0.030 | 579k | 0.62 | 59 |
| memory_control | **2.925** | 18.63 | 0.024 | 576k | 0.61 | 41 |
| full_symbolu | 2.855 | 17.38 | 0.027 | 842k | 1.48 | 158 |
| full_control | 2.881 | 17.84 | 0.027 | 839k | 1.47 | 88 |

## Internal diagnostics (why the result is what it is)

- **Refinement engages but generalizes worse.** Under the contribution objective
  its halting prob is ~0.998 and it "helps" on **94–95 %** of batches *by its own
  per-batch enabled-vs-disabled measure* — yet on held-out val loss the **plain
  recurrent block (same compute) wins by 0.08–0.11 on both seeds.** So the
  per-batch contribution signal is **locally misleading**: the gating machinery
  makes the module engage and lower the *training-batch* loss, but the resulting
  model generalizes worse than simply iterating a plain block. Earned ≠ better.
- **Memory's prefix-summary buys nothing.** A pointwise FFN of the same size
  matches or beats the causal deferred-insight memory on both seeds.
- **Symbol-U is less stable.** Full Symbol-U blew up on seed 1 (val 3.069,
  refine-help-frac collapsed 0.97→0.62) while the control was stable (2.796). The
  apparent full win on seed 0 (−0.026) flipped to +0.273 on seed 1 — it was noise.
- **Latency is worse** for no benefit (refine 121 vs control 87 ms/step;
  full 158 vs 88).
- **No generation advantage.** Samples are incoherent for all runs; if anything
  the control reproduces corpus structure (markdown `|----|`, `***`) at least as
  well as Symbol-U.

## Per-mechanism verdict table

| Mechanism | Active | Capacity-Matched Control | Better Than Control? | Different Behavior? | Verdict |
|---|---|---|---|---|---|
| Typed heads → entropy | Yes (gates the others) | same-size gate signal | n/a (only a gate) | No | (control signal, not an actuator) |
| Recursive refinement | Yes (halt~1, "helps" 94%) | shared plain block ×3 | **No — worse both seeds** | Engages but generalizes worse | **Equivalent to extra capacity** (gating is *harmful* vs plain recurrence) |
| Deferred-Insight memory | Yes | pointwise FFN (≈d²) | **No — tie/worse** | No | **Equivalent to extra capacity** |
| Full Symbol-U | Yes | recur_plain + mem_control | **No — avg worse, high variance** | Less stable | **Equivalent to extra capacity / Inconclusive-negative** |

## Final answer

**Do the currently active Symbol-U mechanisms exhibit computational behavior that
is distinguishable from simply adding equivalent Transformer capacity?**

**No.** At matched parameters *and* FLOPs, across two seeds:
- **Recursive refinement is consistently *worse* than a plain recurrent block**
  (+0.078, +0.109). Its entropy-gating / halting / gated-delta machinery does not
  add a new computation — it *underperforms* simply applying the same block three
  times, despite the contribution objective making it engage.
- **Deferred-Insight memory is equivalent-to-worse than a plain pointwise FFN** of
  the same size — the causal prefix-summary contributes nothing distinguishable.
- **Full Symbol-U does not reliably beat its capacity-matched twin** (one seed
  +0.026, the other −0.273; on average worse and less stable). The single-seed
  apparent win was noise.

The mechanisms behave like "just more Transformer capacity" — and the refinement
variant behaves like a *worse-tuned* extra layer. The earlier "the modules can be
earned" finding holds only in the sense that the contribution objective forces the
gate on; it does **not** translate into a computation a plain, equal-budget
Transformer cannot match or exceed.

## Caveats (kept honest, but they do not rescue the result)

- Small scale: char-level, d=128, 2 layers, 300 steps, 2 seeds. More seeds/steps/
  scale could shift magnitudes — but the **direction is consistent** (refinement
  loses on both seeds; memory never wins), which is the load-bearing finding.
- The comparison is on validation cross-entropy; a task that specifically rewards
  long-range deferred recall might favour memory — untested here, and not claimed.
- Controls were trained in `normal` mode (they have no gates to earn); Symbol-U in
  `combined` (its best). This *favours* Symbol-U, and it still lost — strengthening
  the negative conclusion.
