"""
Embedding Diagnostics for Conscious Generation Training.

Tracks whether CG auxiliary losses are meaningfully changing embeddings
during Mistral (or other backbone) retraining. Without this, you have
no visibility into whether the auxiliaries are cosmetic or structural.

Metrics tracked:
  1. State projector output drift    — cosine distance of 32D states between snapshots
  2. Adapter gate magnitude          — how much the phase adapter is steering
  3. Ontological code distribution   — std/entropy of 32D projections across vocab sample
  4. Per-primitive cache drift       — cosine distance of P_tok/R_tok/V_tok/G_tok buffers
  5. Embedding neighborhood shift    — whether nearest-neighbor structure is changing
  6. Gradient norm per CG module     — are auxiliaries actually backpropagating?

Usage:
    --enable_embedding_diagnostics          Master toggle
    --embedding_diag_interval 200           Steps between snapshots (default: 200)
    --embedding_diag_vocab_sample 1000      Vocab tokens to sample (default: 1000)
    --embedding_diag_neighbors 20           Neighbors to track for stability (default: 20)
"""

from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn


class EmbeddingDiagnostics:
    """
    Snapshots embedding-derived representations at intervals and computes
    drift metrics to verify CG auxiliaries are changing the model meaningfully.
    """

    def __init__(
        self,
        interval: int = 200,
        vocab_sample_size: int = 1000,
        neighbor_k: int = 20,
        seed: int = 42,
    ):
        self.interval = interval
        self.vocab_sample_size = vocab_sample_size
        self.neighbor_k = neighbor_k
        self.seed = seed

        # Snapshot storage
        self._prev_state_proj: Optional[torch.Tensor] = None      # [sample, 32]
        self._prev_P_tok: Optional[torch.Tensor] = None            # [sample, d_j]
        self._prev_R_tok: Optional[torch.Tensor] = None            # [sample, d_c]
        self._prev_V_tok: Optional[torch.Tensor] = None            # [sample, 5]
        self._prev_G_tok: Optional[torch.Tensor] = None            # [sample, 3]
        self._prev_neighbors: Optional[torch.Tensor] = None        # [sample, K] indices
        self._prev_adapter_gate: Optional[float] = None

        # Sampled vocab indices (fixed for consistency)
        self._sample_ids: Optional[torch.Tensor] = None

        # History for trend detection
        self.history: List[Dict[str, float]] = []

    def _ensure_sample_ids(self, vocab_size: int, device: torch.device) -> torch.Tensor:
        """Generate or return fixed vocab sample indices."""
        if self._sample_ids is None or self._sample_ids.device != device:
            gen = torch.Generator(device='cpu')
            gen.manual_seed(self.seed)
            n = min(self.vocab_sample_size, vocab_size)
            self._sample_ids = torch.randperm(vocab_size, generator=gen)[:n].to(device)
        return self._sample_ids

    @torch.no_grad()
    def snapshot(
        self,
        model: nn.Module,
        global_step: int,
        token_cache: Optional[Any] = None,
    ) -> Optional[Dict[str, float]]:
        """
        Take a snapshot and compute drift metrics vs previous snapshot.

        Args:
            model: The MistralCGWrapper (or any model with state_projector, adapter_gate)
            global_step: Current training step
            token_cache: CG TokenPrimitiveCache (has O_tok, P_tok, etc.)

        Returns:
            Dict of diagnostic metrics, or None if this step is not a snapshot step.
        """
        if global_step % self.interval != 0:
            return None

        metrics: Dict[str, float] = {"step": global_step}
        device = next(model.parameters()).device

        # ── 1. State Projector Output Drift ──────────────────────────
        emb_layer = None
        if hasattr(model, 'get_input_embeddings'):
            emb_layer = model.get_input_embeddings()
        elif hasattr(model, 'backbone'):
            emb_layer = model.backbone.get_input_embeddings()

        if emb_layer is not None and hasattr(emb_layer, 'weight'):
            vocab_size = emb_layer.weight.shape[0]
            sample_ids = self._ensure_sample_ids(vocab_size, emb_layer.weight.device)
            sample_emb = emb_layer.weight[sample_ids].float()  # [N, D_mistral]

            # Project through state_projector if available
            state_proj = None
            if hasattr(model, 'state_projector'):
                state_proj = model.state_projector(sample_emb)  # [N, 32]
            elif hasattr(model, 'conscious_gen') and 'token_projector' in model.conscious_gen:
                state_proj = model.conscious_gen['token_projector'](sample_emb)

            if state_proj is not None:
                state_proj = state_proj.float()

                # Drift from previous snapshot
                if self._prev_state_proj is not None:
                    cos_sim = torch.nn.functional.cosine_similarity(
                        state_proj, self._prev_state_proj.to(state_proj.device), dim=-1
                    )
                    metrics["state_proj_cosine_mean"] = cos_sim.mean().item()
                    metrics["state_proj_cosine_std"] = cos_sim.std().item()
                    metrics["state_proj_drift"] = 1.0 - cos_sim.mean().item()

                    # L2 drift per token
                    l2_drift = (state_proj - self._prev_state_proj.to(state_proj.device)).norm(dim=-1)
                    metrics["state_proj_l2_drift_mean"] = l2_drift.mean().item()
                    metrics["state_proj_l2_drift_max"] = l2_drift.max().item()

                # Distribution stats
                metrics["state_proj_std"] = state_proj.std().item()
                metrics["state_proj_norm_mean"] = state_proj.norm(dim=-1).mean().item()

                # Per-dimension activation (are all 32 dims being used?)
                dim_std = state_proj.std(dim=0)  # [32]
                metrics["state_proj_dim_std_min"] = dim_std.min().item()
                metrics["state_proj_dim_std_max"] = dim_std.max().item()
                metrics["state_proj_dead_dims"] = (dim_std < 1e-4).sum().item()

                self._prev_state_proj = state_proj.cpu()

        # ── 2. Adapter Gate Magnitude ────────────────────────────────
        if hasattr(model, 'adapter_gate'):
            gate_val = torch.sigmoid(model.adapter_gate).item()
            metrics["adapter_gate"] = gate_val
            if self._prev_adapter_gate is not None:
                metrics["adapter_gate_delta"] = gate_val - self._prev_adapter_gate
            self._prev_adapter_gate = gate_val

        # ── 3. Phase Adapter Weight Norms ────────────────────────────
        if hasattr(model, 'phase_adapter'):
            total_norm = 0.0
            for p in model.phase_adapter.parameters():
                total_norm += p.data.float().norm().item() ** 2
            metrics["phase_adapter_weight_norm"] = total_norm ** 0.5

        # ── 4. Per-Primitive Cache Drift ─────────────────────────────
        if token_cache is not None:
            for buf_name, prev_attr in [
                ('P_tok', '_prev_P_tok'),
                ('R_tok', '_prev_R_tok'),
                ('V_tok', '_prev_V_tok'),
                ('G_tok', '_prev_G_tok'),
            ]:
                buf = getattr(token_cache, buf_name, None)
                if buf is not None and buf.numel() > 0:
                    buf_float = buf.float()
                    sample_ids = self._ensure_sample_ids(buf.shape[0], buf.device)
                    valid_ids = sample_ids[sample_ids < buf.shape[0]]
                    sampled = buf_float[valid_ids]

                    prev = getattr(self, prev_attr)
                    if prev is not None:
                        prev_dev = prev.to(sampled.device)
                        min_len = min(sampled.shape[0], prev_dev.shape[0])
                        cos = torch.nn.functional.cosine_similarity(
                            sampled[:min_len], prev_dev[:min_len], dim=-1
                        )
                        metrics[f"{buf_name}_drift"] = 1.0 - cos.mean().item()
                        metrics[f"{buf_name}_cosine_mean"] = cos.mean().item()

                    metrics[f"{buf_name}_norm_mean"] = sampled.norm(dim=-1).mean().item()
                    metrics[f"{buf_name}_std"] = sampled.std().item()

                    setattr(self, prev_attr, sampled.cpu())

        # ── 5. Embedding Neighborhood Shift ──────────────────────────
        if emb_layer is not None and hasattr(emb_layer, 'weight'):
            sample_ids = self._ensure_sample_ids(emb_layer.weight.shape[0], emb_layer.weight.device)
            sample_emb = emb_layer.weight[sample_ids].float()

            # Compute pairwise distances within sample (efficient: use matmul)
            normed = torch.nn.functional.normalize(sample_emb, dim=-1)
            sim_matrix = normed @ normed.T  # [N, N]
            # Zero out self-similarity
            sim_matrix.fill_diagonal_(-float('inf'))
            # Get top-K neighbors
            _, curr_neighbors = sim_matrix.topk(min(self.neighbor_k, sim_matrix.shape[0] - 1), dim=-1)

            if self._prev_neighbors is not None:
                prev_n = self._prev_neighbors.to(curr_neighbors.device)
                min_len = min(curr_neighbors.shape[0], prev_n.shape[0])
                k = min(curr_neighbors.shape[1], prev_n.shape[1])
                # Jaccard overlap per token
                overlaps = []
                for i in range(min_len):
                    curr_set = set(curr_neighbors[i, :k].tolist())
                    prev_set = set(prev_n[i, :k].tolist())
                    if len(curr_set | prev_set) > 0:
                        overlaps.append(len(curr_set & prev_set) / len(curr_set | prev_set))
                if overlaps:
                    metrics["neighbor_jaccard_mean"] = sum(overlaps) / len(overlaps)
                    metrics["neighbor_jaccard_min"] = min(overlaps)

            self._prev_neighbors = curr_neighbors.cpu()

        # ── 6. CG Module Gradient Norms ──────────────────────────────
        cg_modules = {}
        if hasattr(model, 'state_projector'):
            cg_modules['state_projector'] = model.state_projector
        if hasattr(model, 'phase_adapter'):
            cg_modules['phase_adapter'] = model.phase_adapter
        if hasattr(model, 'intent_projector'):
            cg_modules['intent_projector'] = model.intent_projector
        if hasattr(model, 'conscious_gen'):
            for name in ('token_projector', 'ontology_scorer', 'jepa_scorer',
                         'csr_scorer', 'vritti_scorer', 'guna_scorer',
                         'kosha_router', 'bliss_gate'):
                if name in model.conscious_gen:
                    cg_modules[name] = model.conscious_gen[name]

        for name, mod in cg_modules.items():
            grad_norm = 0.0
            param_count = 0
            has_grad = False
            for p in mod.parameters():
                if p.grad is not None:
                    has_grad = True
                    grad_norm += p.grad.float().norm().item() ** 2
                    param_count += p.numel()
            if has_grad:
                metrics[f"grad_norm/{name}"] = grad_norm ** 0.5
                metrics[f"grad_norm_per_param/{name}"] = (grad_norm ** 0.5) / max(param_count, 1)

        # ── Store history ────────────────────────────────────────────
        self.history.append(metrics)

        return metrics

    def get_trend_summary(self, last_n: int = 5) -> Dict[str, str]:
        """
        Produce a human-readable trend summary from recent snapshots.

        Returns warnings if embeddings appear stagnant.
        """
        summary: Dict[str, str] = {}
        if len(self.history) < 2:
            summary["status"] = "insufficient_data"
            return summary

        recent = self.history[-last_n:]

        # State projector drift trend
        drifts = [h.get("state_proj_drift", 0) for h in recent if "state_proj_drift" in h]
        if drifts:
            avg_drift = sum(drifts) / len(drifts)
            if avg_drift < 1e-5:
                summary["state_proj"] = f"STAGNANT (drift={avg_drift:.2e}) — CG not changing projections"
            elif avg_drift < 1e-3:
                summary["state_proj"] = f"SLOW (drift={avg_drift:.2e}) — weak CG signal"
            else:
                summary["state_proj"] = f"ACTIVE (drift={avg_drift:.4f})"

        # Dead dimensions warning
        dead_dims = [h.get("state_proj_dead_dims", 0) for h in recent]
        if dead_dims and max(dead_dims) > 0:
            summary["dead_dims"] = f"{max(dead_dims)}/32 dimensions inactive"

        # Adapter gate trend
        gates = [h.get("adapter_gate", 0) for h in recent if "adapter_gate" in h]
        if gates:
            if gates[-1] < 0.01:
                summary["adapter_gate"] = f"NEAR-ZERO ({gates[-1]:.4f}) — adapter not engaged"
            else:
                summary["adapter_gate"] = f"ACTIVE ({gates[-1]:.4f})"

        # Primitive cache drift
        for buf in ('P_tok', 'R_tok', 'V_tok', 'G_tok'):
            key = f"{buf}_drift"
            vals = [h.get(key, 0) for h in recent if key in h]
            if vals:
                avg = sum(vals) / len(vals)
                if avg < 1e-5:
                    summary[buf] = f"FROZEN (drift={avg:.2e})"
                else:
                    summary[buf] = f"ACTIVE (drift={avg:.4f})"

        # Neighborhood stability
        jaccard = [h.get("neighbor_jaccard_mean", 1.0) for h in recent if "neighbor_jaccard_mean" in h]
        if jaccard:
            avg_j = sum(jaccard) / len(jaccard)
            if avg_j > 0.99:
                summary["neighborhoods"] = f"FROZEN (jaccard={avg_j:.4f}) — no structural change"
            elif avg_j > 0.90:
                summary["neighborhoods"] = f"STABLE (jaccard={avg_j:.4f})"
            else:
                summary["neighborhoods"] = f"SHIFTING (jaccard={avg_j:.4f})"

        # Gradient activity
        grad_keys = [k for k in recent[-1] if k.startswith("grad_norm/")]
        zero_grad_modules = []
        for gk in grad_keys:
            vals = [h.get(gk, 0) for h in recent if gk in h]
            if vals and max(vals) < 1e-8:
                zero_grad_modules.append(gk.split("/")[1])
        if zero_grad_modules:
            summary["zero_grad"] = f"No gradients: {', '.join(zero_grad_modules)}"

        return summary

    def format_console_log(self, metrics: Dict[str, float]) -> str:
        """Format metrics as a concise console log line."""
        parts = [f"  [EMBED-DIAG] Step {int(metrics.get('step', 0))}"]

        if "state_proj_drift" in metrics:
            parts.append(f"proj_drift={metrics['state_proj_drift']:.4f}")
        if "state_proj_dead_dims" in metrics:
            parts.append(f"dead_dims={int(metrics['state_proj_dead_dims'])}/32")
        if "adapter_gate" in metrics:
            parts.append(f"gate={metrics['adapter_gate']:.4f}")
        if "phase_adapter_weight_norm" in metrics:
            parts.append(f"adapter_wnorm={metrics['phase_adapter_weight_norm']:.3f}")

        # Primitive drifts
        prim_parts = []
        for buf in ('P_tok', 'R_tok', 'V_tok', 'G_tok'):
            key = f"{buf}_drift"
            if key in metrics:
                prim_parts.append(f"{buf}={metrics[key]:.4f}")
        if prim_parts:
            parts.append(f"cache_drift=[{', '.join(prim_parts)}]")

        if "neighbor_jaccard_mean" in metrics:
            parts.append(f"nn_jaccard={metrics['neighbor_jaccard_mean']:.4f}")

        return " | ".join(parts)
