# PhaseAttention Behavioral Probe Suite

A standalone diagnostic script to scientifically test what PhaseAttention layers are learning behaviorally.

## Purpose

This is a **mechanism verification** tool, not a training improvement or visualization task.

The goal is to answer:
> "Can PhaseAttention bind roles, persist entities, and resist interference **by itself**?"

Before asking whether phase can learn emotional propensities or complex semantics, we must first verify that it performs basic relational selectivity.

## Key Questions Answered

1. Does PhaseAttention enable correct pronoun/reference resolution?
2. Does phase disruption (scramble/freeze) break relational reasoning?
3. Is phase actually contributing, or is it decorative?

## Hard Constraints

- Does **NOT** modify model architecture
- Does **NOT** add or change any loss
- Does **NOT** depend on CSR/SRK internals for scoring
- Runs **POST-TRAINING** on a checkpoint
- Outputs **MEASURABLE, COMPARABLE** metrics

## Usage

```bash
# Run full probe suite
python phase_probe_runner.py --checkpoint checkpoints/best.pt

# Run with verbose output (shows all ablation modes)
python phase_probe_runner.py --checkpoint checkpoints/best.pt --verbose

# Run specific probe
python phase_probe_runner.py --checkpoint checkpoints/best.pt --probe RB1

# Run specific category
python phase_probe_runner.py --checkpoint checkpoints/best.pt --category role_binding

# Save results to JSON
python phase_probe_runner.py --checkpoint checkpoints/best.pt --output results.json
```

## Probe Categories

### A. Role Binding (RB1-RB5)
Tests whether the model can bind pronouns/references to the correct antecedent based on **semantic compatibility**, not just token proximity.

| Probe | Text A | Text B | What It Tests |
|-------|--------|--------|---------------|
| RB1 | Alice blamed Bob because **she** was angry. | Alice blamed Bob because **he** was angry. | Pronoun gender → role binding |
| RB2 | John thanked Mark because **he** helped. | John thanked Mark because **John** helped. | Implicit vs explicit reference |
| RB3 | Sarah apologized to Emma because **she** felt guilty. | ...because **Emma** felt guilty. | Semantic role (apologizer = guilty) |
| RB4 | The lawyer called the client because **he** was late. | ...because **the client** was late. | Ambiguity handling |
| RB5 | Tom warned Jim that **he** was in danger. | ...that **Jim** was in danger. | Control (both should → Jim) |

**Phase Isolation**: These probes require binding pronouns to semantically compatible antecedents. If phase is learning relational selectivity, scrambling phases should break this binding.

### B. Long-Range Persistence (LP1-LP4)
Tests whether the model maintains entity salience across filler material.

| Probe | Structure | What It Tests |
|-------|-----------|---------------|
| LP1 | John entered. Mary left. [filler]. After delay, **he** spoke. | Entity persistence (he→John, not Mary) |
| LP2 | Maria picked up violin. [filler]. **She** played. | Action continuity across distance |
| LP3 | Captain spoke to crew. [filler]. **He** relaxed. | Role-based persistence (singular vs plural) |
| LP4 | John spoke to Mary. Assistant took notes. **He** signed. | Decoy suppression (assistant is closer) |

**Phase Isolation**: Phase should enable selective persistence of the correct entity across intervening tokens. Recency bias alone would pick the wrong referent.

### C. Semantic Interference (SI1-SI3)
Tests whether phase prevents semantic blending when the same token appears with different meanings.

| Probe | Ambiguous Token | What It Tests |
|-------|-----------------|---------------|
| SI1 | "bank" (financial vs river) | Sense disambiguation from context |
| SI2 | "bass" (fish vs instrument) | Sense selection with interference |
| SI3 | "crane" (bird vs machine) | Local continuity over initial sense |

**Phase Isolation**: Phase should encode the appropriate sense for each occurrence. Without phase selectivity, meanings would blur together.

### D. Negation/Polarity (NP1-NP3)
Tests whether phase helps preserve clause-level polarity and scope.

| Probe | Structure | What It Tests |
|-------|-----------|---------------|
| NP1 | Trophy doesn't fit because it's too **big/small**. | Winograd schema (size→object mapping) |
| NP2 | Council refused because they **feared/advocated** violence. | Reason-based role binding |
| NP3 | He didn't say it would fail **until later**. | Negation scope (did say it later) |

**Phase Isolation**: These require tracking polarity across the clause structure. Phase should help maintain logical relationships.

### E. Amplitude vs Phase Conflict (AC1-AC4)
Tests whether the model uses phase for relational binding rather than just high-amplitude (salient/repeated) tokens.

| Probe | High-Amplitude Noise | What It Tests |
|-------|---------------------|---------------|
| AC1 | IMPORTANT IMPORTANT IMPORTANT | Binding despite amplitude distractor |
| AC2 | URGENT URGENT URGENT + CRITICAL CRITICAL | Multiple amplitude sources |
| AC3 | ERROR ERROR ERROR + WARNING WARNING | Pronoun resolution against noise |
| AC4 | LOUD LOUD LOUD on different entities | Amplitude shouldn't shift binding |

**Phase Isolation**: If the model relies on amplitude rather than phase for binding, these probes will fail. They directly test whether phase carries selectivity independent of token salience.

## Ablation Modes

Each probe is run under **4 inference modes**:

| Mode | Description | Effect |
|------|-------------|--------|
| `baseline` | Normal inference | Full phase functionality |
| `scramble` | Randomly permute φ_k, φ_q per head | Destroys position-phase relationships |
| `frozen` | Set all phases to constant | cos(φ_q - φ_k) = 1 everywhere |
| `phase_off` | Set φ_q = φ_k = 0 | Uniform attention weights |

**Key Insight**: If phase is learning real selectivity:
- Baseline should outperform ablations
- Scramble/frozen/phase_off should degrade relational resolution
- The degradation should be **selective** (not everything breaks)

## Metrics

### Per-Probe Metrics
| Metric | Description |
|--------|-------------|
| `margin` | log P(correct) - log P(best_wrong) |
| `confidence` | P(predicted_token) |
| `R_k` | Key phase collapse (0=uniform, 1=collapsed) |
| `R_q` | Query phase collapse |
| `amp_phase_corr` | Correlation between |z| and a_k |
| `head_redundancy` | Mean cosine similarity between heads |
| `head_entropy` | Diversity of head contributions |
| `phase_drift` | Mean |Δφ_k| across time |

### Aggregate Metrics
| Metric | Description |
|--------|-------------|
| `phase_sensitive_pct` | % probes where ablation hurts |
| `phase_contribution_index` | avg(baseline_margin - scramble_margin) |

## Failure Signatures

The script detects 4 failure modes:

| Signature | Detection | Meaning |
|-----------|-----------|---------|
| **F1: Decorative** | Δ ≈ 0 everywhere | Phase not contributing |
| **F2: Brittle** | Scramble breaks >70% | Phase over-coupled |
| **F3: Collapsed** | R_k > 0.5 | Phase diversity lost |
| **F4: Amplitude Cheating** | |amp_phase_corr| > 0.6 | Amplitude compensating |

## Scientific Interpretation

The script provides a **scientific verdict**:

```
CAN demonstrate that PhaseAttention is learning relational selectivity.
  Evidence:
    - Phase-sensitive probes: 75%
    - Phase contribution: 0.45
    - Baseline outperforms ablations by 15%
```

OR

```
CANNOT conclusively demonstrate that PhaseAttention is learning
relational selectivity with this checkpoint.
  Reasons:
    - Only 30% probes are phase-sensitive (<50%)
    - Phase contribution index (0.05) is too low
```

## Design Principles

### Constructive Counter-Examples
Each probe is designed such that:
1. **Token identity alone is insufficient** to solve it
2. **Recency bias would give wrong answer**
3. **Correct behavior must degrade specifically when phase is disrupted**

### Minimal Pairs
Minimal-pair probes keep tokens, length, and structure constant while changing exactly one relational variable. This isolates phase contribution from confounds.

### Pass Criteria
A probe "supports phase learning" if:
- Baseline margin ≥ +0.5
- Scramble OR Frozen margin drops by ≥ 0.5
- Phase-off does not outperform baseline

## File Structure

```
scripts/phase_probes/
├── phase_probe_runner.py  # Main script
├── probe_cases.py         # 19 synthetic probes (pure data)
├── phase_ablation.py      # Ablation utilities
└── README.md              # This file
```

## Example Output

```
================================================================================
ABLATION COMPARISON SUMMARY
================================================================================
Probe        BL       SC       FR      OFF │    Δ_SC    Δ_FR   Δ_OFF Sens
--------------------------------------------------------------------------------
RB1_A       0.823    0.312    0.445   0.298 │  +0.511  +0.378  +0.525 YES
RB1_B       0.756    0.289    0.401   0.267 │  +0.467  +0.355  +0.489 YES
LP1         0.654    0.187    0.234   0.145 │  +0.467  +0.420  +0.509 YES
...

================================================================================
SUMMARY
================================================================================
--- Accuracy by Mode ---
  Baseline:    78.9%
  Scramble:    42.1%  (Δ = +36.8%)
  Frozen:      47.4%  (Δ = +31.5%)
  Phase-Off:   36.8%  (Δ = +42.1%)

--- Phase Sensitivity ---
  Phase-sensitive probes: 15/19 (78.9%)
  Phase contribution index: 0.4521

--- Scientific Verdict ---
CAN demonstrate that PhaseAttention is learning relational selectivity.
```

## Citation

This diagnostic suite was designed to answer the fundamental question:
> Is PhaseAttention learning real relational selectivity, or is it decorative?

The probes are based on established psycholinguistic test paradigms (Winograd schemas, minimal pairs) adapted for neural network mechanism verification.
