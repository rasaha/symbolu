# Frozen Phase-Guided Bounded Slots — Root-Cause Diagnostic Report

**Scope.** Diagnostic only. The frozen `symbolu.lightweight_phase` package was **not
modified** (no change to equations, defaults, weights, normalizer, decay, streaming
semantics, or manifests; no quadratic attention added; the production combined
experiment was not retrained beyond the arms needed to reproduce the failure and
probe it). All new code lives under `experiments/phase_guidance_diagnostics/`.

---

## 1. Frozen baseline

| item | value |
|---|---|
| branch | `claude/frozen-phase-transformer-diag-jzabnu` |
| git commit | `18a5b5a88977b53f9d947a23f4208f73f110baf0` |
| frozen versions | phase_core v1.0 / decay v1.2, streaming v1.1, transformer v1.3, local v1.4, binding v1.5 |
| test count / result | **98/98 pass** (`symbolu/lightweight_phase/tests`) |
| freeze verifier | **FREEZE OK** (`python -m symbolu.lightweight_phase.freeze`) |
| working tree | **clean** (frozen sources untouched; source SHA-256 match manifest) |
| Python / PyTorch | 3.11.15 / 2.13.0+cu130 (CPU) |
| CPU / RAM | 4× Intel Xeon @ 2.10GHz / 15 GiB, no GPU |

```
98/98 tests pass
FREEZE OK
working tree clean
```

**Exact Phase settings in the guidance experiment**
(`LightweightPhaseAttention(PhaseConfig(embed_dim=96, num_heads=4))`,
config hash `d9ba8c6bde3d6773c180d792fbcac045d4f1250b08e6de6c3e797344711d4e3b`):

| setting | value |
|---|---|
| hidden dimension | 96 |
| number of heads | 4 |
| head dimension | 24 |
| bounded_phase | **True** (φ = π·sin(raw)) |
| amplitude floor | 0.0 |
| normalizer clamp | denom_eps = 0.1 → Z_t = max(a_q·A_t, 0.1) |
| normalizer detachment | **True** (stopgrad on Z_t) |
| use_decay | **False** |
| learned_decay | **False** |
| gamma range | [0.90, 0.99999] (unused) |
| initial gamma | 0.99 (unused) |
| state dtype | complex64 (memory) / float32 (amplitude) |
| residual scale | aux_scale = 1.0; g_t = phase(h) − h = W_out(o_t) |
| fusion coefficient | additive: write_key = k_local(h) + k_guide([h;g]); read_query = q_read(hA) + q_read_g(gA) |
| state reset | fresh zero-state per example; no cross-example carry |

> **Key configuration fact:** decay is **off** (`decay_mode="none"`), so the Phase
> recurrence is a pure cumulative sum S_t = Σ_{j≤t} kv_j normalized by a cumulative
> amplitude A_t = Σ_{j≤t} a_{k,j} — it **never forgets**. Also, "frozen" here means
> the frozen *equations/code*; the Phase layer *weights* are randomly initialised
> per arm and **trained jointly** with the rest of the model.

---

## 2. Exact observed failure (seed 0; slots M=8)

| arm / pressure | answer_acc | write_F1 | role |
|---|---:|---:|---|
| A (local only, no slots) | 0.04 (1x) | – | chance (1/20=0.05) → slots are needed |
| **C** (slots, local-only guidance) | **0.95 / 0.98** (1x/3x) | 0.00 | strong |
| **D** (slots, Phase-guided) | **0.97 / 0.85** | 0.00 | degrades under pressure |
| D-no-guid (Phase, guidance zeroed) | 0.97 / **0.40** | 0.08 | unguided slots collapse at 3x |
| D-write-only (Phase on writes) | 0.76 / **0.11** | 0.02 | **write-path Phase is catastrophic** |
| D-query-only (Phase on reads) | 0.89 / 0.71 | 0.00 | read-path Phase mildly harmful |

The headline reproduces (D < C, and the gap widens under pressure), consistent with
the prior single-seed 8-slot result (C 0.99 vs D 0.16/0.53 at 4×/8×). The **arm
decomposition localizes the harm to the write path** (D-write-only = 0.11 ≪ C).
Full D (0.85) is *less* harmed than write-only (0.11) because when both keys and
query carry the Phase term, their common-mode components partially cancel in the
dot-product read.

---

## 3. Diagnostic layers

```
L1 Tokens → frozen Phase recurrent state       (Q A,B,C,D)
L2 Phase state → guidance representation g       (Q A,E,F)
L3 Guidance g → write / retain / evict / read    (Q H,I,L)
L4 Selected slots → relational answer            (Q J,K)
```

---

## 4. Q A — Does Phase retain the global topic?  **NO (near chance).**

Linear probe ŷ_topic = W·x at the answer position (max distance), 20-way, chance 0.05:

| feature | top-1 | top-3 |
|---|---:|---:|
| local-only (h) | **0.367** | 0.583 |
| **phase-only (g)** | **0.117** | 0.283 |
| local + phase | 0.261 | 0.500 |
| random-state control | 0.078 | 0.244 |
| shuffled-phase control | 0.072 | 0.211 |

The **Phase readout barely exceeds a random-noise control** (0.117 vs 0.078) and
**concatenating Phase *degrades* the local probe** (0.367 → 0.261). The topic lives
in the **local** stream (which is exactly what the slots content-address on); the
**global Phase readout does not linearly carry it.** For C (no Phase), phase-only =
chance as expected (g ≡ 0).

## 5. Q B — Does the Phase signal decay with distance?  **It is diluted, not decayed.**

Controlled test: "TOPIC vendor X `<sep>`" + K filler tokens, decode topic from g at
the final position:

| K (filler) | phase top-1 | state ‖S‖ | topic SNR |
|---:|---:|---:|---:|
| 64 | 0.016 | 163 | 0.0103 |
| 256 | 0.031 | 698 | 0.0023 |
| 1 024 | 0.062 | 2 261 | 0.0008 |
| 4 096 | 0.047 | 9 430 | 0.0002 |
| 16 384 | 0.062 | 38 764 | 0.0000 |
| 32 768 | 0.031 | 78 004 | 0.0000 |

Phase topic decoding sits at/near chance (0.05) at **every** distance. The state
norm grows **linearly** with filler (no decay), and the topic token's signal-to-
state ratio falls as **~1/N**. This is *dilution* by never-forgotten filler, not
abrupt disappearance or phase cancellation.

## 6. Q C — Is cumulative normalization diluting rare evidence?  **YES.**

Numerator attribution of the readout at the answer position:

| n_cand | seq_len | topic share | rel-fact share | **filler share** | rel/distr | Z |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 258 | 0.042 | 0.029 | **0.898** | 9.68 | 5 919 |
| 17 | 348 | 0.011 | 0.017 | **0.898** | 0.54 | 8 171 |
| 65 | 1 192 | 0.004 | 0.005 | **0.932** | 0.29 | 25 677 |
| 129 | 2 317 | 0.004 | 0.004 | **0.925** | 0.32 | 49 995 |

The **topic + relevant-fact contribution is < 1%** of the numerator; **~90–93% is
filler**, and the normalizer Z grows without bound. The relevant-to-distractor ratio
collapses from 9.7 (no distractors) to ~0.3. Dilution correlates directly with the
regime where D degrades.

## 7. Q D — Is learned decay removing the topic?  **RULED OUT.**

Decay is **off** in this config. Read-only interventions re-accumulating S,A under an
imposed γ change topic decodability negligibly (γ=1.0→0.9 gives 0.127→0.127, all
near chance). Decay is neither the culprit nor a lever: a shorter horizon would
forget the *distant* topic sooner, and γ=1 (the config) already fails via dilution.

## 8. Q E — Are the heads carrying distinct useful signals?  **Diverse but uniformly uninformative.**

full topic top-1 = 0.133; effective rank **11.5 / 96** (low-rank); mean |off-diag
head corr| = 0.034 (heads **decorrelated**). Per-head topic top-1 = 0.09–0.13 (all
near chance); ablating head 3 *raises* accuracy (+0.047 — it is noise). Heads are not
redundant, but **none preserves the topic** — the shortfall is the diluted input
signal, not a lack of head diversity.

## 9. Q F — Is the guidance head extracting the wrong information?  **The information is not there to extract.**

Freezing the encoder and fitting richer heads:

| input | topic linear | topic MLP | write-worthiness F1 |
|---|---:|---:|---:|
| local-only | 0.307 | 0.227 | 0.00 |
| phase-only | 0.087 | 0.113 | 0.00 |
| local + phase | 0.187 | 0.140 | 0.00 |

A 2-layer MLP on Phase does **not** beat the linear probe (both ≈ chance): the
readout is not the bottleneck — **the Phase state does not encode the topic**.
Write-worthiness F1 is 0 even from local features (1 positive per ~25 tokens; the
objective is imbalanced and never gets traction — see Q J/L).

## 10. Q G — Are the write labels aligned with future utility?  **ALIGNED.**

| fact type | topic-related | needed-later | label |
|---|---:|---:|---:|
| topic fact (1 per ex) | yes | yes (value == answer) | **1** |
| distractors (~24 per ex) | no | no | 0 |

label==1 has **1.000 precision** for "needed-later" (exactly one topic fact whose
value is the gold answer; no superseded/multi-version topic facts in the generator).
**Label misalignment is not the failure.** The real gap is that L_write is *weak/
unlearnable-because-unnecessary* (Q J), not mislabeled.

## 11. Q H — Is Phase overpowering precise content addressing?  **NOT at read.**

Read-score decomposition (D, 3x): **R = |s_phase| / |s_content| = 0.056 mean, 0.107
p90** — the Phase term is a *small* fraction of the content score at read.
Inference-time β-sweep on the full coupling:

| β | 0.0 | 0.05 | 0.1 | 0.25 | 0.5 | 1.0 |
|---|---:|---:|---:|---:|---:|---:|
| answer_acc | 0.900 | 0.910 | 0.910 | 0.900 | 0.910 | 0.910 |
| read changed | 0.00 | 0.00 | 0.00 | 0.02 | 0.02 | 0.03 |

Accuracy is **flat** from β=0 (content-only) to β=1 (trained): in the converged D
model the Phase term neither helps nor overpowers the *read*. The prior report's
"Phase corrupts content-addressing at read" mechanism is **not supported** here. The
harm is on the **write path** (D-write-only = 0.11), where the diluted Phase term
perturbs which slot each fact writes — a training-dynamics effect, not a fixed
inference-time domination.

## 12. Q I — Where does Phase corrupt the chain?  **Writes ≫ reads.**

From the arm decomposition at 3x (vs C = 0.98): D-write-only **0.11**, D-query-only
0.71, D (write+read) 0.85. **Write-path Phase guidance is the damaging channel**;
read-path Phase is mildly harmful; combining them partially cancels via common-mode.
Because the Phase signal fed to writes is topic-noise (Q A/C), it can only randomize
slot assignment.

## 13. Q J — Is the task actually exercising slot pressure?  **NO — invalid pressure.**

Slot-chain trace:

| arm/pressure | occ / M | saturated@end | evictions | hard writes | matches |
|---|---:|---:|---:|---:|---:|
| C / 1x | 1.9 / 8 | 0.00 | **0.0** | 4.4 | 3.6 |
| C / 3x | 2.2 / 8 | 0.00 | **0.0** | 7.3 | 6.4 |
| D / 3x | 1.8 / 8 | 0.00 | **0.0** | 7.6 | 6.8 |

Despite a nominal 3× (24 candidate facts vs 8 slots), only **~2 of 8 slots** ever
fill and there are **zero evictions**. Facts collapse into ~2 slots because they
share structure ("vendor X valued Y…") → most hard writes are **matches** (in-place
supersede), not allocations. **There is no slot-selection pressure for global
guidance to help with.** C "wins" not by surviving pressure but because the task has
none.

## 14. Q K — Is there a query-time shortcut?  **Memory is used; addressing is trivial.**

Answer accuracy under read-time corruption:

| corruption | C | D |
|---|---:|---:|
| intact | 1.000 | 0.907 |
| shuffle slot **values** | **0.060** | **0.053** |
| random slot values | 0.033 | 0.027 |
| zero readout memory | 0.040 | 0.027 |
| shuffle slot **keys** | 0.973 | 0.893 |
| mask query entity | 1.000 | 0.900 |
| remove Phase at query (D) | – | 0.900 |

Corrupting slot **values** collapses accuracy → the answer genuinely comes from the
bounded memory (no full-history shortcut). **But** shuffling slot **keys** and masking
the **query entity** barely change anything: with only ~2 active slots read via
top-k=4 (i.e. all of them), *addressing* is unnecessary. This is the read-side face of
the "no pressure" finding, not a memory bypass.

## 15. Q L — Is multitask interference destroying the Phase signal?  **MILD, secondary.**

Per-loss gradients into shared params (D, 3x):

| group | ‖g_answer‖ | ‖g_write‖ | cosine | write/answer |
|---|---:|---:|---:|---:|
| guidance head | 2.8e-2 | 5.2e-2 | **+0.39** | 1.87 |
| Phase | 1.2e-1 | 5.0e-2 | **−0.18** | 0.42 |

At the guidance head the two objectives are **cooperative** (cos +0.39). Into Phase
they are **mildly opposed** (cos −0.18) but the answer objective dominates (write
gradient is 0.42×). Interference is real but small — not the primary cause. The write
objective simply cannot get traction because the task doesn't need selective writes
(Q J) and the signal it would need (topic) is diluted out of Phase (Q A/C).

## 16. Q M — Does Phase need selective writes internally?  **YES — dilution, not invalidity.**

Topic decode from Phase g when the frozen recurrence is fed masked inputs (read-only):

| input to frozen Phase | keep density | phase topic top-1 |
|---|---:|---:|
| all tokens (as in experiment) | 100% | 0.127 |
| filler zeroed | 7% | 0.093 |
| **topic + fact tokens only** | 5% | **0.293** |

Reducing write density to the topic+fact tokens **more than doubles** Phase topic
decodability (0.127 → 0.293). Per the protocol:

> **The frozen Phase recurrence preserves useful information when write density is
> reduced, suggesting state dilution rather than an invalid recurrence.**

---

## 17. Root-cause decision tree (applied)

- Phase **cannot** decode the topic (Q A/B/E/F: ≈ chance across probes, distances,
  heads, and MLP) → *root cause touches Phase state retention / dilution* … **but**
- the dilution is **removable by reducing write density** (Q M: 0.127→0.293) and by
  configuration (no-decay cumsum on a single rare token among ~470 fillers), and
- **plain slots avoid real eviction** (Q J: occ 2/8, 0 evictions) → *the task is not
  a valid pressure test*, and
- Phase **helps writes 0 and harms writes** (Q I: D-write-only 0.11) while **read
  coupling is small and harmless** (Q H: R=0.06, β-flat) → *the harm is feeding a
  topic-noise signal into an unnecessary write channel*, and
- staged/joint interference is **mild** (Q L: cos −0.18 into Phase).

Therefore the degradation is **not** evidence that the Phase recurrence is invalid.
It is the compound of (i) a diluted, near-noise global signal and (ii) a task that
does not need global guidance, (iii) coupled into the damaging write path.

## Root-cause ranking

**Primary**
1. **Task provides no real slot pressure (L4 / Q J).** occupancy ≈ 2/8, zero
   evictions at nominal 3×; facts collapse into ~2 slots by content-match
   supersession. The premise "bounded slots need a global relevance signal" is never
   exercised, so Phase guidance is at best decorative.
2. **Phase readout does not carry the topic (L1 / Q A,C,M).** Cumulative-normalization
   dilution (no decay) drives the single rare topic token to <1% of the numerator
   (~90% filler); Phase topic decoding ≈ chance everywhere. The guidance head is
   therefore handed **topic-noise**.

**Secondary**
3. **Write-path coupling of that noise (L3 / Q H,I).** Injecting the near-noise Phase
   term into write keys/gate/retention perturbs slot assignment (D-write-only = 0.11).
   Read-path coupling is small (R=0.06) and, in the converged model, harmless.

**Unlikely**
4. Multitask interference (Q L: mild, cos −0.18 into Phase, answer-dominated).
5. Guidance-head weakness (Q F: an MLP does no better; the signal is absent, not
   mis-read).

**Ruled out**
6. Learned decay removing the topic (Q D: decay is off; imposing γ does nothing).
7. Write-label misalignment (Q G: label==1 has 1.0 precision for needed-later).
8. Query-time memory bypass (Q K: corrupting slot values collapses accuracy — memory
   *is* used).
9. Phase overpowering precise content-addressing **at read** (Q H: β-sweep flat).
10. Invalid Phase recurrence (Q M: masking restores decoding — dilution, not invalidity).

## 18. Recommendation

**Do NOT create Phase v2.** Recommendation E requires that topic information be
undecodable, that dilution/decay destroy it, that this persist across probes *and*
training regimes, **and that downstream changes cannot recover it.** The first three
hold, but the fourth fails: the recurrence recovers topic under reduced write density
(Q M), decodability is a no-decay/single-rare-token artifact, and downstream changes
(β→0, or removing the write coupling) recover C-level accuracy. The frozen Phase
algorithm (v1.0–v1.5) **should remain unchanged**.

Permitted next changes, in order, each gated by a diagnostic threshold:

- **(C) Restrict Phase's role / (B) recalibrate coupling — cheap, immediate.** Remove
  the Phase term from the **write** path (keep at most a small read/tie-break term).
  Gate: D-write-only-removed ≥ C within noise; β-sweep already shows β≈0 is optimal.
- **(D) Fix the task before re-testing the hypothesis — required for any real test.**
  Build genuine pressure (facts must occupy **distinct** slots and force eviction:
  distinct entity keys, capacity < live facts, target-arrives-early + late filler,
  superseded topic versions). Gate: arm C must show **non-zero evictions** and a
  measurable **target-survival drop** before Phase guidance can be credited.
- **(Only then) reconsider a selective-write mechanism** so the topic is not diluted
  — as a *task/training* change, not a Phase-core edit. Gate: masked-input Phase
  topic decode (Q M, currently 0.29) must exceed local-only (0.37) before Phase can be
  expected to guide.

---

## Required final block

> **Frozen Phase state:** **does not** retain usable global topic information *in this
> configuration* — near-chance topic decodability everywhere — because the no-decay
> cumulative normalizer dilutes a single rare topic token below linear recoverability
> (<1% of the numerator vs ~90% filler). This is **state dilution, not an invalid
> recurrence**: masking filler restores decodability (0.127→0.293).
>
> **Guidance readout:** **failure, but not the cause** — a linear *and* a 2-layer MLP
> readout both sit at chance on Phase; the information is absent, so no readout
> recovers it.
>
> **Phase-to-slot coupling:** **noisy on writes, harmless on reads** — read
> |s_phase|/|s_content| = 0.06 and the β-sweep is flat, so Phase does **not** overpower
> content-addressing at read; the damage is confined to the write path (D-write-only
> 0.11), where a topic-noise signal randomizes slot assignment.
>
> **Training objective:** **aligned** — write labels have 1.0 precision for
> future-needed facts; the write loss is simply unlearnable-because-unnecessary
> (content-addressed reads solve the answer without selective writes).
>
> **Slot-pressure task:** **insufficiently constraining** — occupancy ≈ 2/8 slots and
> **zero evictions** at nominal 3×; facts collapse into ~2 slots and addressing is
> irrelevant (mask-query-entity and shuffle-keys are harmless).
>
> The observed degradation is primarily caused by **a task with no real slot pressure
> combined with a diluted, topic-uninformative Phase signal coupled into the write
> path** — not by an invalid Phase recurrence.
>
> The frozen Phase algorithm **should remain unchanged** (v1.0–v1.5).
>
> The next permitted change is **task redesign + coupling restriction (remove Phase
> from writes)**, gated by: arm C must exhibit **non-zero evictions and a target-
> survival drop** (a valid pressure test), and masked-input Phase topic decode must
> exceed local-only, **before** any separately-versioned Phase extension is considered.
