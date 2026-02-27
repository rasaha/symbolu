"""
Text generation and quality monitoring utilities.

Provides sample generation with nucleus sampling and quality metrics
for monitoring training progress.

Extracted from train_unified_llm.py
"""

import math
from typing import Optional, Dict, List, Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.training.entropy_control import (
    EntropyControlConfig,
    AdaptiveEntropyController,
)

# Import clean_wikitext_artifacts (optional dependency)
try:
    from symbolu.training import clean_wikitext_artifacts
    _CLEAN_WIKITEXT_AVAILABLE = True
except ImportError:
    _CLEAN_WIKITEXT_AVAILABLE = False


@torch.no_grad()
@torch._dynamo.disable  # Disable torch.compile for generation (dynamic shapes cause hangs)
def generate_sample(
    model: nn.Module,
    tokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 128,
    temperature: float = 0.9,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.15,
    no_repeat_ngram_size: int = 3,
    entropy_controller: Optional[AdaptiveEntropyController] = None,
) -> str:
    """
    Generate text from a prompt for quality monitoring.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    ChatGPT recommendations for breaking repetition:
    - temperature = 0.8-1.0
    - top_p = 0.95
    - top_k = 50
    - repetition_penalty = 1.1-1.2
    - no_repeat_ngram_size = 3
    - max_new_tokens = 128-192

    If entropy_controller is provided, applies adaptive logit scaling
    to keep output entropy near target band.
    """
    model.eval()

    # Encode prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
    prompt_len = input_ids.shape[1]

    # Generate tokens one by one
    generated = input_ids.clone()

    # Reset entropy controller for new generation
    if entropy_controller is not None:
        initial_scale = None
        if hasattr(model, 'entropy_logit_scale'):
            initial_scale = model.entropy_logit_scale.logit_scale
        entropy_controller.reset(initial_scale)

    # Track generated n-grams for no_repeat_ngram blocking
    def get_ngrams(seq, n):
        """Extract n-grams from a sequence."""
        ngrams = set()
        for i in range(len(seq) - n + 1):
            ngrams.add(tuple(seq[i:i+n].tolist()))
        return ngrams

    for step in range(max_new_tokens):
        # Forward pass
        outputs = model(generated)

        # Handle different output formats (dict with 'logits', tuple, or tensor)
        if isinstance(outputs, dict):
            logits = outputs.get('logits', outputs.get('output', None))
            if logits is None:
                # Try to find logits-like tensor in dict
                for key in ['logits', 'output', 'lm_logits']:
                    if key in outputs:
                        logits = outputs[key]
                        break
        elif isinstance(outputs, (tuple, list)):
            logits = outputs[0]
        else:
            logits = outputs

        if logits is None:
            break

        # Get next token logits
        next_logits = logits[:, -1, :].clone()

        # Adaptive entropy control (inference-time)
        if entropy_controller is not None:
            next_logits = entropy_controller.scale_logits(next_logits)
            entropy_controller.update(next_logits)

        # Apply repetition penalty to previously generated tokens
        if repetition_penalty != 1.0:
            for token_id in set(generated[0, prompt_len:].tolist()):
                if next_logits[0, token_id] > 0:
                    next_logits[0, token_id] /= repetition_penalty
                else:
                    next_logits[0, token_id] *= repetition_penalty

        # Apply no_repeat_ngram blocking
        if no_repeat_ngram_size > 0 and generated.shape[1] >= no_repeat_ngram_size:
            # Get the last (n-1) tokens as the prefix
            prefix = tuple(generated[0, -(no_repeat_ngram_size - 1):].tolist())
            # Get all existing n-grams
            existing_ngrams = get_ngrams(generated[0], no_repeat_ngram_size)
            # Block tokens that would create a repeated n-gram
            for ngram in existing_ngrams:
                if ngram[:-1] == prefix:
                    # This token would complete a repeated n-gram
                    next_logits[0, ngram[-1]] = float('-inf')

        # Apply temperature
        next_logits = next_logits / temperature

        # Top-k filtering (optional, applied before top-p)
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

        # Set removed tokens to -inf
        indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
        next_logits[indices_to_remove] = float('-inf')

        # Sample next token
        probs = F.softmax(next_logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)

        # Append to sequence
        generated = torch.cat([generated, next_token], dim=1)

        # Check for EOS
        if next_token.item() == tokenizer.eos_token_id:
            break

    # Decode and return
    return tokenizer.decode(generated[0], skip_special_tokens=True)


def compute_sample_metrics(text: str) -> Dict[str, float]:
    """
    Compute quality metrics for generated text.

    Returns:
        - completion_rate: 1.0 if ends with punctuation, 0.0 otherwise
        - repetition_score: n-gram repetition rate (lower is better)
        - unique_ratio: ratio of unique tokens to total tokens
        - coherence_score: basic semantic coherence (0.0-1.0, higher is better)
    """
    words = text.split()
    if len(words) < 2:
        return {"completion": 0.0, "repetition": 1.0, "unique_ratio": 0.0, "coherence": 0.0}

    # Completion rate: ends with sentence-ending punctuation
    completion = 1.0 if text.rstrip()[-1:] in '.!?' else 0.0

    # Repetition score: bigram repetition rate
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    if bigrams:
        unique_bigrams = len(set(bigrams))
        repetition = 1.0 - (unique_bigrams / len(bigrams))
    else:
        repetition = 0.0

    # Unique token ratio
    unique_ratio = len(set(words)) / len(words) if words else 0.0

    # CRITICAL FIX: Semantic coherence check (basic heuristics)
    # Checks for common signs of gibberish vs. meaningful text
    coherence = 1.0

    # Penalty 1: Too many short words (gibberish often has many 1-2 char tokens)
    short_word_ratio = sum(1 for w in words if len(w) <= 2) / len(words)
    if short_word_ratio > 0.5:
        coherence *= 0.5

    # Penalty 2: Too many non-alphabetic tokens
    alpha_ratio = sum(1 for w in words if w.isalpha()) / len(words)
    if alpha_ratio < 0.6:
        coherence *= 0.6

    # Penalty 3: Excessive punctuation clustering (e.g., "... ,, ,,")
    punct_cluster = text.count(',,') + text.count('..') * 0.5
    if punct_cluster > 3:
        coherence *= 0.4

    # Penalty 4: Repeated single characters (e.g., "a a a a")
    single_char_repeat = sum(1 for i in range(len(words)-2)
                            if len(words[i]) == 1 and words[i] == words[i+1])
    if single_char_repeat > 2:
        coherence *= 0.3

    # Bonus: Reasonable average word length (4-8 chars is typical English)
    avg_word_len = sum(len(w) for w in words) / len(words)
    if 4.0 <= avg_word_len <= 8.0:
        coherence *= 1.1
    coherence = min(coherence, 1.0)

    return {
        "completion": completion,
        "repetition": repetition,
        "unique_ratio": unique_ratio,
        "coherence": coherence,
    }


def run_quality_samples(
    model: nn.Module,
    tokenizer,
    config: 'UnifiedTrainingConfig',
    device: torch.device,
    step: int,
    logger=None,
):
    """
    Generate sample outputs to monitor training quality.

    This provides a qualitative check that the model is learning
    meaningful language patterns, not just minimizing perplexity.

    Samples are logged with prompts, generated completions, and quality metrics.
    """
    def log(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    log("")
    log("=" * 60)
    log(f"  📝 QUALITY SAMPLES (Step {step})")
    log("=" * 60)

    # V9.6.10 Diagnostic: Show top predicted tokens for first prompt
    try:
        diag_prompt = config.sample_prompts[0] if config.sample_prompts else "The"
        diag_ids = tokenizer.encode(diag_prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            diag_out = model(diag_ids)
            if isinstance(diag_out, dict):
                diag_logits = diag_out.get('logits', diag_out.get('output'))
            else:
                diag_logits = diag_out
            # Get logits for last position
            last_logits = diag_logits[0, -1, :]
            top_probs = torch.softmax(last_logits, dim=-1)
            top_vals, top_ids = torch.topk(top_probs, 10)
            log(f"  🔍 [DIAGNOSTIC] Top-10 predicted tokens after \"{diag_prompt}\":")
            for i, (prob, tid) in enumerate(zip(top_vals, top_ids)):
                tok_str = tokenizer.decode([tid.item()])
                log(f"      {i+1}. '{tok_str}' (id={tid.item()}, p={prob.item():.4f})")
    except Exception as e:
        log(f"  🔍 [DIAGNOSTIC] Failed: {e}")

    # Aggregate metrics across all samples
    total_completion = 0.0
    total_repetition = 0.0
    total_unique = 0.0
    total_coherence = 0.0
    sample_count = 0

    for prompt in config.sample_prompts:
        try:
            # ChatGPT recommendations for quality samples:
            # temperature=0.9, top_p=0.95, top_k=50
            # repetition_penalty=1.15, no_repeat_ngram_size=3
            # Create adaptive entropy controller for inference if enabled
            _infer_entropy_ctrl = None
            if hasattr(config, 'enable_entropy_control_infer') and config.enable_entropy_control_infer:
                _ec_cfg = EntropyControlConfig(
                    enable_entropy_control_infer=True,
                    entropy_topk=getattr(config, 'entropy_topk', 50),
                    infer_h_target=getattr(config, 'infer_h_target', 0.25),
                    infer_eta=getattr(config, 'infer_eta', 0.02),
                    infer_delta_clip=getattr(config, 'infer_delta_clip', 0.05),
                    logit_scale_min=getattr(config, 'logit_scale_min', -4.0),
                    logit_scale_max=getattr(config, 'logit_scale_max', 4.0),
                )
                _init_scale = None
                if hasattr(model, 'entropy_logit_scale'):
                    _init_scale = model.entropy_logit_scale.logit_scale
                _infer_entropy_ctrl = AdaptiveEntropyController(_ec_cfg, _init_scale)
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=128,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
                entropy_controller=_infer_entropy_ctrl,
            )
            # Clean up WikiText artifacts and truncate for display
            generated = generated.strip().replace('\n', ' ')
            if _CLEAN_WIKITEXT_AVAILABLE:
                generated = clean_wikitext_artifacts(generated)
            generated = generated[:200]

            # Compute quality metrics
            metrics = compute_sample_metrics(generated)
            total_completion += metrics["completion"]
            total_repetition += metrics["repetition"]
            total_unique += metrics["unique_ratio"]
            total_coherence += metrics["coherence"]
            sample_count += 1

            log(f"  Prompt: \"{prompt}\"")
            log(f"  Output: \"{generated}\"")
            log("")
        except Exception as e:
            log(f"  ⚠️ Sampling failed for prompt '{prompt[:30]}...': {e}")

    # Log aggregate quality metrics
    if sample_count > 0:
        avg_completion = total_completion / sample_count
        avg_repetition = total_repetition / sample_count
        avg_unique = total_unique / sample_count
        avg_coherence = total_coherence / sample_count

        log("  ────────────────────────────────────────────────────────")
        log(f"  📊 SAMPLE QUALITY METRICS (n={sample_count})")
        log(f"     Completion Rate: {avg_completion*100:.0f}% (ends with punctuation)")
        log(f"     Repetition Score: {avg_repetition*100:.1f}% (lower is better)")
        log(f"     Unique Token Ratio: {avg_unique*100:.1f}%")
        log(f"     Coherence Score: {avg_coherence*100:.0f}% (semantic quality)")

        # CRITICAL FIX: Quality indicator now includes coherence
        # Previous logic was misleading - high diversity alone doesn't mean good quality
        if avg_coherence > 0.7 and avg_repetition < 0.3 and avg_unique > 0.6:
            log("     Quality: 🟢 GOOD (coherent + diverse)")
        elif avg_coherence > 0.5 and avg_repetition < 0.5:
            log("     Quality: 🟡 IMPROVING (needs better coherence)")
        else:
            log("     Quality: 🔴 NEEDS WORK (likely gibberish despite diversity)")
            log("     ⚠️  WARNING: High diversity without coherence = meaningless tokens")

    log("=" * 60)
    log("")
