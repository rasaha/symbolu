"""guna_vritti_heads.py — Guna-sigmoid + Vritti auxiliary heads over a 32-D symbolic state projected from
Mistral hidden states. HARNESS ONLY — tests whether these targets can be represented/learned; it does NOT
validate Conscious Generation training, change runtime, or claim cognitive-state/consciousness detection.

FORMULA PROVENANCE (sourced, NOT invented):
  - 32-D sovereign-state layout + per-slice activations:
    Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 1; canonical code in
    symbolu_training/training/conscious_generation/token_ontology.py:
        Bhava[0:12] softmax · Kosha[12:17] softmax · Vritti[17:22] softmax · Guna[22:28] sigmoid ·
        Reserved[28:32] tanh
  - Guna head = SIGMOID 6-D (independent energy activations) -> BCE (multi-label). Names from
    symbolu_training/jepa/state_projector.py: ['SATTVA','RAJAS','TAMAS','VELOCITY','ACCEL','STABLE'].
  - Vritti head = SOFTMAX 5-class (cognitive-mode distribution) -> cross-entropy. Canonical names:
    ['PRAMANA','VIPARYAYA','VIKALPA','NIDRA','SMRITI']  (Pramāṇa/Viparyaya/Vikalpa/Nidrā/Smṛti).
  NOTE: the canonical token-side Guna SCORER (primitives/guna_scorer.py) uses softmax-3 (Sattva/Rajas/
  Tamas) for token-context bilinear scoring; the SOVEREIGN-STATE Guna slice [22:28] is sigmoid-6. This
  harness follows the SOVEREIGN-STATE Guna-SIGMOID formula, as the task specifies.

The 32-D projection is a *sovereign-state projection head*, NOT an attention head (Mistral attention
head_dim = 128; hidden = 4096). Bhava is NOT a supervised target here (interpretive/emergent only).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---- canonical constants (formula provenance) ----------------------------------------------------
HIDDEN_SIZE = 4096
SYMBOLIC_DIM = 32
GUNA_DIM = 6        # sovereign-state Guna slice [22:28], sigmoid
VRITTI_DIM = 5      # sovereign-state Vritti slice [17:22], softmax
SLICES = {"bhava": (0, 12), "kosha": (12, 17), "vritti": (17, 22), "guna": (22, 28), "reserved": (28, 32)}
GUNA_NAMES = ["SATTVA", "RAJAS", "TAMAS", "VELOCITY", "ACCEL", "STABLE"]
VRITTI_NAMES = ["PRAMANA", "VIPARYAYA", "VIKALPA", "NIDRA", "SMRITI"]
FORMULA_PROVENANCE = {
    "source_design": "Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md (Appendix D Phase 1)",
    "source_code": ["symbolu_training/training/conscious_generation/token_ontology.py",
                    "symbolu_training/training/conscious_generation/primitives/guna_scorer.py",
                    "symbolu_training/training/conscious_generation/primitives/vritti_scorer.py",
                    "symbolu_training/jepa/state_projector.py"],
    "guna": "sigmoid 6-D (sovereign-state slice [22:28]); BCE multi-label",
    "vritti": "softmax 5-class (sovereign-state slice [17:22]); cross-entropy",
    "available": True, "invented": False,
}

# decision labels (pre-registered)
DECISIONS = ("CG_GUNA_VRITTI_HARNESS_READY", "CG_GUNA_VRITTI_FORMULA_UNAVAILABLE",
             "CG_GUNA_VRITTI_SHAPE_ONLY_PASS", "CG_GUNA_VRITTI_SYNTHETIC_ONLY",
             "CG_GUNA_VRITTI_NO_LEARNABLE_SIGNAL", "CG_GUNA_VRITTI_LEARNS_SIGNAL",
             "CG_GUNA_VRITTI_ENV_UNAVAILABLE")


@dataclass
class SymbolicHeadConfig:
    hidden_size: int = HIDDEN_SIZE
    symbolic_dim: int = SYMBOLIC_DIM
    guna_dim: int = GUNA_DIM              # 6 (sigmoid, multi-label)
    vritti_dim: int = VRITTI_DIM          # 5 (softmax, single-label)
    pooling: str = "last_token"           # last_token | mean
    hidden_layer: int = -1                # which hidden layer to probe
    use_lora: bool = False                # optional future hook; OFF by default
    train_base_model: bool = False        # probe mode: base FROZEN
    train_projector: bool = True
    train_heads: bool = True
    loss_guna_weight: float = 1.0
    loss_vritti_weight: float = 1.0
    loss_lm_weight: float = 0.0           # first harness tests the HEADS, not generation

    def assert_probe_boundaries(self):
        assert not self.train_base_model, "harness default: base model FROZEN (probe/head-only)"
        assert not self.use_lora, "harness default: LoRA OFF (optional future hook)"
        assert self.loss_lm_weight == 0.0, "harness default: LM loss OFF (test the heads, not generation)"


def formula_available() -> bool:
    """True iff the Guna/Vritti formulas were sourced (not invented). If this is ever False, callers must
    return CG_GUNA_VRITTI_FORMULA_UNAVAILABLE and NOT invent a formula."""
    return bool(FORMULA_PROVENANCE.get("available")) and not FORMULA_PROVENANCE.get("invented")


# ================================================================================================ #
#  torch nn.Modules (import-guarded: pure logic above is usable without torch; these need torch)
# ================================================================================================ #
try:
    import torch
    import torch.nn as nn
    _TORCH = True
except Exception:                          # noqa: BLE001
    _TORCH = False


def _require_torch():
    if not _TORCH:
        raise RuntimeError("torch is required for the projector/heads (CPU-with-torch or GPU pod)")


if _TORCH:
    def pool_hidden(hidden_states, method: str = "last_token", attention_mask=None):
        """[B, T, H] -> [B, H]. last_token (last non-pad) or mean (masked)."""
        if method == "mean":
            if attention_mask is not None:
                m = attention_mask.unsqueeze(-1).to(hidden_states.dtype)
                return (hidden_states * m).sum(1) / m.sum(1).clamp(min=1.0)
            return hidden_states.mean(1)
        # last_token
        if attention_mask is not None:
            idx = attention_mask.sum(1).long() - 1
            return hidden_states[torch.arange(hidden_states.size(0)), idx]
        return hidden_states[:, -1, :]

    class SymbolicStateProjector(nn.Module):
        """h_t ∈ R^4096 -> s_t ∈ R^32  (LayerNorm -> Linear). Optional canonical per-slice activations
        (token_ontology.py): bhava/kosha/vritti softmax, guna sigmoid, reserved tanh."""
        def __init__(self, hidden_size: int = HIDDEN_SIZE, symbolic_dim: int = SYMBOLIC_DIM,
                     constrain_slices: bool = False):
            super().__init__()
            self.ln = nn.LayerNorm(hidden_size)
            self.proj = nn.Linear(hidden_size, symbolic_dim)
            self.constrain_slices = constrain_slices

        def forward(self, hidden_states, method: str = "last_token", attention_mask=None):
            if hidden_states.dim() == 3:
                h = pool_hidden(hidden_states, method, attention_mask)
            else:
                h = hidden_states
            s = self.proj(self.ln(h))
            if self.constrain_slices:
                out = s.clone()
                a, b = SLICES["bhava"]; out[:, a:b] = torch.softmax(s[:, a:b], -1)
                a, b = SLICES["kosha"]; out[:, a:b] = torch.softmax(s[:, a:b], -1)
                a, b = SLICES["vritti"]; out[:, a:b] = torch.softmax(s[:, a:b], -1)
                a, b = SLICES["guna"]; out[:, a:b] = torch.sigmoid(s[:, a:b])
                a, b = SLICES["reserved"]; out[:, a:b] = torch.tanh(s[:, a:b])
                return out
            return s

    class GunaHead(nn.Module):
        """Guna SIGMOID head: guna_scores = sigmoid(W_g s + b_g) ∈ [0,1]^6 (independent, multi-label)."""
        def __init__(self, symbolic_dim: int = SYMBOLIC_DIM, guna_dim: int = GUNA_DIM):
            super().__init__()
            self.fc = nn.Linear(symbolic_dim, guna_dim)

        def forward(self, s):                       # returns scores in [0,1]
            return torch.sigmoid(self.fc(s))

        def logits(self, s):
            return self.fc(s)

    class VrittiHead(nn.Module):
        """Vritti SOFTMAX head: 5-class cognitive-mode distribution (logits for CE)."""
        def __init__(self, symbolic_dim: int = SYMBOLIC_DIM, vritti_dim: int = VRITTI_DIM):
            super().__init__()
            self.fc = nn.Linear(symbolic_dim, vritti_dim)

        def forward(self, s):                       # returns probabilities
            return torch.softmax(self.fc(s), dim=-1)

        def logits(self, s):
            return self.fc(s)

    class SymbolicHeadBundle(nn.Module):
        """Projector + Guna(sigmoid) + Vritti(softmax) heads + combined auxiliary loss."""
        def __init__(self, cfg: SymbolicHeadConfig):
            super().__init__()
            self.cfg = cfg
            self.projector = SymbolicStateProjector(cfg.hidden_size, cfg.symbolic_dim)
            self.guna = GunaHead(cfg.symbolic_dim, cfg.guna_dim)
            self.vritti = VrittiHead(cfg.symbolic_dim, cfg.vritti_dim)

        def forward(self, hidden_states, attention_mask=None):
            s = self.projector(hidden_states, self.cfg.pooling, attention_mask)
            return {"state": s, "guna_scores": self.guna(s), "guna_logits": self.guna.logits(s),
                    "vritti_probs": self.vritti(s), "vritti_logits": self.vritti.logits(s)}

        def loss(self, out, guna_labels=None, vritti_labels=None):
            """L = λ_g·BCE(guna) + λ_v·CE(vritti) (+ λ_lm·LM, default 0). Returns (total, parts)."""
            parts = {}
            total = out["guna_logits"].new_zeros(())
            if guna_labels is not None:
                lg = nn.functional.binary_cross_entropy_with_logits(
                    out["guna_logits"], guna_labels.to(out["guna_logits"].dtype))
                parts["guna_bce"] = float(lg.detach())
                total = total + self.cfg.loss_guna_weight * lg
            if vritti_labels is not None:
                lv = nn.functional.cross_entropy(out["vritti_logits"], vritti_labels.long())
                parts["vritti_ce"] = float(lv.detach())
                total = total + self.cfg.loss_vritti_weight * lv
            parts["total"] = float(total.detach())
            return total, parts
else:
    def pool_hidden(*a, **k): _require_torch()                       # noqa: E704
    def SymbolicStateProjector(*a, **k): _require_torch()            # noqa: E704
    def GunaHead(*a, **k): _require_torch()                          # noqa: E704
    def VrittiHead(*a, **k): _require_torch()                        # noqa: E704
    def SymbolicHeadBundle(*a, **k): _require_torch()                # noqa: E704
