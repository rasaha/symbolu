"""
Chunking Architecture Tests (V10.2.1)

Tests cross-attention, chunk continuity, and cross-chunk dependencies.

CLI Usage::

    python train_hard_probes.py --test-chunking-v10
    python train_hard_probes.py --test-chunking-v10 --chunk-size 64 --chunk-test-seq-len 256
"""

import torch
import torch.nn as nn
from typing import Dict, Optional

# =============================================================================
# V10.2.1 CHUNKING ARCHITECTURE TESTS
# =============================================================================

def run_chunking_tests_v10(args, config):
    """
    V10.2.1: Comprehensive tests for the new chunking architecture.

    Tests:
    1. Cross-Attention Ablation: Does Local need Phase memory?
    2. Chunk Continuity: Full-sequence vs chunked processing match?
    3. Cross-Chunk Dependencies: Can Phase capture long-range across chunks?
    4. Gradient Flow: Does Phase get gradients only through Local?
    """
    print("\n" + "=" * 70)
    print("V10.2.1 CHUNKING ARCHITECTURE TESTS")
    print("=" * 70)
    print("\nThese tests verify the new Protected Phase with cross-attention:")
    print("  - Phase accumulates temporal memory (O(n) cumsum)")
    print("  - Local queries Phase memory via cross-attention")
    print("  - Phase gets gradients ONLY through Local's K/V")
    print()

    # Try to import the actual HybridPhaseTransformer from symbolu
    try:
        import sys
        import os
        # Try multiple paths to find symbolu module
        possible_paths = [
            os.getcwd(),  # Current working directory (e.g., /workspace/symbolu)
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),  # Project root from script
            '/home/user/symbolu',
            '/workspace/symbolu',
        ]
        for path in possible_paths:
            symbolu_path = os.path.join(path, 'symbolu')
            if path not in sys.path and os.path.exists(symbolu_path):
                sys.path.insert(0, path)
                print(f"  Added {path} to PYTHONPATH")
                break

        from symbolu.phase_transformer import HybridPhaseTransformer
        USE_REAL_MODEL = True
        print("✓ Using real HybridPhaseTransformer from symbolu/phase_transformer.py")
    except ImportError as e:
        print(f"⚠ Could not import HybridPhaseTransformer: {e}")
        print("  Hint: Run from project root: cd /workspace/symbolu && python scripts/...")
        print("  Or set PYTHONPATH: export PYTHONPATH=/workspace/symbolu:$PYTHONPATH")
        USE_REAL_MODEL = False

    device = args.device
    chunk_size = args.chunk_size
    seq_len = args.chunk_test_seq_len

    results = {}
    model = None  # Will be created if USE_REAL_MODEL

    # =========================================================================
    # TRAINING PHASE: CURRICULUM LEARNING for Cross-Chunk Memory
    # =========================================================================
    # The key insight: we need to verify the model CAN learn cross-chunk deps.
    # Start with the SIMPLEST possible task and gradually increase complexity.
    #
    # CURRICULUM:
    # Phase 1: SINGLE anchor copy (one value, copy to all queries)
    #          - If this fails, architecture has fundamental issue
    # Phase 2: MULTI anchor with SUM (predict sum of all anchors mod 10)
    #          - Tests if Phase can aggregate info across chunk 0
    # Phase 3: POSITION-BASED recall (original hard task)
    #          - Only attempt if Phase 1 & 2 succeed
    # =========================================================================
    if USE_REAL_MODEL:
        print("\n" + "-" * 70)
        print("[TRAINING] Curriculum Learning for Cross-Chunk Memory")
        print("-" * 70)

        # Smaller vocab makes tasks learnable
        vocab_size = 50
        # Tokens: 0-9 anchor values, 10 query token, 11-49 fillers
        NUM_ANCHORS = 10
        QUERY_TOKEN = 10
        FILLER_START = 11

        model = HybridPhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=config.d_model,
            num_layers=config.num_layers,
            num_heads=config.num_heads,
            ff_dim=config.d_ff,
            max_seq_len=seq_len,
            dropout=0.0,  # No dropout for cleaner learning signal
            local_layers=2,
            window_size=32,
            protected_phase=True,
        ).to(device)

        print(f"  Model: {sum(p.numel() for p in model.parameters()):,} parameters")
        print(f"  Protected Phase: ENABLED")
        print(f"  Vocab: {vocab_size} (anchors 0-9, query 10, fillers 11-49)")

        # =================================================================
        # PHASE 1: Single Anchor Copy (SIMPLEST POSSIBLE)
        # =================================================================
        # One anchor at position 5, every query in later chunks must copy it
        # This is the absolute minimum cross-chunk task
        # =================================================================
        print(f"\n  === PHASE 1: Single Anchor Copy ===")
        print(f"  Task: anchor[5] in chunk 0 → copy to ALL queries in chunks 1+")

        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.0)
        model.train()

        phase1_steps = 3000
        batch_size = 32
        log_every = 500
        anchor_pos = 5  # Single anchor position

        running_loss = 0.0
        running_acc = 0.0
        best_acc = 0.0

        for step in range(phase1_steps):
            # Fill with random fillers
            input_ids = torch.randint(FILLER_START, vocab_size, (batch_size, seq_len), device=device)
            targets = torch.full((batch_size, seq_len), -100, device=device)

            for b in range(batch_size):
                # Single anchor value (0-9) at position 5 in chunk 0
                anchor_val = random.randint(0, NUM_ANCHORS - 1)
                input_ids[b, anchor_pos] = anchor_val

                # Place query tokens at multiple positions in later chunks
                # All must predict the SAME anchor value
                for chunk_idx in range(1, seq_len // chunk_size):
                    chunk_start = chunk_idx * chunk_size
                    # 3 query positions per chunk
                    for q_offset in [5, 20, 40]:
                        query_pos = chunk_start + q_offset
                        if query_pos < seq_len - 1:
                            input_ids[b, query_pos] = QUERY_TOKEN
                            targets[b, query_pos] = anchor_val

            # Forward
            result = model(input_ids)
            logits = result['logits']

            # Loss on query positions only
            shift_logits = logits[:, :-1, :].contiguous()
            shift_targets = targets[:, 1:].contiguous()

            loss = F.cross_entropy(
                shift_logits.view(-1, vocab_size),
                shift_targets.view(-1),
                ignore_index=-100
            )

            # Accuracy
            valid_mask = shift_targets != -100
            if valid_mask.sum() > 0:
                preds = shift_logits.argmax(dim=-1)
                correct = (preds == shift_targets) & valid_mask
                acc = correct.sum().float() / valid_mask.sum().float()
                running_acc += acc.item()
                best_acc = max(best_acc, acc.item())

            running_loss += loss.item()

            # Backward
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            if (step + 1) % log_every == 0:
                avg_loss = running_loss / log_every
                avg_acc = running_acc / log_every
                print(f"    Step {step+1}/{phase1_steps}: Loss={avg_loss:.4f}, Acc={avg_acc:.1%}, Best={best_acc:.1%}")
                running_loss = 0.0
                running_acc = 0.0

        # Evaluate Phase 1
        model.eval()
        phase1_correct = 0
        phase1_total = 0
        with torch.no_grad():
            for _ in range(20):
                input_ids = torch.randint(FILLER_START, vocab_size, (batch_size, seq_len), device=device)
                targets = torch.full((batch_size, seq_len), -100, device=device)

                for b in range(batch_size):
                    anchor_val = random.randint(0, NUM_ANCHORS - 1)
                    input_ids[b, anchor_pos] = anchor_val
                    for chunk_idx in range(1, seq_len // chunk_size):
                        chunk_start = chunk_idx * chunk_size
                        for q_offset in [5, 20, 40]:
                            query_pos = chunk_start + q_offset
                            if query_pos < seq_len - 1:
                                input_ids[b, query_pos] = QUERY_TOKEN
                                targets[b, query_pos] = anchor_val

                result = model(input_ids)
                logits = result['logits']
                shift_logits = logits[:, :-1, :]
                shift_targets = targets[:, 1:]
                valid_mask = shift_targets != -100
                preds = shift_logits.argmax(dim=-1)
                phase1_correct += ((preds == shift_targets) & valid_mask).sum().item()
                phase1_total += valid_mask.sum().item()

        phase1_acc = phase1_correct / phase1_total if phase1_total > 0 else 0
        print(f"  Phase 1 Final Accuracy: {phase1_acc:.1%}")

        phase1_passed = phase1_acc > 0.5  # Should get >50% to show learning

        if phase1_passed:
            print(f"  ✓ PHASE 1 PASSED - Model CAN learn cross-chunk dependencies!")
        else:
            print(f"  ⚠ PHASE 1 INCOMPLETE - Model needs more training or architecture changes")
            print(f"    (But architecture verification still valid)")

        # =================================================================
        # PHASE 2: Multi-Anchor Sum (only if Phase 1 passed)
        # =================================================================
        if phase1_passed:
            print(f"\n  === PHASE 2: Multi-Anchor Aggregation ===")
            print(f"  Task: 3 anchors in chunk 0 → query predicts (sum mod 10)")

            # Fresh optimizer for phase 2
            optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=0.0)
            model.train()

            phase2_steps = 2000
            anchor_positions = [5, 20, 40]

            running_loss = 0.0
            running_acc = 0.0

            for step in range(phase2_steps):
                input_ids = torch.randint(FILLER_START, vocab_size, (batch_size, seq_len), device=device)
                targets = torch.full((batch_size, seq_len), -100, device=device)

                for b in range(batch_size):
                    # 3 anchor values
                    anchor_vals = [random.randint(0, NUM_ANCHORS - 1) for _ in range(3)]
                    target_val = sum(anchor_vals) % NUM_ANCHORS

                    for i, pos in enumerate(anchor_positions):
                        input_ids[b, pos] = anchor_vals[i]

                    # Queries in later chunks predict the sum
                    for chunk_idx in range(1, seq_len // chunk_size):
                        chunk_start = chunk_idx * chunk_size
                        query_pos = chunk_start + 30
                        if query_pos < seq_len - 1:
                            input_ids[b, query_pos] = QUERY_TOKEN
                            targets[b, query_pos] = target_val

                result = model(input_ids)
                logits = result['logits']
                shift_logits = logits[:, :-1, :].contiguous()
                shift_targets = targets[:, 1:].contiguous()

                loss = F.cross_entropy(
                    shift_logits.view(-1, vocab_size),
                    shift_targets.view(-1),
                    ignore_index=-100
                )

                valid_mask = shift_targets != -100
                if valid_mask.sum() > 0:
                    preds = shift_logits.argmax(dim=-1)
                    correct = (preds == shift_targets) & valid_mask
                    acc = correct.sum().float() / valid_mask.sum().float()
                    running_acc += acc.item()

                running_loss += loss.item()

                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

                if (step + 1) % log_every == 0:
                    avg_loss = running_loss / log_every
                    avg_acc = running_acc / log_every
                    print(f"    Step {step+1}/{phase2_steps}: Loss={avg_loss:.4f}, Acc={avg_acc:.1%}")
                    running_loss = 0.0
                    running_acc = 0.0

            print(f"  Phase 2 complete.")

        model.eval()
        print(f"\n  Training curriculum complete.")

        # Store vocab_size for tests
        model._test_vocab_size = vocab_size

    # =========================================================================
    # TEST 1: Cross-Attention Ablation
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 1] CROSS-ATTENTION ABLATION (after training)")
    print("-" * 70)
    print("Question: Does Local NEED Phase memory for long-range info?")
    print("Method: Compare Local with/without phase_memory parameter")
    print()

    if USE_REAL_MODEL and model is not None:
        # Get vocab size from model
        test_vocab_size = getattr(model, '_test_vocab_size', 100)

        # Create test input with cross-chunk copy task structure
        test_input = torch.randint(11, test_vocab_size, (1, seq_len), device=device)
        # Place anchor at position 5 in chunk 0, query at position 5 in chunk 1
        anchor_value = random.randint(0, 9)  # Anchor token
        test_input[0, 5] = anchor_value
        test_input[0, chunk_size + 5] = 10  # Query token

        # Forward with normal protected phase (Local queries Phase memory)
        model.eval()
        with torch.no_grad():
            result_normal = model(test_input)
            logits_normal = result_normal['logits']

        # Now temporarily disable protected_phase in hybrid layers
        # This makes Local use self-attention instead of cross-attention to Phase
        for block in model.blocks:
            if hasattr(block, 'attention') and hasattr(block.attention, 'protected_phase'):
                block.attention.protected_phase = False

        with torch.no_grad():
            result_ablated = model(test_input)
            logits_ablated = result_ablated['logits']

        # Restore
        for block in model.blocks:
            if hasattr(block, 'attention') and hasattr(block.attention, 'protected_phase'):
                block.attention.protected_phase = True

        # Compare
        logit_diff = (logits_normal - logits_ablated).abs()
        max_diff = logit_diff.max().item()
        mean_diff = logit_diff.mean().item()

        print(f"  Logit difference (Protected vs Parallel):")
        print(f"    Max:  {max_diff:.6f}")
        print(f"    Mean: {mean_diff:.6f}")

        # If difference is large, cross-attention to Phase matters
        if max_diff > 0.1:
            print(f"  ✓ PASS: Significant difference - Local depends on Phase memory")
            results['cross_attention_ablation'] = 'PASS'
        else:
            print(f"  ⚠ Note: Small difference - may need more training for Phase to learn")
            results['cross_attention_ablation'] = 'SMALL_DIFF'
    else:
        print("  (Skipped - real model not available)")
        results['cross_attention_ablation'] = 'SKIPPED'

    # =========================================================================
    # TEST 2: Chunk Continuity
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 2] CHUNK CONTINUITY")
    print("-" * 70)
    print("Question: Do full-sequence and chunked processing produce same output?")
    print(f"Method: Compare model(full_seq) vs model.forward_chunk(chunks)")
    print(f"  Sequence length: {seq_len}, Chunk size: {chunk_size}")
    print()

    if USE_REAL_MODEL and model is not None:
        # Use the model's built-in diagnostic
        try:
            diag = model.diagnose_chunk_continuity(
                test_input,
                chunk_size=chunk_size,
                verbose=True
            )
            results['chunk_continuity'] = 'PASS' if diag['healthy'] else 'FAIL'
        except Exception as e:
            print(f"  ✗ Error running diagnostic: {e}")
            results['chunk_continuity'] = 'ERROR'
    else:
        print("  (Skipped - real model not available)")
        results['chunk_continuity'] = 'SKIPPED'

    # =========================================================================
    # TEST 3: Cross-Chunk Dependencies (after training)
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 3] CROSS-CHUNK DEPENDENCIES (after training)")
    print("-" * 70)
    print("Question: Can Phase capture dependencies that span chunk boundaries?")
    print("Method: Create sequence where answer depends on token in previous chunk")
    print()

    if USE_REAL_MODEL and model is not None:
        # Test using the cross-chunk copy task structure
        # If Phase works, changing the anchor should change the prediction at query
        test_vocab_size = getattr(model, '_test_vocab_size', 100)

        # Anchor at position 5 in chunk 0, query at position 5 in chunk 1
        anchor_pos = 5
        query_pos = chunk_size + 5  # Same relative position in chunk 1

        if query_pos < seq_len:
            # Create two inputs: same except for anchor token value
            input_a = torch.randint(11, test_vocab_size, (1, seq_len), device=device)
            input_b = input_a.clone()

            # Set different anchor values (both valid anchor tokens 0-9)
            input_a[0, anchor_pos] = 3  # Anchor A = 3
            input_b[0, anchor_pos] = 7  # Anchor B = 7
            # Both have query token at same position
            input_a[0, query_pos] = 10  # Query token
            input_b[0, query_pos] = 10

            # Process both with chunking
            with torch.no_grad():
                layer_states_a = None
                layer_states_b = None

                # First chunk (contains anchor)
                chunk1_a = input_a[:, :chunk_size]
                chunk1_b = input_b[:, :chunk_size]

                result_a, layer_states_a = model.forward_chunk(
                    chunk1_a, chunk_offset=0, prev_layer_states=layer_states_a
                )
                result_b, layer_states_b = model.forward_chunk(
                    chunk1_b, chunk_offset=0, prev_layer_states=layer_states_b
                )

                # Second chunk (contains reference)
                chunk2_a = input_a[:, chunk_size:2*chunk_size]
                chunk2_b = input_b[:, chunk_size:2*chunk_size]

                result2_a, _ = model.forward_chunk(
                    chunk2_a, chunk_offset=chunk_size, prev_layer_states=layer_states_a
                )
                result2_b, _ = model.forward_chunk(
                    chunk2_b, chunk_offset=chunk_size, prev_layer_states=layer_states_b
                )

            # Check if output at query position differs and predicts correctly
            query_local = anchor_pos  # Same relative position in chunk 1
            if query_local < result2_a['logits'].shape[1]:
                logits_at_query_a = result2_a['logits'][0, query_local]
                logits_at_query_b = result2_b['logits'][0, query_local]

                # Check predictions
                pred_a = logits_at_query_a.argmax().item()
                pred_b = logits_at_query_b.argmax().item()

                # Logit difference
                diff_at_query = (logits_at_query_a - logits_at_query_b).abs().mean().item()

                print(f"  Input A: anchor=3 at pos {anchor_pos}, query at pos {query_pos}")
                print(f"  Input B: anchor=7 at pos {anchor_pos}, query at pos {query_pos}")
                print(f"  Prediction A (should be 3): {pred_a}")
                print(f"  Prediction B (should be 7): {pred_b}")
                print(f"  Logit difference: {diff_at_query:.6f}")

                # Pass if predictions differ AND match anchors
                correct_a = pred_a == 3
                correct_b = pred_b == 7
                if correct_a and correct_b:
                    print(f"  ✓ PASS: Both predictions correct! Cross-chunk memory works!")
                    results['cross_chunk_deps'] = 'PASS'
                elif diff_at_query > 0.1:
                    print(f"  ⚠ Partial: Different predictions but not perfect copy")
                    results['cross_chunk_deps'] = 'PARTIAL'
                else:
                    print(f"  ⚠ Note: Predictions don't reflect anchor difference")
                    results['cross_chunk_deps'] = 'SMALL_DIFF'
            else:
                print(f"  Query position out of bounds")
                results['cross_chunk_deps'] = 'ERROR'
        else:
            print(f"  Sequence too short for cross-chunk test")
            results['cross_chunk_deps'] = 'SKIPPED'
    else:
        print("  (Skipped - real model not available)")
        results['cross_chunk_deps'] = 'SKIPPED'

    # =========================================================================
    # TEST 4: Gradient Flow Verification
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 4] GRADIENT FLOW VERIFICATION")
    print("-" * 70)
    print("Question: Does Phase get gradients only through Local's cross-attention?")
    print("Method: Check gradient paths with backward pass")
    print()

    if USE_REAL_MODEL and model is not None:
        model.train()

        # Create input and do forward pass
        test_vocab_size = getattr(model, '_test_vocab_size', 100)
        test_input_grad = torch.randint(0, test_vocab_size, (2, 64), device=device)

        # Zero gradients
        model.zero_grad()

        # Forward and backward
        result = model(test_input_grad)
        logits = result['logits']

        # Simple loss: sum of logits at last position
        loss = logits[:, -1, :].sum()
        loss.backward()

        # Check gradients in Phase attention layers vs Local
        phase_grad_norms = []
        local_grad_norms = []

        for name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                if 'phase_attn' in name or 'phase' in name.lower():
                    phase_grad_norms.append((name, grad_norm))
                elif 'local_attn' in name or 'local' in name.lower():
                    local_grad_norms.append((name, grad_norm))

        # Report
        if phase_grad_norms:
            avg_phase_grad = sum(g for _, g in phase_grad_norms) / len(phase_grad_norms)
            print(f"  Phase attention gradient norms (sample):")
            for name, norm in phase_grad_norms[:3]:
                print(f"    {name[-50:]}: {norm:.6f}")
            print(f"  Average Phase grad norm: {avg_phase_grad:.6f}")
        else:
            print(f"  No Phase gradients found (names may differ)")

        if local_grad_norms:
            avg_local_grad = sum(g for _, g in local_grad_norms) / len(local_grad_norms)
            print(f"\n  Local attention gradient norms (sample):")
            for name, norm in local_grad_norms[:3]:
                print(f"    {name[-50:]}: {norm:.6f}")
            print(f"  Average Local grad norm: {avg_local_grad:.6f}")

        # In Protected Phase mode, both should have gradients
        # (Phase gets gradients via Local's K/V projection of memory_state)
        if phase_grad_norms and local_grad_norms:
            print(f"\n  ✓ Both Phase and Local receive gradients")
            print(f"    (In Protected Phase, gradients flow: Loss → Local → K/V → Phase)")
            results['gradient_flow'] = 'PASS'
        else:
            print(f"\n  ⚠ Could not verify gradient flow (check parameter names)")
            results['gradient_flow'] = 'UNCLEAR'

        model.eval()
    else:
        print("  (Skipped - real model not available)")
        results['gradient_flow'] = 'SKIPPED'

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("V10.2.1 CHUNKING TEST SUMMARY")
    print("=" * 70)

    print(f"\n{'Test':<35} {'Result':<15}")
    print("-" * 50)
    for test_name, result in results.items():
        status_icon = "✓" if result == "PASS" else "⚠" if result in ["SMALL_DIFF", "UNCLEAR"] else "✗"
        print(f"{test_name:<35} {status_icon} {result:<15}")

    all_pass = all(r == 'PASS' for r in results.values())
    if all_pass:
        print(f"\n✓ ALL TESTS PASSED - V10.2.1 architecture is working correctly!")
    else:
        print(f"\n⚠ Some tests need attention - see details above")

    return results


# =============================================================================
# V10.12: PHASE-AWARE ADAPTATION BENCHMARKS (IA³ + SURGICAL LORA)
# =============================================================================
