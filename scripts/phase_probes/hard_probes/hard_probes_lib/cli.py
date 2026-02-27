"""
CLI argument parser and main entry point.

Defines all ~200 command-line arguments organized by feature area.
Routes to the appropriate benchmark or training function based on flags.

Argument Groups:
    Model:              --d-model, --num-heads, --num-layers, --d-ff
    Training:           --num-steps, --batch-size, --lr, --checkpoint-dir
    Dataset:            --train-samples, --test-samples, --bind-ratio
    Chain lengths:      --train-chain-{min,max}, --test-chain-{min,max}
    Hybrid/Curriculum:  --run-hybrid, --curriculum, --compare-curricula
    Protected Phase:    --protected-phase
    Phase rotation:     --rotation-test, --rotation-angles
    Dual-channel:       --dual-channel-mode, --alignment-authority
    No-write contracts: --enforce-no-write-contracts, --strict-control-contract
    Deep supervision:   --deep-supervision, --deep-supervision-lambda
    Real language:      --real-language, --dataset, --seq-len
    SRK monitoring:     --enable-srk, --srk-*-layer
    Kosha/Witness:      --enable-kosha, --enable-witness
    Binding Cache:      --binding-cache, --binding-slots
    Entropy control:    --enable-entropy-control-train/infer
    Benchmarks:         --test-interference, --test-moe-ffn, --test-hp-quad, etc.

Quick Reference::

    # Default comparison (Quad vs Phase)
    python train_hard_probes.py

    # Real language modeling
    python train_hard_probes.py --real-language --dataset wikitext2

    # Specific benchmark
    python train_hard_probes.py --test-moe-ffn --moe-ablation

    # Full scientific comparison
    python train_hard_probes.py --compare-curricula --bind-ratio 0.7 --match-params
"""

import argparse
import torch

def main():
    parser = argparse.ArgumentParser(
        description="Hard Diagnostic Probe Training for PhaseAttention",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default run (Quadratic vs Phase)
  python train_hard_probes.py

  # BIND-dominant curriculum (recommended)
  python train_hard_probes.py --bind-ratio 0.7

  # Parameter-matched comparison
  python train_hard_probes.py --match-params

  # Longer chains for harder test
  python train_hard_probes.py --test-chain-min 6 --test-chain-max 8

  # v3: Test INVERTED CURRICULUM hypothesis (Phase=state, Quad=reasoning)
  python train_hard_probes.py --compare-curricula

  # v3: Custom curriculum (90% Phase L0 → 10% Phase L3)
  python train_hard_probes.py --run-hybrid --curriculum 0.9,0.7,0.3,0.1

  # Full scientific comparison
  python train_hard_probes.py --compare-curricula --bind-ratio 0.7 --match-params

  # Phase rotation test (verify phase encodes relational structure)
  python train_hard_probes.py --rotation-test

  # Custom rotation angles
  python train_hard_probes.py --rotation-test --rotation-angles 0,30,60,90,120,150,180

  # V10.2.1: Test chunking architecture (cross-attention, continuity, etc.)
  python train_hard_probes.py --test-chunking-v10

  # V10.2.1: Test with custom chunk size and sequence length
  python train_hard_probes.py --test-chunking-v10 --chunk-size 64 --chunk-test-seq-len 256
        """
    )

    # Model - INCREASED CAPACITY (d_model=128, num_heads=8, num_layers=4)
    parser.add_argument("--d-model", type=int, default=128,
                        help="Model dimension (increased for reasoning capacity)")
    parser.add_argument("--num-heads", type=int, default=8,
                        help="Number of attention heads")
    parser.add_argument("--num-layers", type=int, default=4,
                        help="Number of transformer layers")
    parser.add_argument("--d-ff", type=int, default=256,
                        help="FFN dimension (2x d_model)")

    # Training
    parser.add_argument("--num-steps", type=int, default=15000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--checkpoint-dir", type=str, default=None,
                        help="Directory to save model checkpoints. "
                             "Saves best.pt (best val PPL) and last.pt (final step). "
                             "Checkpoint format is compatible with run_symbolu_ontology.py eval.")
    parser.add_argument("--save-every", type=int, default=0,
                        help="Save periodic checkpoint every N steps (0 = disabled)")

    # Dataset
    parser.add_argument("--train-samples", type=int, default=20000)
    parser.add_argument("--test-samples", type=int, default=1000,
                        help="Samples per test split")
    parser.add_argument("--bind-ratio", type=float, default=0.6,
                        help="Ratio of BIND-dominant schemas (0.0-1.0)")

    # Chain lengths
    parser.add_argument("--train-chain-min", type=int, default=3)
    parser.add_argument("--train-chain-max", type=int, default=5)
    parser.add_argument("--test-chain-min", type=int, default=6)
    parser.add_argument("--test-chain-max", type=int, default=8)
    parser.add_argument("--persist-chain-min", type=int, default=8,
                        help="Min chain length for pure persistence test")
    parser.add_argument("--persist-chain-max", type=int, default=12,
                        help="Max chain length for pure persistence test")

    # Parameter matching
    parser.add_argument("--match-params", action="store_true",
                        help="Add extra FF params to quadratic to match phase param count")

    # Hybrid curriculum (v3)
    parser.add_argument("--run-hybrid", action="store_true",
                        help="Also run Hybrid model with inverted curriculum")
    parser.add_argument("--curriculum", type=str, default="0.9,0.7,0.3,0.1",
                        help="Phase ratios per layer (comma-separated). "
                             "Inverted=0.9,0.7,0.3,0.1 (Phase early, Quad late)")
    parser.add_argument("--compare-curricula", action="store_true",
                        help="Compare inverted vs standard curriculum")

    # Protected Phase (v5)
    parser.add_argument("--protected-phase", action="store_true",
                        help="Run Protected Phase model (Phase accumulates, Quad queries)")

    # Phase Rotation Test
    parser.add_argument("--rotation-test", action="store_true",
                        help="Run phase rotation test after training to verify phase encodes relations")
    parser.add_argument("--rotation-angles", type=str, default="0,45,90,135,180,270",
                        help="Comma-separated rotation angles in degrees for rotation test")

    # Phase collapse fix (V9.9.11)
    parser.add_argument("--bounded-phase", action="store_true", default=True,
                        help="Constrain phase to [-π, π] via π*sin() (default: True)")
    parser.add_argument("--no-bounded-phase", dest="bounded_phase", action="store_false",
                        help="Disable bounded phase (use raw linear projection)")

    # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
    parser.add_argument("--dual-channel-mode", action="store_true",
                        help="Enable dual-channel attention: separates content similarity from intent alignment. "
                             "s_content = cos(φ_q - φ_k) (what matches), "
                             "s_align = cos(θ_JEPA - θ_SRK) (intent agreement), "
                             "score = s_content * (1 + α * s_align). "
                             "Prevents intent from dominating content selectivity.")
    parser.add_argument("--alignment-authority", type=float, default=0.1,
                        help="α: Weight for alignment term in dual-channel mode (default: 0.1). "
                             "0.0 = pure content matching (intent ignored), "
                             "0.1 = mild intent influence (recommended), "
                             "1.0 = strong intent influence.")
    # V10.6.1: Clamp bounds for alignment modulator (ChatGPT caveat)
    parser.add_argument("--alignment-clamp-min", type=float, default=0.8,
                        help="Minimum value for alignment modulator clamp (default: 0.8). "
                             "Prevents sustained JEPA/SRK misalignment from over-attenuating proposals. "
                             "Lower values allow more attenuation.")
    parser.add_argument("--alignment-clamp-max", type=float, default=1.2,
                        help="Maximum value for alignment modulator clamp (default: 1.2). "
                             "Prevents alignment agreement from over-amplifying proposals. "
                             "Higher values allow more amplification.")
    # V10.6.2: No-Write Contracts (ChatGPT gap analysis D.5)
    parser.add_argument("--enforce-no-write-contracts", action="store_true", default=True,
                        help="Enable no-write contract assertions (default: True). "
                             "Validates that control signals (intent phases, alignment scores) "
                             "are low-dimensional and broadcastable, not token-wise embeddings. "
                             "This prevents control from injecting content into Phase.")
    parser.add_argument("--no-enforce-no-write-contracts", dest="enforce_no_write_contracts",
                        action="store_false",
                        help="Disable no-write contract assertions for performance.")
    # V10.6.3: Strict vs Warn mode (ChatGPT recommendation)
    parser.add_argument("--strict-control-contract", action="store_true", default=True,
                        help="Raise exceptions on contract violations (default: True). "
                             "In strict mode, violations stop execution immediately. "
                             "Use --no-strict-control-contract for warn mode (log and continue).")
    parser.add_argument("--no-strict-control-contract", dest="strict_control_contract",
                        action="store_false",
                        help="Use warn mode: log contract violations but continue execution. "
                             "Useful for experiments that intentionally explore violations.")
    # V10.6.3: Alignment reduction mode (ChatGPT feedback)
    parser.add_argument("--alignment-reduction", type=str, default="per_head",
                        choices=["per_head", "global", "per_batch_head"],
                        help="How to reduce alignment scores (default: per_head). "
                             "per_head: [H] - per-head control (recommended). "
                             "global: [] - batch-level scalar (safest). "
                             "per_batch_head: [B, H] - per-batch per-head. "
                             "NOTE: [B, N] is no longer supported as it violates "
                             "the contract (token-position dependent).")

    # V10.4: Proposal Mode (Quad-as-Proposer, Phase-as-Integrator)
    parser.add_argument("--proposal-mode", action="store_true",
                        help="Enable proposal mode: Quad returns K proposals (no softmax mixing), "
                             "Phase integrates proposals with gating. This reverses the power hierarchy - "
                             "Phase decides meaning, Quad only proposes. Potential 30-50%% compute savings "
                             "when phase is confident enough to skip quad.")
    parser.add_argument("--confidence-threshold", type=float, default=0.7,
                        help="Threshold for phase confidence to skip quad (default: 0.7). "
                             "Higher = less skipping, lower = more aggressive skipping.")

    # V10.5: Deep Supervision (Fix 1 for L0 overfitting)
    parser.add_argument("--deep-supervision", action="store_true",
                        help="Enable deep supervision: add auxiliary losses at intermediate layers "
                             "to force later layers to learn useful representations. Prevents L0 overfitting "
                             "where only the first layer contributes to PPL reduction.")
    parser.add_argument("--deep-supervision-lambda", type=float, default=0.5,
                        help="Weight for deep supervision losses (default: 0.5). "
                             "Loss_i = lambda * (i+1)/num_layers * CE(h_i, targets). "
                             "Higher values encourage later layers more strongly.")

    # V10.5.4: Soft Routing Warmup (Fix for quad gradient starvation)
    parser.add_argument("--soft-routing-warmup", type=int, default=0,
                        help="Number of steps to use soft routing (full softmax) for quad. "
                             "After warmup, switches to hard top-K selection. "
                             "0 = no warmup (hard top-K from start). "
                             "Recommended: 500-1000 steps to allow gradients to flow to quad.")
    parser.add_argument("--soft-routing-always", action="store_true",
                        help="Always use soft routing (full softmax) for quad, never switch to hard top-K. "
                             "This is O(n²) but ensures gradients always flow to quad.")

    # V10.5.5: Force Quad at L0 experiment
    parser.add_argument("--force-quad-l0", action="store_true",
                        help="Force quad-only at L0, local-only at L1+. "
                             "Tests if quad CAN work when it's the only attention mechanism. "
                             "L0: local=0, quad=0.7, phase=0.3 (quad must do all the work) "
                             "L1+: local=0.7, quad=0, phase=0.3 (local takes over)")

    # ==========================================================================
    # V10.5.6: ASSOCIATIVE RECALL TASK (Forces Quad to Work)
    # ==========================================================================
    parser.add_argument("--associative-recall", action="store_true",
                        help="Use Associative Recall task instead of WikiText. "
                             "This task REQUIRES long-range memory retrieval that local "
                             "attention cannot solve. Format: K1=V1; K2=V2; ... [filler] ?=Ki "
                             "where the model must retrieve Vi. Delay > local window forces "
                             "quad to retrieve from phase memory.")
    parser.add_argument("--ar-num-pairs", type=int, default=8,
                        help="Number of key-value pairs per sample (default: 8)")
    parser.add_argument("--ar-delay-min", type=int, default=80,
                        help="Minimum filler tokens between pairs and query (default: 80, > local window)")
    parser.add_argument("--ar-delay-max", type=int, default=150,
                        help="Maximum filler tokens between pairs and query (default: 150)")
    parser.add_argument("--ar-vocab-size", type=int, default=1000,
                        help="Vocabulary size for associative recall task (default: 1000)")
    parser.add_argument("--ar-train-samples", type=int, default=50000,
                        help="Number of training samples for associative recall (default: 50000)")
    parser.add_argument("--ar-val-samples", type=int, default=2000,
                        help="Number of validation samples for associative recall (default: 2000)")

    # V10.5.8: Dynamic delay curriculum
    parser.add_argument("--ar-dynamic-delay", action="store_true",
                        help="Enable dynamic delay curriculum. Starts with --ar-delay-min/max and "
                             "progressively increases to --ar-target-delay-min/max over training.")
    parser.add_argument("--ar-target-delay-min", type=int, default=120,
                        help="Target minimum delay at end of training (default: 120)")
    parser.add_argument("--ar-target-delay-max", type=int, default=200,
                        help="Target maximum delay at end of training (default: 200)")
    parser.add_argument("--ar-curriculum-warmup", type=float, default=0.3,
                        help="Fraction of training to stay at initial delay before ramping (default: 0.3)")

    # V10.5.7: Binding Slot Cache (explicit key-value memory)
    parser.add_argument("--binding-slots", type=int, default=0,
                        help="Number of binding slots for explicit K-V memory (0=disabled, 16-32 recommended). "
                             "Provides discrete, content-addressable storage separate from Phase decay. "
                             "Required for associative recall task to work.")

    # ==========================================================================
    # REAL LANGUAGE MODE (WikiText/FineWeb)
    # ==========================================================================
    parser.add_argument("--real-language", action="store_true",
                        help="Use real language data (WikiText) instead of synthetic data")
    parser.add_argument("--dataset", type=str, default="wikitext2",
                        choices=["wikitext2", "wikitext103", "tinystories", "writingprompts", "imdb", "openwebtext", "c4"],
                        help="Dataset: tinystories (recommended for Kosha/Witness), wikitext2/103 (LM), writingprompts/imdb (diverse)")
    parser.add_argument("--seq-len", type=int, default=256,
                        help="Sequence length for language modeling")
    parser.add_argument("--lm-vocab-size", type=int, default=50257,
                        help="Vocabulary size for language modeling (GPT-2: 50257)")

    # Phase-first curriculum (from train_unified_llm.py)
    parser.add_argument("--phase-first-curriculum", action="store_true",
                        help="Enable phase-first learning: phase dominates early, local later")
    parser.add_argument("--alpha-phase-high", type=float, default=0.8,
                        help="alpha_phase when PPL >= ppl_high_threshold")
    parser.add_argument("--alpha-phase-low", type=float, default=0.3,
                        help="alpha_phase when PPL <= ppl_low_threshold")
    parser.add_argument("--ppl-high", type=float, default=1000.0,
                        help="PPL threshold for max phase weight")
    parser.add_argument("--ppl-low", type=float, default=100.0,
                        help="PPL threshold for min phase weight")

    # Layer-wise probing
    parser.add_argument("--probe-layers", action="store_true",
                        help="Probe each layer's contribution to PPL (real-language mode only)")

    # ==========================================================================
    # V10.3.0: SRK PHASE LEARNING MONITORING
    # ==========================================================================
    # Enable SRK (Sovereign Reasoning Kernel) to see how phase learning progresses
    # at different layers. SRK provides auxiliary components:
    #   - L4: DNA Bridge (Foundational Ontology)
    #   - L7: CSR Alignment Phase Extraction Hook
    #   - L9: Witness Arbitrator (Consciousness/Attention)
    #   - L11: Synthesis Gate (Output Integration)
    parser.add_argument("--enable-srk", action="store_true",
                        help="Enable SRK phase learning monitoring (requires --real-language --probe-layers)")
    parser.add_argument("--srk-dna-bridge-layer", type=int, default=0,
                        help="Layer for DNA Bridge (default: 0 for 4-layer model, maps to L4 in 12-layer)")
    parser.add_argument("--srk-csr-layer", type=int, default=1,
                        help="Layer for CSR Alignment / Phase Hook (default: 1 for 4-layer model)")
    parser.add_argument("--srk-witness-layer", type=int, default=2,
                        help="Layer for Witness Arbitrator (default: 2 for 4-layer model)")
    parser.add_argument("--srk-synthesis-layer", type=int, default=3,
                        help="Layer for Synthesis Gate (default: 3 for 4-layer model)")
    parser.add_argument("--srk-disable-dna-bridge", action="store_true",
                        help="Disable DNA Bridge component")
    parser.add_argument("--srk-disable-phase-hook", action="store_true",
                        help="Disable Phase Extraction Hook component")
    parser.add_argument("--srk-disable-witness", action="store_true",
                        help="Disable Witness Arbitrator component")
    parser.add_argument("--srk-disable-synthesis", action="store_true",
                        help="Disable Synthesis Gate component")
    parser.add_argument("--srk-lambda-ontology", type=float, default=0.1,
                        help="Weight for ontological alignment loss (default: 0.1)")
    parser.add_argument("--srk-lambda-coherence", type=float, default=0.05,
                        help="Weight for phase coherence loss (default: 0.05)")

    # ==========================================================================
    # V10.3.3: BINDING CACHE ARCHITECTURE
    # ==========================================================================
    parser.add_argument("--binding-cache", action="store_true",
                        help="Use Binding Cache architecture (Local + Phase + Quad) - "
                             "three-path with no gradient competition")
    parser.add_argument("--binding-cache-top-k", type=int, default=64,
                        help="Top-K cache size for Quad query (default: 64)")
    parser.add_argument("--local-window-size", type=int, default=64,
                        help="Window size for local attention (default: 64)")
    parser.add_argument("--decay-gamma", type=float, default=0.9,
                        help="Decay factor for phase memory accumulation (default: 0.9)")
    parser.add_argument("--binding-cache-phase-ratio", type=str, default="0.3,0.3,0.3,0.3",
                        help="Phase ratio per layer for binding cache (default: balanced 0.3)")
    parser.add_argument("--binding-cache-local-ratio", type=str, default="0.4,0.4,0.4,0.4",
                        help="Local ratio per layer for binding cache (default: 0.4)")
    parser.add_argument("--binding-cache-quad-ratio", type=str, default="0.3,0.3,0.3,0.3",
                        help="Quad ratio per layer for binding cache (default: 0.3)")

    # ==========================================================================
    # V10.3.4: KOSHA/WITNESS CONSCIOUSNESS SYSTEM
    # ==========================================================================
    parser.add_argument("--enable-kosha", action="store_true",
                        help="Enable Kosha (5-layer consciousness) diagnostics")
    parser.add_argument("--enable-witness", action="store_true",
                        help="Enable Witness (Sakshi observer) diagnostics")
    parser.add_argument("--kosha-target", type=str, default="INTELLECTUAL",
                        choices=["MATERIAL", "VITAL", "MENTAL", "INTELLECTUAL", "BLISSFUL"],
                        help="Target kosha for steering (default: INTELLECTUAL)")
    parser.add_argument("--kosha-dampen-material", type=float, default=0.5,
                        help="Dampen material kosha during reasoning (default: 0.5)")
    parser.add_argument("--kosha-boost-target", type=float, default=0.4,
                        help="Boost target kosha strength (default: 0.4)")
    parser.add_argument("--kosha-gyro-base-gain", type=float, default=0.15,
                        help="Base gain for kosha homeostatic loss (default: 0.15)")
    parser.add_argument("--kosha-gyro-max-gain", type=float, default=3.0,
                        help="Max gain for kosha homeostatic loss (default: 3.0)")
    parser.add_argument("--witness-constraint-threshold", type=float, default=0.85,
                        help="Threshold for constraint/bottleneck detection (default: 0.85)")

    # V10.3.7: WITNESS ENTROPY REGULARIZATION
    parser.add_argument("--witness-entropy-reg", action="store_true",
                        help="Enable entropy regularization to prevent vritti collapse")
    parser.add_argument("--witness-entropy-lambda", type=float, default=0.1,
                        help="Weight for vritti entropy regularization (default: 0.1)")

    # ENTROPY-BASED LOGIT SCALE CONTROL
    parser.add_argument("--enable-entropy-control-train", action="store_true",
                        help="Enable train-time entropy-based logit scale control")
    parser.add_argument("--enable-entropy-control-infer", action="store_true",
                        help="Enable inference-time adaptive entropy control")
    parser.add_argument("--entropy-topk", type=int, default=50,
                        help="K for top-K entropy computation (default: 50)")
    parser.add_argument("--entropy-h-min", type=float, default=0.15,
                        help="Lower bound of target entropy band (default: 0.15)")
    parser.add_argument("--entropy-h-max", type=float, default=0.35,
                        help="Upper bound of target entropy band (default: 0.35)")
    parser.add_argument("--entropy-control-lambda", type=float, default=0.01,
                        help="Weight for entropy band penalty (default: 0.01)")
    parser.add_argument("--logit-scale-min", type=float, default=-4.0,
                        help="Minimum logit scale clamp (default: -4.0)")
    parser.add_argument("--logit-scale-max", type=float, default=4.0,
                        help="Maximum logit scale clamp (default: 4.0)")
    parser.add_argument("--infer-h-target", type=float, default=0.25,
                        help="Target entropy midpoint for inference (default: 0.25)")
    parser.add_argument("--infer-eta", type=float, default=0.02,
                        help="Inference adaptation rate (default: 0.02)")
    parser.add_argument("--infer-delta-clip", type=float, default=0.05,
                        help="Inference error clipping bound (default: 0.05)")

    # V10.3.5: DOMAIN SEPARATION - Aligned with SRK component layout
    # Layer assignments (4-layer model):
    #   L0: DNA Bridge (Foundational Ontology)       → ONTOLOGY domain
    #   L1: CSR Alignment (Phase Extraction Hook)    → CSR domain
    #   L2: Kosha + Witness (Consciousness/attention) → KOSHA domain
    #   L3: Synthesis Gate (Output integration)       → SYNTHESIS domain
    parser.add_argument("--domain-separation", action="store_true",
                        help="Enable domain separation: each component governs its assigned layer")
    parser.add_argument("--csr-domain-layers", type=str, default="0,1",
                        help="Layers for Ontology+CSR (default: 0=DNA Bridge, 1=CSR Alignment)")
    parser.add_argument("--kosha-domain-layers", type=str, default="2",
                        help="Layers for Kosha consciousness (default: 2)")
    parser.add_argument("--witness-domain-layers", type=str, default="2",
                        help="Layers for Witness observation (default: 2 = same as Kosha)")
    parser.add_argument("--synthesis-domain-layers", type=str, default="3",
                        help="Layers for Synthesis Gate (default: 3 = output integration)")

    # ==========================================================================
    # V10.3.6: SAMPLE GENERATION FOR QUALITY MONITORING
    # ==========================================================================
    parser.add_argument("--sample-every", type=int, default=500,
                        help="Generate quality samples every N steps (0 to disable, default: 500)")
    parser.add_argument("--sample-prompts", type=str, default=None,
                        help="Comma-separated custom prompts for sampling (uses defaults if not set)")

    # ==========================================================================
    # V10.2.1: CHUNKING ARCHITECTURE TESTS
    # ==========================================================================
    parser.add_argument("--test-chunking-v10", action="store_true",
                        help="Run V10.2.1 chunking architecture tests: cross-attention, "
                             "chunk continuity, cross-chunk dependencies")
    parser.add_argument("--chunk-size", type=int, default=64,
                        help="Chunk size for chunking tests (default: 64 for synthetic tasks)")
    parser.add_argument("--chunk-test-seq-len", type=int, default=256,
                        help="Sequence length for chunk continuity test")

    # ==========================================================================
    # V10.5: INTERFERENCE-AWARE PROPOSAL SCORING BENCHMARKS
    # ==========================================================================
    # Tests the text interference scoring implementation to verify:
    # - Task classification accuracy (compositional vs factual)
    # - Interference effect on compositional tasks
    # - No harm on factual/code tasks
    # - Entropy gating behavior
    parser.add_argument("--test-interference", action="store_true",
                        help="Run interference scoring benchmarks. Tests: "
                             "1) Task classifier accuracy (compositional vs factual), "
                             "2) Interference effect on multi-concept reasoning, "
                             "3) No harm on factual/code tasks, "
                             "4) Entropy gating behavior.")
    parser.add_argument("--interference-lambda", type=float, default=0.02,
                        help="Lambda for interference scoring (0.01-0.03 for text). "
                             "Default: 0.02")
    parser.add_argument("--interference-min-step", type=int, default=8,
                        help="Minimum decoding step before interference applies. "
                             "Default: 8")
    parser.add_argument("--interference-entropy-gate", type=float, default=1.2,
                        help="Entropy threshold for interference gating. "
                             "Only apply if proposal entropy > gate. Default: 1.2")
    parser.add_argument("--interference-ablation", action="store_true",
                        help="Run interference ablation tests: "
                             "Base vs +Interference vs +BCVF vs +BCVF+Interference. "
                             "Requires --test-interference.")

    # ==========================================================================
    # V10.6: MOE FFN BENCHMARKS
    # ==========================================================================
    # Tests Mixture of Experts FFN for compute efficiency.
    # Standard Mixtral-style MoE: replaces dense FFN with sparse expert routing.
    parser.add_argument("--test-moe-ffn", action="store_true",
                        help="Run MoE FFN benchmarks. Tests: "
                             "1) Throughput comparison (dense vs MoE), "
                             "2) Expert utilization (load balance), "
                             "3) Quality comparison (accuracy preservation), "
                             "4) Router behavior (entropy, stability).")
    parser.add_argument("--moe-num-experts", type=int, default=8,
                        help="Number of experts in MoE FFN. Default: 8")
    parser.add_argument("--moe-top-k", type=int, default=2,
                        help="Number of experts to activate per token. Default: 2")
    parser.add_argument("--moe-load-balance-weight", type=float, default=0.01,
                        help="Weight for load balance loss. Default: 0.01")
    parser.add_argument("--moe-router-z-weight", type=float, default=0.001,
                        help="Weight for router z-loss (stabilization). Default: 0.001")
    parser.add_argument("--moe-ablation", action="store_true",
                        help="Run MoE ablation tests: "
                             "Dense vs MoE-4E vs MoE-8E vs MoE-16E. "
                             "Requires --test-moe-ffn.")

    # ==========================================================================
    # V10.7: HIERARCHICAL PHASE-QUAD (HP-QUAD) BENCHMARKS
    # ==========================================================================
    # Tests Hierarchical Phase-Quad for multi-timescale processing.
    # Based on HM-RNN: boundary detection, selective updates, hierarchical memory.
    parser.add_argument("--test-hp-quad", action="store_true",
                        help="Run HP-Quad benchmarks. Tests: "
                             "1) Throughput comparison (standard vs hierarchical), "
                             "2) Boundary detection quality, "
                             "3) Memory efficiency, "
                             "4) Long-range dependency handling, "
                             "5) Ablation studies.")
    parser.add_argument("--hp-num-levels", type=int, default=3,
                        help="Number of hierarchy levels. Default: 3")
    parser.add_argument("--hp-d-phase-levels", type=str, default="128,256,512",
                        help="Comma-separated phase dimensions per level. Default: 128,256,512")
    parser.add_argument("--hp-chunk-sizes", type=str, default="1,8,64",
                        help="Comma-separated chunk sizes per level. Default: 1,8,64")
    parser.add_argument("--hp-boundary-threshold", type=float, default=0.5,
                        help="Threshold for boundary detection. Default: 0.5")
    parser.add_argument("--hp-target-boundary-rate", type=float, default=0.15,
                        help="Target boundary rate (for regularization). Default: 0.15")
    parser.add_argument("--hp-boundary-ablation", action="store_true",
                        help="Run boundary detection ablation study. "
                             "Tests different thresholds: 0.3, 0.5, 0.7. "
                             "Requires --test-hp-quad.")

    # ==========================================================================
    # V10.8: RLM-PHASE-QUAD INTEGRATION BENCHMARKS
    # ==========================================================================
    # Tests RLM + Phase-Quad integration for unlimited context handling.
    # Combines RLM orchestration with efficient Phase-Quad processing.
    parser.add_argument("--test-rlm-phase-quad", action="store_true",
                        help="Run RLM-Phase-Quad integration benchmarks. Tests: "
                             "1) End-to-end performance (latency, throughput), "
                             "2) Chunking quality (boundary-aware vs fixed), "
                             "3) Phase State persistence effectiveness, "
                             "4) Scalability with context size, "
                             "5) Memory bank utilization.")
    parser.add_argument("--rlm-pq-max-context", type=int, default=100000,
                        help="Maximum context size for RLM-PQ benchmarks. Default: 100000")
    parser.add_argument("--rlm-pq-max-depth", type=int, default=3,
                        help="Maximum recursion depth. Default: 3")
    parser.add_argument("--rlm-pq-quality-threshold", type=float, default=0.7,
                        help="Quality threshold for recursion control. Default: 0.7")
    parser.add_argument("--rlm-pq-min-chunk", type=int, default=100,
                        help="Minimum chunk size in tokens. Default: 100")
    parser.add_argument("--rlm-pq-max-chunk", type=int, default=4096,
                        help="Maximum chunk size in tokens. Default: 4096")
    parser.add_argument("--rlm-pq-scalability-test", action="store_true",
                        help="Run extended scalability tests up to 1M tokens. "
                             "Requires --test-rlm-phase-quad.")

    # ==========================================================================
    # V10.9: REFLECTIVE PHASE-QUAD BENCHMARKS
    # ==========================================================================
    # Tests self-reflective latent-space revision with neural critic.
    # Key innovation: O(N) revision vs O(N^2) for token-based approaches.
    parser.add_argument("--test-reflective-phase-quad", action="store_true",
                        help="Run Reflective Phase-Quad benchmarks. Tests: "
                             "1) Critic performance (quality estimation), "
                             "2) Decision gate behavior (threshold calibration), "
                             "3) Revision encoder effectiveness, "
                             "4) Full block with revision loop, "
                             "5) Reflective vs Single-Pass comparison, "
                             "6) Quality trajectory analysis.")
    parser.add_argument("--rpq-max-revisions", type=int, default=3,
                        help="Maximum revision attempts. Default: 3")
    parser.add_argument("--rpq-threshold-high", type=float, default=0.85,
                        help="Quality threshold for immediate acceptance. Default: 0.85")
    parser.add_argument("--rpq-threshold-low", type=float, default=0.50,
                        help="Quality threshold below which major revision needed. Default: 0.50")
    parser.add_argument("--rpq-batch-size", type=int, default=4,
                        help="Batch size for RPQ benchmarks. Default: 4")
    parser.add_argument("--rpq-seq-len", type=int, default=64,
                        help="Sequence length for RPQ benchmarks. Default: 64")
    parser.add_argument("--rpq-ablation", action="store_true",
                        help="Run ablation study comparing different configurations. "
                             "Requires --test-reflective-phase-quad.")
    parser.add_argument("--rpq-adaptive-threshold", action="store_true",
                        help="Use learned adaptive thresholds instead of fixed. "
                             "Thresholds are predicted based on input context.")

    # ==========================================================================
    # V10.10: CAUSAL WORLD MODEL BENCHMARKS
    # ==========================================================================
    # Tests explicit causal graphs, intervention modeling, and world simulation.
    parser.add_argument("--test-causal-world-model", action="store_true",
                        help="Run Causal World Model benchmarks. Tests: "
                             "1) DAG constraint enforcement (NOTEARS-style), "
                             "2) Causal graph learning from embeddings, "
                             "3) Intervention modeling (do-calculus), "
                             "4) Counterfactual reasoning, "
                             "5) World simulation (multi-step rollouts).")
    parser.add_argument("--cwm-max-variables", type=int, default=128,
                        help="Maximum number of causal variables. Default: 128")
    parser.add_argument("--cwm-dag-penalty", type=float, default=0.1,
                        help="Weight for DAG constraint in loss. Default: 0.1")
    parser.add_argument("--cwm-edge-threshold", type=float, default=0.5,
                        help="Threshold for edge existence. Default: 0.5")
    parser.add_argument("--cwm-benchmark-discovery", action="store_true",
                        help="Run extended causal discovery benchmarks.")
    parser.add_argument("--cwm-benchmark-intervention", action="store_true",
                        help="Run extended intervention benchmarks.")
    parser.add_argument("--cwm-benchmark-counterfactual", action="store_true",
                        help="Run extended counterfactual benchmarks.")

    # ==========================================================================
    # CAUSAL DATASETS (COPA, e-CARE, Synthetic SCM)
    # ==========================================================================
    parser.add_argument("--cwm-dataset", type=str, default="scm",
                        choices=["copa", "ecare", "scm", "all"],
                        help="Causal dataset to use. 'all' loads all three. Default: scm")
    parser.add_argument("--cwm-dataset-split", type=str, default="train",
                        help="Dataset split (train/validation/test). Default: train")
    parser.add_argument("--cwm-dataset-samples", type=int, default=1000,
                        help="Number of samples to load. Default: 1000")

    # COPA-specific
    parser.add_argument("--copa-split", type=str, default="train",
                        help="COPA dataset split. Default: train")

    # e-CARE-specific
    parser.add_argument("--ecare-split", type=str, default="train",
                        help="e-CARE dataset split. Default: train")
    parser.add_argument("--ecare-explanations", action="store_true", default=True,
                        help="Include causal explanations in e-CARE data.")

    # Synthetic SCM-specific
    parser.add_argument("--scm-num-samples", type=int, default=10000,
                        help="Number of SCM samples to generate. Default: 10000")
    parser.add_argument("--scm-num-variables", type=int, default=10,
                        help="Number of variables in SCM. Default: 10")
    parser.add_argument("--scm-edge-probability", type=float, default=0.3,
                        help="Edge probability in SCM DAG. Default: 0.3")
    parser.add_argument("--scm-noise-std", type=float, default=0.1,
                        help="Noise standard deviation in SCM. Default: 0.1")
    parser.add_argument("--scm-intervention-prob", type=float, default=0.2,
                        help="Probability of interventional examples. Default: 0.2")
    parser.add_argument("--scm-counterfactuals", action="store_true", default=True,
                        help="Include counterfactual examples in SCM data.")

    # ==========================================================================
    # V10.11: SPATIAL-CAUSAL MODULE BENCHMARKS
    # ==========================================================================
    # Tests spatial reasoning integrated with causal reasoning:
    #   - Spatial state tracking (position, orientation, velocity)
    #   - Physics-grounded causal edges (gravity, contact, collision)
    #   - Spatial interventions (move, rotate, place)
    #   - Spatial counterfactual reasoning
    parser.add_argument("--test-spatial-causal", action="store_true",
                        help="Run Spatial-Causal Module benchmarks. Tests: "
                             "1) Spatial state encoding, "
                             "2) Spatial relation prediction, "
                             "3) Physics causal edge computation, "
                             "4) Spatial interventions (move/rotate/place), "
                             "5) Physics simulation, "
                             "6) Spatial counterfactual reasoning.")

    # Spatial config
    parser.add_argument("--scm-hidden-dim", type=int, default=256,
                        help="Hidden dimension for spatial module. Default: 256")
    parser.add_argument("--scm-max-objects", type=int, default=64,
                        help="Maximum number of spatial objects. Default: 64")
    parser.add_argument("--scm-num-heads", type=int, default=8,
                        help="Number of attention heads. Default: 8")

    # Physics config
    parser.add_argument("--scm-gravity", type=float, nargs=3, default=[0.0, -9.81, 0.0],
                        help="Gravity vector [x, y, z]. Default: [0, -9.81, 0]")
    parser.add_argument("--scm-simulation-dt", type=float, default=0.01,
                        help="Simulation timestep. Default: 0.01")
    parser.add_argument("--scm-simulation-steps", type=int, default=100,
                        help="Maximum simulation steps. Default: 100")
    parser.add_argument("--scm-propagation-radius", type=float, default=2.0,
                        help="Radius for effect propagation. Default: 2.0")
    parser.add_argument("--scm-contact-threshold", type=float, default=0.1,
                        help="Distance threshold for contact detection. Default: 0.1")

    # Test scenarios
    parser.add_argument("--scm-scenario", type=str, default="falling_ball",
                        choices=["falling_ball", "collision", "domino", "stacking", "all"],
                        help="Test scenario to run. Default: falling_ball")

    # ==========================================================================
    # V10.12: PHASE-AWARE ADAPTATION BENCHMARKS (IA³ + SURGICAL LORA)
    # ==========================================================================
    # Tests controlled plasticity for Phase Quad:
    #   - IA³ multiplicative gates (primary, phase-congruent)
    #   - Surgical LoRA on projections only (secondary, when needed)
    #   - Identity preservation, training, save/load, merge, ablation
    parser.add_argument("--test-adaptation", action="store_true",
                        help="Run Phase-Aware Adaptation benchmarks. Tests: "
                             "1) Identity preservation (adapted=base at init), "
                             "2) IA3 gate training, "
                             "3) LoRA projection training (if --adapt-lora), "
                             "4) Regularization behavior, "
                             "5) Save/load adapter, "
                             "6) LoRA merge/unmerge, "
                             "7) Ablation comparison (if --adapt-ablation), "
                             "8) Throughput overhead.")

    # Adaptation model config (separate from main probe model)
    parser.add_argument("--adapt-embed-dim", type=int, default=256,
                        help="Embedding dimension for adaptation benchmark model. Default: 256")
    parser.add_argument("--adapt-num-heads", type=int, default=8,
                        help="Number of attention heads. Default: 8")
    parser.add_argument("--adapt-num-blocks", type=int, default=3,
                        help="Number of DiT blocks. Default: 3")
    parser.add_argument("--adapt-topk", type=int, default=16,
                        help="TopK proposals for quad retriever. Default: 16")
    parser.add_argument("--adapt-window-size", type=int, default=4,
                        help="Window size for local attention. Default: 4")

    # IA³ config
    parser.add_argument("--adapt-ia3", action="store_true", default=True,
                        help="Enable IA3 gates (default: True)")
    parser.add_argument("--no-adapt-ia3", dest="adapt_ia3", action="store_false",
                        help="Disable IA3 gates")
    parser.add_argument("--adapt-ia3-reg-lambda", type=float, default=0.01,
                        help="IA3 regularization lambda ||g-1||^2. Default: 0.01")

    # LoRA config
    parser.add_argument("--adapt-lora", action="store_true",
                        help="Enable surgical LoRA on quad projections (default: disabled)")
    parser.add_argument("--adapt-lora-rank", type=int, default=8,
                        help="LoRA rank r (keep small: 4-8). Default: 8")
    parser.add_argument("--adapt-lora-alpha", type=float, default=16.0,
                        help="LoRA scaling alpha (typical: 2*rank). Default: 16.0")

    # Training config
    parser.add_argument("--adapt-train-steps", type=int, default=100,
                        help="Training steps for adaptation benchmark. Default: 100")
    parser.add_argument("--adapt-bench-iters", type=int, default=20,
                        help="Iterations for throughput benchmark. Default: 20")

    # Ablation
    parser.add_argument("--adapt-ablation", action="store_true",
                        help="Run ablation: IA3-only vs LoRA-only vs Combined. "
                             "Requires --test-adaptation.")

    # Device
    parser.add_argument("--device", type=str,
                        default="cuda" if torch.cuda.is_available() else "cpu")

    args = parser.parse_args()

    # V10.6.2: Configure no-write contract enforcement
    set_no_write_contract_enforcement(args.enforce_no_write_contracts)
    if args.enforce_no_write_contracts:
        print("V10.6.2: No-write contract enforcement ENABLED")
    else:
        print("V10.6.2: No-write contract enforcement DISABLED (for performance)")

    # Parse curriculum
    curriculum = [float(x) for x in args.curriculum.split(",")]
    # Pad/truncate to match num_layers
    while len(curriculum) < args.num_layers:
        curriculum.append(curriculum[-1] if curriculum else 0.5)
    curriculum = curriculum[:args.num_layers]

    # Build config
    config = Config(
        d_model=args.d_model,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        d_ff=args.d_ff,
        num_steps=args.num_steps,
        batch_size=args.batch_size,
        lr=args.lr,
        train_samples=args.train_samples,
        test_samples_per_split=args.test_samples,
        bind_ratio=args.bind_ratio,
        train_chain_length=(args.train_chain_min, args.train_chain_max),
        test_chain_length=(args.test_chain_min, args.test_chain_max),
        persist_chain_length=(args.persist_chain_min, args.persist_chain_max),
        match_params=args.match_params,
        bounded_phase=args.bounded_phase,
        dual_channel_mode=args.dual_channel_mode,
        alignment_authority=args.alignment_authority,
        alignment_clamp_min=args.alignment_clamp_min,
        alignment_clamp_max=args.alignment_clamp_max,
        alignment_reduction=args.alignment_reduction,  # V10.6.3
        strict_control_contract=args.strict_control_contract,  # V10.6.3
        device=args.device,
    )

    # ==========================================================================
    # REAL LANGUAGE MODE: Route to WikiText training
    # ==========================================================================
    if args.real_language:
        train_real_language(args, config, curriculum)
        return

    # ==========================================================================
    # V10.2.1 CHUNKING TESTS: Route to chunking architecture tests
    # ==========================================================================
    if args.test_chunking_v10:
        run_chunking_tests_v10(args, config)
        return

    # ==========================================================================
    # V10.5: INTERFERENCE BENCHMARKS: Route to interference scoring tests
    # ==========================================================================
    if args.test_interference:
        run_interference_benchmark_integration(args, config)
        return

    # ==========================================================================
    # V10.6: MOE FFN BENCHMARKS: Route to MoE FFN tests
    # ==========================================================================
    if args.test_moe_ffn:
        run_moe_ffn_benchmark_integration(args, config)
        return

    # ==========================================================================
    # V10.7: HP-QUAD BENCHMARKS: Route to Hierarchical Phase-Quad tests
    # ==========================================================================
    if args.test_hp_quad:
        run_hp_quad_benchmark_integration(args, config)
        return

    # ==========================================================================
    # V10.8: RLM-PHASE-QUAD BENCHMARKS: Route to integration tests
    # ==========================================================================
    if args.test_rlm_phase_quad:
        run_rlm_phase_quad_benchmark_integration(args, config)
        return

    # ==========================================================================
    # V10.9: REFLECTIVE PHASE-QUAD BENCHMARKS: Route to self-reflection tests
    # ==========================================================================
    if args.test_reflective_phase_quad:
        run_reflective_phase_quad_benchmark_integration(args, config)
        return

    # ==========================================================================
    # V10.10: CAUSAL WORLD MODEL BENCHMARKS: Route to causal reasoning tests
    # ==========================================================================
    if args.test_causal_world_model:
        run_causal_world_model_benchmark_integration(args, config)
        return

    # ==========================================================================
    # V10.11: SPATIAL-CAUSAL MODULE BENCHMARKS: Route to spatial reasoning tests
    # ==========================================================================
    if args.test_spatial_causal:
        run_spatial_causal_benchmark_integration(args, config)
        return

    # ==========================================================================
    # V10.12: PHASE-AWARE ADAPTATION: Route to IA³ + LoRA benchmarks
    # ==========================================================================
    if args.test_adaptation:
        run_adaptation_benchmark_integration(args, config)
        return

    print("=" * 70)
    print("HARD DIAGNOSTIC PROBE: PhaseAttention vs Quadratic Attention")
    print("=" * 70)
    print("\nThis benchmark tests TRUE RELATIONAL GENERALIZATION:")
    print("  - Held-out roles (R4-R6 never seen in training)")
    print("  - Open-world entities (E8-E15 never seen in training)")
    print("  - Long chains (6-8 steps vs 3-5 in training)")
    print("  - Schema composition (no single-pattern shortcuts)")
    print()

    # Vocabulary
    vocab = HardVocabulary()
    print(f"Vocabulary: {vocab.vocab_size} tokens")
    print(f"  Train entities: E0-E7 ({len(vocab.train_entities)})")
    print(f"  Test entities:  E8-E15 ({len(vocab.test_entities)})")
    print(f"  Train roles:    R0-R3 ({len(vocab.train_roles)})")
    print(f"  Test roles:     R4-R6 ({len(vocab.test_roles)})")

    # Datasets
    print(f"\nCreating datasets...")
    print(f"  BIND ratio: {config.bind_ratio:.0%}")
    print(f"  Train chain length: {config.train_chain_length}")
    print(f"  Test chain length: {config.test_chain_length}")
    print(f"  Persist chain length: {config.persist_chain_length}")

    train_ds = HardProbeDataset(
        vocab, SplitType.TRAIN, config.train_samples, config.max_seq_len,
        config.train_chain_length, config.bind_ratio, seed=42
    )

    test_datasets = {
        SplitType.TEST_ROLES: HardProbeDataset(
            vocab, SplitType.TEST_ROLES, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=100
        ),
        SplitType.TEST_ENTITIES: HardProbeDataset(
            vocab, SplitType.TEST_ENTITIES, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=200
        ),
        SplitType.TEST_BOTH: HardProbeDataset(
            vocab, SplitType.TEST_BOTH, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=300
        ),
        SplitType.TEST_LONG: HardProbeDataset(
            vocab, SplitType.TEST_LONG, config.test_samples_per_split,
            config.max_seq_len, config.test_chain_length, config.bind_ratio, seed=400
        ),
        # Pure persistence test: BIND+QUERY only, long chains (8-12)
        SplitType.TEST_PERSIST: HardProbeDataset(
            vocab, SplitType.TEST_PERSIST, config.test_samples_per_split,
            config.max_seq_len, config.persist_chain_length, config.bind_ratio, seed=500
        ),
    }

    train_loader = DataLoader(train_ds, batch_size=config.batch_size,
                              shuffle=True, collate_fn=collate_fn)
    test_loaders = {
        split: DataLoader(ds, batch_size=config.batch_size,
                          shuffle=False, collate_fn=collate_fn)
        for split, ds in test_datasets.items()
    }

    print(f"\nTrain samples: {len(train_ds)}")
    for split, ds in test_datasets.items():
        print(f"  {split.value}: {len(ds)}")

    # Show examples
    print("\n--- Example Samples ---")
    for i in range(min(5, len(train_ds))):
        ids, target, explanation = train_ds.samples[i]
        print(f"  {vocab.decode(ids)} → {vocab.id2name.get(target, target)}")
        print(f"    ({explanation})")

    # Models
    print("\n--- Creating Models ---")
    num_classes = len(vocab.entities)  # Classify into entity slots

    # Compute parameter matching if needed
    extra_ff = 0
    if config.match_params:
        param_diff = compute_param_diff(config.d_model, config.num_heads, config.num_layers)
        # Add to d_ff to approximately match
        extra_ff = param_diff // (2 * config.d_model * config.num_layers)
        print(f"Parameter matching: adding {extra_ff} to d_ff for quadratic")

    # Operation tokens for phase-conditioned shifts (NEG, PERMUTE, OVERWRITE)
    operation_tokens = [vocab.NEG, vocab.PERMUTE, vocab.OVERWRITE]
    print(f"Operation tokens for phase shifts: {[vocab.id2name[t] for t in operation_tokens]}")

    model_quad = HardProbeTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes,
        use_phase=False, extra_ff_per_layer=extra_ff if config.match_params else 0
    ).to(config.device)

    model_phase = HardProbeTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes,
        use_phase=True, extra_ff_per_layer=0,
        operation_tokens=operation_tokens,  # Enable operation-conditioned phase shifts
        bounded_phase=config.bounded_phase,  # V9.9.11: Constrain φ to [-π, π]
        dual_channel_mode=config.dual_channel_mode,  # V10.3.8: Dual-channel attention
        alignment_authority=config.alignment_authority,  # V10.3.8: Alignment authority
    ).to(config.device)

    print(f"Quadratic params: {model_quad.count_params():,}")
    print(f"Phase params:     {model_phase.count_params():,}")
    if config.bounded_phase:
        print(f"  Bounded Phase: ENABLED (π*sin() bounds φ to [-π, π])")
    else:
        print(f"  Bounded Phase: DISABLED (raw linear projection)")
    if config.dual_channel_mode:
        print(f"  Dual-Channel Mode: ENABLED (α={config.alignment_authority})")
    if config.match_params:
        diff = abs(model_phase.count_params() - model_quad.count_params())
        print(f"  Param difference: {diff:,} ({diff / model_phase.count_params() * 100:.1f}%)")

    # Hybrid model with inverted curriculum (v3)
    model_hybrid = None
    model_hybrid_std = None  # For curriculum comparison
    opt_hybrid = None
    opt_hybrid_std = None

    if args.run_hybrid or args.compare_curricula:
        # Inverted curriculum: Phase-heavy early, Quadratic-heavy late
        inverted_curriculum = curriculum  # From CLI arg
        print(f"\n--- Hybrid Model (INVERTED CURRICULUM) ---")
        print(f"  Curriculum: {' → '.join(f'L{i}:{r*100:.0f}%P' for i, r in enumerate(inverted_curriculum))}")
        print(f"  Interpretation: Phase-heavy early (state capture) → Quadratic-heavy late (reasoning)")

        model_hybrid = HybridTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            curriculum=inverted_curriculum,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
            dual_channel_mode=config.dual_channel_mode,
            alignment_authority=config.alignment_authority,
        ).to(config.device)
        print(f"  Hybrid params: {model_hybrid.count_params():,}")

        opt_hybrid = torch.optim.AdamW(model_hybrid.parameters(), lr=config.lr,
                                        weight_decay=config.weight_decay)

    if args.compare_curricula:
        # Standard curriculum: Quadratic-heavy early, Phase-heavy late (for comparison)
        standard_curriculum = list(reversed(curriculum))
        print(f"\n--- Hybrid Model (STANDARD CURRICULUM - for comparison) ---")
        print(f"  Curriculum: {' → '.join(f'L{i}:{r*100:.0f}%P' for i, r in enumerate(standard_curriculum))}")
        print(f"  Interpretation: Quadratic-heavy early → Phase-heavy late")

        model_hybrid_std = HybridTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            curriculum=standard_curriculum,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
            dual_channel_mode=config.dual_channel_mode,
            alignment_authority=config.alignment_authority,
        ).to(config.device)
        print(f"  Standard Hybrid params: {model_hybrid_std.count_params():,}")

        opt_hybrid_std = torch.optim.AdamW(model_hybrid_std.parameters(), lr=config.lr,
                                            weight_decay=config.weight_decay)

    # Protected Phase model (v5) - Phase accumulates, Quad queries
    model_protected = None
    opt_protected = None

    if args.protected_phase:
        print(f"\n--- Protected Phase Model (v5) ---")
        print(f"  Architecture: Phase → Memory State → Quadratic Query")
        print(f"  Phase's job:  Accumulate bindings via O(n) cumsum")
        print(f"  Quad's job:   Query memory via O(n²) attention")
        print(f"  Key insight:  No gradient competition - they collaborate")

        model_protected = ProtectedPhaseTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
        ).to(config.device)
        print(f"  Protected params: {model_protected.count_params():,}")

        opt_protected = torch.optim.AdamW(model_protected.parameters(), lr=config.lr,
                                           weight_decay=config.weight_decay)

    # Optimizers
    opt_quad = torch.optim.AdamW(model_quad.parameters(), lr=config.lr,
                                  weight_decay=config.weight_decay)
    opt_phase = torch.optim.AdamW(model_phase.parameters(), lr=config.lr,
                                   weight_decay=config.weight_decay)

    # Training
    print(f"\n--- Training for {config.num_steps} steps ---")
    train_iter = iter(train_loader)
    step = 0

    # Loss tracking for training dynamics analysis
    loss_history = {
        "quad": [],
        "phase": [],
        "hybrid": [],
        "hybrid_std": [],
        "protected": [],
    }

    while step < config.num_steps:
        try:
            ids, targets, _ = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            ids, targets, _ = next(train_iter)

        ids, targets = ids.to(config.device), targets.to(config.device)

        # Convert targets to class indices
        target_idx = torch.tensor([
            vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
            for t in targets
        ], device=config.device)

        # Train quadratic
        model_quad.train()
        opt_quad.zero_grad()
        loss_q = F.cross_entropy(model_quad(ids), target_idx)
        loss_q.backward()
        opt_quad.step()

        # Train phase
        model_phase.train()
        opt_phase.zero_grad()
        loss_p = F.cross_entropy(model_phase(ids), target_idx)
        loss_p.backward()
        opt_phase.step()

        # Train hybrid (inverted curriculum)
        if model_hybrid is not None:
            model_hybrid.train()
            opt_hybrid.zero_grad()
            loss_h = F.cross_entropy(model_hybrid(ids), target_idx)
            loss_h.backward()
            opt_hybrid.step()

        # Train hybrid (standard curriculum - for comparison)
        if model_hybrid_std is not None:
            model_hybrid_std.train()
            opt_hybrid_std.zero_grad()
            loss_hs = F.cross_entropy(model_hybrid_std(ids), target_idx)
            loss_hs.backward()
            opt_hybrid_std.step()

        # Train protected phase (v5)
        loss_prot = None
        if model_protected is not None:
            model_protected.train()
            opt_protected.zero_grad()
            loss_prot = F.cross_entropy(model_protected(ids), target_idx)
            loss_prot.backward()
            opt_protected.step()

        # Track losses for training dynamics
        loss_history["quad"].append(loss_q.item())
        loss_history["phase"].append(loss_p.item())
        if model_hybrid is not None:
            loss_history["hybrid"].append(loss_h.item())
        if model_hybrid_std is not None:
            loss_history["hybrid_std"].append(loss_hs.item())
        if model_protected is not None:
            loss_history["protected"].append(loss_prot.item())

        step += 1

        if step % config.eval_every == 0 or step == config.num_steps:
            # Quick train accuracy check
            train_acc_q = evaluate(model_quad, train_loader, vocab, config.device)
            train_acc_p = evaluate(model_phase, train_loader, vocab, config.device)

            # Compute recent average loss (last eval_every steps)
            window = config.eval_every
            recent_loss_q = sum(loss_history["quad"][-window:]) / window
            recent_loss_p = sum(loss_history["phase"][-window:]) / window

            msg = f"Step {step:5d} | Acc: Q={train_acc_q:.3f} P={train_acc_p:.3f}"
            loss_msg = f" | Loss: Q={recent_loss_q:.3f} P={recent_loss_p:.3f}"

            if model_hybrid is not None:
                train_acc_h = evaluate(model_hybrid, train_loader, vocab, config.device)
                recent_loss_h = sum(loss_history["hybrid"][-window:]) / window
                msg += f" H={train_acc_h:.3f}"
                loss_msg += f" H={recent_loss_h:.3f}"
            if model_hybrid_std is not None:
                train_acc_hs = evaluate(model_hybrid_std, train_loader, vocab, config.device)
                recent_loss_hs = sum(loss_history["hybrid_std"][-window:]) / window
                msg += f" Hs={train_acc_hs:.3f}"
                loss_msg += f" Hs={recent_loss_hs:.3f}"
            if model_protected is not None:
                train_acc_prot = evaluate(model_protected, train_loader, vocab, config.device)
                recent_loss_prot = sum(loss_history["protected"][-window:]) / window
                msg += f" Prot={train_acc_prot:.3f}"
                loss_msg += f" Prot={recent_loss_prot:.3f}"

                # R_k health metrics
                health = model_protected.get_phase_health()
                msg += f" | R_k={health['r_k_mean']:.3f}±{health['r_k_std']:.3f}"

            print(msg + loss_msg)

    # ==========================================================================
    # TRAINING DYNAMICS ANALYSIS
    # ==========================================================================
    print("\n" + "=" * 70)
    print("TRAINING DYNAMICS ANALYSIS")
    print("=" * 70)

    def compute_loss_stats(losses, name, window=1000):
        """Compute loss statistics for training dynamics."""
        if not losses:
            return None
        early = losses[:window] if len(losses) >= window else losses
        late = losses[-window:] if len(losses) >= window else losses
        return {
            "name": name,
            "early_mean": sum(early) / len(early),
            "late_mean": sum(late) / len(late),
            "final": losses[-1],
            "improvement": (sum(early) / len(early)) - (sum(late) / len(late)),
        }

    print(f"\n--- Loss Dynamics (early vs late {min(1000, len(loss_history['quad']))} steps) ---")
    print(f"{'Model':<12} {'Early Loss':>12} {'Late Loss':>12} {'Improvement':>12}")
    print("-" * 50)

    for model_name in ["quad", "phase", "protected"]:
        if loss_history[model_name]:
            stats = compute_loss_stats(loss_history[model_name], model_name)
            print(f"{stats['name']:<12} {stats['early_mean']:>12.4f} {stats['late_mean']:>12.4f} {stats['improvement']:>+12.4f}")

    # Check for Phase plateau (red flag)
    if loss_history["protected"]:
        early_phase_loss = sum(loss_history["protected"][:min(2000, len(loss_history["protected"]))]) / min(2000, len(loss_history["protected"]))
        late_phase_loss = sum(loss_history["protected"][-1000:]) / min(1000, len(loss_history["protected"]))
        if early_phase_loss - late_phase_loss < 0.1:
            print(f"\n  ⚠️  WARNING: Protected Phase loss barely improved ({early_phase_loss:.4f} → {late_phase_loss:.4f})")
            print(f"     This may indicate Phase is not learning or Quad is bypassing Phase.")

    # R_k Health Report
    if model_protected is not None:
        print(f"\n--- Phase Health (R_k = amplitude) ---")
        health = model_protected.get_phase_health()
        print(f"  R_k mean:  {health['r_k_mean']:.4f}")
        print(f"  R_k std:   {health['r_k_std']:.4f}")
        print(f"  R_k range: [{health['r_k_min']:.4f}, {health['r_k_max']:.4f}]")

        # Interpret health
        if health['r_k_mean'] < 0.1:
            print(f"\n  🚨 R_k → 0: Phase COLLAPSED (amplitude too small)")
        elif health['r_k_mean'] > 0.9:
            print(f"\n  🚨 R_k → 1: Phase DEGENERATE (amplitude saturated)")
        elif 0.3 <= health['r_k_mean'] <= 0.7:
            print(f"\n  ✅ R_k in healthy range (0.3-0.7)")
        else:
            print(f"\n  ⚠️  R_k outside ideal range but not critical")

    # ==========================================================================
    # FINAL EVALUATION (SEPARATE REPORTING - NO AVERAGING)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("FINAL RESULTS: GENERALIZATION TEST")
    print("=" * 70)

    # Train accuracy
    train_acc_q = evaluate(model_quad, train_loader, vocab, config.device)
    train_acc_p = evaluate(model_phase, train_loader, vocab, config.device)
    train_acc_h = evaluate(model_hybrid, train_loader, vocab, config.device) if model_hybrid else None
    train_acc_hs = evaluate(model_hybrid_std, train_loader, vocab, config.device) if model_hybrid_std else None
    train_acc_prot = evaluate(model_protected, train_loader, vocab, config.device) if model_protected else None

    print(f"\n--- Training Accuracy (should be high for all) ---")
    print(f"Quadratic:        {train_acc_q*100:.1f}%")
    print(f"Phase:            {train_acc_p*100:.1f}%")
    if train_acc_h is not None:
        print(f"Hybrid (Inv):     {train_acc_h*100:.1f}%")
    if train_acc_hs is not None:
        print(f"Hybrid (Std):     {train_acc_hs*100:.1f}%")
    if train_acc_prot is not None:
        print(f"Protected:        {train_acc_prot*100:.1f}%")

    # Per-split test accuracy (NO AVERAGING)
    results_quad = evaluate_all_splits(model_quad, test_loaders, vocab, config.device)
    results_phase = evaluate_all_splits(model_phase, test_loaders, vocab, config.device)
    results_hybrid = evaluate_all_splits(model_hybrid, test_loaders, vocab, config.device) if model_hybrid else None
    results_hybrid_std = evaluate_all_splits(model_hybrid_std, test_loaders, vocab, config.device) if model_hybrid_std else None
    results_protected = evaluate_all_splits(model_protected, test_loaders, vocab, config.device) if model_protected else None

    # Protected Phase results (v5)
    if model_protected is not None:
        print(f"\n--- PROTECTED PHASE RESULTS (v5) ---")
        print(f"    Architecture: Phase accumulates → Quad queries (no competition)")
        print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'Protect':>8} {'Best':>8}")
        print("-" * 52)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            prot = results_protected[split.value]
            scores = {"Quad": q, "Phase": p, "Protect": prot}
            best = max(scores, key=scores.get)
            print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {prot*100:>7.1f}% {best:>8}")

        # Summary
        prot_avg = sum(results_protected.values()) / len(results_protected)
        q_avg = sum(results_quad.values()) / len(results_quad)
        p_avg = sum(results_phase.values()) / len(results_phase)

        print(f"\n  Average Test Accuracy:")
        print(f"    Quadratic:  {q_avg*100:.1f}%")
        print(f"    Pure Phase: {p_avg*100:.1f}%")
        print(f"    Protected:  {prot_avg*100:.1f}%")

        if prot_avg > max(q_avg, p_avg) + 0.02:
            print(f"\n  → PROTECTED PHASE WINS by {(prot_avg - max(q_avg, p_avg))*100:.1f}%")
            print(f"    Phase and Quadratic collaborate better than compete!")
        elif prot_avg > p_avg + 0.02:
            print(f"\n  → Protected beats Pure Phase by {(prot_avg - p_avg)*100:.1f}%")
            print(f"    Quadratic querying helps Phase's accumulated state")

    if model_hybrid is not None:
        print(f"\n--- Test Accuracy by Generalization Type (FULL COMPARISON) ---")
        if model_hybrid_std is not None:
            print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'HybInv':>8} {'HybStd':>8} {'Best':>8}")
            print("-" * 64)
        else:
            print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'HybInv':>8} {'Best':>8}")
            print("-" * 52)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            h = results_hybrid[split.value]
            scores = {"Quad": q, "Phase": p, "HybInv": h}

            if model_hybrid_std is not None:
                hs = results_hybrid_std[split.value]
                scores["HybStd"] = hs
                best = max(scores, key=scores.get)
                print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {h*100:>7.1f}% {hs*100:>7.1f}% {best:>8}")
            else:
                best = max(scores, key=scores.get)
                print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {h*100:>7.1f}% {best:>8}")

        # Summary: Which curriculum wins?
        if model_hybrid_std is not None:
            print(f"\n--- CURRICULUM COMPARISON SUMMARY ---")
            inv_avg = sum(results_hybrid.values()) / len(results_hybrid)
            std_avg = sum(results_hybrid_std.values()) / len(results_hybrid_std)
            q_avg = sum(results_quad.values()) / len(results_quad)
            p_avg = sum(results_phase.values()) / len(results_phase)

            print(f"Average Test Accuracy:")
            print(f"  Quadratic:        {q_avg*100:.1f}%")
            print(f"  Pure Phase:       {p_avg*100:.1f}%")
            print(f"  Hybrid (Inv):     {inv_avg*100:.1f}%  [Phase early → Quad late]")
            print(f"  Hybrid (Std):     {std_avg*100:.1f}%  [Quad early → Phase late]")

            if inv_avg > std_avg + 0.02:
                print(f"\n  → INVERTED CURRICULUM WINS by {(inv_avg - std_avg)*100:.1f}%")
                print(f"    Supports: Phase = STATE mechanism, Quadratic = REASONING mechanism")
            elif std_avg > inv_avg + 0.02:
                print(f"\n  → STANDARD CURRICULUM WINS by {(std_avg - inv_avg)*100:.1f}%")
                print(f"    Counter-evidence: Original hypothesis may be correct")
            else:
                print(f"\n  → CURRICULA ARE COMPARABLE (diff: {abs(inv_avg - std_avg)*100:.1f}%)")
    else:
        # Original output format without hybrid
        print(f"\n--- Test Accuracy by Generalization Type (NO AVERAGING) ---")
        print(f"{'Split':<20} {'Quadratic':>12} {'Phase':>12} {'Delta':>12}")
        print("-" * 56)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            delta = p - q
            marker = "**" if delta > 0.1 else ""
            print(f"{split.value:<20} {q*100:>11.1f}% {p*100:>11.1f}% {delta*100:>+11.1f}% {marker}")

    # Phase diagnostics
    print(f"\n--- Phase Health ---")
    model_phase.enable_diagnostics(True)
    # Run one batch to capture diagnostics
    with torch.no_grad():
        sample_ids, _, _ = next(iter(train_loader))
        _ = model_phase(sample_ids.to(config.device))
    r_k = model_phase.get_R_k()
    model_phase.enable_diagnostics(False)
    print(f"R_k (mean resultant length): {r_k:.4f}")
    print(f"  Interpretation: {'HEALTHY (diverse phases)' if r_k < 0.3 else 'COLLAPSED (phases aligned)'}")

    # Ablation (on test_roles split)
    print(f"\n--- CAUSALITY TEST: Phase Ablation (on test_roles) ---")
    test_roles_loader = test_loaders[SplitType.TEST_ROLES]
    ablation = run_ablation(model_phase, test_roles_loader, vocab, config.device)
    baseline = ablation["none"]

    print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12}")
    print("-" * 36)
    for mode, acc in ablation.items():
        delta = acc - baseline
        print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}%")

    # ==========================================================================
    # HYBRID ABLATION TESTS (v4) - Is Phase decorative or useful in hybrids?
    # ==========================================================================
    ablation_hybrid_inv = None
    ablation_hybrid_std = None

    if model_hybrid is not None:
        print(f"\n--- HYBRID ABLATION: HybridInv (Phase early → Quad late) ---")
        print(f"    Testing if Phase in EARLY layers contributes or is decorative")
        ablation_hybrid_inv = run_ablation(model_hybrid, test_roles_loader, vocab, config.device)
        baseline_inv = ablation_hybrid_inv["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_hybrid_inv.items():
            delta = acc - baseline_inv
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

    if model_hybrid_std is not None:
        print(f"\n--- HYBRID ABLATION: HybridStd (Quad early → Phase late) ---")
        print(f"    Testing if Phase in LATE layers contributes or is decorative")
        ablation_hybrid_std = run_ablation(model_hybrid_std, test_roles_loader, vocab, config.device)
        baseline_std = ablation_hybrid_std["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_hybrid_std.items():
            delta = acc - baseline_std
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

    # Protected Phase ablation (v5)
    ablation_protected = None
    if model_protected is not None:
        print(f"\n--- PROTECTED PHASE ABLATION (v5) ---")
        print(f"    Testing if Phase contributes when it has PROTECTED role")
        print(f"    (Phase accumulates, Quad queries - no competition)")
        ablation_protected = run_ablation(model_protected, test_roles_loader, vocab, config.device)
        baseline_prot = ablation_protected["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_protected.items():
            delta = acc - baseline_prot
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

        drop_prot = baseline_prot - ablation_protected["scramble"]
        print(f"\n  Protected Phase ablation drop: {drop_prot*100:>+.1f}%")
        if drop_prot > 0.15:
            print(f"  → Phase is ESSENTIAL in protected architecture!")
            print(f"  → No gradient competition = Phase learns meaningful representations")
        elif drop_prot > 0.05:
            print(f"  → Phase CONTRIBUTES in protected architecture")
        else:
            print(f"  → Phase still decorative even when protected")

    # ==========================================================================
    # PHASE ROTATION TEST - Does phase encode relational structure?
    # ==========================================================================
    if args.rotation_test:
        rotation_angles = [float(x) for x in args.rotation_angles.split(",")]
        print(f"\n" + "=" * 70)
        print("PHASE ROTATION TEST")
        print("=" * 70)
        print("\nHypothesis: If phase encodes roles, rotating φ_q should shift bindings.")
        print(f"Testing angles: {rotation_angles}")

        # Test pure Phase model
        rotation_phase = run_rotation_test(
            model_phase, test_roles_loader, vocab, config.device, rotation_angles
        )
        print_rotation_test_results(rotation_phase, "Pure Phase")

        # Test Hybrid models if available
        if model_hybrid is not None:
            rotation_hybrid = run_rotation_test(
                model_hybrid, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_hybrid, "Hybrid (Inverted)")

        if model_hybrid_std is not None:
            rotation_hybrid_std = run_rotation_test(
                model_hybrid_std, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_hybrid_std, "Hybrid (Standard)")

        if model_protected is not None:
            rotation_protected = run_rotation_test(
                model_protected, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_protected, "Protected Phase")

        # Summary
        print(f"\n--- ROTATION TEST SUMMARY ---")
        print(f"  Pure Phase sensitivity:     {rotation_phase['sensitivity']*100:.2f}%")
        if model_hybrid is not None:
            print(f"  Hybrid (Inv) sensitivity:   {rotation_hybrid['sensitivity']*100:.2f}%")
        if model_hybrid_std is not None:
            print(f"  Hybrid (Std) sensitivity:   {rotation_hybrid_std['sensitivity']*100:.2f}%")
        if model_protected is not None:
            print(f"  Protected sensitivity:      {rotation_protected['sensitivity']*100:.2f}%")

        if rotation_phase['sensitivity'] > 0.10:
            print(f"\n  CONCLUSION: Phase encodes MEANINGFUL relational structure")
            print(f"             (rotation significantly affects binding retrieval)")
        elif rotation_phase['sensitivity'] > 0.03:
            print(f"\n  CONCLUSION: Phase shows PARTIAL relational encoding")
            print(f"             (moderate sensitivity to rotation)")
        else:
            print(f"\n  CONCLUSION: Phase is DECORATIVE (rotation has no effect)")
            print(f"             (phase not encoding relational structure)")

    # Summary comparison of ablation impacts
    if ablation_hybrid_inv is not None and ablation_hybrid_std is not None:
        print(f"\n--- ABLATION SUMMARY: Is Phase Decorative? ---")
        drop_pure = baseline - ablation["scramble"]
        drop_inv = ablation_hybrid_inv["none"] - ablation_hybrid_inv["scramble"]
        drop_std = ablation_hybrid_std["none"] - ablation_hybrid_std["scramble"]

        print(f"  Ablation drop (scramble):")
        print(f"    Pure Phase:   {drop_pure*100:>+6.1f}%  {'← Phase is PRIMARY' if drop_pure > 0.15 else ''}")
        print(f"    HybridInv:    {drop_inv*100:>+6.1f}%  {'← Phase EARLY matters' if drop_inv > 0.10 else '← Phase early is weak'}")
        print(f"    HybridStd:    {drop_std*100:>+6.1f}%  {'← Phase LATE matters' if drop_std > 0.10 else '← Phase late is DECORATIVE'}")

        print(f"\n  Conclusion:")
        if drop_std < 0.05:
            print(f"    → Phase is DECORATIVE when Quadratic dominates early")
            print(f"    → Quadratic 'steals' the learning signal")
            print(f"    → Consider: Protected Phase, Sequential, or Different Tasks")
        elif drop_inv < 0.05:
            print(f"    → Phase is DECORATIVE when it comes first")
            print(f"    → Phase can't establish useful representations alone")
            print(f"    → Quadratic late can compensate")
        elif drop_inv > drop_std:
            print(f"    → Phase EARLY contributes more than Phase LATE")
            print(f"    → Supports: Phase = state capture mechanism")
        else:
            print(f"    → Phase LATE contributes more than Phase EARLY")
            print(f"    → Supports: Phase = retrieval mechanism")

    # ==========================================================================
    # SCIENTIFIC VERDICT
    # ==========================================================================
    print("\n" + "=" * 70)
    print("SCIENTIFIC VERDICT")
    print("=" * 70)

    # Compute average test accuracy
    avg_test_q = sum(results_quad.values()) / len(results_quad)
    avg_test_p = sum(results_phase.values()) / len(results_phase)
    avg_test_h = sum(results_hybrid.values()) / len(results_hybrid) if results_hybrid else None
    avg_test_hs = sum(results_hybrid_std.values()) / len(results_hybrid_std) if results_hybrid_std else None

    # Criteria
    quad_memorizes = train_acc_q > 0.85
    quad_fails_generalization = avg_test_q < 0.50
    phase_generalizes = avg_test_p > avg_test_q + 0.15
    phase_is_causal = (baseline - ablation["scramble"]) > 0.1 or (baseline - ablation["freeze"]) > 0.1

    print(f"\nCriteria Check:")
    print(f"  [{'PASS' if quad_memorizes else 'FAIL'}] Quadratic memorizes training ({train_acc_q*100:.1f}% > 85%)")
    print(f"  [{'PASS' if quad_fails_generalization else 'FAIL'}] Quadratic fails generalization ({avg_test_q*100:.1f}% < 50%)")
    print(f"  [{'PASS' if phase_generalizes else 'FAIL'}] Phase outperforms quadratic by >15% ({(avg_test_p - avg_test_q)*100:.1f}%)")
    print(f"  [{'PASS' if phase_is_causal else 'FAIL'}] Phase ablation causes significant drops")

    # NEW: Inverted curriculum hypothesis (v3)
    if results_hybrid is not None:
        hybrid_beats_both = avg_test_h > max(avg_test_q, avg_test_p) + 0.02
        print(f"  [{'PASS' if hybrid_beats_both else 'FAIL'}] Hybrid (inverted) beats both pure models ({avg_test_h*100:.1f}% > {max(avg_test_q, avg_test_p)*100:.1f}%)")

        if results_hybrid_std is not None:
            inverted_beats_standard = avg_test_h > avg_test_hs + 0.02
            print(f"  [{'PASS' if inverted_beats_standard else 'FAIL'}] Inverted curriculum beats standard ({avg_test_h*100:.1f}% > {avg_test_hs*100:.1f}%)")

    # Verdict logic
    if results_hybrid is not None and results_hybrid_std is not None:
        # v3 verdict: Test the STATE vs REASONING hypothesis
        if avg_test_h > max(avg_test_q, avg_test_p, avg_test_hs) + 0.02:
            print("\n" + "=" * 70)
            print("[INVERTED CURRICULUM HYPOTHESIS SUPPORTED]")
            print("=" * 70)
            print("The Hybrid model with INVERTED curriculum achieves best generalization:")
            print(f"  - Phase early (state capture): {curriculum[0]*100:.0f}% → {curriculum[-1]*100:.0f}%")
            print(f"  - Quadratic late (reasoning):  {(1-curriculum[0])*100:.0f}% → {(1-curriculum[-1])*100:.0f}%")
            print(f"\nThis supports the hypothesis:")
            print(f"  PhaseAttention = STATE mechanism (O(n) memory)")
            print(f"  Quadratic      = REASONING mechanism (O(n²) attention)")
            print(f"\nOptimal architecture: Phase-heavy early layers + Quadratic-heavy late layers")
        elif avg_test_h > avg_test_hs + 0.02:
            print("\n[INVERTED > STANDARD]")
            print("Inverted curriculum outperforms standard, supporting Phase-as-state hypothesis.")
            print("But hybrid doesn't beat pure models — consider tuning curriculum ratios.")
        elif avg_test_hs > avg_test_h + 0.02:
            print("\n[STANDARD > INVERTED]")
            print("Standard curriculum outperforms inverted — counter to the hypothesis.")
            print("Phase may be better for reasoning after all, or task requires different mixing.")
        else:
            print("\n[CURRICULA COMPARABLE]")
            print("No significant difference between inverted and standard curriculum.")
            print("Try more extreme ratios: --curriculum 0.95,0.8,0.2,0.05")
    elif quad_memorizes and quad_fails_generalization and phase_generalizes and phase_is_causal:
        print("\n" + "=" * 70)
        print("[HYPOTHESIS STRONGLY SUPPORTED]")
        print("=" * 70)
        print("PhaseAttention demonstrates TRUE RELATIONAL GENERALIZATION:")
        print(f"  - Quadratic memorizes ({train_acc_q*100:.1f}%) but fails to generalize ({avg_test_q*100:.1f}%)")
        print(f"  - Phase generalizes significantly better ({avg_test_p*100:.1f}%)")
        print(f"  - Phase is causally necessary (ablations hurt performance)")
        print("\nThis is strong evidence that phase encodes RELATIONAL STRUCTURE,")
        print("not token-specific patterns.")
    elif phase_generalizes and phase_is_causal:
        print("\n[HYPOTHESIS SUPPORTED]")
        print("Phase shows generalization advantage, but quadratic didn't fail as hard as expected.")
        print("Consider increasing chain length or bind_ratio.")
    elif not quad_fails_generalization:
        print("\n[DATASET TOO EASY]")
        print(f"Quadratic achieved {avg_test_q*100:.1f}% on test — should be <50%.")
        print("Try: --test-chain-min 7 --test-chain-max 10 --bind-ratio 0.8")
    else:
        print("\n[INCONCLUSIVE]")
        print("Results do not clearly support or refute the hypothesis.")
        if results_hybrid is None:
            print("\nTry: --compare-curricula to test Phase-as-state hypothesis")

    print("=" * 70)


if __name__ == "__main__":
    main()
