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

Version: 1.0.0
"""

import logging
from typing import Dict, Any, Optional, List
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


def extract_sovereign_state(
    model_output: Dict[str, torch.Tensor],
    logits_key: str = "logits",
    state_key: str = "state",
) -> SovereignStateInfo:
    """
    Extract Sovereign State information from model output.

    Args:
        model_output: Dictionary from model.forward()
        logits_key: Key for logits tensor
        state_key: Key for state tensor

    Returns:
        SovereignStateInfo with extracted components
    """
    # Get the 32D state vector (last token position)
    state = model_output[state_key]
    if state.dim() == 2:
        state = state[0]  # Take first batch item
    elif state.dim() == 3:
        state = state[0, -1]  # [B, N, 32] -> [32]

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
        raw_state=state,
    )


# =============================================================================
# Gate Logic
# =============================================================================

def should_retrieve(state_info: SovereignStateInfo) -> tuple:
    """
    Determine if episodic memory retrieval should be triggered.

    Gate conditions (OR logic - any triggers retrieval):
    1. Kosha argmax == INTELLECTUAL (abstract reasoning mode)
    2. Bhava argmax in [COG, RSN] (cognition/reason seeking)
    3. Vritti argmax == MEMORY (recall mode)
    4. Vritti argmax == FACT AND entropy > threshold (uncertain facts)

    Args:
        state_info: Extracted Sovereign State information

    Returns:
        Tuple of (should_retrieve: bool, reason: str)
    """
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
# Context Formatting
# =============================================================================

def format_context(
    chunks: List[ScoredChunk],
    prompt: str,
) -> str:
    """
    Format retrieved chunks into the context-augmented prompt.

    Format:
        [CONTEXT START]
        Source: WikiText-103 (Chunk 1)
        ...content...

        Source: WikiText-103 (Chunk 2)
        ...content...
        [CONTEXT END]

        Question: [prompt]
        Answer:

    Args:
        chunks: List of retrieved ScoredChunk objects
        prompt: User's original prompt

    Returns:
        Formatted prompt with context
    """
    context_parts = []

    for i, chunk in enumerate(chunks, 1):
        source = chunk.metadata.get("source", "WikiText-103")
        context_parts.append(f"Source: {source} (Chunk {i})")
        context_parts.append(chunk.text)
        context_parts.append("")  # Empty line between chunks

    context_block = "\n".join(context_parts).strip()

    formatted = f"""[CONTEXT START]
{context_block}
[CONTEXT END]

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
) -> Dict[str, Any]:
    """
    Generate text with Sovereign-gated episodic memory retrieval.

    This function acts as an "Agent" wrapping the model. It:
    1. Runs a diagnostic pass to get the Sovereign State
    2. Checks the gate conditions to decide on retrieval
    3. Retrieves context if triggered (or falls back to pure generation)
    4. Generates the final response

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

    Returns:
        Dictionary containing:
        - text: Generated text
        - retrieval_triggered: Whether retrieval was triggered
        - retrieval_reason: Reason for retrieval decision
        - retrieved_chunks: List of retrieved chunks (if any)
        - state_info: Sovereign state information
        - full_prompt: The actual prompt used for generation
    """
    # Determine device
    if device is None:
        device = next(model.parameters()).device

    # Step 1: Diagnostic Pass - Get Sovereign State
    logger.debug("Running diagnostic pass...")
    model.eval()

    with torch.no_grad():
        # Tokenize prompt
        input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

        # Forward pass to get state (no generation yet)
        outputs = model(input_ids, reset_state=True)

        # Extract state information
        state_info = extract_sovereign_state(outputs)

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

    if retrieval_triggered:
        try:
            chunks = memory_store.query_memory(
                query_text=prompt,
                n_results=n_retrieval_results,
                min_score=min_retrieval_score,
            )

            if chunks:
                retrieved_chunks = chunks
                final_prompt = format_context(chunks, prompt)
                logger.info(f"Retrieved {len(chunks)} chunks")
            else:
                logger.warning("Retrieval returned no results - falling back to pure generation")
                retrieval_triggered = False
                retrieval_reason = "No results"

        except Exception as e:
            logger.error(f"Retrieval failed: {e} - falling back to pure generation")
            retrieval_triggered = False
            retrieval_reason = f"Error: {e}"

    # Step 4: Generation
    logger.debug(f"Generating with prompt length: {len(final_prompt)}")

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
        },
        "full_prompt": final_prompt,
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
        logits = outputs["logits"][:, -1, :]
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

def get_state_description(state_info: Dict[str, Any]) -> str:
    """
    Get a human-readable description of the Sovereign State.

    Args:
        state_info: State info dictionary from generate_with_memory result

    Returns:
        Human-readable description
    """
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
