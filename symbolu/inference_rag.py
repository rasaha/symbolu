"""
Symbol-U Sovereign RAG Interface
================================

Retrieval-Augmented Generation that respects the Sovereign 32D State.

The key innovation: Memory retrieval is GATED by the model's ontological state.
The "Soul" (32D State) controls whether the "Brain" (Memory) is consulted.

Gate Logic:
-----------
Retrieval is triggered if ANY of these conditions are met:
1. Sheath (Kosha) argmax == INTELLECTUAL (index 3 in kosha space)
2. Bhava argmax in [COG, RSN] (indices 4, 6 in bhava space)
3. Vritti argmax == MEMORY (index 4 in vritti space)
4. Vritti argmax == FACT AND Entropy > 4.5 (high uncertainty)

If retrieval is NOT triggered or fails, fall back to pure generation.

Safety Mechanisms:
------------------
1. Context Truncation: Respects model's max_position_embeddings
2. Natural Format: Uses instruction-like format for non-instruct models
3. Error Handling: Graceful fallback on ChromaDB/state extraction failures

Usage:
------
    from symbolu.inference_rag import generate_with_memory
    from symbolu.rag.episodic_store import EpisodicMemoryStore

    # Load model and tokenizer (from your training/inference setup)
    model = OntologicalHybridTransformer(...)
    tokenizer = ...

    # Load episodic memory
    memory = EpisodicMemoryStore("./data/episodic_memory")

    # Generate with memory-gated retrieval
    result = generate_with_memory(
        model=model,
        tokenizer=tokenizer,
        memory_store=memory,
        prompt="What is the capital of France?",
    )

    print(result["text"])
    print(f"Retrieval triggered: {result['retrieval_triggered']}")

Version: 1.1.0
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

import torch
import torch.nn.functional as F

from .rag.episodic_store import EpisodicMemoryStore
from .rag.utils.types import ScoredChunk

logger = logging.getLogger(__name__)


# =============================================================================
# Sovereign State Constants (32D Space)
# =============================================================================
# The 32D Sovereign State is structured as:
# [0:12]  - Bhavas (12 ontological aspects) - softmax normalized
# [12:17] - Koshas/Sheaths (5 consciousness layers) - softmax normalized
# [17:22] - Vrittis (5 mental states) - softmax normalized
# [22:28] - Gunas (6 system dynamics) - sigmoid activated
# [28:32] - Reserved (4 void/toroidal channels) - tanh bounded

# Bhava indices (within 32D state, indices 0-11)
BHAVA_COG = 4   # Cognition - knowing/understanding
BHAVA_RSN = 6   # Reason - logic/analysis

# Kosha indices (within 32D state, indices 12-16)
# Within the 5D kosha subspace (state[12:17]), INTELLECTUAL is index 3
KOSHA_INTELLECTUAL = 3  # Pattern/Wisdom (abstract reasoning)

# Vritti indices (within 32D state, indices 17-21)
# Within the 5D vritti subspace (state[17:22]):
VRITTI_FACT = 0     # Verified Truth (Pramana)
VRITTI_MEMORY = 4   # Recall/Weights (Smriti)

# Entropy threshold for uncertain FACT state
ENTROPY_THRESHOLD = 4.5

# Default max context length if model config not available
DEFAULT_MAX_CONTEXT = 2048

# Safety buffer for generation
CONTEXT_SAFETY_BUFFER = 50


# =============================================================================
# State Extraction
# =============================================================================

@dataclass
class SovereignStateInfo:
    """Extracted information from the 32D Sovereign State."""
    bhava_argmax: int       # Dominant Bhava (0-11)
    kosha_argmax: int       # Dominant Kosha (0-4)
    vritti_argmax: int      # Dominant Vritti (0-4)
    entropy: float          # Next-token entropy
    raw_state: torch.Tensor # Full 32D state vector


def _get_model_max_length(model: torch.nn.Module) -> int:
    """
    Extract max position embeddings from model config.

    Tries multiple common attribute names for compatibility.

    Args:
        model: The model to inspect

    Returns:
        Max sequence length (defaults to DEFAULT_MAX_CONTEXT if not found)
    """
    # Try common config attribute names
    config_attrs = ['config', 'model_config', 'transformer_config']
    length_attrs = [
        'max_position_embeddings',
        'max_seq_len',
        'max_sequence_length',
        'n_positions',
        'max_len',
    ]

    for config_attr in config_attrs:
        config = getattr(model, config_attr, None)
        if config is not None:
            for length_attr in length_attrs:
                max_len = getattr(config, length_attr, None)
                if max_len is not None:
                    return max_len

    # Try direct attributes on model
    for length_attr in length_attrs:
        max_len = getattr(model, length_attr, None)
        if max_len is not None:
            return max_len

    logger.warning(
        f"Could not determine model max length, using default: {DEFAULT_MAX_CONTEXT}"
    )
    return DEFAULT_MAX_CONTEXT


def extract_sovereign_state(
    model_output: Dict[str, torch.Tensor],
    logits_key: str = "logits",
    state_key: str = "state",
) -> Optional[SovereignStateInfo]:
    """
    Extract Sovereign State information from model output.

    Handles various output formats and provides graceful error handling.

    Args:
        model_output: Dictionary from model.forward()
        logits_key: Key for logits tensor
        state_key: Key for state tensor

    Returns:
        SovereignStateInfo with extracted components, or None if extraction fails
    """
    try:
        # Handle different output formats
        if not isinstance(model_output, dict):
            # Try to convert tuple/namedtuple to dict
            if hasattr(model_output, '_asdict'):
                model_output = model_output._asdict()
            elif hasattr(model_output, 'logits'):
                # HuggingFace CausalLMOutput style
                model_output = {'logits': model_output.logits}
                if hasattr(model_output, 'hidden_states'):
                    model_output['hidden_states'] = model_output.hidden_states
            else:
                logger.error(f"Unexpected model output type: {type(model_output)}")
                return None

        # Check for state key
        if state_key not in model_output:
            # Try alternative keys
            alt_keys = ['sovereign_state', 'ontological_state', 'hidden_state']
            for alt_key in alt_keys:
                if alt_key in model_output:
                    state_key = alt_key
                    break
            else:
                logger.warning(f"State key '{state_key}' not found in model output")
                return None

        # Get the 32D state vector (last token position)
        state = model_output[state_key]
        if state.dim() == 2:
            state = state[0]  # Take first batch item: [B, 32] -> [32]
        elif state.dim() == 3:
            state = state[0, -1]  # [B, N, 32] -> [32]

        # Verify state dimension
        if state.shape[0] < 22:
            logger.warning(f"State dimension too small: {state.shape[0]} < 22")
            return None

        # Extract subspaces
        bhavas = state[0:12]
        koshas = state[12:17]
        vrittis = state[17:22]

        # Apply softmax to get probabilities (they should already be normalized,
        # but we apply again to be safe)
        bhava_probs = F.softmax(bhavas, dim=-1)
        kosha_probs = F.softmax(koshas, dim=-1)
        vritti_probs = F.softmax(vrittis, dim=-1)

        # Get argmax indices
        bhava_argmax = bhava_probs.argmax().item()
        kosha_argmax = kosha_probs.argmax().item()
        vritti_argmax = vritti_probs.argmax().item()

        # Calculate entropy from next-token logits
        entropy = 0.0
        if logits_key in model_output:
            logits = model_output[logits_key]
            if logits.dim() == 3:
                logits = logits[0, -1]  # [B, N, V] -> [V]
            elif logits.dim() == 2:
                logits = logits[0]  # [B, V] -> [V]

            probs = F.softmax(logits, dim=-1)
            entropy = -torch.sum(probs * torch.log(probs + 1e-9)).item()

        return SovereignStateInfo(
            bhava_argmax=bhava_argmax,
            kosha_argmax=kosha_argmax,
            vritti_argmax=vritti_argmax,
            entropy=entropy,
            raw_state=state.detach(),
        )

    except Exception as e:
        logger.error(f"Failed to extract sovereign state: {e}")
        return None


# =============================================================================
# Gate Logic
# =============================================================================

def should_retrieve(state_info: Optional[SovereignStateInfo]) -> Tuple[bool, str]:
    """
    Determine if episodic memory retrieval should be triggered.

    Gate conditions (OR logic - any triggers retrieval):
    1. Kosha argmax == INTELLECTUAL (abstract reasoning mode)
    2. Bhava argmax in [COG, RSN] (cognition/reason seeking)
    3. Vritti argmax == MEMORY (recall mode)
    4. Vritti argmax == FACT AND entropy > threshold (uncertain facts)

    Args:
        state_info: Extracted Sovereign State information (can be None)

    Returns:
        Tuple of (should_retrieve: bool, reason: str)
    """
    # If state extraction failed, default to no retrieval
    if state_info is None:
        return False, "State extraction failed - skipping retrieval"

    reasons = []

    # Condition 1: Intellectual sheath active
    if state_info.kosha_argmax == KOSHA_INTELLECTUAL:
        reasons.append("Kosha=INTELLECTUAL")

    # Condition 2: Cognition or Reason bhava active
    if state_info.bhava_argmax == BHAVA_COG:
        reasons.append("Bhava=COG")
    elif state_info.bhava_argmax == BHAVA_RSN:
        reasons.append("Bhava=RSN")

    # Condition 3: Memory vritti active
    if state_info.vritti_argmax == VRITTI_MEMORY:
        reasons.append("Vritti=MEMORY")

    # Condition 4: Fact vritti with high uncertainty
    if state_info.vritti_argmax == VRITTI_FACT and state_info.entropy > ENTROPY_THRESHOLD:
        reasons.append(f"Vritti=FACT+HighEntropy({state_info.entropy:.2f})")

    should_trigger = len(reasons) > 0
    reason_str = " | ".join(reasons) if reasons else "No trigger conditions met"

    return should_trigger, reason_str


# =============================================================================
# Context Formatting with Truncation
# =============================================================================

def format_context_with_truncation(
    chunks: List[ScoredChunk],
    prompt: str,
    tokenizer,
    max_context_tokens: int,
    max_new_tokens: int,
) -> Tuple[str, List[ScoredChunk]]:
    """
    Format retrieved chunks with intelligent truncation.

    Uses the Sovereign Model's tokenizer to ensure chunks fit within
    the model's context window, accounting for the prompt and generation space.

    Format (natural instruction style for non-instruct models):
        Information:
        [chunk 1 text]

        [chunk 2 text]

        Based on the information above, answer the question.
        Question: [prompt]
        Answer:

    Args:
        chunks: List of retrieved ScoredChunk objects
        prompt: User's original prompt
        tokenizer: The Sovereign Model's tokenizer
        max_context_tokens: Model's max position embeddings
        max_new_tokens: Tokens reserved for generation

    Returns:
        Tuple of (formatted_prompt, included_chunks)
    """
    # Calculate available space for context
    prompt_template = """Information:
{context}

Based on the information above, answer the question.
Question: {prompt}
Answer:"""

    # Tokenize the template without context to get overhead
    template_without_context = prompt_template.format(context="", prompt=prompt)
    template_tokens = len(tokenizer.encode(template_without_context))

    # Available space = max_context - template - generation - buffer
    available_tokens = (
        max_context_tokens
        - template_tokens
        - max_new_tokens
        - CONTEXT_SAFETY_BUFFER
    )

    if available_tokens <= 0:
        logger.warning(
            f"No space for context: max={max_context_tokens}, "
            f"template={template_tokens}, gen={max_new_tokens}"
        )
        return prompt, []

    # Add chunks until we run out of space
    included_chunks = []
    context_parts = []
    current_tokens = 0

    for chunk in chunks:
        chunk_tokens = len(tokenizer.encode(chunk.text))

        if current_tokens + chunk_tokens <= available_tokens:
            context_parts.append(chunk.text)
            included_chunks.append(chunk)
            current_tokens += chunk_tokens
        else:
            # Try to fit a truncated version of this chunk
            remaining_tokens = available_tokens - current_tokens
            if remaining_tokens > 100:  # Only truncate if meaningful space left
                # Truncate chunk text (rough approximation)
                truncated_text = _truncate_to_tokens(
                    chunk.text, tokenizer, remaining_tokens
                )
                if truncated_text:
                    context_parts.append(truncated_text + "...")
                    included_chunks.append(chunk)
            break

    if not context_parts:
        return prompt, []

    # Format the final prompt
    context_block = "\n\n".join(context_parts)
    formatted = prompt_template.format(context=context_block, prompt=prompt)

    logger.debug(
        f"Context: {len(included_chunks)} chunks, "
        f"~{current_tokens} tokens, "
        f"available={available_tokens}"
    )

    return formatted, included_chunks


def _truncate_to_tokens(text: str, tokenizer, max_tokens: int) -> str:
    """
    Truncate text to approximately fit within max_tokens.

    Uses binary search for efficiency.
    """
    tokens = tokenizer.encode(text)
    if len(tokens) <= max_tokens:
        return text

    # Decode truncated tokens
    truncated_tokens = tokens[:max_tokens]
    return tokenizer.decode(truncated_tokens, skip_special_tokens=True)


def format_context(
    chunks: List[ScoredChunk],
    prompt: str,
) -> str:
    """
    Format retrieved chunks into the context-augmented prompt.

    Uses a natural instruction format that works better with
    non-instruct models (no special tokens like [CONTEXT START]).

    Format:
        Information:
        [chunk 1 text]

        [chunk 2 text]

        Based on the information above, answer the question.
        Question: [prompt]
        Answer:

    Args:
        chunks: List of retrieved ScoredChunk objects
        prompt: User's original prompt

    Returns:
        Formatted prompt with context
    """
    context_parts = [chunk.text for chunk in chunks]
    context_block = "\n\n".join(context_parts)

    formatted = f"""Information:
{context_block}

Based on the information above, answer the question.
Question: {prompt}
Answer:"""

    return formatted


# =============================================================================
# Main Generation Function
# =============================================================================

def generate_with_memory(
    model: torch.nn.Module,
    tokenizer,
    memory_store: EpisodicMemoryStore,
    prompt: str,
    max_new_tokens: int = 100,
    temperature: float = 1.0,
    top_k: int = 50,
    n_retrieval_results: int = 3,
    min_retrieval_score: float = 0.0,
    force_retrieval: Optional[bool] = None,
    device: Optional[torch.device] = None,
    max_context_length: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate text with Sovereign-gated episodic memory retrieval.

    This function acts as an "Agent" wrapping the model. It:
    1. Runs a diagnostic pass to get the Sovereign State
    2. Checks the gate conditions to decide on retrieval
    3. Retrieves context if triggered (with smart truncation)
    4. Generates the final response

    Safety mechanisms:
    - Context truncation respects model's max_position_embeddings
    - Natural format for non-instruct models
    - Graceful fallback on any errors

    Args:
        model: OntologicalHybridTransformer model
        tokenizer: Tokenizer for encoding/decoding
        memory_store: EpisodicMemoryStore instance
        prompt: User's input prompt
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        top_k: Top-k sampling parameter
        n_retrieval_results: Number of chunks to retrieve
        min_retrieval_score: Minimum similarity score for retrieval
        force_retrieval: Override gate logic (True=always retrieve, False=never)
        device: Device for computation (inferred from model if None)
        max_context_length: Override model's max context length

    Returns:
        Dictionary containing:
        - text: Generated text
        - retrieval_triggered: Whether retrieval was triggered
        - retrieval_reason: Reason for retrieval decision
        - retrieved_chunks: List of retrieved chunks (if any)
        - state_info: Sovereign state information (or None if extraction failed)
        - full_prompt: The actual prompt used for generation
        - truncated: Whether context was truncated
    """
    # Determine device
    if device is None:
        device = next(model.parameters()).device

    # Get model's max context length
    if max_context_length is None:
        max_context_length = _get_model_max_length(model)

    # Step 1: Diagnostic Pass - Get Sovereign State
    logger.debug("Running diagnostic pass...")
    model.eval()
    state_info = None

    try:
        with torch.no_grad():
            # Tokenize prompt
            input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

            # Forward pass to get state (no generation yet)
            outputs = model(input_ids, reset_state=True)

            # Extract state information (handles errors gracefully)
            state_info = extract_sovereign_state(outputs)

    except Exception as e:
        logger.error(f"Diagnostic pass failed: {e}")
        state_info = None

    if state_info:
        logger.debug(
            f"State: Bhava={state_info.bhava_argmax}, "
            f"Kosha={state_info.kosha_argmax}, "
            f"Vritti={state_info.vritti_argmax}, "
            f"Entropy={state_info.entropy:.2f}"
        )

    # Step 2: Gate Decision
    if force_retrieval is not None:
        retrieval_triggered = force_retrieval
        retrieval_reason = "Forced" if force_retrieval else "Disabled"
    else:
        retrieval_triggered, retrieval_reason = should_retrieve(state_info)

    logger.info(f"Retrieval decision: {retrieval_triggered} ({retrieval_reason})")

    # Step 3: Retrieval (if triggered)
    retrieved_chunks = []
    final_prompt = prompt
    context_truncated = False

    if retrieval_triggered:
        try:
            chunks = memory_store.query_memory(
                query_text=prompt,
                n_results=n_retrieval_results,
                min_score=min_retrieval_score,
            )

            if chunks:
                # Format with truncation to fit model's context window
                final_prompt, included_chunks = format_context_with_truncation(
                    chunks=chunks,
                    prompt=prompt,
                    tokenizer=tokenizer,
                    max_context_tokens=max_context_length,
                    max_new_tokens=max_new_tokens,
                )

                retrieved_chunks = included_chunks
                context_truncated = len(included_chunks) < len(chunks)

                if included_chunks:
                    logger.info(
                        f"Retrieved {len(chunks)} chunks, "
                        f"included {len(included_chunks)} after truncation"
                    )
                else:
                    # No space for any context
                    logger.warning("No space for context - falling back to pure generation")
                    final_prompt = prompt
                    retrieval_triggered = False
                    retrieval_reason = "Context too long"
            else:
                logger.warning("Retrieval returned no results - falling back to pure generation")
                retrieval_triggered = False
                retrieval_reason = "No results"

        except Exception as e:
            logger.error(f"Retrieval failed: {e} - falling back to pure generation")
            retrieval_triggered = False
            retrieval_reason = f"Error: {e}"
            final_prompt = prompt

    # Step 4: Generation
    final_prompt_tokens = len(tokenizer.encode(final_prompt))
    logger.debug(f"Generating with prompt: {final_prompt_tokens} tokens")

    try:
        with torch.no_grad():
            # Re-tokenize the (possibly augmented) prompt
            input_ids = tokenizer.encode(final_prompt, return_tensors="pt").to(device)

            # Generate
            if hasattr(model, 'generate'):
                output_ids = model.generate(
                    input_ids,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_k=top_k,
                )
            else:
                # Fallback for models without generate method
                output_ids = _simple_generate(
                    model, input_ids, max_new_tokens, temperature, top_k
                )

        # Decode output (only the new tokens)
        if isinstance(output_ids, dict):
            output_ids = output_ids.get("sequences", output_ids.get("logits"))
        if isinstance(output_ids, torch.Tensor):
            # Get only the generated part
            new_tokens = output_ids[0, input_ids.shape[1]:]
            generated_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        else:
            generated_text = str(output_ids)

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        generated_text = f"[Generation error: {e}]"

    return {
        "text": generated_text,
        "retrieval_triggered": retrieval_triggered,
        "retrieval_reason": retrieval_reason,
        "retrieved_chunks": [
            {"text": c.text, "score": c.score, "source": c.metadata.get("source")}
            for c in retrieved_chunks
        ],
        "state_info": {
            "bhava_argmax": state_info.bhava_argmax,
            "kosha_argmax": state_info.kosha_argmax,
            "vritti_argmax": state_info.vritti_argmax,
            "entropy": state_info.entropy,
        } if state_info else None,
        "full_prompt": final_prompt,
        "truncated": context_truncated,
        "prompt_tokens": final_prompt_tokens,
    }


def _simple_generate(
    model: torch.nn.Module,
    input_ids: torch.Tensor,
    max_new_tokens: int,
    temperature: float,
    top_k: int,
) -> torch.Tensor:
    """
    Simple autoregressive generation fallback.

    Args:
        model: The model
        input_ids: Input token IDs
        max_new_tokens: Max tokens to generate
        temperature: Sampling temperature
        top_k: Top-k sampling

    Returns:
        Generated token IDs
    """
    for _ in range(max_new_tokens):
        outputs = model(input_ids)

        # Handle different output formats
        if isinstance(outputs, dict):
            logits = outputs["logits"][:, -1, :]
        elif hasattr(outputs, 'logits'):
            logits = outputs.logits[:, -1, :]
        else:
            logits = outputs[0][:, -1, :]

        logits = logits / temperature

        if top_k > 0:
            v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
            logits[logits < v[:, [-1]]] = float('-inf')

        probs = F.softmax(logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)
        input_ids = torch.cat([input_ids, next_token], dim=1)

    return input_ids


# =============================================================================
# Batch Generation
# =============================================================================

def generate_batch_with_memory(
    model: torch.nn.Module,
    tokenizer,
    memory_store: EpisodicMemoryStore,
    prompts: List[str],
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Generate for multiple prompts.

    Note: Currently processes sequentially. Could be optimized for batch
    processing if needed.

    Args:
        model: OntologicalHybridTransformer model
        tokenizer: Tokenizer
        memory_store: EpisodicMemoryStore instance
        prompts: List of prompts
        **kwargs: Additional arguments for generate_with_memory

    Returns:
        List of result dictionaries
    """
    results = []
    for prompt in prompts:
        result = generate_with_memory(
            model=model,
            tokenizer=tokenizer,
            memory_store=memory_store,
            prompt=prompt,
            **kwargs,
        )
        results.append(result)
    return results


# =============================================================================
# Convenience Functions
# =============================================================================

def get_state_description(state_info: Optional[Dict[str, Any]]) -> str:
    """
    Get a human-readable description of the Sovereign State.

    Args:
        state_info: State info dictionary from generate_with_memory result

    Returns:
        Human-readable description
    """
    if state_info is None:
        return "State: Unknown (extraction failed)"

    bhava_names = [
        'POT', 'IDN', 'EXE', 'STR', 'COG', 'AGY',
        'RSN', 'PRP', 'WIT', 'UNI', 'INT', 'ABS'
    ]
    kosha_names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
    vritti_names = ['FACT', 'ERROR', 'IMAGINATION', 'VOID', 'MEMORY']

    bhava = bhava_names[state_info['bhava_argmax']]
    kosha = kosha_names[state_info['kosha_argmax']]
    vritti = vritti_names[state_info['vritti_argmax']]

    return (
        f"Bhava: {bhava} | "
        f"Kosha: {kosha} | "
        f"Vritti: {vritti} | "
        f"Entropy: {state_info['entropy']:.2f}"
    )
