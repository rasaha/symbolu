# Explicit-Key Neural Memory Capability Probe (E1) — preregistration

**DRAFT PREREGISTRATION — for approval. Nothing here is executed.** No E1 implementation, no model
classes, no training code, no development sweeps, no final evaluation, no reserved-seed allocation, no
changes to B0/BindingSlots, no KDA/MLA/Phase. Companion documents:
`EXPLICIT_KEY_E1_LEAKAGE_AND_SHORTCUT_ANALYSIS.md` and `EXPLICIT_KEY_E1_GATE_AND_COMPUTE_PLAN.md`.

This document **always** preserves, in any later experiment:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.

## 1. Research framing (what E1 is and is not)

Operational reliability for exact factual retrieval is **already supplied** by the external ephemeral
table under the tested conditions (merged PR #1346; V100 characterization merged PR #1349: T0 = V100 =
1.000, zero leakage, deterministic provenance). **E1 is not required for operational reliability.**

E1 is a **scientific capability probe** asking exactly one question:

> Can a **bounded neural memory** learn **semantic identity-addressed retrieval** across **unseen
> identities** and **paraphrased queries**, **without** relying on literal key matching, evaluator
> information, or external-table lookup?

- A **negative** E1 result does **not** invalidate the external-table architecture; the operational
  path is unaffected.
- A **positive** E1 result does **not** authorize removing the external verifier, and does **not**
  unblock KDA.

## 2. Frozen evidence from prior phases (acknowledged, not re-litigated)

- The **value path often remained intact**; oracle/forced addressing recovered the value (Phase-7
  value-path diagnosis).
- **Ordinary read addressing remained unreliable**, and neural reads could be **confidently wrong**.
- The **confidence-triggered fallback failed** its gate (F0/F1: recall 0.80; 95 confidently-wrong reads
  missed) — neural confidence ≠ retrieval correctness.
- **Hard-negative addressing as a bolt-on to anonymous BindingSlots was already tested as A1 and was
  not selected.** **Gradient isolation was already tested as G1 and was not selected.** The
  persistence, address-generalization, and gradient-isolation interventions failed their frozen gates
  (`NO_BINDINGSLOTS_INTERVENTION_SELECTED`).
- Content-addressed anonymous slots expose **no legitimate discrete identity signal**
  (`KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`): writes are soft/distributed, slots are reused, and no
  `slot → entity` target exists without an oracle or a forbidden sidecar.

**Therefore the new hypothesis is NOT "more hard negatives on the current architecture."** Those are
already-failed interventions and must not be presented as untested. The genuinely new lever is an
**explicit semantic-key substrate** that makes **direct matching supervision legitimate** — which the
anonymous-slot formulation structurally cannot express.

## 3. Primary arms

### B0 — frozen anonymous BindingSlots baseline
The authoritative frozen recipe and task semantics, **unchanged**: architecture, routing, slot count,
dimensions, training objective, initialization, optimizer, schedule, evaluation semantics. B0 is the
historical and experimental comparator only.

### E1 — explicit-key dual-encoder neural memory (successor architecture, **not** a repair)
E1 must include, all together as one bundle:
- a **semantic stored-key encoder** (encodes a description that identifies the fact without its answer);
- a **query-key encoder** (encodes the natural-language question);
- a **separate stored-value representation / value encoder**;
- **matching only against the keys present in the current episode** (open-set, episode-local);
- a **differentiable contrastive key-matching loss**;
- **hard negatives drawn from other keys in the same episode**;
- **hard top-1 value selection during ordinary inference**;
- an **explicit no-match / abstention mechanism** (§7);
- **no external-table lookup during ordinary E1 inference**; **no evaluator slot mapping**; **no
  manufactured slot→entity sidecar**.

**The first experiment tests this bundle.** It does **not** isolate the causal contribution of explicit
keys vs. separate encoders vs. contrastive supervision vs. hard negatives vs. hard top-1 reads vs.
no-match training. A positive result supports **only** that the E1 bundle outperformed B0. Component
ablations are deferred and would run only after the bundle clears the go/no-go gate.

## 4. Address training and value reading are decoupled (the crux)

### 4.1 Address training (differentiable)
Train query→key matching with a differentiable **contrastive objective** over the episode's stored keys:
`score(query, correct key)` must exceed `score(query, every incorrect episode key)`. The score function
is **frozen before execution** as **cosine similarity** (scale-invariant; avoids norm-magnitude
confounds). It is **not** left open for post-evaluation selection. (Loss family — InfoNCE-style
softmax-over-episode-keys cross-entropy — proposed; temperature is a dev-fixture-frozen constant, see
gate/compute plan.)

### 4.2 Value read at inference (hard, non-differentiable)
Ordinary held-out evaluation uses **hard top-1 key selection**, then retrieves **exactly** the value
associated with the selected key. **No** soft weighted average over stored values. In the first go/no-go
experiment E1 must **not** use Gumbel-softmax, straight-through estimators, differentiable top-k, soft
value mixtures, or multi-key averaging. The contrastive objective supplies gradients to the key/query
encoders; **hard top-1 inference prevents distributed value averaging from recreating the original
anonymous-slot failure.**

### 4.3 Training-time value path
Value learning uses **teacher-forced correct-key value selection during training** (the correct
episode-local key is used to route the value objective while training; this is the standard teacher
forcing, not an evaluation oracle). **Ordinary held-out evaluation always uses the predicted key, never
the evaluator-provided correct key.** Any oracle-key read at evaluation is **diagnostic only** and must
never be used to select the key or to compute the headline retrieval metric.

## 5. The semantic key (identifies the fact without its answer)

A legitimate semantic key may encode: entity description; attribute/relation description; relevant
write-event context. It must **not** contain the value.

```
Stored semantic key : "Northbridge Components — current supplier eligibility status"
Stored value        : "suspended"
Query               : "Can another purchase order be issued to Northbridge?"
```

The key must not include "suspended." The query must not expose the literal stored-key token. Success
must **not** be based on a literal machine identifier shared verbatim between write and query. The full
list of forbidden shortcut designs and the mechanical tests that enforce this are in
`EXPLICIT_KEY_E1_LEAKAGE_AND_SHORTCUT_ANALYSIS.md`.

## 6. Open-set matching, not fixed classification

E1 must **not** train a fixed softmax classifier over globally known identities (no `Alice=class 17`).
Evaluation identities are **open-set and episode-specific**: the query embedding is compared against the
**stored keys present in that episode**, and the model must support identities **unseen during
training**. The correct episode-local key must score above the other episode keys.

## 7. No-match / abstention mechanism (a primary gate, frozen to one design)

A system that abstains on every query does **not** qualify; a system that always selects the nearest key
does **not** qualify. Per protocol, **one** primary strategy is frozen before execution (no selecting
the winner on reserved seeds):

**Frozen primary: Option A — learned null key.** Each episode contains a designated no-match
representation; queries with no corresponding memory key are trained to select it. **Rationale for
choosing A over B:** a frozen score/margin threshold (Option B) rejects on score magnitude, which is
exactly the signal that failed in the confidence-trigger phase — a *confident wrong* match has high
score and high margin, so threshold rejection re-imports the confidently-wrong weakness. A learned null
key trains the abstention **decision** directly rather than thresholding a magnitude. **Documented risks
to control (on dev fixtures only):** null-key shortcut, over-abstention, class imbalance, collapse to the
null key. Mitigations (null-query sampling rate, null-key regularization) are frozen on **non-reserved**
fixtures; their numeric values are in the gate/compute plan (marked `APPROVAL_REQUIRED_BEFORE_EXECUTION`
where dev evidence is insufficient).

**Option B — frozen score/margin rejection is explicitly NOT the primary** (documented, considered,
rejected for the reason above). It may appear only as a diagnostic, never as the selected mechanism, and
is never tuned on reserved seeds.

Required no-match metrics: false-accept rate (no valid key exists), false-reject rate (a valid key
exists), no-match precision, no-match recall, answer availability, confidently-wrong nearest-key
selections, score/margin distributions, per-seed no-match pass/fail.

## 8. Honest episode density (comparable to where B0 failed)

The first E1 test operates at **≈32 competing stored keys per episode** (matching the 32-slot regime
where anonymous BindingSlots failed), or the exact frozen density justified by the authoritative B0
task. The primary go/no-go claim is **not** evaluated only on easy 5–10-key episodes. Each episode
contains difficult in-episode negatives: similar entity names; same entity / different attributes;
different entities / same attribute; similar relations; similar values; unrelated distractors;
recombined entity–attribute pairs. The preregistration must state exactly (values proposed in the
gate/compute plan, some `APPROVAL_REQUIRED_BEFORE_EXECUTION`): keys/episode; valid queries; no-match
queries; hard-negative composition; candidate ordering; randomization rule; whether values repeat across
keys. **The claim remains scoped to the preregistered density.**

## 9. Held-out generalization drives the verdict

In-distribution, training-style address accuracy is **not** the main gate — E1 receives matching
supervision B0 cannot express, so an in-distribution addressing win is expected and insufficient. The
verdict is driven **primarily** by held-out splits:

- **G1 — unseen identities:** all entity identities absent from training.
- **G2 — paraphrased queries:** same semantic identity, substantially different wording.
- **G3 — hard-name confusions:** similar/confusable entity names present.
- **G4 — same entity, different attributes:** must retrieve the correct attribute-specific key.
- **G5 — recombined facts:** familiar linguistic structure, unseen entity–attribute–value combinations.
- **G6 — no-match queries:** requested entity/fact absent from episode memory.
- **G7 — previously stable B0 cases:** confirm E1 does not catastrophically regress on historically
  stable/easy retrieval cases.

Train / development / final-evaluation splits must prevent identity and combination leakage; the
construction and the leakage proofs are specified in the leakage-and-shortcut analysis.

## 10. Metrics (addressing, no-match, end-to-end, stability kept separate)

**Addressing:** correct-key top-1; correct-key top-k; mean/median correct-key rank; correct-key score;
strongest-wrong-key score; top-1 margin; hard-negative error rate; per-split address accuracy; per-seed
address accuracy.
**No-match:** false-accept; false-reject; no-match precision; no-match recall; abstention rate;
answer-availability; confidently-wrong no-match selections.
**End-to-end:** ordinary retrieval accuracy; oracle-key value accuracy (diagnostic); predicted-key value
accuracy; final answer accuracy; oracle-vs-predicted gap; historically-stable-case accuracy; per-split;
per-seed.
**Stability:** fresh-seed pass count; variance across seeds; worst-seed; deterministic-reproduction
equality; state-hash equality for repeated fixtures.

**These are never combined into one misleading headline metric.**

## 11. Determinism prerequisite (before any reserved-cohort run)

E1 must clear a deterministic reproduction fixture before the final cohort. Frozen: seed; data order;
episode construction; negative ordering; parameter init; optimizer; LR schedule; batch size; steps;
checkpoint interval; CPU/GPU environment; precision; thread count; software versions. Where the
repository contract requires it: **CPU fp32, `threads=4`**. Repeated fixture runs must produce
byte-identical model-state hashes, identical loss trajectory, identical predictions, identical metrics,
identical artifact hashes. If deterministic reproduction fails, stop before reserved-cohort execution
with `EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED`. (Details in the gate/compute plan.)

## 12. Outcome vocabulary (mechanically reconstructable)

`EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED` · `…_PARTIAL` · `…_NOT_SELECTED` ·
`EXPLICIT_KEY_NO_MATCH_GATE_FAILED` · `EXPLICIT_KEY_GENERALIZATION_GATE_FAILED` ·
`EXPLICIT_KEY_STABLE_CASE_REGRESSION` · `EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED` ·
`EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED` · `EXPLICIT_KEY_PROTOCOL_VIOLATED` ·
`EXPLICIT_KEY_RESULTS_INCONCLUSIVE` · `EXPLICIT_KEY_RESOURCE_BLOCKED`. **Always also preserve**
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` and `KDA_VALIDATION_BLOCKED`. **If E1 passes, also
require** `INDEPENDENT_NEURAL_MEMORY_CONFIRMATION_REQUIRED`. A passing E1 does **not** unblock KDA
automatically. The verdict→gate mapping is in the gate/compute plan.

## 13. Interpretation boundaries

A **passing** E1 result may support **only**: "the preregistered explicit-key dual-encoder memory recipe
learned semantic episode-local key matching and hard top-1 value retrieval **more reliably than the
frozen anonymous BindingSlots baseline** at the evaluated density and held-out generalization
conditions." It does **not** establish: which E1 component caused the improvement; arbitrary-capacity
memory; production readiness; long-context reasoning; durable versioned memory; enterprise data
correctness; external-table replacement; KDA readiness; repair of the original anonymous BindingSlots
architecture.

A **failed** E1 result supports **only**: "the explicit-key bundled successor did not clear the
preregistered semantic-matching, generalization, no-match, stability, or integrity gates under the
bounded experiment." The operational external-table path remains unaffected.

## 14. Prohibited in the eventual experiment (and in this task)

Confidence-threshold tuning; changing B0/BindingSlots; K1; V75/V50; versioning experiments; capacity
scaling; realistic enterprise tasks; Phase; KDA; MLA; base-recipe training beyond the frozen E1 recipe;
soft/differentiable value mixing in the first go/no-go; selecting the no-match strategy or any threshold
on reserved seeds; using the expected answer or evaluator information to construct or score keys. **This
task is documentation-only: no E1 code, no training, no evaluation.**
