#!/usr/bin/env python3
"""
Generation Tracer — Appendix F Stage 0 Instrumentation
========================================================

Per-token instrumentation for baseline capture during generation.
No generation behavior is modified — observation only.

Implements:
- GenerationTracer: Core per-token metrics (logit entropy, hidden norms, CG primitives)
- BindingCacheTracerMixin: Intent phase, salience, proposal confidence (F.2.7)
- CTMPlusTracerMixin: Layer access patterns, tier placement simulation (F.2.8)
- MistralCGGenerationTracer: Composed tracer for mistral_cg model type (F.2.9)

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.2.3–F.2.9

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 0 — Baseline System Capture
"""

import json
import math
from typing import Dict, List, Optional, Any

import torch
import torch.nn.functional as F


# =============================================================================
# CORE TRACER (F.2.3)
# =============================================================================

class GenerationTracer:
    """Per-token instrumentation for baseline capture. No generation modification."""

    def __init__(self, model, csr_scorer=None, vritti_scorer=None,
                 kosha_router=None, bliss_gate=None):
        self.model = model
        self.csr_scorer = csr_scorer
        self.vritti_scorer = vritti_scorer
        self.kosha_router = kosha_router
        self.bliss_gate = bliss_gate
        self.trace: List[Dict[str, Any]] = []

    def record_token(self, token_id, logits, hidden_state, onto_state=None):
        """Record per-token auxiliary measurements without modifying generation."""
        entry = {
            "token_id": int(token_id) if not isinstance(token_id, int) else token_id,
            "logit_entropy": -(F.softmax(logits, -1) * F.log_softmax(logits, -1)).sum().item(),
            "token_prob": F.softmax(logits, -1).view(-1)[token_id].item()
                if logits.numel() > 0 else 0.0,
            "hidden_norm": hidden_state.norm().item(),
        }
        if onto_state is not None:
            entry["bhava_coherence"] = onto_state.get("coherence", None)
        if self.csr_scorer is not None:
            entry["csr_score"] = self._compute_csr(token_id, hidden_state, onto_state)
        if self.vritti_scorer is not None:
            entry["vritti_vector"] = self._compute_vritti(hidden_state, onto_state)
        if self.kosha_router is not None:
            entry["kosha_alpha"] = self._compute_kosha(hidden_state, onto_state)
        if self.bliss_gate is not None:
            entry["bliss"] = self._compute_bliss(hidden_state, onto_state)
        self.trace.append(entry)

    def _compute_csr(self, token_id, hidden_state, onto_state):
        """Compute CSR bilinear score S_csr(w)."""
        try:
            return self.csr_scorer.score_token(token_id, hidden_state).item()
        except Exception:
            return 0.0

    def _compute_vritti(self, hidden_state, onto_state):
        """Compute Vritti distribution [FACT, ERROR, IMAGINATION, VOID, MEMORY]."""
        try:
            v = self.vritti_scorer.score(hidden_state)
            return v.detach().cpu().tolist() if hasattr(v, 'tolist') else [0.0] * 5
        except Exception:
            return [0.0] * 5

    def _compute_kosha(self, hidden_state, onto_state):
        """Compute Kosha routing weights."""
        try:
            alpha = self.kosha_router.route(hidden_state, onto_state)
            return alpha.detach().cpu().tolist() if hasattr(alpha, 'tolist') else [0.0] * 6
        except Exception:
            return [0.0] * 6

    def _compute_bliss(self, hidden_state, onto_state):
        """Compute Bliss coherence gate B(w)."""
        try:
            return self.bliss_gate.gate(hidden_state).item()
        except Exception:
            return 1.0

    def export(self, path="generation_trace.json"):
        """Export trace to JSON for offline analysis."""
        with open(path, 'w') as f:
            json.dump(self.trace, f, indent=2)

    def clear(self):
        """Clear trace buffer."""
        self.trace.clear()

    def summary(self) -> Dict[str, float]:
        """Compute baseline statistics from trace (F.2.5)."""
        if not self.trace:
            return {}
        entropies = [e["logit_entropy"] for e in self.trace]
        probs = [e["token_prob"] for e in self.trace]
        norms = [e["hidden_norm"] for e in self.trace]
        return {
            "mean_logit_entropy": sum(entropies) / len(entropies),
            "mean_token_prob": sum(probs) / len(probs),
            "mean_hidden_norm": sum(norms) / len(norms),
            "num_tokens": len(self.trace),
        }


# =============================================================================
# BINDING CACHE TRACER MIXIN (F.2.7)
# =============================================================================

class BindingCacheTracerMixin:
    """Extends GenerationTracer with Binding Cache observation metrics."""

    def init_binding_cache_tracer(self, num_heads, head_dim, top_k=64):
        """Initialize Binding Cache observation state."""
        self._bc_num_heads = num_heads
        self._bc_head_dim = head_dim
        self._bc_top_k = top_k
        self._prev_intent = None

    def record_binding_cache(self, token_id, hidden_state, intent_phase,
                              input_ids):
        """Record per-token Binding Cache metrics without modifying generation."""
        entry = {}

        # Intent phase tracking
        if intent_phase is not None:
            phase_flat = intent_phase.detach().cpu()
            entry["intent_phase"] = phase_flat.tolist() if phase_flat.dim() <= 1 else phase_flat[0].tolist()
            if self._prev_intent is not None:
                entry["intent_drift"] = (
                    (intent_phase.detach().float() - self._prev_intent.float())
                    .norm().item()
                )
            else:
                entry["intent_drift"] = 0.0
            self._prev_intent = intent_phase.detach().clone()

        # Salience distribution analysis (simplified — from hidden norm per position)
        if hidden_state is not None and hidden_state.dim() >= 2:
            # Use position-wise hidden norms as proxy for salience
            if hidden_state.dim() == 3:
                pos_norms = hidden_state[0].norm(dim=-1)  # [T]
            else:
                pos_norms = hidden_state.norm(dim=-1)  # [T]

            sal_probs = F.softmax(pos_norms, dim=-1)
            entry["salience_entropy"] = (
                -(sal_probs * (sal_probs + 1e-8).log()).sum().item()
            )
            entry["salience_top_k_ratio"] = (
                (pos_norms > pos_norms.mean()).float().mean().item()
            )

            # Simulated cache hit rate under Top-K pruning
            T = pos_norms.shape[0]
            if T > self._bc_top_k:
                entry["binding_cache_hit_rate"] = self._bc_top_k / T
            else:
                entry["binding_cache_hit_rate"] = 1.0
        else:
            entry["salience_entropy"] = 0.0
            entry["salience_top_k_ratio"] = 0.0
            entry["binding_cache_hit_rate"] = 1.0

        return entry


# =============================================================================
# CTM+ TRACER MIXIN (F.2.8)
# =============================================================================

class CTMPlusTracerMixin:
    """Extends GenerationTracer with CTM+ offload observation metrics."""

    def init_ctm_plus_tracer(self, num_layers=32, gpu_budget=24):
        """Initialize CTM+ observation state."""
        self._ctm_num_layers = num_layers
        self._ctm_gpu_budget = gpu_budget
        self._access_counts = [0] * num_layers
        self._adaptive_p = 0.5
        self._total_steps = 0
        self._shadow_b1_hits = 0
        self._shadow_b2_hits = 0

    def record_layer_access(self, layer_idx):
        """Record that a layer was accessed during forward pass."""
        if 0 <= layer_idx < self._ctm_num_layers:
            self._access_counts[layer_idx] += 1

    def record_ctm_metrics(self):
        """Compute CTM+ metrics for the current generation step."""
        self._total_steps += 1
        entry = {}

        entry["ctm_layer_access"] = list(self._access_counts)

        # Phase coherence: entropy of access frequency distribution
        access_tensor = torch.tensor(self._access_counts, dtype=torch.float32)
        total_access = access_tensor.sum()
        if total_access > 0:
            access_probs = access_tensor / total_access
            entry["ctm_phase_coherence"] = (
                -(access_probs * (access_probs + 1e-8).log()).sum().item()
            )
        else:
            entry["ctm_phase_coherence"] = 0.0

        # Workload classification
        if total_access > 0:
            access_var = access_tensor.var().item()
            access_mean = access_tensor.mean().item()
            if access_var < 0.1:
                entry["ctm_workload_mode"] = "temporal"
            elif access_tensor.max().item() > 3 * max(access_mean, 1e-8):
                entry["ctm_workload_mode"] = "scan"
            else:
                entry["ctm_workload_mode"] = "mixed"
        else:
            entry["ctm_workload_mode"] = "idle"

        # Simulated tier placement
        sorted_layers = sorted(
            range(self._ctm_num_layers),
            key=lambda i: self._access_counts[i],
            reverse=True,
        )
        gpu_layers = sorted_layers[:self._ctm_gpu_budget]
        cpu_layers = sorted_layers[self._ctm_gpu_budget:]
        entry["ctm_adaptive_p"] = self._adaptive_p
        entry["ctm_simulated_gpu_layers"] = len(gpu_layers)
        entry["ctm_simulated_cpu_layers"] = len(cpu_layers)
        entry["ctm_prefetch_hits"] = 0  # Populated after multi-step tracking

        return entry

    def reset_access_counts(self):
        """Reset per-step access counts (call between generation steps)."""
        self._access_counts = [0] * self._ctm_num_layers


# =============================================================================
# COMPOSED TRACER FOR MISTRAL CG (F.2.9)
# =============================================================================

class MistralCGGenerationTracer(GenerationTracer):
    """
    Full Stage 0 tracer for Mistral CG with Binding Cache + CTM+ observation.

    Composes:
    - GenerationTracer: logit entropy, token probs, CG primitive scores
    - BindingCacheTracerMixin: intent phase, salience, proposal confidence
    - CTMPlusTracerMixin: layer access patterns, tier placement simulation
    """

    def __init__(self, model, csr_scorer=None, vritti_scorer=None,
                 kosha_router=None, bliss_gate=None,
                 binding_cache_top_k=64, ctm_num_layers=32,
                 ctm_gpu_budget=24):
        super().__init__(model, csr_scorer, vritti_scorer,
                         kosha_router, bliss_gate)

        # Binding Cache observation
        num_heads = getattr(model, 'num_heads', 12)
        hidden_dim = getattr(model, 'mistral_hidden_dim',
                             getattr(model, 'embed_dim', 768))
        head_dim = hidden_dim // num_heads

        self._bc_mixin = BindingCacheTracerMixin()
        self._bc_mixin.init_binding_cache_tracer(
            num_heads=num_heads,
            head_dim=head_dim,
            top_k=binding_cache_top_k,
        )

        # CTM+ observation
        self._ctm_mixin = CTMPlusTracerMixin()
        self._ctm_mixin.init_ctm_plus_tracer(
            num_layers=ctm_num_layers,
            gpu_budget=ctm_gpu_budget,
        )

    def record_token(self, token_id, logits, hidden_state, onto_state=None,
                      intent_phase=None, input_ids=None):
        """Record all metrics: base CG + Binding Cache + CTM+."""
        # Base CG metrics
        super().record_token(token_id, logits, hidden_state, onto_state)

        # Binding Cache metrics
        if intent_phase is not None:
            bc_entry = self._bc_mixin.record_binding_cache(
                token_id, hidden_state, intent_phase, input_ids,
            )
            self.trace[-1].update(bc_entry)

        # CTM+ metrics (layer access recorded separately via record_layer_access)
        ctm_entry = self._ctm_mixin.record_ctm_metrics()
        self.trace[-1].update(ctm_entry)

        # Reset per-step access counts
        self._ctm_mixin.reset_access_counts()

    def record_layer_access(self, layer_idx):
        """Record a layer access for CTM+ tracking."""
        self._ctm_mixin.record_layer_access(layer_idx)

    def summary(self) -> Dict[str, float]:
        """Extended summary including Binding Cache and CTM+ metrics."""
        base = super().summary()
        if not self.trace:
            return base

        # Binding Cache summary
        intent_drifts = [e.get("intent_drift", 0.0) for e in self.trace if "intent_drift" in e]
        salience_entropies = [e.get("salience_entropy", 0.0) for e in self.trace if "salience_entropy" in e]
        cache_hit_rates = [e.get("binding_cache_hit_rate", 1.0) for e in self.trace if "binding_cache_hit_rate" in e]

        if intent_drifts:
            base["mean_intent_drift"] = sum(intent_drifts) / len(intent_drifts)
        if salience_entropies:
            base["mean_salience_entropy"] = sum(salience_entropies) / len(salience_entropies)
        if cache_hit_rates:
            base["mean_cache_hit_rate"] = sum(cache_hit_rates) / len(cache_hit_rates)

        # CTM+ summary
        coherences = [e.get("ctm_phase_coherence", 0.0) for e in self.trace if "ctm_phase_coherence" in e]
        workload_modes = [e.get("ctm_workload_mode", "idle") for e in self.trace if "ctm_workload_mode" in e]

        if coherences:
            base["mean_ctm_phase_coherence"] = sum(coherences) / len(coherences)
        if workload_modes:
            from collections import Counter
            mode_counts = Counter(workload_modes)
            base["ctm_dominant_workload"] = mode_counts.most_common(1)[0][0]
            transitions = sum(1 for i in range(1, len(workload_modes))
                              if workload_modes[i] != workload_modes[i-1])
            base["ctm_mode_transitions"] = transitions
            base["ctm_mode_stability"] = 1.0 - (transitions / max(len(workload_modes) - 1, 1))

        return base
