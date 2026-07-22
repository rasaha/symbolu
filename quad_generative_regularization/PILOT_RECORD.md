# Bounded Pilot Record (Phase 1)

Per spec section 16 (Phase 1) and section 28 item 8. All pilot exploration used **one seed
(seed 0)**, short runs, and one shared learning-rate configuration. No broad hyperparameter
grid search was performed; Arms C and D were **not** independently optimized. Every setting
below was frozen at the end of the pilot and is not re-tuned after observing screen results.

## 1. Phase 0B implementation validation (all passed)

| Check | Result |
|---|---|
| Unit + leakage + shape tests (21 tests, spec §22 items 1-19) | **21 passed** |
| Arm A vs Arm D0 (λ=0) deterministic equivalence | **bit-identical** (max param diff 0.00e+00) |
| Future-token shuffle invariance of Quad score | **invariant** (max diff 0.00e+00) |
| Inference output identical with aux-only objects disabled | **identical** |
| Tiny fixed-batch overfit, Arms A / C / D | **all > 0.95** (architecture has capacity) |

## 2. Task-difficulty calibration (baseline learnability)

The baseline (Arm A, task loss only) was probed across MQAR difficulty to locate a valid
operating point. Model = spec-recommended 2-layer, hidden 96 unless noted.

| num_kv | Arm A final acc | note |
|---|---|---|
| 2 | 1.00 | trivial (no room to show an effect) |
| 3 | 1.00 (by ~step 625) | baseline learns easily; all arms saturate |
| 4 | **0.24–0.26** (plateau, stable to 5000 steps) | baseline capability boundary (≈ chance among 4 values) |
| 8 | 0.13 | far beyond baseline capability |

Chance accuracy at num_kv=K is ≈ 1/K (guessing among the present values). At **num_kv=4 the
baseline plateaus at chance and does not improve even at 5000 steps**, yet the same
architecture (a) solves num_kv≤3 and (b) overfits a fixed num_kv=4 batch to 100%. The plateau
is therefore a genuine **sample-efficiency / capability wall**, not an implementation defect
(spec §16: failure to overfit would be an implementation problem — overfit succeeds here).

**Frozen base (in-distribution) condition: num_kv=4, num_queries=2, vocab=32.** This is the
baseline capability boundary — the regime where an auxiliary objective can plausibly change
what the small model can learn, which is precisely what the study screens for.

## 3. Auxiliary hyperparameters (frozen)

Conservative fixed values, one-seed pilot at the frozen config:

| Setting | Value | Rationale |
|---|---|---|
| objective | `classification` (Option B) | native to Quad's own softmax/Top-K use of the score (QUAD_TRACEABILITY.md §5) |
| λ (lambda_aux) | **1.0** | both λ=0.5 (0.99) and λ=1.0 (0.993) solved the task; 1.0 frozen as the natural unit weight |
| τ (temperature) | **1.0** | unit temperature; not tuned |
| lr | 4e-3 | single shared schedule (warmup 50, then constant) across all arms |
| steps | 2500 | D and C converge well within budget; A has plateaued by ~500 |

Pilot arm results at the frozen config (seed 0, hidden 96, 2500 steps):

| Arm | final val acc |
|---|---|
| A (baseline) | 0.26 |
| C (generic relational, learned off-path head) | **0.997** |
| D (Quad-native, λ=1.0) | 0.993 |
| D (Quad-native, λ=0.5) | 0.99 |

**Key pilot observation (drives the honest expected verdict):** at the spec-recommended
hidden size (96), the *fair* generic relational control (Arm C) solves the task just as well
as the Quad-native arm (D) — C even converges slightly faster. Auxiliary relational
supervision clearly helps (A 0.26 → C/D 0.99), but the pilot does **not** show a Quad-specific
advantage over generic relational supervision at this configuration.

## 4. Arm C control design (pre-registered)

Two candidate Arm-C designs were considered during the pilot:

1. **Raw hidden-state dot product** `⟨h_i,h_j⟩/√D` (no parameters). Rejected as the primary
   control: because a query token is literally the repeated key token, this similarity is
   ~85% pre-satisfied at initialization (aux loss ≈ 0.17 vs the uniform ln(8)=2.08), so it
   provides almost no gradient — an unfairly *weak* control that would inflate any apparent
   Quad advantage.
2. **Equal-capacity learned off-path relation head** (LayerNorm + W_q/W_k + scaled dot
   product, structurally identical to the Quad scorer but never used in the forward path,
   discarded at inference). **Selected** — it starts from a non-trivial (uniform-ish) init
   like Arm D, so neither aux target is pre-satisfied; the only difference between C and D is
   whether the supervised relation is the model's *own forward-path Quad score* (D) or an
   *identical-form off-path relation* (C).

Choosing the strong, fair control (2) is the conservative, anti-overclaiming decision: it
gives the Quad-native hypothesis its fairest test and prevents a false-positive from a
strawman control.

## 5. Capacity-dependence note (exploratory, NOT used to redefine success)

During difficulty calibration a smaller model (hidden 64) was also observed: there, Arm D
(0.57) beat both Arm C (0.13) and Arm A (0.13) at num_kv=8 — i.e. at lower capacity the
Quad-native arm *did* outperform the generic control. At the spec-recommended hidden 96 this
advantage disappears (C ≈ D). This capacity-dependence is reported as an **exploratory**
observation and a lead for future work (§ limitations of the report). The frozen protocol uses
the **spec-recommended hidden size 96, decided a priori**; the more favorable hidden-64 result
is deliberately **not** adopted as the headline config, since selecting a configuration after
seeing that it favors the hypothesis would be results-driven redefinition of success (spec
§10.2, §14).
