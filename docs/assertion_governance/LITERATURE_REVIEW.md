# Literature Review — Techniques Adjacent to Assertion Governance

*Phase 1. A conceptual survey (from established knowledge, not an exhaustive citation index) of
techniques that touch the question "should this model output be delivered as written?". For each:
what it solves, what it leaves unsolved, and where it would overlap or differ from a proposed
Assertion Governance layer. The point is to locate the gap — if there is one.*

## The techniques

### Constitutional AI / principle-based self-critique
- **Solves:** steering *generation* toward stated principles (harmlessness, honesty) via self-
  critique and RLAIF. Shapes what the model *produces*.
- **Unsolved:** operates *during* generation, not as a post-generation delivery gate; principles
  are baked into weights/prompts, not applied as an auditable per-output disposition with evidence.
- **Overlap:** shares the "honesty/qualification" intent. **Differs:** AGE governs *delivery of a
  fixed output* against *this request's evidence and risk*, producing an auditable disposition —
  not a training signal.

### Guardrails (rule/classifier output filters)
- **Solves:** blocking outputs that match unsafe patterns (PII, toxicity, jailbreaks, format).
- **Unsolved:** guardrails are largely *content-category* gates (is this class of text allowed?),
  not *epistemic* gates (is this claim supported enough to state as written?).
- **Overlap:** both are post-generation gates. **Differs:** AGE's question is epistemic
  (support/qualification), not category membership; and AGE can *transform* (QUALIFY), not only
  block.

### Grounding / attribution
- **Solves:** checking whether output is supported by / attributable to provided sources;
  citation generation.
- **Unsolved:** grounding yields a *support score or attribution set*; it does not decide the
  *delivery action* (allow vs qualify vs escalate) nor how to rewrite an overclaim, nor how risk
  class changes the threshold.
- **Overlap:** grounding is a core *input* to AGE. **Differs:** AGE consumes grounding and adds the
  decision layer + qualification transform + risk sensitivity.

### NLI / entailment
- **Solves:** does evidence *entail*, *contradict*, or is *neutral* to the claim (a 3-way label).
- **Unsolved:** entailment is per-claim and evidence-relative; it does not itself set the delivery
  disposition, handle "evidence missing" vs "evidence conflicting" distinctly, or calibrate to risk.
- **Overlap:** entailment is arguably the *closest* single technique — CONTRADICTION≈REJECT,
  NEUTRAL≈INDETERMINATE, ENTAILMENT≈ALLOW. **Differs:** entailment has no QUALIFY (partial-support
  rewrite), no ESCALATE (human-review trigger), no risk weighting, no missing-vs-conflicting split.
  **This is the key baseline to beat (Baseline D / G).**

### Confidence estimation / calibration
- **Solves:** estimating and calibrating the model's probability of correctness (logits, verbalized
  confidence, ensembles).
- **Unsolved:** confidence is a *scalar about the model*, not about *evidence support of this
  specific claim*; a confidently-stated but unsupported claim scores high. Calibration improves the
  scalar, not the delivery decision.
- **Overlap:** confidence is an input signal. **Differs:** AGE's core case — the *overconfident but
  unsupported* assertion — is exactly where confidence *fails* and evidence-support is needed.

### Hallucination detection
- **Solves:** flagging fabricated/unsupported spans (self-consistency, retrieval cross-check,
  detectors).
- **Unsolved:** detection is binary-ish (hallucinated or not); it does not prescribe the graded
  delivery response (qualify vs reject vs escalate) or preserve/rewrite the supported remainder.
- **Overlap:** "unsupported claim" detection feeds AGE. **Differs:** AGE is the *response policy*
  on top of detection.

### Truthfulness benchmarks (TruthfulQA, FActScore, etc.)
- **Solves:** *measuring* truthfulness/factuality of models at eval time.
- **Unsolved:** benchmarks score models; they are not a runtime per-output governor.
- **Differs:** AGE is a runtime layer; benchmarks are its measuring stick, not its mechanism.

### Selective prediction / abstention
- **Solves:** letting a model *abstain* when uncertain (reject option, risk-coverage curves).
- **Unsolved:** abstention is typically binary (answer/abstain) driven by a confidence threshold;
  it lacks the qualify-rewrite and the evidence-relative + risk-relative graded dispositions.
- **Overlap:** ESCALATE/INDETERMINATE resemble abstention. **Differs:** AGE adds QUALIFY (deliver a
  weakened but still useful claim) rather than only answer-or-abstain, and grounds the decision in
  evidence support, not just self-confidence.

### Human uncertainty communication / hedging
- **Solves:** guidance on expressing uncertainty (hedges, confidence language).
- **Unsolved:** it's a *style* prescription, not a mechanism that decides *when* and *how much* to
  hedge based on evidence and risk.
- **Overlap:** QUALIFY output *is* calibrated hedging. **Differs:** AGE decides it mechanically and
  auditably.

### AI assurance / safety layers
- **Solves:** organizational assurance, red-teaming, policy layers around deployment.
- **Unsolved:** broad and process-oriented; not a concrete per-assertion delivery function.
- **Differs:** AGE is one concrete assurance *mechanism* at the delivery boundary.

### Authority resolution (TAP, this repo)
- **Solves:** which documented *authority governs a situation* (jurisdiction/precedence/exceptions).
- **Unsolved:** it answers a *governance-authority* question, not "is this *claim* supported enough
  to state?"; the Shadow Pilot documented this exact **semantic gap** when it used TAP-E4 as an
  assertion proxy.
- **Overlap:** both are "governance." **Differs:** authority ≠ assertion support. AGE is precisely
  the layer the Shadow Pilot found *missing*.

## Where is the gap?

Every technique above supplies a **signal** (confidence, support, entailment label, authority) or a
**binary gate** (block/abstain). None supplies the **graded delivery decision** that:

1. distinguishes **ALLOW / QUALIFY / REJECT / ESCALATE / INDETERMINATE** (five actions, not a scalar
   or a binary),
2. **transforms** an overclaim into a supported qualified claim (QUALIFY), preserving the supported
   remainder rather than blocking wholesale,
3. is **evidence-relative** (support of *this* claim, not model self-confidence),
4. is **risk-relative** (the same support level yields different dispositions in medical vs casual
   domains),
5. distinguishes **missing** evidence from **conflicting** evidence from **contradicting** evidence,
6. emits an **auditable disposition + reason + qualification**, not just a score.

## The honest counter-position (to be tested, not assumed)

A skeptic's claim, which Phase 3 must try to confirm: *"AGE is just entailment + grounding with a
threshold table and a risk multiplier — i.e. Baseline G with extra labels."* If a well-tuned
**combined grounding+entailment baseline (G)** matches AGE, then AGE is **not** an independent layer
— it is a presentation of existing signals. The literature does **not** settle this; only the
evaluation (Phase 9) can. This review establishes that a *gap in the decision layer* plausibly
exists; it does **not** establish that filling it requires a new architectural layer.
