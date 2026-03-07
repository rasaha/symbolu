"""
Knowledge Probes: Three independent diagnostic metrics that measure real model
capabilities beyond perplexity.

These run every N training steps and provide signals orthogonal to PPL:

1. Factual Probe Accuracy   — Can the model complete known facts? (exact match)
2. Slot Retrieval Precision  — Can slot memory recover previously stored info?
3. Phase Coherence Score     — Does the model maintain topic over long sequences?

Usage (called from train.py):
    from symbolu.training.unified.knowledge_probes import run_knowledge_probes
    results = run_knowledge_probes(model, tokenizer, config, device, step)
"""

from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


# =============================================================================
# 1. FACTUAL PROBE ACCURACY
# =============================================================================
# Curated set of factual completions where there's a clear "right answer"
# in the training data (OpenWebText). These are facts that appear frequently
# enough that even a small model should learn them with sufficient training.
#
# Format: (prompt, list_of_acceptable_completions)
# We check if ANY acceptable completion appears in top-K predictions.

FACTUAL_PROBES = [
    # Geography — very common in web text
    ("The capital of France is", ["Paris"]),
    ("The capital of the United States is", ["Washington"]),
    ("The largest ocean on Earth is the", ["Pacific"]),

    # Science — extremely common facts
    ("Water is composed of hydrogen and", ["oxygen"]),
    ("The speed of light is approximately", ["300", "186"]),
    ("The chemical symbol for gold is", ["Au"]),

    # History — high frequency in OpenWebText
    ("World War II ended in", ["1945"]),
    ("The first president of the United States was", ["George", "Washington"]),
    ("The Berlin Wall fell in", ["1989"]),

    # Math/Logic — pattern recognition
    ("The square root of 144 is", ["12"]),
    ("One kilometer equals 1000", ["meters", "metres"]),

    # Common knowledge — extremely high frequency
    ("The sun rises in the", ["east"]),
    ("There are 365 days in a", ["year"]),
    ("The largest planet in our solar system is", ["Jupiter"]),
    ("DNA stands for deoxyribonucleic", ["acid"]),
]


def run_factual_probes(
    model: nn.Module,
    tokenizer,
    device: torch.device,
    top_k: int = 10,
    autocast_dtype: Optional[torch.dtype] = None,
) -> Dict[str, float]:
    """
    Run factual probe accuracy: for each probe, check if the correct
    completion token appears in the model's top-K predictions.

    Returns:
        dict with:
            - 'accuracy': fraction of probes where correct answer is in top-K
            - 'mean_rank': average rank of correct answer (lower = better)
            - 'mean_prob': average probability assigned to correct answer
            - 'num_probes': total probes tested
            - 'per_probe': list of per-probe results for detailed logging
    """
    model.eval()
    _use_autocast = autocast_dtype is not None and device.type == 'cuda'

    correct = 0
    total = 0
    ranks = []
    probs = []
    per_probe = []

    with torch.no_grad():
        for prompt, acceptable in FACTUAL_PROBES:
            try:
                input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

                if _use_autocast:
                    with torch.amp.autocast('cuda', dtype=autocast_dtype):
                        outputs = model(input_ids)
                else:
                    outputs = model(input_ids)

                if isinstance(outputs, dict):
                    logits = outputs.get('logits', outputs.get('output'))
                elif isinstance(outputs, (tuple, list)):
                    logits = outputs[0]
                else:
                    logits = outputs

                # Get probabilities for the next token position
                next_probs = F.softmax(logits[0, -1, :], dim=-1)
                top_vals, top_ids = torch.topk(next_probs, min(top_k, next_probs.shape[0]))

                # Decode top-K tokens
                top_tokens = [tokenizer.decode([tid.item()]).strip() for tid in top_ids]

                # Check if any acceptable completion appears in top-K
                found = False
                best_rank = top_k + 1
                best_prob = 0.0
                matched_token = None

                for accept in acceptable:
                    accept_lower = accept.lower()
                    for i, tok in enumerate(top_tokens):
                        if accept_lower in tok.lower():
                            found = True
                            if i < best_rank:
                                best_rank = i + 1  # 1-indexed rank
                                best_prob = top_vals[i].item()
                                matched_token = tok
                            break

                if found:
                    correct += 1
                    ranks.append(best_rank)
                    probs.append(best_prob)
                else:
                    ranks.append(top_k + 1)
                    probs.append(0.0)

                total += 1
                per_probe.append({
                    'prompt': prompt,
                    'expected': acceptable,
                    'found': found,
                    'rank': best_rank if found else None,
                    'prob': best_prob if found else 0.0,
                    'matched': matched_token,
                    'top3': top_tokens[:3],
                })

            except Exception:
                # Skip probes that fail (e.g., tokenizer issues)
                continue

    accuracy = correct / max(total, 1)
    mean_rank = sum(ranks) / max(len(ranks), 1)
    mean_prob = sum(probs) / max(len(probs), 1)

    return {
        'accuracy': accuracy,
        'mean_rank': mean_rank,
        'mean_prob': mean_prob,
        'num_probes': total,
        'correct': correct,
        'per_probe': per_probe,
    }


# =============================================================================
# 2. SLOT RETRIEVAL PRECISION
# =============================================================================
# Tests whether the slot memory system actually stores and retrieves information.
# We feed a sequence through the model, record what gets written to slots,
# then test if a related query can retrieve the correct content.

def run_slot_retrieval_probes(
    model: nn.Module,
    tokenizer,
    device: torch.device,
    autocast_dtype: Optional[torch.dtype] = None,
) -> Dict[str, float]:
    """
    Test slot memory retrieval precision.

    Strategy:
    1. Feed a "storage" passage through the model to populate slots
    2. Feed a related "query" that should trigger retrieval
    3. Measure:
       - Slot utilization: how many slots have non-zero values
       - Read attention entropy: is retrieval focused or diffuse?
       - Retrieval-augmented prediction: does slot content help predict
         the right continuation?

    Returns empty metrics if model has no slot memory.
    """
    # Check if model has slot memory
    slot_memory = _get_slot_memory(model)
    if slot_memory is None:
        return {
            'available': False,
            'slot_utilization': 0.0,
            'read_entropy': 0.0,
            'retrieval_match': 0.0,
            'retrieval_boost': 0.0,
        }

    model.eval()
    _use_autocast = autocast_dtype is not None and device.type == 'cuda'

    # Storage-query pairs: the query should benefit from remembering the storage passage
    # These are designed so the model needs to recall specific info from the passage
    probe_pairs = [
        {
            'storage': "The Eiffel Tower was built in 1889 for the World's Fair in Paris. "
                       "It was designed by Gustave Eiffel and stands 330 meters tall.",
            'query': "The designer of the Eiffel Tower was",
            'expected_tokens': ["Gust", "Eiff"],  # Gustave Eiffel
        },
        {
            'storage': "Python was created by Guido van Rossum and first released in 1991. "
                       "It emphasizes code readability and uses significant indentation.",
            'query': "The creator of the Python programming language was",
            'expected_tokens': ["Gu", "van", "Ross"],
        },
        {
            'storage': "The Amazon River is the largest river by discharge volume of water. "
                       "It flows through Brazil, Peru, and Colombia, stretching 6,400 kilometers.",
            'query': "The Amazon River flows through Brazil, Peru, and",
            'expected_tokens': ["Colomb"],
        },
        {
            'storage': "Albert Einstein published his theory of general relativity in 1915. "
                       "The theory describes gravity as the curvature of spacetime.",
            'query': "Einstein's theory of general relativity describes gravity as",
            'expected_tokens': ["curv", "space"],
        },
    ]

    utilizations = []
    read_entropies = []
    retrieval_matches = []
    retrieval_boosts = []

    with torch.no_grad():
        for pair in probe_pairs:
            try:
                result = _probe_single_slot_retrieval(
                    model, slot_memory, tokenizer, device, pair,
                    autocast_dtype, _use_autocast,
                )
                if result is not None:
                    utilizations.append(result['utilization'])
                    read_entropies.append(result['read_entropy'])
                    retrieval_matches.append(result['match'])
                    retrieval_boosts.append(result['boost'])
            except Exception:
                continue

    n = max(len(utilizations), 1)
    return {
        'available': True,
        'slot_utilization': sum(utilizations) / n,
        'read_entropy': sum(read_entropies) / n,
        'retrieval_match': sum(retrieval_matches) / n,
        'retrieval_boost': sum(retrieval_boosts) / n,
        'num_probes': len(utilizations),
    }


def _get_slot_memory(model: nn.Module):
    """Extract SlotMemoryGCT from model if present."""
    # OntologicalHybridTransformer → hybrid → slot_memory
    hybrid = getattr(model, 'hybrid', None)
    if hybrid is not None:
        sm = getattr(hybrid, 'slot_memory', None)
        if sm is not None:
            return sm
    # Direct access
    sm = getattr(model, 'slot_memory', None)
    if sm is not None:
        return sm
    return None


def _probe_single_slot_retrieval(
    model: nn.Module,
    slot_memory,
    tokenizer,
    device: torch.device,
    pair: dict,
    autocast_dtype,
    use_autocast: bool,
) -> Optional[Dict[str, float]]:
    """
    Run a single storage→query slot retrieval probe.

    Key insight: slot memory is initialized fresh each forward pass inside
    HybridPhaseTransformer.forward(). To test retrieval, we must concatenate
    storage+query into a SINGLE sequence so slots written during storage
    tokens are available when the query tokens are processed.

    We compare the model's prediction at the query's last position with
    vs without the storage prefix to measure retrieval benefit.
    """
    # Step 1: Reset model state
    if hasattr(model, 'prev_state'):
        model.prev_state = None
    if hasattr(model, 'prev_bhava'):
        model.prev_bhava = None

    # Step 2: Encode storage + query as a single concatenated sequence
    # This ensures slot writes from storage tokens persist during query processing
    combined_text = pair['storage'] + " " + pair['query']
    combined_ids = tokenizer.encode(combined_text, return_tensors="pt").to(device)

    # Also encode query alone (baseline — no storage context)
    query_ids = tokenizer.encode(pair['query'], return_tensors="pt").to(device)

    # Step 3: Forward pass with combined sequence (slots active)
    if use_autocast:
        with torch.amp.autocast('cuda', dtype=autocast_dtype):
            combined_out = model(combined_ids, reset_state=True)
    else:
        combined_out = model(combined_ids, reset_state=True)

    if isinstance(combined_out, dict):
        combined_logits = combined_out.get('logits', combined_out.get('output'))
    elif isinstance(combined_out, (tuple, list)):
        combined_logits = combined_out[0]
    else:
        combined_logits = combined_out

    # Step 4: Read slot diagnostics NOW (before query-only pass overwrites them)
    # These were populated during the combined forward pass
    read_entropy = getattr(slot_memory, '_diag_read_attn_entropy', 0.0)
    write_gate = getattr(slot_memory, '_diag_write_gate_mean', 0.0)
    utilization = write_gate if write_gate > 0 else 0.0

    # Step 5: Forward pass with query alone (baseline — no slot context)
    # Reset state so comparison is fair
    if hasattr(model, 'prev_state'):
        model.prev_state = None
    if hasattr(model, 'prev_bhava'):
        model.prev_bhava = None

    if use_autocast:
        with torch.amp.autocast('cuda', dtype=autocast_dtype):
            query_out = model(query_ids, reset_state=True)
    else:
        query_out = model(query_ids, reset_state=True)

    if isinstance(query_out, dict):
        query_logits = query_out.get('logits', query_out.get('output'))
    elif isinstance(query_out, (tuple, list)):
        query_logits = query_out[0]
    else:
        query_logits = query_out

    # Step 6: Check predictions — compare combined vs query-alone
    combined_probs = F.softmax(combined_logits[0, -1, :], dim=-1)
    query_probs = F.softmax(query_logits[0, -1, :], dim=-1)

    top_vals, top_ids = torch.topk(combined_probs, 20)
    top_tokens = [tokenizer.decode([tid.item()]).strip().lower() for tid in top_ids]

    # Check if expected tokens appear in combined top-20
    match = 0.0
    best_combined_prob = 0.0
    for expected in pair['expected_tokens']:
        for i, tok in enumerate(top_tokens):
            if expected.lower() in tok:
                match = 1.0
                best_combined_prob = top_vals[i].item()
                break
        if match > 0:
            break

    # Check baseline probability for the same expected tokens (query_probs is 1D [V])
    best_baseline_prob = 0.0
    for expected in pair['expected_tokens']:
        for tid in top_ids:
            tok_str = tokenizer.decode([tid.item()]).strip().lower()
            if expected.lower() in tok_str:
                best_baseline_prob = query_probs[tid.item()].item()
                break

    # Boost: how much does storage context increase probability of correct answer
    boost = max(0.0, best_combined_prob - best_baseline_prob)

    return {
        'utilization': utilization,
        'read_entropy': read_entropy,
        'match': match,
        'boost': boost,
    }


# =============================================================================
# 3. PHASE COHERENCE OVER LONG SEQUENCES
# =============================================================================
# Tests whether the model maintains topical coherence over 1k+ token sequences.
# We generate a long passage and measure:
# - Topic drift: does the model stay on-topic or wander?
# - Semantic similarity between chunks (beginning vs end)
# - Phase state stability: does delta_bhava stay small (stable) or oscillate?

# Topical prompts that should produce sustained, coherent passages
COHERENCE_PROMPTS = [
    "The history of astronomy begins with early civilizations observing the night sky.",
    "Machine learning algorithms can be broadly categorized into supervised and unsupervised methods.",
    "The process of photosynthesis converts sunlight into chemical energy in plants.",
]


def run_phase_coherence_probes(
    model: nn.Module,
    tokenizer,
    device: torch.device,
    max_tokens: int = 512,
    chunk_size: int = 64,
    autocast_dtype: Optional[torch.dtype] = None,
) -> Dict[str, float]:
    """
    Measure phase coherence over long generated sequences.

    For each prompt, generates a long passage and measures:
    1. Token-level coherence: Consecutive chunk embedding similarity
    2. Long-range coherence: First-chunk vs last-chunk similarity
    3. Phase stability: Mean |delta_bhava| over the sequence (if available)
    4. Topic drift rate: How quickly similarity to the prompt decays

    Returns:
        dict with coherence metrics
    """
    model.eval()
    _use_autocast = autocast_dtype is not None and device.type == 'cuda'

    all_local_coherence = []
    all_longrange_coherence = []
    all_phase_stability = []
    all_drift_rates = []

    with torch.no_grad():
        for prompt in COHERENCE_PROMPTS:
            try:
                result = _measure_sequence_coherence(
                    model, tokenizer, device, prompt,
                    max_tokens, chunk_size,
                    autocast_dtype, _use_autocast,
                )
                if result is not None:
                    all_local_coherence.append(result['local_coherence'])
                    all_longrange_coherence.append(result['longrange_coherence'])
                    all_phase_stability.append(result['phase_stability'])
                    all_drift_rates.append(result['drift_rate'])
            except Exception:
                continue

    n = max(len(all_local_coherence), 1)
    return {
        'local_coherence': sum(all_local_coherence) / n,
        'longrange_coherence': sum(all_longrange_coherence) / n,
        'phase_stability': sum(all_phase_stability) / n,
        'drift_rate': sum(all_drift_rates) / n,
        'num_prompts': len(all_local_coherence),
    }


def _measure_sequence_coherence(
    model: nn.Module,
    tokenizer,
    device: torch.device,
    prompt: str,
    max_tokens: int,
    chunk_size: int,
    autocast_dtype,
    use_autocast: bool,
) -> Optional[Dict[str, float]]:
    """
    Generate a long sequence and measure coherence metrics.

    Two-phase approach to avoid O(n^2) cost:
    1. Greedy-generate the full token sequence (fast, logits-only)
    2. Single forward pass on the complete sequence to get hidden states

    This is O(n) in forward passes instead of O(n^2).
    """
    # Reset model state
    if hasattr(model, 'prev_state'):
        model.prev_state = None
    if hasattr(model, 'prev_bhava'):
        model.prev_bhava = None

    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
    generated = input_ids.clone()
    prompt_len = input_ids.shape[1]

    # Phase 1: Generate tokens greedily (only need logits, not hidden states)
    for step in range(max_tokens):
        if use_autocast:
            with torch.amp.autocast('cuda', dtype=autocast_dtype):
                outputs = model(generated)
        else:
            outputs = model(generated)

        if isinstance(outputs, dict):
            logits = outputs.get('logits', outputs.get('output'))
        elif isinstance(outputs, (tuple, list)):
            logits = outputs[0]
        else:
            logits = outputs

        next_token = logits[:, -1, :].argmax(dim=-1, keepdim=True)
        generated = torch.cat([generated, next_token], dim=1)

        if next_token.item() == getattr(tokenizer, 'eos_token_id', -1):
            break

    total_len = generated.shape[1]
    generated_len = total_len - prompt_len
    if generated_len < chunk_size * 2:
        return None

    # Phase 2: Single forward pass on the complete sequence to get hidden states
    if hasattr(model, 'prev_state'):
        model.prev_state = None
    if hasattr(model, 'prev_bhava'):
        model.prev_bhava = None

    if use_autocast:
        with torch.amp.autocast('cuda', dtype=autocast_dtype):
            full_out = model(generated, return_last_hidden=True, reset_state=True)
    else:
        full_out = model(generated, return_last_hidden=True, reset_state=True)

    if isinstance(full_out, dict):
        hidden = full_out.get('last_hidden_state', None)  # [1, T, D]
        delta_bhava = full_out.get('delta_bhava', None)    # [1, 12]
    else:
        hidden = None
        delta_bhava = None

    if hidden is None:
        return None

    # Extract hidden states for generated tokens only (skip prompt)
    gen_hidden = hidden[:, prompt_len:, :].float()  # [1, gen_len, D]
    gen_len = gen_hidden.shape[1]

    # Split into chunks and compute mean embedding per chunk
    num_full_chunks = gen_len // chunk_size
    if num_full_chunks < 2:
        return None

    chunk_embeddings = []
    for c in range(num_full_chunks):
        start = c * chunk_size
        end = start + chunk_size
        chunk_emb = gen_hidden[:, start:end, :].mean(dim=1)  # [1, D]
        chunk_embeddings.append(chunk_emb)

    # --- Metric 1: Local coherence (consecutive chunk similarity) ---
    local_sims = []
    for i in range(len(chunk_embeddings) - 1):
        sim = F.cosine_similarity(
            chunk_embeddings[i], chunk_embeddings[i + 1], dim=-1
        ).item()
        local_sims.append(sim)
    local_coherence = sum(local_sims) / len(local_sims)

    # --- Metric 2: Long-range coherence (first vs last chunk) ---
    longrange_coherence = F.cosine_similarity(
        chunk_embeddings[0], chunk_embeddings[-1], dim=-1
    ).item()

    # --- Metric 3: Phase stability (mean |delta_bhava|) ---
    # delta_bhava from a single forward pass is the aggregate delta.
    # Use its norm as a proxy: small norm = stable phase throughout.
    if delta_bhava is not None:
        bhava_norm = delta_bhava.norm().item()
        phase_stability = 1.0 - min(1.0, bhava_norm)
    else:
        phase_stability = 0.5  # Unknown

    # --- Metric 4: Drift rate (slope of similarity decay from first chunk) ---
    if len(chunk_embeddings) >= 3:
        sims_from_first = []
        for i in range(1, len(chunk_embeddings)):
            sim = F.cosine_similarity(
                chunk_embeddings[0], chunk_embeddings[i], dim=-1
            ).item()
            sims_from_first.append(sim)
        # Drift rate = how much similarity drops per chunk
        # Negative = drifting away, zero = stable, positive = converging
        drift_rate = (sims_from_first[-1] - sims_from_first[0]) / len(sims_from_first)
    else:
        drift_rate = 0.0

    return {
        'local_coherence': local_coherence,
        'longrange_coherence': longrange_coherence,
        'phase_stability': phase_stability,
        'drift_rate': drift_rate,
    }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_knowledge_probes(
    model: nn.Module,
    tokenizer,
    config,  # UnifiedTrainingConfig
    device: torch.device,
    step: int,
    logger=None,
) -> Dict[str, Dict[str, float]]:
    """
    Run all three knowledge probes and print formatted results.

    Called from the training loop at config.knowledge_probe_every intervals.

    Returns:
        dict with 'factual', 'slots', 'coherence' sub-dicts
    """
    def log(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    # Derive autocast dtype from config
    _mp = getattr(config, 'mixed_precision', 'none')
    _autocast_dtype = None
    if _mp == 'bf16':
        _autocast_dtype = torch.bfloat16
    elif _mp == 'fp16':
        _autocast_dtype = torch.float16

    log("")
    log("=" * 60)
    log(f"  🧠 KNOWLEDGE PROBES (Step {step})")
    log("=" * 60)

    was_training = model.training
    model.eval()

    results = {}

    # --- 1. Factual Probe Accuracy ---
    try:
        factual = run_factual_probes(
            model, tokenizer, device,
            top_k=getattr(config, 'knowledge_probe_top_k', 10),
            autocast_dtype=_autocast_dtype,
        )
        results['factual'] = factual

        # Format output
        emoji = "🟢" if factual['accuracy'] > 0.3 else "🟡" if factual['accuracy'] > 0.1 else "🔴"
        log(f"  {emoji} Factual Accuracy: {factual['accuracy']*100:.1f}% "
            f"({factual['correct']}/{factual['num_probes']} in top-{getattr(config, 'knowledge_probe_top_k', 10)})")
        log(f"     Mean Rank: {factual['mean_rank']:.1f} | Mean Prob: {factual['mean_prob']:.4f}")

        # Show a few examples
        for probe in factual['per_probe'][:3]:
            status = "✓" if probe['found'] else "✗"
            prompt_short = probe['prompt'][-40:]
            if probe['found']:
                log(f"     {status} ...{prompt_short} → '{probe['matched']}' (rank {probe['rank']})")
            else:
                log(f"     {status} ...{prompt_short} → got {probe['top3']}")

    except Exception as e:
        log(f"  ⚠️ Factual probes failed: {e}")
        results['factual'] = {'accuracy': 0.0, 'error': str(e)}

    # --- 2. Slot Retrieval Precision ---
    try:
        slots = run_slot_retrieval_probes(
            model, tokenizer, device,
            autocast_dtype=_autocast_dtype,
        )
        results['slots'] = slots

        if slots.get('available', False):
            emoji = "🟢" if slots['retrieval_match'] > 0.3 else "🟡" if slots['retrieval_match'] > 0 else "🔴"
            log(f"  {emoji} Slot Retrieval: match={slots['retrieval_match']*100:.0f}% "
                f"util={slots['slot_utilization']*100:.0f}% "
                f"entropy={slots['read_entropy']:.2f}")
        else:
            log(f"  ○ Slot Memory: not available in this model configuration")

    except Exception as e:
        log(f"  ⚠️ Slot probes failed: {e}")
        results['slots'] = {'available': False, 'error': str(e)}

    # --- 3. Phase Coherence ---
    try:
        coherence = run_phase_coherence_probes(
            model, tokenizer, device,
            max_tokens=getattr(config, 'knowledge_probe_coherence_tokens', 256),
            chunk_size=getattr(config, 'knowledge_probe_chunk_size', 64),
            autocast_dtype=_autocast_dtype,
        )
        results['coherence'] = coherence

        emoji = "🟢" if coherence['local_coherence'] > 0.8 else "🟡" if coherence['local_coherence'] > 0.5 else "🔴"
        drift_emoji = "↗" if coherence['drift_rate'] > 0 else "↘" if coherence['drift_rate'] < -0.02 else "→"
        log(f"  {emoji} Phase Coherence: local={coherence['local_coherence']:.3f} "
            f"longrange={coherence['longrange_coherence']:.3f} "
            f"stability={coherence['phase_stability']:.3f} "
            f"drift={drift_emoji}{abs(coherence['drift_rate']):.4f}")

    except Exception as e:
        log(f"  ⚠️ Coherence probes failed: {e}")
        results['coherence'] = {'local_coherence': 0.0, 'error': str(e)}

    log("=" * 60)
    log("")

    if was_training:
        model.train()

    return results
