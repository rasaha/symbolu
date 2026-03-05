"""
Main training loop for real language mode.

Contains:
    - generate_sample: Quality sample generation
    - run_quality_samples: Run quality monitoring
    - train_real_language: Main training loop with all monitoring

CLI Usage::

    # Train with all features
    python train_hard_probes.py --real-language --dataset wikitext2 \\
        --enable-srk --probe-layers --enable-kosha --enable-witness

    # Save checkpoints
    python train_hard_probes.py --real-language --checkpoint-dir ./checkpoints

    # Sample generation monitoring
    python train_hard_probes.py --real-language --sample-every 500
"""

import math
import os
import random
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from typing import List, Tuple, Dict, Optional

# =============================================================================
# SAMPLE GENERATION FOR QUALITY MONITORING
# =============================================================================
# V10.3.5: Generate text samples every N steps to monitor quality

SAMPLE_PROMPTS = (
    "The",                                          # Simple completion
    "In the beginning",                             # Narrative
    "The cat sat on",                               # Simple syntax
    "Scientists have discovered that",              # Factual
    "Once upon a time, there was a",               # Story
)


def generate_sample(
    model: nn.Module,
    tokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 64,
    temperature: float = 0.9,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.15,
    autocast_dtype: Optional[torch.dtype] = None,
) -> str:
    """
    Generate text from a prompt for quality monitoring.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    """
    model.eval()

    # Encode prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

    # Generate tokens one by one
    generated = input_ids.clone()

    _use_autocast = autocast_dtype is not None and device.type == 'cuda'

    with torch.no_grad():
        for _ in range(max_new_tokens):
            # Forward pass (use autocast to match training dtype for FlashAttention)
            if _use_autocast:
                with torch.amp.autocast('cuda', dtype=autocast_dtype):
                    outputs = model(generated)
            else:
                outputs = model(generated)

            # Handle different output formats
            if isinstance(outputs, dict):
                logits = outputs.get('logits', outputs.get('output', None))
            elif isinstance(outputs, (tuple, list)):
                logits = outputs[0]
            else:
                logits = outputs

            if logits is None:
                break

            # Get next token logits
            next_logits = logits[:, -1, :].clone()

            # Apply repetition penalty
            if repetition_penalty != 1.0:
                for token_id in set(generated[0].tolist()):
                    if next_logits[0, token_id] > 0:
                        next_logits[0, token_id] /= repetition_penalty
                    else:
                        next_logits[0, token_id] *= repetition_penalty

            # Apply temperature
            next_logits = next_logits / temperature

            # Top-k filtering
            if top_k > 0:
                top_k_vals, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
                threshold = top_k_vals[0, -1]
                next_logits[next_logits < threshold] = float('-inf')

            # Top-p (nucleus) sampling
            sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
            cumsum = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

            # Remove tokens with cumulative probability above threshold
            sorted_indices_to_remove = cumsum > top_p
            sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
            sorted_indices_to_remove[:, 0] = False

            indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
            next_logits[indices_to_remove] = float('-inf')

            # Sample next token
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append to sequence
            generated = torch.cat([generated, next_token], dim=1)

            # Check for EOS
            if hasattr(tokenizer, 'eos_token_id') and next_token.item() == tokenizer.eos_token_id:
                break

    # Decode and return
    return tokenizer.decode(generated[0], skip_special_tokens=True)


def run_quality_samples(
    model: nn.Module,
    tokenizer,
    device: torch.device,
    step: int,
    prompts: tuple = SAMPLE_PROMPTS,
):
    """Generate and display quality samples."""
    print(f"\n      ╔═══════════════════════════════════════════════════════════════════╗")
    print(f"      ║  QUALITY SAMPLES @ Step {step:<6}                                 ║")
    print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

    model.eval()
    for i, prompt in enumerate(prompts):
        try:
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=64,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.15,
            )
            # Clean up for display
            generated = generated.strip().replace('\n', ' ')[:150]
            print(f"      ║  [{i+1}] Prompt: \"{prompt}\"")
            print(f"      ║      Output: \"{generated}\"")
            print(f"      ║")
        except Exception as e:
            print(f"      ║  [{i+1}] Error: {e}")
            print(f"      ║")

    print(f"      ╚═══════════════════════════════════════════════════════════════════╝")
    model.train()


def train_real_language(
    args,
    config: Config,
    curriculum: List[float],
):
    """
    Train with real language data (WikiText) and layer probing.
    """
    # V10.5.6: Check for Associative Recall mode
    use_associative_recall = getattr(args, 'associative_recall', False)
    ar_dataset = None  # For accuracy evaluation
    ar_pad_token = None  # For custom loss computation
    ar_eq_token = None  # V10.5.7: For binding slot cache pattern detection
    ar_query_token = None  # V10.5.7b: For forcing slot usage at query positions

    if use_associative_recall:
        print("\n" + "=" * 70)
        print("V10.5.6: ASSOCIATIVE RECALL MODE")
        print("=" * 70)
        print("\nThis task REQUIRES long-range memory retrieval:")
        print("  - Local attention (window=64) CANNOT solve when delay > window")
        print("  - Quad MUST retrieve from phase memory to succeed")
        print("  - If quad works → accuracy >> 0%, if broken → accuracy ≈ random")
        print()

        ar_vocab_size = getattr(args, 'ar_vocab_size', 1000)
        ar_num_pairs = getattr(args, 'ar_num_pairs', 8)
        ar_delay_min = getattr(args, 'ar_delay_min', 80)
        ar_delay_max = getattr(args, 'ar_delay_max', 150)
        ar_train_samples = getattr(args, 'ar_train_samples', 50000)
        ar_val_samples = getattr(args, 'ar_val_samples', 2000)

        print(f"  Vocabulary size: {ar_vocab_size}")
        print(f"  Key-value pairs: {ar_num_pairs}")
        print(f"  Initial delay range: [{ar_delay_min}, {ar_delay_max}] tokens")
        print(f"  Local window: {getattr(args, 'local_window_size', 64)}")
        print(f"  → Delay > window, so LOCAL CANNOT SOLVE THIS")
        print(f"  Train samples: {ar_train_samples}")
        print(f"  Val samples: {ar_val_samples}")

        # V10.5.8: Dynamic delay curriculum
        ar_dynamic_delay = getattr(args, 'ar_dynamic_delay', False)
        ar_target_delay_min = getattr(args, 'ar_target_delay_min', 120)
        ar_target_delay_max = getattr(args, 'ar_target_delay_max', 200)
        ar_curriculum_warmup = getattr(args, 'ar_curriculum_warmup', 0.3)

        if ar_dynamic_delay:
            print(f"\n  ★ DYNAMIC DELAY CURRICULUM ENABLED (V10.5.8)")
            print(f"    Initial: delay=[{ar_delay_min}, {ar_delay_max}]")
            print(f"    Target:  delay=[{ar_target_delay_min}, {ar_target_delay_max}]")
            print(f"    Warmup:  {ar_curriculum_warmup*100:.0f}% of training at initial delay")
            print(f"    Formula: delay(t) = base + (t - warmup) * (target - base) / (1 - warmup)")

        train_dataset = AssociativeRecallDataset(
            num_samples=ar_train_samples,
            num_pairs=ar_num_pairs,
            delay_min=ar_delay_min,
            delay_max=ar_delay_max,
            seq_len=args.seq_len,
            vocab_size=ar_vocab_size,
            seed=42,
            dynamic_delay=ar_dynamic_delay,  # V10.5.8
        )
        val_dataset = AssociativeRecallDataset(
            num_samples=ar_val_samples,
            num_pairs=ar_num_pairs,
            delay_min=ar_delay_min,
            delay_max=ar_delay_max,
            seq_len=args.seq_len,
            vocab_size=ar_vocab_size,
            seed=123,  # Different seed for validation
            dynamic_delay=False,  # Validation uses fixed delays for fair comparison
        )

        ar_dataset = val_dataset  # For accuracy evaluation
        ar_pad_token = train_dataset.PAD_TOKEN
        ar_eq_token = train_dataset.EQ_TOKEN  # V10.5.7: For binding slot cache
        ar_query_token = train_dataset.QUERY_TOKEN  # V10.5.7b: For forcing slot usage

        # Custom collator for associative recall
        collator = AssociativeRecallCollator(ar_pad_token)
        train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True, collate_fn=collator)
        val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False, collate_fn=collator)

        # Override vocab size for model creation
        args.lm_vocab_size = ar_vocab_size

        # V10.5.7: Print binding slots info if enabled
        binding_slots = getattr(args, 'binding_slots', 0)
        if binding_slots > 0:
            print(f"\n  ★ BINDING SLOT CACHE ENABLED (V10.5.7)")
            print(f"    Number of slots: {binding_slots}")
            print(f"    EQ_TOKEN ID: {ar_eq_token}")
            print(f"    Purpose: Explicit K-V memory separate from Phase decay")
    else:
        print("\n" + "=" * 70)
        print("REAL LANGUAGE MODE: WikiText Language Modeling")
        print("=" * 70)

        # Load dataset
        print(f"\nLoading {args.dataset} dataset...")
        train_dataset = WikiTextDataset("train", args.seq_len, args.dataset)
        val_dataset = WikiTextDataset("validation", args.seq_len, args.dataset)

        train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False)

    # Create model
    # V10.3.3: Support for Binding Cache architecture
    use_binding_cache = getattr(args, 'binding_cache', False)
    # V10.3.2: Support for Protected Phase architecture
    use_protected_phase = getattr(args, 'protected_phase', False)

    if use_binding_cache:
        # Parse binding cache ratios
        bc_phase_ratio = [float(x) for x in args.binding_cache_phase_ratio.split(",")]
        bc_local_ratio = [float(x) for x in args.binding_cache_local_ratio.split(",")]
        bc_quad_ratio = [float(x) for x in args.binding_cache_quad_ratio.split(",")]

        # Pad/truncate to match num_layers
        while len(bc_phase_ratio) < config.num_layers:
            bc_phase_ratio.append(bc_phase_ratio[-1] if bc_phase_ratio else 0.3)
        while len(bc_local_ratio) < config.num_layers:
            bc_local_ratio.append(bc_local_ratio[-1] if bc_local_ratio else 0.4)
        while len(bc_quad_ratio) < config.num_layers:
            bc_quad_ratio.append(bc_quad_ratio[-1] if bc_quad_ratio else 0.3)
        bc_phase_ratio = bc_phase_ratio[:config.num_layers]
        bc_local_ratio = bc_local_ratio[:config.num_layers]
        bc_quad_ratio = bc_quad_ratio[:config.num_layers]

        # V10.5.5: Force Quad at L0 experiment
        force_quad_l0 = getattr(args, 'force_quad_l0', False)
        if force_quad_l0:
            print(f"\n  ★ FORCE QUAD L0 EXPERIMENT (V10.5.5)")
            print(f"    Overriding ratios to test if quad CAN work:")
            # L0: Quad-only (no local)
            bc_local_ratio[0] = 0.0
            bc_quad_ratio[0] = 0.7
            bc_phase_ratio[0] = 0.3
            print(f"    L0: local=0.0, quad=0.7, phase=0.3 (QUAD MUST DO ALL WORK)")
            # L1+: Local-only (no quad)
            for i in range(1, config.num_layers):
                bc_local_ratio[i] = 0.7
                bc_quad_ratio[i] = 0.0
                bc_phase_ratio[i] = 0.3
                print(f"    L{i}: local=0.7, quad=0.0, phase=0.3 (local only)")

        print(f"\n╔═══════════════════════════════════════════════════════════════════════╗")
        print(f"║  V10.3.3: BINDING CACHE ARCHITECTURE                                  ║")
        print(f"╠═══════════════════════════════════════════════════════════════════════╣")
        print(f"║  d_model={config.d_model}, num_heads={config.num_heads}, num_layers={config.num_layers}")
        print(f"║  Three-Path Architecture (No Gradient Competition):                   ║")
        print(f"║                                                                       ║")
        print(f"║    1. LOCAL PATH  - O(n*w) Window Attention                          ║")
        print(f"║       Window size: {args.local_window_size}")
        print(f"║       Fast syntax learning, direct token-to-token                    ║")
        print(f"║                                                                       ║")
        print(f"║    2. PHASE PATH  - O(n) Memory State Accumulation                   ║")
        print(f"║       Decay gamma: {args.decay_gamma}")
        print(f"║       Binding accumulation via decayed cumsum                        ║")
        print(f"║                                                                       ║")
        print(f"║    3. QUAD PATH   - O(n*k) Top-K Cache Query                         ║")
        print(f"║       Top-K: {args.binding_cache_top_k}")
        print(f"║       Quadratic attention over cached memories                       ║")
        if args.proposal_mode:
            print(f"╠═══════════════════════════════════════════════════════════════════════╣")
            print(f"║  V10.4 PROPOSAL MODE ENABLED                                          ║")
            print(f"║    Quad returns K proposals (no softmax mixing)                       ║")
            print(f"║    Phase integrates proposals with gating                             ║")
            print(f"║    Confidence threshold: {args.confidence_threshold:.2f}                                      ║")
        if config.dual_channel_mode:
            print(f"╠═══════════════════════════════════════════════════════════════════════╣")
            print(f"║  V10.6 DUAL-CHANNEL MODE ENABLED                                      ║")
            print(f"║    JEPA/SRK intent alignment for proposal integration                 ║")
            print(f"║    s_align = cos(θ_JEPA - θ_SRK)                                      ║")
            print(f"║    output = output * clamp(1 + α * s_align, min, max)                 ║")
            print(f"║    Alignment authority (α): {config.alignment_authority:.2f}                                    ║")
            print(f"║    Clamp bounds: [{config.alignment_clamp_min:.2f}, {config.alignment_clamp_max:.2f}] (V10.6.1 stability fix)             ║")
        print(f"╠═══════════════════════════════════════════════════════════════════════╣")
        print(f"║  Per-Layer Ratios:                                                    ║")
        for i in range(config.num_layers):
            print(f"║    L{i}: Local={bc_local_ratio[i]:.2f}, Phase={bc_phase_ratio[i]:.2f}, Quad={bc_quad_ratio[i]:.2f}")
        print(f"╚═══════════════════════════════════════════════════════════════════════╝")

        # V10.5.7: Get binding slots configuration
        binding_slots = getattr(args, 'binding_slots', 0)
        binding_slot_eq_token = ar_eq_token if use_associative_recall else None
        binding_slot_query_token = ar_query_token if use_associative_recall else None  # V10.5.7b

        model = BindingCacheLMTransformer(
            vocab_size=args.lm_vocab_size,
            d_model=config.d_model,
            num_heads=config.num_heads,
            num_layers=config.num_layers,
            d_ff=config.d_ff,
            dropout=config.dropout,
            max_seq_len=args.seq_len,
            window_size=args.local_window_size,
            top_k=args.binding_cache_top_k,
            decay_gamma=args.decay_gamma,
            phase_ratios=bc_phase_ratio,
            local_ratios=bc_local_ratio,
            quad_ratios=bc_quad_ratio,
            proposal_mode=args.proposal_mode,
            confidence_threshold=args.confidence_threshold,
            # V10.5.7: Binding slot cache for explicit K-V memory
            binding_slots=binding_slots,
            binding_slot_eq_token=binding_slot_eq_token,
            binding_slot_query_token=binding_slot_query_token,  # V10.5.7b
            # V10.6: Dual-channel mode (JEPA/SRK intent alignment)
            dual_channel_mode=config.dual_channel_mode,
            alignment_authority=config.alignment_authority,
            # V10.6.1: Clamp bounds for alignment modulator
            alignment_clamp_min=config.alignment_clamp_min,
            alignment_clamp_max=config.alignment_clamp_max,
        ).to(config.device)

    elif use_protected_phase:
        print(f"\nCreating ProtectedPhaseLMTransformer (V10.3.2)...")
        print(f"  d_model={config.d_model}, num_heads={config.num_heads}, num_layers={config.num_layers}")
        print(f"  Architecture: Phase → Memory State → Quadratic Query")
        print(f"  Phase's job:  Accumulate bindings via O(n) cumsum")
        print(f"  Quad's job:   Query memory via O(n²) attention")
        print(f"  Key insight:  No gradient competition - they collaborate")

        model = ProtectedPhaseLMTransformer(
            vocab_size=args.lm_vocab_size,
            d_model=config.d_model,
            num_heads=config.num_heads,
            num_layers=config.num_layers,
            d_ff=config.d_ff,
            dropout=config.dropout,
            max_seq_len=args.seq_len,
            bounded_phase=config.bounded_phase,
        ).to(config.device)
    else:
        print(f"\nCreating HybridLMTransformer...")
        print(f"  d_model={config.d_model}, num_heads={config.num_heads}, num_layers={config.num_layers}")
        print(f"  Initial curriculum: {curriculum}")

        model = HybridLMTransformer(
            vocab_size=args.lm_vocab_size,
            d_model=config.d_model,
            num_heads=config.num_heads,
            num_layers=config.num_layers,
            d_ff=config.d_ff,
            dropout=config.dropout,
            max_seq_len=args.seq_len,
            curriculum=curriculum,
            bounded_phase=config.bounded_phase,
        ).to(config.device)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {param_count:,}")

    # V10.5: Deep Supervision initialization (Fix 1 for L0 overfitting)
    use_deep_supervision = getattr(args, 'deep_supervision', False)
    if use_deep_supervision and hasattr(model, 'init_deep_supervision'):
        deep_lambda = getattr(args, 'deep_supervision_lambda', 0.5)
        model.init_deep_supervision(lambda_decay=deep_lambda)
        print(f"\n  Deep Supervision: ENABLED (V10.5)")
        print(f"    Lambda (layer weight): {deep_lambda}")
        print(f"    Purpose: Force later layers to learn useful representations")
        print(f"    Formula: loss += λ * (i+1)/L * CE(aux_proj(h_i), targets)")
    elif use_deep_supervision:
        print(f"\n  Deep Supervision: REQUESTED but model lacks init_deep_supervision()")
        print(f"    Only supported for BindingCacheLMTransformer currently")
        use_deep_supervision = False

    # V10.5.4: Soft Routing Warmup initialization
    soft_routing_warmup = getattr(args, 'soft_routing_warmup', 0)
    soft_routing_always = getattr(args, 'soft_routing_always', False)
    if soft_routing_always or soft_routing_warmup > 0:
        if hasattr(model, 'set_soft_routing'):
            model.set_soft_routing(True)  # Start with soft routing
            print(f"\n  Soft Routing Warmup: ENABLED (V10.5.4)")
            if soft_routing_always:
                print(f"    Mode: ALWAYS (never switch to hard top-K)")
                print(f"    Complexity: O(n²) full attention")
            else:
                print(f"    Warmup steps: {soft_routing_warmup}")
                print(f"    After warmup: switch to hard top-K O(n*k)")
            print(f"    Purpose: Allow gradients to flow to quad (was 0.1% with hard top-K)")
        else:
            print(f"\n  Soft Routing Warmup: REQUESTED but model lacks set_soft_routing()")
            soft_routing_warmup = 0
            soft_routing_always = False

    # Phase-first curriculum controller (disabled for protected phase)
    pfc = None
    if args.phase_first_curriculum and not use_protected_phase:
        pfc = PhaseFirstCurriculum(
            num_layers=config.num_layers,
            alpha_high=args.alpha_phase_high,
            alpha_low=args.alpha_phase_low,
            ppl_high=args.ppl_high,
            ppl_low=args.ppl_low,
        )
        print(f"\n  Phase-First Curriculum: ENABLED")
        print(f"    alpha_high={args.alpha_phase_high}, alpha_low={args.alpha_phase_low}")
        print(f"    ppl_high={args.ppl_high}, ppl_low={args.ppl_low}")

    # ==========================================================================
    # V10.3.0: SRK PHASE LEARNING MONITORING
    # ==========================================================================
    srk_monitor = None
    if hasattr(args, 'enable_srk') and args.enable_srk:
        if not args.probe_layers:
            print("\n  ⚠️  WARNING: --enable-srk requires --probe-layers to capture layer outputs")
            print("       Enabling --probe-layers automatically.")
            args.probe_layers = True

        # Build SRK configuration
        srk_config = SRKPhaseLearningConfig(
            enable_srk=True,
            dna_bridge_layer=getattr(args, 'srk_dna_bridge_layer', 0),
            csr_alignment_layer=getattr(args, 'srk_csr_layer', 1),
            witness_layer=getattr(args, 'srk_witness_layer', 2),
            synthesis_layer=getattr(args, 'srk_synthesis_layer', 3),
            enable_dna_bridge=not getattr(args, 'srk_disable_dna_bridge', False),
            enable_phase_hook=not getattr(args, 'srk_disable_phase_hook', False),
            enable_witness=not getattr(args, 'srk_disable_witness', False),
            enable_synthesis=not getattr(args, 'srk_disable_synthesis', False),
            lambda_ontology=getattr(args, 'srk_lambda_ontology', 0.1),
            lambda_coherence=getattr(args, 'srk_lambda_coherence', 0.05),
        )

        # Validate layer indices for this model
        layer_warnings = srk_config.validate_for_model(config.num_layers)
        for warning in layer_warnings:
            print(f"  ⚠️  {warning}")

        # Create SRK monitor
        srk_monitor = SRKPhaseLearningMonitor(
            config=srk_config,
            hidden_dim=config.d_model,
            num_heads=config.num_heads,
            device=torch.device(config.device),
        )

        # V10.3.1: Create layer influence diagnostics
        srk_influence = LayerInfluenceDiagnostics(srk_config)

        print(f"\n  ╔══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.1: SRK PHASE LEARNING MONITORING ENABLED                  ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Layer Components (with Influence Diagnostics):                  ║")
        if srk_config.enable_dna_bridge:
            print(f"  ║    L{srk_config.dna_bridge_layer}: DNA Bridge (Ontology)          ACTIVE + INFLUENCE    ║")
        if srk_config.enable_phase_hook:
            print(f"  ║    L{srk_config.csr_alignment_layer}: CSR Alignment (Phase Hook)   ACTIVE + INFLUENCE    ║")
        if srk_config.enable_witness:
            print(f"  ║    L{srk_config.witness_layer}: Witness Arbitrator         ACTIVE + INFLUENCE    ║")
        if srk_config.enable_synthesis:
            print(f"  ║    L{srk_config.synthesis_layer}: Synthesis Gate            ACTIVE + INFLUENCE    ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Tracking: Phase coherence, Ontological diversity, Layer PPL     ║")
        print(f"  ║  NEW: Per-layer CONSTRUCTIVE/DESTRUCTIVE influence analysis      ║")
        print(f"  ╚══════════════════════════════════════════════════════════════════╝")
    else:
        srk_influence = None

    # ==========================================================================
    # V10.3.4: KOSHA/WITNESS CONSCIOUSNESS DIAGNOSTICS
    # ==========================================================================
    kosha_diagnostics = None
    witness_diagnostics = None

    if getattr(args, 'enable_kosha', False):
        kosha_diagnostics = KoshaDiagnostics(
            hidden_dim=config.d_model,
            num_layers=config.num_layers,
            state_dim=SOVEREIGN_STATE_DIM,
            device=torch.device(config.device),
        )

        print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.4: KOSHA CONSCIOUSNESS DIAGNOSTICS ENABLED                 ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  The 5-Layer Kosha Model (Pancha Kosha):                          ║")
        print(f"  ║                                                                    ║")
        print(f"  ║    0. MATERIAL   (Annamaya)     - Token/syntax grounding          ║")
        print(f"  ║    1. VITAL      (Pranamaya)    - Energy/gradient flow            ║")
        print(f"  ║    2. MENTAL     (Manomaya)     - Semantic binding                ║")
        print(f"  ║    3. INTELLECTUAL (Vijnanamaya) - Abstract reasoning             ║")
        print(f"  ║    4. BLISSFUL   (Anandamaya)   - Coherence/integration           ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Target Kosha: {args.kosha_target:<12}                              ║")
        print(f"  ║  Dampen Material: {args.kosha_dampen_material:.2f}  |  Boost Target: {args.kosha_boost_target:.2f}       ║")
        print(f"  ║  Gyroscopic Loss: base={args.kosha_gyro_base_gain:.2f}, max={args.kosha_gyro_max_gain:.2f}            ║")
        print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

    if getattr(args, 'enable_witness', False):
        witness_diagnostics = WitnessDiagnostics(
            hidden_dim=config.d_model,
            state_dim=SOVEREIGN_STATE_DIM,
            constraint_threshold=args.witness_constraint_threshold,
            device=torch.device(config.device),
        )

        print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.4: WITNESS (SAKSHI) OBSERVER DIAGNOSTICS ENABLED           ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  The Witness observes thought patterns without attachment:        ║")
        print(f"  ║                                                                    ║")
        print(f"  ║    Vritti (Epistemic States):                                     ║")
        print(f"  ║      - FACT: Verified truth                                       ║")
        print(f"  ║      - MISCONCEPTION: Believed but wrong                          ║")
        print(f"  ║      - IMAGINATION: Creative/hypothetical                         ║")
        print(f"  ║      - VOID: Unknown/uncertain                                    ║")
        print(f"  ║      - MEMORY: Retrieved from context                             ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Constraint Threshold: {args.witness_constraint_threshold:.2f}                               ║")
        print(f"  ║  Tracks: Domain arbitration, bottleneck detection, meta-cognition ║")
        print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

        # V10.3.7: Witness entropy regularization
        if getattr(args, 'witness_entropy_reg', False):
            lambda_entropy = getattr(args, 'witness_entropy_lambda', 0.1)
            print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
            print(f"  ║  V10.3.7: WITNESS ENTROPY REGULARIZATION ENABLED                  ║")
            print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
            print(f"  ║  Prevents vritti collapse to single epistemic state               ║")
            print(f"  ║  Loss += -λ * H(vritti)   where H = -Σ p*log(p)                   ║")
            print(f"  ║  Lambda: {lambda_entropy:.3f}  (higher = more balanced distribution)        ║")
            print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

    # ==========================================================================
    # V10.3.5: DOMAIN SEPARATION - Aligned with SRK component layout
    # ==========================================================================
    use_domain_separation = getattr(args, 'domain_separation', False)
    csr_domain_layers = []
    kosha_domain_layers = []
    witness_domain_layers = []
    synthesis_domain_layers = []

    if use_domain_separation:
        # Parse layer assignments
        csr_domain_layers = [int(x) for x in args.csr_domain_layers.split(",")]
        kosha_domain_layers = [int(x) for x in args.kosha_domain_layers.split(",")]
        witness_domain_layers = [int(x) for x in args.witness_domain_layers.split(",")]
        synthesis_domain_layers = [int(x) for x in args.synthesis_domain_layers.split(",")]

        print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.5: DOMAIN SEPARATION ENABLED                               ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  SRK Component Layout (no authority conflict):                    ║")
        print(f"  ║                                                                    ║")
        print(f"  ║  Layer  Component              Domain         Role                ║")
        print(f"  ║  ─────────────────────────────────────────────────────────────    ║")
        print(f"  ║  L0     DNA Bridge            ONTOLOGY       Foundational Ontology║")
        print(f"  ║  L1     CSR Alignment         CSR            Phase Extraction     ║")
        print(f"  ║  L2     Kosha + Witness       KOSHA          Consciousness        ║")
        print(f"  ║  L3     Synthesis Gate        SYNTHESIS      Output Integration   ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Actual Layer Assignments:                                        ║")
        for i in range(config.num_layers):
            components = []
            if i in csr_domain_layers:
                if i == 0:
                    components.append("DNA_BRIDGE")
                else:
                    components.append("CSR")
            if i in kosha_domain_layers:
                components.append("KOSHA")
            if i in witness_domain_layers and i not in kosha_domain_layers:
                components.append("WITNESS")
            elif i in witness_domain_layers and i in kosha_domain_layers:
                components[-1] = "KOSHA+WITNESS"  # Combine if same layer
            if i in synthesis_domain_layers:
                components.append("SYNTHESIS")
            comp_str = "+".join(components) if components else "NONE"
            print(f"  ║    L{i}: {comp_str:<30}                     ║")
        print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

    # Entropy-Based Logit Scale Control (attach BEFORE optimizer)
    entropy_scale_module = None
    if getattr(args, 'enable_entropy_control_train', False):
        entropy_cfg = EntropyControlConfig(
            enable_entropy_control_train=True,
            enable_entropy_control_infer=getattr(args, 'enable_entropy_control_infer', False),
            entropy_topk=getattr(args, 'entropy_topk', 50),
            entropy_h_min=getattr(args, 'entropy_h_min', 0.15),
            entropy_h_max=getattr(args, 'entropy_h_max', 0.35),
            entropy_lambda=getattr(args, 'entropy_control_lambda', 0.01),
            logit_scale_min=getattr(args, 'logit_scale_min', -4.0),
            logit_scale_max=getattr(args, 'logit_scale_max', 4.0),
            infer_h_target=getattr(args, 'infer_h_target', 0.25),
            infer_eta=getattr(args, 'infer_eta', 0.02),
            infer_delta_clip=getattr(args, 'infer_delta_clip', 0.05),
        )
        entropy_scale_module = attach_logit_scale(model, entropy_cfg)
        print(f"  Entropy Logit Scale Control: ENABLED")
        print(f"    H_band=[{entropy_cfg.entropy_h_min}, {entropy_cfg.entropy_h_max}], lambda={entropy_cfg.entropy_lambda}")

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)

    # Checkpoint saving setup
    checkpoint_dir = getattr(args, 'checkpoint_dir', None)
    save_every = getattr(args, 'save_every', 0)
    if checkpoint_dir:
        os.makedirs(checkpoint_dir, exist_ok=True)
        print(f"\n  Checkpoint dir: {checkpoint_dir}")
        if save_every > 0:
            print(f"  Save every: {save_every} steps")

    def _save_checkpoint(model, optimizer, step, val_ppl, tag="best"):
        """Save checkpoint in format compatible with run_symbolu_ontology.py eval."""
        if not checkpoint_dir:
            return
        ckpt = {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "step": step,
            "val_ppl": val_ppl,
            "config": {
                "model_type": "hybrid" if not use_binding_cache else "binding_cache",
                "d_model": config.d_model,
                "embed_dim": config.d_model,
                "num_layers": config.num_layers,
                "num_heads": config.num_heads,
                "d_ff": config.d_ff,
                "vocab_size": getattr(args, 'lm_vocab_size', 50257),
                "seq_len": args.seq_len,
                "bounded_phase": config.bounded_phase,
                "source": "train_hard_probes.py",
            },
        }
        path = os.path.join(checkpoint_dir, f"{tag}.pt")
        torch.save(ckpt, path)
        print(f"  💾 Saved {tag} checkpoint → {path} (step={step}, PPL={val_ppl:.2f})")

    # Training loop
    print(f"\nTraining for {config.num_steps} steps...")
    model.train()
    step = 0
    total_loss = 0.0
    total_main_loss = 0.0  # V10.5.1: Track main loss separately for comparable PPL
    total_deep_loss = 0.0  # V10.5.1: Track deep supervision loss separately
    log_interval = 100

    train_iter = iter(train_loader)
    best_val_ppl = float('inf')

    # Convergence milestones tracking (to measure learning speed)
    ppl_milestones = [500, 200, 100, 50]
    milestone_steps = {m: None for m in ppl_milestones}
    ppl_history = []  # Track PPL over time

    while step < config.num_steps:
        # V10.5.8: Dynamic delay curriculum update
        if use_associative_recall and ar_dynamic_delay and hasattr(train_dataset, 'set_delay_range'):
            # Progress with warmup: stay at initial delay during warmup, then ramp
            progress = step / config.num_steps
            if progress < ar_curriculum_warmup:
                # During warmup - use initial delays
                pass
            else:
                # After warmup - linear ramp to target
                ramp_progress = (progress - ar_curriculum_warmup) / (1.0 - ar_curriculum_warmup)
                new_delay_min = int(ar_delay_min + ramp_progress * (ar_target_delay_min - ar_delay_min))
                new_delay_max = int(ar_delay_max + ramp_progress * (ar_target_delay_max - ar_delay_max))
                train_dataset.set_delay_range(new_delay_min, new_delay_max)

        try:
            batch = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch = next(train_iter)

        # V10.16.1: Handle dict batches (with query_mask) and tuple batches
        if isinstance(batch, dict):
            x = batch["input_ids"].to(config.device)
            y = batch["labels"].to(config.device)
        else:
            x, y = batch
            x, y = x.to(config.device), y.to(config.device)

        # V10.3.7: Check if witness entropy regularization is enabled
        use_witness_entropy = getattr(args, 'witness_entropy_reg', False) and witness_diagnostics is not None

        # V10.5: Deep Supervision forward path
        deep_loss_value = 0.0
        main_loss_value = 0.0  # V10.5.1: Track main loss separately for PPL reporting

        # V10.16.1: Targets now use -100 for ignored positions (standard PyTorch convention)
        ignore_idx = -100

        if use_deep_supervision and hasattr(model, 'forward_with_deep_supervision'):
            logits, deep_loss, layer_losses = model.forward_with_deep_supervision(x, y, ignore_index=ignore_idx)
            main_loss = F.cross_entropy(logits.view(-1, args.lm_vocab_size), y.view(-1), ignore_index=ignore_idx)
            main_loss_value = main_loss.item()  # Track main loss for reporting
            loss = main_loss + deep_loss  # Combined loss for backprop
            deep_loss_value = deep_loss.item()
            layer_hidden_states = None  # Not needed when using deep supervision
        # Forward - use probe_layers if witness entropy is enabled
        elif use_witness_entropy and hasattr(model, 'layer_outputs'):
            logits = model(x, probe_layers=True)
            layer_hidden_states = model.layer_outputs
            loss = F.cross_entropy(logits.view(-1, args.lm_vocab_size), y.view(-1), ignore_index=ignore_idx)
            main_loss_value = loss.item()
        else:
            logits = model(x)
            layer_hidden_states = None
            loss = F.cross_entropy(logits.view(-1, args.lm_vocab_size), y.view(-1), ignore_index=ignore_idx)
            main_loss_value = loss.item()

        # V10.3.7: Witness entropy regularization to prevent vritti collapse
        if use_witness_entropy and layer_hidden_states:
            # Use witness domain layer if domain separation enabled
            if use_domain_separation and witness_domain_layers:
                witness_layer_idx = max([l for l in witness_domain_layers if l < len(layer_hidden_states)])
            else:
                witness_layer_idx = min(2, len(layer_hidden_states) - 1)
            # Forward pass through witness (this stores _last_vritti_entropy with gradients)
            _ = witness_diagnostics(layer_hidden_states[witness_layer_idx], step=step)
            # Get entropy loss and add to main loss
            lambda_entropy = getattr(args, 'witness_entropy_lambda', 0.1)
            entropy_loss = witness_diagnostics.get_entropy_loss(lambda_entropy)
            loss = loss + entropy_loss

        # Entropy-Based Logit Scale Control (train-time)
        if entropy_scale_module is not None:
            scaled_logits = entropy_scale_module(logits)
            loss, ec_metrics = entropy_scale_module.compute_loss(scaled_logits, loss)
            if step % log_interval == 0:
                log_msg = log_entropy_metrics(ec_metrics, step)
                print(log_msg)

        # Backward
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()
        total_main_loss += main_loss_value  # V10.5.1: Track main loss separately
        total_deep_loss += deep_loss_value  # V10.5.1: Track deep loss separately
        step += 1

        # Periodic checkpoint save
        if save_every > 0 and step % save_every == 0:
            _save_checkpoint(model, optimizer, step, best_val_ppl, tag=f"step_{step}")

        # V10.5.4: Soft routing warmup schedule
        if soft_routing_warmup > 0 and not soft_routing_always and step == soft_routing_warmup:
            if hasattr(model, 'set_soft_routing'):
                model.set_soft_routing(False)  # Switch to hard top-K
                print(f"\n  ★ SOFT ROUTING WARMUP COMPLETE at step {step}")
                print(f"    Switching to hard top-K selection for quad")

        # Logging
        if step % log_interval == 0:
            avg_loss = total_loss / log_interval
            avg_main_loss = total_main_loss / log_interval  # V10.5.1: Main loss for PPL
            avg_deep_loss = total_deep_loss / log_interval  # V10.5.1: Deep loss avg
            ppl = math.exp(avg_main_loss)  # V10.5.1: PPL from main loss only (comparable)
            total_loss = 0.0
            total_main_loss = 0.0
            total_deep_loss = 0.0

            # Track PPL history (using main-loss PPL for comparability)
            ppl_history.append((step, ppl))

            # Check milestones (convergence speed tracking)
            for milestone in ppl_milestones:
                if milestone_steps[milestone] is None and ppl < milestone:
                    milestone_steps[milestone] = step
                    print(f"  ★ MILESTONE: PPL dropped below {milestone} at step {step}!")

            # Update phase-first curriculum
            if pfc is not None:
                new_curriculum = pfc.update(ppl)
                model.update_curriculum(new_curriculum)
                curr_str = ",".join([f"{c:.2f}" for c in new_curriculum])
                print(f"  Step {step:5d} | Loss: {avg_loss:.4f} | PPL: {ppl:8.2f} | Curriculum: [{curr_str}]")
            elif use_deep_supervision:
                # V10.5.1: Show main loss, PPL (from main loss), and deep loss separately
                print(f"  Step {step:5d} | MainLoss: {avg_main_loss:.4f} | PPL: {ppl:8.2f} | DeepLoss: {avg_deep_loss:.4f}")
            elif use_associative_recall and ar_dynamic_delay:
                # V10.5.8: Show delay curriculum progress
                curr_delay_min = train_dataset.delay_min
                curr_delay_max = train_dataset.delay_max
                print(f"  Step {step:5d} | Loss: {avg_loss:.4f} | PPL: {ppl:8.2f} | Delay: [{curr_delay_min}, {curr_delay_max}]")
            else:
                print(f"  Step {step:5d} | Loss: {avg_loss:.4f} | PPL: {ppl:8.2f}")

        # Evaluation
        if step % config.eval_every == 0:
            model.eval()
            val_loss = 0.0
            val_batches = 0

            with torch.no_grad():
                for x, y in val_loader:
                    x, y = x.to(config.device), y.to(config.device)
                    logits = model(x)
                    # V10.5.6: Use ignore_index for associative recall
                    val_loss += F.cross_entropy(
                        logits.view(-1, args.lm_vocab_size),
                        y.view(-1),
                        ignore_index=ignore_idx
                    ).item()
                    val_batches += 1
                    if val_batches >= 50:  # Limit eval batches
                        break

            val_loss /= val_batches
            val_ppl = math.exp(val_loss)
            print(f"\n  === Validation @ Step {step} ===")
            print(f"      Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f}")

            # V10.5.6: Associative Recall accuracy evaluation
            if use_associative_recall and ar_dataset is not None:
                retrieval_acc = ar_dataset.get_accuracy(model, config.device, num_samples=500)
                print(f"      ★ Retrieval Accuracy: {retrieval_acc*100:.1f}%")
                # Random baseline for num_pairs=8 keys would be 12.5%
                random_baseline = 100.0 / getattr(args, 'ar_num_pairs', 8)
                if retrieval_acc * 100 > random_baseline * 2:
                    print(f"        → QUAD IS WORKING! ({retrieval_acc*100:.1f}% >> {random_baseline:.1f}% random)")
                elif retrieval_acc * 100 > random_baseline * 1.2:
                    print(f"        → Quad shows some learning ({retrieval_acc*100:.1f}% > {random_baseline:.1f}% random)")
                else:
                    print(f"        → Quad NOT working (≈ random {random_baseline:.1f}%)")

                # V10.5.7: Show binding slot usage if enabled
                if hasattr(model, 'get_slot_usage'):
                    slot_usage = model.get_slot_usage()
                    if slot_usage['total_slots'] > 0:
                        print(f"      Binding Slots: {slot_usage['used_slots']}/{slot_usage['total_slots']} used ({slot_usage['usage_ratio']*100:.1f}%)")

            if val_ppl < best_val_ppl:
                best_val_ppl = val_ppl
                print(f"      ★ New best Val PPL!")
                _save_checkpoint(model, optimizer, step, val_ppl, tag="best")

            # V10.3.2: Protected Phase health monitoring
            if use_protected_phase and hasattr(model, 'get_phase_health'):
                phase_health = model.get_phase_health()
                print(f"\n      Protected Phase Health (R_k statistics):")
                print(f"        R_k mean: {phase_health['r_k_mean']:.4f} (target: 0.3-0.7)")
                print(f"        R_k std:  {phase_health['r_k_std']:.4f}")
                print(f"        R_k range: [{phase_health['r_k_min']:.4f}, {phase_health['r_k_max']:.4f}]")

                # Interpret health
                r_k_mean = phase_health['r_k_mean']
                if r_k_mean < 0.1:
                    print(f"        ⚠️  Phase COLLAPSED (R_k → 0)")
                elif r_k_mean > 0.9:
                    print(f"        ⚠️  Phase DEGENERATE (R_k → 1)")
                elif 0.3 <= r_k_mean <= 0.7:
                    print(f"        ✓  Phase HEALTHY")
                else:
                    print(f"        Phase marginal (outside optimal range)")

            # Layer-wise probing with detailed metrics
            if args.probe_layers:
                x_sample, y_sample = next(iter(val_loader))
                x_sample, y_sample = x_sample.to(config.device), y_sample.to(config.device)

                # Get detailed layer contributions
                contrib = model.get_layer_contributions(x_sample, y_sample)

                print(f"\n      Layer Contributions (Does Phase Learn Faster/Richer?):")
                print(f"      {'Layer':<8} {'Phase%':<8} {'PPL':<10} {'Δ PPL':<10} {'Contrib%':<10}")
                print(f"      {'-'*46}")
                for i in range(model.num_layers):
                    phase_pct = contrib['phase_ratio'][i] * 100
                    ppl = contrib['ppl'][i]
                    delta = contrib['ppl_delta'][i]
                    contrib_pct = contrib['contribution_pct'][i]
                    # Highlight layers that contribute most
                    marker = "★" if contrib_pct > 100 / model.num_layers * 1.5 else " "
                    print(f"      L{i:<6} {phase_pct:>6.1f}%  {ppl:>8.1f}  {delta:>+8.1f}  {contrib_pct:>8.1f}% {marker}")

                print(f"\n      Summary:")
                print(f"        Embed-only PPL: {contrib['ppl_embed']:.1f}")
                print(f"        Final PPL:      {contrib['ppl'][-1]:.1f}")
                print(f"        Total Reduction: {contrib['total_reduction']:.1f}")

                # Ablation test: Phase-only vs Local-only
                if use_protected_phase:
                    # Protected Phase: Sequential collaboration, not parallel mixing
                    print(f"\n      Protected Phase Architecture (no ablation test):")
                    print(f"        Architecture: Phase → Memory → Quad Query (sequential)")
                    print(f"        Normal PPL:  {val_ppl:.1f}")
                    print(f"        Phase and Quad COLLABORATE, not compete")
                    print(f"        → Ablation N/A for sequential architecture")

                    # Use dummy values for later analysis
                    ppl_phase_only = val_ppl
                    ppl_local_only = val_ppl
                else:
                    print(f"\n      Ablation Test (Phase vs Local contribution):")
                    ppl_normal = val_ppl
                    ppl_phase_only = model.ablate_attention(x_sample, y_sample, ablate_local=True)
                    ppl_local_only = model.ablate_attention(x_sample, y_sample, ablate_phase=True)

                    print(f"        Normal (mixed):    PPL = {ppl_normal:.1f}")
                    print(f"        Phase-only:        PPL = {ppl_phase_only:.1f}")
                    print(f"        Local-only:        PPL = {ppl_local_only:.1f}")

                    # Interpretation
                    phase_better = ppl_phase_only < ppl_local_only
                    if phase_better:
                        improvement = ((ppl_local_only - ppl_phase_only) / ppl_local_only) * 100
                        print(f"        → Phase is {improvement:.1f}% BETTER than Local alone!")
                    else:
                        improvement = ((ppl_phase_only - ppl_local_only) / ppl_phase_only) * 100
                        print(f"        → Local is {improvement:.1f}% better than Phase alone")

                # V10.3.0: SRK Phase Learning Observation
                if srk_monitor is not None:
                    # Forward pass with layer capture
                    _ = model(x_sample, probe_layers=True)
                    layer_hidden_states = model.layer_outputs

                    if layer_hidden_states:
                        srk_metrics = srk_monitor.observe(layer_hidden_states)

                        print(f"\n      ╔══════════════════════════════════════════════════════╗")
                        print(f"      ║  SRK Phase Learning Metrics @ Step {step:<6}            ║")
                        print(f"      ╠══════════════════════════════════════════════════════╣")

                        # DNA Bridge (L4)
                        dna_key = f'L{srk_monitor.config.dna_bridge_layer}_dna_onto_diversity'
                        if dna_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.dna_bridge_layer} DNA Bridge:                              ║")
                            print(f"      ║    Ontology Diversity: {srk_metrics[dna_key]:.4f}                   ║")

                        # CSR Phase Hook (L7)
                        csr_key = f'L{srk_monitor.config.csr_alignment_layer}_csr_phase_coherence'
                        if csr_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.csr_alignment_layer} CSR Alignment:                           ║")
                            print(f"      ║    Phase Coherence (R_k): {srk_metrics[csr_key]:.4f}                ║")

                        # Witness Arbitrator (L9)
                        wit_key = f'L{srk_monitor.config.witness_layer}_witness_witness_activation'
                        if wit_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.witness_layer} Witness Arbitrator:                       ║")
                            print(f"      ║    Witness Activation: {srk_metrics[wit_key]:.4f}                  ║")

                        # Synthesis Gate (L11)
                        syn_key = f'L{srk_monitor.config.synthesis_layer}_synth_synthesis_gate_mean'
                        if syn_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.synthesis_layer} Synthesis Gate:                           ║")
                            print(f"      ║    Gate Mean: {srk_metrics[syn_key]:.4f}                           ║")

                        print(f"      ╚══════════════════════════════════════════════════════╝")

                        # V10.3.1: Layer Influence Diagnostics
                        if srk_influence is not None:
                            influence_metrics = srk_influence.analyze_all_layers(
                                layer_hidden_states,
                                num_heads=config.num_heads,
                            )
                            srk_influence.print_influence_report(influence_metrics, step)

                            # Print detailed breakdown every 5 evaluations
                            if len(srk_influence.influence_history) % 5 == 0:
                                srk_influence.print_detailed_layer_report(influence_metrics)

                # V10.3.4/V10.3.5: Kosha Consciousness Diagnostics (with domain separation)
                if kosha_diagnostics is not None:
                    # Forward pass with layer capture
                    if not layer_hidden_states:
                        _ = model(x_sample, probe_layers=True)
                        layer_hidden_states = model.layer_outputs

                    # V10.3.5: Only analyze layers in Kosha's domain
                    if use_domain_separation and kosha_domain_layers:
                        layers_to_analyze = [i for i in kosha_domain_layers if i < len(layer_hidden_states)]
                    else:
                        layers_to_analyze = range(len(layer_hidden_states))

                    for i in layers_to_analyze:
                        if i < len(layer_hidden_states):
                            kosha_metrics = kosha_diagnostics(layer_hidden_states[i], layer_idx=i, step=step)

                    # Print summary report
                    if use_domain_separation:
                        print(f"\n      [Kosha Domain: Layers {list(layers_to_analyze)}]")
                    kosha_diagnostics.print_report(step)

                # V10.3.4/V10.3.5: Witness Observer Diagnostics (with domain separation)
                if witness_diagnostics is not None:
                    # Forward pass with layer capture
                    if not layer_hidden_states:
                        _ = model(x_sample, probe_layers=True)
                        layer_hidden_states = model.layer_outputs

                    # V10.3.5: Only observe layers in Witness's domain
                    if use_domain_separation and witness_domain_layers:
                        # Use the highest layer in witness domain
                        witness_layer_idx = max([l for l in witness_domain_layers if l < len(layer_hidden_states)])
                    else:
                        witness_layer_idx = min(2, len(layer_hidden_states) - 1)

                    if layer_hidden_states and witness_layer_idx < len(layer_hidden_states):
                        witness_metrics = witness_diagnostics(
                            layer_hidden_states[witness_layer_idx],
                            step=step,
                        )

                    # Print summary report
                    if use_domain_separation:
                        print(f"\n      [Witness Domain: Layer {witness_layer_idx}]")
                    witness_diagnostics.print_report(step)

            print()
            model.train()

        # V10.3.6: Quality sample generation (skip for associative recall - no tokenizer)
        sample_every = getattr(args, 'sample_every', 500)
        if sample_every > 0 and step % sample_every == 0 and step > 0 and not use_associative_recall:
            # Get tokenizer from dataset
            tokenizer = train_dataset.tokenizer
            # Parse custom prompts if provided
            prompts = SAMPLE_PROMPTS
            custom_prompts = getattr(args, 'sample_prompts', None)
            if custom_prompts:
                prompts = tuple(p.strip() for p in custom_prompts.split(","))
            run_quality_samples(model, tokenizer, config.device, step, prompts)
            model.train()

    # Final evaluation with comprehensive analysis
    print("\n" + "=" * 70)
    if use_associative_recall:
        print("FINAL RESULTS: Associative Recall Task (V10.5.6)")
    elif use_protected_phase:
        print("FINAL RESULTS: Protected Phase Learning Analysis (V10.3.2)")
    else:
        print("FINAL RESULTS: Phase Learning Analysis")
    print("=" * 70)
    print(f"  Best Val PPL: {best_val_ppl:.2f}")

    # V10.5.6: Final Associative Recall accuracy
    if use_associative_recall and ar_dataset is not None:
        final_acc = ar_dataset.get_accuracy(model, config.device, num_samples=1000)
        random_baseline = 100.0 / getattr(args, 'ar_num_pairs', 8)
        print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
        print(f"  ║  ASSOCIATIVE RECALL FINAL ACCURACY                           ║")
        print(f"  ╠══════════════════════════════════════════════════════════════╣")
        print(f"  ║  Retrieval Accuracy:   {final_acc*100:6.2f}%                            ║")
        print(f"  ║  Random Baseline:      {random_baseline:6.2f}%                            ║")
        if final_acc * 100 > 80:
            print(f"  ║  Verdict: QUAD WORKS VERY WELL!   ★★★                         ║")
        elif final_acc * 100 > 50:
            print(f"  ║  Verdict: QUAD WORKS MODERATELY  ★★                           ║")
        elif final_acc * 100 > random_baseline * 2:
            print(f"  ║  Verdict: QUAD SHOWS LEARNING    ★                            ║")
        else:
            print(f"  ║  Verdict: QUAD BROKEN (≈ random)  ✗                           ║")
        print(f"  ╚══════════════════════════════════════════════════════════════╝")

        # V10.5.7: Show binding slot usage in final results
        if hasattr(model, 'get_slot_usage'):
            slot_usage = model.get_slot_usage()
            if slot_usage['total_slots'] > 0:
                print(f"\n  Binding Slot Cache Usage:")
                print(f"    Slots used: {slot_usage['used_slots']}/{slot_usage['total_slots']}")
                print(f"    Usage ratio: {slot_usage['usage_ratio']*100:.1f}%")

    if use_protected_phase:
        print(f"  Architecture: Protected Phase (sequential collaboration)")
        print(f"  Phase contributes 100% as memory accumulator")
    else:
        print(f"  Final Curriculum: {[f'{c:.2f}' for c in model.curriculum]}")

    # Convergence speed summary
    print(f"\n  Convergence Speed (steps to reach PPL milestone):")
    for milestone in ppl_milestones:
        steps = milestone_steps[milestone]
        if steps is not None:
            print(f"    PPL < {milestone:4d}: {steps:5d} steps ✓")
        else:
            print(f"    PPL < {milestone:4d}: Not reached")

    # Final ablation and layer contribution analysis
    model.eval()
    x_final, y_final = next(iter(val_loader))
    x_final, y_final = x_final.to(config.device), y_final.to(config.device)

    with torch.no_grad():
        if use_protected_phase:
            # Protected Phase: no ablation (sequential architecture)
            ppl_phase_only = best_val_ppl  # Phase is always active
            ppl_local_only = best_val_ppl  # Local is always active
        else:
            ppl_phase_only = model.ablate_attention(x_final, y_final, ablate_local=True)
            ppl_local_only = model.ablate_attention(x_final, y_final, ablate_phase=True)
        # Get layer contributions for stability analysis
        contrib = model.get_layer_contributions(x_final, y_final)

    if use_protected_phase:
        print(f"\n  Protected Phase Architecture:")
        print(f"    Phase + Quad collaboration:  PPL = {best_val_ppl:.2f}")
        print(f"    (No ablation - they work sequentially, not in parallel)")

        # Show phase health instead
        if hasattr(model, 'get_phase_health'):
            phase_health = model.get_phase_health()
            print(f"\n  Final Phase Health:")
            print(f"    R_k mean: {phase_health['r_k_mean']:.4f}")
            print(f"    R_k std:  {phase_health['r_k_std']:.4f}")
            if 0.3 <= phase_health['r_k_mean'] <= 0.7:
                print(f"    Status:   HEALTHY ✓")
            elif phase_health['r_k_mean'] < 0.1:
                print(f"    Status:   COLLAPSED ⚠️")
            elif phase_health['r_k_mean'] > 0.9:
                print(f"    Status:   DEGENERATE ⚠️")
            else:
                print(f"    Status:   MARGINAL")
    else:
        print(f"\n  Final Ablation:")
        print(f"    Phase-only PPL: {ppl_phase_only:.2f}")
        print(f"    Local-only PPL: {ppl_local_only:.2f}")
        print(f"    Mixed PPL:      {best_val_ppl:.2f}")

    # =========================================================================
    # CONTROL BASELINE ANCHOR (Epistemic Hygiene)
    # =========================================================================
    print(f"\n  Control Baselines (Rules out confounds):")
    param_count = sum(p.numel() for p in model.parameters())
    print(f"    • Model parameters: {param_count:,}")
    print(f"    • Local-only (ablated) uses SAME parameters, SAME curriculum")
    print(f"    • Phase-only (ablated) uses SAME parameters, SAME curriculum")
    print(f"    • Difference is ONLY attention mechanism, not capacity")

    # Curriculum effect isolation
    if use_protected_phase:
        print(f"    • Architecture: Protected Phase (Phase→Memory→Quad Query)")
        print(f"    • Phase and Quad have SEPARATE roles, not parallel mixing")
        print(f"    • No curriculum needed - roles are architecturally defined")
    elif pfc is not None:
        print(f"    • Curriculum was DYNAMIC (PPL-based), applied to BOTH attention types")
        print(f"    • Final curriculum: {[f'{c:.2f}' for c in model.curriculum]}")
    else:
        print(f"    • Curriculum was STATIC: {[f'{c:.2f}' for c in model.curriculum]}")

    # =========================================================================
    # STABILITY / CONFIDENCE FLAGS (Trust indicators)
    # =========================================================================
    print(f"\n  Stability Notes (Why you can trust these results):")

    # 1. Phase collapse detection (phase values cluster near 0 or ±π)
    phase_collapse_detected = False
    phase_variance_total = 0.0
    phase_layers_checked = 0
    for layer in model.layers:
        if hasattr(layer, 'phase_attn') and hasattr(layer.phase_attn, 'W_phase'):
            # Check if phase projection has collapsed (very low variance)
            w = layer.phase_attn.W_phase.weight.data
            var = w.var().item()
            phase_variance_total += var
            phase_layers_checked += 1
            if var < 1e-6:
                phase_collapse_detected = True

    avg_phase_var = phase_variance_total / max(phase_layers_checked, 1)
    print(f"    • Phase collapse detected:     {'YES ⚠️' if phase_collapse_detected else 'NO ✓'}")
    if phase_layers_checked > 0:
        print(f"      (avg phase weight variance: {avg_phase_var:.6f})")

    # 2. Gradient dominance (one attention component dominates gradients)
    # V10.5 FIX 3: Use actual gradient norms instead of curriculum-based classification
    # The old curriculum-based diagnostic was broken for Protected Phase (curriculum=[1.0]*L)
    if hasattr(model, 'get_gradient_dominance_report'):
        # New: Measure actual gradient norms per component (local/phase/quad/ff)
        grad_report = model.get_gradient_dominance_report()
        gradient_dominance = grad_report['dominance_detected']
        layer_grad_decay = grad_report['layer_gradient_decay']

        print(f"    • Gradient dominance:          {'YES ⚠️' if gradient_dominance else 'NO ✓'}")
        print(f"      Component gradient distribution:")
        for comp, pct in grad_report['component_pcts'].items():
            marker = "⚠️" if pct > 70 else ""
            print(f"        {comp:6s}: {pct:5.1f}% {marker}")
        print(f"      Layer gradient decay (L{model.num_layers-1}/L0): {layer_grad_decay:.3f}", end="")
        if layer_grad_decay < 0.1:
            print(" ⚠️ (vanishing gradients)")
        elif layer_grad_decay > 10:
            print(" ⚠️ (exploding gradients)")
        else:
            print(" ✓")
    else:
        # Fallback for models without the new diagnostic (HybridTransformer, etc.)
        # This is the OLD curriculum-based diagnostic - known to be broken for Protected Phase
        phase_contrib = sum(contrib['contribution_pct'][i] for i in range(model.num_layers) if model.curriculum[i] > 0.5)
        local_contrib = sum(contrib['contribution_pct'][i] for i in range(model.num_layers) if model.curriculum[i] <= 0.5)
        gradient_dominance = abs(phase_contrib - local_contrib) > 70  # One side > 85%
        print(f"    • Gradient dominance:          {'YES ⚠️' if gradient_dominance else 'NO ✓'}")
        print(f"      (phase-heavy layers: {phase_contrib:.1f}%, local-heavy: {local_contrib:.1f}%)")
        if all(c == 1.0 for c in model.curriculum):
            print(f"      ⚠️  WARNING: curriculum=[1.0]*L, this metric is INVALID for Protected Phase")

    # 3. Representation saturation (PPL stops improving)
    ppl_improving = len(ppl_history) < 5 or (ppl_history[-1][1] < ppl_history[-5][1] * 0.99)
    print(f"    • Representation saturation:   {'YES ⚠️' if not ppl_improving else 'NO ✓'}")

    # 4. Early-layer overfitting (L0 contributes too much)
    early_overfit = contrib['contribution_pct'][0] > 60 if len(contrib['contribution_pct']) > 0 else False
    print(f"    • Early-layer overfitting:     {'YES ⚠️' if early_overfit else 'NO ✓'}")
    if early_overfit:
        print(f"      (L0 contributes {contrib['contribution_pct'][0]:.1f}% of PPL reduction)")

    # Overall confidence
    issues = sum([phase_collapse_detected, gradient_dominance, not ppl_improving, early_overfit])
    if issues == 0:
        confidence = "HIGH ✓"
    elif issues == 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW ⚠️"
    print(f"\n    Overall Confidence: {confidence} ({4-issues}/4 checks passed)")

    # V10.5: Deep Supervision Status
    if use_deep_supervision:
        print(f"\n  Deep Supervision (V10.5 Fix 1):")
        print(f"    Status: ENABLED")
        deep_lambda = getattr(args, 'deep_supervision_lambda', 0.5)
        print(f"    Lambda: {deep_lambda}")
        if early_overfit:
            print(f"    Effect: L0 still dominates ({contrib['contribution_pct'][0]:.1f}%) - consider increasing lambda")
        else:
            print(f"    Effect: Depth utilization improved ✓")
            # Show per-layer contribution distribution
            print(f"    Layer contributions: ", end="")
            for i, pct in enumerate(contrib['contribution_pct']):
                marker = "★" if pct > 100 / model.num_layers * 1.5 else ""
                print(f"L{i}:{pct:.0f}% ", end="")
            print()

    # =========================================================================
    # CONCLUSION
    # =========================================================================
    if use_protected_phase:
        print(f"\n  CONCLUSION: Protected Phase Architecture (V10.3.2)")
        print(f"    Phase ACCUMULATES memory state via O(n) cumsum")
        print(f"    Quad QUERIES memory state via O(n²) attention")
        print(f"    They COLLABORATE sequentially - no gradient competition")
        print(f"    Final PPL: {best_val_ppl:.2f}")

        # Protected phase health verdict
        if hasattr(model, 'get_phase_health'):
            health = model.get_phase_health()
            if 0.3 <= health['r_k_mean'] <= 0.7:
                print(f"    Phase health: OPTIMAL (R_k = {health['r_k_mean']:.3f})")
            else:
                print(f"    Phase health: SUBOPTIMAL (R_k = {health['r_k_mean']:.3f})")
    elif ppl_phase_only < ppl_local_only:
        print(f"\n  CONCLUSION: Phase learns RICHER representations!")
        print(f"    Phase alone achieves {((ppl_local_only - ppl_phase_only) / ppl_local_only * 100):.1f}% better PPL than Local alone.")
        if issues == 0:
            print(f"    This result is TRUSTWORTHY (all stability checks passed).")
    else:
        print(f"\n  CONCLUSION: Local attention dominates for this task.")
        print(f"    But mixed attention achieves best results ({best_val_ppl:.2f}).")

    # =========================================================================
    # V10.3.0: SRK PHASE LEARNING FINAL REPORT
    # =========================================================================
    if srk_monitor is not None:
        print("\n" + "=" * 70)
        print("SRK PHASE LEARNING ANALYSIS (V10.3.0)")
        print("=" * 70)
        srk_monitor.print_phase_learning_report()

        # Detailed trend analysis
        summary = srk_monitor.get_phase_learning_summary()
        if summary.get('num_observations', 0) > 1:
            print("\n  Phase Learning Trends Over Training:")
            print("  " + "-" * 50)

            # Check if phase coherence improved
            csr_key = f'L{srk_monitor.config.csr_alignment_layer}_csr_phase_coherence'
            if f'{csr_key}_trend' in summary:
                trend = summary[f'{csr_key}_trend']
                initial = summary.get(f'{csr_key}_initial', 0)
                final = summary.get(f'{csr_key}_final', 0)
                if trend > 0:
                    print(f"    Phase Coherence: IMPROVED {initial:.4f} → {final:.4f} (+{trend:.4f})")
                    print(f"      → Phase is LEARNING relational structure!")
                else:
                    print(f"    Phase Coherence: DECLINED {initial:.4f} → {final:.4f} ({trend:.4f})")
                    print(f"      → Phase may be collapsing or becoming decorative")

            # Check ontological diversity
            dna_key = f'L{srk_monitor.config.dna_bridge_layer}_dna_onto_diversity'
            if f'{dna_key}_trend' in summary:
                trend = summary[f'{dna_key}_trend']
                initial = summary.get(f'{dna_key}_initial', 0)
                final = summary.get(f'{dna_key}_final', 0)
                if trend > 0:
                    print(f"    Ontology Diversity: IMPROVED {initial:.4f} → {final:.4f} (+{trend:.4f})")
                    print(f"      → Model developing rich 12D ontological representation")
                else:
                    print(f"    Ontology Diversity: DECLINED {initial:.4f} → {final:.4f} ({trend:.4f})")
                    print(f"      → Possible dimensional collapse in ontological space")

            # Check witness activation
            wit_key = f'L{srk_monitor.config.witness_layer}_witness_witness_activation'
            if f'{wit_key}_trend' in summary:
                trend = summary[f'{wit_key}_trend']
                initial = summary.get(f'{wit_key}_initial', 0)
                final = summary.get(f'{wit_key}_final', 0)
                print(f"    Witness Activation: {initial:.4f} → {final:.4f} ({trend:+.4f})")
                if abs(final) > 0.1:
                    print(f"      → Consciousness/attention layer is ACTIVE")
                else:
                    print(f"      → Witness layer may be underutilized")

            # Check synthesis gate
            syn_key = f'L{srk_monitor.config.synthesis_layer}_synth_synthesis_gate_mean'
            if f'{syn_key}_trend' in summary:
                trend = summary[f'{syn_key}_trend']
                initial = summary.get(f'{syn_key}_initial', 0)
                final = summary.get(f'{syn_key}_final', 0)
                print(f"    Synthesis Gate: {initial:.4f} → {final:.4f} ({trend:+.4f})")
                if 0.3 < final < 0.7:
                    print(f"      → Gate is SELECTIVE (good output integration)")
                elif final > 0.9:
                    print(f"      → Gate is fully OPEN (minimal filtering)")
                else:
                    print(f"      → Gate is mostly CLOSED (may block outputs)")

        # V10.3.1: Layer Influence Summary
        if srk_influence is not None and srk_influence.influence_history:
            print("\n" + "=" * 70)
            print("SRK LAYER INFLUENCE ANALYSIS (V10.3.1)")
            print("=" * 70)

            inf_summary = srk_influence.get_influence_summary()

            print(f"\n  Layer Influence Over Training ({inf_summary.get('num_observations', 0)} observations):")
            print("  " + "-" * 60)
            print(f"  {'Layer':<8} {'Component':<20} {'Initial':<10} {'Final':<10} {'Trend':<12} {'Verdict'}")
            print("  " + "-" * 60)

            layer_verdicts = []
            for layer_idx in sorted(set(int(k.split('_')[0][1:]) for k in inf_summary.keys() if k.startswith('L') and '_score_initial' in k)):
                # Get metrics for this layer
                initial = inf_summary.get(f'L{layer_idx}_score_initial', 0)
                final = inf_summary.get(f'L{layer_idx}_score_final', 0)
                trend = inf_summary.get(f'L{layer_idx}_score_trend', 0)
                constructive_pct = inf_summary.get(f'L{layer_idx}_constructive_pct', 0)
                destructive_pct = inf_summary.get(f'L{layer_idx}_destructive_pct', 0)

                # Determine component name
                if layer_idx == srk_monitor.config.dna_bridge_layer:
                    component = "DNA Bridge"
                elif layer_idx == srk_monitor.config.csr_alignment_layer:
                    component = "CSR Alignment"
                elif layer_idx == srk_monitor.config.witness_layer:
                    component = "Witness Arbitrator"
                elif layer_idx == srk_monitor.config.synthesis_layer:
                    component = "Synthesis Gate"
                else:
                    component = "Unknown"

                # Determine verdict
                if constructive_pct > 0.6:
                    verdict = "CONSTRUCTIVE"
                    layer_verdicts.append(("constructive", layer_idx, component))
                elif destructive_pct > 0.6:
                    verdict = "DESTRUCTIVE"
                    layer_verdicts.append(("destructive", layer_idx, component))
                elif trend > 0.1:
                    verdict = "IMPROVING"
                    layer_verdicts.append(("improving", layer_idx, component))
                elif trend < -0.1:
                    verdict = "DEGRADING"
                    layer_verdicts.append(("degrading", layer_idx, component))
                else:
                    verdict = "NEUTRAL"
                    layer_verdicts.append(("neutral", layer_idx, component))

                trend_arrow = "↑" if trend > 0.05 else "↓" if trend < -0.05 else "→"
                print(f"  L{layer_idx:<6} {component:<20} {initial:+.3f}     {final:+.3f}     {trend:+.3f} {trend_arrow}     {verdict}")

            # Overall recommendation
            print("\n  " + "=" * 60)
            print("  RECOMMENDATIONS:")
            print("  " + "-" * 60)

            constructive_layers = [v for v in layer_verdicts if v[0] == "constructive"]
            destructive_layers = [v for v in layer_verdicts if v[0] == "destructive"]
            degrading_layers = [v for v in layer_verdicts if v[0] == "degrading"]

            if destructive_layers:
                print(f"\n  ⚠️  DESTRUCTIVE layers detected:")
                for _, idx, name in destructive_layers:
                    print(f"      L{idx} ({name}): Consider disabling or adjusting")
                    if name == "DNA Bridge":
                        print(f"        → Try --srk-disable-dna-bridge or different layer")
                    elif name == "CSR Alignment":
                        print(f"        → Try --srk-disable-phase-hook or different layer")
                    elif name == "Witness Arbitrator":
                        print(f"        → Try --srk-disable-witness or different layer")
                    elif name == "Synthesis Gate":
                        print(f"        → Try --srk-disable-synthesis or different layer")

            if degrading_layers:
                print(f"\n  ⚠️  DEGRADING layers (getting worse over training):")
                for _, idx, name in degrading_layers:
                    print(f"      L{idx} ({name}): May need longer training or tuning")

            if constructive_layers:
                print(f"\n  ✓  CONSTRUCTIVE layers (helping phase learning):")
                for _, idx, name in constructive_layers:
                    print(f"      L{idx} ({name}): Keep enabled!")

            # Overall assessment
            if len(destructive_layers) > len(constructive_layers):
                print(f"\n  OVERALL: More layers DESTRUCTIVE than constructive.")
                print(f"           Consider adjusting layer positions or disabling problematic layers.")
            elif len(constructive_layers) > len(destructive_layers):
                print(f"\n  OVERALL: More layers CONSTRUCTIVE - SRK is helping phase learning!")
            else:
                print(f"\n  OVERALL: Mixed influence - consider fine-tuning layer positions.")

    # ==========================================================================
    # V10.3.4/V10.3.5: KOSHA/WITNESS FINAL ANALYSIS (with domain separation)
    # ==========================================================================
    if kosha_diagnostics is not None:
        print("\n" + "=" * 70)
        if use_domain_separation:
            print(f"KOSHA CONSCIOUSNESS ANALYSIS (V10.3.5) - Domain: Layers {kosha_domain_layers}")
        else:
            print("KOSHA CONSCIOUSNESS ANALYSIS (V10.3.4)")
        print("=" * 70)
        kosha_diagnostics.print_report(step)

        summary = kosha_diagnostics.get_summary()
        if summary:
            kosha_names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
            vedic_names = ['Annamaya', 'Pranamaya', 'Manomaya', 'Vijnanamaya', 'Anandamaya']
            means = summary['mean_activations']
            trends = summary['trends']

            # Find dominant and fastest-growing kosha
            dominant_idx = means.index(max(means))
            fastest_idx = trends.index(max(trends))

            print(f"\n  KOSHA CONCLUSIONS:")
            print(f"  " + "-" * 60)
            print(f"    Dominant Kosha: {kosha_names[dominant_idx]} ({vedic_names[dominant_idx]})")
            print(f"    Fastest Growing: {kosha_names[fastest_idx]} ({vedic_names[fastest_idx]})")
            print(f"    Gyroscopic Loss: {summary['mean_gyro_loss']:.4f}")
            print(f"    Transitions: {summary['num_transitions']} state changes")

            # Interpretation
            if dominant_idx == 3:  # INTELLECTUAL
                print(f"\n    ✓ Model is operating at INTELLECTUAL (Vijnanamaya) level")
                print(f"      → Good for abstract reasoning and pattern recognition")
            elif dominant_idx == 4:  # BLISSFUL
                print(f"\n    ✓ Model reached BLISSFUL (Anandamaya) level")
                print(f"      → Excellent coherence and integration")
            elif dominant_idx <= 1:  # MATERIAL or VITAL
                print(f"\n    ⚠️ Model is stuck at lower consciousness layers")
                print(f"      → May need more training or kosha steering")

    if witness_diagnostics is not None:
        print("\n" + "=" * 70)
        if use_domain_separation:
            print(f"WITNESS (SAKSHI) OBSERVER ANALYSIS (V10.3.5) - Domain: Layers {witness_domain_layers}")
        else:
            print("WITNESS (SAKSHI) OBSERVER ANALYSIS (V10.3.4)")
        print("=" * 70)
        witness_diagnostics.print_report(step)

        summary = witness_diagnostics.get_summary()
        if summary:
            vritti_names = ['FACT', 'MISCONCEPTION', 'IMAGINATION', 'VOID', 'MEMORY']
            means = summary['mean_vritti']

            # Find dominant vritti
            dominant_idx = means.index(max(means))

            print(f"\n  WITNESS CONCLUSIONS:")
            print(f"  " + "-" * 60)
            print(f"    Dominant Vritti: {vritti_names[dominant_idx]}")
            print(f"    Constraint Detection Rate: {summary['high_constraint_ratio']*100:.1f}%")
            print(f"    Meta-Cognitive Confidence: {summary['mean_confidence']:.3f}")

            # Interpretation
            if dominant_idx == 0:  # FACT
                print(f"\n    ✓ Model primarily in FACTUAL epistemic state")
                print(f"      → High reliability for factual reasoning")
            elif dominant_idx == 2:  # IMAGINATION
                print(f"\n    Creative/imaginative state dominant")
                print(f"      → Good for generative tasks, verify facts carefully")
            elif dominant_idx == 3:  # VOID
                print(f"\n    ⚠️ High uncertainty (VOID) detected")
                print(f"      → Model may need more training or clearer inputs")

    # Save final checkpoint
    _save_checkpoint(model, optimizer, step, best_val_ppl, tag="last")

    return model, best_val_ppl


# =============================================================================
# V10.2.1 CHUNKING ARCHITECTURE TESTS
# =============================================================================

