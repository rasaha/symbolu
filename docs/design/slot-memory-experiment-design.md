# Slot Memory Experiment Design: Read Interval + Late-Layer Writes

## Context

SlotMemoryGCT (`phase_transformer.py:8386`) is a 64-slot addressable key-value
memory that reads at every layer and writes at `global_update_interval` (default 1).
The version history (V10.14 through V11.x) documents ~15 stability fixes:
gradient explosions, slot collapse, gate starvation, winner-take-all routing.

The hypothesis: slots may be over-influencing the residual stream (reads at every
layer) and capturing low-level representations (writes at every layer). Two
targeted experiments test this without removing the system.

---

## Experiment 1: Global Read Interval

### Rationale

Slot reads happen unconditionally at every layer (`phase_transformer.py:7153-7162`).
Write frequency is already gated by `global_update_interval`, but reads have no
equivalent control. Each read injects `alpha * slot_out.detach()` into the
residual — repeated across all 12 layers, this amplifies any instability in
slot content through the full transformer stack.

### Change

Add `global_read_interval: int` parameter (default 1 = current behavior).

**Model constructor** (`HybridPhaseTransformer.__init__`, line ~6734):
```
global_read_interval: int = 1,  # Read slots every N layers (1 = every layer)
```
Store as `self.global_read_interval`.

**Forward loop** (`phase_transformer.py:7150-7162`):
```python
# Current: reads unconditionally
if self.global_tokens_enabled:
    if self.global_update_mode == "slots":
        _slot_out = self.slot_memory.read(x, _slot_keys, _slot_vals)
        ...

# Changed: read only every N layers
if self.global_tokens_enabled:
    if self.global_update_mode == "slots":
        if (i % self.global_read_interval) == 0:
            _slot_out = self.slot_memory.read(x, _slot_keys, _slot_vals)
            _alpha = self.slot_memory.read_warmstart_alpha
            x = x + _alpha * _slot_out.detach()
```

Same change in `forward_chunk` (`phase_transformer.py:7378`).

**CLI arg** (`train_unified_llm_clean.py`, near line 7140):
```
parser.add_argument("--global_read_interval", type=int, default=1,
                   help="Read slots every N layers (default: 1 = every layer)")
```

Pass through config to model constructor.

### Test matrix

| Config | Read interval | Expected effect |
|--------|--------------|-----------------|
| Baseline | 1 (every layer) | Current behavior |
| Moderate | 3 (every 3rd layer) | 4 reads across 12 layers |
| Sparse | 4 (every 4th layer) | 3 reads across 12 layers |

### Metrics to watch

- PPL delta vs baseline (slot ablation already measures this)
- `slot_read_entropy` — should be more structured with fewer reads
- `slot_assignment_entropy` — should be unaffected (writes unchanged)
- Sample quality — the primary signal; PPL alone is insufficient
- Training curve smoothness (loss variance over 100-step windows)

---

## Experiment 2: Late-Layer-Only Writes

### Rationale

Currently writes happen at every `global_update_interval` layers (default: every
layer). Early layers produce low-level / syntactic representations. When these
write into slots, the memory fills with noisy content that:
- doesn't represent semantic abstractions
- creates long gradient paths back through many layers
- was implicated in the step-650 gradient explosions (V10.14.9 fix: detaching
  `_slot_hidden`)

### Change

Add `global_write_start_layer: int` parameter. Writes only happen at layers >= this
value, AND still respecting `global_update_interval`.

**Model constructor** (`HybridPhaseTransformer.__init__`, line ~6734):
```
global_write_start_layer: int = 0,  # Only write to slots from this layer onward
```
Store as `self.global_write_start_layer`.

**Forward loop** (`phase_transformer.py:7173-7184`):
```python
# Current:
if self.global_tokens_enabled and self.global_update_enabled:
    if (i % self.global_update_interval) == 0:
        if self.global_update_mode == "slots":
            _slot_keys, _slot_vals = self.slot_memory.write(...)

# Changed:
if self.global_tokens_enabled and self.global_update_enabled:
    if (i % self.global_update_interval) == 0 and i >= self.global_write_start_layer:
        if self.global_update_mode == "slots":
            _slot_keys, _slot_vals = self.slot_memory.write(...)
```

Same change in `forward_chunk` (`phase_transformer.py:7389`).

**CLI arg**:
```
parser.add_argument("--global_write_start_layer", type=int, default=0,
                   help="Only write to slots from this layer onward (default: 0)")
```

### Test matrix (12-layer model)

| Config | Write start | Write layers | Description |
|--------|------------|-------------|-------------|
| Baseline | 0 | 0-11 | Current: all layers write |
| Upper half | 6 | 6-11 | Only semantic layers write |
| Upper third | 8 | 8-11 | Late-layer summaries only |

### Metrics to watch

- `slot_write_gate` — should be higher per-write (fewer but more meaningful)
- `slot_marginal_entropy` — should improve (less noise → less collapse pressure)
- Gradient norms on `slot_keys_init` — the primary stability signal
- Sample quality vs PPL trade-off

---

## Experiment Ordering

1. **First**: Run read interval experiment alone (3 or 4). This is the least
   invasive change — it only reduces how often slot content reaches the residual.
   If this alone stabilizes training and improves samples, write changes may be
   unnecessary.

2. **Second**: If read interval helps but instability remains, add late-layer
   writes (start_layer=6 or 8).

3. **Third**: If both help, run the slot ablation (`--global_tokens_enabled=False`)
   with the same sample-quality evaluation to determine if the improved slot
   system actually earns its keep vs Phase+Quad alone.

---

## What This Does NOT Change

- Slot count stays at 64 (no reduction yet)
- Write gate initialization stays at sigmoid(1.0) ≈ 0.73
- Orthogonality loss, balance loss, sharpness loss unchanged
- Read warmstart ramp unchanged
- Retrieval loss and its detach strategy unchanged

These are minimal, targeted experiments. If they fail to show benefit, the next
step is slot count reduction (64→32→16), then full removal.

---

## Files Touched

| File | Change |
|------|--------|
| `symbolu/phase_transformer.py` | Add `global_read_interval` and `global_write_start_layer` params to `HybridPhaseTransformer.__init__`; gate read/write in forward loops |
| `train_unified_llm_clean.py` | Add CLI args, pass through to model config |
| `symbolu/training/unified/train.py` | Same CLI args if this training script is used |
