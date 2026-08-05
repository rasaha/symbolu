# E1 — determinism, frozen numerical gates, compute budget, and verdict mapping

**Draft plan for approval; nothing is executed.** Companion to `EXPLICIT_KEY_E1_PREREGISTRATION.md`.
Numeric thresholds are proposed **structurally**; every value that cannot be justified without
non-reserved development fixtures is marked `APPROVAL_REQUIRED_BEFORE_EXECUTION`. Thresholds are frozen
**only** on development fixtures, **before** inspecting any reserved evaluation result. No threshold is
invented to make the experiment easy to pass. Always preserved:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.

## 1. Determinism prerequisite (hard precondition)

Before any reserved-cohort run, E1 must clear a deterministic reproduction fixture. Frozen and recorded:
seed; data order; episode construction; negative ordering; parameter initialization; optimizer; LR
schedule; batch size; number of steps; checkpoint interval; CPU/GPU environment; numerical precision;
thread count; software versions. Repository determinism contract: **CPU fp32, `threads=4`**, sequential
runs.

Acceptance (repeated fixture runs must be **identical**): model-state hashes byte-identical; loss
trajectory identical; predictions identical; metrics identical; artifact hashes identical. **Failure →
stop before reserved-cohort execution with `EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED`.** (New trainable
modules have twitchier dynamics than the inference-only prior phases, so this is a real gate, not a
formality.)

## 2. Frozen score function and matching (no post-hoc selection)

- Score: **cosine similarity** (frozen).
- Loss: InfoNCE-style softmax cross-entropy over episode-local keys (proposed); **temperature τ** frozen
  on dev fixtures — value `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
- Inference read: **hard top-1** (frozen); no soft/Gumbel/STE/top-k/mixture in the first go/no-go.
- No-match: **learned null key** (frozen primary; §7 of the preregistration). Null-query sampling rate
  and null-key regularization strength frozen on dev fixtures — values
  `APPROVAL_REQUIRED_BEFORE_EXECUTION`.

## 3. Episode density parameters (frozen; scoped claim)

| parameter | proposed | status |
|---|---|---|
| keys per episode | ≈ **32** (match the 32-slot regime where B0 failed) | proposed; exact value `APPROVAL_REQUIRED_BEFORE_EXECUTION` if B0 task justifies a different density |
| valid queries per episode | proposed on dev fixtures | `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| no-match queries per episode | proposed on dev fixtures (must be > 0 and not dominate) | `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| hard-negative composition | similar names / same-entity-diff-attribute / diff-entity-same-attribute / similar relations / similar values / distractors / recombined pairs | structure frozen; proportions `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| candidate ordering | randomized, seeded, frozen rule | frozen rule; seed frozen |
| values repeat across keys? | **yes** (values are not unique identifiers — prevents value-as-key shortcut) | frozen |

The capability claim is **scoped to the frozen density**; a win at low density does not transfer and is
not the go/no-go.

## 4. Frozen numerical gates (structure fixed; values on dev fixtures)

The verdict is driven **primarily by held-out generalization + no-match**, not by in-distribution
addressing (which E1 is expected to win and which is therefore **not** a gate).

### 4.1 Generalization gates (held-out)
- min **unseen-identity (G1)** correct-key top-1 accuracy — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- min **paraphrase (G2)** accuracy — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- min **hard-negative (G3)** accuracy — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- min **recombined-fact (G5)** accuracy — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- min **same-entity/different-attribute (G4)** accuracy — `APPROVAL_REQUIRED_BEFORE_EXECUTION`

### 4.2 No-match gates (G6; a primary gate)
- max **false-accept** rate (no valid key exists) — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- max **false-reject** rate (a valid key exists) — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- min no-match **precision** — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- min no-match **recall** — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- max **confidently-wrong nearest-key** rate — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- **hard sanity bounds (frozen now, not tunable):** abstain-on-everything → automatic fail;
  always-select-nearest-key → automatic fail.

### 4.3 End-to-end gates
- min **improvement over B0** on held-out retrieval — `APPROVAL_REQUIRED_BEFORE_EXECUTION` (must exceed
  a preregistered margin; an in-distribution-only win does not satisfy this)
- min absolute ordinary (predicted-key) retrieval accuracy — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- min **oracle-key value accuracy** (diagnostic value-path health) — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- max **oracle-to-predicted-key gap** — `APPROVAL_REQUIRED_BEFORE_EXECUTION`
- max **regression on historically stable B0 cases (G7)** — `APPROVAL_REQUIRED_BEFORE_EXECUTION`

### 4.4 Fresh-seed gate
- required number/proportion of evaluation seeds that must pass **all** primary gates —
  `APPROVAL_REQUIRED_BEFORE_EXECUTION`. Fresh-seed consistency (not a single lucky seed) is mandatory.

## 5. Bounded compute and futility

Frozen before execution:

| item | proposed | status |
|---|---|---|
| development seeds | small, disjoint from reserved | count `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| final evaluation seeds | fresh, held-out, disjoint from dev & from V100 seeds 28–32 | set `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| max training steps / seed | bounded | `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| max wall-clock / seed | bounded (CPU fp32 is slow; keep the probe small) | `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| total compute budget | bounded | `APPROVAL_REQUIRED_BEFORE_EXECUTION` |
| max retries | infrastructure-failure retries only; **no selective seed restarts** | frozen policy |
| failure-recovery | resume-from-checkpoint on infra failure only; never re-roll a failed seed to improve pass rate | frozen policy |
| post-evaluation hyperparameter tuning | **prohibited** | frozen |

**Mechanical futility rule (frozen):** stop E1 when the **maximum possible remaining seed pass count can
no longer satisfy the frozen fresh-seed gate** (i.e., even if all remaining seeds passed, the required
proportion is unreachable). Also terminate early on: determinism failure
(`EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED`); any leakage/shortcut test failure
(`EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED`); no-match collapse under a frozen early-stop rule
(all-abstain or all-nearest); resource exhaustion (`EXPLICIT_KEY_RESOURCE_BLOCKED`). **No selective
restart of failed seeds.**

## 6. Verdict mapping (mechanical; co-emissions fixed)

Evaluated in this precedence (integrity/determinism first, then gates):

1. leakage/shortcut test fails → `EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED`
2. determinism fixture fails → `EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED`
3. protocol breach (soft read used, threshold tuned on reserved seeds, table consulted, etc.) →
   `EXPLICIT_KEY_PROTOCOL_VIOLATED`
4. resource/budget exhausted before a decision → `EXPLICIT_KEY_RESOURCE_BLOCKED`
5. no-match gate fails → `EXPLICIT_KEY_NO_MATCH_GATE_FAILED`
6. any generalization gate fails → `EXPLICIT_KEY_GENERALIZATION_GATE_FAILED`
7. catastrophic G7 regression → `EXPLICIT_KEY_STABLE_CASE_REGRESSION`
8. **all** primary gates pass on the required fresh-seed proportion →
   `EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED`
9. some but not all primary gates pass → `EXPLICIT_KEY_SEMANTIC_MATCHING_PARTIAL` /
   `EXPLICIT_KEY_SEMANTIC_MATCHING_NOT_SELECTED` (per the frozen partial-vs-not-selected rule, to be
   fixed on dev fixtures — `APPROVAL_REQUIRED_BEFORE_EXECUTION`)
10. otherwise → `EXPLICIT_KEY_RESULTS_INCONCLUSIVE`

**Always co-emit** `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` and `KDA_VALIDATION_BLOCKED`. **On
`…_VALIDATED`, additionally require** `INDEPENDENT_NEURAL_MEMORY_CONFIRMATION_REQUIRED`. A passing E1 does
**not** unblock KDA and does **not** authorize removing the external verifier.

## 7. What is NOT decided here (must be approved before any execution)

Every `APPROVAL_REQUIRED_BEFORE_EXECUTION` value above; the exact final-seed set; the partial-vs-
not-selected boundary; the compute budget numbers. Until these are frozen on non-reserved development
fixtures and approved, **no execution begins**. This plan fixes structure, precedence, and integrity
rules only.
