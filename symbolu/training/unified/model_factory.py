"""
Model factory for creating different model architectures.

Supports ontological, phase, hybrid, gen2, standard, ontological_hybrid,
binding_cache, and ontological_binding_cache model types.

Extracted from train_unified_llm.py
"""

from typing import Optional, Dict, Any

import torch
import torch.nn as nn

from symbolu.training.unified.config import UnifiedTrainingConfig, MODEL_PRESETS

from symbolu.phase_transformer import (
    PhaseTransformer,
    HybridPhaseTransformer,
    StandardTransformer,
    OntologicalHybridTransformer,
    BindingCacheTransformer,
    OntologicalBindingCacheTransformer,
    SOVEREIGN_STATE_DIM,
    PHASE_STATE_DIM,
)

# Import ontological models (optional)
try:
    from symbolu.ontological.symbolu12_bhava import (
        SymbolU12LLMWithBhava,
        SymbolU12BhavaConfig,
    )
    ONTOLOGICAL_AVAILABLE = True
except ImportError:
    ONTOLOGICAL_AVAILABLE = False

# Import Gen 2 models (optional)
try:
    from symbolu.ontological.symbolu12_gen2 import (
        SymbolU12Gen2,
        SymbolU12Gen2Config,
    )
    GEN2_AVAILABLE = True
except ImportError:
    GEN2_AVAILABLE = False


def create_model(config: UnifiedTrainingConfig, device: torch.device) -> nn.Module:
    """Create model based on configuration."""
    preset = MODEL_PRESETS[config.model_size]

    # Apply architecture overrides if provided
    embed_dim = config.n_embd if config.n_embd is not None else preset["embed_dim"]
    num_layers = config.n_layer if config.n_layer is not None else preset["num_layers"]
    num_heads = config.n_head if config.n_head is not None else preset["num_heads"]
    ff_dim = int(embed_dim * 4)  # Standard 4x expansion for FFN
    n_kv_heads = config.n_kv_heads if config.n_kv_heads is not None else None  # None = use num_heads

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

    return model.to(device)
