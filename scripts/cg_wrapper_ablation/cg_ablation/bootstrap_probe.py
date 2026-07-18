"""bootstrap_probe.py — removable, env-gated instrumentation for CG gate/adapter dynamics.

Logs, every N steps, the quantities that decide whether the CG wrapper can become active:

    step  gate_value  gate_grad_norm  phase_adapter_output_norm  correction_hidden_ratio
          state_projector_grad_norm  intent_projector_grad_norm  phase_adapter_grad_norm

Design constraints (all satisfied):
  * No behavioral change — reads .grad and forward activations only; never writes params/grads,
    never participates in autograd (everything detached, no_grad).
  * Removable — activated only when env var CG_BOOTSTRAP_PROBE_EVERY is set; the train.py hook is
    a single guarded block. Call get_probe(model).remove() to detach the forward hooks.
  * Training-safe — wrapped so any failure is swallowed by the caller; hooks stash one scalar.
  * Negligible overhead — two cheap norm reductions per forward + a few grad norms every N steps.

Usage (already wired into train.py):
    CG_BOOTSTRAP_PROBE_EVERY=10 python train_unified_llm.py --model_type mistral_cg ...
"""

from __future__ import annotations

from typing import List, Optional

_PROBES: dict = {}  # id(model) -> BootstrapProbe (install hooks once)


def _unwrap(model):
    return getattr(model, "module", model)


class BootstrapProbe:
    def __init__(self, model, every: int = 50, writer=None):
        self.model = _unwrap(model)
        self.every = int(every)
        self.writer = writer
        self._a_norm: Optional[float] = None   # ‖adapter_output‖ (post-RMSNorm)
        self._h_norm: Optional[float] = None   # ‖adapted_hidden‖ (lm_head input)
        self._handles: List = []

    # ---- forward hooks: capture activation norms (detached, no grad) ----------
    def install(self) -> "BootstrapProbe":
        import torch  # noqa: F401
        m = self.model
        norm_mod = getattr(m, "adapter_output_norm", None)
        if norm_mod is not None:
            self._handles.append(norm_mod.register_forward_hook(self._cap_a))
        backbone = getattr(m, "backbone", None)
        lm_head = getattr(backbone, "lm_head", None) if backbone is not None else None
        if lm_head is not None:
            self._handles.append(lm_head.register_forward_pre_hook(self._cap_h))
        return self

    def _cap_a(self, _mod, _inp, out):
        import torch
        with torch.no_grad():
            self._a_norm = float(out.detach().float().norm(dim=-1).mean().item())

    def _cap_h(self, _mod, inp):
        import torch
        with torch.no_grad():
            x = inp[0] if isinstance(inp, (tuple, list)) else inp
            self._h_norm = float(x.detach().float().norm(dim=-1).mean().item())

    def remove(self) -> None:
        for h in self._handles:
            try:
                h.remove()
            except Exception:
                pass
        self._handles = []

    # ---- grad-norm helpers -----------------------------------------------------
    @staticmethod
    def _grad_norm(params) -> float:
        import math
        total = 0.0
        seen = 0
        for p in params:
            g = getattr(p, "grad", None)
            if g is not None:
                total += float(g.detach().float().norm().item()) ** 2
                seen += 1
        return math.sqrt(total) if seen else float("nan")

    def _group(self, substr: str):
        return [p for n, p in self.model.named_parameters() if substr in n]

    # ---- emit ------------------------------------------------------------------
    def log(self, step: int) -> None:
        if self.every <= 0 or (step % self.every) != 0:
            return
        import torch
        m = self.model
        gate_p = getattr(m, "adapter_gate", None)
        if gate_p is None:
            return
        gate_val = float(torch.sigmoid(gate_p.detach()).item())
        gate_gn = self._grad_norm([gate_p])
        pa_gn = self._grad_norm(self._group("phase_adapter"))
        sp_gn = self._grad_norm(self._group("state_projector"))
        ip_gn = self._grad_norm(self._group("intent_projector"))
        a = self._a_norm or 0.0
        h = self._h_norm or 0.0
        ratio = (gate_val * a / h) if h else 0.0
        print(
            f"  [CG-BOOTSTRAP] step={step} gate={gate_val:.4f} gate_gn={gate_gn:.3e} "
            f"pa_out_norm={a:.3e} corr/hidden={ratio:.3e} "
            f"sp_gn={sp_gn:.3e} ip_gn={ip_gn:.3e} pa_gn={pa_gn:.3e}"
        )
        if self.writer is not None:
            try:
                self.writer.add_scalar("cg_bootstrap/gate", gate_val, step)
                self.writer.add_scalar("cg_bootstrap/gate_grad_norm", gate_gn, step)
                self.writer.add_scalar("cg_bootstrap/pa_out_norm", a, step)
                self.writer.add_scalar("cg_bootstrap/corr_hidden_ratio", ratio, step)
                self.writer.add_scalar("cg_bootstrap/state_proj_grad_norm", sp_gn, step)
                self.writer.add_scalar("cg_bootstrap/intent_proj_grad_norm", ip_gn, step)
            except Exception:
                pass


def get_probe(model, every: int = 50, writer=None) -> BootstrapProbe:
    """Return the (singleton-per-model) probe, installing forward hooks on first call."""
    key = id(_unwrap(model))
    probe = _PROBES.get(key)
    if probe is None:
        probe = BootstrapProbe(model, every=every, writer=writer).install()
        _PROBES[key] = probe
    else:
        probe.every = int(every)
    return probe
