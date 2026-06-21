# C×R×S MATCH-Filter — Phase 2B Robustness Validation — RESULTS

> Pre-registered rubric `framed_answer_rubric_v1` (locked) over the held-out v2 dataset (110 cases),
> frozen Phase 1 frame + Phase 2 framed prompt, real answer model Mistral-7B-Instruct-v0.3, real frame
> (`all-MiniLM-L6-v2`), deterministic judge. Builds on Phase 1 (`5cb4f76`) and Phase 2 (`c22a323`).

## Outcome: INCONCLUSIVE under rubric_v1 — primary-frame lift is real; the factuality "regression" is a rubric artifact

Locked-rubric label: **`PHASE2B_FACTUALITY_REGRESSION`** (framed factuality 0.836 < base 0.909 − 0.05).
But human inspection of the flagged cases shows the regression is **spurious** (see below), so Phase 2B
**neither confirms a clean robust PASS nor a genuine regression** — it surfaced a rubric design flaw.

### Mistral metrics (n=110, base → framed)

| metric | base | framed | Δ | gate |
|---|---:|---:|---:|---|
| primary_frame_correct | 0.564 | **0.727** | **+0.164** | ✓ (distributed 10/10 categories; no domination) |
| rejected_domain_avoidance | 0.745 | 0.818 | +0.073 | ✗ (needs +0.10 or ≥0.90) |
| phoneme_overreach_rate | 0.000 | 0.000 | 0 | ✓ |
| factuality_preserved | 0.909 | 0.836 | **−0.073** | ✗ (triggers regression label) |
| must_include_recall | 0.382 | 0.464 | +0.082 | — |
| must_not_violation_rate | 0.029 | 0.070 | +0.041 | — |
| clarity_proxy | 0.936 | 0.982 | +0.045 | ✓ |
| trace_completeness | — | 1.000 | — | ✓ |

`lift_distribution`: overall +0.164, dominated_by_single_category = None, 10/10 categories framed ≥ base
→ `robust=True`, `polysemy_ok=True`.

### What survived
**The primary-frame correctness lift survived and is robust** (+0.164, distributed). Framing genuinely
makes the model lead with the correct sense, and clarity improved. Overreach stayed 0.

### Why the factuality regression is spurious (confirmed by inspection)
The regression and the rejected-leaks are concentrated on **polysemy**. Sampled framed answers:
- `poly_010` python→programming: *"...primarily programming... However, it's also a species of snake
  in the secondary domain of biology."* — **factually correct**, correct primary.
- `poly_016` virus→biology: *"...primarily biology... While it can also be used in computer security,
  its primary meaning is biology."* — **factually correct**, correct primary.

Both score `factuality_preserved=False` only because they **mention the alternate TRUE sense**, which
the v2 dataset marks as `expected_rejected` and `rubric_v1` couples to factuality via
`must_not_violation`. This is **off-frame-but-true**, not a factual error. (`poly_001` scored
`must_not=0.5` on a correct one-line answer — a few polysemy rows also have a mismatched `must_not`
phrase.)

### Root causes (in the LOCKED rubric_v1 / v2 dataset — not the model, not the frame)
1. **Factuality is coupled to frame-compliance** (`factuality_preserved` keys off `must_not_violation`),
   so a frame-violation reads as a factuality loss — contradicting the *intent* of pre-registered
   rule 5.
2. **Polysemy alternate senses are marked `rejected` (must-not-mention)**, but the *correct* behavior
   for an ambiguous term is to LEAD with the primary sense and may briefly note the other — which the
   rubric penalizes as a leak.

## Decision: do NOT claim PASS; do NOT claim regression; do NOT patch the locked rubric

Per the pre-registration discipline, `rubric_v1` stands and its label is recorded as-is. The honest
status is **`PHASE2B_NEEDS_HUMAN_REVIEW`** (the v1 regression is not corroborated by human inspection).
We do **not** rescore v1 with a changed rubric to flip the label — that is the Phase 2 overfitting sin.

## Recommendation
1. **Author a separately pre-registered `framed_answer_rubric_v2`** that:
   - **decouples factuality from frame-compliance** — factuality = no *false* claim, independent of
     must_not / rejected mentions;
   - treats a polysemy **alternate sense as secondary-allowed** (a brief, correctly-subordinated
     mention is not a leak; only *framing around* the wrong sense is);
   - fixes the few `must_not` phrase mismatches on polysemy rows.
   Pre-register it **before** re-running, then re-run on the same v2 dataset + Mistral.
2. **Do not proceed to Phase 3 / product use** until the re-run resolves the polysemy factuality
   question, ideally with an **LLM-as-judge or human review** (the deterministic proxy cannot tell
   off-frame-true from false).
3. **Do not revise the frozen Phase 2 prompt** based on these numbers. (A future versioned prompt that
   says "lead with the primary sense; you may briefly note other senses" is Phase 3 design, not 2B.)

## Bottom line
Phase 2B did its job: under a pre-registered rubric on held-out data, the **primary-frame lift
replicated and is robust**, but the rubric's **factuality/rejected metrics conflate frame-compliance
with correctness on polysemy**, producing a spurious regression label. The validation is **inconclusive
on factuality** pending a decoupled, pre-registered `rubric_v2` re-run (and ideally an independent
judge). Phase 1 (frame selection) and the *focus* benefit of framing remain well-supported.
