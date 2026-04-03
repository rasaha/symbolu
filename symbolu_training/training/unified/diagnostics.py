import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Any, Tuple

from symbolu.phase_transformer import (
    BHAVA_NAMES,
    KOSHA_NAMES,
    BHAVA_SLICE,
    KOSHA_SLICE,
    VRITTI_SLICE,
    GUNA_SLICE,
    get_sovereign_state_summary,
)


# =============================================================================
# KOSHA-VRITTI DIAGNOSTIC SYSTEM
# =============================================================================


def compute_layer_gradient_norm(model: nn.Module, layer_idx: int) -> float:
    """
    V9.7.0: Compute gradient norm for a specific transformer layer.

    This enables layer-specific Kosha diagnostics by measuring the gradient
    magnitude at the target layer (e.g., Layer 9 for O9_WITNESSES).

    Args:
        model: The model with gradients computed
        layer_idx: Which layer to measure (0-11)

    Returns:
        Gradient L2 norm for that layer's parameters
    """
    layer_grad_norm = 0.0
    layer_found = False

    # Try to find transformer layers in common locations
    layers = None
    for attr in ['layers', 'blocks', 'transformer_blocks', 'encoder_layers', 'decoder_layers']:
        if hasattr(model, attr):
            candidate = getattr(model, attr)
            if isinstance(candidate, nn.ModuleList) and len(candidate) > layer_idx:
                layers = candidate
                break

    if layers is not None and layer_idx < len(layers):
        layer = layers[layer_idx]
        for param in layer.parameters():
            if param.grad is not None:
                layer_grad_norm += param.grad.norm().item() ** 2
                layer_found = True
        layer_grad_norm = math.sqrt(layer_grad_norm) if layer_grad_norm > 0 else 0.0

    # If layer not found, return 0 (caller will use fallback)
    return layer_grad_norm if layer_found else 0.0


def apply_kosha_phase_steering(
    embeddings: torch.Tensor,
    target_angle_rad: float,
    steering_force: float = 0.15,
) -> torch.Tensor:
    """
    Apply phase coupling steering to rotate embeddings toward target angle.

    This implements the 'Mind-Body Bridge' that couples:
    - Entity State (Entropy/Gradients) → target_angle
    - Representation (Embeddings) → current phase

    The steering nudges the embedding phase toward the geometric target,
    solving the 'Mind-Body Split' that causes hallucinations.

    Args:
        embeddings: Tensor of shape [..., D] where D is embedding dimension
        target_angle_rad: Target angle in radians (from atan2(t, r))
        steering_force: Nudge strength (0.0-1.0, default 0.15 = gentle)

    Returns:
        Steered embeddings with phase rotated toward target
    """
    with torch.no_grad():
        # Treat embedding pairs as complex numbers: (dim_0, dim_1) = (Re, Im)
        # This assumes the embedding dimension is even
        D = embeddings.shape[-1]
        if D % 2 != 0:
            return embeddings  # Can't do complex pairing with odd dimension

        # Reshape to pairs: [..., D] -> [..., D//2, 2]
        emb_pairs = embeddings.view(*embeddings.shape[:-1], D // 2, 2)
        real = emb_pairs[..., 0]  # Real part
        imag = emb_pairs[..., 1]  # Imaginary part

        # Compute current phase and magnitude for each pair
        current_phase = torch.atan2(imag, real)  # [-π, π]
        magnitude = torch.sqrt(real ** 2 + imag ** 2 + 1e-8)

        # Calculate rotation needed (target - current)
        # Wrap to [-π, π] to get shortest rotation
        rotation_needed = target_angle_rad - current_phase
        rotation_needed = torch.atan2(torch.sin(rotation_needed), torch.cos(rotation_needed))

        # Apply gentle nudge (only a fraction of the full rotation)
        nudge = rotation_needed * steering_force

        # Compute new phase
        new_phase = current_phase + nudge

        # Reconstruct embeddings with new phase, same magnitude
        new_real = magnitude * torch.cos(new_phase)
        new_imag = magnitude * torch.sin(new_phase)

        # Stack and reshape back: [..., D//2, 2] -> [..., D]
        steered_pairs = torch.stack([new_real, new_imag], dim=-1)
        steered_embeddings = steered_pairs.view(*embeddings.shape)

    # Return with gradients enabled (clone to allow gradient flow)
    return steered_embeddings.clone().detach().requires_grad_(embeddings.requires_grad)


def compute_kosha_steering_stats(
    embeddings: torch.Tensor,
    target_angle_rad: float,
) -> Dict[str, float]:
    """Compute statistics about current embedding phase vs target."""
    with torch.no_grad():
        D = embeddings.shape[-1]
        if D % 2 != 0:
            return {'phase_error': 0.0, 'mean_phase': 0.0}

        emb_pairs = embeddings.view(*embeddings.shape[:-1], D // 2, 2)
        real = emb_pairs[..., 0]
        imag = emb_pairs[..., 1]

        current_phase = torch.atan2(imag, real)
        mean_phase = current_phase.mean().item()

        # Phase error (how far from target)
        phase_error = abs(target_angle_rad - mean_phase)
        phase_error = min(phase_error, 2 * math.pi - phase_error)  # Shortest arc

    return {
        'phase_error': math.degrees(phase_error),
        'mean_phase': math.degrees(mean_phase),
        'target_phase': math.degrees(target_angle_rad),
    }


def compute_kosha_vritti_diagnostics(
    logits: torch.Tensor,
    grad_norm: float,
    hidden_states: Optional[List[torch.Tensor]] = None,
    metrics: Optional[Dict[str, float]] = None,
    diagnostic_layer: int = 9,  # V9.7.0: Layer-specific diagnostics
    layer_grad_norm: Optional[float] = None,  # V9.7.0: Layer-specific gradient
) -> Dict[str, Any]:
    """
    Compute Kosha-Vritti diagnostic coordinates.

    V9.7.0: Now computes layer-specific diagnostics for accurate Kosha measurement.
    - Reality Axis (r): Computed from diagnostic_layer hidden state entropy
    - Time Axis (t): Computed from layer-specific gradient norm (or total if unavailable)

    This is a READ-ONLY diagnostic system that maps training state to:
    - Reality Axis (r): +1 (Unmanifest/uncertain) to -1 (Manifest/confident)
    - Time Axis (t): -1 (Past/Smriti) to +1 (Future/Pramana)
    - Phase Angle: Current position in Kosha space (0-360°)
    - Vritti State: Cognitive mode classification

    Kosha zones (Cartesian Quadrants per Symbolu Ontology):
    - Q1 (0-90°):   +r, +t = BLISSFUL (Unity/Integration) - optimal flow
    - Q2 (90-180°): -r, +t = INTELLECTUAL (Pattern/Wisdom) - valid learning
    - Q3 (180-270°): -r, -t = MATERIAL (Physicality/Syntax) - execution
    - Q4 (270-360°): +r, -t = MENTAL (Semantics/Meaning) - recall

    Vritti states (with corrected Reality axis):
    - FACT (Verified Truth): r < -0.3, t > 0.2 - confident learning
    - ERROR (Hallucination): r < -0.5, t < -0.2 - over-confident, stagnant
    - IMAGINATION (Conceptualization): -0.3 < r < 0.3 - conceptual exploration
    - VOID (Null State): r > 0.3, |t| < 0.2 - uncertain and stuck
    - MEMORY (Recall/Weights): r < 0, t < -0.3 - confident but decaying
    """
    result = {}
    result['diagnostic_layer'] = diagnostic_layer

    with torch.no_grad():
        # =========================================================================
        # REALITY AXIS (r): Layer-Specific Hidden State Entropy
        # V9.7.0: Compute from diagnostic_layer hidden states, not final logits
        # High activation entropy = uncertain (-1), Low = confident/focused (+1)
        # =========================================================================
        layer_entropy = None
        if hidden_states is not None and len(hidden_states) > diagnostic_layer:
            layer_hidden = hidden_states[diagnostic_layer]  # [B, N, D]
            if layer_hidden is not None and layer_hidden.numel() > 0:
                # Compute activation entropy across the hidden dimension
                # Use softmax to get "attention" distribution over features
                # This measures how focused vs distributed the activations are
                layer_abs = layer_hidden.abs().float()  # [B, N, D]
                # Normalize to probability-like distribution per position
                layer_probs = layer_abs / (layer_abs.sum(dim=-1, keepdim=True) + 1e-10)
                # Compute entropy: H = -sum(p * log(p))
                log_probs = torch.log(layer_probs + 1e-10)
                position_entropy = -(layer_probs * log_probs).sum(dim=-1)  # [B, N]
                layer_entropy = position_entropy.mean().item()

                # Normalize: max entropy for D dimensions = log(D)
                D = layer_hidden.shape[-1]
                max_entropy = math.log(D)  # e.g., log(768) ≈ 6.6 for typical models
                # Map: 0 → +1 (focused/manifest), max → -1 (diffuse/unmanifest)
                r = 1.0 - (2.0 * layer_entropy / max_entropy)
                r = max(-1.0, min(1.0, r))
                result['r'] = r
                result['entropy'] = layer_entropy
                result['entropy_source'] = f'layer_{diagnostic_layer}'

        # Fallback to logits entropy if layer-specific not available
        if 'r' not in result:
            if logits is not None and logits.numel() > 0:
                probs = F.softmax(logits.float(), dim=-1)
                log_probs = torch.log(probs + 1e-10)
                entropy = -(probs * log_probs).sum(dim=-1).mean()
                max_entropy = 12.0
                r = 1.0 - (2.0 * entropy.item() / max_entropy)
                r = max(-1.0, min(1.0, r))
                result['r'] = r
                result['entropy'] = entropy.item()
                result['entropy_source'] = 'logits_fallback'
            else:
                result['r'] = 0.0
                result['entropy'] = 6.0
                result['entropy_source'] = 'default'

        # =========================================================================
        # TIME AXIS (t): Layer-Specific Gradient Norm
        # V9.7.0: Use layer_grad_norm if provided, otherwise fall back to total
        # High grad = future-oriented/learning (+1), Low = past-oriented/memory (-1)
        # =========================================================================
        effective_grad_norm = layer_grad_norm if layer_grad_norm is not None else grad_norm

        if effective_grad_norm > 0:
            log_grad = math.log10(effective_grad_norm + 1e-8)
            # Map: log10(0.01)=-2 → -1, log10(1)=0 → 0, log10(100)=2 → +1
            t = log_grad / 3.0
            t = max(-1.0, min(1.0, t))
        else:
            t = 0.0
        result['t'] = t
        result['grad_norm'] = effective_grad_norm
        result['grad_source'] = f'layer_{diagnostic_layer}' if layer_grad_norm is not None else 'total'

        # =========================================================================
        # PHASE ANGLE: Geometric Truth using atan2(t, r)
        # This ensures the compass matches the map (r,t quadrant)
        # Standard polar angle: 0° = +r axis, counter-clockwise positive
        #   Q1 (0-90°):   +r, +t = BLISSFUL
        #   Q2 (90-180°): -r, +t = INTELLECTUAL
        #   Q3 (180-270°): -r, -t = MATERIAL
        #   Q4 (270-360°): +r, -t = MENTAL
        # =========================================================================
        # atan2 returns [-180, 180], we convert to [0, 360]
        raw_angle = math.atan2(t, r) * 180 / math.pi  # Returns [-180, 180]
        phase_angle = raw_angle if raw_angle >= 0 else raw_angle + 360  # Convert to [0, 360]

        result['phase_angle'] = phase_angle

        # Compute target angle for steering (same as phase_angle when aligned)
        result['target_angle'] = phase_angle

        # =========================================================================
        # KOSHA ZONE: Direct Cartesian Quadrant Classification (Gemini Fix)
        # Use r,t coordinates directly instead of phase angle for accuracy
        #   Q1: +r, +t = BLISSFUL (Unity/Integration)
        #   Q2: -r, +t = INTELLECTUAL (Pattern/Wisdom)
        #   Q3: -r, -t = MATERIAL (Physicality/Syntax)
        #   Q4: +r, -t = MENTAL (Semantics/Meaning)
        # =========================================================================
        r = result['r']
        t = result['t']

        if r > 0 and t > 0:
            kosha = "BLISSFUL"
            kosha_desc = "Unity"
        elif r < 0 and t > 0:
            kosha = "INTELLECTUAL"
            kosha_desc = "Wisdom"
        elif r < 0 and t < 0:
            kosha = "MATERIAL"
            kosha_desc = "Physical"
        else:  # r > 0 and t < 0, or edge cases
            kosha = "MENTAL"
            kosha_desc = "Meaning"

        result['kosha'] = kosha
        result['kosha_desc'] = kosha_desc

        # =========================================================================
        # VRITTI STATE: Cognitive mode classification (Corrected per Symbolu Ontology)
        # With corrected Reality axis: +r = Unmanifest (uncertain), -r = Manifest (confident)
        # =========================================================================
        # r and t already defined above for Kosha zone

        if r < -0.3 and t > 0.2:
            # Low entropy (confident) + High gradient (learning) = Valid cognition
            vritti = "FACT"
            vritti_desc = "Verified Truth"
            vritti_icon = "✅"
        elif r < -0.5 and t < -0.2:
            # Very low entropy (over-confident) + Low gradient (stagnant) = Hallucination risk
            vritti = "ERROR"
            vritti_desc = "Hallucination Risk"
            vritti_icon = "⚠️"
        elif -0.3 < r < 0.3:
            # Transitional entropy = Conceptual exploration
            vritti = "IMAGINATION"
            vritti_desc = "Conceptualization"
            vritti_icon = "🔍"
        elif r > 0.3 and abs(t) < 0.2:
            # High entropy (uncertain) + Low gradient (not moving) = Plateau
            vritti = "VOID"
            vritti_desc = "Null State"
            vritti_icon = "💤"
        elif r < 0 and t < -0.3:
            # Low entropy (confident) + Negative gradient (decaying) = Memory recall
            vritti = "MEMORY"
            vritti_desc = "Recall/Weights"
            vritti_icon = "📚"
        else:
            vritti = "BALANCED"
            vritti_desc = "Balanced State"
            vritti_icon = "⚖️"

        result['vritti'] = vritti
        result['vritti_desc'] = vritti_desc
        result['vritti_icon'] = vritti_icon

        # =========================================================================
        # REALITY ZONE: Manifest vs Unmanifest (Corrected per Symbolu Ontology)
        # Gemini Correction: +r = Unmanifest (high entropy/potential)
        #                    -r = Manifest (low entropy/concrete)
        # =========================================================================
        if r > 0.3:
            reality_zone = "Unmanifest"  # High entropy = abstract/potential
        elif r < -0.3:
            reality_zone = "Manifest"    # Low entropy = concrete/actualized
        else:
            reality_zone = "Transitional"
        result['reality_zone'] = reality_zone

        # =========================================================================
        # TIME ZONE: Past, Present, Future
        # =========================================================================
        if t > 0.3:
            time_zone = "Future"
        elif t < -0.3:
            time_zone = "Past"
        else:
            time_zone = "Present"
        result['time_zone'] = time_zone

    return result


def format_kosha_diagnostic(
    diag: Dict[str, Any],
    include_phase: bool = True,
    steering_metrics: Optional[Dict[str, float]] = None,
) -> str:
    """Format Sheath diagnostic for logging output."""
    lines = []

    # Line 1: Sheath coordinates
    r = diag['r']
    t = diag['t']
    reality_zone = diag['reality_zone']
    time_zone = diag['time_zone']
    kosha = diag['kosha']

    lines.append(
        f"    🧭 [SHEATH] Coords: r={r:+.2f} ({reality_zone}) | "
        f"t={t:+.2f} ({time_zone}) --> Zone: {kosha}"
    )

    # Line 2: Phase angle (optional)
    if include_phase:
        phase = diag['phase_angle']
        kosha_desc = diag['kosha_desc']
        lines.append(
            f"    📐 [PHASE] Angle: {phase:.0f}° ({kosha_desc}) | "
            f"Entropy: {diag['entropy']:.2f} | GradNorm: {diag['grad_norm']:.2f}"
        )

    # Line 3: State (Vritti)
    vritti = diag['vritti']
    vritti_desc = diag['vritti_desc']
    vritti_icon = diag['vritti_icon']

    lines.append(
        f"    🧠 [STATE] Mode: {vritti} ({vritti_desc}) {vritti_icon}"
    )

    # Line 4: Steering info (if active)
    if steering_metrics is not None and 'kosha_steering_loss' in steering_metrics:
        target = steering_metrics.get('kosha_target_angle', 0)
        mean_phase = steering_metrics.get('kosha_mean_phase', 0)
        phase_err = steering_metrics.get('kosha_phase_error', 0)
        steer_loss = steering_metrics.get('kosha_steering_loss', 0)

        # Direction indicator
        if phase_err > 10:
            direction = "↻" if mean_phase < target else "↺"
        else:
            direction = "✓"

        lines.append(
            f"    🎯 [STEER] Target: {target:.0f}° | Current: {mean_phase:.0f}° | "
            f"Error: {phase_err:.1f}° {direction} | Loss: {steer_loss:.4f}"
        )

    return "\n".join(lines)


def compute_csr_diagnostics(
    hidden_states: Optional[List[torch.Tensor]] = None,
    csr_metrics: Optional[Dict[str, float]] = None,
    diagnostic_layer: int = 7,
    layer_grad_norm: Optional[float] = None,
    grad_norm: float = 0.0,
) -> Dict[str, Any]:
    """
    V9.7.0: Compute CSR diagnostic coordinates at Layer 7.

    CSR (Coherent Semantic Resonance) aligns hidden states with Sanskrit
    phoneme-ontological embeddings. Layer 7 is where concept consolidation
    happens - abstract concepts solidify into coherent representations.

    Diagnostic Axes:
    - Coherence Axis (c): -1 (fragmented) to +1 (coherent/aligned)
    - Flow Axis (f): -1 (static/stuck) to +1 (flowing/learning)

    CSR States (based on quadrant):
    - RESONANT (c>0, f>0): Strong alignment + active learning - optimal
    - SEEKING (c<0, f>0): Weak alignment but learning - exploring
    - ANCHORED (c>0, f<0): Strong alignment but static - stable/memorized
    - LOST (c<0, f<0): Weak alignment and stuck - needs intervention
    """
    result = {
        'diagnostic_layer': diagnostic_layer,
    }

    with torch.no_grad():
        # =====================================================================
        # COHERENCE AXIS (c): Layer 7 Activation Focus
        # High focus = coherent representations (+1)
        # Low focus = fragmented/diffuse representations (-1)
        # =====================================================================
        layer_entropy = None
        if hidden_states is not None and len(hidden_states) > diagnostic_layer:
            layer_hidden = hidden_states[diagnostic_layer]
            if layer_hidden is not None and layer_hidden.numel() > 0:
                # Compute activation entropy (same method as Kosha)
                layer_abs = layer_hidden.abs().float()
                layer_probs = layer_abs / (layer_abs.sum(dim=-1, keepdim=True) + 1e-10)
                log_probs = torch.log(layer_probs + 1e-10)
                position_entropy = -(layer_probs * log_probs).sum(dim=-1)
                layer_entropy = position_entropy.mean().item()

                D = layer_hidden.shape[-1]
                max_entropy = math.log(D)
                # Map: low entropy → +1 (coherent), high entropy → -1 (fragmented)
                c = 1.0 - (2.0 * layer_entropy / max_entropy)
                c = max(-1.0, min(1.0, c))
                result['c'] = c
                result['entropy'] = layer_entropy
                result['entropy_source'] = f'layer_{diagnostic_layer}'

        if 'c' not in result:
            result['c'] = 0.0
            result['entropy'] = 0.0
            result['entropy_source'] = 'default'

        # =====================================================================
        # FLOW AXIS (f): Layer 7 Gradient Activity
        # High gradient = active learning/flow (+1)
        # Low gradient = static/stuck (-1)
        # =====================================================================
        effective_grad = layer_grad_norm if layer_grad_norm is not None else grad_norm

        if effective_grad > 0:
            log_grad = math.log10(effective_grad + 1e-8)
            f = log_grad / 3.0
            f = max(-1.0, min(1.0, f))
        else:
            f = 0.0
        result['f'] = f
        result['grad_norm'] = effective_grad
        result['grad_source'] = f'layer_{diagnostic_layer}' if layer_grad_norm is not None else 'total'

        # =====================================================================
        # CSR STATE CLASSIFICATION
        # =====================================================================
        c = result['c']
        f = result['f']

        if c >= 0 and f >= 0:
            state = 'RESONANT'
            state_desc = 'Aligned & Learning'
            state_icon = '🎵'
        elif c < 0 and f >= 0:
            state = 'SEEKING'
            state_desc = 'Exploring Alignment'
            state_icon = '🔍'
        elif c >= 0 and f < 0:
            state = 'ANCHORED'
            state_desc = 'Stable/Memorized'
            state_icon = '⚓'
        else:
            state = 'LOST'
            state_desc = 'Needs Intervention'
            state_icon = '❓'

        result['state'] = state
        result['state_desc'] = state_desc
        result['state_icon'] = state_icon

        # Coherence zone description
        if c > 0.3:
            result['coherence_zone'] = 'FOCUSED'
        elif c < -0.3:
            result['coherence_zone'] = 'DIFFUSE'
        else:
            result['coherence_zone'] = 'BALANCED'

        # Flow zone description
        if f > 0.3:
            result['flow_zone'] = 'FLOWING'
        elif f < -0.3:
            result['flow_zone'] = 'STATIC'
        else:
            result['flow_zone'] = 'MODERATE'

        # =====================================================================
        # CSR ALIGNMENT METRICS (from training loop)
        # =====================================================================
        if csr_metrics is not None:
            result['csr_loss'] = csr_metrics.get('csr_loss', 0.0)
            result['csr_confidence'] = csr_metrics.get('csr_confidence', 0.0)
            result['csr_similarity'] = csr_metrics.get('csr_similarity', 0.0)
            result['entropy_sink'] = csr_metrics.get('entropy_sink_entropy', 0.0)
            result['synthesis_gate'] = csr_metrics.get('synthesis_gate_value', 0.0)

    return result


def format_csr_diagnostic(diag: Dict[str, Any]) -> str:
    """Format CSR diagnostic for logging output (single line, condensed)."""
    c = diag.get('c', 0.0)
    f = diag.get('f', 0.0)
    coherence_zone = diag.get('coherence_zone', 'UNK')[:3].upper()
    flow_zone = diag.get('flow_zone', 'UNK')[:3].upper()
    state = diag.get('state', 'UNK')
    entropy = diag.get('entropy', 0.0)
    sim = diag.get('csr_similarity', 0.0)
    conf = diag.get('csr_confidence', 0.0)

    return (
        f"    🎼 [CSR] c={c:+.2f}({coherence_zone})|f={f:+.2f}({flow_zone})→{state} | "
        f"H={entropy:.2f} Sim={sim:.3f} Conf={conf:.3f}"
    )


def compute_onto_bridge_diagnostics(
    hidden_states: Optional[List[torch.Tensor]] = None,
    onto_metrics: Optional[Dict[str, float]] = None,
    onto_bridge: Optional[nn.Module] = None,
    diagnostic_layer: int = 4,
    layer_grad_norm: Optional[float] = None,
    grad_norm: float = 0.0,
) -> Dict[str, Any]:
    """
    V9.7.0: Compute Ontological Bridge diagnostics at Layer 4.

    The Ontological Bridge projects hidden states to 12D ontological space,
    one dimension per Aspect (O1-O12). Layer 4 is where foundational
    structure forms - the ontological "DNA" that propagates to all later layers.

    Diagnostic Axes:
    - Structure Axis (s): -1 (collapsed/uniform) to +1 (diverse/structured)
    - Grounding Axis (g): -1 (static/stuck) to +1 (adapting/learning)

    Onto States (based on quadrant):
    - GROUNDED (s>0, g>0): Diverse structure + active learning - optimal
    - FORMING (s<0, g>0): Uniform but learning - structure emerging
    - STABLE (s>0, g<0): Diverse but static - established ontology
    - DORMANT (s<0, g<0): Collapsed and stuck - needs activation
    """
    result = {
        'diagnostic_layer': diagnostic_layer,
    }

    with torch.no_grad():
        # =====================================================================
        # STRUCTURE AXIS (s): Layer 4 Representation Diversity
        # High diversity = rich ontological structure (+1)
        # Low diversity = collapsed/uniform (-1)
        # =====================================================================
        if hidden_states is not None and len(hidden_states) > diagnostic_layer:
            layer_hidden = hidden_states[diagnostic_layer]
            if layer_hidden is not None and layer_hidden.numel() > 0:
                # Compute activation entropy for structure measurement
                layer_abs = layer_hidden.abs().float()
                layer_probs = layer_abs / (layer_abs.sum(dim=-1, keepdim=True) + 1e-10)
                log_probs = torch.log(layer_probs + 1e-10)
                position_entropy = -(layer_probs * log_probs).sum(dim=-1)
                layer_entropy = position_entropy.mean().item()

                D = layer_hidden.shape[-1]
                max_entropy = math.log(D)
                # For structure, higher entropy = more diverse structure (+1)
                # This is OPPOSITE of coherence - we want distributed activations
                s = (2.0 * layer_entropy / max_entropy) - 1.0
                s = max(-1.0, min(1.0, s))
                result['s'] = s
                result['entropy'] = layer_entropy
                result['entropy_source'] = f'layer_{diagnostic_layer}'

        if 's' not in result:
            result['s'] = 0.0
            result['entropy'] = 0.0
            result['entropy_source'] = 'default'

        # =====================================================================
        # GROUNDING AXIS (g): Layer 4 Gradient Activity
        # High gradient = actively grounding/adapting (+1)
        # Low gradient = static/fixed (-1)
        # =====================================================================
        effective_grad = layer_grad_norm if layer_grad_norm is not None else grad_norm

        if effective_grad > 0:
            log_grad = math.log10(effective_grad + 1e-8)
            g = log_grad / 3.0
            g = max(-1.0, min(1.0, g))
        else:
            g = 0.0
        result['g'] = g
        result['grad_norm'] = effective_grad
        result['grad_source'] = f'layer_{diagnostic_layer}' if layer_grad_norm is not None else 'total'

        # =====================================================================
        # ONTO STATE CLASSIFICATION
        # =====================================================================
        s = result['s']
        g = result['g']

        if s >= 0 and g >= 0:
            state = 'GROUNDED'
            state_desc = 'Diverse & Adapting'
            state_icon = '🌳'
        elif s < 0 and g >= 0:
            state = 'FORMING'
            state_desc = 'Structure Emerging'
            state_icon = '🌱'
        elif s >= 0 and g < 0:
            state = 'STABLE'
            state_desc = 'Established Ontology'
            state_icon = '🏛️'
        else:
            state = 'DORMANT'
            state_desc = 'Needs Activation'
            state_icon = '💤'

        result['state'] = state
        result['state_desc'] = state_desc
        result['state_icon'] = state_icon

        # Structure zone description
        if s > 0.3:
            result['structure_zone'] = 'DIVERSE'
        elif s < -0.3:
            result['structure_zone'] = 'UNIFORM'
        else:
            result['structure_zone'] = 'MODERATE'

        # Grounding zone description
        if g > 0.3:
            result['grounding_zone'] = 'ADAPTING'
        elif g < -0.3:
            result['grounding_zone'] = 'STATIC'
        else:
            result['grounding_zone'] = 'STABLE'

        # =====================================================================
        # 12D ASPECT METRICS (from OntologicalBridge or onto_metrics)
        # =====================================================================
        if onto_metrics is not None:
            result['diversity'] = onto_metrics.get('onto_diversity', 0.0)
            result['pramana_corr'] = onto_metrics.get('onto_pramana_corr', 0.0)
            result['o9_witness'] = onto_metrics.get('onto_o9_witness', 0.0)
            result['mean_activation'] = onto_metrics.get('onto_mean_activation', 0.0)

        # Compute 12D projection if bridge available
        if onto_bridge is not None and hidden_states is not None and len(hidden_states) > diagnostic_layer:
            layer_hidden = hidden_states[diagnostic_layer]
            if layer_hidden is not None:
                onto_repr, bridge_metrics = onto_bridge(layer_hidden)
                # Get aspect activations
                aspect_means = onto_repr.mean(dim=[0, 1])  # [12]
                result['aspect_activations'] = aspect_means.tolist()

                # Find dominant aspect
                dominant_idx = aspect_means.abs().argmax().item()
                result['dominant_aspect'] = f'O{dominant_idx + 1}'
                result['dominant_value'] = aspect_means[dominant_idx].item()

    return result


def format_onto_bridge_diagnostic(diag: Dict[str, Any]) -> str:
    """Format Ontological Bridge diagnostic for logging output (single line, condensed)."""
    # Short names for 12 aspects
    ASPECT_SHORT = ['POT', 'IDN', 'EXE', 'STR', 'COG', 'AGY', 'RSN', 'PRP', 'WIT', 'UNI', 'INT', 'ABS']

    s = diag.get('s', 0.0)
    g = diag.get('g', 0.0)
    structure_zone = diag.get('structure_zone', 'UNK')[:3].upper()
    grounding_zone = diag.get('grounding_zone', 'UNK')[:3].upper()
    state = diag.get('state', 'UNK')
    div = diag.get('diversity', 0.0)
    pram = diag.get('pramana_corr', 0.0)

    # Find dominant aspect
    dominant = "ABS"
    if 'aspect_activations' in diag:
        activations = diag['aspect_activations']
        max_idx = 0
        max_val = abs(activations[0]) if activations else 0
        for i, v in enumerate(activations):
            if abs(v) > max_val:
                max_val = abs(v)
                max_idx = i
        dominant = ASPECT_SHORT[max_idx]

    return (
        f"    🌉 [ONTO] s={s:+.2f}({structure_zone})|g={g:+.2f}({grounding_zone})→{state} | "
        f"Div={div:.2f} Pram={pram:+.2f} Dom={dominant}"
    )


def compute_sovereign_state_diagnostics(
    state: Optional[torch.Tensor] = None,
    delta_S: Optional[torch.Tensor] = None,
    grad_norm: float = 0.0,
) -> Dict[str, Any]:
    """
    Compute diagnostics for the 32D Sovereign State.

    V9.8.0: Replaces the arbitrary 124D diagnostics with principled readouts.

    Args:
        state: [B, 32] Sovereign State tensor from OntologicalHybridTransformer
        delta_S: [B, 32] State delta tensor
        grad_norm: Current gradient norm

    Returns:
        Dict with:
        - dominant_bhava: Name of most active Bhava (0-11)
        - active_kosha: Name of most active Kosha (12-16)
        - vritti_state: Name of current Vritti (17-21)
        - guna_balance: Lucidity/Activity/Stability balance
        - delta_magnitude: How much state changed
        - All raw activations for detailed logging
    """
    result = {
        'dominant_bhava': 'ABS',
        'dominant_bhava_idx': 11,
        'bhava_activation': 0.0,
        'active_kosha': 'MATERIAL',
        'active_kosha_idx': 0,
        'kosha_activation': 0.0,
        'vritti_state': 'FACT',
        'vritti_state_idx': 0,
        'vritti_activation': 0.0,
        'guna_sattva': 0.33,
        'guna_rajas': 0.33,
        'guna_tamas': 0.33,
        'velocity': 0.0,
        'delta_magnitude': 0.0,
        'grad_norm': grad_norm,
        'bhava_activations': [0.0] * 12,
        'kosha_activations': [0.0] * 5,
        'vritti_activations': [0.0] * 5,
        'guna_activations': [0.0] * 6,
    }

    if state is None:
        return result

    try:
        # Use get_sovereign_state_summary from phase_transformer
        summary = get_sovereign_state_summary(state)
        result.update(summary)

        # Extract raw activations for detailed logging
        if state.dim() == 1:
            state = state.unsqueeze(0)

        # Bhava activations [0:12]
        bhava_vals = state[0, BHAVA_SLICE].detach().cpu().tolist()
        result['bhava_activations'] = bhava_vals

        # V9.6.8: Compute Bhava top-3 for "snap point" visibility
        # State is now properly normalized by SovereignStateProjector (softmax applied)
        bhava_tensor = state[0, BHAVA_SLICE].detach().cpu()
        sorted_bhava, sorted_idx = bhava_tensor.sort(descending=True)
        result['bhava_top1_val'] = sorted_bhava[0].item()
        result['bhava_top1_name'] = BHAVA_NAMES[sorted_idx[0].item()]
        result['bhava_top2_val'] = sorted_bhava[1].item()
        result['bhava_top2_name'] = BHAVA_NAMES[sorted_idx[1].item()]
        result['bhava_top3_val'] = sorted_bhava[2].item()
        result['bhava_top3_name'] = BHAVA_NAMES[sorted_idx[2].item()]
        result['bhava_margin'] = (sorted_bhava[0] - sorted_bhava[1]).item()

        # Kosha activations [12:17]
        kosha_vals = state[0, KOSHA_SLICE].detach().cpu().tolist()
        result['kosha_activations'] = kosha_vals

        # V9.6.8: Compute Kosha (Sheath) top-3
        # State is now properly normalized by SovereignStateProjector (softmax applied)
        kosha_tensor = state[0, KOSHA_SLICE].detach().cpu()
        sorted_kosha, sorted_kosha_idx = kosha_tensor.sort(descending=True)
        result['kosha_top1_val'] = sorted_kosha[0].item()
        result['kosha_top1_name'] = KOSHA_NAMES[sorted_kosha_idx[0].item()]
        result['kosha_top2_val'] = sorted_kosha[1].item()
        result['kosha_top2_name'] = KOSHA_NAMES[sorted_kosha_idx[1].item()]
        result['kosha_top3_val'] = sorted_kosha[2].item()
        result['kosha_top3_name'] = KOSHA_NAMES[sorted_kosha_idx[2].item()]
        result['kosha_margin'] = (sorted_kosha[0] - sorted_kosha[1]).item()

        # Vritti activations [17:22]
        vritti_vals = state[0, VRITTI_SLICE].detach().cpu().tolist()
        result['vritti_activations'] = vritti_vals

        # Guna activations [22:28]
        guna_vals = state[0, GUNA_SLICE].detach().cpu().tolist()
        result['guna_activations'] = guna_vals

        # Compute delta magnitude if provided
        if delta_S is not None:
            result['delta_magnitude'] = delta_S.norm().item()

    except Exception as e:
        # Silent fallback on error
        pass

    return result


def format_sovereign_state_diagnostic(diag: Dict[str, Any]) -> str:
    """
    Format 32D Sovereign State diagnostic for logging output.

    V9.8.0: Condensed single-line output (was 6 lines).
    V9.6.8: Added top-3 Bhava/Kosha to visualize "snap point" proximity.
    Shows Bhava/Kosha/Vritti/Guna summary in compact form.
    """
    # V9.6.8: Top-3 Bhava with probabilities
    b1_name = diag.get('bhava_top1_name', diag.get('dominant_bhava', 'ABS'))
    b1_val = diag.get('bhava_top1_val', 0.0)
    b2_name = diag.get('bhava_top2_name', '???')
    b2_val = diag.get('bhava_top2_val', 0.0)
    b3_name = diag.get('bhava_top3_name', '???')
    b3_val = diag.get('bhava_top3_val', 0.0)
    bhava_margin = diag.get('bhava_margin', 0.0)

    # V9.6.8: Top-3 Kosha (Sheath) with probabilities
    k1_name = diag.get('kosha_top1_name', diag.get('active_kosha', 'ANNA'))
    k1_val = diag.get('kosha_top1_val', 0.0)
    k2_name = diag.get('kosha_top2_name', '???')
    k2_val = diag.get('kosha_top2_val', 0.0)
    k3_name = diag.get('kosha_top3_name', '???')
    k3_val = diag.get('kosha_top3_val', 0.0)
    kosha_margin = diag.get('kosha_margin', 0.0)

    vritti = diag.get('vritti_state', 'FACT')
    delta = diag.get('delta_magnitude', 0.0)

    # Guna balance as compact percentages (L=Lucidity, A=Activity, S=Stability)
    lucidity = diag.get('guna_sattva', 0.33)
    activity = diag.get('guna_rajas', 0.33)
    stability = diag.get('guna_tamas', 0.33)

    # Format margin indicator: 🔴 (<5%), 🟡 (5-15%), 🟢 (>15%)
    def margin_icon(m):
        if m < 0.05:
            return "🔴"  # Very close to snap
        elif m < 0.15:
            return "🟡"  # Moderate margin
        return "🟢"  # Stable

    # Shorten Kosha names for display (using English meanings)
    # ANNA=Physical, PRANA=Vital, MANO=Mental, VIJNANA=Intellect, ANANDA=Bliss
    kosha_short = {'ANNA': 'PHY', 'PRANA': 'VIT', 'MANO': 'MEN', 'VIJNANA': 'INT', 'ANANDA': 'BLI'}

    # Format: Bhava: IDN(45%)>RSN(30%)>COG(10%) 🟢
    bhava_str = f"{b1_name}({b1_val:.0%})>{b2_name}({b2_val:.0%})>{b3_name}({b3_val:.0%})"
    kosha_str = f"{kosha_short.get(k1_name, k1_name[:3])}({k1_val:.0%})>{kosha_short.get(k2_name, k2_name[:3])}({k2_val:.0%})"

    # V11.0.0: Two-line output showing separated planes
    # Phase plane (12D Bhava) is marked with → to show it feeds phase rotation
    # Control plane (Kosha/Vritti/Guna) is marked with | to show it's separate
    return (
        f"    🔱 [Phase:12D] Bhava→θ:{bhava_str} {margin_icon(bhava_margin)} | "
        f"[Ctrl] Sheath:{kosha_str} {margin_icon(kosha_margin)} | Vritti:{vritti}\n"
        f"           [Ctrl] Qualia[L{lucidity:.0%}/A{activity:.0%}/S{stability:.0%}] Δ={delta:.2f}"
    )
