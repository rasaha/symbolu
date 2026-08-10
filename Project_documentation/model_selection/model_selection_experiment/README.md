# Model Selection Policy — Empirical Experiment

**A self-contained, deterministic experiment that tests one question:**
*does a governed Model Selection Policy produce measurable routing value versus
simpler strategies — and does bounded self-assessment add marginal value?*

This package is the empirical follow-up to three prior research documents in the
repository root:

- `MODEL_SELECTION_POLICY_ENGINE_SPEC.md` — the policy design under test.
- `CAPABILITY_NEGOTIATION_SELF_ASSESSMENT_RESEARCH.md` — predicts self-assessment
  helps only at cold start; the G-vs-F ablation here tests that prediction.
- `CAPABILITY_DISCOVERY_PROTOCOL_RESEARCH.md` — argues capability data belongs in
  an enterprise registry; the registry here is that idea, exercised.

It imports **nothing** from the production tree (Hybrid LLM, ActionGate, TAP,
KVPro, Cloud Scaling). Pure Python standard library. No network, no external API.

---

## How to run

```bash
cd model_selection_experiment
python3 build_data.py         # regenerate versioned data artifacts (deterministic)
python3 harness.py            # run all arms x regimes, write results/
python3 -m pytest tests -q    # 15 deterministic behavior tests
```

`harness.py` prints a summary table and writes:
- `results/aggregate_metrics.json` — all metrics, all arms, all regimes, ablation.
- `results/decision_records_FG_mature.json` — every policy decision record.
- `results/decision_record_samples.json` — annotated adversarial-case records.

Read the conclusions in `FALSIFICATION_ASSESSMENT.md` and `ARCHITECTURE_NOTE.md`.

---

## What is measured

Seven routing arms:

| Arm | Strategy |
|---|---|
| A | Fixed default model (no constraint filtering) |
| B | Strongest candidate, ignoring cost/latency **and** constraints |
| C | Cheapest eligible (hard constraints, then lowest cost) |
| D | Static task-class → model rules (constraint-aware) |
| E | Benchmark-only (hard constraints, then highest measured quality) |
| **F** | **Policy engine without self-assessment** |
| **G** | **Policy engine with bounded self-assessment** |

The critical marginal comparison is **G vs F**, run across three telemetry
regimes: **cold** (no telemetry), **partial** (6 samples/cell), **mature** (80).

Primary metric: **selection regret** = oracle utility − achieved utility, where a
hard-constraint-violating pick is charged a large penalty. Secondary metrics:
constraint-violation rate, quality-threshold success, cost per successful task,
p50/p95 latency, fallback/abstention rates, unnecessary strongest-model use,
explanation completeness, routing stability.

---

## Files

| File | Role |
|---|---|
| `common.py` | deterministic hash-noise, IO, versions, constants |
| `build_data.py` | emits the four versioned data artifacts (below) |
| `simulator.py` | ground-truth world: eligibility, outcomes, telemetry, advisory, oracle, regret |
| `policy.py` | the smallest defensible policy interpreter + explanation record |
| `baselines.py` | arms A–G |
| `metrics.py` | scoring, explanation-completeness check |
| `harness.py` | runs everything, writes results |
| `tests/test_policy.py` | 15 deterministic tests (8 mandated behaviors) |
| `data/ground_truth_v1.json` | TRUE model behavior — simulator/oracle only |
| `data/registry_v1.json` | policy-visible registry: declared + measured, with provenance |
| `data/corpus_v1.json` | 37 tasks with constraints, priorities, thresholds |
| `data/policy_v1.json` | declarative weights, fusion confidences, precedence, field rules |

---

## Synthetic assumptions (explicit — read before trusting any number)

This is a **synthetic** first-phase experiment. Its results are **conditional on
its generative model**, stated here so they are not over-read:

1. **Cost and latency are accurate facts for every arm.** No arm gets a private
   advantage there. The only *uncertain* quantity is task **quality**, which each
   arm estimates from whatever evidence it is allowed to use. This is deliberate:
   the experiment tests *evidence use and constraint handling*, not cost lookup.
2. **True quality** of a (model, task) is the weighted average of the model's true
   capability vector over the task's required capabilities, minus a context-rot
   penalty as input approaches the model's true effective context.
3. **Declared capability tiers are optimistically biased** (`+0.12`), as real spec
   sheets are — so leaning on declared evidence is penalized, not rewarded.
4. **Benchmark evidence is noisy (`±0.08`) and has coverage gaps (28% of cells
   missing).** No arm has complete measured evidence.
5. **Telemetry** is a noisy view of truth whose confidence grows with sample count
   (the regime knob). It is the highest-trust quality signal when mature.
6. **Self-assessment (arm G)** is a bounded, overconfident (`+0.06` bias), noisy
   (`±0.10`) read of a model's own true suitability, restricted to self-knowledge
   fields; it is charged a preflight cost and latency.
7. **Declared context can overstate true effective context** (e.g. 200k declared /
   128k effective), creating a "context trap." All arms filter on *declared*
   context — none truly detects the gap. See `FALSIFICATION_ASSESSMENT.md` §
   *Limitations* for why this matters.

**The experiment demonstrates whether the policy correctly *uses* evidence and
enforces constraints. It does NOT prove that real-world benchmarks/telemetry are
predictive of real quality — that requires real telemetry and is out of scope for
phase one.** Claims are bounded accordingly.
