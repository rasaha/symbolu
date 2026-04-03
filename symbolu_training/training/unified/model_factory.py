"""
Model factory for creating different model architectures.

Supports ontological, phase, hybrid, gen2, standard, gct, ontological_hybrid,
binding_cache, ontological_binding_cache, mistral_cg, and mistral_hybrid model types.

Extracted from train_unified_llm.py
"""

from typing import Optional, Dict, List, Any

import torch
import torch.nn as nn

from symbolu_training.training.unified.config import UnifiedTrainingConfig, MODEL_PRESETS

from symbolu_core.phase_transformer import (
    PhaseTransformer,
    HybridPhaseTransformer,
    StandardTransformer,
    GCTTransformer,
    OntologicalHybridTransformer,
    BindingCacheTransformer,
    OntologicalBindingCacheTransformer,
    SOVEREIGN_STATE_DIM,
    PHASE_STATE_DIM,
)

# Import ontological models (optional)
try:
    from symbolu_core.ontological.symbolu12_bhava import (
        SymbolU12LLMWithBhava,
        SymbolU12BhavaConfig,
    )
    ONTOLOGICAL_AVAILABLE = True
except ImportError:
    ONTOLOGICAL_AVAILABLE = False

# Import Gen 2 models (optional)
try:
    from symbolu_core.ontological.symbolu12_gen2 import (
        SymbolU12Gen2,
        SymbolU12Gen2Config,
    )
    GEN2_AVAILABLE = True
except ImportError:
    GEN2_AVAILABLE = False

# Import Mistral CG wrapper (optional)
try:
    from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper
    MISTRAL_CG_AVAILABLE = True
except ImportError:
    MISTRAL_CG_AVAILABLE = False

# Import Mistral Hybrid wrapper (optional)
try:
    from symbolu_training.training.unified.mistral_hybrid_wrapper import MistralHybridWrapper
    MISTRAL_HYBRID_AVAILABLE = True
except ImportError:
    MISTRAL_HYBRID_AVAILABLE = False

# Import Conscious Generation modules (optional)
try:
    from symbolu_training.training.conscious_generation.token_ontology import TokenOntologyProjector
    from symbolu_training.training.conscious_generation.token_cache import TokenPrimitiveCache
    from symbolu_training.training.conscious_generation.primitives.ontology_scorer import (
        OntologyCompatibilityScorer,
    )
    from symbolu_training.training.conscious_generation.losses.ontological_structure import (
        OntologicalStructureLoss,
    )
    from symbolu_training.training.conscious_generation.primitives import (
        BaseScorer,
        PlausibilityTokenScorer,
        CSRTokenScorer,
        VrittiTokenScorer,
        GunaTokenScorer,
        TokenEvaluationTensor,
    )
    from symbolu_training.training.conscious_generation.governance.kosha_router import (
        KoshaPrimitiveRouter,
    )
    from symbolu_training.training.conscious_generation.governance.bliss_gate import (
        BlissTokenGate,
    )
    from symbolu_training.training.conscious_generation.integration.token_scorer import (
        IntegratedTokenScorer,
    )
    from symbolu_training.training.conscious_generation.losses.kosha_routing import (
        KoshaRoutingLoss,
    )
    from symbolu_training.training.conscious_generation.losses.primitive_auxiliary import (
        PrimitiveAuxiliaryLosses,
    )
    from symbolu_training.training.conscious_generation.losses.bliss_coherence import (
        BlissCoherenceLoss,
    )
    from symbolu_training.training.conscious_generation.integration.field_softmax import (
        FieldIntegratedSoftmax,
    )
    from symbolu_training.training.conscious_generation.integration.two_stage_generator import (
        TwoStageGenerator,
    )
    CONSCIOUS_GENERATION_AVAILABLE = True
except ImportError:
    CONSCIOUS_GENERATION_AVAILABLE = False


def create_model(config: UnifiedTrainingConfig, device: torch.device) -> nn.Module:
    """Create model based on configuration."""
    preset = MODEL_PRESETS[config.model_size]

    # Apply architecture overrides if provided
    embed_dim = config.n_embd if config.n_embd is not None else preset["embed_dim"]
    num_layers = config.n_layer if config.n_layer is not None else preset["num_layers"]
    num_heads = config.n_head if config.n_head is not None else preset["num_heads"]
    ff_dim = int(embed_dim * 4)  # Standard 4x expansion for FFN
    n_kv_heads = config.n_kv_heads if config.n_kv_heads is not None else None  # None = use num_heads

    # V20: Compute auto-scaling for slot memory if enabled
    slot_scaling = None
    if config.slot_auto_scale and config.global_tokens_enabled:
        slot_scaling = config.compute_slot_scaling()
        print(f"  Slot Auto-Scale: ENABLED (embed_dim={slot_scaling['embed_dim']}, "
              f"num_layers={slot_scaling['num_layers']}, steps={slot_scaling['total_steps']})")
        print(f"    Model-size derived:")
        print(f"      num_slots={slot_scaling['num_slots']}, write_top_k={slot_scaling['write_top_k']}, "
              f"local_layers={slot_scaling['local_layers']}")
        print(f"      write_start_layer={slot_scaling['write_start_layer']}, "
              f"read_interval={slot_scaling['read_interval']}, "
              f"slot_lr_scale={slot_scaling['slot_lr_scale']}")
        print(f"    Budget derived (from {slot_scaling['total_steps']} steps):")
        print(f"      plasticity_warmup={slot_scaling['plasticity_warmup_end']}, "
              f"cooldown={slot_scaling['plasticity_cooldown_end']}")
        print(f"      leak_curriculum={slot_scaling['leak_curriculum_steps']}, "
              f"read_gate_freeze={slot_scaling['read_gate_freeze_steps']}")
        print(f"      sample_every={slot_scaling['sample_every']}, "
              f"phase_health={slot_scaling['phase_health_interval']}")

    # Validate embed_dim / num_heads divisibility
    if embed_dim % num_heads != 0:
        raise ValueError(
            f"n_embd ({embed_dim}) must be evenly divisible by n_head ({num_heads}). "
            f"Got head_dim = {embed_dim}/{num_heads} = {embed_dim/num_heads:.2f} (not integer). "
            f"Valid n_head values for n_embd={embed_dim}: "
            f"{[h for h in [8, 12, 16, 20, 32, 64] if embed_dim % h == 0]}"
        )
    if n_kv_heads is not None and num_heads % n_kv_heads != 0:
        raise ValueError(
            f"n_head ({num_heads}) must be evenly divisible by n_kv_heads ({n_kv_heads})."
        )

    # Print architecture configuration
    print(f"\n{'='*80}")
    if config.model_type == "mistral_cg":
        # For mistral_cg, the preset dims are irrelevant — show backbone info instead
        backbone_name = getattr(config, 'mistral_model_name', 'mistralai/Mistral-7B-v0.3')
        print(f"Model Architecture: {config.model_type} (frozen backbone: {backbone_name})")
        print(f"{'='*80}")
        print(f"  NOTE: Architecture determined by backbone, not preset ({config.model_size})")
        print(f"  See backbone load output below for actual dimensions")
    else:
        print(f"Model Architecture: {config.model_type} ({config.model_size} preset)")
        print(f"{'='*80}")
        if config.n_embd is not None or config.n_layer is not None or config.n_head is not None:
            print(f"  ⚙️  Architecture Overrides Active:")
        print(f"  Embedding Dimension:  {embed_dim}" + (" (override)" if config.n_embd is not None else ""))
        print(f"  Number of Layers:     {num_layers}" + (" (override)" if config.n_layer is not None else ""))
        print(f"  Number of Heads:      {num_heads}" + (" (override)" if config.n_head is not None else ""))
        print(f"  FFN Dimension:        {ff_dim}")
        if n_kv_heads is not None:
            print(f"  KV Heads (GQA):       {n_kv_heads} (override)")
        print(f"  Dropout:              {config.dropout}")
        print(f"  Attention Dropout:    {config.attention_dropout}")
    print(f"{'='*80}\n")

    if config.model_type == "ontological":
        if not ONTOLOGICAL_AVAILABLE:
            raise ImportError("Ontological models not available. Check imports.")

        # Create SymbolU12 with Bhava
        bhava_config = SymbolU12BhavaConfig(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            max_seq_len=config.max_seq_len,
            num_heads=num_heads,
            bhava_embed_dim=config.bhava_embed_dim,
            num_drishti_heads=config.num_drishti_heads,
        )

        model = SymbolU12LLMWithBhava(bhava_config)

        # Enable gradient checkpointing if requested
        if config.gradient_checkpointing:
            # Apply gradient checkpointing to transformer layers
            for name, module in model.named_modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True

    elif config.model_type == "phase":
        # V9.6.0: Untie embeddings when CSR is enabled to prevent vocabulary corruption
        tie_emb = not config.untie_embeddings
        model = PhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
            tie_embeddings=tie_emb,
            cosine_mode=config.cosine_mode,  # V9.6.12: Pass cosine mode
            decay_gamma=config.decay_gamma,  # V9.6.13: Pass decay factor
        )
        print(f"  Phase Cosine Mode: {config.cosine_mode}")  # V9.6.12: Log mode
        print(f"  Phase Decay Gamma: {config.decay_gamma}")  # V9.6.13: Log decay

    elif config.model_type == "hybrid":
        # V9.6.0: Untie embeddings when CSR is enabled to prevent vocabulary corruption
        tie_emb = not config.untie_embeddings
        # V10.2.1: Determine protected_phase setting
        use_protected_phase = config.protected_phase and not config.no_protected_phase
        model = HybridPhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
            tie_embeddings=tie_emb,
            cosine_mode=config.cosine_mode,  # V9.6.12: Pass cosine mode
            decay_gamma=config.decay_gamma,  # V9.6.13: Pass decay factor
            learned_decay=config.learned_decay,  # V9.9.7: Per-head learned decay
            bounded_phase=config.bounded_phase,  # V9.9.11: Phase collapse fix 1
            zero_mean_cosine=config.zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
            dual_channel_mode=config.dual_channel_mode,  # V10.3.8: Dual-channel attention
            alignment_authority=config.alignment_authority,  # V10.3.8: Alignment authority
            protected_phase=use_protected_phase,  # V10.2.1: Protected Phase for chunking
            # V10.14: Global Tokens / Slot Memory
            global_tokens_enabled=config.global_tokens_enabled,
            num_global_tokens=config.num_global_tokens,
            global_update_mode=config.global_update_mode,
            slots_write_lr=config.slots_write_lr,
            retrieval_loss_weight=config.retrieval_loss_weight,
            global_read_interval=config.global_read_interval,
            global_write_start_layer=config.global_write_start_layer,
            slot_scaling=slot_scaling,  # V20: Auto-scaling overrides
        )
        print(f"  Hybrid Cosine Mode: {config.cosine_mode}")  # V9.6.12: Log mode
        print(f"  Hybrid Decay Gamma: {config.decay_gamma}")  # V9.6.13: Log decay
        if config.learned_decay:
            print(f"  Learned Decay: ENABLED (per-head attention span)")  # V9.9.7
        if config.bounded_phase:
            print(f"  Bounded Phase: ENABLED (π*sin() bounds φ to [-π, π])")  # V9.9.11
        if config.zero_mean_cosine:
            print(f"  Zero-Mean Cosine: ENABLED (forces selectivity)")  # V9.9.11
        if config.dual_channel_mode:
            print(f"  Dual-Channel Mode: ENABLED (α={config.alignment_authority})")  # V10.3.8
        if config.global_tokens_enabled:
            print(f"  Global Tokens: ENABLED ({config.num_global_tokens} slots, mode={config.global_update_mode})")
            print(f"  Slot Write LR: {config.slots_write_lr}, Retrieval Loss Weight: {config.retrieval_loss_weight}")
            if config.slot_prediction_loss_weight > 0:
                print(f"  Slot Prediction Loss: ENABLED (weight={config.slot_prediction_loss_weight})")
            if config.global_read_interval > 1:
                print(f"  Slot Read Interval: every {config.global_read_interval} layers")
            if config.global_write_start_layer > 0:
                print(f"  Slot Write Start Layer: {config.global_write_start_layer}")
        # V10.2.1: Log chunking settings
        if config.enable_chunking:
            print(f"  Chunking: ENABLED (chunk_size={config.chunk_size})")
            print(f"  Protected Phase: {'ENABLED' if use_protected_phase else 'DISABLED (legacy parallel)'}")

    elif config.model_type == "gen2":
        if not GEN2_AVAILABLE:
            raise ImportError("Gen 2 models not available. Check imports.")

        # Determine num_layers: use 12 for 9:3 split, otherwise preset
        # 9:3 split requires exactly (authority_layers + sensory_layers) = 12 layers
        if config.use_9_3_split:
            gen2_num_layers = config.authority_layers + config.sensory_layers
        else:
            gen2_num_layers = num_layers

        # Create SymbolU12 Gen 2 (Hierarchical Complex Bhava)
        gen2_config = SymbolU12Gen2Config(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_heads=num_heads,
            num_layers=gen2_num_layers,
            complex_dim=64,  # Complex embedding dimension
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            ffn_mult=ff_dim / embed_dim,
        )

        model = SymbolU12Gen2(gen2_config)
        print(f"\n  [Gen 2] Hierarchical Complex Bhava enabled")
        print(f"  [Gen 2] Complex dim: {gen2_config.complex_dim}")
        print(f"  [Gen 2] Num layers: {gen2_num_layers} (9:3 split: {config.use_9_3_split})")
        print(f"  [Gen 2] Hierarchy: 3-tier phase rotation")

    elif config.model_type == "standard":
        # V9.6.9: Standard O(n²) transformer baseline for comparison
        # Uses StandardTransformer from phase_transformer.py
        tie_emb = not config.untie_embeddings
        model = StandardTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            tie_embeddings=tie_emb,
        )
        print(f"\n  [Standard] O(n²) baseline transformer for comparison")

    elif config.model_type == "gct":
        # Gated Coherence Transformer: pre-softmax coherence routing
        # Routes heads between full O(n²) and local-window O(n*w) attention
        # based on temporal stability signals (output + residual deltas).
        # FlashAttention-compatible on the full path.
        tie_emb = not config.untie_embeddings
        model = GCTTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            tie_embeddings=tie_emb,
            gct_window_size=config.gct_window_size,
            gct_coherence_gamma=config.gct_coherence_gamma,
            gct_coherence_delta=config.gct_coherence_delta,
            gct_ema_decay=config.gct_ema_decay,
            gct_num_bands=config.gct_num_bands,
            gct_alpha_sharpness=config.gct_alpha_sharpness,
            gct_hard_route_threshold=config.gct_hard_route_threshold,
            gct_use_hard_routing=False,  # Training uses soft blend
            gct_kappa=config.gct_kappa,
            gct_tau_ladder=config.gct_tau_ladder,
            gct_warmup_steps=config.gct_warmup_steps,
            gct_anneal_steps=config.gct_anneal_steps,
        )
        print(f"\n  [GCT] Gated Coherence Transformer")
        print(f"    Attention: Full O(n^2) + Local-Window O(n*{config.gct_window_size})")
        print(f"    Coherence: output_delta(gamma={config.gct_coherence_gamma}) * residual_delta(delta={config.gct_coherence_delta})")
        print(f"    Bands: {config.gct_num_bands} (equal head partition)")
        print(f"    Lambda_ladder: kappa={config.gct_kappa}, tau={config.gct_tau_ladder}")
        print(f"    Schedule: warmup={config.gct_warmup_steps}, anneal={config.gct_anneal_steps}")
        print(f"    Routing: soft blend (training), hard theta={config.gct_hard_route_threshold} (inference)")

    elif config.model_type == "ontological_hybrid":
        # V9.6.14: Two-Tier AGI Architecture (Ontological State Delta + Hybrid)
        # Ontological: Slow semantic state tracking (System 2)
        # Hybrid: Fast token generation with intent-modulated attention (System 1)
        tie_emb = not config.untie_embeddings
        model = OntologicalHybridTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            n_kv_heads=n_kv_heads,  # V9.8.7: GQA support
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
            tie_embeddings=tie_emb,
            cosine_mode=config.cosine_mode,
            decay_gamma=config.decay_gamma,
            learned_decay=config.learned_decay,  # V9.9.7: Per-head learned decay
            bounded_phase=config.bounded_phase,  # V9.9.11: Phase collapse fix 1
            zero_mean_cosine=config.zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
            dual_channel_mode=config.dual_channel_mode,  # V10.3.8: Dual-channel attention
            alignment_authority=config.alignment_authority,  # V10.3.8: Alignment authority
            state_dim=config.state_dim,
            project_per_head_dim=config.project_per_head_dim,
            # V10.14: Global Tokens / Slot Memory
            global_tokens_enabled=config.global_tokens_enabled,
            num_global_tokens=config.num_global_tokens,
            global_update_mode=config.global_update_mode,
            slots_write_lr=config.slots_write_lr,
            retrieval_loss_weight=config.retrieval_loss_weight,
            global_read_interval=config.global_read_interval,
            global_write_start_layer=config.global_write_start_layer,
            slot_scaling=slot_scaling,  # V20: Auto-scaling overrides
        )
        print(f"\n  [Ontological Hybrid] Two-Tier AGI Architecture enabled (V11.0.0: Separated Planes)")
        print(f"    Full Sovereign State: {config.state_dim}D (diagnostics/control/learning)")
        print(f"    Phase Rotation Input: {PHASE_STATE_DIM}D (Bhava-only → ΔBhava → θ → attention)")
        if config.state_dim == SOVEREIGN_STATE_DIM:
            print(f"      Phase:   [0:12]  12 Bhavas → phase rotation (identity)")
            print(f"      Control: [12:17] 5 Sheaths | [17:22] 5 States | [22:28] 6 Qualia")
            print(f"      Learn:   [28:32] Reserved/JEPA (training-time only)")
        print(f"    Project Per Head Dim: {config.project_per_head_dim}")
        print(f"    Hybrid Cosine Mode: {config.cosine_mode}")
        print(f"    Hybrid Decay Gamma: {config.decay_gamma}")
        if config.learned_decay:
            print(f"    Learned Decay: ENABLED (per-head attention span)")  # V9.9.7
        if config.bounded_phase:
            print(f"    Bounded Phase: ENABLED (π*sin() bounds φ to [-π, π])")  # V9.9.11
        if config.zero_mean_cosine:
            print(f"    Zero-Mean Cosine: ENABLED (forces selectivity)")  # V9.9.11
        if config.dual_channel_mode:
            print(f"    Dual-Channel Mode: ENABLED (α={config.alignment_authority})")  # V10.3.8
        print(f"    Initial State: O12_ABS (Absolute) + Material (Physicality) - Grounded Awareness")

    elif config.model_type == "binding_cache":
        # V10.0: Binding Cache architecture (validated by diagnostic probes)
        # Protected Phase + Top-K Query - prevents Phase decorativeness
        # Reference: train_hard_probes.py --protected-phase showed -50% ablation drop
        tie_emb = not config.untie_embeddings

        # Determine if cache should be used
        use_cache = not config.no_binding_cache
        top_k = config.binding_cache_top_k if use_cache else 0

        model = BindingCacheTransformer(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            decay_gamma=config.decay_gamma,
            learned_decay=config.learned_decay,
            bounded_phase=True,  # Always enabled (mandatory from probes)
            top_k=top_k,
            use_cache=use_cache,
            tie_embeddings=tie_emb,
        )
        print(f"\n  [Binding Cache V10.0] Protected Phase + Top-K Query")
        print(f"    Architecture: Phase (O(n) cumsum) → Quad (O(nk) query)")
        print(f"    Validated by diagnostic probes: -50% Phase ablation drop")
        print(f"    Top-K cache size: {top_k} (use_cache: {use_cache})")
        print(f"    Bounded Phase: ENABLED (mandatory)")
        print(f"    Decay Gamma: {config.decay_gamma}")
        if config.learned_decay:
            print(f"    Learned Decay: ENABLED (per-head attention span)")

    elif config.model_type == "ontological_binding_cache":
        # V10.0: AGI Architecture - Binding Cache + 32D Sovereign State
        # Combines validated Protected Phase with ontological reasoning
        tie_emb = not config.untie_embeddings

        # Determine if cache should be used
        use_cache = not config.no_binding_cache
        top_k = config.binding_cache_top_k if use_cache else 0

        model = OntologicalBindingCacheTransformer(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            decay_gamma=config.decay_gamma,
            learned_decay=config.learned_decay,
            top_k=top_k,
            use_cache=use_cache,
            state_dim=config.state_dim,
            project_per_head_dim=config.project_per_head_dim,
            tie_embeddings=tie_emb,
            # V10.0: Binding Annotation (CSR/Kosha/SRK as SELECTORS, not modifiers)
            use_binding_annotator=config.use_binding_annotator,
            use_csr_annotation=config.use_csr_annotation,
            use_kosha_annotation=config.use_kosha_annotation,
            use_srk_annotation=config.use_srk_annotation,
        )
        print(f"\n  [Ontological Binding Cache V11.0.0] AGI Architecture (Separated Planes)")
        print(f"    Combines: Protected Phase + Top-K Query + Separated Sovereign State")
        print(f"    Architecture: ΔBhava[12D] → Phase rotation → Memory binding → Query")
        print(f"    Full Sovereign State: {config.state_dim}D (diagnostics/control/learning)")
        print(f"    Phase Rotation Input: {PHASE_STATE_DIM}D (Bhava-only → ΔBhava → θ → attention)")
        if config.state_dim == SOVEREIGN_STATE_DIM:
            print(f"      Phase:   [0:12]  12 Bhavas → phase rotation (identity)")
            print(f"      Control: [12:17] 5 Sheaths | [17:22] 5 States | [22:28] 6 Qualia → Annotator/CTM+")
            print(f"      Learn:   [28:32] Reserved/JEPA (training-time only)")
        print(f"    Top-K cache size: {top_k} (use_cache: {use_cache})")
        print(f"    Bounded Phase: ENABLED (mandatory from probes)")
        print(f"    Decay Gamma: {config.decay_gamma}")
        if config.learned_decay:
            print(f"    Learned Decay: ENABLED (per-head attention span)")
        print(f"    Project Per Head Dim: {config.project_per_head_dim}")
        # V10.0: Binding Annotation status
        if config.use_binding_annotator:
            print(f"    Binding Annotator: ENABLED (semantics → Top-K selection)")
            print(f"      CSR: {'ON' if config.use_csr_annotation else 'OFF'} | "
                  f"Kosha: {'ON' if config.use_kosha_annotation else 'OFF'} | "
                  f"SRK: {'ON' if config.use_srk_annotation else 'OFF'}")
            print(f"      Clean separation: Attention=physics, Annotator=semantics")
        else:
            print(f"    Binding Annotator: DISABLED (pure attention, no semantic selection)")

    elif config.model_type == "mistral_hybrid":
        # Frozen Mistral backbone + trainable Phase attention layers (no CG)
        if not MISTRAL_HYBRID_AVAILABLE:
            raise ImportError(
                "MistralHybridWrapper not available. Check: pip install transformers"
            )
        quantize = config.mistral_quantize if config.mistral_quantize != "none" else None
        model = MistralHybridWrapper(
            model_name=config.mistral_model_name,
            quantize=quantize,
            num_phase_layers=config.mistral_hybrid_num_phase_layers,
            local_layers=config.mistral_hybrid_local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
            decay_gamma=config.decay_gamma,
            learned_decay=config.learned_decay,
            protected_phase=config.protected_phase and not config.no_protected_phase,
            phase_adapter_hidden=config.mistral_phase_adapter_hidden,
            device_map=config.mistral_device_map,
            trust_remote_code=config.mistral_trust_remote_code,
        )
        # Override dims to match backbone
        embed_dim = model.mistral_hidden_dim
        num_heads = model.num_heads
        config.vocab_size = model.vocab_size
        print(f"\n  [Mistral Hybrid] Frozen Backbone + Trainable Phase Layers (no CG)")
        print(f"    Model: {config.mistral_model_name}")
        print(f"    Quantization: {config.mistral_quantize}")
        print(f"    Backbone hidden_dim: {embed_dim}")
        print(f"    Phase layers: {config.mistral_hybrid_num_phase_layers} "
              f"({config.mistral_hybrid_local_layers} local + "
              f"{config.mistral_hybrid_num_phase_layers - config.mistral_hybrid_local_layers} hybrid)")
        print(f"    Phase adapter hidden: {config.mistral_phase_adapter_hidden}")
        model.print_trainable_summary()

    elif config.model_type == "mistral_cg":
        # Frozen Mistral backbone + trainable CG adapter modules
        if not MISTRAL_CG_AVAILABLE:
            raise ImportError(
                "MistralCGWrapper not available. Check: pip install transformers"
            )
        quantize = config.mistral_quantize if config.mistral_quantize != "none" else None
        model = MistralCGWrapper(
            model_name=config.mistral_model_name,
            quantize=quantize,
            state_dim=config.state_dim,
            project_per_head_dim=config.project_per_head_dim,
            phase_adapter_hidden=config.mistral_phase_adapter_hidden,
            device_map=config.mistral_device_map,
            trust_remote_code=config.mistral_trust_remote_code,
        )
        # Override dims for CG module creation below
        embed_dim = model.mistral_hidden_dim
        num_heads = model.num_heads
        # Override vocab_size to match Mistral's tokenizer
        config.vocab_size = model.vocab_size
        print(f"\n  [Mistral CG] Frozen Backbone + Trainable CG Adapter")
        print(f"    Model: {config.mistral_model_name}")
        print(f"    Quantization: {config.mistral_quantize}")
        print(f"    Backbone hidden_dim: {embed_dim}")
        print(f"    State dim: {config.state_dim}D Sovereign State")
        print(f"    Phase adapter hidden: {config.mistral_phase_adapter_hidden}")
        model.print_trainable_summary()

    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    # Enable gradient checkpointing after model creation
    # V9.5.2 Metabolic Tuning: Use non-reentrant checkpointing for better memory efficiency
    if config.gradient_checkpointing:
        if hasattr(model, 'gradient_checkpointing_enable'):
            # Try HuggingFace-style API first, fall back to simple call
            try:
                model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
                print(f"  [Metabolic] Gradient checkpointing enabled (non-reentrant mode)")
            except TypeError:
                # Model has the method but doesn't accept kwargs
                model.gradient_checkpointing_enable()
                print(f"  [Metabolic] Gradient checkpointing enabled")
        else:
            # Manual flag-based checkpointing
            for module in model.modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True
                # Set use_reentrant=False for torch.utils.checkpoint compatibility
                if hasattr(module, 'use_reentrant'):
                    module.use_reentrant = False
            print(f"  [Metabolic] Gradient checkpointing enabled (flag-based)")

        if config.checkpoint_offload_cpu:
            print(f"  [Metabolic] CPU activation offloading requested (requires custom forward)")

    # =========================================================================
    # Conscious Generation: Phase 1 — Token-Side Ontological Foundation
    # Instantiate TokenOntologyProjector, TokenPrimitiveCache, OntologyScorer,
    # and OntologicalStructureLoss when enabled for ontological_hybrid.
    # =========================================================================
    conscious_gen_modules = None
    if config.enable_conscious_generation:
        if not CONSCIOUS_GENERATION_AVAILABLE:
            raise ImportError(
                "Conscious Generation modules not available. "
                "Check symbolu/training/conscious_generation/ imports."
            )
        if config.model_type not in ("ontological_hybrid", "ontological_binding_cache", "mistral_cg"):
            print(
                f"  [Conscious Gen] WARNING: enable_conscious_generation=True but "
                f"model_type={config.model_type}. Conscious generation is designed "
                f"for ontological_hybrid. Proceeding anyway."
            )

        token_projector = TokenOntologyProjector(
            embed_dim=embed_dim,
            state_dim=config.token_ontology_dim,
        )

        # Single cache with Phase 1 + Phase 2 buffer dimensions
        token_cache = TokenPrimitiveCache(
            projector=token_projector,
            vocab_size=config.vocab_size,
            state_dim=config.token_ontology_dim,
            refresh_interval=config.ontology_cache_refresh_interval,
            jepa_dim=config.plausibility_token_dim,
            csr_dim=config.csr_token_dim,
        )

        ontology_scorer = OntologyCompatibilityScorer(
            state_dim=config.token_ontology_dim,
            use_low_rank=config.ontology_scorer_use_low_rank,
            rank=config.ontology_scorer_rank,
        )

        ontology_loss = OntologicalStructureLoss(
            state_dim=config.token_ontology_dim,
            loss_type=config.ontology_loss_type,
            temperature=config.ontology_loss_temperature,
        ) if config.lambda_ont > 0 else None

        # Phase 2: Primitive Scoring Heads
        base_scorer = BaseScorer()

        plausibility_scorer = PlausibilityTokenScorer(
            embed_dim=embed_dim,
            state_dim=config.token_ontology_dim,
            jepa_dim=config.plausibility_token_dim,
            use_low_rank=config.use_low_rank_primitives,
            rank=config.primitive_rank,
        )

        csr_scorer = CSRTokenScorer(
            embed_dim=embed_dim,
            state_dim=config.token_ontology_dim,
            csr_dim=config.csr_token_dim,
            use_low_rank=config.use_low_rank_primitives,
            rank=config.primitive_rank,
        )

        vritti_scorer = VrittiTokenScorer(
            embed_dim=embed_dim,
            state_dim=config.token_ontology_dim,
        )

        guna_scorer = GunaTokenScorer(
            embed_dim=embed_dim,
            state_dim=config.token_ontology_dim,
        )

        token_eval_tensor = TokenEvaluationTensor(
            base_scorer=base_scorer,
            ontology_scorer=ontology_scorer,
            jepa_scorer=plausibility_scorer,
            csr_scorer=csr_scorer,
            vritti_scorer=vritti_scorer,
            guna_scorer=guna_scorer,
            shortlist_k=config.primitive_shortlist_k,
        )

        # Register Phase 2 scorers with cache for refresh
        token_cache.set_scorers(
            jepa_scorer=plausibility_scorer,
            csr_scorer=csr_scorer,
            vritti_scorer=vritti_scorer,
            guna_scorer=guna_scorer,
        )

        conscious_gen_modules = {
            "token_projector": token_projector,
            "token_cache": token_cache,
            "ontology_scorer": ontology_scorer,
            "base_scorer": base_scorer,
            "plausibility_scorer": plausibility_scorer,
            "csr_scorer": csr_scorer,
            "vritti_scorer": vritti_scorer,
            "guna_scorer": guna_scorer,
            "token_eval_tensor": token_eval_tensor,
        }

        # Attach to model as a ModuleDict so parameters are tracked
        model.conscious_gen = nn.ModuleDict({
            "token_projector": token_projector,
            "token_cache": token_cache,
            "ontology_scorer": ontology_scorer,
            "base_scorer": base_scorer,
            "plausibility_scorer": plausibility_scorer,
            "csr_scorer": csr_scorer,
            "vritti_scorer": vritti_scorer,
            "guna_scorer": guna_scorer,
            "token_eval_tensor": token_eval_tensor,
        })
        if ontology_loss is not None:
            model.conscious_gen["ontology_loss"] = ontology_loss

        print(f"\n  [Conscious Gen Phase 1] Token-Side Ontological Foundation")
        print(f"    TokenOntologyProjector: {embed_dim}D -> {config.token_ontology_dim}D")
        print(f"    TokenPrimitiveCache: V={config.vocab_size}, refresh every {config.ontology_cache_refresh_interval} steps")
        print(f"    OntologyScorer: {'low-rank r=' + str(config.ontology_scorer_rank) if config.ontology_scorer_use_low_rank else 'full bilinear'}")
        if config.lambda_ont > 0:
            print(f"    OntologicalStructureLoss: type={config.ontology_loss_type}, lambda={config.lambda_ont}, tau={config.ontology_loss_temperature}")
        else:
            print(f"    OntologicalStructureLoss: DISABLED (lambda_ont=0)")

        print(f"  [Conscious Gen Phase 2] Primitive Scoring Heads")
        print(f"    PlausibilityTokenScorer: d_j={config.plausibility_token_dim}, {'low-rank r=' + str(config.primitive_rank) if config.use_low_rank_primitives else 'full bilinear'}")
        print(f"    CSRTokenScorer: d_c={config.csr_token_dim}, {'low-rank r=' + str(config.primitive_rank) if config.use_low_rank_primitives else 'full bilinear'}")
        print(f"    VrittiTokenScorer: 5 classes (dot-product)")
        print(f"    GunaTokenScorer: 3 classes (bilinear G)")
        print(f"    TokenEvaluationTensor: K={config.primitive_shortlist_k}, 6 primitives")

        # Phase 3: Governance Integration (Pranamaya plane — Domain × Kosha)
        kosha_router = KoshaPrimitiveRouter(
            embed_dim=embed_dim,
            state_dim=config.token_ontology_dim,
            num_domains=getattr(config, 'kosha_num_domains', 8),
            rank=getattr(config, 'kosha_interaction_rank', 16),
            init_mode=config.kosha_routing_init,
            initial_policy_scale=getattr(config, 'kosha_initial_policy_scale', 0.10),
            use_kosha=getattr(config, 'kosha_use_kosha', True),
            use_domain=getattr(config, 'kosha_use_domain', True),
            use_interaction=getattr(config, 'kosha_use_interaction', True),
        )

        bliss_gate = BlissTokenGate(
            lambda_B=config.bliss_lambda_B,
            bliss_scale=getattr(config, 'kosha_bliss_scale', 2.0),
            use_dynamic_bliss=getattr(config, 'kosha_use_dynamic_bliss', True),
        )

        integrated_scorer = IntegratedTokenScorer(
            kosha_router=kosha_router,
            bliss_gate=bliss_gate,
        )

        model.conscious_gen["kosha_router"] = kosha_router
        model.conscious_gen["bliss_gate"] = bliss_gate
        model.conscious_gen["integrated_scorer"] = integrated_scorer

        # Phase 3 losses: instantiate when lambda > 0 OR when curriculum is enabled
        # (curriculum starts lambdas at 0 and ramps them up later)
        _cg_curriculum = getattr(config, 'enable_cg_curriculum', False)
        _any_prim_loss = (_cg_curriculum or config.lambda_plausibility_token > 0
                         or config.lambda_csr_token > 0
                         or config.lambda_vritti_token > 0
                         or config.lambda_guna_token > 0)
        if _any_prim_loss:
            prim_aux_losses = PrimitiveAuxiliaryLosses()
            model.conscious_gen["primitive_aux_losses"] = prim_aux_losses

        if _cg_curriculum or config.lambda_kosha_routing > 0:
            kosha_routing_loss = KoshaRoutingLoss()
            model.conscious_gen["kosha_routing_loss"] = kosha_routing_loss

        if _cg_curriculum or config.lambda_bliss_token > 0:
            bliss_coherence_loss = BlissCoherenceLoss()
            model.conscious_gen["bliss_coherence_loss"] = bliss_coherence_loss

        print(f"  [Conscious Gen Phase 3] Governance Integration")
        print(f"    KoshaPrimitiveRouter: init={config.kosha_routing_init}")
        print(f"    BlissTokenGate: lambda_B={config.bliss_lambda_B}")
        _p3_losses = []
        if config.lambda_kosha_routing > 0:
            _p3_losses.append(f"L_kosha={config.lambda_kosha_routing}")
        if config.lambda_bliss_token > 0:
            _p3_losses.append(f"L_bliss={config.lambda_bliss_token}")
        if config.lambda_plausibility_token > 0:
            _p3_losses.append(f"L_plausibility={config.lambda_plausibility_token}")
        if config.lambda_csr_token > 0:
            _p3_losses.append(f"L_csr={config.lambda_csr_token}")
        if config.lambda_vritti_token > 0:
            _p3_losses.append(f"L_vritti={config.lambda_vritti_token}")
        if config.lambda_guna_token > 0:
            _p3_losses.append(f"L_guna={config.lambda_guna_token}")
        if _p3_losses:
            print(f"    Losses: {', '.join(_p3_losses)}")
        else:
            print(f"    Losses: ALL DISABLED (all lambda=0)")

        # Phase 4: Field-Integrated Generation
        # Also create when curriculum is enabled (Stage D will activate it)
        if config.use_field_integrated_softmax or _cg_curriculum:
            field_softmax = FieldIntegratedSoftmax(
                vocab_size=config.vocab_size,
                temperature=config.field_softmax_temperature,
                use_agreement_energy=config.use_agreement_energy,
                agreement_energy_weight=config.agreement_energy_weight,
            )
            two_stage_gen = TwoStageGenerator(
                token_eval_tensor=model.conscious_gen["token_eval_tensor"],
                integrated_scorer=integrated_scorer,
                field_softmax=field_softmax,
                shortlist_k=config.primitive_shortlist_k,
            )
            model.conscious_gen["field_softmax"] = field_softmax
            model.conscious_gen["two_stage_generator"] = two_stage_gen

            print(f"  [Conscious Gen Phase 4] Field-Integrated Generation")
            print(f"    FieldIntegratedSoftmax: τ={config.field_softmax_temperature}, "
                  f"agreement_energy={config.use_agreement_energy}")
            print(f"    TwoStageGenerator: K={config.primitive_shortlist_k}")

    # =========================================================================
    # Conscious Generation: Stage 8 — Perspective Synthesizer
    # Representation conditioning before lm_head via gated residual.
    # =========================================================================
    if config.enable_conscious_generation and config.enable_perspective_synthesizer:
        from agentic.inference.perspective_synthesizer import (
            PerspectiveSynthesizer, PerspectiveSynthesizerConfig,
        )
        ps_config = PerspectiveSynthesizerConfig(
            enable=True,
            d_synthesis=config.perspective_d_synthesis,
            gate_init=config.perspective_gate_init,
            log_interpretive_state=config.perspective_log_interpretive,
            onto_dim=12,
        )
        perspective_synth = PerspectiveSynthesizer(ps_config, hidden_dim=embed_dim)
        if not hasattr(model, 'conscious_gen'):
            model.conscious_gen = nn.ModuleDict()
        model.conscious_gen["perspective_synthesizer"] = perspective_synth

        # For SymbolU12LLM: attach via the model's method
        if hasattr(model, 'attach_perspective_synthesizer'):
            model.attach_perspective_synthesizer(perspective_synth)

        # For MistralCGWrapper: store reference for forward pass
        if hasattr(model, 'backbone'):
            model._perspective_synthesizer = perspective_synth

        ps_params = sum(p.numel() for p in perspective_synth.parameters())
        print(f"  [Conscious Gen Stage 8] Perspective Synthesizer")
        print(f"    d_synthesis={config.perspective_d_synthesis}, "
              f"gate_init={config.perspective_gate_init:.1f}, "
              f"interp_dim={perspective_synth.interp_dim}, "
              f"params={ps_params/1e3:.1f}K")

    # For mistral_cg with device_map="auto", backbone handles its own placement;
    # only move trainable adapter layers. For all other models, move to device.
    if config.model_type == "mistral_cg":
        # Move only trainable CG adapter layers to the right device
        model.state_projector.to(device)
        model.intent_projector.to(device)
        model.phase_adapter.to(device)
        model.adapter_gate.data = model.adapter_gate.data.to(device)
        if hasattr(model, 'conscious_gen'):
            model.conscious_gen.to(device)
        return model
    return model.to(device)


class PerLayerPhaseController:
    """
    V9.9.1: Manages per-layer phase weights for fine-grained control over
    the Phase/Sensory split during Inverted Curriculum Evolution.

    Instead of a global alpha_phase applied to all layers, this controller
    maintains individual weights for each layer, enabling:
    1. Soft layer transitions (gradual 0→1 ramp)
    2. Per-layer decay schedules
    3. Inverted curriculum where Sensory→Authority transitions happen one layer at a time

    The weight for each layer controls the blend:
        output = (1 - alpha) * quadratic_attention + alpha * phase_attention
        - alpha = 0.0: Pure Sensory (Quadratic attention)
        - alpha = 1.0: Pure Authority (Phase attention)
        - 0 < alpha < 1: Hybrid blend

    Usage:
        controller = PerLayerPhaseController(num_layers=12)
        controller.set_weights([0.0] * 12)  # Start all Sensory

        # In training loop:
        controller.update(step)
        controller.apply_to_model(model)
    """

    def __init__(
        self,
        num_layers: int = 12,
        initial_weights: Optional[List[float]] = None,
        local_layers: int = 4,  # Layers 0 to local_layers-1 are LocalAttention (no phase weight)
    ):
        """
        Initialize per-layer phase controller.

        Args:
            num_layers: Total number of layers in the model
            initial_weights: Initial phase weights for each layer (0.0 = Sensory, 1.0 = Authority)
                            If None, defaults to [0.0] * num_layers (all Sensory)
            local_layers: Number of early layers that use LocalAttention only (no phase component)
        """
        self.num_layers = num_layers
        self.local_layers = local_layers

        # Initialize weights
        if initial_weights is not None:
            if len(initial_weights) != num_layers:
                raise ValueError(f"initial_weights must have {num_layers} elements, got {len(initial_weights)}")
            self.weights = list(initial_weights)
        else:
            # Default: all Sensory (alpha_phase = 0.0)
            self.weights = [0.0] * num_layers

        # Transition tracking for soft layer transitions
        self.transitions = {}  # layer_idx -> {start_step, end_step, start_val, end_val}
        self.transition_history = []  # Log of completed transitions

        print(f"\n  🎛️ [PER-LAYER PHASE] Controller initialized:")
        print(f"      Total layers: {num_layers}")
        print(f"      Local layers: 0-{local_layers-1} (no phase component)")
        print(f"      Hybrid layers: {local_layers}-{num_layers-1} (per-layer phase weights)")
        print(f"      Initial weights: {self._format_weights()}")

    def _format_weights(self) -> str:
        """Format weights for display, showing only hybrid layers."""
        hybrid_weights = self.weights[self.local_layers:]
        return "[" + ", ".join(f"{w:.2f}" for w in hybrid_weights) + "]"

    def get_weight(self, layer_idx: int) -> float:
        """Get the current phase weight for a specific layer."""
        if layer_idx < 0 or layer_idx >= self.num_layers:
            return 0.0
        return self.weights[layer_idx]

    def set_weight(self, layer_idx: int, weight: float):
        """Set the phase weight for a specific layer."""
        if 0 <= layer_idx < self.num_layers:
            self.weights[layer_idx] = max(0.0, min(1.0, weight))

    def set_weights(self, weights: List[float]):
        """Set all phase weights at once."""
        if len(weights) != self.num_layers:
            raise ValueError(f"weights must have {self.num_layers} elements, got {len(weights)}")
        self.weights = [max(0.0, min(1.0, w)) for w in weights]

    def start_transition(
        self,
        layer_idx: int,
        target_weight: float,
        duration_steps: int,
        current_step: int,
    ):
        """
        Start a soft transition for a specific layer.

        The weight will linearly interpolate from current value to target
        over duration_steps training steps.

        Args:
            layer_idx: Which layer to transition
            target_weight: Target phase weight (0.0 = Sensory, 1.0 = Authority)
            duration_steps: Number of steps for the transition
            current_step: Current training step
        """
        if layer_idx < self.local_layers:
            print(f"  ⚠️ [PER-LAYER PHASE] Layer {layer_idx} is LocalAttention, no phase to transition")
            return

        current_weight = self.weights[layer_idx]
        self.transitions[layer_idx] = {
            'start_step': current_step,
            'end_step': current_step + duration_steps,
            'start_val': current_weight,
            'end_val': target_weight,
        }
        direction = "→Authority" if target_weight > current_weight else "→Sensory"
        print(f"  🔄 [PER-LAYER PHASE] Layer {layer_idx} transition: {current_weight:.2f} → {target_weight:.2f} ({direction}) over {duration_steps} steps")

    def update(self, current_step: int) -> Dict[str, any]:
        """
        Update all active transitions based on current step.

        Returns dict with:
            - 'weights': Current per-layer weights
            - 'active_transitions': Number of layers currently transitioning
            - 'completed': List of layer indices that completed this step
        """
        completed = []

        for layer_idx, trans in list(self.transitions.items()):
            start_step = trans['start_step']
            end_step = trans['end_step']
            start_val = trans['start_val']
            end_val = trans['end_val']

            if current_step >= end_step:
                # Transition complete
                self.weights[layer_idx] = end_val
                completed.append(layer_idx)
                self.transition_history.append({
                    'layer_idx': layer_idx,
                    'completed_step': current_step,
                    'final_weight': end_val,
                })
                del self.transitions[layer_idx]
                print(f"  ✓ [PER-LAYER PHASE] Layer {layer_idx} transition complete: α={end_val:.2f}")
            else:
                # Interpolate
                progress = (current_step - start_step) / (end_step - start_step)
                self.weights[layer_idx] = start_val + progress * (end_val - start_val)

        return {
            'weights': self.weights.copy(),
            'active_transitions': len(self.transitions),
            'completed': completed,
        }

    def apply_to_model(self, model: nn.Module):
        """
        Apply current per-layer weights to the model's HybridAttentionLayer modules.

        This updates each layer's alpha_phase parameter based on its layer_idx.
        """
        applied_count = 0
        for module in model.modules():
            if hasattr(module, 'alpha_phase') and hasattr(module, 'layer_idx'):
                layer_idx = module.layer_idx
                if 0 <= layer_idx < self.num_layers:
                    weight = self.weights[layer_idx]
                    module.alpha_phase.data.fill_(weight)
                    if hasattr(module, 'alpha_local'):
                        module.alpha_local.data.fill_(1.0 - weight)
                    applied_count += 1
        if applied_count > 0:
            print(f"      Applied per-layer weights to {applied_count} HybridAttentionLayer modules")

    def get_status(self) -> Dict[str, any]:
        """Get current controller status for logging."""
        # Count layers by type based on current weights
        authority_count = sum(1 for w in self.weights[self.local_layers:] if w >= 0.9)
        sensory_count = sum(1 for w in self.weights[self.local_layers:] if w <= 0.1)
        transitioning_count = len(self.weights[self.local_layers:]) - authority_count - sensory_count

        return {
            'weights': self.weights.copy(),
            'local_layers': self.local_layers,
            'authority_count': authority_count,
            'sensory_count': sensory_count,
            'transitioning_count': transitioning_count,
            'active_transitions': len(self.transitions),
            'completed_transitions': len(self.transition_history),
        }

    @classmethod
    def from_config(cls, config) -> 'PerLayerPhaseController':
        """Create controller from UnifiedTrainingConfig."""
        # Parse initial weights from config string
        initial_weights = None
        if hasattr(config, 'per_layer_phase_weights') and config.per_layer_phase_weights:
            try:
                initial_weights = [float(w.strip()) for w in config.per_layer_phase_weights.split(',')]
            except ValueError:
                print(f"  ⚠️ [PER-LAYER PHASE] Invalid weights string: {config.per_layer_phase_weights}")
                initial_weights = None

        return cls(
            num_layers=12,  # Fixed for Sovereign-1 architecture
            initial_weights=initial_weights,
            local_layers=config.local_layers if hasattr(config, 'local_layers') else 4,
        )



