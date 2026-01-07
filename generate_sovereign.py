#!/usr/bin/env python3
"""
Sovereign Generation Script
===========================

The inference counterpart to train_unified_llm.py.

This script implements the Metabolic Inference Loop for Sovereign-1 models,
enabling cognitive-aware text generation with:

- Karma persistence across conversation turns (O12->O1 evolutionary bridge)
- 3-way toroidal coherence tracking (Seed <-> O1 <-> O12)
- Guna state monitoring (Sattva/Rajas/Tamas)
- Metacognitive recommendations (BRAKE/RECOVER/ABORT)
- CSR safety layer intervention
- 9:3 hierarchical layer awareness

Usage:
    # Basic generation
    python generate_sovereign.py --checkpoint checkpoints/sovereign.pt \
        --prompt "The meaning of life is"

    # Interactive mode
    python generate_sovereign.py --checkpoint checkpoints/sovereign.pt --interactive

    # With specific mode
    python generate_sovereign.py --checkpoint checkpoints/sovereign.pt \
        --mode sovereign --temp 0.7 --max_tokens 256

    # Batch generation from file
    python generate_sovereign.py --checkpoint checkpoints/sovereign.pt \
        --input prompts.txt --output generations.txt

Author: Sovereign-1 Training Initiative
Date: January 2026
Version: 1.0.0
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

import torch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.inference import (
    InferenceManager,
    EvolutionaryInferenceEngine,
    InferenceMetacognition,
    InferenceGunas,
    CSRInferenceGuard,
    LayerInferenceConfig,
)
from symbolu.inference.manager import InferenceMode, InferenceManagerConfig
from symbolu.inference.checkpoint_utils import load_sovereign_config, InferenceCheckpointLoader


def load_tokenizer(tokenizer_name: str = "gpt2"):
    """Load tokenizer."""
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        return tokenizer
    except ImportError:
        print("WARNING: transformers not installed. Using basic tokenizer.")
        return None


def load_model_from_checkpoint(
    checkpoint_path: str,
    device: torch.device,
) -> torch.nn.Module:
    """
    Load model from checkpoint.

    Supports multiple model architectures:
    - HybridPhaseTransformer
    - OntologicalHybridTransformer
    - PhaseTransformer
    """
    print(f"Loading checkpoint from {checkpoint_path}...")
    checkpoint = torch.load(checkpoint_path, map_location='cpu')

    # Detect model type from checkpoint
    if 'config' in checkpoint:
        config = checkpoint['config']
        model_type = getattr(config, 'model_type', 'hybrid')
    elif 'model_type' in checkpoint:
        model_type = checkpoint['model_type']
    else:
        model_type = 'hybrid'

    print(f"  Detected model type: {model_type}")

    # Import appropriate model class
    if model_type == 'ontological_hybrid':
        from symbolu.phase_transformer import OntologicalHybridTransformer
        ModelClass = OntologicalHybridTransformer
    elif model_type == 'hybrid':
        from symbolu.phase_transformer import HybridPhaseTransformer
        ModelClass = HybridPhaseTransformer
    elif model_type == 'phase':
        from symbolu.phase_transformer import PhaseTransformer
        ModelClass = PhaseTransformer
    else:
        from symbolu.phase_transformer import HybridPhaseTransformer
        ModelClass = HybridPhaseTransformer

    # Extract model config
    if 'model_config' in checkpoint:
        model_config = checkpoint['model_config']
    elif 'config' in checkpoint and hasattr(checkpoint['config'], 'vocab_size'):
        cfg = checkpoint['config']
        model_config = {
            'vocab_size': getattr(cfg, 'vocab_size', 50257),
            'embed_dim': getattr(cfg, 'embed_dim', 768),
            'num_layers': getattr(cfg, 'num_layers', 12),
            'num_heads': getattr(cfg, 'num_heads', 12),
            'ff_dim': getattr(cfg, 'ff_dim', 3072),
            'max_seq_len': getattr(cfg, 'max_seq_len', 2048),
            'dropout': getattr(cfg, 'dropout', 0.1),
        }
    else:
        # Default small model config
        model_config = {
            'vocab_size': 50257,
            'embed_dim': 768,
            'num_layers': 12,
            'num_heads': 12,
            'ff_dim': 3072,
            'max_seq_len': 2048,
            'dropout': 0.0,  # No dropout at inference
        }

    # Create model
    print(f"  Creating {ModelClass.__name__}...")
    model = ModelClass(**model_config)

    # Load weights
    if 'model' in checkpoint:
        model.load_state_dict(checkpoint['model'], strict=False)
    elif 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'], strict=False)
    else:
        # Try loading directly
        model.load_state_dict(checkpoint, strict=False)

    model.to(device)
    model.eval()

    param_count = sum(p.numel() for p in model.parameters())
    print(f"  Loaded model with {param_count:,} parameters")

    return model


def create_inference_manager(
    model: torch.nn.Module,
    tokenizer: Any,
    checkpoint_path: str,
    mode: str,
    device: torch.device,
) -> InferenceManager:
    """Create and configure inference manager."""

    # Map mode string to enum
    mode_map = {
        'fast': InferenceMode.FAST,
        'standard': InferenceMode.STANDARD,
        'full': InferenceMode.FULL,
        'safe': InferenceMode.SAFE,
        'sovereign': InferenceMode.SOVEREIGN,
    }
    inference_mode = mode_map.get(mode.lower(), InferenceMode.SOVEREIGN)

    # Create config
    config = InferenceManagerConfig(mode=inference_mode)

    # Get embed_dim from model
    embed_dim = getattr(model, 'embed_dim', 768)
    lm_head = getattr(model, 'lm_head', None)

    # Create evolutionary engine
    evolutionary_engine = EvolutionaryInferenceEngine(
        model=model,
        bridge_checkpoint_path=checkpoint_path,
    )
    evolutionary_engine.to(device)

    # Create CSR guard (if lm_head available)
    csr_guard = None
    if lm_head is not None and inference_mode in [InferenceMode.FULL, InferenceMode.SAFE, InferenceMode.SOVEREIGN]:
        csr_guard = CSRInferenceGuard(
            lm_head=lm_head,
            dim=embed_dim,
        )
        csr_guard.to(device)

    # Create layer config
    layer_config = LayerInferenceConfig()

    # Try to load sovereign config from checkpoint
    try:
        sovereign_config = load_sovereign_config(checkpoint_path)
        if sovereign_config is not None:
            print(f"  Loaded sovereign config: split={sovereign_config.authority_sensory_split}, "
                  f"alpha={sovereign_config.recommended_alpha}")
            # Apply recommended alpha
            evolutionary_engine.config.resonance_alpha = sovereign_config.recommended_alpha
    except Exception as e:
        print(f"  Note: Could not load sovereign config ({e})")

    # Create manager
    manager = InferenceManager(
        model=model,
        tokenizer=tokenizer,
        config=config,
        evolutionary_engine=evolutionary_engine,
        csr_guard=csr_guard,
        layer_config=layer_config,
        device=device,
    )

    return manager


def format_cognitive_log(output: Dict[str, Any]) -> str:
    """Format cognitive telemetry for display."""
    lines = []

    # Guna state
    s, r, t = output.get('gunas', (0.33, 0.33, 0.34))
    dominant = "Sattva" if s >= r and s >= t else "Rajas" if r >= t else "Tamas"
    lines.append(f"[Cognitive Log] {dominant} dominant | S:{s:.2f} R:{r:.2f} T:{t:.2f}")

    # Metacognition
    rec = output.get('recommendation', 'CONTINUE')
    lines.append(f"[Metacognition] Recommendation: {rec}")

    # Coherence
    coh = output.get('coherence', 0.0)
    details = output.get('coherence_details', {})
    if details.get('3way', False):
        lines.append(f"[Coherence] 3-Way Flow: {coh:.4f} "
                     f"(Birth:{details.get('birth_similarity', 0):.2f}, "
                     f"Flow:{details.get('flow_similarity', 0):.2f}, "
                     f"Evolution:{details.get('evolution_similarity', 0):.2f})")
    else:
        lines.append(f"[Coherence] 2-Way Flow: {coh:.4f}")

    # Generation stats
    lines.append(f"[Stats] Tokens:{output.get('tokens_generated', 0)} | "
                 f"Interventions:{output.get('interventions', 0)} | "
                 f"Karma:{'stored' if output.get('karma_stored') else 'none'}")

    if output.get('aborted'):
        lines.append(f"[ABORT] Reason: {output.get('abort_reason', 'unknown')}")

    if output.get('sovereign_score') is not None:
        lines.append(f"[Sovereign] Alignment Score: {output['sovereign_score']:.4f}")

    return "\n".join(lines)


def run_interactive_session(
    manager: InferenceManager,
    tokenizer: Any,
    args: argparse.Namespace,
):
    """Run interactive generation session."""

    print("\n" + "=" * 70)
    print("  SOVEREIGN ENGINE ACTIVE")
    print(f"  Mode: {args.mode.upper()} | Temp: {args.temp} | Max Tokens: {args.max_tokens}")
    print("  Type 'exit' or 'quit' to end session")
    print("  Type 'clear' to clear karma buffer")
    print("  Type 'status' to show cognitive status")
    print("=" * 70 + "\n")

    while True:
        try:
            prompt = input("[Sovereign Query] > ")
        except EOFError:
            break

        if not prompt:
            continue

        prompt_lower = prompt.lower().strip()

        if prompt_lower in ['exit', 'quit']:
            print("\nEnding sovereign session.")
            break

        if prompt_lower == 'clear':
            manager.clear_state()
            print("Karma buffer cleared.\n")
            continue

        if prompt_lower == 'status':
            print(manager.get_cognitive_status_line())
            print()
            continue

        # Tokenize prompt
        if tokenizer is not None:
            input_ids = tokenizer.encode(prompt, return_tensors='pt')
        else:
            # Fallback: treat as space-separated tokens (for testing)
            print("Warning: No tokenizer available. Using dummy tokenization.")
            input_ids = torch.tensor([[0] * len(prompt.split())], dtype=torch.long)

        input_ids = input_ids.to(manager.device)

        # Generate
        print(f"\n| Mode: {args.mode.upper()} | Scaling: 9:3 Hierarchical |")
        print("-" * 50)

        output = manager.generate_full_sequence(
            prompt_ids=input_ids,
            max_tokens=args.max_tokens,
            base_temp=args.temp,
            top_p=args.top_p,
            top_k=args.top_k,
        )

        # Display cognitive telemetry
        print(format_cognitive_log(output))
        print("-" * 50)

        # Display response
        response_text = output.get('text', '')
        if not response_text and tokenizer is not None:
            # Decode manually
            gen_ids = output['generated_ids'][0, input_ids.size(1):].tolist()
            response_text = tokenizer.decode(gen_ids, skip_special_tokens=True)

        print(f"[Response] {response_text}\n")


def run_single_generation(
    manager: InferenceManager,
    tokenizer: Any,
    prompt: str,
    args: argparse.Namespace,
) -> str:
    """Run single generation and return result."""

    if tokenizer is not None:
        input_ids = tokenizer.encode(prompt, return_tensors='pt')
    else:
        input_ids = torch.tensor([[0] * len(prompt.split())], dtype=torch.long)

    input_ids = input_ids.to(manager.device)

    output = manager.generate_full_sequence(
        prompt_ids=input_ids,
        max_tokens=args.max_tokens,
        base_temp=args.temp,
        top_p=args.top_p,
        top_k=args.top_k,
    )

    response_text = output.get('text', '')
    if not response_text and tokenizer is not None:
        gen_ids = output['generated_ids'][0, input_ids.size(1):].tolist()
        response_text = tokenizer.decode(gen_ids, skip_special_tokens=True)

    if args.verbose:
        print(format_cognitive_log(output))

    return response_text


def run_batch_generation(
    manager: InferenceManager,
    tokenizer: Any,
    input_file: str,
    output_file: str,
    args: argparse.Namespace,
):
    """Run batch generation from file."""

    with open(input_file, 'r') as f:
        prompts = [line.strip() for line in f if line.strip()]

    print(f"Processing {len(prompts)} prompts...")

    results = []
    for i, prompt in enumerate(prompts):
        print(f"  [{i+1}/{len(prompts)}] {prompt[:50]}...")
        response = run_single_generation(manager, tokenizer, prompt, args)
        results.append(response)

        # Clear karma between unrelated prompts if specified
        if args.clear_between:
            manager.clear_state()

    with open(output_file, 'w') as f:
        for response in results:
            f.write(response + "\n")

    print(f"Results written to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Sovereign Generation Script - Cognitive-aware text generation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required arguments
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="Path to model checkpoint (.pt file)")

    # Mode selection
    parser.add_argument("--mode", type=str, default="sovereign",
                        choices=["fast", "standard", "full", "safe", "sovereign"],
                        help="Inference mode (sovereign = full metabolic loop)")

    # Generation parameters
    parser.add_argument("--prompt", type=str, default=None,
                        help="Single prompt to generate from")
    parser.add_argument("--temp", type=float, default=0.7,
                        help="Base sampling temperature")
    parser.add_argument("--top_p", type=float, default=0.9,
                        help="Nucleus sampling threshold")
    parser.add_argument("--top_k", type=int, default=50,
                        help="Top-k sampling")
    parser.add_argument("--max_tokens", type=int, default=128,
                        help="Maximum tokens to generate")

    # Interactive mode
    parser.add_argument("--interactive", action="store_true",
                        help="Run interactive session")

    # Batch mode
    parser.add_argument("--input", type=str, default=None,
                        help="Input file with prompts (one per line)")
    parser.add_argument("--output", type=str, default="generations.txt",
                        help="Output file for batch generations")
    parser.add_argument("--clear_between", action="store_true",
                        help="Clear karma between prompts in batch mode")

    # Model configuration
    parser.add_argument("--tokenizer", type=str, default="gpt2",
                        help="Tokenizer to use")
    parser.add_argument("--device", type=str, default=None,
                        help="Device (cuda/cpu). Auto-detected if not specified.")

    # Output options
    parser.add_argument("--verbose", action="store_true",
                        help="Show cognitive telemetry for each generation")
    parser.add_argument("--no_banner", action="store_true",
                        help="Suppress startup banner")

    args = parser.parse_args()

    # Determine device
    if args.device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(args.device)

    # Print banner
    if not args.no_banner:
        print("\n" + "=" * 70)
        print("  SYMBOLU SOVEREIGN GENERATION ENGINE")
        print("  Version 1.0.0 | January 2026")
        print("=" * 70)
        print(f"  Device: {device}")
        print(f"  Checkpoint: {args.checkpoint}")
        print("=" * 70 + "\n")

    # Validate arguments
    if not args.interactive and args.prompt is None and args.input is None:
        parser.error("Must specify --prompt, --input, or --interactive")

    if not os.path.exists(args.checkpoint):
        parser.error(f"Checkpoint not found: {args.checkpoint}")

    # Load tokenizer
    print("Loading tokenizer...")
    tokenizer = load_tokenizer(args.tokenizer)

    # Load model
    model = load_model_from_checkpoint(args.checkpoint, device)

    # Create inference manager
    print("\nInitializing inference manager...")
    manager = create_inference_manager(
        model=model,
        tokenizer=tokenizer,
        checkpoint_path=args.checkpoint,
        mode=args.mode,
        device=device,
    )
    print(f"  Mode: {args.mode}")
    print(f"  Karma: {'enabled' if manager.config.enable_karma else 'disabled'}")
    print(f"  CSR Guard: {'enabled' if manager.config.enable_csr_guard else 'disabled'}")
    print(f"  Metacognition: {'enabled' if manager.config.enable_metacognition else 'disabled'}")

    # Run appropriate mode
    if args.interactive:
        run_interactive_session(manager, tokenizer, args)

    elif args.input is not None:
        run_batch_generation(manager, tokenizer, args.input, args.output, args)

    elif args.prompt is not None:
        response = run_single_generation(manager, tokenizer, args.prompt, args)
        print(f"\n[Response] {response}")

    print("\nSovereign session complete.")


if __name__ == "__main__":
    main()
