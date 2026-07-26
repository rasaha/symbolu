# Phase v2-S as a retention-priority signal in oracle-addressed bounded memory

**Gated experiment — result: NEGATIVE (primary endpoint not met).**
Phase v2-S, inserted only into the retention/eviction priority of the validated
oracle-addressed bounded-memory task, does **not** produce a reliable target-survival
or answer-accuracy gain over the oracle capacity baseline. The permitted-λ Phase term
is effectively inert at the eviction boundary, and target survival does not depend on
the distant focus cue it was meant to exploit. **Do not proceed to the
quadratic-attention hybrid on the basis of this signal.**

Frozen Phase v1 is untouched (`FREEZE OK`); the full lightweight_phase suite is green
(`98 passed`); oracle identity allocation, query lookup, value encoding, slot value,
and the answer decoder are byte-identical across all arms — only the retention signal
differs.

---

## 1. Hypothesis under test

Chain (as specified):

> distant focus cue → Phase v2-S preserves its relevance in bounded state → the
> focus-target record receives higher retention priority → it survives eviction more
> often → answer accuracy improves.

Primary endpoint: **Δsurvival = P_{D-v2}(target survives) − P_{C-oracle}(target survives)**,
with acceptance **Δsurvival ≥ 0.10** at n_live = 12 or 16, corroborated by (a) the gain
appearing in early/middle target positions, (b) D-zero ≈ C, (c) D-random and D-shuffled
≤ C, and (d) the effect holding across three seeds.

## 2. Design

- **Task:** `datasets_pressure_v2.make_focus` (`focus_retention=True`). A distant
  "focus vendor V*" header precedes a flood of records under bounded slots (M = 8);
  the target is a focus-vendor contract that competes for retention against `n_live`
  live identities. Answering requires the target record to have survived eviction and
  be readable from its slot.
- **Oracle addressing (unchanged, all arms):** same identity → same slot; new identity →
  free slot, else evict the active slot of lowest `r_final`; query identity → matching
  slot. Value encoding, slot value, read, and the answer decoder are identical across
  arms. This isolates retention as the only intervention.
- **Retention interface (§7):** `r_final = r_local(h) + λ · normalize(r_phase([h; g_v2]))`,
  λ ∈ [0, 0.25]. Study runs use fixed **λ = 0.25** (the maximum permitted; Phase must not
  *dominate* eviction). Arms differ only in the phase contribution:

  | arm | retention |
  |---|---|
  | C-oracle | `r_final = r_local` (capacity baseline) |
  | D-v2 | `r_local + λ·norm(r_phase)` from Phase v2-S state |
  | D-zero | `r_local + λ·0` (Phase computed, then zeroed) |
  | D-random | `r_local + λ·randn` (scale-matched noise) |
  | D-shuffled | `r_local + λ·norm(r_phase)` shuffled across the batch |

- **Training:** curriculum `[(2,100),(4,120),(8,150),(n_live,180)]`; losses = answer CE
  + write-gate BCE + Phase-gate BCE (research scaffold, v2 arms) + retention hinge
  (`focus records must out-rank distractor records by a margin`; uses the focus-cue
  label, never the future query). Adam 1e-3, batch 16, grad-clip 1.0.
- **Seeds:** 0, 1, 2. **Pressures:** n_live ∈ {12, 16}. Paired data seeds across arms.

## 3. Primary result — endpoint NOT met

Means over 3 seeds (test seeds 1000+s, disjoint from train). Full per-seed values in
`results/aggregate.json`; formatted in `results/tables.md`.

### n_live = 12 (M = 8)

| arm | survival | early-target survival | acc | acc \| survived | acc \| evicted |
|---|---:|---:|---:|---:|---:|
| C-oracle | **0.847** | 0.870 | **0.825** | 0.967 | 0.040 |
| D-v2 | 0.828 | 0.925 | 0.773 | 0.928 | 0.028 |
| D-zero | 0.813 | 0.828 | 0.785 | 0.949 | 0.079 |
| D-random | 0.788 | 0.819 | 0.738 | 0.928 | 0.040 |
| D-shuffled | 0.817 | 0.847 | 0.775 | 0.941 | 0.038 |

**D-v2 − C (paired):** survival **−0.018 ± 0.076**; early-survival **+0.054 ± 0.061**;
acc **−0.052 ± 0.082**.

### n_live = 16 (M = 8)

| arm | survival | early-target survival | acc | acc \| survived | acc \| evicted |
|---|---:|---:|---:|---:|---:|
| C-oracle | 0.727 | 0.764 | **0.722** | 0.986 | 0.018 |
| D-v2 | **0.735** | 0.793 | 0.662 | 0.891 | 0.026 |
| D-zero | 0.677 | 0.689 | 0.662 | 0.973 | 0.009 |
| D-random | 0.738 | 0.774 | 0.725 | 0.961 | 0.064 |
| D-shuffled | 0.717 | 0.734 | 0.665 | 0.911 | 0.045 |

**D-v2 − C (paired):** survival **+0.008 ± 0.041**; early-survival **+0.029 ± 0.066**;
acc **−0.060 ± 0.050**.

**Verdict on the endpoint:** Δsurvival is −0.018 (L12) and +0.008 (L16) — both far below
the +0.10 acceptance threshold and within one standard deviation of zero. Answer accuracy
is consistently *lower* with Phase in the retention path (−0.05, −0.06). The only
positive is a small early-target survival bump (+0.05 / +0.03) that is within noise
(std ≈ 0.06) and **not** accompanied by the required control separation (below).

## 4. Controls — no specificity to the real Phase signal

For the survival gain to be attributed to Phase v2-S, the controls must order as
`D-random, D-shuffled ≤ C ≤ D-v2` with `D-zero ≈ C`. Observed:

- **D-zero ≈ C:** yes, roughly (0.813 vs 0.847 at L12; 0.677 vs 0.727 at L16) — zeroing
  the phase contribution recovers the baseline, as designed.
- **D-random / D-shuffled ≤ C:** **not established.** At L12, D-shuffled (0.817) and
  D-random (0.788) sit around C (0.847), not clearly below. At L16, D-random (0.738)
  slightly *exceeds* C (0.727). The scale-matched-noise and identity-scrambled arms are
  statistically indistinguishable from D-v2, so any D-v2 movement is consistent with an
  effect of *adding a comparable-magnitude perturbation to r_final*, not with the
  *content* of the focus signal.

## 5. Why it fails — two direct causal probes

### Decision trace (§12): Phase is inert at the eviction boundary

Re-running the oracle write stream and comparing the eviction victim chosen by `r_local`
alone vs `r_final = r_local + λ·r_phase` (120 examples per D-v2 run):

| run | frac decisions changed by Phase | help − hurt | mean \|λ·phase\|/\|local\| |
|---|---:|---:|---:|
| L12 s0 | 0.017 | −0.017 | 0.66 |
| L12 s1 | 0.000 | 0.000 | 0.87 |
| L12 s2 | 0.017 | 0.000 | 1.33 |
| L16 s0 | 0.017 | +0.017 | 0.26 |
| L16 s1 | 0.000 | 0.000 | 4.92 |
| L16 s2 | 0.025 | +0.008 | 0.27 |

The Phase term changes which record is evicted in **≈0–2.5 % of examples**. Even though
its magnitude is comparable to (sometimes larger than) `r_local`, its *ranking* rarely
disagrees with the local ranking at the eviction margin, so it almost never moves the
target across the survive/evict line. Within the permitted λ ≤ 0.25 (Phase must not
dominate), Phase cannot causally shift retention.

### Shortcut check (§14): survival does not depend on the focus cue

Blanking the distant focus header (positions 0–3, so Phase cannot read the focus vendor)
leaves target survival essentially unchanged in every D-v2 run:

| run | intact survival | focus-header removed |
|---|---:|---:|
| L12 s0 | 0.883 | 0.883 |
| L12 s1 | 0.717 | 0.717 |
| L12 s2 | 0.858 | 0.858 |
| L16 s0 | 0.817 | 0.808 |
| L16 s1 | 0.708 | 0.700 |
| L16 s2 | 0.750 | 0.750 |

The retention the model actually uses is **not keying off the focus cue** — the
hypothesised mechanism ("Phase preserves distant focus relevance") is not operative.

### The oracle task itself is valid (positive control)

`remove_target_slot_acc ≈ 0.008` (chance) in every run — deactivating the slot that
holds the target collapses the answer to chance, proving the answer genuinely depends on
bounded memory. `acc | survived` is 0.89–0.99 while `acc | evicted ≈ 0.02` (chance):
survival, not a decode shortcut, gates the answer. The negative result is a property of
the *Phase retention signal*, not a broken task.

## 6. λ ablation (§7/§13)

*(Populated from `results/lambda_sweep.json` — λ ∈ {0, 0.01, 0.05, 0.10, 0.25}, seed 0,
n_live = 12. See §"λ sweep" table below; the study caps λ at 0.25 because Phase must not
dominate eviction, and the decision trace shows the term is already near-inert at that
ceiling.)*

<!-- LAMBDA_SWEEP_TABLE -->

## 7. Supervised vs end-to-end gate

Both the Phase v2-S write gate and the pairwise retention hinge are trained with
focus-cue supervision (a research scaffold — labels derive from the distant focus vendor,
never the future query). The retention hinge *does* successfully order focus records above
distractor records in `r_final` (that is what makes the retention head trainable under
discrete eviction). The failure is downstream: a correctly-ranked phase score still does
not change the *discrete* eviction victim often enough, because `r_local` already
separates the competing records and λ is bounded. No purely end-to-end (unsupervised)
variant was attempted, and it would be expected to do no better given the supervised
signal is already near-inert at the eviction boundary.

## 8. Retention interface & resources (§18)

Bank sizes measured at B = 1; all arms O(N) runtime, constant state in N, no N×N, no
unbounded cache.

| arm | params | slot state (B) | phase state (B) | total state (B) | tokens/s |
|---|---:|---:|---:|---:|---:|
| C-oracle | 940,516 | 3072 | 0 | 3072 | 20,308 |
| D-v2 | 996,392 | 3072 | 1152 | 4224 | 18,873 |
| D-v1 | 996,004 | 3072 | 0¹ | 3072 | 19,458 |

¹ D-v1 uses frozen Phase v1's dense-cumsum readout, which keeps no persistent recurrent
bank; the +56 k params over C are the retention/phase heads. D-v2 adds a single
persistent Phase v2-S bank (γ = 1), +1152 B of state — a ~37 % state increase for no
retention benefit here.

## 9. What this rules in and out

- **Rules in:** the oracle-addressed bounded-memory task is a valid substrate — answer
  depends on retained bounded state, decode is not a shortcut, capacity pressure is real
  (survival falls from ~0.85 at n_live 12 to ~0.73 at n_live 16 for C-oracle).
- **Rules out (for now):** Phase v2-S as a *bounded-λ additive retention-priority term*
  improving target survival/accuracy in this task. The signal is real (the hinge orders
  it correctly) but causally inert at the discrete eviction boundary, and the learned
  retention does not actually exploit the focus cue.

## 10. §20 — Final block

| item | result |
|---|---|
| **Oracle capacity baseline (C)** | survival 0.847 (L12) / 0.727 (L16); acc 0.825 / 0.722; acc\|survived 0.97 / 0.99; acc\|evicted ≈ chance |
| **Phase v2 focus signal** | retention hinge orders focus > distractor in `r_final`, but the term changes the discrete eviction victim in only ≈0–2.5 % of examples at λ = 0.25 |
| **Target-survival gain [D-v2 − C]** | **−0.018 ± 0.076 (L12); +0.008 ± 0.041 (L16)** — endpoint (≥ 0.10) **NOT met** |
| **Answer-accuracy gain [D-v2 − C]** | **−0.052 ± 0.082 (L12); −0.060 ± 0.050 (L16)** — Phase in the retention path *lowers* accuracy |
| **Early-target survival gain** | +0.054 ± 0.061 (L12); +0.029 ± 0.066 (L16) — within noise; not corroborated by controls |
| **Causal ablations** | D-zero ≈ C (recovers baseline); D-random / D-shuffled **not** below C (no specificity); removing focus header does **not** reduce survival; removing target slot → chance (task valid) |
| **Supervised vs end-to-end gate** | supervised hinge ranks focus correctly, but a correct ranking does not flip bounded-λ discrete eviction; no end-to-end variant would be expected to help |
| **Retention interface** | `r_final = r_local + λ·norm(r_phase)`, λ = 0.25 fixed (max permitted; init 0 when learned) |
| **Complexity** | O(N) runtime, constant state in N, no N×N, no unbounded cache; D-v2 adds 1152 B persistent bank (+37 % state) |
| **Verdict** | **NEGATIVE — hypothesis not supported.** Phase v2-S retention gives no reliable survival or accuracy gain; the mechanism (focus-cue-driven retention) is not operative. |
| **Next permitted step** | Do **not** start the quadratic-attention hybrid on this signal. If Phase retention is pursued further, the blocking issue is the *discrete* eviction boundary: candidate next probes (each its own gated experiment) are (a) a soft/temperature eviction that lets a bounded phase term actually move the margin, or (b) making the phase score feed *value refresh* rather than eviction rank. Both remain unproven and out of scope here. |

---

### Reproduce

```
PYTHONPATH=. python3 -m experiments.phase_v2_oracle_retention.run_study      # full 3-seed × 2-pressure study
PYTHONPATH=. python3 -m experiments.phase_v2_oracle_retention._run_lambda     # λ ablation (§6)
python3 -m symbolu.lightweight_phase.freeze                                    # FREEZE OK
python3 -m pytest symbolu/lightweight_phase/tests/ -q                          # 98 passed
```

Artifacts: `results/aggregate.json`, `results/tables.md`, `results/raw/*.json`,
`results/lambda_sweep.json`, `PHASE_V2_ORACLE_RETENTION_MANIFEST.json`.
