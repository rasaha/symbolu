# Hard Diagnostic Probe Dataset for PhaseAttention

## Scientific Goal

This benchmark tests whether PhaseAttention performs **true relational reasoning** rather than pattern memorization. The key insight is that quadratic attention can achieve high training accuracy through token-specific memorization, but should fail on held-out tokens that require the same relational structure.

## Why the Previous Dataset Failed

The original probe dataset allowed both architectures to succeed because:

| Problem | What Quadratic Learns | Why It Works |
|---------|----------------------|--------------|
| Fixed role tokens | "R0 at position X → attend there" | Memorized attention patterns |
| Fixed entity tokens | "E3 often correct for BIND" | Token-specific output mapping |
| Single schema per sample | "BIND pattern → template match" | No state tracking needed |
| Short sequences (≤32) | Everything visible in attention | No persistence required |

**Result**: Both architectures achieved ~100% accuracy, showing "PARTIAL SUPPORT" at best.

## How This Dataset Fixes the Problems

### 1. Held-Out Role Generalization

```
Training:  R0, R1, R2, R3
Testing:   R4, R5, R6 (NEVER seen in training)
```

**Why quadratic fails**: It learns token-specific attention patterns. R4 has no learned pattern → random performance.

**Why phase succeeds**: Phase encodes roles as relative phase offsets. New roles get new offsets → same relational mechanism works.

### 2. Open-World Entity Generalization

```
Training:  E0, E1, ..., E7
Testing:   E8, E9, ..., E15 (NEVER seen in training)
```

**Why quadratic fails**: It learns "E3 → class 3" mappings. New entities have random embeddings → memorization breaks.

**Why phase succeeds**: Entities are values in the state, not memorized token patterns. New entities slot into the same state mechanism.

### 3. Schema Composition

Each sample combines multiple operations that require intermediate state:

```
BIND E1 R0 | BIND E2 R1 | BIND E3 R0 | QUERY R0 → E3
                         ↑
                    Overwrites E1!
```

**Why quadratic fails**: Pattern matching finds "first BIND with R0" → returns E1 (wrong).

**Why phase succeeds**: Cumsum state naturally accumulates. Later bindings overwrite earlier ones.

### 4. Role Permutation Probe

```
BIND E1 R0 | BIND E2 R1 | PERMUTE R0 R1 | QUERY R0 → E2
```

**Why quadratic fails**: R0 always attends to the same learned positions. Cannot dynamically swap.

**Why phase succeeds**: PERMUTE swaps phase offsets → queries work with new assignments.

### 5. Long-Chain State Persistence

```
Training chains:  3-5 steps
Testing chains:   6-8 steps
```

**Why quadratic fails**: Attention span is limited. Early information is "washed out" by later processing.

**Why phase succeeds**: Cumsum has O(n) complexity with no span limitation. State persists arbitrarily.

## Expected Results

```
                         Train Acc    Test Acc
Quadratic Attention:     ~95%         <40%
Phase Attention:         ~95%         >70%
```

### Per-Split Breakdown (what we expect)

| Test Split | Quadratic | Phase | Why |
|------------|-----------|-------|-----|
| test_roles | ~25% | ~75% | Role memorization breaks |
| test_entities | ~35% | ~80% | Entity memorization breaks |
| test_both | ~20% | ~70% | Both fail together |
| test_long | ~20% | ~65% | Attention span limit |

## Running the Benchmark

### Basic Run
```bash
python train_hard_probes.py
```

### BIND-Dominant Curriculum (Recommended)
```bash
python train_hard_probes.py --bind-ratio 0.7
```

### Parameter-Matched Comparison
```bash
python train_hard_probes.py --match-params
```

### Harder Test (longer chains)
```bash
python train_hard_probes.py --test-chain-min 7 --test-chain-max 10
```

### Full Scientific Run
```bash
python train_hard_probes.py \
    --bind-ratio 0.7 \
    --match-params \
    --num-steps 20000 \
    --test-chain-min 7 \
    --test-chain-max 10
```

## Interpreting Results

### Success Criteria

1. **Quadratic memorizes training**: Train accuracy > 85%
2. **Quadratic fails generalization**: Average test accuracy < 50%
3. **Phase generalizes**: Phase > Quadratic + 15% on test
4. **Phase is causal**: Ablation (scramble/freeze) drops accuracy significantly

### Verdict Meanings

| Verdict | Meaning |
|---------|---------|
| HYPOTHESIS STRONGLY SUPPORTED | All 4 criteria pass. Phase demonstrates true relational generalization. |
| HYPOTHESIS SUPPORTED | Phase wins but quadratic didn't fail hard enough. |
| DATASET TOO EASY | Quadratic > 50% on test. Increase difficulty. |
| INCONCLUSIVE | Mixed results, need more analysis. |

## Key Ablation Modes

| Mode | What It Does | Expected Effect |
|------|-------------|-----------------|
| `none` | Baseline (normal operation) | Best accuracy |
| `scramble` | Randomize phase positions | Should drop significantly |
| `freeze` | Zero all phases | Should drop significantly |
| `off` | Disable phase computation | Same as freeze |

If ablations don't hurt, phase is "decorative" (not causally necessary).

## File Structure

```
hard_probes/
├── train_hard_probes.py    # Main training script (this file)
└── README.md               # Scientific documentation (this file)
```

## Design Decisions

### Why 48 Tokens?
- Large enough to have meaningful train/test splits
- Small enough for fast iteration
- Entities: 16 (8 train + 8 test)
- Roles: 7 (4 train + 3 test)

### Why Chain Length 3-5 / 6-8?
- Training on shorter chains prevents length-based memorization
- Testing on longer chains reveals state persistence limits
- O(n²) attention struggles more at longer lengths

### Why BIND-Dominant Ratio?
- Previous experiments showed phase advantage scales with relational pressure
- 60-70% BIND schemas creates enough binding-heavy samples
- Remaining 30-40% are SI/LP for variety

## Citation

This benchmark was designed to isolate relational reasoning from pattern memorization, following principles from:
- Compositional generalization literature
- Systematic generalization in transformers
- State space models vs attention comparisons
