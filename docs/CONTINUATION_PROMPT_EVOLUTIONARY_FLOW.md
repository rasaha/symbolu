# Continuation Prompt: Evolutionary Flow System Implementation

Use this prompt to continue the discussion in a new session.

---

## Copy-Paste Prompt for New Session

```
I'm continuing work on the Sovereign-1 Evolutionary Flow System implementation. Here's the context:

## Project: SymbolU - Sovereign-1 Training Optimization

### What Was Implemented (Phases 1-5 Complete)

**Phase 1: Core Classes** (Commit: e481ca1)
- `EvolutionaryGate`: Bidirectional gates for each O(n)→O(n+1) transition
- `EvolutionaryFlowNetwork`: 11 forward gates + 1 toroidal gate (O12→O1)
- `EvolutionaryFlowLoss`: Multi-scale loss (micro/meso/macro)
- `EvolutionaryIntelligenceEngine`: Master controller

**Phase 2: Training Loop Integration** (Commit: d6fd602)
- Delayed Resonance: `O1' = O1 + (α × O12_prev)` - injects previous O12 into current O1
- Hidden state extraction from model outputs
- Loss integration: `total_loss = main_loss + evo_lambda * evo_loss`
- Guna-aware metacognitive LR modulation

**Phase 3: CLI Arguments** (Commit: d6fd602)
- `--enable_evolutionary_flow` (default: True)
- `--evo_lambda 0.1` (overall loss weight)
- `--evo_micro_weight 0.3`, `--evo_meso_weight 0.3`, `--evo_macro_weight 0.4`
- `--evo_resonance_alpha 0.1` (O12→O1 injection strength)
- `--evo_lr_modulation`, `--evo_lr_slowdown 0.5`, `--evo_lr_accelerate 1.2`

**Phase 4: TensorBoard Logging** (Commit: d6fd602)
- `evo/coherence_micro`, `evo/coherence_authority`, `evo/coherence_sensory`
- `evo/coherence_toroidal`, `evo/meso_delta`, `evo/metacog_state`
- `evo/lr_multiplier`, `evo/loss_*` components

**Phase 5: Delayed Resonance** (Merged with Phase 2)
- Resonance buffer stores detached hidden states from previous step
- O12 (Authority/Integration) injects into O1 (Potential/Sensory)

### Key Files

1. **train_unified_llm.py** - Main training script with:
   - `EvolutionaryIntelligenceEngine` class (line ~1162)
   - `EvolutionaryFlowNetwork` class (line ~907)
   - `MetacognitiveTracker` with BRAKE/SLOW_DOWN/RECOVER/ACCELERATE/STABILIZE/CONTINUE
   - `SOVEREIGN_R_MATRIX` (5×12 Vṛtti-Layer probability matrix)
   - CLI args for evolutionary flow (line ~4512)
   - Training loop integration (line ~5474)

2. **stress_test_evolutionary_flow.py** - Pre-flight stress test with:
   - Probe 1: Causal Anchor (IF/THEN logic persistence)
   - Probe 2: Entropy Gradient (Authority stiffness vs noise)
   - Probe 3: Recursive Loop (Delayed Resonance buffer test)
   - Green Light thresholds check

3. **docs/design/EVOLUTIONARY_FLOW_SYSTEM_DESIGN.md** - Design document (v1.1)

### 9:3 Meso-Scale Split Alignment

- **Authority gates 0-7**: O1→O2 through O8→O9 (8 gates, 9 "Senior Architect" layers)
- **Sensory gates 8-10**: O9→O10 through O11→O12 (3 gates, 3 "Junior Coder" layers)

### Metacognitive Recommendations

| Status | Icon | LR Factor | Condition |
|--------|------|-----------|-----------|
| BRAKE | 🛑 | 0.5× | Coherence alarm + rapid drop |
| SLOW_DOWN | 🐢 | 0.7× | Coherence below threshold |
| RECOVER | 🔄 | 1.05× | High Tamas + flat coherence |
| STABILIZE | ⚓ | 1.0× | Declining trend |
| CONTINUE | ➡️ | 1.0× | Default state |
| ACCELERATE | 🚀 | 1.2× | High Sattva + rising coherence |

### Next Steps

1. **Run the stress test** to verify Toroidal Bridge connectivity:
   ```bash
   python stress_test_evolutionary_flow.py --device cuda
   ```

2. **Check Green Light thresholds**:
   - Meso-Delta > 0.1 (Authority leading)
   - Toroidal Coherence > 0.0 (Bridge connected)
   - Sattva > 0.3 (Clarity present)
   - Resonance Buffer ACTIVE

3. **If GREEN LIGHT**, start 20,000-step WikiText-103 training:
   ```bash
   python train_unified_llm.py \
       --model_type ontological \
       --model_size small \
       --max_steps 20000 \
       --enable_evolutionary_flow \
       --evo_lambda 0.1 \
       --use_9_3_split \
       --tensorboard
   ```

4. **Monitor at Step 100/1000**:
   - Toroidal > 0.10 = O12→O1 bridge passing "essence"
   - Meso Delta > 0 = Authority dominant (9:3 working)
   - Metacog = STABILIZE/CONTINUE/ACCELERATE = healthy

### Console Output Format

```
Step    100 | Loss:3.21 | PPL:24.8 | S/A:0.15+ | GC:0.72~ | Conf:0.65✓
    --> [EvoFlow] Micro:0.45 | Auth:0.52 Sens:0.38+ | Toroid:0.12 | CONT➡️
```

### Git Branch

Working on: `claude/sovereign-1-evaluation-Q66nP`

### What I Need Help With

[Describe what you want to do next - run stress test, start training, analyze results, etc.]
```

---

## Quick Reference

### Key Commits (in order)
1. `e481ca1` - Phase 1: Core Evolutionary Flow classes
2. `b826530` - Design document v1.0
3. `d6fd602` - Phase 2-5: Training integration, CLI, TensorBoard, Delayed Resonance
4. `3d43180` - Design document v1.1
5. `4dc9d5c` - Pre-flight stress test script

### Key Concepts
- **Toroidal Flow**: O1→O2→...→O12→O1 cyclic cognitive evolution
- **Delayed Resonance**: Previous step's O12 injected into current O1
- **Multi-scale Coherence**: Micro (per-gate), Meso (9:3 clusters), Macro (toroidal)
- **R-Matrix**: 5×12 Vṛtti probabilities guiding evolutionary pressure
- **Training Gunas**: Sattva (clarity), Rajas (activity), Tamas (inertia)

### Important Thresholds
- Toroidal Coherence > 0.10 at Step 100 = healthy
- Meso Delta (Auth - Sens) > 0 = 9:3 split working
- Metacog recommendation = CONTINUE/ACCELERATE = optimal
