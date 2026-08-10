# PhaseAttention Diagnostic Probe Suite

A comprehensive suite of diagnostic tools to scientifically test what PhaseAttention layers are learning and whether they provide advantages over standard quadratic attention.

## Overview

This suite contains three types of diagnostic tools:

| Tool Type | Purpose | Key Question |
|-----------|---------|--------------|
| **Behavioral Probes** | Test trained models on relational reasoning tasks | "Does this checkpoint exhibit relational selectivity?" |
| **Training Probes** | Train small models on synthetic binding tasks | "Can phase learn relational structure from scratch?" |
| **Hard Generalization Probes** | Test true generalization vs memorization | "Does phase generalize relationally or memorize tokens?" |

## File Structure

```
scripts/phase_probes/
├── README.md                    # This file
├── __init__.py                  # Package init
│
├── # Behavioral Probes (test trained checkpoints)
├── phase_probe_runner.py        # Main behavioral probe runner
├── probe_cases.py               # 25+ synthetic probe definitions
├── phase_ablation.py            # Ablation utilities
│
├── # Training Probes (train from scratch)
├── train_binding_probe.py       # Simple BIND-only training
├── train_probe_schemas.py       # Multi-schema training (5 types)
│
└── hard_probes/                 # Hard generalization benchmark
    ├── README.md                # Detailed scientific rationale
    └── train_hard_probes.py     # Hard generalization training
```

---

## 1. Behavioral Probes (Post-Training Analysis)

### Purpose

Test whether a **trained checkpoint** exhibits relational selectivity. This answers:
> "Can PhaseAttention bind roles, persist entities, and resist interference **by itself**?"

### Usage

```bash
# Run full probe suite with PhaseAttention checkpoint
python phase_probe_runner.py --checkpoint checkpoints/best.pt

# Run with a pre-trained HuggingFace model (baseline comparison)
python phase_probe_runner.py --pretrained gpt2
python phase_probe_runner.py --pretrained gpt2-medium

# Run with verbose output
python phase_probe_runner.py --checkpoint checkpoints/best.pt --verbose

# Run specific probe or category
python phase_probe_runner.py --checkpoint checkpoints/best.pt --probe RB1
python phase_probe_runner.py --checkpoint checkpoints/best.pt --category role_binding

# Save results to JSON
python phase_probe_runner.py --checkpoint checkpoints/best.pt --output results.json
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--checkpoint` | Path to PhaseAttention checkpoint | Required (or --pretrained) |
| `--pretrained` | Use HuggingFace model (gpt2, gpt2-medium, etc.) | None |
| `--probe` | Run specific probe by ID (RB1, LP1, etc.) | All probes |
| `--category` | Run specific category (role_binding, long_range, etc.) | All categories |
| `--verbose` | Show detailed per-probe ablation results | False |
| `--output` | Save results to JSON file | None |

### Probe Categories (25 Total)

| Category | Probes | What It Tests |
|----------|--------|---------------|
| **Role Binding (RB1-RB5)** | Pronoun resolution | Semantic role → antecedent binding |
| **Long-Range Persistence (LP1-LP4)** | Entity tracking | Salience across filler material |
| **Semantic Interference (SI1-SI3)** | Sense disambiguation | Same token, different meanings |
| **Negation/Polarity (NP1-NP3)** | Clause polarity | Negation scope tracking |
| **Amplitude vs Phase (AC1-AC4)** | Phase vs salience | Binding despite high-amplitude distractors |
| **Control (CTRL1-CTRL3)** | Baseline sanity | Simple facts (phase should NOT matter) |
| **Binding-Only (BIND1-BIND3)** | Pure binding | Token-symmetric, structure-different |

### Ablation Modes

| Mode | Effect | Expected Result |
|------|--------|-----------------|
| `baseline` | Normal inference | Best performance |
| `scramble` | Permute phases randomly | Destroys position-phase relationships |
| `frozen` | Set all phases to constant | cos(φ_q - φ_k) = 1 everywhere |
| `phase_off` | Set φ_q = φ_k = 0 | Uniform attention weights |

---

## 2. Training Probes (Train From Scratch)

### Purpose

Train small transformers on synthetic relational binding tasks to test whether PhaseAttention can **learn** relational structure better than quadratic attention.

### 2a. Simple BIND Training (`train_binding_probe.py`)

Single-schema training focused on explicit entity-role binding.

```bash
# Basic run
python train_binding_probe.py

# With custom settings
python train_binding_probe.py --num-steps 5000 --d-model 32 --num-bindings 4
```

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--num-steps` | Training steps | 10000 |
| `--batch-size` | Batch size | 64 |
| `--d-model` | Model dimension | 64 |
| `--num-layers` | Number of layers | 2 |
| `--num-bindings` | Bindings per sample | 3 |
| `--device` | Device (cuda/cpu) | Auto-detect |

### 2b. Multi-Schema Training (`train_probe_schemas.py`)

Trains on 5 schema types simultaneously for comprehensive evaluation.

```bash
# Basic run
python train_probe_schemas.py

# Higher difficulty
python train_probe_schemas.py --num-bindings 6 --filler-length 4

# Smaller model, more samples
python train_probe_schemas.py --d-model 32 --samples-per-schema 5000
```

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--num-steps` | Training steps | 10000 |
| `--batch-size` | Batch size | 64 |
| `--d-model` | Model dimension | 64 |
| `--num-layers` | Number of layers | 2 |
| `--samples-per-schema` | Samples per schema type | 2000 |
| `--num-bindings` | BIND schema complexity | 3 |
| `--filler-length` | LP schema filler length | 2 |
| `--device` | Device (cuda/cpu) | Auto-detect |

#### Schema Types

| Schema | Pattern | What It Tests |
|--------|---------|---------------|
| **RB** (Relational Binding) | `E1 V E2 SEP PRON V2 SEP Q PRON →` | Pronoun resolution via verb semantics |
| **BIND** (Entity-Role) | `BIND E R BIND E R ... SEP Q R →` | Explicit binding and retrieval |
| **NP** (Negation Polarity) | `E V [NEG] CTX SEP Q V →` | Negation scope affects answer |
| **LP** (Long Persistence) | `E V SEP [filler] SEP PRON V SEP Q PRON →` | Entity tracking across distance |
| **SI** (Symbol Indirection) | `E CTX SEP E CTX SEP Q E →` | Same symbol, different referent |

---

## 3. Hard Generalization Probes (`hard_probes/`)

### Purpose

Test **true relational generalization** vs token memorization. This is the definitive test for whether PhaseAttention learns relational structure.

### Why This Exists

Previous probe datasets were "too easy" — both architectures achieved ~100% accuracy because quadratic attention could memorize token-specific patterns. This benchmark systematically removes memorization shortcuts.

### Key Constraints

| Constraint | Implementation | Why Quadratic Fails |
|------------|----------------|---------------------|
| **Held-out Roles** | Train: R0-R3, Test: R4-R6 | Learns token-specific patterns |
| **Open-world Entities** | Train: E0-E7, Test: E8-E15 | Memorizes entity-output mappings |
| **Schema Composition** | Multi-step chains with overwrites | Single-pattern matching fails |
| **Role Permutation** | PERMUTE R0 R1 swaps bindings | Cannot dynamically swap meanings |
| **Long Chains** | Train: 3-5 steps, Test: 6-8 steps | Attention span is limited |

### Usage

```bash
# Basic run
python hard_probes/train_hard_probes.py

# BIND-dominant curriculum (recommended)
python hard_probes/train_hard_probes.py --bind-ratio 0.7

# Parameter-matched comparison (fairness control)
python hard_probes/train_hard_probes.py --match-params

# Maximum difficulty
python hard_probes/train_hard_probes.py \
    --bind-ratio 0.8 \
    --test-chain-min 7 \
    --test-chain-max 10 \
    --match-params

# Full scientific run
python hard_probes/train_hard_probes.py \
    --bind-ratio 0.7 \
    --match-params \
    --num-steps 20000 \
    --test-chain-min 7 \
    --test-chain-max 10
```

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--d-model` | Model dimension | 64 |
| `--num-heads` | Attention heads | 4 |
| `--num-layers` | Number of layers | 2 |
| `--d-ff` | FFN dimension | 128 |
| `--num-steps` | Training steps | 15000 |
| `--batch-size` | Batch size | 64 |
| `--lr` | Learning rate | 1e-3 |
| `--train-samples` | Training samples | 20000 |
| `--test-samples` | Samples per test split | 1000 |
| `--bind-ratio` | Ratio of BIND-dominant schemas (0.0-1.0) | 0.6 |
| `--train-chain-min` | Min chain length for training | 3 |
| `--train-chain-max` | Max chain length for training | 5 |
| `--test-chain-min` | Min chain length for testing | 6 |
| `--test-chain-max` | Max chain length for testing | 8 |
| `--match-params` | Add extra FF to quadratic for fair comparison | False |
| `--device` | Device (cuda/cpu) | Auto-detect |

#### Test Splits (Reported Separately)

| Split | Entities | Roles | Chain Length | Tests |
|-------|----------|-------|--------------|-------|
| `train` | E0-E7 | R0-R3 | 3-5 | Training accuracy |
| `test_roles` | E0-E7 | **R4-R6** | 3-5 | Role generalization |
| `test_entities` | **E8-E15** | R0-R3 | 3-5 | Entity generalization |
| `test_both` | **E8-E15** | **R4-R6** | 3-5 | Full generalization |
| `test_long` | E0-E7 | R0-R3 | **6-8** | State persistence |

#### Schema Types

| Schema | Description | Why Quadratic Fails |
|--------|-------------|---------------------|
| **BIND_CHAIN** | Multiple bindings with overwrites | Returns first binding, not last |
| **BIND_NEG** | Scoped negation of specific roles | Cannot track per-role negation |
| **CHAIN_DEEP** | 4-8 step chains with filler | Attention span limits |
| **PERMUTE_BIND** | Role swapping | Fixed token-attention patterns |
| **SI_BIND** | Context-varied bindings | Cannot distinguish contexts |
| **LP_BIND** | Long persistence + binding | Entity salience decays |

#### Expected Results

```
                         Train Acc    Test Acc (avg)
Quadratic Attention:     ~95%         <40%
Phase Attention:         ~95%         >70%
```

#### Success Criteria

1. **Quadratic memorizes training**: Train accuracy > 85%
2. **Quadratic fails generalization**: Average test accuracy < 50%
3. **Phase generalizes**: Phase > Quadratic + 15% on test
4. **Phase is causal**: Ablation (scramble/freeze) drops accuracy significantly

---

## Interpreting Results

### Behavioral Probes Verdict

| Verdict | Meaning |
|---------|---------|
| **CAN demonstrate relational selectivity** | >50% probes phase-sensitive, ablations hurt |
| **CANNOT conclusively demonstrate** | <50% sensitive, low contribution index |

### Training Probes Verdict

| Verdict | Meaning |
|---------|---------|
| **HYPOTHESIS SUPPORTED** | Phase outperforms + ablations hurt significantly |
| **PARTIAL SUPPORT** | Phase is causal but doesn't outperform quadratic |
| **HYPOTHESIS FALSIFIED** | No advantage, phase may be decorative |

### Hard Probes Verdict

| Verdict | Meaning |
|---------|---------|
| **HYPOTHESIS STRONGLY SUPPORTED** | All 4 criteria pass — true relational generalization |
| **HYPOTHESIS SUPPORTED** | Phase wins but quadratic didn't fail hard enough |
| **DATASET TOO EASY** | Quadratic > 50% on test — increase difficulty |
| **INCONCLUSIVE** | Mixed results, need more analysis |

---

## Phase Health Metrics

| Metric | Healthy Range | Meaning |
|--------|---------------|---------|
| **R_k** (Mean Resultant Length) | < 0.3 | Phase diversity (0=uniform, 1=collapsed) |
| **R_q** | < 0.3 | Query phase diversity |
| **Phase Drift** | > 0.1 | Phases change across positions |
| **Head Entropy** | > 0.5 | Heads contribute diversely |

---

## Scientific Rationale

### Why These Probes Matter

1. **Behavioral Probes**: Verify that trained models use phase for relational tasks
2. **Training Probes**: Test if phase can *learn* relational structure
3. **Hard Probes**: Distinguish memorization from true generalization

### Evolution of the Suite

| Stage | Finding | Next Step |
|-------|---------|-----------|
| Behavioral probes | Phase is used, but need controlled comparison | Create training probes |
| Training probes (easy) | Both achieve 100%, "PARTIAL SUPPORT" | Phase is causal but task too easy |
| Training probes (hard) | Need to break memorization shortcuts | Create hard generalization probes |
| Hard probes | Tests true relational generalization | Definitive evidence |

### Key Insight

> The goal is not just "does phase help?" but "does phase enable a *different kind* of learning?"

Quadratic attention can memorize token-specific patterns. PhaseAttention should learn relational structure that generalizes to new tokens. The hard probes test exactly this distinction.

---

## Citation

This diagnostic suite was designed to answer:
> Is PhaseAttention learning real relational selectivity, or is it decorative?

The probes are based on:
- Psycholinguistic test paradigms (Winograd schemas, minimal pairs)
- Compositional generalization literature
- State space models vs attention comparisons
