# Cost, Ablation & Complexity Challenge (Phases 21–23)

*`claim_integrity/eval_ablation.py` → `eval_results/ablation.json`. Does the full ClaimIntegrity
component earn its complexity? The honest answer on this corpus: **mostly no** — a 2-probe sentence
splitter ties it on the primary safety endpoint, and the only mechanism that earns its keep is
reference resolution.*

## Phase 21 — cost proxy

Probe count per stage (deterministic; not wall-clock). Full component = **15 probes**: span-detection
1, segmentation 1, reference-resolution 2, safe-split 2, non-assertive-filter 1, dimension-detect 3,
validation 4, audit 1.

## Phase 22 — ablation (leave-one-out, downstream outcome)

| Config | unsafe delivery | evidence-query altered | false rejection |
|---|--:|--:|--:|
| FULL | 0.068 | 0.000 | 0.068 |
| −nonassertive_filter | 0.068 | 0.000 | 0.068 |
| −safe_split | 0.000 | 0.068 | 0.000 |
| −reference_resolution | 0.068 | **0.091** | 0.068 |

- **`reference_resolution` is the one clearly load-bearing mechanism.** Remove it and evidence-query
  alteration returns to 0.091 (dangling pronouns on the 104 cross-sentence claims). It is what the full
  component does that sentence splitting does not.
- **`nonassertive_filter` is redundant on the main corpus** (no rhetorical questions here; it mattered
  only on the constructed adversarial set). An honestly-reported dead weight in normal traffic.
- **`safe_split` does not clearly help — it trades one harm for another.** Removing it (naive-splitting
  every conjunction) *reduces* unsafe delivery 0.068 → 0.000 (the adversarial conjunctions get split so
  nothing is omitted) but *introduces* evidence-query alteration 0.000 → 0.068 (the split leaves a
  dangling pronoun). Neither direction is clean; only the oracle's subject-carrying split gets both to
  zero. We report this rather than claim safe_split as a win.

## Phase 23 — complexity challenge

| Method | unsafe delivery | evidence-query altered | cost (probes) |
|---|--:|--:|--:|
| **SC1: sentence split + negation-preserved** | **0.068** | 0.091 | **2** |
| SC2: clause split + qualifier | 0.568 | 0.091 | 3 |
| SC3: preserve-whole unless conjunction | 0.454 | 0.000 | 2 |
| **FULL component** | **0.068** | **0.000** | **15** |

**SC1 — a 2-probe sentence splitter — ties the 15-probe component on unsafe delivery (0.068 = 0.068).**
The full machinery's entire measured advantage over SC1 is the evidence-query number (0.091 → 0.000),
i.e. reference resolution. SC2 (clause splitting) and SC3 (preserve-whole) are both far worse, in
opposite directions — so the middle ground SC1 occupies is what matters, and the component does not
improve on it except by resolving references.

## The complexity verdict (honest, mostly negative)

- **The per-dimension modules (qualifier, negation, modality, scope, numeric, attribution checkers) do
  not earn their cost in the component's own output.** Preservation of those dimensions comes for free
  from *not stripping* — which sentence splitting already does. Those modules are valuable as an
  **audit instrument** (they are what caught OpenIE/SPO drifting at 0.86 unsafe, and what would flag a
  third-party extractor), but they are not load-bearing for producing a safe decomposition.
- **The minimal sufficient configuration is `sentence-split + reference-resolution + never-strip`** —
  roughly 4 probes, reproducing the full component's 0.068 unsafe / 0.000 evidence-query. The other
  ~11 probes buy nothing measurable on this corpus.
- **The residual 0.068 unsafe delivery is unsolved by every non-oracle method**, minimal or full. It is
  the exception-bearing conjunction that needs a subject-carrying structural split the deterministic
  component cannot produce. Complexity is not the missing ingredient; structural parsing is.

This points the architectural decision (Phase 28) away from a heavyweight distinct layer and toward a
**reduction**: keep the cheap preservation-first splitter and reference resolution, keep the per-
dimension checkers as an *audit* of untrusted extractors, and drop the rest.
