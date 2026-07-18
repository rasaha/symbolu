# B1.12 BSR Crossover — Disagreement Audit

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`

Follow-up to `B1_12_SYMBOLIC_RESONANCE_MULTILLM_REPORT.md` §6. **Central question:** are the two LLMs' scoring
disagreements caused by *correctable* prompt/rubric ambiguity, or are symbolic-resonance judgments *inherently*
model-dependent? Source: the archived per-component score files (`run_a_scores.json`, `run_b_scores.json`), which
reproduce the report aggregates exactly (overall means A = 37.71 / B = 48.65).

**Answer: predominantly correctable.** Two identifiable, fixable causes — a global scorer-strictness offset and one
rubric specification gap — account for the disagreement. There is no sign of large, unstructured, irreducible
divergence.

---

## 1. Shape of the disagreement (all 54 components)

| Absolute score gap | # components |
|---|---|
| 0 (exact) | 27 |
| 25 (one step) | 24 |
| 50 (two steps) | 3 |
| ≥ 75 | 0 |

- **94.4% within one 25-point step.** No component disagreed by more than two steps; none by three+.
- **The disagreement is directional, not random:** Qwen-as-scorer (Run B) > Mistral-as-scorer (Run A) on **24**
  components, equal on **27**, and Mistral > Qwen on only **3**. Mean signed B − A = **+11.11**. A random
  labelling disagreement would be roughly symmetric; this is a one-sided *bias*.

## 2. Cause 1 — a global scorer-strictness offset (correctable by calibration)

Restricting to the **27 components where both models chose the identical `final_relationship`** (so relationship
choice is held constant), Qwen still scores **+10.19** higher on average (mean abs diff 13.89). The generosity gap
is therefore **not** a by-product of disagreeing about the relationship — it is a baseline calibration difference:
given the same evidence and the same relationship, Mistral maps it to a lower anchor than Qwen.

Worked example — **sneha #1** (affection ↔ *moha*, blind attachment), both authors' evidence agrees "affection can
lead to blind attachment/infatuation":
- Mistral scores **25**: "loss of rationality requires substantial qualification."
- Qwen scores **75**: "affection can naturally lead to blind attachment, though specific examples stretch slightly."
- Same substantive claim; the only difference is *how much* the gloss's extra specifics (thief, nostalgia) should
  dock the score. That is a calibration decision, not a factual disagreement.

**Fix (future instrument, not applied here):** anchor each of the five scale points with worked exemplars, and/or
apply a per-model calibration offset estimated on a held-out set. Expected to remove most of the ~10-point bias.

## 3. Cause 2 — an unspecified mapping of `opposition`/`resolution` to the score scale (correctable by spec)

Mean BSR by final relationship:

| final_relationship | Mistral (A) mean / n | Qwen (B) mean / n |
|---|---|---|
| opposition | **40.9 / 11** | **66.7 / 6** |
| natural_consequence | 32.1 / 7 | 58.3 / 3 |
| implication | 30.4 / 23 | 44.0 / 29 |
| constitutive_property | 50.0 / 2 | 62.5 / 2 |
| characteristic_expression | 56.8 / 11 | 52.1 / 12 |
| embodiment | — / 0 | 50.0 / 2 |

The largest per-relationship split is **`opposition`: a 25.8-point gap** (Qwen 66.7 vs Mistral 40.9). The rubric
defines resonance as how naturally the bare word *accounts for* the mapping and lists `opposition` as a valid
relationship, but it never states whether a **clean opposition** should score *high* (the word relates to the
mapping strongly, via opposition) or *low* (the word does not embody/imply the mapping). The two models filled the
gap with opposite conventions.

Worked example — **santoṣa #1** (contentment ↔ *moha*, blind attachment):
- Qwen assigns `opposition` and scores **75** — treating a strong, clean opposition as high resonance.
- Mistral assigns `implication` and scores **25** — treating the same as failure-to-account.
- Both agree on the *content* (contentment is a balanced state, moha is irrational fixation; they are opposed).
  They disagree only on how "opposed" cashes out on a 0–100 "accounting-for" scale — a **specification gap**.

**Fix (future instrument, not applied here):** amend the rubric to state explicitly how `opposition`/`resolution`
relationships map to the scale (e.g. score the *strength/cleanliness of the opposition*, or route oppositional
relationships to a separate axis). This single clarification would resolve the biggest structured disagreement.

## 4. Cause 3 — supplementation firewall not enforced at scoring (correctable by prompt)

The one remaining ≥50-gap component is **dīpa #1** (lamp ↔ *ghṛṇā*, hatred/revulsion): Mistral **0**, Qwen **50**.
Both models' *opposing_evidence* says a lamp does not inherently cause hatred. Mistral therefore scores 0
("requires symbolic inversion"). Qwen nonetheless constructs an implication chain — "a lamp reveals unpleasant
truths → revulsion" — and scores 50. That chain is precisely the **post-hoc story / semantic supplementation** the
rubric forbids; Qwen's own adjudication concedes it is "not a direct or constitutive property of the lamp" yet does
not zero the score. This is the 0-vs-50 anchor ambiguity ("cannot support without external meaning" vs "plausible
but requires interpretation") plus weak enforcement of the no-supplementation rule at scoring time.

**Fix (future instrument, not applied here):** add an explicit scorer instruction — "if accounting for the mapping
required inventing a causal/narrative chain absent from the bare word, score 0, regardless of how plausible the
chain is" — and tighten the 0/25 boundary with exemplars.

## 5. Verdict of the audit

| | |
|---|---|
| Disagreements > 1 step | 3 / 54 (5.6%), each traceable to a named cause |
| Directional bias | systematic (+11.1 Qwen over Mistral), survives relationship agreement (+10.2) |
| Largest structured split | `opposition` scoring (25.8 pts) — a rubric spec gap |
| Classification | **correctable rubric/prompt ambiguity + calibration offset**, not demonstrated inherent model-dependence |

The evidence points to a **fixable instrument**, not to symbolic-resonance judgment being irreducibly
model-dependent. The `SIGNIFICANT_ROLE_DEPENDENCE` verdict stands for the **current** (v1) instrument, but its
drivers are structured and named: a global strictness offset (Cause 1), an unspecified opposition-scale convention
(Cause 2), and under-enforced supplementation control (Cause 3).

## 6. Recommended sequence (unchanged discipline)

1. **Do not mutate the frozen v1 prereg or freeze.** The fixes above are proposals for a *future* instrument
   version; v1's verdict is recorded as-is.
2. If a v2 instrument is preregistered with Causes 1–3 addressed, re-run the **same** frozen 20-word crossover and
   compare role-dependence directly — that isolates whether the fixes actually reduce evaluator dependence.
3. Only after the instrument is demonstrably role-stable does an LLM-adjudicated resonance score become usable as a
   B1.12 evaluator. Instrument reliability is a prerequisite to, not a substitute for, any claim about the mappings.

## 7. Provenance

`run_a_scores.json` / `run_b_scores.json` are the verbatim per-component outputs from the completed RunPod
execution (Qwen3-32B × Mistral-Small-3.1-24B, deterministic, seed 20260714). Every number in this audit is
recomputed from them. No frozen input, prereg, freeze, or prior artifact was modified.
