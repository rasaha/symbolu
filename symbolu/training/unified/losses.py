"""
Loss computation functions for ontological, sovereign, and phase models.

Handles priority-based loss selection (Sovereign-Lagrangian vs Sovereign-1 vs legacy),
chunked forward passes for long sequences, and phase loss computation.

Extracted from train_unified_llm.py
"""

import math
from typing import Optional, Dict, List, Tuple, Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.training.unified.config import UnifiedTrainingConfig

# Import Sovereign-1 components
try:
    from symbolu.sovereign import SovereignLoss, SovereignObserver
    from symbolu.sovereign.loss import LegacyLossAdapter
    SOVEREIGN_AVAILABLE = True
except ImportError:
    SOVEREIGN_AVAILABLE = False


def compute_ontological_loss(
    outputs: Dict[str, torch.Tensor],
    targets: torch.Tensor,
    config: UnifiedTrainingConfig,
    sovereign_loss: Optional['SovereignLoss'] = None,
    sovereign_engine: Optional['SovereignEngine'] = None,
    phase_angles: Optional[List[torch.Tensor]] = None,
    epoch: int = 0,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute loss for ontological model.

    Priority order:
    1. Sovereign-Lagrangian Loss (Patent B1/S3) - if enable_sovereign_loss
    2. Sovereign-1 hardened loss - if use_sovereign_loss
    3. Legacy loss (fallback)

    Sovereign-Lagrangian Loss combines:
    - L_task: Standard cross-entropy
    - L_consistency [B1]: Forward/Backward feasibility alignment
    - L_align [S3]: Global coherence penalty

    Sovereign-1 hardened loss uses:
    - Decomposed state friction (prevents Signal Washing)
    - Weighted signals (prioritizes R-Signal over C-Signal)
    - Bhava transition penalty

    Legacy loss uses:
    - Language modeling loss (cross-entropy)
    - Bhava relationship consistency loss
    - Global coherence regularization
    - Entropy regularization
    """
    metrics = {}
    logits = outputs["logits"]
    B, N, V = logits.shape

    # Compute semantic entropy [S5] for all code paths
    with torch.no_grad():
        probs = F.softmax(logits, dim=-1)
        entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
        max_entropy = math.log(V)
        onto_entropy = (entropy / max_entropy).mean().item()
    metrics["onto_entropy"] = onto_entropy

    # 1. Language modeling loss (always computed for PPL tracking)
    lm_loss = F.cross_entropy(
        logits.view(-1, V),
        targets.view(-1),
        ignore_index=-100,
    )
    metrics["lm_loss"] = lm_loss.item()
    metrics["ppl"] = math.exp(min(lm_loss.item(), 20))

    # Priority 1: Sovereign-Lagrangian Loss (Patent B1/S3)
    if config.enable_sovereign_loss and sovereign_engine is not None:
        # Get R-Signal from outputs (the Authority's intent)
        r_signal = outputs.get('r_signal', None)
        if r_signal is None:
            # Fall back to ontological_probs expanded to 48D
            onto_probs = outputs.get('ontological_probs', torch.zeros(B, N, 12, device=logits.device))
            if onto_probs.dim() == 2:
                onto_probs = onto_probs.unsqueeze(1).expand(-1, N, -1)
            # Expand 12D to 48D by repeating
            r_signal = onto_probs.repeat(1, 1, 4)

        # Get Guna Coherence from outputs if available
        gc = outputs.get('global_coherence', None)
        if gc is not None and isinstance(gc, torch.Tensor):
            gc = gc.mean()

        # [S5/B1] Scale lambda_b1 based on entropy - higher entropy = stronger consistency
        b1_scale = 1.0
        if onto_entropy > 0.60:
            # Scale up to 1.5x when entropy is very high (Rajasic state)
            excess = (onto_entropy - 0.60) / 0.40  # Scale 0.60-1.0 to 0-1
            b1_scale = 1.0 + excess * 0.5  # 1.0 to 1.5
            # Temporarily boost lambda_b1
            original_lambda_b1 = sovereign_engine.config.lambda_b1
            sovereign_engine.config.lambda_b1 = original_lambda_b1 * b1_scale

        # Compute Sovereign-Lagrangian loss
        total_loss, sov_metrics = sovereign_engine.sovereign_loss(
            logits, targets, r_signal,
            phase_angles=phase_angles,
            guna_coherence=gc,
        )

        # Restore original lambda_b1 if scaled
        if b1_scale > 1.0:
            sovereign_engine.config.lambda_b1 = original_lambda_b1

        # Merge metrics
        metrics.update({
            "total_loss": total_loss.item(),
            "l_task": sov_metrics["l_task"],
            "l_consistency": sov_metrics["l_consistency"],
            "l_align": sov_metrics["l_align"],
            "gc": sov_metrics["gc"],
            "sf_mean": sov_metrics["sf_mean"],
            "sb_mean": sov_metrics["sb_mean"],
            "b1_scale": b1_scale,  # Track the scaling factor
        })

        # Add coherence from outputs if available
        if "global_coherence" in outputs:
            metrics["coherence"] = outputs["global_coherence"].mean().item()

        return total_loss, metrics

    # Priority 2: Sovereign-1 hardened loss
    if config.use_sovereign_loss and sovereign_loss is not None and SOVEREIGN_AVAILABLE:
        # Build state from outputs
        onto_probs = outputs.get('ontological_probs', torch.zeros(B, 12, device=logits.device))
        bhava_vec = outputs.get('bhava_vector', torch.zeros(B, 144, device=logits.device))
        coherence = outputs.get('global_coherence', torch.ones(B, device=logits.device))

        # Construct 128D predicted state
        predicted_state = _build_sovereign_state(onto_probs, bhava_vec, coherence)
        # Target state (self-supervised: predict next state)
        target_state = torch.zeros_like(predicted_state)

        # Compute Sovereign loss
        total_loss, sov_metrics = sovereign_loss(
            logits, targets, predicted_state, target_state, epoch=epoch
        )

        # Merge metrics
        metrics.update({
            "total_loss": total_loss.item(),
            "sovereign_friction": sov_metrics.get("loss_friction", 0),
            "sovereign_transition": sov_metrics.get("loss_transition", 0),
            "onto_phoneme_ratio": sov_metrics.get("ontology_to_phoneme_ratio", 0),
            "meaning_fraction": sov_metrics.get("meaning_fraction", 0),
            "signal_washing": sov_metrics.get("signal_washing", False),
            "semantic_healthy": sov_metrics.get("semantic_healthy", False),
        })

        # Add coherence from outputs if available
        if "global_coherence" in outputs:
            metrics["coherence"] = outputs["global_coherence"].mean().item()

        return total_loss, metrics

    # Legacy loss computation (fallback)
    # 2. Bhava relationship consistency loss
    if "relationship_matrix" in outputs:
        rel_matrix = outputs["relationship_matrix"]  # [B, 12, 12]
        rel_diff = (rel_matrix[:, 1:, :] - rel_matrix[:, :-1, :]).abs().mean()
        bhava_loss = rel_diff
        metrics["bhava_loss"] = bhava_loss.item()
    else:
        bhava_loss = torch.tensor(0.0, device=logits.device)

    # 3. Global coherence regularization
    if "global_coherence" in outputs and not config.no_coherence_loss:
        coherence = outputs["global_coherence"].mean()
        coherence_loss = 1.0 - coherence
        metrics["coherence"] = coherence.item()
        metrics["coherence_loss"] = coherence_loss.item()
    else:
        coherence_loss = torch.tensor(0.0, device=logits.device)
        if "global_coherence" in outputs:
            # Still track coherence metric even if loss is disabled
            metrics["coherence"] = outputs["global_coherence"].mean().item()

    # 4. Entropy regularization
    if "ontological_probs" in outputs:
        probs = outputs["ontological_probs"]
        entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
        target_entropy = 1.5
        entropy_loss = (entropy - target_entropy).abs()
        metrics["onto_entropy"] = entropy.item()
    else:
        entropy_loss = torch.tensor(0.0, device=logits.device)

    # Combine losses
    total_loss = (
        config.lambda_lm * lm_loss +
        config.bhava_lambda * bhava_loss +
        config.coherence_lambda * coherence_loss +
        config.lambda_entropy * entropy_loss
    )

    metrics["total_loss"] = total_loss.item()

    return total_loss, metrics


def _build_sovereign_state(
    onto_probs: torch.Tensor,  # [B, 12]
    bhava_vec: torch.Tensor,   # [B, 144]
    coherence: torch.Tensor,   # [B]
) -> torch.Tensor:
    """Build 128D Sovereign state from ontological outputs."""
    B = onto_probs.shape[0]
    device = onto_probs.device

    # Guna [16]: Derived from coherence
    guna = coherence.unsqueeze(-1).expand(-1, 16)

    # S-Signal [32]: First 32 dims of bhava
    s_signal = bhava_vec[:, :32] if bhava_vec.shape[1] >= 32 else F.pad(bhava_vec, (0, 32 - bhava_vec.shape[1]))

    # R-Signal [48]: Ontology (12) expanded + bhava subset
    r_onto = F.pad(onto_probs, (0, 36))  # 12 -> 48
    if bhava_vec.shape[1] >= 80:
        bhava_r = bhava_vec[:, 32:80]  # 48 dims
    elif bhava_vec.shape[1] > 32:
        bhava_r = F.pad(bhava_vec[:, 32:], (0, 80 - bhava_vec.shape[1]))  # Pad to 48
    else:
        bhava_r = torch.zeros(B, 48, device=device)
    r_signal = r_onto + bhava_r * 0.1

    # C-Signal [32]: Remaining bhava or zeros
    if bhava_vec.shape[1] >= 112:
        c_signal = bhava_vec[:, 80:112]  # 32 dims
    elif bhava_vec.shape[1] > 80:
        c_signal = F.pad(bhava_vec[:, 80:], (0, 112 - bhava_vec.shape[1]))  # Pad to 32
    else:
        c_signal = torch.zeros(B, 32, device=device)

    return torch.cat([guna, s_signal, r_signal, c_signal], dim=-1)


def forward_chunked(
    model: torch.nn.Module,
    input_ids: torch.Tensor,
    chunk_size: int,
    return_decorr_loss: bool = False,
) -> Dict[str, torch.Tensor]:
    """
    V10.2.2: Chunked forward pass for training long sequences.

    Processes input in chunks, maintaining Phase state across chunks:
    - Phase attention persists state (temporal memory)
    - Local attention resets per chunk (spatial reasoning)
    - Gradients flow through entire sequence

    Args:
        model: HybridPhaseTransformer model
        input_ids: [B, N] token indices (full sequence)
        chunk_size: Size of each chunk
        return_decorr_loss: Whether to compute decorrelation loss

    Returns:
        Dict with 'logits' and optionally 'decorr_loss'
    """
    B, N = input_ids.shape
    device = input_ids.device

    # Process in chunks, accumulating logits
    all_logits = []
    layer_states = None  # Persists across chunks

    for chunk_start in range(0, N, chunk_size):
        chunk_end = min(chunk_start + chunk_size, N)
        chunk_ids = input_ids[:, chunk_start:chunk_end]

        # Forward chunk with state management
        result, layer_states = model.forward_chunk(
            chunk_ids,
            chunk_offset=chunk_start,
            prev_layer_states=layer_states,
        )

        all_logits.append(result['logits'])

    # Concatenate all chunk logits
    logits = torch.cat(all_logits, dim=1)  # [B, N, V]

    outputs = {'logits': logits}

    # V10.14.10: Propagate slot tensors from last chunk for retrieval loss.
    # The training loop expects _slot_keys/_slot_vals/_slot_hidden in the
    # output dict to compute auxiliary retrieval loss for slot memory.
    for _slot_key in ('_slot_keys', '_slot_vals', '_slot_hidden'):
        if _slot_key in result:
            outputs[_slot_key] = result[_slot_key]

    # Decorrelation loss not supported in chunked mode yet
    # (would need to accumulate across chunks)
    if return_decorr_loss:
        outputs['decorr_loss'] = torch.tensor(0.0, device=device)

    return outputs


def compute_phase_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    config: UnifiedTrainingConfig,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """Compute loss for phase/hybrid models."""
    B, N, V = logits.shape

    lm_loss = F.cross_entropy(
        logits.reshape(-1, V),
        targets.reshape(-1),
        ignore_index=-100,
    )

    total_loss = lm_loss

    # V10.7.2: z-loss regularization — penalizes log(sum(exp(logits)))^2
    # Prevents unbounded logit norm growth during generation.
    # From PaLM/ST-MoE: z_loss = λ * mean(log(Σ_j exp(z_j))^2)
    # This is differentiable and gently pushes logits toward zero.
    z_loss_weight = getattr(config, 'z_loss_weight', 1e-4)
    if z_loss_weight > 0:
        log_z = torch.logsumexp(logits, dim=-1)  # [B, N]
        z_loss = z_loss_weight * (log_z ** 2).mean()
        total_loss = total_loss + z_loss
    else:
        z_loss = torch.tensor(0.0, device=logits.device)

    # Compute entropy for Sattvic controller (prevents variance=0.0 stagnation bug)
    # V10.7.2: Chunk over sequence dim to avoid OOM at long sequences
    # (full softmax [B,N,V] = B*N*V*4 bytes, e.g. 24GB at seq=32k, V=50k)
    with torch.no_grad():
        chunk_size = max(1, min(1024, N))  # Process 1024 tokens at a time
        entropy_sum = 0.0
        token_count = 0
        for start in range(0, N, chunk_size):
            end = min(start + chunk_size, N)
            chunk_logits = logits[:, start:end, :]  # [B, chunk, V]
            probs = F.softmax(chunk_logits, dim=-1)
            token_entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
            entropy_sum += token_entropy.sum().item()
            token_count += token_entropy.numel()
            del probs, token_entropy, chunk_logits
        max_entropy = math.log(V)
        normalized_entropy = (entropy_sum / token_count) / max_entropy

    metrics = {
        "lm_loss": lm_loss.item(),
        "z_loss": z_loss.item(),
        "ppl": math.exp(min(lm_loss.item(), 20)),
        "total_loss": total_loss.item(),
        "onto_entropy": normalized_entropy,  # Required for Sattvic stagnation detection
    }

    return total_loss, metrics

