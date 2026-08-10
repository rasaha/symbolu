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
- BaselineStatisticsAnalyzer: Full F.2.5 + F.2.6a baseline statistics (F.2.5)

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.2.3–F.2.9

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 0 — Baseline System Capture
"""

import json
import math
from collections import Counter
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

    def summary(self) -> Dict[str, Any]:
        """Compute baseline statistics from trace (F.2.5)."""
        if not self.trace:
            return {}
        return BaselineStatisticsAnalyzer.compute(self.trace)


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

    def summary(self) -> Dict[str, Any]:
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
            mode_counts = Counter(workload_modes)
            base["ctm_dominant_workload"] = mode_counts.most_common(1)[0][0]
            transitions = sum(1 for i in range(1, len(workload_modes))
                              if workload_modes[i] != workload_modes[i-1])
            base["ctm_mode_transitions"] = transitions
            base["ctm_mode_stability"] = 1.0 - (transitions / max(len(workload_modes) - 1, 1))

        return base


# =============================================================================
# BASELINE STATISTICS ANALYZER (F.2.5 + F.2.6a)
# =============================================================================

class BaselineStatisticsAnalyzer:
    """
    Computes the full set of baseline statistics from a generation trace.

    Implements all metrics from Appendix F §F.2.5:
    - Mean logit entropy (expected: 5.0–8.0)
    - Coherence distribution / histogram of B(w) values
    - Token repetition rate (expected: < 15%)
    - Long-form drift rate via cosine(h_t, h_{t-50}) (expected: > 0.3)
    - CSR score distribution μ(S_csr), σ(S_csr)
    - Vritti entropy per token (expected: > 0.5 bits)
    - Kosha alpha entropy per token (expected: > 1.0 bits)

    And from §F.2.6a (Binding Cache + CTM+):
    - Mean intent drift (expected: 0.01–0.5)
    - Salience concentration / Gini coefficient
    - Simulated cache efficiency
    - CTM+ layer access entropy (expected: > 3.0 bits)
    - CTM+ optimal GPU budget
    - Workload mode stability (expected: < 0.05 transition rate)
    """

    @staticmethod
    def compute(trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute all baseline statistics from a trace."""
        if not trace:
            return {}

        stats: Dict[str, Any] = {}
        n = len(trace)

        # --- Core metrics (F.2.5) ---

        # Mean logit entropy: μ(H) across all tokens — expected 5.0–8.0
        entropies = [e["logit_entropy"] for e in trace]
        stats["mean_logit_entropy"] = sum(entropies) / n
        stats["std_logit_entropy"] = _std(entropies)

        # Mean token probability
        probs = [e["token_prob"] for e in trace]
        stats["mean_token_prob"] = sum(probs) / n

        # Mean hidden norm
        norms = [e["hidden_norm"] for e in trace]
        stats["mean_hidden_norm"] = sum(norms) / n

        stats["num_tokens"] = n

        # Token repetition rate: # repeated n-grams / total n-grams — expected < 15%
        token_ids = [e["token_id"] for e in trace]
        for ngram_n in (2, 3, 4):
            rate = _ngram_repetition_rate(token_ids, ngram_n)
            stats[f"token_repetition_rate_{ngram_n}gram"] = rate

        # Long-form drift rate: cosine(h_t, h_{t-50}) for t > 100 — expected > 0.3
        # We store hidden norms but not full vectors in JSON traces. When full
        # hidden states are available (live tracer), this is computed from them.
        # For JSON-loaded traces, we use hidden norm ratio as a proxy.
        if n > 100:
            drift_proxy = []
            for i in range(100, n):
                j = max(0, i - 50)
                h_i, h_j = norms[i], norms[j]
                if h_j > 0:
                    drift_proxy.append(min(h_i / h_j, h_j / h_i))
                else:
                    drift_proxy.append(0.0)
            stats["long_form_drift_proxy"] = sum(drift_proxy) / len(drift_proxy)
        else:
            stats["long_form_drift_proxy"] = None

        # Coherence distribution: histogram of B(w) / bliss values
        bliss_values = [e["bliss"] for e in trace if "bliss" in e]
        if bliss_values:
            stats["bliss_mean"] = sum(bliss_values) / len(bliss_values)
            stats["bliss_std"] = _std(bliss_values)
            stats["bliss_min"] = min(bliss_values)
            stats["bliss_max"] = max(bliss_values)
            stats["bliss_histogram"] = _histogram(bliss_values,
                                                   bins=[0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0])

        # Bhava coherence distribution
        bhava_values = [e["bhava_coherence"] for e in trace
                        if e.get("bhava_coherence") is not None]
        if bhava_values:
            stats["bhava_coherence_mean"] = sum(bhava_values) / len(bhava_values)
            stats["bhava_coherence_std"] = _std(bhava_values)

        # CSR score distribution: μ(S_csr), σ(S_csr) — should have meaningful variance
        csr_scores = [e["csr_score"] for e in trace if "csr_score" in e]
        if csr_scores:
            stats["csr_score_mean"] = sum(csr_scores) / len(csr_scores)
            stats["csr_score_std"] = _std(csr_scores)

        # Vritti entropy: H(vritti_vector) per token — expected > 0.5 bits
        vritti_entropies = []
        for e in trace:
            if "vritti_vector" in e:
                v = e["vritti_vector"]
                if isinstance(v, list) and len(v) > 0:
                    vritti_entropies.append(_entropy(v))
        if vritti_entropies:
            stats["vritti_entropy_mean"] = sum(vritti_entropies) / len(vritti_entropies)
            stats["vritti_entropy_std"] = _std(vritti_entropies)

        # Kosha alpha entropy: H(α_t) per token — expected > 1.0 bits
        kosha_entropies = []
        for e in trace:
            if "kosha_alpha" in e:
                alpha = e["kosha_alpha"]
                if isinstance(alpha, list) and len(alpha) > 0:
                    kosha_entropies.append(_entropy(alpha))
        if kosha_entropies:
            stats["kosha_alpha_entropy_mean"] = sum(kosha_entropies) / len(kosha_entropies)
            stats["kosha_alpha_entropy_std"] = _std(kosha_entropies)

        # --- Binding Cache metrics (F.2.6a) ---

        intent_drifts = [e["intent_drift"] for e in trace if "intent_drift" in e]
        if intent_drifts:
            stats["mean_intent_drift"] = sum(intent_drifts) / len(intent_drifts)
            stats["std_intent_drift"] = _std(intent_drifts)

        salience_entropies = [e["salience_entropy"] for e in trace if "salience_entropy" in e]
        if salience_entropies:
            stats["mean_salience_entropy"] = sum(salience_entropies) / len(salience_entropies)

        # Salience concentration: Gini coefficient — expected 0.2–0.6
        sal_top_k_ratios = [e["salience_top_k_ratio"] for e in trace if "salience_top_k_ratio" in e]
        if sal_top_k_ratios:
            stats["salience_gini_proxy"] = 1.0 - 2.0 * (sum(sal_top_k_ratios) / len(sal_top_k_ratios))

        cache_hit_rates = [e["binding_cache_hit_rate"] for e in trace if "binding_cache_hit_rate" in e]
        if cache_hit_rates:
            stats["mean_cache_hit_rate"] = sum(cache_hit_rates) / len(cache_hit_rates)

        # --- CTM+ metrics (F.2.6a) ---

        coherences = [e["ctm_phase_coherence"] for e in trace if "ctm_phase_coherence" in e]
        if coherences:
            stats["mean_ctm_phase_coherence"] = sum(coherences) / len(coherences)

        # CTM+ optimal GPU budget: min layers for 95% access coverage
        all_accesses = [e["ctm_layer_access"] for e in trace if "ctm_layer_access" in e]
        if all_accesses:
            total_per_layer = [0] * len(all_accesses[0])
            for acc in all_accesses:
                for i, v in enumerate(acc):
                    total_per_layer[i] += v
            total = sum(total_per_layer)
            if total > 0:
                sorted_counts = sorted(total_per_layer, reverse=True)
                cumsum = 0
                for k, c in enumerate(sorted_counts, 1):
                    cumsum += c
                    if cumsum >= 0.95 * total:
                        stats["ctm_optimal_gpu_budget_95pct"] = k
                        break

        workload_modes = [e["ctm_workload_mode"] for e in trace if "ctm_workload_mode" in e]
        if workload_modes:
            mode_counts = Counter(workload_modes)
            stats["ctm_dominant_workload"] = mode_counts.most_common(1)[0][0]
            transitions = sum(1 for i in range(1, len(workload_modes))
                              if workload_modes[i] != workload_modes[i - 1])
            stats["ctm_mode_transitions"] = transitions
            stats["ctm_mode_transition_rate"] = transitions / max(len(workload_modes) - 1, 1)
            stats["ctm_mode_stability"] = 1.0 - stats["ctm_mode_transition_rate"]

        return stats

    @staticmethod
    def from_file(path: str) -> Dict[str, Any]:
        """Load a trace JSON and compute baseline statistics."""
        with open(path, 'r') as f:
            trace = json.load(f)
        return BaselineStatisticsAnalyzer.compute(trace)

    @staticmethod
    def report(stats: Dict[str, Any]) -> str:
        """Format baseline statistics as a human-readable report."""
        lines = ["=" * 60, "Stage 0 Baseline Statistics Report", "=" * 60, ""]

        # Core metrics
        lines.append("--- Core Generation Metrics (F.2.5) ---")
        lines.append(f"  Tokens traced:       {stats.get('num_tokens', 0)}")
        lines.append(f"  Mean logit entropy:  {stats.get('mean_logit_entropy', 0):.4f}"
                      f"  (expected: 5.0–8.0)")
        lines.append(f"  Std logit entropy:   {stats.get('std_logit_entropy', 0):.4f}")
        lines.append(f"  Mean token prob:     {stats.get('mean_token_prob', 0):.6f}")
        lines.append(f"  Mean hidden norm:    {stats.get('mean_hidden_norm', 0):.4f}")
        lines.append("")

        # Repetition
        for n in (2, 3, 4):
            key = f"token_repetition_rate_{n}gram"
            val = stats.get(key)
            if val is not None:
                flag = " OK" if val < 0.15 else " HIGH"
                lines.append(f"  {n}-gram repetition:  {val:.4f}  (expected: < 0.15){flag}")

        # Drift
        drift = stats.get("long_form_drift_proxy")
        if drift is not None:
            flag = " OK" if drift > 0.3 else " LOW"
            lines.append(f"  Long-form drift:     {drift:.4f}  (expected: > 0.3){flag}")
        lines.append("")

        # CG primitives
        if "bliss_mean" in stats:
            lines.append("--- Bliss Coherence ---")
            lines.append(f"  Mean B(w):   {stats['bliss_mean']:.4f}  "
                          f"[{stats.get('bliss_min', 0):.3f}, {stats.get('bliss_max', 0):.3f}]")
            hist = stats.get("bliss_histogram", {})
            if hist:
                lines.append(f"  Histogram:   {hist}")
            lines.append("")

        if "csr_score_mean" in stats:
            lines.append("--- CSR Score Distribution ---")
            lines.append(f"  μ(S_csr): {stats['csr_score_mean']:.4f}  "
                          f"σ(S_csr): {stats.get('csr_score_std', 0):.4f}")
            lines.append("")

        if "vritti_entropy_mean" in stats:
            lines.append("--- Vritti Entropy ---")
            flag = " OK" if stats["vritti_entropy_mean"] > 0.5 else " LOW"
            lines.append(f"  Mean H(vritti): {stats['vritti_entropy_mean']:.4f}  "
                          f"(expected: > 0.5 bits){flag}")
            lines.append("")

        if "kosha_alpha_entropy_mean" in stats:
            lines.append("--- Kosha Alpha Entropy ---")
            flag = " OK" if stats["kosha_alpha_entropy_mean"] > 1.0 else " LOW"
            lines.append(f"  Mean H(α): {stats['kosha_alpha_entropy_mean']:.4f}  "
                          f"(expected: > 1.0 bits){flag}")
            lines.append("")

        # Binding Cache
        if "mean_intent_drift" in stats:
            lines.append("--- Binding Cache Metrics ---")
            lines.append(f"  Mean intent drift:   {stats['mean_intent_drift']:.4f}  "
                          f"(expected: 0.01–0.5)")
            if "salience_gini_proxy" in stats:
                lines.append(f"  Salience Gini proxy: {stats['salience_gini_proxy']:.4f}  "
                              f"(expected: 0.2–0.6)")
            if "mean_cache_hit_rate" in stats:
                lines.append(f"  Cache hit rate:      {stats['mean_cache_hit_rate']:.4f}  "
                              f"(expected: > 0.8)")
            lines.append("")

        # CTM+
        if "mean_ctm_phase_coherence" in stats:
            lines.append("--- CTM+ Offload Metrics ---")
            lines.append(f"  Layer access entropy: {stats['mean_ctm_phase_coherence']:.4f}  "
                          f"(expected: > 3.0 bits)")
            if "ctm_optimal_gpu_budget_95pct" in stats:
                lines.append(f"  Optimal GPU budget:   {stats['ctm_optimal_gpu_budget_95pct']} layers  "
                              f"(expected: < 24)")
            if "ctm_mode_transition_rate" in stats:
                flag = " OK" if stats["ctm_mode_transition_rate"] < 0.05 else " HIGH"
                lines.append(f"  Mode transition rate: {stats['ctm_mode_transition_rate']:.4f}  "
                              f"(expected: < 0.05){flag}")
            if "ctm_dominant_workload" in stats:
                lines.append(f"  Dominant workload:    {stats['ctm_dominant_workload']}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _std(values: List[float]) -> float:
    """Compute sample standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _entropy(probs: List[float]) -> float:
    """Compute Shannon entropy in bits from a probability distribution."""
    h = 0.0
    for p in probs:
        if p > 1e-12:
            h -= p * math.log2(p)
    return h


def _ngram_repetition_rate(token_ids: List[int], n: int) -> float:
    """Compute n-gram repetition rate: # repeated / total n-grams."""
    if len(token_ids) < n:
        return 0.0
    ngrams = []
    for i in range(len(token_ids) - n + 1):
        ngrams.append(tuple(token_ids[i:i + n]))
    total = len(ngrams)
    unique = len(set(ngrams))
    if total == 0:
        return 0.0
    return (total - unique) / total


def _histogram(values: List[float], bins: List[float]) -> Dict[str, int]:
    """Compute histogram of values given bin edges."""
    result = {}
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        label = f"{lo:.1f}-{hi:.1f}"
        count = sum(1 for v in values if lo <= v < hi)
        result[label] = count
    # Include values == max bin edge in last bucket
    if bins:
        label = f"{bins[-2]:.1f}-{bins[-1]:.1f}"
        count = sum(1 for v in values if v == bins[-1])
        result[label] = result.get(label, 0) + count
    return result
