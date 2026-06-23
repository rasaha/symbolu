# RESULTS — CG Training T1: C×R×S-only LoRA on Mistral (four-arm)

> **Decision: `CG_TRAINING_WRAPPER_STILL_BEST`.** Pre-registration:
> `docs/CG_TRAINING_CRS_MISTRAL_PREREG.md`. Not a product failure — it means **inference wrapping is the
> better deployment path today.** No post-hoc tuning. T2 (DPO) is **not** auto-opened (see §5).

## 1. Run
- **Model:** Mistral-7B-Instruct-v0.3, **QLoRA** (r=16), 3 epochs, **51 train / 7 val** self-distilled from
  the validated wrapper's audit-passing framed answers; **20 test** (term-grouped, unseen-term holdout).
- **Eval:** four arms, real generation, scored by the **validated `rubric_v2`** (no new judge). bf16.
- **Self-distillation ceiling (stated up front):** targets are the wrapper's own good answers, so C cannot
  exceed its teacher; T1 tests weight-internalization + generalization, not superiority over the wrapper.

## 2. Result (n_test = 20)
| metric | A base | B base+wrapper | C LoRA | D LoRA+wrapper |
|---|---|---|---|---|
| primary_frame_correct | 0.80 | **0.90** | **0.90** | 0.60 |
| rejected_domain_avoidance | 0.95 | **1.00** | 0.95 | 0.65 |
| factuality_preserved | 1.00 | 1.00 | 1.00 | 0.80 |
| clarity_usefulness | 1.00 | 1.00 | 1.00 | 1.00 |
| must_include_recall | 0.25 | **0.40** | 0.20 | 0.10 |
| generalization_to_unseen_terms | 0.80 | 0.90 | 0.90 | 0.60 |

- ΔPFC **C−B** = 0.00 [−0.15, 0.15] (CI incl. 0) · ΔPFC **C−A** = +0.10 [0.00, 0.25] (CI incl. 0)
- gate reasons: `c_beats_a=False, generalizes=True, approaches_or_beats_b=True, d_not_worse_than_b=False`

## 3. Why `WRAPPER_STILL_BEST` (against §11)
- `c_beats_a` = **False**: C beat A on primary-frame (0.90 vs 0.80) but only **tied** on rejected-domain
  avoidance (0.95 = 0.95); the gate requires strictly beating A on **both**.
- `d_not_worse_than_b` = **False**: D collapsed (see §4).
- B (the wrapper) has the best/tied primary-frame correctness → `CG_TRAINING_WRAPPER_STILL_BEST`.

## 4. Two informative findings (beyond the headline)
1. **Partial internalization signal (encouraging, NOT significant).** Arm **C — the LoRA on a PLAIN prompt
   with no frame text — matched B (base + full wrapper) on primary-frame correctness (0.90 = 0.90) and on
   unseen-term generalization (0.90),** and beat base A (0.80). i.e. the LoRA carried framing behavior in
   its *weights* without being told the frame at inference. **But** ΔC−A CI includes 0 (n=20,
   underpowered), and C tied (not beat) A on rejected-domain — so this is a *hint*, not a validated effect.
2. **Stacking fine-tuning + wrapper HURTS (important negative).** Arm **D (LoRA + wrapper) collapsed** —
   primary-frame 0.60, rejected-domain 0.65, factuality 0.80 — far worse than B. Feeding the LoRA the
   longer framed prompt (a distribution it didn't train on) degraded it. **Practical warning: do not
   naively combine a frame-LoRA with the inference wrapper.**
3. **Completeness regression:** `must_include_recall` dropped for C (0.20) and D (0.10) vs B (0.40) — the
   self-distilled LoRA answers are terser / less complete.

## 5. Close-out (kill criterion)
- **Ship/keep the inference wrapper (arm B) as the deployment path.** Fine-tuning did not beat it.
- **No post-hoc tuning.** A new attempt is a new pre-registration.
- **T2 (DPO) is NOT auto-opened.** The C≈B internalization hint is real but **underpowered** (n=20, wide
  CIs, self-distillation ceiling) and comes with a completeness regression + the D-collapse warning. The
  honest next step is **not** DPO yet — it is a **larger, powered T1 re-run** (more training data, larger
  held-out test, multiple seeds) under a fresh pre-registration to test whether C-internalization is real;
  only if that confirms signal does T2 DPO make sense.

## 6. Standing claim (unchanged)
*Conscious Generation training is a new experimental track. C×R×S is validated today as an inference-time
semantic-framing mechanism; whether that behavior can be internalized into Mistral through LoRA
fine-tuning remains unvalidated.* T1 showed a **promising but non-significant** internalization signal
(plain-prompt LoRA ≈ wrapper on primary-frame correctness) and a clear negative (LoRA+wrapper degrades);
the wrapper remains the best deployment path.
