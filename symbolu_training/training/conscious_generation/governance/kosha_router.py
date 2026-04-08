"""
KoshaDomainRouter: Governance-plane routing over 6 primitives.

Produces α_t = softmax(R(h,o) + λ·Policy(k, d)) where:
    R(h,o)     = residual learned router (backward-compatible)
    Policy(k,d) = W_k·k + W_d·d + W_z·((U_k·k) ⊙ (U_d·d))

The governance plane (Pranamaya/Koshas [12:17]) explicitly controls routing.
Domain context provides the external task signal. Their interaction (k ⊗ d)
captures how each Kosha behaves differently across domains:
    - INTELLECTUAL × math → JEPA very high
    - MENTAL × narrative → CSR dominant
    - BLISSFUL × factual → stronger coherence gate

Kosha mapping to primitive bias:
    MATERIAL [12]     → base (surface/logits)
    VITAL [13]        → temperature/control
    MENTAL [14]       → CSR (phonemic/resonance)
    INTELLECTUAL [15] → JEPA + vritti (reasoning)
    BLISSFUL [16]     → coherence enforcement (BlissGate)

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict

NUM_PRIMITIVES = 6
PRIMITIVE_NAMES = ["base", "ontology", "jepa", "csr", "vritti", "guna"]

# Default domain categories
DEFAULT_DOMAINS = ["code", "math", "factual", "chat", "emotional", "narrative", "planning", "retrieval"]
DEFAULT_NUM_DOMAINS = len(DEFAULT_DOMAINS)

# Kosha indices within the 32D Sovereign State
KOSHA_START = 12
KOSHA_END = 17
NUM_KOSHAS = 5


class KoshaDomainRouter(nn.Module):
    """
    Governance-plane router: Domain × Kosha → Primitive routing weights.

    Combines a residual learned path (existing MLP) with a structured
    policy path that explicitly uses Kosha [12:17] and domain signals.
    The interaction term (k ⊗ d via low-rank factorization) captures
    how cognition mode changes under different task demands.

    Args:
        embed_dim: Transformer hidden state dimension
        state_dim: Ontological code dimension (32)
        num_primitives: Number of primitives to route over (6)
        num_domains: Number of domain categories (default 8)
        hidden_dim: Hidden dimension for residual MLP (None = embed_dim // 4)
        rank: Low-rank dimension for k ⊗ d interaction
        init_mode: "uniform" or "base_dominant"
        initial_policy_scale: Starting strength of structured policy (ramps up)
        use_kosha: Ablation switch — if False, zeros Kosha contribution
        use_domain: Ablation switch — if False, zeros domain contribution
        use_interaction: Ablation switch — if False, zeros k⊗d term
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,
        num_primitives: int = NUM_PRIMITIVES,
        num_domains: int = DEFAULT_NUM_DOMAINS,
        hidden_dim: Optional[int] = None,
        rank: int = 16,
        init_mode: str = "uniform",
        initial_policy_scale: float = 0.10,
        use_kosha: bool = True,
        use_domain: bool = True,
        use_interaction: bool = True,
    ):
        super().__init__()
        self.num_primitives = num_primitives
        self.num_domains = num_domains
        self.init_mode = init_mode

        # Ablation switches (zero logits, keep shapes)
        self.use_kosha = use_kosha
        self.use_domain = use_domain
        self.use_interaction = use_interaction

        hidden = hidden_dim or (embed_dim // 4)

        # === Residual learned router (backward-compatible) ===
        self.router = nn.Sequential(
            nn.Linear(embed_dim + state_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, num_primitives),
        )

        # === Structured policy: first-order terms ===
        # Kosha → primitive bias
        self.k_proj = nn.Linear(NUM_KOSHAS, num_primitives, bias=False)
        # Domain → primitive bias
        self.d_proj = nn.Linear(num_domains, num_primitives, bias=False)

        # === Low-rank interaction: (U_k·k) ⊙ (U_d·d) → W_z → primitives ===
        self.k_latent = nn.Linear(NUM_KOSHAS, rank, bias=False)
        self.d_latent = nn.Linear(num_domains, rank, bias=False)
        self.kd_proj = nn.Linear(rank, num_primitives, bias=False)

        # === Control parameters ===
        # Policy scale starts small, ramps up during training
        self.policy_scale = nn.Parameter(torch.tensor(initial_policy_scale))
        # Routing temperature (clamped to [1.0, 3.0])
        # Init at 2.0 to prevent early softmax collapse; the model can
        # learn to sharpen routing as training stabilizes.
        self.route_temp = nn.Parameter(torch.tensor(2.0))

        self._init_weights(init_mode)

    def _init_weights(self, init_mode: str) -> None:
        """Initialize weights for stable training."""
        # Residual router: small init for near-uniform initial routing
        for module in self.router:
            if isinstance(module, nn.Linear):
                nn.init.xavier_normal_(module.weight, gain=0.3)
                module.bias.data.fill_(0.0)

        if init_mode == "base_dominant":
            final_layer = self.router[-1]
            final_layer.bias.data[0] = 3.0

        # Policy paths: very small init so they don't dominate early
        nn.init.xavier_normal_(self.k_proj.weight, gain=0.1)
        nn.init.xavier_normal_(self.d_proj.weight, gain=0.1)
        nn.init.xavier_normal_(self.k_latent.weight, gain=0.1)
        nn.init.xavier_normal_(self.d_latent.weight, gain=0.1)
        nn.init.xavier_normal_(self.kd_proj.weight, gain=0.1)

    def forward(
        self,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
        domain: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute governance-plane routing weights.

        α = softmax((R(h,o) + λ·Policy(k,d)) / τ)

        Args:
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)
            domain: Domain distribution (..., num_domains). If None,
                    falls back to residual-only routing (backward-compatible).

        Returns:
            Dict with:
                'alpha': Routing weights (..., 6) summing to 1
                'residual_logits': From learned MLP path
                'policy_logits': From structured Kosha×Domain path
                'kosha': Extracted Kosha distribution (..., 5)
        """
        # Residual learned path (always active)
        combined = torch.cat([hidden, o_ctx], dim=-1)
        residual_logits = self.router(combined)  # (..., P)

        # Explicit Kosha extraction from governance plane
        k_raw = o_ctx[..., KOSHA_START:KOSHA_END]
        k = F.softmax(k_raw, dim=-1)  # (..., 5)

        # Build policy logits from active components (ablation-aware)
        # Each component produces (..., P) logits; disabled components contribute zero.
        k_logits = self.k_proj(k) if self.use_kosha else torch.zeros_like(residual_logits)

        if domain is not None:
            d_logits = self.d_proj(domain) if self.use_domain else torch.zeros_like(residual_logits)

            # Interaction: low-rank (U_k·k) ⊙ (U_d·d)
            if self.use_interaction and self.use_kosha and self.use_domain:
                u = self.k_latent(k)       # (..., rank)
                v = self.d_latent(domain)  # (..., rank)
                z = u * v                  # (..., rank)
                kd_logits = self.kd_proj(z)  # (..., P)
            else:
                kd_logits = torch.zeros_like(residual_logits)

            policy_logits = k_logits + d_logits + kd_logits
        else:
            # No domain signal: Kosha-only policy
            policy_logits = k_logits

        # Combine: residual + scaled policy
        logits = residual_logits + self.policy_scale * policy_logits
        tau = self.route_temp.clamp(min=1.0, max=3.0)
        alpha = F.softmax(logits / tau, dim=-1)

        return {
            "alpha": alpha,
            "logits": logits,
            "residual_logits": residual_logits,
            "policy_logits": policy_logits,
            "k_logits": k_logits,
            "kd_logits": kd_logits if domain is not None else torch.zeros_like(residual_logits),
            "kosha": k,
        }

    def get_diagnostics(self, result: Dict[str, torch.Tensor]) -> dict:
        """Compute routing diagnostics from forward() output."""
        with torch.no_grad():
            alpha = result["alpha"]
            mean_alpha = alpha.mean(dim=tuple(range(alpha.dim() - 1)))
            entropy = -(alpha * (alpha + 1e-8).log()).sum(dim=-1).mean()
            max_weight = alpha.max(dim=-1).values.mean()

            diag = {
                "alpha_mean": {name: mean_alpha[i].item()
                               for i, name in enumerate(PRIMITIVE_NAMES)},
                "alpha_entropy": entropy.item(),
                "alpha_max_weight": max_weight.item(),
                "policy_scale": self.policy_scale.item(),
                "route_temp": self.route_temp.item(),
            }

            # Policy vs residual magnitude ratio
            res_mag = result["residual_logits"].abs().mean().item()
            pol_mag = result["policy_logits"].abs().mean().item()
            diag["policy_residual_ratio"] = pol_mag / (res_mag + 1e-8)

            # Kosha distribution
            k = result["kosha"]
            mean_k = k.mean(dim=tuple(range(k.dim() - 1)))
            diag["kosha_mean"] = {
                name: mean_k[i].item()
                for i, name in enumerate(
                    ["material", "vital", "mental", "intellectual", "blissful"]
                )
            }

            return diag


# Backward compatibility alias
KoshaPrimitiveRouter = KoshaDomainRouter
