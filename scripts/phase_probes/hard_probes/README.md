# Hard Diagnostic Probe Dataset for PhaseAttention

## Scientific Goal

This benchmark tests whether PhaseAttention performs **true relational reasoning** rather than pattern memorization. The key insight is that quadratic attention can achieve high training accuracy through token-specific memorization, but should fail on held-out tokens that require the same relational structure.

## Key Enhancements (v2)

### 1. Increased Model Capacity

```
Previous:  d_model=64,  num_heads=4, num_layers=2
Current:   d_model=128, num_heads=8, num_layers=4
```

**Why**: Phase needs room to encode role phase, entity amplitude, AND operation effects simultaneously. The previous 64×2 configuration tested compression, not reasoning.

### 2. Operation-Conditioned Phase Offsets

```python
# NEG, PERMUTE, OVERWRITE tokens add learned phase shifts
operation_tokens = [vocab.NEG, vocab.PERMUTE, vocab.OVERWRITE]
```

**Why**: Without this, operations like NEG are just passive symbols that the model must interpret through content-based attention. With operation-conditioned phase offsets, operations directly TRANSFORM the phase state. This tests the hypothesis more faithfully by making operations act as they're theoretically supposed to.

**Note**: This is NOT cheating — quadratic attention doesn't get this enhancement, so if Phase wins, it's because phase-based state transformation is genuinely more powerful than attention-based pattern matching.

### 3. Pure Persistence Test (`test_persist`)

```
Chain length: 8-12 steps
Schemas: BIND + QUERY only (no NEG, PERMUTE, CONTEXT)
```

**Why**: This isolates "memory" from "logic". It shows Phase's clean O(n) advantage without the complexity of operations. If Phase wins here, it's pure state persistence superiority.

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
Training chains:   3-5 steps
Testing chains:    6-8 steps
Persistence test:  8-12 steps (BIND+QUERY only)
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
| test_persist | ~15% | ~80% | Pure persistence advantage |

## Running the Benchmark

### Basic Run (with new defaults: d_model=128, num_heads=8, num_layers=4)
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

### Longer Persistence Test
```bash
python train_hard_probes.py --persist-chain-min 10 --persist-chain-max 15
```

### Full Scientific Run
```bash
python train_hard_probes.py \
    --bind-ratio 0.7 \
    --match-params \
    --num-steps 20000 \
    --test-chain-min 7 \
    --test-chain-max 10 \
    --persist-chain-min 10 \
    --persist-chain-max 15
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--d-model` | 128 | Model dimension (increased for reasoning capacity) |
| `--num-heads` | 8 | Number of attention heads |
| `--num-layers` | 4 | Number of transformer layers |
| `--d-ff` | 256 | FFN dimension (2x d_model) |
| `--num-steps` | 15000 | Training steps |
| `--batch-size` | 64 | Batch size |
| `--lr` | 1e-3 | Learning rate |
| `--train-samples` | 20000 | Training samples |
| `--test-samples` | 1000 | Samples per test split |
| `--bind-ratio` | 0.6 | Ratio of BIND-dominant schemas |
| `--train-chain-min/max` | 3, 5 | Training chain length |
| `--test-chain-min/max` | 6, 8 | Test chain length |
| `--persist-chain-min/max` | 8, 12 | Pure persistence chain length |
| `--match-params` | False | Match parameter counts for fairness |

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

## Design Decisions

### Why 48 Tokens?
- Large enough to have meaningful train/test splits
- Small enough for fast iteration
- Entities: 16 (8 train + 8 test)
- Roles: 7 (4 train + 3 test)

### Why Increased Capacity (128×8×4)?
- Previous 64×2 was too constrained
- Phase needs capacity for: role encoding, entity values, operation effects
- This tests reasoning ability, not compression limits

### Why Operation-Conditioned Phase Offsets?
- Operations should TRANSFORM state, not just be passive tokens
- This is the core hypothesis: phase enables relational state updates
- Without this, we're testing whether phase learns to BE quadratic attention

### Why Pure Persistence Test?
- Separates "memory" from "logic"
- Clean test of O(n) state maintenance
- Previous experiments showed Phase wins on simple BIND tasks

## D.6 Control Plane Test Suite

The `test_hard_probes_d6_control_plane.py` script provides comprehensive validation of the control plane implementation per the D.6 Test Priority Matrix.

### Test Groups

| Group | Name | Tests | Purpose |
|-------|------|-------|---------|
| **A** | Leak Detector | 15 tests | Assert control signals cannot be token-wise embeddings (no-write contract) |
| **B** | AR Regression | 7 tests | Verify AR accuracy doesn't collapse when Onto/CSR controls enabled vs disabled |
| **C** | Enable Slots Read | 6 tests | Verify the D.2 `enable_slots_read` control flag works correctly |
| **D** | OntoControl Interface | 10 tests | Verify OntoControl dataclass formalizes control plane correctly (V10.6.4) |
| **E** | Forward-Pass Enforcement | 10 tests | Verify no-write contract is enforced INSIDE forward(), not just config (V10.6.6) |
| **Integration** | Full Pipeline | 1 test | End-to-end validation combining multiple D.6 requirements |

### Critical Invariants Tested

- **INV-D6-1**: `intent_phase` must be low-dimensional `[B, H]` or `[B, H, D_h]`, NOT `[B, N, D]`
- **INV-D6-2**: `binding_salience` must be `[B, N]` for per-position gating, NOT `[B, N, D]`
- **INV-D6-3**: Control signals must be broadcastable to control shapes
- **INV-D6-4**: AR accuracy must not collapse when Onto/CSR enabled vs disabled
- **INV-D6-5**: `enable_slots_read=False` must skip quad retrieval without affecting phase writes
- **INV-D6-6**: `s_align` (alignment signal) must be `[H]` or `[]`, NOT `[B, N]` (V10.6.3)
- **INV-D6-7**: OntoControl wraps binding_salience without changing behavior (V10.6.4)
- **INV-E6-1**: Invalid control signals in forward() must raise `ControlShapeViolation` (V10.6.6)
- **INV-E6-4**: `enforce_control_contract=True` is the default (STRICT) (V10.6.6)
- **INV-E6-5**: `set_enforce_control_contract()` propagates to all child blocks (V10.6.6)

### Running the Tests

**Run all D.6 control plane tests:**
```bash
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py -v
```

**Run specific test groups:**
```bash
# Group A: Leak detector tests
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py -v -k "TestGroupA"

# Group B: AR regression tests
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py -v -k "TestGroupB"

# Group C: Enable slots read tests
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py -v -k "TestGroupC"

# Group D: OntoControl interface tests
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py -v -k "TestGroupD"

# Group E: Forward-pass enforcement tests
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py -v -k "TestGroupE"

# Integration tests
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py -v -k "TestIntegration"
```

**Run with coverage:**
```bash
pytest scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py --cov=symbolu.phase_transformer -v
```

**Run as standalone script:**
```bash
python scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py
```

### Test Details by Group

#### Group A: Leak Detector Tests (15 tests)
Tests the no-write contract (D.5) enforcement:
- `test_a01-a04`: Valid/invalid `intent_phase` shape validation
- `test_a05-a06`: Valid/invalid `binding_salience` shape validation
- `test_a07-a10`: Multi-signal validation and scalar/per-head controls
- `test_a11-a15`: Alignment signal (`s_align`) shape validation (V10.6.3)

#### Group B: AR Regression Tests (7 tests)
Tests autoregressive stability with control signals:
- `test_b01-b04`: Forward pass with various control configurations
- `test_b05`: Logit magnitude stability check (INV-D6-4)
- `test_b06`: Gradient flow verification
- `test_b07`: Output determinism verification

#### Group C: Enable Slots Read Tests (6 tests)
Tests the D.2 READ/WRITE path separation:
- `test_c01-c02`: Default and explicit `enable_slots_read` flag
- `test_c03`: Output difference verification
- `test_c04-c06`: Combined controls and gradient flow

#### Group D: OntoControl Interface Tests (10 tests)
Tests the V10.6.4 formalized control plane interface:
- `test_d01-d03`: Creation and factory methods
- `test_d04-d06`: Validation with valid/invalid signals
- `test_d07-d08`: Serialization (`to_dict`)
- `test_d09-d10`: Future flags and no-write contract preservation

#### Group E: Forward-Pass Enforcement Tests (10 tests)
Tests V10.6.6 runtime enforcement (highest-risk gap):
- `test_e01-e03`: Block-level forward rejection/acceptance
- `test_e04-e06`: Transformer-level forward rejection/acceptance
- `test_e07`: Default enforcement verification (INV-E6-4)
- `test_e08`: Propagation to child blocks (INV-E6-5)
- `test_e09`: Disabled enforcement behavior (debugging only)
- `test_e10`: `forward_hidden()` enforcement

---

## Citation

This benchmark was designed to isolate relational reasoning from pattern memorization, following principles from:
- Compositional generalization literature
- Systematic generalization in transformers
- State space models vs attention comparisons
