# Track F Smoke Pilot — Result Log (exploratory triage)

**Exploratory triage result. Not validation, no varṇa-truth claim.** No `ONTOLOGICAL_SIGNAL`, no
Sanskrit privilege. `frozen/manifest.json` remains NOT_READY; the base Track F smoke manifest stayed
`run_enabled:false` / `NOT_APPROVED` throughout (authorization came from the separate approved run
config); psr runner NOT_RUN; Stage A untouched; four-sphere JSON parked/not integrated; **Track B
remains BLOCKED.** Per the no-rescue rule this cannot become a positive.

## Run

- **Environment:** RunPod, NVIDIA RTX 6000 Ada (48 GB). Operator-run (Claude did not execute it).
- **Design:** prompt-boundary injection, arms X/A/B/F/I/R (72 packets = 12 tasks × 6 arms).
- **Answer model:** `mistralai/Mistral-7B-Instruct-v0.3`, temp 0.0, JSON-only, no browsing, no
  carryover.
- **Judge:** **single-model (EXPLORATORY / weaker)** — Mistral judged its own anonymized outputs;
  A-vs-arm distances are lexical (Jaccard). No answer ≠ judge separation.
- **Coverage:** 10/12 tasks judged, **2 dropped** (`f010`, `f002` — malformed/incomplete judge
  output); answer malformed rate 0.0278; contamination none.

## Result

- **Primary label:** **`CORRECTNESS_DEGRADED`**

| Metric | Value | Reading |
|---|---|---|
| `delta_A_vs_X` | 0.6448 | A's output differs substantially from the normal prompt (a steer occurred) |
| `spec_A_vs_B` | 0.5690 | A is distinct from the scrambled boundary |
| `spec_A_vs_I` | 0.5675 | A is distinct from the Barnum boundary |
| `incr_A_vs_F` | 0.6478 | A is distinct from dictionary/etymology |
| `correctness_preserved` | **−0.1000** | A correctness **below** X → the steer is mildly harmful |
| `usefulness_gain` | −0.1000 | A no more useful than X/B/I |
| `noise_A` / `halluc_A` | 0.05 / 0.05 | low |

Per-arm judge means (correctness): X 1.0 · B 1.0 · I 1.0 · **A 0.9** · F 0.9.

## Honest interpretation

- **The real varṇa boundary *did* steer inference, and specifically.** `delta_A_vs_X ≈ 0.64` with A
  distinct from scramble (B), Barnum (I), and dictionary/etymology (F). So this is **not**
  `PROMPT_PRIMING_ONLY`, `SCRAMBLE_EQUIVALENT`, or `BARNUM_EQUIVALENT` — the real vṛtti-gloss content
  changed the model's answers in its own way.
- **But the steer slightly reduced correctness** (A 0.9 vs X 1.0), with no usefulness gain → the
  change is **harmful, not useful**. Track F requires a steer that is specific **and useful and**
  correctness-preserving; this fails the correctness/usefulness bar → `CORRECTNESS_DEGRADED`.
- **This is NOT a `INFERENCE_STEERING_SIGNAL` and NOT a positive.** Adding the varṇa boundary made
  answers marginally worse, not better.

## Weight the caveats (why this is soft, not a strong "harmful")

- **Single-model judge (the dominant caveat).** Mistral scored its own outputs and returned coarse,
  near-ceiling numbers (X/B/I all exactly 1.0; A/F 0.9). The entire "degradation" is a single 0.1
  notch on that coarse self-judged scale — **well within self-judge noise**. A self-judge also tends
  to rate no-lens (X) and ignored-lens (scramble/Barnum) answers as "perfectly on-reference" and
  penalize any lens that actually changed the answer, which can manufacture an apparent A/F penalty.
- **Small n / low resolution:** 10 tasks judged, round-number scores.
- **Robust takeaway:** *no useful inference-steering was demonstrated*; the observed correctness cost
  is small and weak-judge-dependent. The safe reading is "no positive," not "reliably harmful."

## Consequence

- **Triage decision:** under this single-model-judged smoke, the varṇa boundary shows **no useful,
  correctness-preserving inference steering** — a full Track F pilot is **not justified on this
  evidence**. The one lead worth a *separate* future step is an **answer ≠ judge** re-run (a distinct
  judge model) with a finer scoring scale, to test whether the small correctness cost is real or
  self-judge artifact. That is a new run with its own approval, **not** a rescue of this result.
- **No rescue.** This does not reinterpret or soften Track C / D0 / Track E-flat, does not claim
  varṇa truth, and does not touch the Track B block.
- **Consistent with the program:** the varṇa content again fails to add *useful* value — here it
  even slightly steers the model off-answer.

> Track F smoke pilot, exploratory triage only. Single-model judge; not validation, no varṇa truth.
> Track B remains blocked. Structure, not validated meaning.
