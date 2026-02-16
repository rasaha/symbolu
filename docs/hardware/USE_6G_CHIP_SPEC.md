# USE-6G Massive MIMO Synchronization Chip

## Hardware Specification v1.0

**Classification:** CONFIDENTIAL — Patent-Adjacent Technical Specification
**Revision:** 1.0
**Date:** 2025-01-15
**Inventor:** Rakesh Mohan
**Reference:** UCP Spec Section 5.1 (6G Telecom: $110B/yr TAM)

---

## 1. Executive Summary

The USE-6G is a purpose-built silicon accelerator for 6G Massive MIMO phase synchronization. It implements the USE patent formulas (U1–U5) in dedicated hardware to achieve O(n) antenna element synchronization at sub-THz frequencies, targeting the phone form factor within the UCP-Edge power envelope.

Current 5G baseband processors use software-driven phase calibration with O(n²) pairwise correlation — limiting antenna counts and requiring millisecond-scale convergence. The USE-6G chip replaces this with hardware-accelerated mean-field synchronization that scales linearly, converges in microseconds, and maintains phase lock under mobility and panel handover.

### 1.1 Key Specifications

| Parameter | Specification | 5G Baseband Comparison |
|-----------|---------------|------------------------|
| **Phase Precision** | ±100 picoseconds | ±1 ns (10× worse) |
| **Sync Complexity** | O(n) mean-field | O(n²) pairwise |
| **Convergence Time** | <500 μs to phase lock | >5 ms |
| **Antenna Elements** | 128 (8×8 × 2 panels) | 32–64 typical |
| **Simultaneous Beams** | 4 | 1–2 |
| **Carrier Frequency** | 100–300 GHz (sub-THz) | 24–71 GHz (mmWave) |
| **Channel Bandwidth** | 10 GHz | 400 MHz–2 GHz |
| **Sync Update Rate** | 100K updates/sec | ~1K updates/sec |
| **Beam Steers/sec** | 10K | ~500 |
| **Process Node** | 4 nm | 7 nm / 5 nm |
| **Die Area** | ≤25 mm² | 50–100 mm² |
| **Power (total)** | ≤20 W | 5–10 W (fewer elements) |
| **Power (sync only)** | ≤5 W | N/A (shared with DSP) |
| **Form Factor** | Phone (UCP-Edge) | Phone/base station |

### 1.2 USE Patent Formula Mapping

The five USE patent formulas map directly to hardware functional units:

| Formula | Name | Hardware Unit | Silicon Function |
|---------|------|---------------|------------------|
| **U1** | Cross-Modal Correlation Matrix | Correlation Engine (CE) | Windowed pairwise cos(Δφ) over W=16 samples |
| **U2** | Coherence-Weighted Fusion | Coherence Accumulator (CA) | Σ M_ij · C[i,j] normalized to [-1,1] |
| **U3** | Mean-Field Gradient | Mean-Field Unit (MFU) | O(n) gradient: −sin(φ_i − φ̄) via circular mean |
| **U4** | Phase Update Rule | Phase Update Engine (PUE) | φ_i(t+1) = (φ_i(t) + α·∇) mod 2π |
| **U5** | Correlation Interpretation | Threshold Comparator (TC) | >0.7 strong, 0.3–0.7 moderate, <0.3 weak |

---

## 2. System Architecture

### 2.1 Top-Level Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USE-6G CHIP TOP LEVEL                              │
│                        4nm · ≤25 mm² · ≤20 W                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EXTERNAL INTERFACES                                                        │
│  ═══════════════════                                                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  RF FRONT END │    │   BASEBAND   │    │   UCP-Edge   │                  │
│  │  INTERFACE    │    │   INTERFACE  │    │   INTERFACE  │                  │
│  │  (128 elem)  │    │   (SPI/I2C)  │    │   (PCIe 3.0) │                  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SYSTEM FABRIC (NoC + CSAC Sync)                   │   │
│  │                    ±100ps timing precision                           │   │
│  │                    10 MHz CSAC master clock                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                   │                   │                           │
│  ═══════╪═══════════════════╪═══════════════════╪═══════════════════════   │
│         │    PHASE SYNCHRONIZATION LAYER (U1–U5)│                           │
│  ═══════╪═══════════════════════════════════════╪═══════════════════════   │
│         │                                       │                           │
│         ▼                                       ▼                           │
│  ┌──────────────────┐                    ┌──────────────────┐              │
│  │ ELEMENT PHASE    │                    │  MEAN-FIELD UNIT │              │
│  │ REGISTER FILE    │───────────────────▶│  (MFU)           │              │
│  │ 128 × Q2.30      │   128 phases       │  U3: O(n) grad   │              │
│  │ per-element state │                    │  circular mean    │              │
│  └──────┬───────────┘                    └──────┬───────────┘              │
│         │                                       │                           │
│         │              ┌────────────────────────┘                           │
│         ▼              ▼                                                    │
│  ┌──────────────────────────┐     ┌──────────────────┐                     │
│  │  PHASE UPDATE ENGINE     │     │ CORRELATION       │                     │
│  │  (PUE)                   │◀───│ ENGINE (CE)       │                     │
│  │  U4: φ += α·∇            │     │ U1: windowed      │                     │
│  │  adaptive learning rate  │     │ cos(Δφ) matrix    │                     │
│  │  mod 2π wrap             │     │ W=16 depth FIFO   │                     │
│  └──────┬───────────────────┘     └──────────────────┘                     │
│         │                                                                   │
│         ▼                                                                   │
│  ┌──────────────────┐     ┌──────────────────┐                             │
│  │ COHERENCE        │     │ THRESHOLD         │                             │
│  │ ACCUMULATOR (CA) │────▶│ COMPARATOR (TC)   │                             │
│  │ U2: global metric│     │ U5: classify      │                             │
│  │ Σ cos(Δφ)/pairs  │     │ lock detection    │                             │
│  └──────────────────┘     │ hysteresis band   │                             │
│                           └──────┬───────────┘                             │
│                                  │                                          │
│  ═══════════════════════════════╪═══════════════════════════════════════   │
│         BEAMFORMING LAYER       │                                           │
│  ═══════════════════════════════╪═══════════════════════════════════════   │
│                                  │                                          │
│         ┌────────────────────────┘                                          │
│         ▼                                                                   │
│  ┌──────────────────┐     ┌──────────────────┐                             │
│  │ STEERING VECTOR  │     │  BEAM QUALITY    │                             │
│  │ GENERATOR (SVG)  │────▶│  MONITOR (BQM)   │                             │
│  │ az/el → per-elem │     │  gain, sidelobe  │                             │
│  │ 2π(x·u + y·v)    │     │  array factor    │                             │
│  └──────────────────┘     └──────────────────┘                             │
│         │                        │                                          │
│         ▼                        ▼                                          │
│  ┌──────────────────┐     ┌──────────────────┐                             │
│  │ MULTI-BEAM       │     │  PANEL HANDOVER  │                             │
│  │ CONTROLLER (MBC) │     │  CONTROLLER (PHC)│                             │
│  │ 4 concurrent     │     │  2-panel switch   │                             │
│  │ beam contexts    │     │  re-acquisition   │                             │
│  └──────────────────┘     └──────────────────┘                             │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│         SUPPORT                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   CLOCK &    │  │   POWER      │  │   CHANNEL    │  │   METRICS &  │   │
│  │   TIMING     │  │   MANAGEMENT │  │   ESTIMATOR  │  │   DEBUG      │   │
│  │   (CSAC PLL) │  │   (DVFS)     │  │   (Doppler)  │  │   (JTAG)     │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SRAM (Phase History + Beam Context)                │   │
│  │                    128 elements × 16 depth × 32b = 8 KB              │   │
│  │                    + 4 beams × 128 steering × 32b = 2 KB             │   │
│  │                    + Calibration tables = 2 KB                        │   │
│  │                    Total: 12 KB on-chip SRAM                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow — Synchronization Cycle

```
                    ┌─────────────────────────────┐
                    │  TRIGGER: sync_update_interval│
                    │  (every 10 μs)               │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  1. READ ELEMENT PHASES      │
                    │     128 × Q2.30 from EPRF    │
                    │     1 cycle (parallel read)   │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
 ┌────────────────────┐ ┌──────────────────┐ ┌──────────────────┐
 │ 2a. MEAN-FIELD (U3)│ │ 2b. CORRELATION  │ │ 2c. COHERENCE    │
 │  sin_sum = Σsin(φ) │ │  (U1) optional   │ │  (U2) pairwise   │
 │  cos_sum = Σcos(φ) │ │  update W=16     │ │  Σcos(Δφ)/pairs  │
 │  φ̄ = atan2(s,c)    │ │  history FIFO    │ │                  │
 │  2 cycles           │ │  16 cycles       │ │  2 cycles         │
 └─────────┬──────────┘ └──────────────────┘ └────────┬─────────┘
           │                                           │
           ▼                                           ▼
 ┌──────────────────────┐               ┌──────────────────────┐
 │ 3. PHASE UPDATE (U4) │               │ 4. LOCK DETECT (U5)  │
 │  ∇_i = -sin(φ_i - φ̄)│               │  coherence ≥ 0.95?   │
 │  α = adapt(history)  │               │  stable variance?    │
 │  φ_i += α · ∇_i      │               │  hysteresis ±0.02    │
 │  mod 2π              │               │  1 cycle             │
 │  128 elements × 1 cyc│               └──────────┬───────────┘
 └─────────┬────────────┘                          │
           │                                       │
           ▼                                       ▼
 ┌──────────────────────┐               ┌──────────────────────┐
 │ 5. WRITE BACK        │               │ 6. STATE MACHINE     │
 │  updated φ to EPRF   │               │  UNSYNC → ACQUIRING  │
 │  1 cycle             │               │  → LOCKED → TRACKING │
 │                      │               │  → LOST → ACQUIRING  │
 └──────────────────────┘               └──────────────────────┘
```

---

## 3. Frequency Band Support

### 3.1 Supported Bands

| Band | Designation | Carrier (GHz) | Wavelength (mm) | Bandwidth (GHz) | Phase Error at ±100ps |
|------|-------------|---------------|-----------------|------------------|-----------------------|
| FR3 Upper | `fr3_upper` | 15.0 | 19.99 | 0.4 | 0.54° |
| FR2 mmWave | `fr2_mmwave` | 39.0 | 7.69 | 2.0 | 1.40° |
| **Sub-THz Low** | **`sub_thz_low`** | **140.0** | **2.14** | **10.0** | **5.04°** |
| Sub-THz High | `sub_thz_high` | 500.0 | 0.60 | 50.0 | 18.0° |

**Primary target: Sub-THz Low (140 GHz)** — the leading 6G candidate band.

### 3.2 Phase Error Budget

At the primary 140 GHz carrier, ±100ps timing precision produces:

```
phase_error = 2π × f × Δt
            = 2π × 140×10⁹ × 100×10⁻¹²
            = 0.0880 rad
            = 5.04°
```

This is within the acceptance threshold of 5.0° max per-element phase error, requiring the CSAC + PLL chain to deliver the full ±100ps specification.

### 3.3 Element Spacing

At 140 GHz (λ = 2.14 mm), half-wavelength spacing is **1.07 mm**, enabling dense 8×8 arrays in ~9 mm × 9 mm panel footprint — compatible with phone form factors.

---

## 4. Antenna Array Architecture

### 4.1 Array Configuration

| Parameter | Value | Derivation |
|-----------|-------|------------|
| Elements per axis (X) | 8 | Phone width constraint |
| Elements per axis (Y) | 8 | Phone height constraint |
| Elements per panel | 64 | 8 × 8 UPA |
| Number of panels | 2 | Front + back coverage |
| **Total elements** | **128** | 64 × 2 |
| Topology | UPA | Uniform Planar Array |
| Element spacing | 0.5λ | Half-wavelength (1.07 mm at 140 GHz) |
| RF chains | 4 | Hybrid beamforming |
| Max simultaneous beams | 4 | One per RF chain |
| Panel footprint | ~9 × 9 mm | Per panel |

### 4.2 Multi-Panel Layout

```
┌─────────────────────────────────────────────────┐
│                   PHONE BODY                     │
│                                                  │
│  ┌──────────────┐            ┌──────────────┐   │
│  │  PANEL 0      │            │  PANEL 1      │   │
│  │  (front)      │            │  (back)       │   │
│  │               │            │               │   │
│  │  8×8 UPA      │            │  8×8 UPA      │   │
│  │  64 elements  │            │  64 elements  │   │
│  │               │            │               │   │
│  │  elem 0–63    │            │  elem 64–127  │   │
│  │               │            │               │   │
│  │  ┌─┬─┬─┬─┬─┬─┬─┬─┐       │  ┌─┬─┬─┬─┬─┬─┬─┬─┐  │
│  │  ├─┼─┼─┼─┼─┼─┼─┼─┤       │  ├─┼─┼─┼─┼─┼─┼─┼─┤  │
│  │  ├─┼─┼─┼─┼─┼─┼─┼─┤       │  ├─┼─┼─┼─┼─┼─┼─┼─┤  │
│  │  ├─┼─┼─┼─┼─┼─┼─┼─┤       │  ├─┼─┼─┼─┼─┼─┼─┼─┤  │
│  │  ├─┼─┼─┼─┼─┼─┼─┼─┤       │  ├─┼─┼─┼─┼─┼─┼─┼─┤  │
│  │  ├─┼─┼─┼─┼─┼─┼─┼─┤       │  ├─┼─┼─┼─┼─┼─┼─┼─┤  │
│  │  ├─┼─┼─┼─┼─┼─┼─┼─┤       │  ├─┼─┼─┼─┼─┼─┼─┼─┤  │
│  │  └─┴─┴─┴─┴─┴─┴─┴─┘       │  └─┴─┴─┴─┴─┴─┴─┴─┘  │
│  │  ← 1.07mm →               │                      │
│  └──────────────┘            └──────────────┘   │
│                                                  │
│            Panel handover at 180° rotation       │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 4.3 Per-Element State (Hardware)

Each of the 128 antenna elements maintains the following state in silicon:

| Field | Width | Format | Description |
|-------|-------|--------|-------------|
| `phase` | 32 bits | Q2.30 | Current phase [0, 2π) |
| `target_phase` | 32 bits | Q2.30 | Steering target phase |
| `phase_offset_cal` | 16 bits | Q1.15 | Factory calibration offset |
| `amplitude_cal` | 16 bits | UQ1.15 | Element gain calibration |
| `pos_x` | 16 bits | Q8.8 | X position in wavelengths |
| `pos_y` | 16 bits | Q8.8 | Y position in wavelengths |
| `flags` | 8 bits | — | active[0], failed[1], panel_id[3:2] |
| **Total per element** | **152 bits** | | **19 bytes** |
| **Total all elements** | **19,456 bits** | | **128 × 19 = 2,432 bytes** |

---

## 5. Functional Unit Specifications

### 5.1 Element Phase Register File (EPRF)

The EPRF stores current phase state for all 128 antenna elements with single-cycle parallel read.

```
┌─────────────────────────────────────────────────────────────────┐
│                  ELEMENT PHASE REGISTER FILE                     │
│                  128 entries × 152 bits                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────┬───────────┬───────────┬────────┬────────┬─────┬─────┐ │
│  │ ID  │  phase    │  target   │ cal_φ  │ cal_a  │ pos │flags│ │
│  │ 7b  │  Q2.30   │  Q2.30   │ Q1.15  │UQ1.15 │ 32b │ 8b  │ │
│  ├─────┼───────────┼───────────┼────────┼────────┼─────┼─────┤ │
│  │  0  │ φ₀       │ φ₀_tgt   │ Δφ₀   │  a₀   │x,y  │ AF  │ │
│  │  1  │ φ₁       │ φ₁_tgt   │ Δφ₁   │  a₁   │x,y  │ AF  │ │
│  │ ... │ ...       │ ...       │ ...    │ ...    │ ... │ ... │ │
│  │ 127 │ φ₁₂₇     │ φ₁₂₇_tgt │ Δφ₁₂₇ │ a₁₂₇  │x,y  │ AF  │ │
│  └─────┴───────────┴───────────┴────────┴────────┴─────┴─────┘ │
│                                                                  │
│  Ports: 1 × 128-wide read (all phases in 1 cycle)              │
│         1 × 128-wide write (all phases in 1 cycle)              │
│         1 × single-entry RW (register access)                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Mean-Field Unit (MFU) — U3

Computes the O(n) mean-field gradient for all elements in 2 cycles.

**Cycle 1 — Circular Mean Accumulation:**
```
sin_sum = Σᵢ sin(φᵢ)     // 128 parallel sin lookups + adder tree
cos_sum = Σᵢ cos(φᵢ)     // 128 parallel cos lookups + adder tree
φ̄ = atan2(sin_sum, cos_sum)  // CORDIC
```

**Cycle 2 — Per-Element Gradient:**
```
For each element i (128-way parallel):
    ∇ᵢ = −sin(φᵢ − φ̄)    // 128 parallel sin units
```

| Parameter | Value |
|-----------|-------|
| Latency | 2 cycles |
| Throughput | 128 gradients / 2 cycles |
| Complexity | O(n) — single pass over all elements |
| Key hardware | 128 × sin/cos LUTs (10-bit, 1024-entry) |
| | 7-level adder tree (128→1) |
| | 1 × CORDIC atan2 unit |

**Beamforming Mode Override:** When target steering phases are loaded, the MFU bypasses the circular mean and instead computes:
```
∇ᵢ = target_phaseᵢ − φᵢ     // wrapped to [−π, π]
```

### 5.3 Phase Update Engine (PUE) — U4

Applies the adaptive learning rate and updates all element phases in 1 cycle.

```
For each element i (128-way parallel):
    α = adapt(coherence_history)   // shared adaptive LR
    δᵢ = α × ∇ᵢ                   // fixed-point multiply
    φᵢ(t+1) = (φᵢ(t) + δᵢ) mod 2π // add + wrap
```

**Adaptive Learning Rate Logic:**

| Condition | Learning Rate | Rationale |
|-----------|---------------|-----------|
| Oscillating coherence (>50% sign changes) | 0.3 × base (0.03) | Dampen oscillations |
| High coherence (>0.9) | 0.5 × base (0.05) | Fine-tuning mode |
| Low coherence (<0.5) | 1.5 × base (0.15) | Fast convergence |
| Normal | 1.0 × base (0.10) | Default |

The adaptation uses a 10-sample coherence history register and a sign-change counter.

| Parameter | Value |
|-----------|-------|
| Base learning rate | 0.10 (Q0.16 fixed-point) |
| Latency | 1 cycle |
| Key hardware | 128 × 16-bit multipliers |
| | 128 × 32-bit adders with modular wrap |
| | 1 × adaptation FSM (10-entry shift register) |

### 5.4 Correlation Engine (CE) — U1

Computes the windowed pairwise correlation matrix for diagnostics and U5 evaluation. Runs in background (not on critical sync path).

```
C[i,j] = (1/W) × Σₖ cos(φᵢ(t−k) − φⱼ(t−k))     for k = 0..W−1
```

| Parameter | Value |
|-----------|-------|
| Window depth (W) | 16 samples |
| Storage | 128 × 16 × 32b = 8 KB phase history FIFO |
| Matrix size | 128 × 128 = 16,384 entries (symmetric, store upper triangle) |
| Computation | Background — not on sync critical path |
| Update rate | Every 16 sync cycles (1.6 ms at 10 μs interval) |
| Key hardware | 16-deep × 128-wide shift register file |
| | Pipelined cos(Δφ) + accumulate unit |

### 5.5 Coherence Accumulator (CA) — U2

Computes global coherence in 2 cycles using the current phase snapshot.

```
C_total = Σᵢ<ⱼ cos(φᵢ − φⱼ)
C_normalized = C_total / (n×(n−1)/2)
```

For 128 elements: n×(n−1)/2 = 8,128 pairs.

**Optimization:** The CA uses the mean-field approximation for the fast path:

```
C_approx = (sin_sum² + cos_sum²) / n²    // from MFU accumulators
```

This reuses MFU cycle-1 outputs, requiring zero additional cycles on the critical path. The exact pairwise computation runs in background for validation.

| Parameter | Value |
|-----------|-------|
| Fast-path latency | 0 additional cycles (reuses MFU) |
| Fast-path formula | (sin_sum² + cos_sum²) / n² |
| Background exact | 8,128 pair evaluations, pipelined |
| Output range | [0, 1] as UQ0.32 |

### 5.6 Threshold Comparator (TC) — U5

Lock detection state machine with hysteresis.

```
                      coherence ≥ 0.95
                      AND stable(var < 0.001)
    ┌──────────┐    ─────────────────────▶   ┌──────────┐
    │ACQUIRING │                              │ LOCKED   │
    └──────────┘    ◀─────────────────────   └──────────┘
                      coherence < 0.93                │
                      (threshold − 3×hysteresis)      │
                                                       │ coherence < 0.93
    ┌──────────┐    ◀──────────────────────────────────┘
    │  LOST    │                              ┌──────────┐
    └──────────┘    ◀─────────────────────   │ TRACKING │
                      coherence < 0.89        └──────────┘
                                                       ▲
                      coherence drops below 0.93       │
    LOCKED ──────────────────────────────────────────▶─┘
                      but stays above 0.89
```

**U5 Correlation Classification (per-element pair):**

| Correlation C[i,j] | Classification | Hardware Action |
|--------------------|----------------|-----------------|
| > 0.7 | `STRONG_ALIGNMENT` | Normal operation |
| 0.3 – 0.7 | `MODERATE_CORRELATION` | Monitor, no action |
| −0.3 – 0.3 | `WEAK_CORRELATION` | Flag for diagnostics |
| < −0.3 | `ANTI_CORRELATION` | Element failure candidate |

| Parameter | Value |
|-----------|-------|
| Coherence threshold | 0.95 (UQ0.32) |
| Hysteresis band | 0.02 |
| Stability window | 5 samples |
| Stability variance threshold | 0.001 |
| Latency | 1 cycle |
| States | UNSYNCHRONIZED, ACQUIRING, LOCKED, TRACKING, LOST |

### 5.7 Steering Vector Generator (SVG)

Computes per-element target phases for a given beam direction.

```
For each element i with position (xᵢ, yᵢ) in wavelengths:
    u = sin(az) × cos(el)       // direction cosines
    v = sin(el)
    target_φᵢ = (2π × (xᵢ·u + yᵢ·v) + cal_offsetᵢ) mod 2π
```

| Parameter | Value |
|-----------|-------|
| Inputs | azimuth (Q9.7), elevation (Q9.7) |
| Outputs | 128 × target phases (Q2.30) |
| Latency | 4 cycles (sin/cos + multiply + accumulate + cal) |
| Key hardware | 2 × CORDIC sin/cos units |
| | 128 × multiply-accumulate units (shared with PUE) |

### 5.8 Multi-Beam Controller (MBC)

Manages 4 concurrent beam contexts with independent steering vectors.

```
┌─────────────────────────────────────────────────────────┐
│                  MULTI-BEAM CONTROLLER                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │  BEAM 0    │  │  BEAM 1    │  │  BEAM 2    │  │  BEAM 3    │  │
│  │  az/el     │  │  az/el     │  │  az/el     │  │  az/el     │  │
│  │  steering  │  │  steering  │  │  steering  │  │  steering  │  │
│  │  128×Q2.30 │  │  128×Q2.30 │  │  128×Q2.30 │  │  128×Q2.30 │  │
│  │  user_id   │  │  user_id   │  │  user_id   │  │  user_id   │  │
│  │  active    │  │  active    │  │  active    │  │  active    │  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
│                                                          │
│  Beam context storage: 4 × 128 × 32b = 2 KB            │
│  Round-robin or priority scheduling                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

| Parameter | Value |
|-----------|-------|
| Max beams | 4 (one per RF chain) |
| Context size | 512 bytes per beam |
| Scheduling | Round-robin with priority override |
| Beam steer latency | 4 cycles (SVG) + sync convergence |

### 5.9 Panel Handover Controller (PHC)

Manages antenna panel switching during phone rotation.

| Parameter | Value |
|-----------|-------|
| Panels | 2 (panel 0: elements 0–63, panel 1: elements 64–127) |
| Handover trigger | Best-panel determination from rotation angle |
| Panel 0 active | 0° ≤ wrapped_angle < 180° |
| Panel 1 active | 180° ≤ wrapped_angle < 360° |
| Re-acquisition | Automatic sync on new panel after switch |
| Handover latency | <500 μs (full re-acquisition budget) |

### 5.10 Beam Quality Monitor (BQM)

Computes real-time beam pattern metrics from phase errors.

**Array Gain:**
```
ideal_gain = 10 × log₁₀(N)                    // N = active elements
AF = |Σᵢ exp(j×(φᵢ − targetᵢ))| / N          // array factor magnitude
gain_loss = 20 × log₁₀(AF)
actual_gain = ideal_gain + gain_loss
```

**Sidelobe Estimation:**
```
ideal_sidelobe = −13.3 dB                      // uniform array first sidelobe
rms_error = √(Σᵢ (φᵢ − targetᵢ)² / N)
sidelobe_floor = 10 × log₁₀(rms_error²)
actual_sidelobe = max(ideal_sidelobe, sidelobe_floor)
```

**Half-Power Beamwidth:**
```
HPBW = 51.0° / (√N × d/λ)
     = 51.0° / (√64 × 0.5)
     = 12.75°  (per panel at 140 GHz)
```

---

## 6. Register Map

### 6.1 Address Space Overview

| Base Address | Unit | Size | Description |
|-------------|------|------|-------------|
| 0x0000 | GCR | 256 B | Global Control Registers |
| 0x0100 | MFU | 256 B | Mean-Field Unit Control |
| 0x0200 | PUE | 256 B | Phase Update Engine |
| 0x0300 | CE | 256 B | Correlation Engine |
| 0x0400 | CA | 256 B | Coherence Accumulator |
| 0x0500 | TC | 256 B | Threshold Comparator |
| 0x0600 | SVG | 256 B | Steering Vector Generator |
| 0x0700 | MBC | 256 B | Multi-Beam Controller |
| 0x0800 | PHC | 256 B | Panel Handover Controller |
| 0x0900 | BQM | 256 B | Beam Quality Monitor |
| 0x0A00 | CHE | 256 B | Channel Estimator |
| 0x0B00 | PWR | 256 B | Power Management |
| 0x0C00 | DBG | 256 B | Debug & Metrics |
| 0x1000 | EPRF | 4 KB | Element Phase Register File |
| 0x2000 | PHIST | 8 KB | Phase History FIFO (U1) |
| 0x4000 | BCTX | 2 KB | Beam Context Storage |
| 0x5000 | CAL | 2 KB | Calibration Tables |

### 6.2 Global Control Registers (GCR)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0000 | GCR_CTRL | 32 | RW | Global control |
| 0x0004 | GCR_STATUS | 32 | RO | Global status |
| 0x0008 | GCR_IRQ_EN | 32 | RW | Interrupt enable |
| 0x000C | GCR_IRQ_STAT | 32 | RW1C | Interrupt status |
| 0x0010 | GCR_SYNC_CNT | 64 | RO | Total sync updates |
| 0x0018 | GCR_FREQ_BAND | 32 | RW | Frequency band select |
| 0x001C | GCR_CARRIER_GHZ | 32 | RW | Carrier frequency (UQ16.16 GHz) |
| 0x0020 | GCR_WAVELENGTH | 32 | RO | Wavelength (UQ16.16 mm) |
| 0x0024 | GCR_BANDWIDTH | 32 | RW | Channel bandwidth (UQ16.16 GHz) |
| 0x0028 | GCR_CHIP_ID | 32 | RO | Chip revision / ID |
| 0x002C | GCR_TIMESTAMP | 64 | RO | Current time (μs, UQ48.16) |

**GCR_CTRL Bit Fields:**
```
[0]     ENABLE          - Global enable (sync engine active)
[1]     SOFT_RESET      - Soft reset (auto-clear)
[2]     SYNC_START      - Trigger single sync cycle
[3]     CONTINUOUS      - Continuous sync mode enable
[5:4]   SYNC_MODE       - 00=coherence, 01=beamforming, 10=tracking
[7:6]   FREQ_BAND       - 00=FR3, 01=FR2, 10=sub-THz-low, 11=sub-THz-high
[15:8]  MAX_SYNC_ITER   - Max sync iterations (1–255, default 50)
[23:16] NUM_PANELS      - Active panels (1–4, default 2)
[31:24] RESERVED
```

**GCR_STATUS Bit Fields:**
```
[2:0]   SYNC_STATE      - 000=unsync, 001=acquiring, 010=locked,
                           011=tracking, 100=lost
[3]     SYNC_BUSY       - Sync cycle in progress
[7:4]   ACTIVE_BEAMS    - Number of active beams
[15:8]  ACTIVE_ELEMENTS - Number of non-failed elements
[23:16] FAILED_ELEMENTS - Number of failed elements
[24]    THERMAL_WARN    - Junction temp > throttle threshold
[25]    THERMAL_CRIT    - Junction temp > maximum
[31:26] RESERVED
```

**GCR_IRQ_EN / GCR_IRQ_STAT Bit Fields:**
```
[0]     SYNC_LOCKED     - Phase lock achieved
[1]     SYNC_LOST       - Phase lock lost
[2]     HANDOVER_DONE   - Panel handover complete
[3]     BEAM_STEER_DONE - Beam steering complete
[4]     ELEMENT_FAIL    - Element failure detected
[5]     THERMAL_WARN    - Temperature warning
[6]     CORR_READY      - Correlation matrix updated
[31:7]  RESERVED
```

### 6.3 Mean-Field Unit Registers (MFU)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0100 | MFU_CTRL | 32 | RW | MFU control |
| 0x0104 | MFU_SIN_SUM | 32 | RO | Σ sin(φᵢ) (Q2.30) |
| 0x0108 | MFU_COS_SUM | 32 | RO | Σ cos(φᵢ) (Q2.30) |
| 0x010C | MFU_PHI_MEAN | 32 | RO | atan2(sin_sum, cos_sum) (Q2.30) |
| 0x0110 | MFU_GRAD_BASE | 32 | RO | Base address for 128 gradients |

**MFU_CTRL Bit Fields:**
```
[0]     ENABLE          - Enable mean-field computation
[1]     USE_TARGET      - Use target phases (beamforming mode)
[3:2]   BEAM_SELECT     - Which beam context for target phases (0–3)
[31:4]  RESERVED
```

### 6.4 Phase Update Engine Registers (PUE)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0200 | PUE_CTRL | 32 | RW | PUE control |
| 0x0204 | PUE_LEARNING_RATE | 32 | RW | Base α (UQ0.16, default 0x199A = 0.1) |
| 0x0208 | PUE_CURRENT_LR | 32 | RO | Current adapted α |
| 0x020C | PUE_MEAN_UPDATE | 32 | RO | Mean |δφ| from last cycle |
| 0x0210 | PUE_LR_ADAPT_WIN | 32 | RW | Adaptation window (default 10) |
| 0x0214 | PUE_LR_FAST_MULT | 16 | RW | Fast-convergence multiplier (UQ0.8, default 0x26 = 1.5) |
| 0x0216 | PUE_LR_FINE_MULT | 16 | RW | Fine-tuning multiplier (UQ0.8, default 0x80 = 0.5) |
| 0x0218 | PUE_LR_DAMP_MULT | 16 | RW | Damping multiplier (UQ0.8, default 0x4D = 0.3) |
| 0x021A | PUE_LR_TRACK_MULT | 16 | RW | Tracking multiplier (UQ0.8, default 0xB3 = 0.7) |

### 6.5 Correlation Engine Registers (CE)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0300 | CE_CTRL | 32 | RW | CE control |
| 0x0304 | CE_WINDOW | 32 | RW | Correlation window W (default 16) |
| 0x0308 | CE_STATUS | 32 | RO | Computation status |
| 0x030C | CE_UPDATE_PERIOD | 32 | RW | Background update period (sync cycles) |
| 0x0310 | CE_PAIR_ADDR | 32 | RW | Read address: element i (15:8), j (7:0) |
| 0x0314 | CE_PAIR_VALUE | 32 | RO | C[i,j] for addressed pair (Q1.31) |

### 6.6 Coherence Accumulator Registers (CA)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0400 | CA_CTRL | 32 | RW | CA control |
| 0x0404 | CA_GLOBAL_COH | 32 | RO | Global coherence C (UQ0.32) |
| 0x0408 | CA_PANEL0_COH | 32 | RO | Panel 0 coherence (UQ0.32) |
| 0x040C | CA_PANEL1_COH | 32 | RO | Panel 1 coherence (UQ0.32) |
| 0x0410 | CA_BEAM0_COH | 32 | RO | Beam 0 coherence vs steering (UQ0.32) |
| 0x0414 | CA_BEAM1_COH | 32 | RO | Beam 1 coherence vs steering (UQ0.32) |
| 0x0418 | CA_BEAM2_COH | 32 | RO | Beam 2 coherence vs steering (UQ0.32) |
| 0x041C | CA_BEAM3_COH | 32 | RO | Beam 3 coherence vs steering (UQ0.32) |

### 6.7 Threshold Comparator Registers (TC)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0500 | TC_CTRL | 32 | RW | TC control |
| 0x0504 | TC_COH_THRESH | 32 | RW | Lock threshold (UQ0.32, default 0.95) |
| 0x0508 | TC_HYSTERESIS | 32 | RW | Hysteresis band (UQ0.32, default 0.02) |
| 0x050C | TC_STAB_WINDOW | 32 | RW | Stability check window (default 5) |
| 0x0510 | TC_STAB_VAR_MAX | 32 | RW | Max variance for stable (UQ0.32, default 0.001) |
| 0x0514 | TC_SYNC_STATE | 32 | RO | Current sync state (see GCR_STATUS[2:0]) |
| 0x0518 | TC_COH_HISTORY | 32×5 | RO | Last 5 coherence values |

### 6.8 Steering Vector Generator Registers (SVG)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0600 | SVG_CTRL | 32 | RW | SVG control |
| 0x0604 | SVG_AZIMUTH | 32 | RW | Target azimuth (Q9.7 degrees) |
| 0x0608 | SVG_ELEVATION | 32 | RW | Target elevation (Q9.7 degrees) |
| 0x060C | SVG_BEAM_ID | 32 | RW | Target beam context (0–3) |
| 0x0610 | SVG_STATUS | 32 | RO | Computation complete flag |

### 6.9 Multi-Beam Controller Registers (MBC)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0700 | MBC_CTRL | 32 | RW | MBC control |
| 0x0704 | MBC_ACTIVE_MASK | 32 | RW | Beam active bits [3:0] |
| 0x0708 | MBC_SCHED_MODE | 32 | RW | 0=round-robin, 1=priority |
| 0x0710 | MBC_BEAM0_AZ | 32 | RO | Beam 0 current azimuth |
| 0x0714 | MBC_BEAM0_EL | 32 | RO | Beam 0 current elevation |
| 0x0718 | MBC_BEAM0_GAIN | 32 | RO | Beam 0 gain (Q8.8 dB) |
| 0x071C | MBC_BEAM0_SL | 32 | RO | Beam 0 sidelobe (Q8.8 dB) |
| 0x0720 | MBC_BEAM0_UID | 32 | RW | Beam 0 user ID |
| 0x0730–0x077C | MBC_BEAM1–3 | | | Beams 1–3 (same layout, +0x20 stride) |

### 6.10 Panel Handover Controller Registers (PHC)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0800 | PHC_CTRL | 32 | RW | PHC control |
| 0x0804 | PHC_ACTIVE_PANEL | 32 | RO | Currently active panel (0 or 1) |
| 0x0808 | PHC_ROTATION_DEG | 32 | RW | Current rotation angle (Q16.16) |
| 0x080C | PHC_HANDOVER_CNT | 32 | RO | Total handovers since reset |
| 0x0810 | PHC_REACQ_ITERS | 32 | RO | Iterations for last re-acquisition |
| 0x0814 | PHC_REACQ_COH | 32 | RO | Coherence after last re-acquisition |

### 6.11 Channel Estimator Registers (CHE)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0A00 | CHE_CTRL | 32 | RW | Channel estimator control |
| 0x0A04 | CHE_DOPPLER_HZ | 32 | RO | Estimated Doppler shift (UQ16.16) |
| 0x0A08 | CHE_PATH_LOSS | 32 | RO | Path loss estimate (Q8.8 dB) |
| 0x0A0C | CHE_SNR | 32 | RO | SNR estimate (Q8.8 dB) |
| 0x0A10 | CHE_INTERFERENCE | 32 | RO | Interference power (Q8.8 dBm) |
| 0x0A14 | CHE_FADING_EN | 32 | RW | Enable fading compensation |
| 0x0A18 | CHE_MOBILITY_EN | 32 | RW | Enable mobility tracking |

### 6.12 Power Management Registers (PWR)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0B00 | PWR_CTRL | 32 | RW | Power control |
| 0x0B04 | PWR_STATE | 32 | RO | Current power state |
| 0x0B08 | PWR_CURRENT_W | 32 | RO | Instantaneous power (UQ8.8 W) |
| 0x0B0C | PWR_JUNC_TEMP | 32 | RO | Junction temperature (Q8.8 °C) |
| 0x0B10 | PWR_THROTTLE_TEMP | 32 | RW | Throttle threshold (default 90°C) |
| 0x0B14 | PWR_MAX_TEMP | 32 | RW | Max junction temp (default 105°C) |
| 0x0B18 | PWR_IDLE_POWER | 32 | RW | Idle power target (UQ8.8, default 0.5W) |
| 0x0B1C | PWR_SYNC_POWER | 32 | RW | Sync mode power budget (UQ8.8, default 3W) |
| 0x0B20 | PWR_BEAM_POWER | 32 | RW | Beamforming power budget (UQ8.8, default 8W) |

---

## 7. Timing Specifications

### 7.1 Clock Domains

| Clock | Frequency | Source | Purpose |
|-------|-----------|--------|---------|
| `clk_core` | 1 GHz | On-chip PLL | Sync engine, register access |
| `clk_csac` | 10 MHz | Microchip SA.45s CSAC | Master phase reference |
| `clk_rf` | Variable | Per-band PLL | RF front-end timing |
| `clk_slow` | 100 MHz | Divided from core | Power management, debug |

### 7.2 Critical Timing Parameters

| Parameter | Value | Register | Derivation |
|-----------|-------|----------|------------|
| Sync update interval | 10 μs | — (timer) | `TimingConfig.sync_update_interval_us` |
| Timing precision | ±100 ps | — (analog) | CSAC + PLL chain |
| Max drift rate | 1 ps/ms | — (spec) | `TimingConfig.max_drift_rate_ps_per_ms` |
| Sync cycle latency | 4 core cycles (4 ns) | — | MFU(2) + PUE(1) + TC(1) |
| Max sync iterations | 50 | GCR_CTRL[15:8] | `TimingConfig.max_sync_iterations` |
| Max convergence time | 500 μs | — (derived) | 50 iter × 10 μs |
| Beam steer latency | 8 core cycles (8 ns) | — | SVG(4) + sync path(4) |

### 7.3 Sync Cycle Timing

```
Time (core cycles)
  │
  0 ──── EPRF parallel read (128 phases)
  │
  1 ──── MFU cycle 1: sin/cos accumulate + atan2
  │
  2 ──── MFU cycle 2: per-element gradient (128-parallel)
  │      CA: coherence from MFU accumulators (piggyback)
  │
  3 ──── PUE: phase update (128-parallel multiply-add-wrap)
  │
  4 ──── TC: lock detection + EPRF write-back
  │
  Total: 4 cycles @ 1 GHz = 4 ns per sync iteration
  Budget: 10 μs interval → can run 2,500 iterations per interval
  Actual: max 50 iterations → 200 ns, well within budget
```

---

## 8. Power Architecture

### 8.1 Power Envelope (UCP-Edge Mobile)

| Mode | Power (W) | Register | Duration |
|------|-----------|----------|----------|
| **Idle / Sleep** | 0.5 | PWR_IDLE_POWER | Indefinite |
| **Sync Only** | 3.0 | PWR_SYNC_POWER | During acquisition |
| **Active Beamforming** | 8.0 | PWR_BEAM_POWER | During data transfer |
| **Peak (all units)** | ≤15.0 | — | Transient |
| **Absolute Maximum** | 20.0 | — | Acceptance limit |

### 8.2 Power Breakdown by Unit

| Unit | Estimated Power (mW) | % of Active | Notes |
|------|---------------------|-------------|-------|
| EPRF (SRAM) | 200 | 2.5% | 12 KB, low-leakage |
| MFU (128 sin/cos + adder tree) | 1,500 | 18.8% | Dominant compute |
| PUE (128 multipliers) | 1,200 | 15.0% | Fixed-point multiply |
| CE (background correlation) | 800 | 10.0% | Duty-cycled |
| CA (coherence) | 100 | 1.3% | Reuses MFU outputs |
| TC (comparator + FSM) | 50 | 0.6% | Minimal logic |
| SVG (CORDIC + MAC) | 500 | 6.3% | 4-cycle burst |
| MBC (beam context) | 200 | 2.5% | SRAM + mux |
| PHC (handover FSM) | 50 | 0.6% | Event-driven |
| BQM (beam quality) | 300 | 3.8% | Background |
| CHE (channel estimation) | 400 | 5.0% | Continuous |
| Clock tree + PLL | 800 | 10.0% | CSAC interface |
| I/O + NoC | 600 | 7.5% | Interfaces |
| Leakage (4nm) | 1,300 | 16.3% | Process-dependent |
| **Total Active** | **8,000** | **100%** | **Target met** |

### 8.3 Thermal Management

| Parameter | Value | Register |
|-----------|-------|----------|
| Max junction temperature | 105°C | PWR_MAX_TEMP |
| Thermal throttle threshold | 90°C | PWR_THROTTLE_TEMP |
| Throttle action | Reduce sync rate by 2× | Automatic |
| Package | FOWLP (Fan-Out Wafer-Level Package) | — |
| Thermal resistance (θ_JA) | ~25°C/W | — |

At 8W active power: T_junction = T_ambient + 8 × 25 = T_ambient + 200°C — requires heatspreader. With phone thermal solution (θ_JA ~12°C/W): T_junction = 25 + 96 = 121°C. DVFS and duty-cycling keep sustained power below 5W for phone thermal budget.

---

## 9. Acceptance Validation Gates

These gates map directly from `AcceptanceThresholds` in `simulator/use_6g/core/config.py` and define silicon tape-out acceptance criteria.

### 9.1 Gate Definitions

| Gate | Metric | Threshold | Simulator Source | Pass Criteria |
|------|--------|-----------|------------------|---------------|
| **G1: Sync Coherence** | Mean global coherence | ≥ 0.95 | `min_global_coherence` | `metrics.sync.mean_coherence ≥ 0.95` |
| **G2: Phase Error** | Max per-element error | ≤ 5.0° | `max_phase_error_deg` | `metrics.sync.max_phase_error_deg ≤ 5.0` |
| **G3: Sync Time** | Mean time to lock | ≤ 500 μs | `max_sync_time_us` | `metrics.sync.mean_time_to_lock_us ≤ 500` |
| **G4: Beam Gain** | Mean array gain | ≥ 15.0 dB | `min_beam_gain_db` | `metrics.beamforming.mean_gain_db ≥ 15.0` |
| **G5: Sidelobe Level** | Max sidelobe | ≤ −13.0 dB | `max_sidelobe_level_db` | `metrics.beamforming.mean_sidelobe_db ≤ −13.0` |
| **G6: Null Depth** | Interference null | ≤ −25.0 dB | `min_null_depth_db` | Measured in multi-beam scenario |
| **G7: Sync Throughput** | Sync updates/sec | ≥ 100K | `min_sync_updates_per_sec` | `metrics.throughput.sync_ops_per_sec ≥ 100K` |
| **G8: Beam Throughput** | Beam steers/sec | ≥ 10K | `min_beam_steers_per_sec` | `metrics.throughput.beam_ops_per_sec ≥ 10K` |
| **G9: Sync Power** | Power during sync | ≤ 5 W | `max_sync_power_w` | `metrics.power.peak_power_w ≤ 5` (sync mode) |
| **G10: Total Power** | Total chip power | ≤ 20 W | `max_total_power_w` | `metrics.power.peak_power_w ≤ 20` |
| **G11: Die Area** | Silicon area | ≤ 25 mm² | `max_area_mm2` | Post-synthesis measurement |
| **G12: Process** | Fabrication node | 4 nm | `target_process_nm` | Foundry target |

### 9.2 Validation Scenarios

Each gate is validated across four scenarios that exercise different chip operating modes:

| Scenario | Simulator Method | Primary Gates | Description |
|----------|-----------------|---------------|-------------|
| **1. Initial Acquisition** | `run_acquisition_scenario()` | G1, G2, G3 | Cold-start phase lock from random initial phases. 10 independent trials with different seeds. |
| **2. Beam Tracking** | `run_beam_tracking_scenario()` | G1, G2, G4, G5 | Maintain lock during mobility (5 km/h pedestrian). 100 ms duration with Doppler and fading. |
| **3. Multi-Beam MIMO** | `run_multi_beam_scenario()` | G4, G5, G6, G8 | 4 concurrent users at (−45°, −15°, +15°, +45°). Simultaneous beam quality validation. |
| **4. Panel Handover** | `run_panel_handover_scenario()` | G1, G3 | Phone rotation at 90°/sec for 2 seconds. Panel switching with re-acquisition. |

### 9.3 Theoretical Performance Bounds

| Metric | Theoretical Limit | Spec Target | Margin |
|--------|-------------------|-------------|--------|
| Array gain (64 elem) | 10·log₁₀(64) = 18.06 dB | 15.0 dB | 3.06 dB |
| Array gain (128 elem) | 10·log₁₀(128) = 21.07 dB | 15.0 dB | 6.07 dB |
| Sidelobe (uniform, no errors) | −13.3 dB | −13.0 dB | 0.3 dB |
| Phase lock (128 elem, 50 iter) | ~10–20 iterations typical | 50 max | 2.5–5× |
| HPBW (64 elem, 0.5λ) | 12.75° | — | Informational |

---

## 10. Simulator-to-Silicon Parameter Mapping

Complete mapping from simulator Python code to hardware registers and constants.

### 10.1 FrequencyConfig → GCR

| Simulator Parameter | Simulator Default | Register | Hardware Format |
|---------------------|-------------------|----------|-----------------|
| `FrequencyBand` | `SUB_THZ_LOW` | GCR_CTRL[7:6] | 2-bit enum (10) |
| `carrier_freq_ghz` | 140.0 | GCR_CARRIER_GHZ | UQ16.16 |
| `wavelength_mm` | 2.14 | GCR_WAVELENGTH | UQ16.16 (computed) |
| `bandwidth_ghz` | 10.0 | GCR_BANDWIDTH | UQ16.16 |
| `max_phase_error_rad` | 0.088 (computed) | — | Derived from CSAC spec |

### 10.2 AntennaConfig → EPRF + MBC

| Simulator Parameter | Simulator Default | Register / Hardware | Notes |
|---------------------|-------------------|---------------------|-------|
| `num_elements_x` | 8 | EPRF layout | Fixed at synthesis |
| `num_elements_y` | 8 | EPRF layout | Fixed at synthesis |
| `num_panels` | 2 | GCR_CTRL[23:16] | Runtime configurable |
| `element_spacing_lambda` | 0.5 | EPRF pos_x/pos_y | Pre-loaded calibration |
| `num_rf_chains` | 4 | MBC (beam contexts) | Fixed at synthesis |
| `max_beams` | 4 | MBC_ACTIVE_MASK | Up to 4 |
| `total_elements` | 128 | EPRF depth | Fixed at synthesis |

### 10.3 TimingConfig → PUE + TC + CE

| Simulator Parameter | Simulator Default | Register | Hardware Format |
|---------------------|-------------------|----------|-----------------|
| `timing_precision_ps` | 100.0 | — (analog) | CSAC + PLL spec |
| `sync_update_interval_us` | 10.0 | Timer (hardware) | Fixed interval |
| `max_drift_rate_ps_per_ms` | 1.0 | — (analog) | CSAC spec |
| `sync_learning_rate` | 0.1 | PUE_LEARNING_RATE | UQ0.16 = 0x199A |
| `correlation_window` | 16 | CE_WINDOW | 32-bit unsigned |
| `mean_field_enabled` | True | MFU_CTRL[0] | Enable bit |
| `coherence_threshold` | 0.95 | TC_COH_THRESH | UQ0.32 |
| `max_sync_iterations` | 50 | GCR_CTRL[15:8] | 8-bit unsigned |
| `phase_lock_hysteresis` | 0.02 | TC_HYSTERESIS | UQ0.32 |

### 10.4 PowerConfig → PWR

| Simulator Parameter | Simulator Default | Register | Hardware Format |
|---------------------|-------------------|----------|-----------------|
| `max_power_w` | 15.0 | — (design target) | — |
| `idle_power_w` | 0.5 | PWR_IDLE_POWER | UQ8.8 |
| `sync_power_w` | 3.0 | PWR_SYNC_POWER | UQ8.8 |
| `beamform_power_w` | 8.0 | PWR_BEAM_POWER | UQ8.8 |
| `max_junction_temp_c` | 105.0 | PWR_MAX_TEMP | Q8.8 |
| `thermal_throttle_temp_c` | 90.0 | PWR_THROTTLE_TEMP | Q8.8 |

### 10.5 AcceptanceThresholds → Validation Gates

| Simulator Parameter | Value | Gate |
|---------------------|-------|------|
| `min_global_coherence` | 0.95 | G1 |
| `max_phase_error_deg` | 5.0 | G2 |
| `max_sync_time_us` | 500.0 | G3 |
| `min_beam_gain_db` | 15.0 | G4 |
| `max_sidelobe_level_db` | −13.0 | G5 |
| `min_null_depth_db` | −25.0 | G6 |
| `min_sync_updates_per_sec` | 100K | G7 |
| `min_beam_steers_per_sec` | 10K | G8 |
| `max_sync_power_w` | 5.0 | G9 |
| `max_total_power_w` | 20.0 | G10 |
| `max_area_mm2` | 25.0 | G11 |
| `target_process_nm` | 4 | G12 |

---

## 11. Physical Implementation

### 11.1 Process Technology

| Parameter | Specification |
|-----------|---------------|
| Process node | 4 nm (TSMC N4 or Samsung 4LPP) |
| Standard cells | Multi-Vt (SVT, LVT, ULVT) |
| SRAM | High-density 6T for PHIST, beam context |
| | Low-leakage 8T for EPRF (always-on) |
| Metal layers | 12–14 |
| Supply voltage | 0.75V nominal, 0.6V–0.85V DVFS range |

### 11.2 Area Estimate

| Block | Estimated Area (mm²) | % of Die |
|-------|----------------------|----------|
| EPRF (2.4 KB, 8T SRAM) | 0.02 | 0.1% |
| Phase History (8 KB, 6T SRAM) | 0.05 | 0.2% |
| Beam Context (2 KB, 6T SRAM) | 0.01 | <0.1% |
| Calibration (2 KB, 6T SRAM) | 0.01 | <0.1% |
| MFU (128 sin/cos LUT + adder tree) | 2.0 | 8.0% |
| PUE (128 multipliers + adders) | 1.5 | 6.0% |
| CE (pipelined correlator) | 1.0 | 4.0% |
| SVG (CORDIC + MAC) | 0.5 | 2.0% |
| BQM + CA + TC | 0.3 | 1.2% |
| MBC + PHC | 0.2 | 0.8% |
| CHE (channel estimator) | 0.5 | 2.0% |
| Clock tree + PLL + CSAC I/F | 1.5 | 6.0% |
| I/O pads + ESD | 3.0 | 12.0% |
| NoC fabric | 0.5 | 2.0% |
| Power management (DVFS, LDO) | 0.8 | 3.2% |
| Debug (JTAG, trace) | 0.3 | 1.2% |
| **Subtotal (logic + memory)** | **12.2** | **48.7%** |
| Routing overhead (~50%) | 6.1 | 24.4% |
| Guard bands + fill | 1.7 | 6.8% |
| **Total Die Area** | **~20 mm²** | **Within 25 mm² budget** |

### 11.3 Package

| Parameter | Specification |
|-----------|---------------|
| Package type | FOWLP (Fan-Out Wafer-Level Package) |
| Package size | 8 mm × 8 mm |
| Pin count | ~200 (BGA) |
| Thermal resistance (θ_JC) | ~3°C/W |

---

## 12. Integration with UCP-Edge

The USE-6G chip operates as a companion accelerator to the UCP-Edge cognitive processor, connected via the system fabric.

```
┌──────────────────────────────────────────────────────────┐
│                     UCP-Edge MODULE                       │
│                     10–20W total                          │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────┐        ┌──────────────────┐        │
│  │    UCP-Edge      │  NoC   │    USE-6G        │        │
│  │    Cognitive      │◀─────▶│    MIMO Sync      │        │
│  │    Processor      │  ±100ps│    Accelerator    │        │
│  │                   │        │                   │        │
│  │  PAU (Phase Attn) │        │  MFU (Mean-Field) │        │
│  │  TCU (Temporal)   │        │  PUE (Phase Upd)  │        │
│  │  OPU (Ontology)   │        │  SVG (Steering)   │        │
│  │  SDU (State Δ)    │        │  MBC (Multi-Beam)  │        │
│  │  KEE (Kosha)      │        │  CE (Correlation)  │        │
│  │                   │        │                   │        │
│  │  LPDDR5 16GB      │        │  12 KB SRAM       │        │
│  │  ~12W             │        │  ~8W              │        │
│  └──────────────────┘        └──────────────────┘        │
│                                                           │
│  Shared: CSAC 10 MHz master clock, ±100ps precision      │
│  Interface: PCIe 3.0 x4 or proprietary coherence bus     │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

The UCP's Phase Attention Unit (PAU) and the USE-6G's Mean-Field Unit (MFU) share the same USE patent formulas — one applied to cognitive processing (token phase alignment), the other to RF antenna synchronization (element phase alignment). The CSAC master clock provides the common ±100ps timing reference across both chips.

---

## 13. Development Roadmap

| Phase | Duration | Deliverable | Key Risk |
|-------|----------|-------------|----------|
| **Phase 1: RTL Design** | 6 months | Synthesizable Verilog for all units | MFU timing closure |
| **Phase 2: FPGA Prototype** | 3 months | Xilinx RFSoC validation | RF interface fidelity |
| **Phase 3: Synthesis** | 3 months | 4nm gate-level netlist, area/power | Area budget (25 mm²) |
| **Phase 4: Physical Design** | 6 months | GDSII tape-out | Timing closure at 1 GHz |
| **Phase 5: Silicon Validation** | 3 months | First silicon characterization | Yield, CSAC integration |
| **Total** | **~21 months** | **Production USE-6G** | |

---

## 14. Summary

The USE-6G chip translates the USE patent formulas (U1–U5) from algorithmic simulation into dedicated 4nm silicon, delivering:

- **O(n) phase synchronization** for 128 antenna elements via hardware mean-field computation (U3)
- **±100ps timing precision** through CSAC-referenced PLL chains
- **<500 μs convergence** from cold start to phase lock
- **4 simultaneous beams** for multi-user MIMO
- **2-panel handover** for phone rotation coverage
- **≤20W total power** in UCP-Edge mobile form factor
- **≤25 mm² die area** at 4nm process

Every simulator parameter has a corresponding hardware register or synthesis constant, ensuring the validation framework directly verifies silicon behavior against acceptance gates G1–G12.

---

## Supporting Materials

| Document | Description |
|----------|-------------|
| `simulator/use_6g/core/config.py` | Configuration dataclasses and acceptance thresholds |
| `simulator/use_6g/core/state.py` | Antenna array state and USE formula implementations (U1–U5) |
| `simulator/use_6g/core/metrics.py` | Metrics collection and acceptance gate checking |
| `simulator/use_6g/mimo_sync.py` | MIMO synchronization engine (adaptive LR, lock detection) |
| `simulator/use_6g/simulator.py` | Top-level simulator with 4 validation scenarios |
| `symbolu_robotics/formulas/use.py` | Original USE patent formulas for robotics |
| `docs/hardware/UNIVERSAL_COHERENCE_PROCESSOR_SPEC.md` | Parent UCP specification |
| `docs/hardware/COHERA_ISA_REFERENCE.md` | Instruction set for phase operations |

---

*Document Version: 1.0*
*Aligned with: UCP Spec v2.0, USE-6G Simulator v1.0*
*Status: Hardware Specification*
*Classification: CONFIDENTIAL*
