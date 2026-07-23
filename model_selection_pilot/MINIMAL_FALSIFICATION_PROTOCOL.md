# Minimum Falsification Protocol — Model Selection Policy on Real LLMs

*An experimental-design specification (not architecture). It defines the smallest
statistically meaningful, pre-registered experiment that can validate or falsify the
policy-engine hypothesis on real models, executable in ~1 week for < $100 of API spend
on the harness already built in this package.*

---

## 0. The hypothesis, as three pre-registered directional contrasts

The commercial claim is "**as-good quality, at lower cost, with better decisions than a
hardcoded table.**" That decomposes into three contrasts, tested in a **fixed-sequence
gatekeeping** order (each tested only if the prior passes) so family-wise error stays at
α = 0.05 with **no multiplicity penalty**:

| # | Contrast | Baseline | Type | Directional claim |
|---|---|---|---|---|
| **C1** | Selection regret | vs static rules (D) | superiority | policy makes **better decisions than a table** |
| **C2** | Cost per successful task | vs strongest-eligible (B) | superiority (≥15%) | policy **saves money vs always-strong** |
| **C3** | Quality-threshold success | vs strongest-eligible (B) | **non-inferiority** (margin 3 pp) | **without losing quality** |

If C1 fails, stop — the policy does not beat a static table and nothing else matters.
Only if C1 passes is C2 tested; only if C2 passes is C3 tested. This ordering encodes
the decision logic and preserves power.

---

## 1. The design principle that makes it cheap: paired counterfactual

One execution pass serves every arm. Because we **run every eligible model on every
task once** (per repetition), each arm is just a different *selection function* over the
same fixed outcome store. So cost = `tasks × eligible_models × reps` and is
**independent of the number of arms** — A–E, F1, F2, G all score from one pass.

Two consequences drive the minimum N:

- **Matched pairs.** Every contrast is a *within-task* comparison (F2's pick vs D's pick
  on the *same* task), which removes between-task variance — the dominant variance
  source — and shrinks N by 3–10× versus an unpaired design.
- **Effective N = discordant pairs.** Tasks where two arms pick the *same* model
  contribute a zero difference and no information. **The binding sample size is the
  number of tasks where the arms' choices diverge**, not the total. So the experiment is
  powered in discordant pairs and the corpus is **enriched toward decision-relevant
  tasks** (near constraint, quality, cost, or latency boundaries) by a *pre-declared
  rule* estimated on the dev pilot — never by hand-picking.

---

## 2. Minimum configuration (with justification)

| Knob | Minimum | Why |
|---|---:|---|
| **Models** | **4** (5 preferred) | Routing decisions only diverge with heterogeneous operating points: 1 cheap-fast, 1 mid general, 1 strong reasoning, 1 long-context; a 5th open-weight adds a family. < 3 makes routing trivial. |
| **Providers** | **≥ 2** | Exposes provider-governance constraints and avoids a single-vendor drift confound. |
| **Model families** | **≥ 3** | Distinct capability profiles (reasoning / general / small) are what create discordance. |
| **Domains** | **1** to falsify; **2** to generalize | One coherent domain (document intelligence) can already falsify. A 2nd domain is a *confirmatory replication*, run only if domain 1 passes. |
| **Tasks (confirmatory shadow)** | **~100 per domain** | Power analysis (§3): ~40 discordant pairs ÷ ~0.4 discordance rate ≈ 100 tasks. |
| **Tasks (dev pilot)** | **~30** | Estimate paired-difference variance and discordance rate; freeze policy; **never reused in the confirmatory set.** |
| **Repetitions** | **k = 3** per (model, task) | Separates model capability from sampling noise; needed because temp-0 is not truly deterministic (batching/MoE) and latency is variable. Use the median for quality, report p50/p95 latency. |
| **Human review** | **~15% of tasks, blind** + a **50-item scorer-validation set** (2 raters) | Not to score everything — to *validate the automated scorer* (require Cohen's κ ≥ 0.7 vs human) and adjudicate the subjective classes (summarization, QA groundedness). |
| **API cost** | **~$30–40 typical, cap $100** | ~130 tasks × 4 models × 3 reps ≈ 1,560 calls + ~300 G-preflight ≈ 1,860 calls at ~$0.02/call ≈ **$37**. Reasoning-model tokens + retries → cap $100. |
| **Statistical power** | **80%** (primary), report at 90% too | Standard; 90% needs ~35 discordant pairs at medium effect (§3). |

---

## 3. Power analysis (formulas + plugged numbers)

Paired, one-sided, α = 0.05. Standardized paired effect `d = δ / σ_d`. Required
**discordant** pairs `n = (z_{1-α} + z_{1-β})² / d²`:

| Effect `d` | 80% power | 90% power |
|---|---:|---:|
| 0.4 (small–med) | 39 | 54 |
| **0.5 (medium)** | **25** | **35** |
| 0.6 | 17 | 24 |
| 0.8 (large) | 10 | 14 |

- **C2 (cost)** is a *large* paired effect — routing a task from a $15/Mtok model to a
  $0.8/Mtok one is a big, low-variance per-task saving, `d` typically > 1 → **< 15
  discordant pairs** suffice. Cost is never the binding constraint.
- **C1 (regret)** and **C3 (quality non-inferiority)** are the binding constraints
  (bounded, noisier outcomes). Budget for a **medium effect** → target **~40 discordant
  pairs** (covers 90% power at d ≈ 0.5 and the McNemar discordant-pair floor for
  non-inferiority within a 3 pp margin).
- **Total tasks** = 40 ÷ discordance rate. At an enriched discordance rate of ~0.4 →
  **~100 tasks**; measure the actual rate on the dev pilot and adjust before spending.

**Two-stage procedure.** Stage 1 (dev, ~30 tasks): estimate σ_d and the discordance
rate; freeze the policy config (hash it). Stage 2 (shadow, N from stage 1): the
confirmatory run. This spends real money only once N is known.

**Minimum detectable effect at N ≈ 100 / ~40 discordant:** regret reduction ≈ 0.5 σ_d
(≈ a medium effect); cost reduction ≥ ~15% detectable with wide margin; quality
non-inferiority resolvable to a ~3 pp margin.

---

## 4. Statistical analysis plan

- **Resampling unit = task** (not the individual call). Aggregate the k reps to one
  value per (model, task) first, so the k repetitions never become pseudo-replicates.
  Cluster all resampling by task, and by domain when pooled.
- **C1 (regret superiority):** **Wilcoxon signed-rank** on paired regret differences
  (regret is bounded/skewed — do not assume normality), one-sided. Report the
  **Hodges–Lehmann** median paired difference with a **BCa bootstrap 95% CI**
  (task-clustered, 10,000 resamples). Effect size: **Cliff's δ** / matched-pairs
  rank-biserial. Confirm the p-value with a **paired sign-flip permutation test**
  (exchange arm labels within each pair under H₀) — assumption-light and exact-ish.
- **C2 (cost superiority ≥ 15%):** paired difference in cost-per-successful-task;
  **BCa bootstrap** one-sided CI vs the 15% margin (cost is heavy-tailed → bootstrap,
  not t-test).
- **C3 (quality non-inferiority, margin 3 pp):** **McNemar** on paired binary
  threshold-success; non-inferiority via the CI of the paired proportion difference
  (Wilson / bootstrap) lying above −3 pp. **Report quality both ways: abstention-as-
  failure and abstention-as-correct-deferral** (a routed-to-human abstention is not a
  wrong answer).
- **Bootstrap vs permutation:** **permutation for p-values** (exact under label
  exchangeability), **BCa bootstrap for CIs** (better small-sample coverage on skewed
  metrics). Use both; they answer different questions.
- **Multiplicity:** the three confirmatory contrasts use **fixed-sequence gatekeeping**
  (no correction needed). Any *exploratory* per-class breakdown uses **Benjamini–Hochberg
  FDR at 0.10** and is labeled exploratory, never confirmatory.
- **Human-scorer validation gates the automated metrics:** if κ < 0.7 on the validation
  set, the automated score for that class is not trusted and those tasks are
  human-scored before analysis.

---

## 5. Commercial decision threshold — and why

The registry + telemetry + policy + explanation stack has a standing cost (an
eng-owned eval budget, benchmark refresh, drift monitoring). It must clear a hurdle over
static routing:

- **Headline: ≥ 15% reduction in cost-per-successful-task, sustained, vs the enterprise's
  current default** — with quality non-inferior (within 3 pp) and regret ≥ 20% below a
  static table. **Why 15%:** below ~10% the annual maintenance cost of the pipeline
  plausibly exceeds the savings at typical enterprise volumes, and a 5–10% edge is inside
  the measurement error at N ≈ 100 (not reliably claimable). 15% sits **above the noise
  floor at this N and above the maintenance break-even** for realistic call volumes.
  Above 20% it clears with comfortable margin. **Why 20% on regret vs a table:** if the
  policy is < 20% better than a task→model table an engineer writes in an afternoon, buy
  the table — the machinery is not earning its complexity.
- **This is a *floor*, and the enterprise should re-derive it from its own numbers:**
  threshold ≈ (annual pipeline maintenance cost) ÷ (annual inference spend under the
  default). Publish the arithmetic; do not treat 15% as universal.
- Quality can **never** be traded for cost here: C3 non-inferiority is a hard gate, not a
  weighted term.

---

## 6. Failure modes → mitigations (every realistic misleading positive)

| Misleading positive | Mitigation baked into the protocol |
|---|---|
| Provider update / model aliasing / silent drift | **Version-lock** dated model IDs; run a **canary probe set at start and end** and abort/flag on drift; complete the whole run inside a **≤1-week window**. |
| Prompt leakage / benchmark contamination | **Freshly synthesized / private documents**, not public benchmarks; contamination probe (ask for verbatim continuation) to check memorization; vary surface form. |
| Task imbalance | **Stratify + balance by class**; report per-class; aggregate under a **pre-declared class mix**. |
| Overfitting the policy | Strict **dev/shadow split**; tune only on dev; **freeze + hash the policy config** before touching shadow; all confirmatory claims are shadow-only. |
| Selection bias in task choice | **Pre-register the task-generation rule**; enrichment toward boundary tasks is a *declared rule*, not cherry-picking; report the generator. |
| Cost mismeasurement | Use **billed token counts from API responses**, include cache/preflight/retry; charge G's preflight; reconcile against the provider invoice. |
| Human-review inconsistency | **Blind** review (arm/model hidden); **≥2 raters** on the validation subset; report κ; adjudicate disagreements. |
| Telemetry feedback loop | **Freeze the telemetry snapshot** from dev for the whole confirmatory run — no online adaptation; the loop is a deployment risk, out of scope for the falsification test (stated, not hidden). |
| Self-referential oracle / scorer bias | Oracle = best *actual* outcome among eligible, scored by the **same** scorer for all arms; **validate the scorer against blind human labels** (κ ≥ 0.7) so a style-biased scorer can't manufacture a winner. |
| Ties inflating/deflating power | Handle zero-difference pairs correctly (Wilcoxon drops them); **report the discordance rate** as a first-class result. |
| Latency confound (time-of-day/load) | **Randomize + interleave** call order across arms/models; run in one window; report p50/p95; never compare latency across different times. |
| Multiple-comparisons fishing | **Pre-registration** + fixed-sequence gatekeeping; only the 3 contrasts are confirmatory. |
| Optional stopping / peeking | **Fixed N** from the power analysis; if monitoring is required, use an **O'Brien–Fleming alpha-spending** boundary — no ad-hoc peeking. |

---

## 7. The one-week protocol (executable on this package's `harness.py`)

**Pre-run (before any spend):** pick 4–5 version-locked models across ≥2 providers;
re-verify `registry.json` pricing/context against live endpoints; generate the corpus
with the pre-declared, boundary-enriched generator; split dev(30)/shadow(100); **freeze
and hash the policy config and the corpus**; set `PILOT_MAX_SPEND_USD`.

- **Day 1 — dev pilot.** Run the counterfactual on the 30 dev tasks (k=3). Estimate σ_d
  and discordance rate → finalize shadow N. **Futility gate:** if discordance ≈ 0 (policy
  ≈ static rules), **stop** — an informative near-null; report it and do not spend on the
  shadow set.
- **Day 2 — freeze + canary.** Lock policy/telemetry snapshot; record start-of-run canary
  fingerprints for every model.
- **Days 3–4 — confirmatory shadow run.** Counterfactual over 100 shadow tasks (k=3),
  randomized/interleaved call order, cost-guarded. Record billed tokens, latency, retries,
  raw + normalized separately.
- **Day 5 — human validation.** Blind 2-rater scoring of the 50-item validation set + 15%
  task sample; compute κ; adjudicate; gate the automated metrics.
- **Day 6 — analysis.** Run the §4 tests in fixed sequence (C1→C2→C3); bootstrap CIs;
  effect sizes; per-class exploratory breakdown (FDR-labeled). End-of-run canary check;
  abort/flag on drift.
- **Day 7 — verdict.** Grade against `FALSIFICATION_PREREGISTRATION.md`. Write the
  result (pass / fail / near-null) with CIs, the discordance rate, the human-κ, and the
  reconciled invoice cost.

**Stopping criteria:** fixed N (no peeking); dev-stage **futility stop** on near-zero
discordance; **hard cost-cap** abort. Report whichever fires.

---

## 8. Pre-registration checklist (freeze before spending)

- [ ] Model list with dated version IDs + canary probe set.
- [ ] Corpus generator rule + dev/shadow split + config hashes.
- [ ] Primary endpoint (regret), the 3 contrasts, fixed-sequence order.
- [ ] Effect-size targets, N, power, and the two-stage variance plan.
- [ ] Analysis code (tests, bootstrap seed, task-clustered resampling).
- [ ] Commercial thresholds (15% cost / 3 pp non-inferiority / 20% vs table) with the
      enterprise-specific arithmetic.
- [ ] Human-review plan (blind, 2 raters, κ ≥ 0.7 gate).
- [ ] Cost cap and stopping/futility rules.

**One sentence:** run every one of 4–5 version-locked models on ~130 boundary-enriched,
freshly-synthesized document tasks (×3 reps, one counterfactual pass), then test — in a
fixed C1→C2→C3 sequence on ~40 discordant matched pairs, with permutation p-values and
bootstrap CIs, blind-human-validated scoring, and a hard $100 cap — whether the policy
beats a static table on regret, beats always-strong on cost by ≥15%, and holds quality
non-inferior; if it can't clear that in one coherent domain, the hypothesis is falsified.
