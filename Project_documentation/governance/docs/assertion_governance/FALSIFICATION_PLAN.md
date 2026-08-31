# Falsification Plan (PREREGISTERED)

*Phase 3. We attempt to REJECT Assertion Governance before implementing it. For every null
hypothesis "an existing technique already solves this", we specify an experiment capable of
disproving AGE and a preregistered kill-criterion. These thresholds are fixed BEFORE the dataset
and engine are built, and are not tuned to observed results.*

## Preregistered decision rule (applies to all H0)

Let `ground_truth` be the human-rubric disposition per item (Phase 6, frozen). Let each method's
score be its agreement with ground truth on the **held-out eval split**, and separately its
**unsupported-assertion escape rate** (the safety-critical metric: an unsupported claim delivered
as ALLOW).

- **AGE is REJECTED as an independent layer** if the best single baseline **or** the combined
  baseline G (grounding+entailment, dev-tuned) matches AGE within **Δ ≤ 0.03** on the primary
  metric (disposition agreement) **and** within **Δ ≤ 0.02** on unsupported-escape rate. If a
  cheaper existing technique ties AGE, AGE is redundant.
- **AGE is SUPPORTED as an independent layer** only if it **exceeds every baseline** by **> 0.05**
  on disposition agreement **or** reduces unsupported-escape **> 0.03** below the best baseline,
  **and** this margin is not attributable to a single feature a baseline could trivially add.
- **AGE is SUPPORTED ONLY FOR HIGH-RISK** if the margin above holds on the high-risk subset but
  vanishes (falls within the reject band) on the low-risk subset.
- **NOT ENOUGH EVIDENCE** if results are mixed/underpowered (dataset too small, high variance).

Baselines are **tuned on the dev split** to give each its best shot; AGE is **not** tuned on eval.

## Null hypotheses and disproving experiments

### H0-1: Confidence scores already solve it
- **Experiment:** Baseline B = threshold on the model's stated confidence (dev-tuned threshold).
  Include items that are **confident-but-unsupported** and **unconfident-but-supported**.
- **Kills AGE if:** B's disposition agreement is within Δ ≤ 0.03 of AGE.
- **Kills H0 if:** B fails specifically on confident-but-unsupported items (delivers them as ALLOW)
  where AGE qualifies/rejects — i.e. confidence is orthogonal to evidence support.

### H0-2: Grounding already solves it
- **Experiment:** Baseline C = threshold on evidence-support (grounding) score.
- **Kills AGE if:** C within Δ ≤ 0.03.
- **Kills H0 if:** C cannot separate QUALIFY from REJECT from ESCALATE (grounding gives a scalar,
  not the graded action), and mishandles conflicting-vs-missing evidence.

### H0-3: Entailment already solves it
- **Experiment:** Baseline D = NLI 3-way (ENTAIL→ALLOW, CONTRADICT→REJECT, NEUTRAL→INDETERMINATE).
- **Kills AGE if:** D within Δ ≤ 0.03. **This is the strongest single baseline.**
- **Kills H0 if:** D has no QUALIFY (partial support), no ESCALATE (conflict/high-risk), and is
  risk-insensitive — so it mislabels partial-support and high-risk items.

### H0-4: Better prompting removes the need
- **Experiment:** simulate a "strong-model" condition by **improving input quality** (higher base
  confidence + cleaner evidence) and re-measuring unsupported-escape with NO governance (Baseline
  A). If escape → 0 with better inputs, governance is unnecessary.
- **Kills AGE if:** unsupported-escape under Baseline A on the "strong-model" split ≤ 0.02.
- **Kills H0 if:** overconfident-unsupported assertions persist regardless of input quality (a
  stronger model still overclaims on missing/conflicting evidence).

### H0-5: Constitutional prompting subsumes it
- **Experiment:** model as a fixed *generation-time* qualifier that applies surface hedging rules
  (Baseline E, rule-based qualification) without consulting evidence.
- **Kills AGE if:** E within Δ ≤ 0.03.
- **Kills H0 if:** E hedges uniformly (over-qualifies supported claims → high false-qualification
  rate) because it is evidence-blind.

### H0-6: ActionGate already covers it
- **Experiment:** map the assertion task onto an action-authorization frame and measure whether an
  action-style gate produces correct assertion dispositions.
- **Kills AGE if:** an ActionGate-style rule reproduces the dispositions within Δ ≤ 0.03.
- **Kills H0 if:** action authorization is about *permission to act*, not *support to state*; it has
  no QUALIFY-rewrite and treats "state a claim" as out-of-scope. (Conceptual + measured mismatch.)

### H0-7: TAP authority resolution already covers it
- **Experiment:** Baseline F = TAP-style authority resolution mapped to dispositions (the Shadow
  Pilot's exact proxy).
- **Kills AGE if:** F within Δ ≤ 0.03.
- **Kills H0 if:** F answers "which authority governs", scoring poorly where the issue is *evidence
  support of a claim* with no authority dimension — reproducing the Shadow Pilot's semantic gap.

### H0-8: AGE is only renamed uncertainty estimation
- **Experiment:** correlate AGE dispositions with a pure uncertainty scalar; test whether a
  monotone threshold on uncertainty reproduces AGE's 5-way output.
- **Kills AGE if:** a single uncertainty threshold reproduces AGE dispositions (rank correlation
  high AND agreement within Δ ≤ 0.03) → AGE is uncertainty estimation with labels.
- **Kills H0 if:** AGE's disposition is NOT monotone in any single uncertainty scalar because it
  depends on the *interaction* of support × claim-strength × risk (e.g. same uncertainty →
  different disposition at different risk).

## Anti-circularity safeguards

1. **Ground truth is independent of AGE's logic.** Dataset dispositions come from a documented
   human-judgment rubric (Phase 6), authored and frozen BEFORE the engine. If AGE merely re-
   implements the rubric, its "win" is definitional — so we additionally require the margin to come
   from the *interaction* structure (H0-8) and report AGE-vs-Baseline-G separately as the decisive
   comparison.
2. **Baselines get their best shot** (dev-tuned thresholds); AGE is frozen and un-tuned on eval.
3. **Adversarial-to-AGE items** are included: cases where AGE's simple logic is expected to fail,
   so the dataset can punish AGE, not just reward it.
4. **The decisive test is AGE vs Baseline G**, not AGE vs the weak baselines. Beating no-governance
   is trivial and not evidence for an independent layer.

## What we will report even if it kills AGE

If Baseline G (or any baseline) ties AGE within the reject band, we will report **REJECT / NOT AN
INDEPENDENT LAYER** and say so plainly. Negative findings are the expected default until the margin
is demonstrated.
