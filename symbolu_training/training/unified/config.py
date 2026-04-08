"""
Configuration module for the Unified LLM Training system.

Contains UnifiedTrainingConfig dataclass, MODEL_PRESETS, and SRK configuration builders.
Extracted from train_unified_llm.py.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

# Import SOVEREIGN_STATE_DIM for default config values
try:
    from symbolu_core.phase_transformer import SOVEREIGN_STATE_DIM
except ImportError:
    SOVEREIGN_STATE_DIM = 32  # Fallback

# SRK imports (conditional)
try:
    from agentic.sovereign import SRKConfig, SRKLossConfig
    SRK_AVAILABLE = True
except ImportError:
    SRK_AVAILABLE = False


@dataclass
class UnifiedTrainingConfig:
    """Unified training configuration for all model types."""

    # Model architecture
    model_type: str = "ontological"  # ontological, phase, hybrid
    model_size: str = "small"  # tiny, small, medium, large
    vocab_size: int = 50257
    max_seq_len: int = 2048
    dropout: float = 0.1
    attention_dropout: float = 0.1

    # Architecture overrides (optional - if None, use model_size preset)
    n_layer: Optional[int] = None
    n_head: Optional[int] = None
    n_embd: Optional[int] = None
    n_kv_heads: Optional[int] = None

    # Phase-specific parameters
    sync_steps: int = 3
    sync_lr: float = 0.1
    cosine_mode: str = "standard"  # V9.6.12: "standard", "shifted", or "complex"
    decay_gamma: float = 1.0  # V9.6.13: State decay factor (1.0=infinite, <1.0=local focus)
    learned_decay: bool = False  # V9.9.7: Per-head learned decay (Mamba/S4-style)
    bounded_phase: bool = True  # V9.9.11: Constrain φ to [-π, π] via π*sin() (mandatory fix - enabled by default)
    zero_mean_cosine: bool = False  # V9.9.11: Center cosine per head (forces selectivity)

    # V10.7.2: z-loss regularization — prevents unbounded logit norm growth
    # Penalizes log(sum(exp(logits)))^2. From PaLM/ST-MoE.
    # Set to 0 to disable. 1e-4 is a safe default.
    z_loss_weight: float = 1e-4

    # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
    # Separates content similarity from intent alignment to prevent intent from dominating:
    #   s_content = cos(φ_q - φ_k)           # What matches (preserved)
    #   s_align = cos(θ_JEPA - θ_SRK)        # Intent agreement (modulator)
    #   score = s_content * (1 + α * s_align) # Combined
    dual_channel_mode: bool = False  # Enable dual-channel attention
    alignment_authority: float = 0.1  # α: weight for alignment term (0=pure content, higher=more intent influence)

    # ==========================================================================
    # V10.6+ CONTROL-PLANE ITEMS (Hard Probes Integration)
    # ==========================================================================
    # D.5: No-Write Contract Enforcement - prevents control signals from encoding content
    # D.2: enable_slots_read routing flag - separate read/write paths for quad
    # D.1: OntoControl formalized interface - explicit control plane object
    # Reference: QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md, Appendix D

    # V10.6.1: Alignment Clamp (ChatGPT caveat - prevents over-constraint collapse)
    # Clamp bounds for alignment modulator: output = output * clamp(1 + α * s_align, min, max)
    alignment_clamp_min: float = 0.8  # Lower bound (prevents over-suppression)
    alignment_clamp_max: float = 1.2  # Upper bound (prevents over-amplification)

    # V10.6.2 D.5: No-Write Contract Enforcement
    strict_control_contract: bool = True  # If True, raise on contract violation; if False, warn

    # V10.6.3: Architecture Health Summary (PASS/FAIL diagnostics at startup)
    run_architecture_health_check: bool = True  # Run health check at training start
    architecture_health_strict: bool = False  # If True, abort training on FAIL

    # V10.6.5: Parameter-Matched Baseline Enforcement
    # Ensures baseline comparison uses exact parameter count (not just same architecture)
    enforce_baseline_param_match: bool = True  # Validate param count matches

    # V10.6.6: Quad Utilization Sanity Checks (diagnostic probes)
    enable_quad_utilization_checks: bool = False  # Enable quad utilization monitoring
    quad_utilization_warn_threshold: float = 0.01  # Warn if quad contributes < 1%
    quad_utilization_check_interval: int = 100  # Check every N steps

    # V10.6.7: Lightweight Probe Hooks (diagnostic only, not full datasets)
    enable_probe_hooks: bool = False  # Enable lightweight diagnostic probes
    probe_hook_interval: int = 500  # Run probes every N steps
    probe_hook_types: str = "phase_rotation,chunk_continuity"  # Comma-separated probe types

    # Phase Rotation Test (validates phase encodes relational structure)
    phase_rotation: bool = False  # Run phase rotation test after training
    phase_rotation_angles: str = "0,45,90,135,180,270"  # Angles to test (degrees)
    phase_rotation_as_diagnostic: bool = False  # Run as periodic diagnostic during training

    # V10.0: Binding Cache architecture (validated by diagnostic probes)
    binding_cache_top_k: int = 64  # Top-K cache size per head (O(nk) vs O(n²))
    no_binding_cache: bool = False  # Disable cache (use full attention)

    # V10.5: Interference-Aware Proposal Scoring (compositional creativity)
    # Applied AFTER proposals, BEFORE phase integration. Task-conditional.
    enable_quad_interference: bool = False  # Master switch (OFF by default)
    interference_lambda_text: float = 0.02  # Strength (0.01-0.03 for text, lower than vision)
    interference_min_step: int = 8  # Only apply after N decoding steps
    interference_entropy_gate: float = 1.2  # Only apply if proposal entropy > threshold
    interference_auto_classify: bool = True  # Auto-detect compositional tasks
    interference_modes: str = "compose,reason,write"  # Enabled modes (comma-separated)

    # V10.0: Binding Annotation (CSR/Kosha/SRK as SELECTORS, not attention modifiers)
    use_binding_annotator: bool = True  # Enable OntologicalBindingAnnotator
    use_csr_annotation: bool = True  # CSR affects binding salience (phonological grounding)
    use_kosha_annotation: bool = True  # Kosha affects binding salience (consciousness sheaths)
    use_srk_annotation: bool = True  # SRK affects binding salience (Sovereign State)

    # ==========================================================================
    # GCT (Gated Coherence Transformer) parameters
    # ==========================================================================
    # Pre-softmax coherence gating with lambda_ladder band insulation.
    # Routes heads between full O(n²) and local-window O(n*w) attention.
    gct_window_size: int = 128           # Local window size for coarse path
    gct_coherence_gamma: float = 5.0     # Output delta sensitivity in coherence score
    gct_coherence_delta: float = 3.0     # Residual delta sensitivity in coherence score
    gct_ema_decay: float = 0.9           # EMA smoothing for coherence scores
    gct_num_bands: int = 3               # Frequency bands (global/mid/local head partition)
    gct_alpha_sharpness: float = 10.0    # Sigmoid sharpness for routing probability
    gct_hard_route_threshold: float = 0.5  # Hard routing threshold (inference)
    gct_kappa: float = 3.0              # Lambda_ladder suppression strength
    gct_tau_ladder: float = 0.15        # Collapse detection threshold
    gct_warmup_steps: int = 500         # Full-attention-only warmup (Phase 1)
    gct_anneal_steps: int = 2000        # Anneal from full to gated (Phase 2)

    # Hybrid-specific parameters
    local_layers: int = 4
    window_size: int = 256
    local_backend: str = "auto"
    alpha_local: float = 0.8
    alpha_phase: float = 0.2

    # Alpha decay schedule (for phase/hybrid attention)
    alpha_phase_start: float = 0.6
    alpha_phase_end: float = 0.4
    alpha_decay_steps: int = 10000

    # V10.2.1: Chunking for long sequences (hybrid models)
    enable_chunking: bool = False  # Enable chunked training for long sequences
    chunk_size: int = 512  # Size of each chunk when chunking enabled
    protected_phase: bool = True  # V10.2.1: Protected Phase (Local cross-attends to Phase)
    no_protected_phase: bool = False  # Disable protected phase (legacy parallel mode)
    run_chunk_diagnostic: bool = False  # Run chunk continuity diagnostic at start
    chunk_diagnostic_seq_len: int = 2048  # Sequence length for chunk diagnostic
    enable_tbptt: bool = False  # V10.7: Truncated BPTT (detach state between chunks, memory O(C))

    # ==========================================================================
    # V10.14: GLOBAL TOKENS / SLOT MEMORY (GCT)
    # ==========================================================================
    # SlotMemoryGCT provides addressable memory slots for long-range retrieval.
    # Tokens write to slots via competitive assignment; queries read via attention.
    # Required for associative recall beyond the local attention window.
    global_tokens_enabled: bool = False  # Enable GCT memory slots
    num_global_tokens: int = 64  # Number of memory slots
    global_update_mode: str = "slots"  # "pool", "attn-lite", or "slots"
    slots_write_lr: float = 0.15  # EMA learning rate for slot writes (V10.22: 0.1->0.3 overshot, settling at 0.15)
    retrieval_loss_weight: float = 2.0  # V10.21: Increased from 1.0 to compensate for gradient attenuation
    slot_prediction_loss_weight: float = 0.1  # V11.4: Weight for slot-only prediction loss
    slot_memory_lr_scale: float = 0.1  # Slot param LR multiplier vs main LR

    # V11: Slot memory experiment — read interval and late-layer writes
    global_read_interval: int = 1  # Read slots every N layers (1 = every layer)
    global_write_start_layer: int = 0  # Only write to slots from this layer onward
    disable_slot_adaptive_constraints: bool = False  # Disable adaptive constraint relaxation
    reset_slot_constraints: bool = False  # Reset adaptive constraints to defaults on resume
    slot_gate_target: Optional[float] = None  # Override gate ceiling target (default: 0.35)
    slot_gate_ceil_weight: Optional[float] = None  # Override gate ceiling penalty weight (default: 5.0)
    slot_gate_ceil_margin: Optional[float] = None  # Free zone above target before penalty (default: 0.05)
    # V16: Semantic coherence gate — modulates write assignment by value-space coherence
    slot_coherence_floor: Optional[float] = None  # Initial coherence floor (default: 0.3, decays to 0)
    slot_coherence_floor_tied: bool = True  # V16.1: Tie coherence floor to slot LR scale (default: on)

    # V20: Auto-scaling slot memory — derives slot hyperparameters from model size
    # and training budget. When enabled, num_global_tokens and step-based schedules
    # are computed from embed_dim, num_layers, and max_steps instead of using
    # fixed defaults that only work well for small/medium models.
    slot_auto_scale: bool = False  # Enable auto-scaling (overrides manual slot defaults)

    # V10.23: Three-phase proportional slot LR controller
    # Phase 1 (bootstrap): fixed LR until warmup_complete + sufficient signal history
    # Phase 2 (adaptive): continuous proportional control via LR *= e^(eta * health_score)
    # Phase 3 (stabilize): freeze when scale converges or step limit reached
    # Auto-enabled when slot memory params exist. Set slot_lr_eta=0 to disable.
    slot_lr_scale_min: float = 0.1    # Floor for slot LR scale
    slot_lr_scale_max: float = 0.8    # Ceiling for slot LR scale
    slot_lr_eta: float = 0.03         # Proportional controller gain (0 = disabled)
    slot_lr_stabilize_after: Optional[int] = None  # Hard step limit for phase 3 (None = auto-detect only)

    # ==========================================================================
    # PHASE-FIRST CURRICULUM (unified inverse curriculum for phase attention)
    # ==========================================================================
    # Master toggle that enables optimal phase-first learning configuration:
    #   - SRK inverted annealing (strong early, ramp down)
    #   - PPL-alpha curriculum (phase high when PPL high)
    #   - Adaptive window size (small early, large later)
    #   - Layerwise: lower layers keep phase longer
    # Individual settings below can override defaults when phase_first_curriculum=True
    phase_first_curriculum: bool = False

    # PPL-gated alpha curriculum (phase dominates early, local refines later)
    # When enabled, alpha_phase is computed based on current PPL:
    #   PPL >= ppl_high: alpha_phase = alpha_phase_ppl_high (phase dominates)
    #   PPL <= ppl_low:  alpha_phase = alpha_phase_ppl_low (local refines)
    #   In between: linear interpolation
    enable_ppl_alpha_curriculum: bool = False
    alpha_phase_ppl_high: float = 0.8   # alpha_phase when PPL >= ppl_high_threshold
    alpha_phase_ppl_low: float = 0.3    # alpha_phase when PPL <= ppl_low_threshold
    ppl_high_threshold: float = 1000.0  # PPL threshold for max phase weight
    ppl_low_threshold: float = 100.0    # PPL threshold for min phase weight
    # Adaptive window size (small early for fast phase, large later for local context)
    enable_adaptive_window: bool = False  # Enable window size adaptation with PPL
    window_size_high_ppl: int = 128       # Window size when PPL >= ppl_high_threshold
    window_size_low_ppl: int = 256        # Window size when PPL <= ppl_low_threshold
    # Post-curriculum adaptive alpha (slot ablation-driven)
    enable_adaptive_alpha: bool = False    # Adapt alpha_phase from slot ablation after curriculum settles
    adaptive_alpha_min: float = 0.20      # Floor for adaptive alpha_phase
    adaptive_alpha_max: float = 0.60      # Ceiling for adaptive alpha_phase

    # Decorrelation loss (to force phase and local to learn different features)
    decorr_loss_weight: float = 0.0  # Weight for decorrelation loss (0=disabled, 0.1=recommended)

    # V9.9.10: Phase diversity loss (to combat phase collapse)
    # Uses uniformity loss |E[e^{iφ}]|² and entropy proxy R = |E[e^{iφ}]|
    phase_diversity_weight: float = 0.0  # Combined weight (0=disabled, 0.001=start, ramp to 0.01)
    phase_diversity_ramp_steps: int = 5000  # Steps to ramp weight linearly (ignored if adaptive)

    # V9.9.12: Adaptive Phase Diversity Controller (ChatGPT Universal Proposal)
    # Replaces fixed λ and ramp with scale-free control loop based on R
    enable_adaptive_phase_diversity: bool = False  # Use adaptive controller instead of fixed
    phase_diversity_target_R: float = 0.25  # Target mean resultant length (0.25 = healthy)
    phase_diversity_lambda_init: float = 0.0001  # Initial λ after ramp
    phase_diversity_lambda_max: float = 0.1  # Maximum λ ceiling
    phase_diversity_eta: float = 0.1  # Control gain (how fast λ adapts)
    phase_diversity_ramp_multiplier: float = 5.0  # ramp_steps = multiplier * warmup_steps
    # V9.9.12b: Task-loss scaling (ChatGPT's Lagrange multiplier approach)
    phase_diversity_task_scaling: bool = True  # Scale λ by task loss (self-normalizing)
    phase_diversity_task_alpha: float = 0.01  # Base coefficient for task-loss mode

    # V9.9.1 Per-Layer Phase Control (for Inverted Curriculum)
    enable_per_layer_phase: bool = False  # Enable per-layer phase weight control
    per_layer_phase_weights: str = ""  # Initial weights: "0,0,0,0,0,0,0,0,0,0,0,0" (12 values)
    layer_transition_steps: int = 500  # Steps for soft layer transitions

    # V9.9.1 Inverted Curriculum Controller
    enable_inverted_curriculum: bool = False  # Enable full inverted curriculum
    inverted_curriculum_stages: str = ""  # Custom stages: "3:9@256,5:7@512,6:6@768,9:3@2048"
    inverted_curriculum_ppl_triggers: str = ""  # PPL triggers: "300,200,120,75,45,25"
    # V9.9.4: PPL Stability Check (ChatGPT's Readiness Index)
    inverted_curriculum_stability_threshold: float = 5.0  # Max PPL slope for "stable"
    inverted_curriculum_stability_stages: str = "2,3,4"  # Stages requiring stability (geometry shift zone)

    # Ontological-specific parameters
    bhava_embed_dim: int = 128
    num_drishti_heads: int = 4

    # V9.8.0: Ontological Hybrid (Two-Tier AGI) with 32D Sovereign State
    # Replaces arbitrary 124D (44 phonemes + 64 topics + 12 bhava + 4 dynamics)
    # with principled 32D: [0:12] Bhava, [12:17] Kosha, [17:22] Vritti, [22:28] Guna, [28:32] Reserved
    state_dim: int = SOVEREIGN_STATE_DIM  # 32D Sovereign State (was 124D CognitiveState)
    project_per_head_dim: bool = False  # If True, project ΔS to [H, D_h] instead of [H]

    # Training hyperparameters
    batch_size: int = 8
    batch_size_max: int = 512  # Max batch size for dynamic scaling (seq len curriculum)
    gradient_accumulation: int = 1
    vram_threshold: float = 0.95  # VRAM % to trigger batch reduction (0.95 = 95%)
    vram_recovery_buffer: float = 0.12  # Recovery when VRAM < (threshold - buffer)
    max_steps: int = 10000
    warmup_steps: int = 500  # Max warmup steps (fallback if PPL doesn't drop)
    warmup_until_ppl: float = 500.0  # End warmup when PPL < this (0 = disabled, use fixed steps)

    # Optimizer
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    max_grad_norm: float = 1.0
    use_per_layer_clipping: bool = False  # Clip auth/sens layers separately
    use_8bit_optimizer: bool = False  # Use bitsandbytes 8-bit AdamW (saves ~50% optimizer memory)
    use_compile: bool = False  # Use torch.compile() for faster training (PyTorch 2.0+)

    # Mixed precision
    mixed_precision: str = "bf16"

    # Gradient checkpointing
    gradient_checkpointing: bool = False
    checkpoint_offload_cpu: bool = False  # Offload checkpointed activations to CPU (metabolic tuning)

    # Checkpointing
    checkpoint_dir: str = "checkpoints_unified"
    save_every: int = 1000
    no_save: bool = False  # Skip all checkpoint saving (useful for benchmark runs)
    eval_every: int = 100
    log_every: int = 10

    # Logging verbosity
    quiet: bool = False  # Quiet mode: only print Critical 5 (Loss, PPL, S/A, GC, Conf)

    # Kosha-Vritti Diagnostic System
    enable_kosha_diagnostics: bool = False   # Enable Sheath-State diagnostic output
    kosha_log_every: int = 0                 # Log Kosha every N steps (0 = use log_every)
    lightweight_diagnostics: bool = True     # V9.7.0: Skip expensive gradient norm computation in diagnostics

    # Kosha Phase Steering (Active Intervention) - Layer 9 = O9_WITNESSES
    enable_kosha_steering: bool = False      # Enable phase coupling steering
    kosha_steering_force: float = 0.15       # Steering strength (0.0-1.0, start gentle)
    kosha_steering_warmup: int = 100         # Steps before steering activates
    kosha_steering_layer: int = 9            # V9.7.0: Layer 9 = O9_WITNESSES (consciousness/awareness alignment)

    # ==========================================================================
    # v2.2.1: Kosha Gyroscope - Homeostatic Self-Regulation Loss
    # Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md
    # ==========================================================================
    enable_kosha_gyroscope: bool = False     # Master toggle for Kosha Gyroscope system
    # V9.8.7: Dynamic three-phase engagement based on Val PPL thresholds
    gyroscope_engage_ppl: float = 50.0       # Phase 2: Auto-engage with RELAXED settings
    gyroscope_active_ppl: float = 30.0       # Phase 3: Switch to ACTIVE settings
    # Phase settings: RELAXED (30-50 PPL) vs ACTIVE (<30 PPL)
    gyroscope_relaxed_ceiling_clamp: float = 0.90   # Relaxed: gentle clamping
    gyroscope_relaxed_floor_push: float = 0.30      # Relaxed: gentle push
    gyroscope_active_ceiling_clamp: float = 0.65    # Active: firm clamping
    gyroscope_active_floor_push: float = 0.75       # Active: firm push
    # Dynamic Weight Scheduler (v2.2.1 - prevents "Aphasia")
    gyroscope_base_gain: float = 0.15        # Gentle observation when PPL > 100
    gyroscope_max_gain: float = 3.0          # Strict enforcement when PPL -> 30
    gyroscope_ppl_ceiling: float = 100.0     # PPL above which gain stays at base
    gyroscope_target_ppl: float = 30.0       # PPL at which gain reaches max (disengage threshold)
    # Trap detection thresholds (v2.2.5: Golden Ratio φ for sigmoid mode)
    gyroscope_trap_threshold: float = 0.618  # Legacy: Kosha saturation point (Golden Ratio φ)
    gyroscope_gate_threshold: float = 0.30   # Minimum for gate activation
    gyroscope_balance_target: float = 0.25   # Required opposite activation
    gyroscope_gate_temperature: float = 10.0 # Softness of gate (higher = sharper)
    # v2.3.0: Complete Harmonic Pentad - Sattvic Range for each Kosha
    # Each Kosha has a Floor (Push) and Ceiling (Clamp) defining the healthy band
    # ┌───────────┬─────────────────────────┬─────────────────────┬─────────────────────────┐
    # | Kosha     | Floor (Push)            | Sattvic Band        | Ceiling (Clamp)         |
    # ├───────────┼─────────────────────────┼─────────────────────┼─────────────────────────┤
    # | Mental    | 23.6%: Spark Abstraction| 23.6% - 38.2%       | 38.2%: Bliss Damper/Rip |
    # | Physical  | 38.2%: Grounding Push   | 38.2% - 61.8%       | 61.8%: Data Trap        |
    # | Intellect | 25.0%: Logic Pressure   | 25.0% - 61.8%       | 61.8%: Hubris Tax       |
    # | Vital     | 23.6%: Wake-up Boost    | 23.6% - 78.6%       | 78.6%: Momentum Brake   |
    # | Bliss     | 23.6%: Spark Creativity | 23.6% - 61.8%       | 61.8%: Delusion Tether  |
    # └───────────┴─────────────────────────┴─────────────────────┴─────────────────────────┘
    # Mental thresholds
    gyroscope_floor_mental: float = 0.236         # Spark Abstraction - below this, push toward abstraction
    gyroscope_ceiling_mental: float = 0.382       # Bliss Damper / Reality Rip
    # Physical thresholds
    gyroscope_floor_physical: float = 0.382       # Grounding Push - below this, push toward grounding
    gyroscope_ceiling_physical: float = 0.618     # Data Trap - above this, dilute raw data copying
    # Intellect thresholds
    gyroscope_floor_intellect: float = 0.250      # Logic Pressure - below this, push toward reasoning
    gyroscope_ceiling_intellect: float = 0.618    # Hubris Tax - above this, penalize over-intellectualization
    # Vital thresholds
    gyroscope_floor_vital: float = 0.236          # Wake-up Boost - below this, increase momentum
    gyroscope_ceiling_vital: float = 0.786        # Momentum Brake - above this, dampen overheating
    # Bliss thresholds
    gyroscope_floor_bliss: float = 0.236          # Spark Creativity - below this, release damping
    gyroscope_ceiling_bliss: float = 0.618        # Delusion Tether - above this, reduce gain
    # Clamp/Push factors (how strongly to correct deviations)
    gyroscope_floor_push_factor: float = 0.5      # Loss weight for floor violations
    gyroscope_ceiling_clamp_factor: float = 0.5   # Gain reduction for ceiling violations
    # v2.3.2: Reflexive Domain Morph
    # Combines external signal (token heuristics) with internal signal (Kosha state)
    # to create a morph factor μ ∈ [0, 1] that adjusts Sattvic Bands in real-time.
    gyroscope_domain_morph_enabled: bool = True   # Enable reflexive domain morphing
    gyroscope_domain_morph_ema_decay: float = 0.9  # EMA decay for token heuristics
    gyroscope_domain_morph_internal_weight: float = 0.5  # Weight for internal (Kosha) signal
    gyroscope_domain_morph_external_weight: float = 0.5  # Weight for external (token) signal
    # v2.2.4: Three-Stage Hybrid Logic (Damping + Gate + Rip)
    gyroscope_damper_steepness: float = 5.0  # Sigmoid steepness for Bliss/Physical damper
    gyroscope_gate_steepness: float = 5.0    # Sigmoid steepness for Physical/Mental gate
    gyroscope_rip_multiplier: float = 2.0    # Multiplier for Reality Rip signal (circuit breaker)
    # Legacy: steepness (deprecated in v2.2.4, kept for backward compatibility)
    gyroscope_steepness: float = 5.0         # Soft-threshold steepness (2.0=fluid, 5.0=balanced, 10.0=sharp)
    # Refinements (v2.2.0)
    gyroscope_temporal_window: int = 3       # Physical history window size
    gyroscope_vital_momentum: bool = True    # Enable dynamic gain via Vital
    gyroscope_warmup_steps: int = 100        # Steps before gyroscope fully active
    kosha_rampdown_steps: int = 500      # Steps to ramp gain to 0 at disengage
    # V9.9.0 CRITICAL FIX: Corrected Kosha Engagement Logic
    # PREVIOUS (WRONG): Engaged at high PPL (struggling) → Added constraints when model needed fundamentals
    # CORRECTED: Engage at low PPL (ready) → Add sophistication only after basics are learned
    #
    # Phase A (PPL > disengage): Kosha OFF - "learning fundamentals, no constraints"
    # Phase B (engage < PPL < disengage): Linear rampup - "transition"
    # Phase C (PPL < engage): Kosha fully ON - "ready for homeostatic regulation"
    kosha_engage_ppl: float = 30.0       # Kosha fully ON below this PPL (model ready)
    kosha_disengage_ppl: float = 100.0   # Kosha OFF above this PPL (model struggling)
    # Graduation criteria (legacy - kept for stability check)
    gyroscope_graduation_ppl: float = 30.0   # PPL threshold for graduation (mean)
    gyroscope_graduation_variance: float = 1.5  # Max PPL variance for stability
    gyroscope_graduation_window: int = 10    # Window for stability check
    # Diagnostic logging
    enable_rip_logger: bool = False          # Enable Reality Rip diagnostic logging
    rip_logger_dir: str = "diagnostics/rips" # Directory for rip event files
    # v2.3.3: 32D Sovereign State Regularizer
    enable_state_regularizer: bool = False   # Enable 32D anti-saturation regularizer
    state_reg_anti_sat_weight: float = 0.5   # Weight for anti-saturation loss
    state_reg_variance_weight: float = 0.2   # Weight for VICReg variance loss
    state_reg_sat_thresh_high: float = 0.95  # Penalize above this (too hot)
    state_reg_sat_thresh_low: float = 0.05   # Penalize below this (too cold)
    state_reg_target_std_kosha: float = 0.15 # Target std for Kosha dimensions
    state_reg_vital_weight: float = 1.5      # Extra penalty for VITAL (prone to saturation)
    state_reg_bliss_weight: float = 1.5      # Extra penalty for BLISS (prone to saturation)

    # V9.7.0: Ontological Bridge (Layer 4 - Foundational Structure)
    enable_onto_bridge: bool = False         # Enable 12D ontological projection at Layer 4
    onto_bridge_lambda: float = 0.1          # Weight for ontological bridge loss
    onto_bridge_diversity: float = 0.1       # Weight for diversity component (prevent collapse)
    onto_bridge_pramana: float = 0.1         # Weight for Pramāṇa alignment component
    onto_bridge_layer: int = 4               # V9.7.0: Layer 4 = foundational ontological grounding
    # V9.9.0 CRITICAL FIX: Corrected Ontological Bridge Engagement Logic
    # PREVIOUS (WRONG): Engaged at PPL>150 → Added 12D ontological constraints too early
    # CORRECTED: Engage at PPL<50 → Add ontological structure only after language modeling works
    #
    # Phase A (PPL > disengage): Onto OFF - "pure language modeling"
    # Phase B (engage < PPL < disengage): Linear rampup - "gradual introduction"
    # Phase C (PPL < engage): Onto fully ON - "ontological grounding ready"
    onto_engage_ppl: float = 50.0            # Onto fully ON below this PPL (model ready)
    onto_disengage_ppl: float = 150.0        # Onto OFF above this PPL (model needs fundamentals)
    onto_rampdown_steps: int = 500           # Steps to ramp to 0 after disengage

    # Dataset
    dataset: str = "wikitext103"  # "wikitext103", "wikitext2", "fineweb", "mixed", "reasoning_hf", "reasoning", or "synthetic"
    dataset_name: str = "HuggingFaceFW/fineweb"  # HuggingFace dataset name (for fineweb/reasoning_hf mode)
    dataset_subset: str = "sample-10BT"  # Dataset subset/config
    mix_datasets: str = ""  # For mixed mode: "wikitext103:0.7,reasoning_hf:0.3"
    cache_val_batches: int = 20  # Pre-cache N validation batches (for streaming datasets)
    cache_dataset: bool = False  # Download and cache dataset locally (vs streaming)
    tokenizer: str = "gpt2"

    # Loss weights for ontological model
    lambda_lm: float = 1.0        # Language modeling loss
    bhava_lambda: float = 0.1     # Bhava relationship consistency
    coherence_lambda: float = 0.05  # Global coherence
    lambda_entropy: float = 0.01  # Entropy regularization

    # V9.5.1 Entropy Floor (prevents repetition curse)
    enable_entropy_floor: bool = False  # Enable entropy floor penalty
    entropy_floor: float = 0.48  # Minimum entropy target
    entropy_floor_weight: float = 0.1  # Weight for floor penalty

    # Entropy-Based Logit Scale Control
    # Train-time: learnable logit scale with entropy band penalty
    # Inference-time: adaptive temperature targeting entropy midpoint
    enable_entropy_control_train: bool = False  # Enable train-time entropy regulation
    enable_entropy_control_infer: bool = False  # Enable inference-time adaptive entropy
    entropy_topk: int = 50                      # K for top-K entropy computation
    entropy_h_min: float = 0.15                 # Lower bound of target entropy band
    entropy_h_max: float = 0.35                 # Upper bound of target entropy band
    entropy_control_lambda: float = 0.01        # Weight for entropy band penalty
    logit_scale_min: float = -4.0               # Min log-scale clamp
    logit_scale_max: float = 4.0                # Max log-scale clamp
    infer_h_target: float = 0.25                # Target entropy for inference
    infer_eta: float = 0.02                     # Inference adaptation rate
    infer_delta_clip: float = 0.05              # Inference error clip

    # V9.5.1 Force Evolution (manual intervention)
    force_evolution_stage: int = None  # Force to stage: 1=6:6, 2=5:7, 3=4:8, 4=3:9

    # V9.9.1 Multi-Stage Evolution Configuration
    # Allows dynamic progression through layer splits based on PPL or step triggers
    enable_multi_stage_evolution: bool = True  # Enable automatic multi-stage evolution
    evolution_trigger_mode: str = "auto"  # "metrics", "ppl", "step", or "auto" (best available)
    evolution_ppl_triggers: str = ""  # PPL thresholds: "100,50,25,15" → trigger at each PPL
    evolution_step_triggers: str = ""  # Step triggers: "10000,30000,50000,70000"
    custom_evolution_stages: str = ""  # Custom stages: "9:3,6:6,4:8,3:9" (default: 9:3→6:6→5:7→4:8→3:9)
    evolution_patience: int = 200  # Steps of stable metrics before evolution (for metrics mode)
    evolution_coherence_min: float = 0.82  # Minimum coherence to evolve (metrics mode)
    evolution_entropy_floor: float = 0.42  # Minimum entropy to evolve (metrics mode)
    evolution_ppl_window: int = 10  # Steps to average PPL for smoother triggers
    evolution_thaw_alpha: float = 0.1  # Initial gradient scale for newly sensory layers
    evolution_thaw_steps: int = 300  # Steps to ramp newly sensory layer gradients

    # V9.5.2 Emergency Stress-Probe (Phase A: 3:9 Rajas)
    # Gemini Protocol: Freeze Authority, flood with Sensory to break stiffness
    # ChatGPT Guardrails: Compound trigger, strict duration, gradual LR restore
    enable_stress_probe: bool = False  # Enable automatic stress-probe detection
    stress_probe_entropy_trigger: float = 0.42  # Trigger when entropy drops below this (ChatGPT: 0.42)
    stress_probe_rep3_trigger: float = 0.18  # Trigger when REP-3 exceeds this (ChatGPT: 0.18)
    stress_probe_utr_trigger: float = 0.55  # Trigger when UTR drops below this (ChatGPT: 0.55)
    stress_probe_drs_trigger: float = 12.0  # Trigger when DRS exceeds this (ChatGPT: 12)
    stress_probe_coherence_min: float = 0.80  # Only trigger if coherence is high (stiff, not dying)
    stress_probe_patience: int = 2  # Consecutive evals of degeneracy before triggering (ChatGPT: 2)
    stress_probe_authority_scale: float = 0.05  # Nearly freeze Authority layers
    stress_probe_lr_factor: float = 0.60  # Reduce LR to 60% during stress-probe (ChatGPT: 0.6)
    stress_probe_exit_entropy: float = 0.55  # Exit when entropy exceeds this for 2 evals
    stress_probe_exit_rep3: float = 0.12  # Exit when REP-3 drops below this
    stress_probe_min_steps: int = 100  # Minimum steps in stress-probe (ChatGPT: 100)
    stress_probe_max_steps: int = 300  # Maximum steps in stress-probe (ChatGPT: 300)
    stress_probe_lr_restore_steps: int = 50  # Steps to gradually restore LR after exit
    force_stress_probe: bool = False  # Force immediate stress-probe activation

    # Sovereign-1 loss configuration (hardened decomposed loss)
    use_sovereign_loss: bool = True  # Enable Sovereign-1 decomposed loss
    sovereign_weight_guna: float = 1.0   # Guna signal weight
    sovereign_weight_s: float = 2.0      # S-Signal (referent) weight
    sovereign_weight_r: float = 5.0      # R-Signal (ontology) weight - CRITICAL
    sovereign_weight_c: float = 0.5      # C-Signal (phoneme) weight

    # Coherence loss (for phase/hybrid)
    use_coherence_loss: bool = False
    no_coherence_loss: bool = False  # CLI flag to disable

    # Sovereign-Lagrangian Loss [Patent B1/S3]
    enable_sovereign_loss: bool = False   # Enable Sovereign-Lagrangian loss
    b1_lambda: float = 0.5                # Consistency Lagrangian weight [B1]
    mu_s3: float = 0.2                    # Global Coherence weight [S3]
    enable_stability_constraint: bool = False  # Enable S8 entropy anchoring
    gc_floor: float = 0.65                # Minimum GC for PIDv2 intervention

    # PIDv2 Controller settings (V9.4.4)
    controller: str = "none"  # none, pidv2, emergency_pd
    pidv2_kp_min: float = 0.10
    pidv2_kp_max: float = 0.30
    pidv2_kp_sensitivity: float = 5.0
    pidv2_ki: float = 0.02
    pidv2_kd: float = 0.10
    pidv2_a_min: float = 0.40  # Raised from 0.30 to boost sensory floor
    pidv2_c_floor: float = 0.45  # V9.8.6: Relaxed for Phase 1 (construction)
    pidv2_c_good: float = 0.65   # V9.8.6: Achievable target, auto-disable PID at 0.75
    pidv2_w_s: float = 0.30  # Semantic weight
    pidv2_semantic_scale: float = 50.0
    pidv2_handshake_dampen: bool = True
    # V9.7.0: PIDv2 Dynamic Batch Sizing
    pidv2_batch_resize: bool = False          # Enable PPL-driven batch resizing
    pidv2_batch_min: int = 4                  # Minimum batch size
    pidv2_batch_max: int = 64                 # Maximum batch size
    pidv2_batch_velocity_threshold: float = 5.0  # PPL velocity % to trigger reduction
    pidv2_batch_stable_streak: int = 5        # Consecutive stable evals before increase

    # V9.8.7: Three-phase PID engagement based on Val PPL
    # Phase 1 (Construction): PPL > engage_ppl → PID ON (aggressive correction)
    # Phase 2 (Transition):   disengage_ppl < PPL < engage_ppl → PID continues
    # Phase 3 (Polishing):    PPL < disengage_ppl → PID OFF (let model converge naturally)
    pidv2_engage_ppl: float = 100.0      # PID turns ON when Val PPL > this
    pidv2_disengage_ppl: float = 30.0    # PID turns OFF when Val PPL < this
    pidv2_rampdown_steps: int = 500      # Steps to ramp down after disengage
    pidv2_engagement_enabled: bool = True # Enable dynamic PID engagement

    # Phase ramp settings (for handshake dampening)
    phase_delay_steps: int = 0
    phase_ramp_steps: int = 7000

    # Formula [1331]: 9:3 Hierarchical Split Configuration
    use_9_3_split: bool = False           # Enable 9:3 Authority/Sensory gradient scaling
    enable_gradient_scaling: bool = False  # Enable gradient scaling for ANY split (6:6, 9:3, etc.)
    authority_layers: int = 9             # Number of Authority (State-Delta) layers
    sensory_layers: int = 3               # Number of Sensory (Quadratic) layers
    alpha_sens_initial: float = 0.05      # Initial sensory gradient multiplier (balanced start to prevent S/A spikes)
    alpha_sens_max: float = 0.7           # Maximum sensory gradient (after warmup/relaxation)
    gradient_warmup_steps: int = 500      # Steps to ramp α_sens from initial to max
    # V9.6.8: Layer-wise alpha dampening (Gemini recommendation)
    # Output layers (9-11) should be more stable than reasoning layers (6-8)
    enable_layerwise_alpha: bool = True   # Enable per-layer alpha scaling
    alpha_output_scale: float = 0.5       # Scale for output layers 9-11 (α × 0.5 = more stable)
    alpha_reasoning_scale: float = 1.0    # Scale for reasoning layers 6-8 (α × 1.0 = more expressive)
    authority_floor: float = 1.0          # Alpha floor for authority layers (1.0 = full gradients, 0.3 = 30% dampened)

    # Dynamic Relaxation: 9:3 → 6:6 transition
    enable_dynamic_relaxation: bool = True   # Enable automatic 9:3 → 6:6 transition
    relaxation_mode: str = "sa_ratio"        # "sa_ratio" (recommended), "consecutive", or "average"
    relaxation_stability_threshold: float = 0.50  # S/A ratio threshold for trigger
    relaxation_stability_window: int = 500   # Steps for stability check (rolling window)
    relaxation_streak_target: int = 5        # Consecutive stable evals (for consecutive mode)
    force_relaxation_step: int = None        # Force 9:3→6:6 at this step (bypasses stability check)
    # Sovereign Saturation Gate (automatic detection)
    enable_saturation_gate: bool = True      # Enable automatic saturation detection
    saturation_coherence_threshold: float = 0.74  # Coherence threshold for trigger
    saturation_patience: int = 50            # Steps where sensory derivative must be flat
    saturation_thaw_start: float = 0.3       # New sensory layers start at this α
    saturation_thaw_end: float = 0.7         # Ramp to this α
    saturation_thaw_steps: int = 100         # Steps to ramp new layers
    relaxation_target_authority: int = 6     # Target authority layers after relaxation
    relaxation_target_sensory: int = 6       # Target sensory layers after relaxation
    relaxation_thaw_alpha: float = 0.05      # Dampened Thaw starting α for new sensory layers
    relaxation_thaw_steps: int = 500         # Steps for Dampened Thaw warmup
    relaxation_ppl_spike_threshold: float = 0.20  # PPL spike % to trigger Viparyaya
    relaxation_recovery_steps: int = 100     # Steps to stay in recovery mode

    # Weight Transfer (9:3 → 6:6)
    enable_weight_transfer: bool = True      # Enable weight transfer during relaxation
    guna_lock_steps: int = 50                # Steps to freeze W_q/W_k post-swap

    # Toroidal Evolutionary Bridge (O12 → O1 Recursive Intelligence)
    enable_toroidal_bridge: bool = False     # Enable state carryover from O12 to O1
    toroidal_lambda: float = 0.1             # Weight for toroidal consistency loss
    toroidal_dropout: float = 0.1            # Dropout in seed projection
    toroidal_use_gating: bool = True         # Use gated projection for selective carryover
    toroidal_truncated_bptt: int = 0         # Steps of gradient flow (0 = full detach)
    toroidal_coherence_threshold: float = 0.3  # Alarm threshold for cognitive discontinuity

    # Full Evolutionary Flow System (Phase 2: All Layer Transitions)
    # Extends Toroidal Bridge to ALL layer transitions with Delayed Resonance
    enable_evolutionary_flow: bool = False   # Master switch for evolutionary intelligence (opt-in)
    evo_lambda: float = 0.1                  # Overall evolutionary loss weight
    evo_micro_weight: float = 0.3            # Weight for per-gate coherence loss
    evo_meso_weight: float = 0.3             # Weight for cluster coherence loss (Auth/Sens)
    evo_macro_weight: float = 0.4            # Weight for toroidal coherence loss
    evo_dropout: float = 0.1                 # Dropout in evolutionary gates
    evo_use_rmatrix: bool = True             # Use R-Matrix for evolutionary weights
    evo_coherence_window: int = 100          # Steps for coherence history tracking
    evo_resonance_alpha: float = 0.1         # Strength of O12→O1 delayed resonance injection
    evo_lr_modulation: bool = True           # Enable metacognitive LR adjustment
    evo_lr_slowdown: float = 0.5             # LR multiplier when SLOW_DOWN/BRAKE
    evo_lr_accelerate: float = 1.2           # LR multiplier when ACCELERATE
    # V9.7.0: EvoFlow Fluency Gate - auto-engage gradients when model is fluent
    evo_fluency_gate: bool = False           # Enable automatic EvoFlow gradient engagement
    evo_fluency_min_steps: int = 2000        # Minimum steps before engagement (warmup)
    evo_fluency_ppl_threshold: float = 100.0 # PPL threshold for "fluent" (engage when PPL < this)

    # V9.8.0: RSS (Rational Sovereign Sequence) - Staged gradient engagement
    # Replaces individual fluency gates with unified phase controller
    # Key insight: Layer 7 (CSR) feeds Layer 9 (Kosha), so CSR must stabilize first
    enable_rss: bool = False                 # Enable RSS phase controller
    rss_evoflow_ppl: float = 100.0           # EvoFlow engages when PPL < this
    rss_toroidal_ppl: float = 60.0           # Toroidal engages when PPL < this
    rss_csr_ppl: float = 45.0                # CSR engages when PPL < this (with warmup)
    rss_kosha_ppl: float = 35.0              # Kosha engages when PPL < this AND CSR > 50%
    rss_csr_warmup_steps: int = 2500         # Steps for CSR to reach full strength (prevents 14x shock)
    rss_use_val_ppl: bool = True             # Use validation PPL (more stable) vs training PPL

    # PPL-Gated Curriculum Learning - Phased auxiliary loss introduction
    # Ensures model learns coherent generation BEFORE ontological constraints
    enable_curriculum: bool = False           # Enable curriculum controller
    curriculum_ppl_regularization: float = 30.0   # Enter REGULARIZATION when PPL < this
    curriculum_ppl_grounding: float = 15.0        # Enter GROUNDING when PPL < this
    curriculum_ppl_sovereign: float = 10.0        # Enter SOVEREIGN when PPL < this
    curriculum_stability_window: int = 5          # Consecutive evals below threshold
    curriculum_hysteresis: float = 1.5            # Prevent oscillation between phases

    # V2.3.4: Sequence Length Curriculum - Gradual sequence length ramping
    # Starts with shorter sequences for faster syntax learning, ramps up for long-range dependencies
    enable_seq_curriculum: bool = False           # Enable sequence length ramping
    seq_len_start: int = 256                      # Starting sequence length
    seq_len_end: int = 1024                       # Target sequence length (will use max_seq_len if 0)
    seq_len_ramp_steps: int = 5000                # Steps to reach full length
    seq_len_ramp_mode: str = "linear"             # "linear" or "exponential"
    seq_len_ppl_gate: float = 0.0                 # If > 0, only ramp when PPL < this (0 = step-based only)

    # CSR Phoneme-Ontological Grounding
    # NOTE: This is the standalone spatial-grounding CSR path. It injects phoneme
    # embeddings across layers (0, 7, 11) with entropy/synthesis safety gates.
    # A separate token-level CSR path exists via `lambda_csr_token` (see CG
    # Primitives section below). The two paths are NOT redundant:
    #   - enable_csr: spatial grounding (phoneme→hidden-state injection per layer)
    #   - lambda_csr_token: token scoring (bilinear phoneme×context compatibility)
    # Both default to off. Neither path feeds into inference (MistralCGAdapter).
    enable_csr: bool = False                 # Enable CSR phoneme grounding (opt-in)
    csr_lambda: float = 0.1                  # CSR injection strength
    csr_tau: float = 0.07                    # InfoNCE temperature (lower = sharper gradients, 0.07 = 14x amplification)
    csr_use_phase_gating: bool = True        # Gate Phase Attention with CSR confidence
    csr_trainable: bool = True               # Allow CSR projection to train
    csr_use_entropy_sink: bool = True        # Apply Layer 0 entropy floor
    csr_use_synthesis_gate: bool = True      # Apply Layer 11 synthesis reconciliation
    csr_alignment_layer: int = 7             # V9.7.0: Which layer to use for CSR alignment (7=concept consolidation, 2=early, 11=output)
    # V9.6.8: CSR Projector Learning Rate Scale (Gemini recommendation)
    csr_projector_lr_scale: float = 0.1      # CSR projector learns at 0.1x main LR for stability
    # V9.6.8: CSR Gradient Warmup - re-enable gradients after model learns grammar
    csr_gradient_warmup_steps: int = 0       # Steps before re-enabling CSR gradients (0=always detached)

    # V9.7.0: CSR Sparse Delayed Supervision (Whole Word Alignment)
    csr_sparse_supervision: bool = False     # Enable word-boundary-only supervision
    csr_content_word_only: bool = False      # Also filter out stopwords (requires sparse_supervision)

    # V9.9.0 CRITICAL FIX: Corrected CSR Engagement Logic
    # PREVIOUS (WRONG): Engaged at PPL>120 → Added phoneme constraints before basic tokens learned
    # CORRECTED: Engage at PPL<40 → Add CSR grounding only after coherent generation works
    #
    # Phase A (PPL > disengage): CSR OFF - "learning basic tokenization"
    # Phase B (engage < PPL < disengage): Linear rampup - "introducing phoneme awareness"
    # Phase C (PPL < engage): CSR fully ON - "phoneme-semantic alignment ready"
    csr_engage_ppl: float = 40.0             # CSR fully ON below this PPL (model ready)
    csr_disengage_ppl: float = 120.0         # CSR OFF above this PPL (model struggling)
    csr_rampdown_steps: int = 500            # Steps to ramp down after disengage trigger

    # ==========================================================================
    # Appendix G: Bliss Coherence Functional & Monitoring
    # Reference: docs/design/LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md, §G.10
    # Phase 1/2: measure + log (no gating)
    # Phase 3: Bliss gates CSR injection strength via λ_eff
    # ==========================================================================
    enable_bliss_monitoring: bool = True     # Compute & log Bliss B/B_A/B_B
    bliss_beta: float = 0.3                 # Cross-layer stability weight in B = mean(B_A) - β·B_B
    bliss_log_interval: int = 100           # Log Bliss metrics every N steps
    enable_12d_health_monitor: bool = True  # Track ontology projection health (SVD, variance, drift)
    health_monitor_interval: int = 100      # Steps between 12D health checks
    enable_gradient_tracker: bool = True    # Track gradient variance & direction stability
    enable_variance_dampen: bool = True    # V10.24: Adaptive LR dampening on variance spikes
    variance_dampen_threshold: int = 3     # Min spiking layers to engage dampening
    variance_dampen_min: float = 0.5       # Floor for variance dampening factor
    variance_dampen_recovery: float = 0.02 # Recovery rate per step toward 1.0

    # Phase 3: Bliss Gating (adaptive λ_eff for CSR injection)
    enable_bliss_gating: bool = False        # Phase 3: Bliss modulates csr_lambda via sigmoid gate
    bliss_gate_gamma: float = 5.0            # Gate sharpness: σ(γ·(B−τ))
    bliss_gate_lambda_min: float = 0.1       # Floor: λ_eff never drops below λ_min × λ_base
    bliss_gate_warmup_steps: int = 1000      # Steps before gating activates (bypass = full λ)

    # Phase 4: JEPA Injection (CSR + Bliss + JEPA multi-prior injection)
    # Reference: Appendix G.10.2 Stage 4
    # Requires: enable_jepa=True AND enable_bliss_gating=True
    enable_jepa_injection: bool = False      # Phase 4: Enable JEPA state delta as weak prior
    jepa_injection_lambda: float = 0.03      # Base λ_JEPA injection strength (G.3.4 default)
    jepa_injection_layer: int = 3            # Layer to inject JEPA prior (concept formation)
    jepa_injection_projector_lr_scale: float = 0.1  # LR scale for 32D→d_model projector

    # V9.6.0: Embedding configuration
    untie_embeddings: bool = False           # Untie input/output embeddings (CRITICAL when using CSR)

    # SGP (Stochastic Gradient Persistence) - "Cement" for CSR structure
    # V9.6.8: Updated defaults per Gemini recommendation (stronger cement, less frequent)
    enable_sgp: bool = False                 # Enable SGP synchronized with Sattvic Controller (opt-in)
    sgp_base_rate: int = 200                 # Base SGP rate (Toroidal Refresh Rate) - every 200 steps
    sgp_stagnation_rate: int = 100           # Rate when stagnation detected - halved from base
    sgp_gamma: float = 0.5                   # Persistence coefficient - was 0.3 (stronger cement)

    # Sattvic Controller (Dynamic λ_csr regulation)
    sattvic_initial_lambda: float = 0.5      # Initial λ_csr during warmup
    sattvic_floor_lambda: float = 0.1        # Minimum λ_csr after decay
    sattvic_warmup_steps: int = 500          # Steps for warmup phase
    sattvic_variance_window: int = 50        # Window for entropy variance detection
    sattvic_variance_threshold: float = 0.00001  # Lowered from 0.0001 - variance ~1e-5 still triggering boosts

    # Adaptive Training Controller (dynamic hyperparameter tuning)
    enable_adaptive_training: bool = True    # Enable automatic LR/Kp adjustment
    adaptive_lr_min: float = 1e-5            # Minimum learning rate floor
    adaptive_lr_max: float = 1e-3            # Maximum learning rate ceiling
    adaptive_lr_boost: float = 1.5           # LR boost multiplier when plateau/slow
    adaptive_lr_decay: float = 0.7           # LR decay multiplier when spike
    adaptive_velocity_slow: float = -2.0     # PPL velocity threshold for "too slow" (%)
    adaptive_velocity_spike: float = 10.0    # PPL velocity threshold for "spike" (%)
    adaptive_plateau_window: int = 5         # Evals to check for plateau
    adaptive_plateau_threshold: float = 1.0  # Min improvement % to avoid plateau detection
    adaptive_min_interval: int = 200         # Min steps between adjustments
    # V9.8.2: Safeguards to prevent runaway LR
    adaptive_max_lr_relative: float = 10.0   # Max LR = base_lr * this (prevents runaway)
    adaptive_loss_spike_threshold: float = 5.0  # % loss increase triggers emergency decay
    adaptive_grad_norm_spike: float = 100.0  # Gradient norm above this triggers decay
    adaptive_emergency_decay: float = 0.5    # Aggressive decay factor for emergencies
    adaptive_consecutive_spike_limit: int = 3  # After N consecutive spikes, halt boosts
    # V10.23: Spike-aware boost dampening
    adaptive_max_boost_from_base: float = 2.0   # Max LR = base_lr * this (cap compounding boosts)
    adaptive_spike_dampen_threshold: int = 10   # If >=N params spiked after last boost, dampen next
    adaptive_boost_cooldown_steps: int = 400    # Min steps between consecutive boosts

    # Auto Batch Sizing (VRAM-based startup probing)
    enable_auto_batch: bool = False          # Enable automatic batch size detection at startup
    auto_batch_target_utilization: float = 0.80  # Target VRAM utilization (80%)
    auto_batch_safety_margin: float = 0.05   # Extra headroom (5%)
    auto_batch_target_effective: int = 0     # Target effective batch (0 = just find max, no accum)

    # Friction Controller (V9.4.5)
    disable_friction: bool = False           # Disable friction controller
    friction_dom_high: float = 3.0           # Dominance 'riot' threshold (higher = allow more Sanskrit)
    friction_dom_low: float = 0.3            # Dominance 'lock' threshold
    friction_align_critical: float = -0.10   # Alignment critical threshold

    # Resume checkpoint
    resume: str = ""
    resume_weights_only: bool = False

    # TensorBoard
    tensorboard: bool = True

    # Quality Sampling
    sample_every: int = 50  # Generate samples every N steps (0 = disabled)
    sample_prompts: tuple = (
        "The Roman Empire began when Julius Caesar",  # Baseline
        "Water boils at 100 degrees Celsius, but at high altitudes,",  # Pivot/Contrast
        "To solve for x in the equation 2x + 6 = 10, the first step is to",  # Logic
        "The three primary colors are red, blue, and yellow. If we mix the first two, we get",  # Memory/Reference
        "The primary difference between a stack and a queue is that",  # Definitions (FineWeb)
    )

    # Knowledge Probes (factual accuracy, slot retrieval, phase coherence)
    knowledge_probe_every: int = 0    # Run probes every N steps (0 = disabled)
    knowledge_probe_top_k: int = 10   # Top-K to check for factual probes
    knowledge_probe_coherence_tokens: int = 256  # Tokens to generate for coherence test
    knowledge_probe_chunk_size: int = 64  # Chunk size for coherence measurement

    # LRA Validation (Long-Range Retrieval)
    lra_validate_every: int = 0  # Run LRA validation every N steps (0 = disabled)
    lra_haystack_lengths: str = "256,512,1024"  # Comma-separated lengths
    lra_num_samples: int = 50  # Samples per test

    # Hardware
    device: str = "auto"
    num_workers: int = 4

    # Seed
    seed: int = 42

    # ==========================================================================
    # V9.8.0: Sovereign Reasoning Kernel (SRK) Configuration
    # Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md
    # ==========================================================================
    enable_srk: bool = False                 # Master toggle for SRK system
    srk_hidden_dim: int = 768                # Hidden dimension for SRK projections
    srk_dna_bridge_layer: int = 4            # Layer 4: DNA Bridge (foundational ontology)
    srk_csr_alignment_layer: int = 7         # Layer 7: CSR Alignment (Phase Extraction Hook)
    srk_witness_layer: int = 9               # Layer 9: Witness Arbitrator (consciousness)
    srk_synthesis_layer: int = 11            # Layer 11: Synthesis Gate (output integration)
    srk_enable_dna_bridge: bool = True       # Enable DNA Bridge at Layer 4
    srk_enable_witness: bool = True          # Enable Witness Arbitrator at Layer 9
    srk_enable_synthesis: bool = True        # Enable Synthesis Gate at Layer 11
    srk_enable_imr: bool = True              # Enable Isomorphic Mapping Router
    srk_isomorphism_threshold: float = 0.75  # Threshold for IMR template matching
    srk_karma_decay: float = 0.9             # O12→O1 karma decay factor
    srk_enable_mauna: bool = True            # Enable Mauna Protocol (inference safety)
    srk_mauna_confidence_threshold: float = 0.6   # Minimum confidence for output
    srk_mauna_consistency_threshold: float = 0.5  # Minimum backward score

    # SRK Loss Configuration (B1/U2/S8 patent formulas)
    srk_lambda_f: float = 1.0                # Forward score weight (linguistic)
    srk_lambda_b: float = 1.0                # Backward score weight (ontological)
    srk_lambda_c: float = 0.5                # Consistency divergence penalty (B1)
    srk_lambda_coherence: float = 0.2        # Phase coherence weight (U2)
    srk_lambda_entropy: float = 0.1          # Stability constraint weight (S8)
    srk_lambda_task: float = 1.0             # Task loss weight (cross-entropy)
    srk_enable_nidra_penalty: bool = True    # Penalize VOID/dormancy state
    srk_nidra_penalty_weight: float = 0.05   # VOID penalty weight

    # SRK Annealing (Lambda Warmup)
    srk_total_steps: int = 50000             # Total training steps for annealing
    srk_warmup_steps: int = 5000             # Steps for System 1 warmup phase
    srk_invert_annealing: bool = False       # Invert: start strong, ramp DOWN (phase-first)

    # ==========================================================================
    # V9.8.8: Sovereign Phase Controller (SPC) Configuration
    # Reference: docs/SOVEREIGN_PHASE_CONTROLLER_DESIGN.md
    # ==========================================================================
    enable_sovereign_phase_controller: bool = False  # Master toggle (DISABLED by default)
    spc_entropy_critical: float = 0.4        # Red alert entropy threshold
    spc_entropy_warning: float = 0.5         # Yellow alert entropy threshold
    spc_entropy_recovered: float = 0.55      # Exit boost threshold (hysteresis)
    spc_variance_critical: float = 0.0005    # Critical variance threshold (stagnation)
    spc_variance_warning: float = 0.001      # Warning variance threshold
    spc_variance_recovered: float = 0.002    # Exit boost variance threshold
    spc_min_boost_duration: int = 100        # Minimum steps in boost mode (prevents oscillation)
    spc_alpha: float = 0.2                   # EMA smoothing coefficient for rotation damping
    spc_max_rotation: float = 0.3            # Maximum rotation per step (radians ~17°)
    spc_damping: float = 0.9                 # Velocity damping coefficient
    spc_velocity_threshold: float = 0.2      # Velocity threshold for applying damping

    # ==========================================================================
    # V9.8.9: Dynamic Window Scheduler (DWS) Configuration
    # Reference: Curriculum learning for receptive field dimension
    # ==========================================================================
    enable_dynamic_window: bool = False      # Master toggle (DISABLED by default)
    dws_schedule: Optional[str] = None       # Custom schedule "ppl1:win1,ppl2:win2,..."
    dws_growth_rate_max: float = 1.25        # Maximum growth rate (25% per transition)
    dws_shrink_rate_max: float = 0.80        # Maximum shrink rate (20% per transition)
    dws_align_to: int = 32                   # Align to multiples (GPU efficiency)
    dws_smooth_steps: int = 100              # Interpolation steps (smooth transitions)
    dws_min_steps_between: int = 200         # Cooldown between changes (stability)
    dws_hysteresis: float = 0.15             # PPL hysteresis factor (prevent thrashing)
    dws_vram_threshold: float = 0.85         # VRAM emergency shrink threshold

    # ==========================================================================
    # Phase-JEPA: Joint Embedding Predictive Architecture Configuration
    # Reference: docs/design/HYBRID_PHASE_JEPA_DESIGN.md
    # ==========================================================================
    enable_jepa: bool = False                # Master toggle for Phase-JEPA system
    jepa_hidden_dim: int = 256               # Hidden dimension for JEPA predictor
    jepa_prediction_steps: int = 4           # Number of k-step lookahead predictions
    jepa_num_heads: int = 4                  # Number of attention heads in predictor
    jepa_cosine_mode: str = "complex"        # Phase attention mode (complex/shifted/standard)

    # JEPA Loss Weights
    jepa_vicreg_weight: float = 1.0          # VICReg loss weight
    jepa_alignment_weight: float = 1.0       # Alignment loss weight
    jepa_prediction_weight: float = 0.5      # Prediction loss weight
    jepa_orthogonality_weight: float = 0.01  # Orthogonality regularization

    # JEPA Per-Component Alignment Weights
    # V9.6.8: Rebalanced to prevent Bhava mode collapse (was 10.0/1.0)
    jepa_bhava_weight: float = 1.0           # Bhava (identity) - equal weight allows evolution
    jepa_semantic_weight: float = 5.0        # Kosha/Vritti (semantic) - prioritized for coherence
    jepa_guna_weight: float = 0.1            # Guna (loosely coupled) weight

    # JEPA Target Encoder (EMA)
    jepa_target_momentum: float = 0.996      # EMA momentum for target encoder
    jepa_momentum_schedule: str = "cosine"   # constant/cosine/linear

    # JEPA Training Curriculum (Body→Soul→Union)
    jepa_training_phase: str = "body"        # Current phase: body/soul/union
    jepa_phase_body_steps: int = 20000       # Steps for Body phase
    jepa_phase_soul_steps: int = 30000       # Steps for Soul phase
    jepa_auto_phase_transition: bool = False # Auto-transition phases

    # JEPA Dynamic Graduation (metric-based phase transitions)
    jepa_enable_dynamic_graduation: bool = True    # Enable threshold-based graduation
    jepa_graduation_loss_threshold: float = 20.0   # Graduate if JEPA loss < this
    jepa_graduation_alignment_threshold: float = 25.0  # V9.6.8: Was 72.0 - unrealistic, caused stuck BODY phase

    # JEPA Vritti Validation
    jepa_enable_vritti_validation: bool = False  # Enable Vritti gate validation
    jepa_viparyaya_threshold: float = 0.4    # Max error before damping
    jepa_vikalpa_threshold: float = 0.6      # Max imagination (factual tasks)
    jepa_damping_factor: float = 0.5         # Damping for rejected predictions

    # JEPA-SRK Integration (Master/Sensor)
    jepa_enable_karma_injection: bool = False  # Enable karma injection from SRK
    jepa_karma_gate_bias: float = 0.5        # Initial gate bias (0=internal, 1=external)

    # V10.3.7: Vritti Entropy Regularization (prevents single-vritti collapse)
    vritti_entropy_reg: bool = False       # Enable entropy regularization for vritti
    vritti_entropy_lambda: float = 0.1     # Weight for entropy regularization

    # ==========================================================================
    # BCVF Contrastive Structural Pressure on Representations
    # Reference: symbolu/ontological/bcvf_contrastive.py
    # ==========================================================================
    use_bcvf_contrastive: bool = False     # Master toggle for contrastive objective
    bcvf_contrastive_lambda: float = 0.1   # Weight for L_rep in total loss
    bcvf_contrastive_K: int = 16           # Number of negatives per position
    bcvf_contrastive_K_pool: int = 256     # Candidate pool size for Stage A
    bcvf_contrastive_margin: float = 0.15  # Margin for ranking loss
    bcvf_contrastive_alpha: float = 2.0    # Temperature for BCVF negative weighting
    bcvf_contrastive_eta: float = 0.3      # Token embedding injection scale for proxy r_neg
    bcvf_contrastive_d_r: int = 128        # Projection output dimensionality
    bcvf_contrastive_T_sample: int = 4     # Positions per sequence to sample
    bcvf_contrastive_projector: str = "mlp"  # "linear" or "mlp"

    # ==========================================================================
    # BCVF Logit-Margin + Entropy Band (perplexity-aligned)
    # Reference: symbolu/ontological/bcvf_logit_margin.py
    # ==========================================================================
    use_logit_margin: bool = False         # Master toggle
    logit_margin_lambda: float = 0.05      # Weight for margin loss
    logit_margin_entropy_lambda: float = 0.01  # Weight for entropy band loss
    logit_margin_m: float = 0.7            # Minimum logit gap z_pos - z_neg
    logit_margin_H_min: float = 1.5        # Entropy band lower bound
    logit_margin_H_max: float = 4.0        # Entropy band upper bound
    logit_margin_top_k_neg: int = 1        # Hard negatives to average (1 = hardest)

    # ==========================================================================
    # KOSHA-VRITTI STRUCTURED SUPERVISION (Static Compatibility Version)
    # Reference: symbolu/training/kosha_vritti_supervision.py
    # ==========================================================================
    # Auxiliary soft-label supervision for Kosha (4-class) and Vritti (5-class)
    # with entropy floor, static joint compatibility matrix, and staged curriculum.
    # Does NOT modify transformer blocks -- only adds auxiliary linear heads.
    enable_kv_supervision: bool = False        # Master toggle
    kv_weight_kosha_kl: float = 0.1            # Weight for Kosha KL loss
    kv_weight_vritti_kl: float = 0.1           # Weight for Vritti KL loss
    kv_weight_entropy_floor: float = 0.01      # Weight for entropy floor penalty
    kv_weight_compatibility: float = 0.05      # Weight for joint compatibility loss
    kv_weight_prior: float = 0.001             # Weight for W_kv prior regularization
    kv_entropy_floor_ratio: float = 0.4        # Hmin = ratio * log(num_classes)
    kv_compatibility_prior_path: str = ""      # Path to W0 prior matrix (empty = none)
    kv_curriculum_exclude_epochs: int = 2      # Epochs to exclude Viparyaya/Nidra
    kv_curriculum_ramp_epochs: int = 1         # Epochs to ramp inclusion
    kv_teacher_mode: str = "heuristic"         # "uniform" or "heuristic" teacher labels
    kv_collapse_check_interval: int = 100      # Steps between collapse checks
    kv_kl_clamp_max: float = 100.0             # Clamp individual KL values

    # ==========================================================================
    # STATE-CONDITIONAL LOGIT SCALE ("Confidence Knob") + ENTROPY BAND
    # Reference: symbolu/training/confidence_scaler.py
    # ==========================================================================
    # Per-token learned logit scale s_t with optional Vritti risk gating.
    # Eliminates calibration artifacts, stabilises training, improves reliability.
    # Does NOT modify transformer blocks -- only emission path + loss + logging.
    enable_confidence_scaler: bool = False       # Master toggle
    confidence_s_min: float = 0.3                # Min scale (prevents over-sharpening)
    confidence_s_max: float = 10.0               # Max scale (prevents trivial uncertainty)
    confidence_epsilon: float = 1e-4             # Numerical floor for softplus
    confidence_entropy_band_min: float = 0.10    # H_min = ratio * log(V)
    confidence_entropy_band_max: float = 0.35    # H_max = ratio * log(V)
    confidence_lambda_band: float = 1e-3         # Weight for entropy band loss
    confidence_lambda_scale: float = 1e-4        # Weight for log(s) regulariser
    # Risk gating via Vritti head (Viparyaya + Nidra → increase uncertainty)
    confidence_enable_risk_gating: bool = False   # Enable Vritti risk gating
    confidence_alpha_risk: float = 0.5            # Risk scaling coefficient
    confidence_vritti_kl_weight: float = 0.1      # Weight for Vritti KL aux loss

    # ==========================================================================
    # Conscious Generation (Phase 1+): Token-Side Ontological Foundation
    # Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix D
    # ==========================================================================
    enable_conscious_generation: bool = False      # Master toggle for conscious generation modules
    token_ontology_dim: int = 32                   # Must match SOVEREIGN_STATE_DIM
    ontology_cache_refresh_interval: int = 100     # Steps between O_tok cache refresh
    lambda_ont: float = 0.0                        # Ontological structure loss weight (0 = disabled)
    ontology_loss_type: str = "contrastive"        # "contrastive" (InfoNCE) or "prototype"
    ontology_loss_temperature: float = 0.1         # Temperature for contrastive loss
    ontology_scorer_use_low_rank: bool = True      # Low-rank M_ont = A B^T (saves params)
    ontology_scorer_rank: int = 8                  # Rank for low-rank factorization

    # Phase 2: Primitive Scoring Heads
    plausibility_token_dim: int = 16               # d_j for plausibility token representations
    jepa_token_dim: int = None                     # Backward-compatible alias for plausibility_token_dim
    csr_token_dim: int = 16                        # d_c for CSR token representations
    primitive_shortlist_k: int = 128               # Top-K base logits for primitive evaluation
    use_low_rank_primitives: bool = True           # Low-rank M_f = A_f B_f^T (reduces params)
    primitive_rank: int = 8                        # Rank for low-rank factorization
    use_shared_token_basis: bool = False           # Share intermediate projection across primitives

    # Phase 3: Governance Integration
    lambda_kosha_routing: float = 0.0              # Kosha routing loss weight
    lambda_bliss_token: float = 0.0                # Bliss token-level coherence loss weight
    lambda_plausibility_token: float = 0.0          # Plausibility token-level loss
    lambda_jepa_token: float = None                # Backward-compatible alias for lambda_plausibility_token
    lambda_csr_token: float = 0.0                  # CSR token-level resonance loss (see also: enable_csr for spatial path)
    lambda_vritti_token: float = 0.0               # Vritti token-level cognitive mode loss
    lambda_guna_token: float = 0.0                 # Guna token-level energetic loss

    # Ontology → Vritti directional prior (cognitive axis alignment)
    # Adds a KL regularizer encouraging the learned Vritti context profile
    # to be consistent with an ontology-derived prior via R[v,a] transpose.
    # Training-only: no inference-path impact. Set to 0.0 to disable.
    lambda_vritti_ontology_prior: float = 0.0      # Weight for ontology→vritti KL prior
    vritti_ontology_prior_alpha: float = 0.1       # Mixing strength of prior (capped at 0.4)
    vritti_ontology_prior_tau: float = 1.0         # Temperature for prior softmax
    bliss_lambda_B: float = 1.0                    # λ_B temperature for Bliss gate
    kosha_routing_init: str = "uniform"            # "uniform" or "base_dominant"

    # Phase 3+: Governance plane (Pranamaya) — Domain × Kosha routing
    kosha_num_domains: int = 8                     # Number of domain categories
    kosha_interaction_rank: int = 16               # Low-rank dim for k ⊗ d interaction
    kosha_initial_policy_scale: float = 0.10       # Starting policy blend strength (ramps up)
    kosha_bliss_scale: float = 2.0                 # How much BLISSFUL Kosha increases gate lambda
    kosha_use_kosha: bool = True                   # Ablation: explicit Kosha slice contribution
    kosha_use_domain: bool = True                  # Ablation: domain contribution
    kosha_use_interaction: bool = True             # Ablation: k ⊗ d interaction term
    kosha_use_dynamic_bliss: bool = True           # Ablation: BLISSFUL Kosha → gate lambda
    enable_governance_probes: bool = False          # Enable sensitivity probes (extra router passes)

    # Phase 4: Field-Integrated Generation
    use_field_integrated_softmax: bool = False      # Replace standard logits with Z*(w) for L_LM
    field_softmax_temperature: float = 1.0          # Temperature scaling for integrated softmax
    use_agreement_energy: bool = False              # Enable pairwise agreement term A_t(w)
    agreement_energy_weight: float = 0.1            # β weight for agreement-energy synergy term

    # Phase 5: Curriculum, Validation, and Ablation
    enable_cg_curriculum: bool = False              # Enable staged curriculum (A→D) for conscious gen
    cg_curriculum_ramp_mode: str = "cosine"         # Lambda ramp mode: linear, cosine, step
    cg_curriculum_ppl_var_threshold: float = 0.5    # Max PPL variance for stage transition
    cg_curriculum_stability_window: int = 5         # Eval steps for PPL stability check
    cg_curriculum_stage_proportions: str = "0.30,0.20,0.25,0.25"  # Stage A,B,C,D proportions
    enable_cg_diagnostics: bool = False             # Enable governance diagnostics tracking

    # Phase 5+: Embedding Diagnostics — verify CG auxiliaries change representations
    enable_embedding_diagnostics: bool = False      # Master toggle for embedding drift tracking
    embedding_diag_interval: int = 200              # Steps between diagnostic snapshots
    embedding_diag_vocab_sample: int = 1000         # Vocab tokens to sample for drift metrics
    embedding_diag_neighbors: int = 20              # Nearest neighbors to track for stability
    embedding_diag_no_samples: bool = False         # Disable vocab sampling (only grad norms + adapter gate)
    embedding_diag_start_step: int = 0              # Delay diagnostics until this step

    # ==========================================================================
    # Experiential Controller: 12-parameter resistance-driven plasticity
    # Reference: experiential/minimal_controller.py
    # Training-time only — does NOT modify inference path.
    # ==========================================================================
    cg_sample_every: int = 0                         # CG progress snapshot interval (0 = disabled, independent of sample_every)

    enable_experiential_controller: bool = False     # Master toggle
    experiential_d_model: int = 128                  # Internal d_model for controller
    experiential_num_regions: int = 12               # Number of plasticity regions
    experiential_lambda_temporal: float = 0.5        # Temporal consistency weight
    experiential_lambda_coherence: float = 0.3       # Cross-signal coherence weight
    experiential_lambda_latent: float = 0.1          # Latent alignment weight
    experiential_k_r: float = 2.0                    # Resistance openness scaling
    experiential_k_m: float = 2.0                    # Misalignment suppression scaling
    experiential_b_p: float = -1.0                   # Bias floor for plasticity gate
    experiential_G_base: float = 3.0                 # Base gain
    experiential_G_min: float = 0.1                  # Minimum gain
    experiential_G_max: float = 5.0                  # Maximum gain
    experiential_k_dv: float = 1.0                   # Gradient variance damping
    experiential_k_dc: float = 0.5                   # Coherence instability damping
    experiential_alpha_base: float = 0.01            # Identity EMA base rate
    experiential_replay_interval: int = 100          # Medium loop: replay every N steps
    experiential_consolidation_interval: int = 1000  # Slow loop: identity consolidation every N steps
    experiential_log_interval: int = 100             # Diagnostics logging interval
    experiential_loss_weight: float = 0.01           # Weight for experiential loss contribution (0.1 saturates clamp)
    experiential_warmup_steps: int = 200             # Ramp loss weight from 0 to full over N steps
    experiential_loss_clamp: float = 20.0            # Max experiential loss contribution (raised: 0.01 × 20 = 0.2 max)

    # Factual Eval — verify CG primitives distinguish facts from hallucinations
    enable_factual_eval: bool = False               # Master toggle for CG factual evaluation
    factual_eval_interval: int = 500                # Steps between eval runs
    factual_eval_probes: int = 50                   # Number of fact/hallucination pairs per eval
    factual_eval_start_step: int = 0                # Delay eval until this training step

    # ==========================================================================
    # Appendix F Stage 0: Binding Cache + CTM+ Observation Tracers
    # Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, F.2.7–F.2.9
    # ==========================================================================
    enable_binding_cache_tracer: bool = False       # Enable Binding Cache observation (Stage 0)
    binding_cache_top_k: int = 64                   # Simulated Top-K for cache hit rate estimation
    binding_cache_confidence_threshold: float = 0.7 # Proposal confidence threshold for logging
    enable_ctm_plus_tracer: bool = False            # Enable CTM+ offload observation (Stage 0)
    ctm_plus_gpu_budget: int = 24                   # Simulated GPU layer budget for tier placement
    ctm_plus_num_layers: int = 32                   # Number of backbone layers to track
    generation_trace_output: str = "generation_trace.json"  # Path for Stage 0 trace output
    generation_trace_interval: int = 500            # Steps between trace snapshots

    # ==========================================================================
    # Appendix F Stage 8: Perspective Synthesizer (Representation Conditioning)
    # Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md §F.12
    # ==========================================================================
    enable_perspective_synthesizer: bool = False  # Master toggle for Stage 8
    perspective_d_synthesis: int = 64             # Synthesis MLP hidden dimension
    perspective_gate_init: float = 0.0            # Gate init (0.0 for safe cold start)
    perspective_log_interpretive: bool = True     # Log full InterpretiveState per token

    # ==========================================================================
    # Stage 9: Post-Training Attention Mechanism Ablation Audit (F.14)
    # Toggle flags for independently disabling attention modulation mechanisms.
    # These flags should be set BEFORE training so they are available at ablation
    # time, but only activated post-convergence for the actual ablation audit.
    # ==========================================================================
    ablation_disable_phase_sync: bool = False       # Disable U3/U4 phase synchronization
    ablation_disable_vritti: bool = False            # Disable Vritti cognitive gating
    ablation_disable_guna_bias: bool = False         # Disable Guna top-down bias
    ablation_enable_dual_channel_intent: bool = False  # Enable dual-channel intent (off by default)
    ablation_log_mechanism_strength_every: int = 0  # Log mechanism strength every N steps (0=off)
    run_ablation_audit: bool = False                 # Run full ablation matrix (requires --resume)

    # ==========================================================================
    # Mistral CG Wrapper (--model_type mistral_cg)
    # Pre-trained Mistral backbone + trainable CG modules
    # ==========================================================================
    mistral_model_name: str = "mistralai/Mistral-7B-v0.3"  # HuggingFace model ID
    mistral_quantize: str = "none"                          # "none", "4bit", "8bit"
    mistral_device_map: str = "auto"                        # Device placement strategy
    mistral_trust_remote_code: bool = False                 # Trust remote code in model repo
    mistral_phase_adapter_hidden: int = 1024                # Hidden dim for phase adapter MLP

    # ==========================================================================
    # Mistral Hybrid Wrapper (--model_type mistral_hybrid)
    # Frozen Mistral backbone + trainable Phase attention layers (no CG)
    # ==========================================================================
    mistral_hybrid_num_phase_layers: int = 4                # Number of Phase layers on top of Mistral
    mistral_hybrid_local_layers: int = 2                    # First N Phase layers use local attention only
    phase_ppl_delta_interval: int = 500                     # Steps between Phase PPL delta measurement (0=off)

    # ==========================================================================
    # Knowledge Distillation from Mistral Teacher
    # Use frozen Mistral as teacher for hybrid / ontological_hybrid students
    # ==========================================================================
    distill_from_mistral: bool = False                      # Enable distillation mode
    distill_temperature: float = 2.0                        # Softmax temperature (higher = softer targets)
    distill_alpha: float = 0.5                              # Weight for KD loss (1.0 = pure KD, 0.0 = pure CE)
    distill_warmup_steps: int = 0                           # Steps before KD kicks in (CE-only warmup)

    # =========================================================================
    # V20: AUTO-SCALING SLOT MEMORY
    # =========================================================================
    # When slot_auto_scale=True, call compute_slot_scaling() after parsing args
    # to derive slot hyperparameters from model size and training budget.
    #
    # Scaling principles:
    #   1. Slot count scales with model capacity: more parameters → more slots
    #      to store distinct associative patterns.
    #   2. Step-based schedules normalize to training budget: a 50K-step run
    #      and a 200K-step run should spend the same *fraction* of training
    #      in bootstrap vs refinement phases.
    #   3. Write temperature scales with slot count (already in V19).
    #   4. Gate targets and coherence floors are dimensionless — keep fixed.
    # =========================================================================

    def __post_init__(self):
        """Resolve backward-compatible aliases."""
        # jepa_token_dim → plausibility_token_dim
        if self.jepa_token_dim is not None:
            self.plausibility_token_dim = self.jepa_token_dim
        self.jepa_token_dim = self.plausibility_token_dim

        # lambda_jepa_token → lambda_plausibility_token
        if self.lambda_jepa_token is not None:
            self.lambda_plausibility_token = self.lambda_jepa_token
        self.lambda_jepa_token = self.lambda_plausibility_token

    def compute_slot_scaling(self) -> dict:
        """
        V20: Derive slot memory hyperparameters from model size and training budget.

        Call this after config is fully initialized (model_size resolved, max_steps set).
        Returns a dict of the computed values for logging. Mutates self in-place.

        Parameters that scale with MODEL SIZE (embed_dim, num_layers):
          num_global_tokens    = embed_dim // 8, rounded to power of 2
          write_top_k          = max(4, num_slots // 16)
          global_write_start_layer = int(num_layers * 0.67)  (late-layer writes)
          global_read_interval = max(1, num_layers // 4)     (maintain ~4 reads)
          local_layers         = max(2, num_layers // 6)     (early local-only)
          slot_memory_lr_scale = 0.1 + embed_dim / 5120      (grows with model)

        Parameters that scale with TRAINING BUDGET (max_steps):
          plasticity_warmup    = max_steps * 0.10
          plasticity_cooldown  = max_steps * 0.20
          leak_curriculum      = max_steps * 0.08
          read_gate_freeze     = max_steps * 0.01
          coherence_decay      = max_steps * 0.08
          router_noise_warmup  = max_steps * 0.20
          sample_every         = max_steps * 0.025
          phase_health_interval= max_steps * 0.025

        Parameters that scale with CONTEXT LENGTH (max_seq_len):
          window_size              = min(512, max_seq_len // 4)
          window_size_high_ppl     = window_size // 2
          window_size_low_ppl      = window_size
          ppl_high_threshold       = 500 * (max_seq_len / 1024)  (longer ctx → higher PPL)
          ppl_low_threshold        = 50 * (max_seq_len / 1024)

        Parameters that DON'T scale (dimensionless ratios / thresholds):
          slots_write_lr, slot_prediction_loss_weight, slot_coherence_floor,
          adaptive_max_lr_relative, alpha_phase_ppl_low,
          learning_rate, adaptive_lr_min, batch_size,
          gradient_accumulation, log_every
        """
        if not self.slot_auto_scale:
            return {}

        preset = MODEL_PRESETS.get(self.model_size, MODEL_PRESETS["small"])
        embed_dim = self.n_embd if self.n_embd is not None else preset["embed_dim"]
        num_layers = self.n_layer if self.n_layer is not None else preset["num_layers"]
        total_steps = self.max_steps

        # =================================================================
        # MODEL-SIZE-DEPENDENT PARAMETERS
        # =================================================================

        # --- Slot count: scales with embed_dim ---
        # Each slot key lives in embed_dim space. More dimensions →
        # easier to pack orthogonal keys → more slots without interference.
        # embed_dim//8 gives: 32(tiny), 64(small), 96(medium), 128(large).
        num_slots = embed_dim // 8
        # Round to nearest power of 2 for hardware efficiency
        num_slots = max(16, 2 ** round(math.log2(num_slots)))
        self.num_global_tokens = num_slots

        # --- Write top-k: scales with slot count ---
        # Each token writes to top-k slots. More slots → slightly more writes
        # per token to maintain coverage, but keep it sparse.
        # 4 for 64 slots, 8 for 128, 16 for 256.
        write_top_k = max(4, num_slots // 16)

        # --- Write start layer: late-layer writes ---
        # Slot memory works best with well-processed representations, not
        # raw embeddings from early layers. Writing from ~67% through the
        # network (e.g., layer 8/12 for medium) ensures slots receive
        # semantically rich features.
        # Reference: user validated 8/12 for medium = 0.67 ratio.
        write_start_layer = max(1, int(num_layers * 0.67))
        self.global_write_start_layer = write_start_layer

        # --- Read interval: maintain ~4 reads across the network ---
        # For 12 layers with interval=3, that's 4 read opportunities.
        # Scaling to more layers should maintain similar read density.
        # Reference: user validated interval=3 for 12 layers.
        read_interval = max(1, num_layers // 4)
        self.global_read_interval = read_interval

        # --- Local layers: early local-only layers ---
        # First N layers use local attention only for fast syntactic
        # pattern learning before hybrid phase+local kicks in.
        # ~17% of layers (2/12 for medium, 3/16 for large).
        # Reference: user validated 2 for 12 layers.
        local_layers = max(2, num_layers // 6)
        self.local_layers = local_layers

        # --- LR scale: larger models need higher slot LR ---
        # Larger models have stronger backbone gradients that dominate the
        # slot parameter group. Linear scale: 0.1 + embed_dim/7680.
        # Gives: 0.13(tiny/256), 0.17(small/512), 0.20(medium/768), 0.23(large/1024).
        # Anchored at 0.2 for medium/768 (validated by user).
        slot_lr_scale = round(0.1 + embed_dim / 7680, 3)
        slot_lr_scale = max(0.1, min(0.5, slot_lr_scale))  # Clamp [0.1, 0.5]
        self.slot_memory_lr_scale = slot_lr_scale

        # =================================================================
        # TRAINING-BUDGET-DEPENDENT PARAMETERS (fractions of max_steps)
        # =================================================================

        # Plasticity schedule: bootstrap (high write_lr) for 10% of training,
        # then cool down over the next 10% to refinement write_lr.
        plasticity_warmup_end = max(500, int(total_steps * 0.10))
        plasticity_cooldown_end = max(1000, int(total_steps * 0.20))

        # Soft detach leak curriculum: reach full LM gradient by 8% of training.
        # Shorter than plasticity because gradient flow is more urgent.
        leak_curriculum_steps = max(500, int(total_steps * 0.08))

        # Read gate freeze: force gate open for 1% of training.
        # Just long enough to establish slot-backbone coupling.
        read_gate_freeze_steps = max(100, int(total_steps * 0.01))

        # Coherence floor decay: loosen bootstrap coherence over 8% of training.
        coherence_floor_decay_steps = max(500, int(total_steps * 0.08))

        # Router noise warmup: maintain diversity pressure for 20% of training.
        router_noise_warmup = max(1000, int(total_steps * 0.20))

        # Sample generation interval: ~2.5% of training → ~40 samples total.
        # Reference: user uses 500 for 20K steps = 2.5%.
        sample_every = max(50, int(total_steps * 0.025))
        self.sample_every = sample_every

        # Phase health diagnostics interval: same cadence as sampling.
        # Reference: user uses 500 for 20K steps = 2.5%.
        phase_health_interval = max(50, int(total_steps * 0.025))

        # =================================================================
        # CONTEXT-LENGTH-DEPENDENT PARAMETERS
        # =================================================================

        ctx_len = self.max_seq_len

        # --- Window size: ~25% of context length, capped at 512 ---
        # Local attention window should cover enough context for syntactic
        # patterns without blowing up memory. 256 is right for 1024-ctx,
        # but undersized for 4096+. Cap at 512 for VRAM safety.
        # Reference: optimize_training.py uses min(512, target_context // 4).
        window_size = min(512, ctx_len // 4)
        window_size = max(64, window_size)  # Floor at 64 for very short contexts
        self.window_size = window_size

        # --- Adaptive window endpoints scale with window_size ---
        # High-PPL (early training): half the base window for fast phase learning.
        # Low-PPL (converged): full base window for richer local context.
        self.window_size_high_ppl = max(64, window_size // 2)
        self.window_size_low_ppl = window_size

        # --- PPL thresholds: scale with context length ---
        # Longer sequences produce higher perplexity (more tokens to predict).
        # Fixed thresholds (100/1000) are calibrated for ~1024 context.
        # Scale linearly: 2048-ctx sees ~2x the PPL of 1024-ctx for the same
        # model quality, so thresholds should shift proportionally.
        ctx_ratio = ctx_len / 1024.0
        self.ppl_high_threshold = round(500.0 * ctx_ratio, 1)
        self.ppl_low_threshold = round(50.0 * ctx_ratio, 1)

        # =================================================================
        # BUILD SCALING DICT
        # =================================================================
        scaling = {
            # Model-size-dependent
            "num_slots": num_slots,
            "write_top_k": write_top_k,
            "write_start_layer": write_start_layer,
            "read_interval": read_interval,
            "local_layers": local_layers,
            "slot_lr_scale": slot_lr_scale,
            # Training-budget-dependent
            "plasticity_warmup_end": plasticity_warmup_end,
            "plasticity_cooldown_end": plasticity_cooldown_end,
            "leak_curriculum_steps": leak_curriculum_steps,
            "read_gate_freeze_steps": read_gate_freeze_steps,
            "coherence_floor_decay_steps": coherence_floor_decay_steps,
            "router_noise_warmup": router_noise_warmup,
            "sample_every": sample_every,
            "phase_health_interval": phase_health_interval,
            # Context-length-dependent
            "window_size": window_size,
            "window_size_high_ppl": self.window_size_high_ppl,
            "window_size_low_ppl": self.window_size_low_ppl,
            "ppl_high_threshold": self.ppl_high_threshold,
            "ppl_low_threshold": self.ppl_low_threshold,
            # Context (for diagnostics)
            "embed_dim": embed_dim,
            "num_layers": num_layers,
            "total_steps": total_steps,
            "context_length": ctx_len,
        }
        # Attach to config so training loop and SlotMemoryGCT can access it
        self._slot_scaling = scaling
        return scaling


# Model size presets
MODEL_PRESETS = {
    "tiny": {
        "embed_dim": 256,
        "num_layers": 6,
        "num_heads": 4,
        "ff_dim": 1024,
    },
    "small": {
        "embed_dim": 512,
        "num_layers": 8,
        "num_heads": 8,
        "ff_dim": 2048,
    },
    "medium": {
        "embed_dim": 768,
        "num_layers": 12,
        "num_heads": 12,
        "ff_dim": 3072,
    },
    "large": {
        "embed_dim": 1024,
        "num_layers": 16,
        "num_heads": 16,
        "ff_dim": 4096,
    },
}


# =============================================================================
# V9.8.0: SRK BACKWARD COMPATIBILITY BRIDGE
# =============================================================================
# Maps legacy ontological intervention flags to unified SRK configuration.
# Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md Appendix G
#
# Option (A) Implementation: Legacy flags become aliases that auto-enable SRK
# and configure the appropriate SRK component.
# =============================================================================

def build_srk_config_from_legacy(args, config: 'UnifiedTrainingConfig') -> Tuple[Optional['SRKConfig'], List[str]]:
    """
    Build SRK configuration from legacy CLI flags with deprecation warnings.

    This function implements the backward compatibility bridge described in
    SOVEREIGN_REASONING_KERNEL_DESIGN.md Section 27 and Appendix G.

    Legacy Flag → SRK Mapping:
    - --enable_onto_bridge → srk.enable_dna_bridge (Layer 4)
    - --enable_csr → srk.csr_alignment_layer (Layer 7)
    - --enable_kosha_steering → srk.enable_witness (Layer 9)
    - --enable_toroidal_bridge → srk.karma_decay (O12→O1)
    - --enable_sovereign_loss → srk_loss.* (B1/U2/S8)

    Args:
        args: Parsed CLI arguments
        config: UnifiedTrainingConfig (will be mutated)

    Returns:
        Tuple of (SRKConfig or None, list of deprecation warnings)
    """
    warnings = []

    # Check if SRK is available
    if not SRK_AVAILABLE:
        if config.enable_srk:
            warnings.append("WARNING: --enable_srk specified but SRK module not available. Ignoring.")
        return None, warnings

    # Auto-detect if legacy flags should trigger SRK
    legacy_triggers = {
        'enable_onto_bridge': getattr(args, 'enable_onto_bridge', False),
        'enable_csr': getattr(args, 'enable_csr', False) and not getattr(args, 'disable_csr', False),
        'enable_kosha_steering': getattr(args, 'enable_kosha_steering', False),
        'enable_toroidal_bridge': getattr(args, 'enable_toroidal_bridge', False),
        'enable_sovereign_loss': getattr(args, 'enable_sovereign_loss', False),
    }

    # Count active legacy flags
    active_legacy = [k for k, v in legacy_triggers.items() if v]

    # If --enable_srk is explicitly set, use it directly
    if config.enable_srk:
        srk_config = SRKConfig(
            state_dim=SOVEREIGN_STATE_DIM,
            hidden_dim=config.srk_hidden_dim,
            num_heads=MODEL_PRESETS.get(config.model_size, {}).get('num_heads', 12),
            dna_bridge_layer=config.srk_dna_bridge_layer,
            csr_alignment_layer=config.srk_csr_alignment_layer,
            witness_layer=config.srk_witness_layer,
            synthesis_layer=config.srk_synthesis_layer,
            enable_dna_bridge=config.srk_enable_dna_bridge,
            enable_witness=config.srk_enable_witness,
            enable_synthesis=config.srk_enable_synthesis,
            enable_imr=config.srk_enable_imr,
            isomorphism_threshold=config.srk_isomorphism_threshold,
            karma_decay=config.srk_karma_decay,
            enable_mauna=config.srk_enable_mauna,
            mauna_confidence_threshold=config.srk_mauna_confidence_threshold,
            mauna_consistency_threshold=config.srk_mauna_consistency_threshold,
        )
        return srk_config, warnings

    # If legacy flags are active but --enable_srk not set, print migration warnings
    if active_legacy:
        warnings.append("=" * 70)
        warnings.append("⚠️  LEGACY FLAG MIGRATION NOTICE (V9.8.0)")
        warnings.append("=" * 70)
        warnings.append("The following legacy flags are deprecated and map to SRK components:")
        warnings.append("")

        # Build SRK config from legacy flags
        srk_config = SRKConfig(
            state_dim=SOVEREIGN_STATE_DIM,
            hidden_dim=config.srk_hidden_dim,
            num_heads=MODEL_PRESETS.get(config.model_size, {}).get('num_heads', 12),
        )

        # --enable_onto_bridge → SRK Layer 4 (DNA Bridge)
        if legacy_triggers['enable_onto_bridge']:
            warnings.append(f"  --enable_onto_bridge → SRK Layer {config.onto_bridge_layer} (DNA Bridge)")
            warnings.append(f"    Use: --enable_srk --srk_dna_bridge_layer={config.onto_bridge_layer}")
            srk_config.enable_dna_bridge = True
            srk_config.dna_bridge_layer = config.onto_bridge_layer
            config.enable_srk = True

        # --enable_csr → SRK Layer 7 (CSR Alignment / Phase Hook)
        if legacy_triggers['enable_csr']:
            warnings.append(f"  --enable_csr → SRK Layer {config.csr_alignment_layer} (Phase Extraction Hook)")
            warnings.append(f"    Use: --enable_srk --srk_csr_alignment_layer={config.csr_alignment_layer}")
            srk_config.csr_alignment_layer = config.csr_alignment_layer
            config.enable_srk = True

        # --enable_kosha_steering → SRK Layer 9 (Witness Arbitrator)
        if legacy_triggers['enable_kosha_steering']:
            warnings.append(f"  --enable_kosha_steering → SRK Layer {config.kosha_steering_layer} (Witness Arbitrator)")
            warnings.append(f"    Use: --enable_srk --srk_witness_layer={config.kosha_steering_layer}")
            srk_config.enable_witness = True
            srk_config.witness_layer = config.kosha_steering_layer
            config.enable_srk = True

        # --enable_toroidal_bridge → SRK karma_decay (O12→O1)
        if legacy_triggers['enable_toroidal_bridge']:
            warnings.append(f"  --enable_toroidal_bridge → SRK O12→O1 Karma Loop")
            warnings.append(f"    Use: --enable_srk --srk_karma_decay={config.srk_karma_decay}")
            srk_config.karma_decay = config.srk_karma_decay
            config.enable_srk = True

        # --enable_sovereign_loss → SRK Loss (B1/U2/S8)
        if legacy_triggers['enable_sovereign_loss']:
            warnings.append(f"  --enable_sovereign_loss → SRK Loss Functions (B1/U2/S8)")
            warnings.append(f"    Use: --enable_srk (loss is automatically enabled with SRK)")
            config.enable_srk = True

        warnings.append("")
        warnings.append("To suppress this notice, use --enable_srk explicitly.")
        warnings.append("Legacy flags will be removed in V10.0.0.")
        warnings.append("=" * 70)

        return srk_config, warnings

    # No SRK or legacy flags active
    return None, warnings


def build_srk_loss_config(config: 'UnifiedTrainingConfig') -> Optional['SRKLossConfig']:
    """Build SRK Loss configuration from UnifiedTrainingConfig."""
    if not SRK_AVAILABLE or not config.enable_srk:
        return None

    return SRKLossConfig(
        lambda_f=config.srk_lambda_f,
        lambda_b=config.srk_lambda_b,
        lambda_c=config.srk_lambda_c,
        lambda_coherence=config.srk_lambda_coherence,
        lambda_entropy=config.srk_lambda_entropy,
        lambda_task=config.srk_lambda_task,
        enable_nidra_penalty=config.srk_enable_nidra_penalty,
        nidra_penalty_weight=config.srk_nidra_penalty_weight,
    )

