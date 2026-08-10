# Agentic Framework — Trust-Observable Architecture (Next Generation)

**Status:** Architecture & product strategy. No implementation. Supersedes the CG-as-governance
framing for the *product* path; the CG research plan
(`AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md`) continues only as research.

**Audit basis (established, not re-argued here):** Vritti/Guna/Kosha are unsupervised read-outs;
Guna entropy measures guna-imbalance (not predictive uncertainty); Vritti risk is a heuristic
sum over an unsupervised softmax slice; Kosha entropy is inactive in the single-state path; JEPA
residual is a hand-coded rulebook that largely re-encodes tool risk; Bhava→phase→phase_adapter is
the only state→logit write path and is small/gated/unsupervised for governance; raw next-token
entropy outperforms all CG-derived governance signals; the confidence-risk gap has demonstrated
practical value.

---

## 1. Direct recommendation

**Yes — evolve Agentic Framework into a supervised, evidence-gated trust-observable architecture,
and keep all current CG-state governance signals research-only and off by default.**

Four positions:

1. **Phase 1 (trust validation from proven signals) becomes the primary production architecture
   now.** It is ~80% already present in the gateway (raw entropy, confidence-risk gap, risk
   taxonomy, tool validity, approvals, audit, budget, escalation tiers). The new work is
   *formalization*: a clean observable **registry** + an **asymmetric, staged decision tree** — not
   a greenfield rebuild.
2. **Phase 2 (supervised observables) is developed in `experiments/`, promoted by evidence.**
   Observables enter the product **one at a time**, each only after it beats the proven baseline on
   held-out confident-unsafe scenarios. No big-bang module.
3. **Phase 3 (CG candidates) may compete, but are not assumed useful.** The input/action-derived
   CG labels are mostly **standard observables renamed**; they stay **internal/explanatory** and
   must clear the same promotion bar as anything else (and will likely lose to plainly-named
   equivalents).
4. **Phase 4 (CG wrapper) is a separate track.** Bhava→phase→phase_adapter is **behavior
   modulation**, evaluated on generation quality, **never wired into governance**. Trust validation
   stays **read-only**.

The discipline that makes this different from the CG failure: **validators gate signals (they do
not sum with them); authority is earned by evidence; nothing reaches the production decision before
it beats the cheap baseline.**

---

## 2. Proposed architecture (module structure)

```
agentic/agentic_framework/trust/        # PRODUCT — only promoted, proven observables land here
  validators/        proven, may veto/cap (raw entropy, tool validity, permission validity,
                     action-risk taxonomy, confidence-risk gap)
  observables/       registry: each tagged {hard_veto | advisory | signal} × {proven | provisional}
                     with provenance + fail-closed contract
  decision/          the asymmetric, staged, weakest-link decision tree (allow/confirm/block)
  audit/             per-validator verdict trace (explainable governance)

experiments/trust_signal/               # RESEARCH — candidates live here until promoted
  observables/       input/action/model/outcome candidates + offline probes
  cg_candidates/     input/action-derived CG-labeled features, competing via the same pipeline
  hidden_heads/      R1/R2 heads — GATED on the one retained D1 probe
  benchmarks/        confident-unsafe twins + AgentDojo/InjecAgent + hallucinated-tool/permission
  promote.py         conditional-on-fooled AUROC · DeLong · marginal-value-over-baseline gate
```

**Invariant:** the product package (`agentic/.../trust/`) contains **only** observables that have
cleared promotion. Everything unproven is advisory/logged in `experiments/`. This mirrors the
existing `experiments/signal_gov → gateway` pattern and prevents unproven signals (the CG failure
mode) from acquiring decision authority.

---

## 3. Decision tree (locked specification)

```
0. HARD VETOES (proven, rule-based correctness checks)
     invalid/hallucinated tool · invalid permission claim · unapproved destructive   → BLOCK
1. VALIDATORS, entered at their PROVEN AUTHORITY, aggregated by MAX-SEVERITY (weakest link)
     proven validator  UNSAFE                                → BLOCK
     proven validator  UNSURE                                → CONFIRM / ESCALATE
     provisional validator UNSAFE                            → ESCALATE + log (NEVER block)
2. TRUST SIGNAL (model-emitted; if absent → validators decide alone, conservatively)
     admits doubt / refuses   → may LOWER trust   (credible direction)
     claims "safe / confident" → ~0 upgrade        (gameable direction)
3. COMPLIANCE / MISMATCH (the confidence-risk gap, generalized)
     validator/input says risky  ∧  model claims safe  ∧  tool ≥ write   → CONFIRM / BLOCK
     validators SAFE  ∧  no admitted doubt                               → ALLOW
```

**Five non-negotiable principles:**
- **Hard gates first** — categorical violations are vetoes, not penalties.
- **Asymmetry** — a confident claim can *lower but never raise* trust (claims are free to assert).
- **Staged authority** — unproven observables *advise/escalate*, they do not *block*.
- **Weakest-link aggregation** — the most severe proven validator dominates (no averaging).
- **Fit, don't sum** — fitted/calibrated weights for proven terms only; no additive sum of
  mixed-quality, self-reported signals.

---

## 4. Promotion pipeline

A candidate observable advances through four stages, each with a rising evidence bar. **Hard
vetoes are exempt** — they are deterministic correctness checks (tool validity,
unapproved-destructive), veto by definition, not by statistics.

| Stage | Authority in the decision | Evidence required to enter |
|---|---|---|
| **Research** | none (offline only) | defined + labeled; offline probe shows fooled-subset AUROC > chance on the probe set |
| **Advisory** | logs; may *escalate*, never block | adds marginal fooled-subset AUROC over the proven baseline on a **held-out** split (single draw); correct provenance + fail-closed behavior |
| **Validator** | may *cap trust / CONFIRM* | **DeLong-significant** marginal value over (risk taxonomy + raw entropy + tool validity), **replicated on a 2nd independent draw**; operational lift (catch@budget at ≤ over-block); calibrated |
| **Veto** | may *BLOCK* | all of the above **plus** low over-block at the operating point, stability across seeds/checkpoints, a documented failure mode, and a rollback path |

**Circularity guard:** input/action observables must prove out on **realistic** injections
(AgentDojo/InjecAgent), not the templated twins whose oracle labels they can re-derive.

**Marginal-value rule (applies at every stage):** the observable must beat the baseline *that
already exists*. Re-deriving raw entropy through a detour is not promotion.

---

## 5. Trust-score design (the mathematically correct structure)

Trust is **not** a single additive number. It is a **validator-compliance decision with a
calibrated residual score for the graded zone.** Three layers:

1. **Hard vetoes — boolean, outside the score.** A categorical violation sets the decision to
   BLOCK regardless of any score.
2. **Validator caps — weakest-link.** Each proven validator emits a calibrated risk/uncertainty
   estimate; trust is **upper-bounded by the most severe proven validator** (`trust ≤ min over
   validators`). This is the structural fix for the dilution that sank `internal_risk`: a single
   strong validator cannot be averaged away.
3. **Graded zone — a fitted, calibrated log-odds.** Among items not vetoed or capped, compute a
   **logistic (log-odds) probability of safe-to-auto-execute** over **proven terms only**, with
   weights fit on a held-out split (report the zero-tuning variant too). The model-emitted **trust
   signal enters only as an asymmetric modifier** — it can subtract (admitted doubt) but not add.

Equivalently:
```
if hard_veto:                         decision = BLOCK
trust_cap   = min over proven validators (calibrated)         # weakest link
graded      = logistic(fitted weights · proven_observables)   # calibrated log-odds
trust       = min(trust_cap, graded)  −  doubt_admission_bonus_only
mismatch    = confidence_risk_gap(verbalized_safety, validator_risk, tool_risk)  # first-class trigger
decision    = tree(trust, mismatch)   → allow / confirm / block
```

**Why this and not a sum:** an additive score lets a gameable, self-reported signal buy trust by
volume and dilutes the one informative validator. Capping + fitting + asymmetry removes both
failure modes. The **compliance/mismatch** quantity (the confidence-risk gap = "calibrated
humility") is the single most valuable trigger and should be first-class, not a summand.

---

## 6. Role of supervised observables

| Observable group | Class | Initial authority |
|---|---|---|
| tool validity, permission validity, hallucinated tool/capability (∉ available), unapproved-destructive, action-risk taxonomy | **rule-based** | **hard veto / proven validator** |
| raw entropy, confidence-risk mismatch | **proven model signal** | **validator** (entropy already proven) |
| manipulation/injection/authority/urgency/ambiguity/permission-overclaim (input) | **supervised classifier** | **advisory** → validator on evidence |
| plan-action inconsistency, destructive-action likelihood | **supervised** (harder; labels scarce) | research → advisory |
| hidden-state uncertainty / trust-mismatch head | **supervised** | research, **gated on the D1 probe**; advisory only if it beats raw entropy |
| task-success / correction / override / audit history | **outcome/reputation** | **separate axis** (prior/gate), never summed into per-action risk |

**Notes.** Outcome observables are a *reputation* axis on a different timescale — a trusted-but-
compromised actor must not buy a dangerous action; model them as a prior/gate, not an additive
term. The hidden-state head's only promotion path is **R2 contrastive** (catch what entropy
misses); **R1 (regress entropy) is insurance, not a win.**

---

## 7. Role of CG candidates (Phase 3)

1. **Useful supervised labels?** Marginally. The input/action-derived versions
   (Sattva=clarity, Rajas=pressure, Tamas=ambiguity; Pramana/Viparyaya/Vikalpa/Nidra/Smriti as
   action categories) are **standard observables renamed**.
2. **Redundant with standard observables?** Largely yes — they overlap manipulation_pressure,
   ambiguity, hallucinated-capability, and groundedness.
3. **Explanatory value only?** Mostly. They are a *presentation taxonomy*, useful for human-
   readable audit rationale, not a source of new predictive power.
4. **Can they become predictive signals?** Only if a CG-derived feature **beats the plainly-named
   equivalent on held-out scenarios.** No evidence suggests it will. Allowed to compete via the
   same promotion pipeline; expected to lose.
5. **Should they stay internal?** **Yes.** Keep the CG taxonomy as an optional **internal
   explanatory mapping**; do **not** ship Sanskrit-named features in the product (auditability +
   credibility cost, zero demonstrated lift).

**Verdict:** CG candidates are admitted to the *arena*, not the *product*. They earn inclusion only
by out-predicting the standard observable they shadow.

---

## 8. Role of the CG wrapper (Phase 4)

**Evaluate independently of governance — it is a behavior-modulation mechanism, not a trust
mechanism.**

1. **Independent evaluation?** Yes. Judge Bhava→phase→phase_adapter on **generation
   quality/behavior** (perplexity, task quality, phase-adapter ablations), never on governance
   AUROC. "CG failed at governance" says nothing about its value (or lack) as a wrapper.
2. **Behavior modulation, not trust?** Yes — it perturbs logits via a small gated residual driven
   by ΔBhava. That is steering, not detection.
3. **Trust validation read-only?** Yes. Detection never requires changing generation.
4. **Should Bhava write ever participate in governance?** **No.** Its input (ΔBhava, sequence-mean
   identity shift) is unrelated to uncertainty/safety, it changes behavior, and it is unsupervised
   for governance.
5. **Connect trust validation into generation?** **No reason today.** Detection ≠ steering;
   coupling adds risk and conflates two problems. Reserve any "act-on-uncertainty" generation
   change for a separate future product with its own evaluation.

The CG wrapper gets its own keep/kill decision on its own (generation-quality) evidence.

---

## 9. What to build now (next 30 days)

1. **Formalize the Phase-1 trust layer** into `agentic/.../trust/`: the observable **registry** +
   the **asymmetric/staged decision tree**, wrapping the proven signals the gateway already runs.
2. **Demote heuristic CG/JEPA out of the decision path.** Keep `enable_cg_state_signals=False`
   **and close the partial off-switch gap** (gate the `vritti_result`/`entropy_result`→JEPA
   attachment too); set JEPA to **advisory-off** until it clears promotion.
3. **Stand up `experiments/trust_signal/`** reusing the signal_gov harness; build the cheapest
   observables offline — **input_risk, hallucinated_tool, permission_overclaim** from existing
   oracle metadata + AgentDojo/InjecAgent — and run the **marginal-value-over-baseline** probe.
4. **Ship the product story:** raw entropy + confidence-risk gap + risk taxonomy + tool validity +
   approvals/audit/budget. (Mostly already default-on; formalize and document.)

## 10. What to defer

- Hidden-state uncertainty/mismatch heads (gated on the one D1 probe).
- Plan-action consistency, groundedness/evidence-linking (hard ML, no labels yet).
- Outcome/reputation observables (need accumulated production data).
- CG-candidate features (let them compete *after* the standard observables exist).

## 11. What to kill

- **Guna entropy, Vritti risk, Kosha signals as governance signals.**
- **JEPA as a blocking validator** (demote to advisory/off; it re-encodes tool risk).
- **Sanskrit-named features in the product.**
- **CSR write intervention** for governance.
- **The full D1 ladder + D4 + D5** as ongoing work (they were CG-internal localization).

## 12. D1 — continue, pause, or partially retain?

**Partially retain exactly one probe; retire the rest.**

| D1 component | Verdict | Why |
|---|---|---|
| **hidden_probe vs raw_entropy** (fooled subset) | **Retain (in reserve)** | It is the **go/no-go gate** for the only model-observable that needs the hidden state (the uncertainty/mismatch head). Resume *just this* if/when that head is on the roadmap. |
| **state_probe (32-D)** | **Retire to research** | Probes the CG bottleneck we are abandoning for the product. |
| **cg_entropy / D5 correlation** | **Retire** | CG-internal; the entropy-definition question is moot once CG-state is off the product path. |
| **Vritti/Guna/Kosha collapse (D4)** | **Retire** | CG-research closure only; not a product signal. |

So: **pause D1 as the CG-rescue program; keep the single hidden-probe-vs-raw-entropy check as the
gate for future hidden heads; retire everything else for the product.**

---

## Summary

Build the supervised, evidence-gated **trust-observable** architecture. Make **validators gate
signals**, earn **authority by evidence**, and let **CG compete but never assume it.** Ship the
proven trust layer + raw entropy + confidence-risk gap + control plane now; develop new observables
in research and promote them one at a time; keep CG-state read-outs, the Bhava write path, and CSR
intervention as research only; and retain just the one D1 probe that still answers a live question.
The differentiator is not a mystical internal state — it is a **measurable, adversarially honest,
auditable trust-validation layer.**
