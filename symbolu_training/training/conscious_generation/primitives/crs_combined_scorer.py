"""
CRSCombinedScorer: Cognitive–Resonance–Semantic combined token scorer.

Implements the CRS doctrine where three branches are computed independently
and combined with semantic firewall authority:

  C = cognitive compatibility  (Vritti mode × Kosha sheath alignment)
  R = resonance compatibility  (phonemic Varna structure — delegates to CSRTokenScorer)
  S = semantic compatibility   (Bhava ontological identity, base-logit anchored)

Combination formula (semantic-dominant):
  S_raw  = bilinear(s_ctx, S_tok[w]) + α_base · ẑ_base(w)
  S_prob = σ(S_raw)
  S_gate = σ(k_s · (S_prob − τ_s))
  CRS(w) = S_gate · (w_C · C_raw + w_R · R_raw + w_S · S_raw) · S_prob

Non-negotiable rule: high resonance must never rescue low semantic correctness.

Reference: docs/audits/CRS_DOCTRINE_FREEZE.md
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Any


class CRSCombinedScorer(nn.Module):
    """
    Combined Cognitive–Resonance–Semantic scorer with semantic firewall.

    Args:
        csr_scorer: Existing CSRTokenScorer instance (delegated for R branch).
        embed_dim: Transformer hidden state dimension.
        semantic_dim: Dimension for S branch representations (d_s).
        bhava_dim: Bhava slice dimension (12).
        cognitive_dim: Cognitive feature dim (Vritti 5 + Kosha 5 = 10).
        cognitive_rank: Low-rank factorization rank for C bilinear form.
        semantic_rank: Low-rank factorization rank for S bilinear form.
        w_c: Branch weight for C (must sum to 1 with w_r, w_s).
        w_r: Branch weight for R.
        w_s: Branch weight for S.
        s_threshold: Semantic gate threshold (τ_s).
        k_s: Semantic gate sharpness.
        alpha_base: Base-logit anchor weight.
    """

    def __init__(
        self,
        csr_scorer: nn.Module,
        embed_dim: int,
        semantic_dim: int = 32,
        bhava_dim: int = 12,
        cognitive_dim: int = 10,
        cognitive_rank: int = 4,
        semantic_rank: int = 8,
        w_c: float = 0.2,
        w_r: float = 0.2,
        w_s: float = 0.6,
        s_threshold: float = 0.45,
        k_s: float = 10.0,
        alpha_base: float = 0.5,
    ):
        super().__init__()
        self.csr_scorer = csr_scorer
        self.embed_dim = embed_dim
        self.semantic_dim = semantic_dim
        self.bhava_dim = bhava_dim
        self.cognitive_dim = cognitive_dim

        # Fixed combination parameters (not learnable in Phase 2)
        self.w_c = w_c
        self.w_r = w_r
        self.w_s = w_s
        self.s_threshold = s_threshold
        self.k_s = k_s
        self.alpha_base = alpha_base

        # --- C branch: bilinear over 10D cognitive features ---
        # Low-rank: M_C = A_C @ B_C^T, A_C/B_C ∈ ℝ^{10 × rank}
        self.A_C = nn.Parameter(torch.empty(cognitive_dim, cognitive_rank))
        self.B_C = nn.Parameter(torch.empty(cognitive_dim, cognitive_rank))
        # gain=1.0 (not 0.3): softmax-normalized inputs have small per-element
        # values (~0.2 for 5-class simplex), so the bilinear product is inherently
        # small. gain=0.3 produced C_mean ≈ 0.005, too weak to contribute.
        nn.init.orthogonal_(self.A_C, gain=1.0)
        nn.init.orthogonal_(self.B_C, gain=1.0)

        # --- S branch: bilinear over learned semantic representations ---
        hidden_s = embed_dim // 4

        # Token-side: [e_w; bhava_w(12D)] → d_s
        self.semantic_token_mlp = nn.Sequential(
            nn.Linear(embed_dim + bhava_dim, hidden_s),
            nn.GELU(),
            nn.Linear(hidden_s, semantic_dim),
        )

        # Context-side: [h_t; bhava_ctx(12D)] → d_s
        self.semantic_context_mlp = nn.Sequential(
            nn.Linear(embed_dim + bhava_dim, hidden_s),
            nn.GELU(),
            nn.Linear(hidden_s, semantic_dim),
        )

        # Low-rank bilinear: M_S = A_S @ B_S^T
        self.A_S = nn.Parameter(torch.empty(semantic_dim, semantic_rank))
        self.B_S = nn.Parameter(torch.empty(semantic_dim, semantic_rank))
        nn.init.orthogonal_(self.A_S, gain=0.5)
        nn.init.orthogonal_(self.B_S, gain=0.5)

        self._init_semantic_mlps()

    def _init_semantic_mlps(self):
        """Initialize S MLPs with meaningful gain so S has signal from step 0."""
        for mlp in [self.semantic_token_mlp, self.semantic_context_mlp]:
            for module in mlp:
                if isinstance(module, nn.Linear):
                    nn.init.xavier_normal_(module.weight, gain=0.5)
                    nn.init.zeros_(module.bias)

    # ------------------------------------------------------------------
    # C branch
    # ------------------------------------------------------------------

    def compute_C(
        self,
        v_ctx: torch.Tensor,
        kosha_ctx: torch.Tensor,
        V_cand: torch.Tensor,
        Kosha_cand: torch.Tensor,
    ) -> torch.Tensor:
        """
        Cognitive compatibility: Vritti mode × Kosha sheath alignment.

        Args:
            v_ctx: Context Vritti profile (..., 5)
            kosha_ctx: Context Kosha distribution (..., 5)
            V_cand: Candidate Vritti profiles (..., K, 5)
            Kosha_cand: Candidate Kosha distributions (..., K, 5)

        Returns:
            C_raw: Cognitive compatibility scores (..., K)
        """
        # Assemble 10D cognitive vectors
        c_ctx = torch.cat([v_ctx, kosha_ctx], dim=-1)  # (..., 10)
        c_tok = torch.cat([V_cand, Kosha_cand], dim=-1)  # (..., K, 10)

        # Low-rank bilinear: c_ctx^T (A_C @ B_C^T) c_tok
        intermediate = c_ctx @ self.B_C  # (..., rank)
        m_ctx = intermediate @ self.A_C.t()  # (..., 10)
        return torch.einsum("...d,...kd->...k", m_ctx, c_tok)

    # ------------------------------------------------------------------
    # R branch
    # ------------------------------------------------------------------

    def compute_R(
        self,
        r_ctx: torch.Tensor,
        R_cand: torch.Tensor,
    ) -> torch.Tensor:
        """
        Resonance compatibility: delegates to existing CSRTokenScorer.

        Args:
            r_ctx: Context CSR representation (..., d_c)
            R_cand: Candidate CSR representations (..., K, d_c)

        Returns:
            R_raw: Resonance scores (..., K)
        """
        # CSRTokenScorer.forward expects (r_ctx, R_tok) where R_tok is (V, d_c)
        # or (K, d_c). For batched candidates (..., K, d_c), we use the same
        # bilinear logic inline to handle the extra batch dims.
        scorer = self.csr_scorer
        if scorer.use_low_rank:
            intermediate = r_ctx @ scorer.B  # (..., rank)
            m_r = intermediate @ scorer.A.t()  # (..., d_c)
        else:
            m_r = r_ctx @ scorer.M.t()  # (..., d_c)
        return torch.einsum("...d,...kd->...k", m_r, R_cand)

    # ------------------------------------------------------------------
    # S branch
    # ------------------------------------------------------------------

    def compute_S_token_repr(
        self,
        embeddings: torch.Tensor,
        bhava: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute token-side semantic representations for caching in S_tok.

        Args:
            embeddings: Token embeddings (N, embed_dim)
            bhava: Bhava slice of ontological codes (N, 12)

        Returns:
            S_tok representations (N, d_s)
        """
        combined = torch.cat([embeddings, bhava], dim=-1)
        return self.semantic_token_mlp(combined)

    def compute_S_context_repr(
        self,
        hidden: torch.Tensor,
        bhava_ctx: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute context-side semantic representation.

        Args:
            hidden: Transformer hidden states (..., embed_dim)
            bhava_ctx: Bhava slice of context state (..., 12)

        Returns:
            Semantic context representation (..., d_s)
        """
        combined = torch.cat([hidden, bhava_ctx], dim=-1)
        return self.semantic_context_mlp(combined)

    def compute_S(
        self,
        s_ctx: torch.Tensor,
        S_cand: torch.Tensor,
        base_logits_cand: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute raw semantic branch score with base-logit anchor.

        S_raw = bilinear(s_ctx, S_cand) + α_base · standardize(base_logits)

        Args:
            s_ctx: Semantic context repr (..., d_s)
            S_cand: Cached semantic token reprs (..., K, d_s)
            base_logits_cand: Base logits for candidates (..., K)

        Returns:
            S_raw: Raw semantic scores (..., K)
        """
        # Bilinear: s_ctx^T M_S S_cand
        intermediate = s_ctx @ self.B_S  # (..., rank)
        m_s = intermediate @ self.A_S.t()  # (..., d_s)
        s_bilinear = torch.einsum("...d,...kd->...k", m_s, S_cand)

        # Base-logit anchor: standardize within candidate set
        mu = base_logits_cand.mean(dim=-1, keepdim=True)
        sigma = base_logits_cand.std(dim=-1, keepdim=True) + 1e-6
        z_base = (base_logits_cand - mu) / sigma

        return s_bilinear + self.alpha_base * z_base

    # ------------------------------------------------------------------
    # Combination with semantic firewall
    # ------------------------------------------------------------------

    def combine_crs(
        self,
        C_raw: torch.Tensor,
        R_raw: torch.Tensor,
        S_raw: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Combine CRS branches with semantic firewall.

        S_centered = S_raw - mean(S_raw)              — prevent S mean drift
        S_prob = σ(S_centered)                         — centered, so σ ≈ 0.5 on average
        S_gate = σ(k_s · (S_prob − τ_s))
        CRS    = S_gate · (w_C·C + w_R·R + w_S·S) · S_prob

        Center-normalization ensures S_prob stays near 0.5 on average across
        candidates, preventing the negative-drift failure mode where S_mean
        goes strongly negative → S_gate closes → L_S explodes → runaway.
        The gate still discriminates: candidates with above-average S get
        S_prob > 0.5 → S_gate opens; below-average get S_gate closes.

        Returns:
            Dict with 'crs_score', 'S_prob', 'S_gate'
        """
        # Center S within each candidate set to prevent mean drift
        S_centered = S_raw - S_raw.mean(dim=-1, keepdim=True)
        S_prob = torch.sigmoid(S_centered)
        S_gate = torch.sigmoid(self.k_s * (S_prob - self.s_threshold))
        weighted = self.w_c * C_raw + self.w_r * R_raw + self.w_s * S_raw
        crs_score = S_gate * weighted * S_prob

        return {
            "crs_score": crs_score,
            "S_prob": S_prob,
            "S_gate": S_gate,
        }

    # ------------------------------------------------------------------
    # Full forward
    # ------------------------------------------------------------------

    def forward(
        self,
        v_ctx: torch.Tensor,
        kosha_ctx: torch.Tensor,
        V_cand: torch.Tensor,
        Kosha_cand: torch.Tensor,
        r_ctx: torch.Tensor,
        R_cand: torch.Tensor,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
        S_cand: torch.Tensor,
        base_logits_cand: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Full CRS forward pass.

        Args:
            v_ctx: Context Vritti profile (..., 5)
            kosha_ctx: Context Kosha distribution (..., 5)
            V_cand: Candidate Vritti profiles (..., K, 5)
            Kosha_cand: Candidate Kosha slices (..., K, 5)
            r_ctx: Context CSR representation (..., d_c)
            R_cand: Candidate CSR representations (..., K, d_c)
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., 32)
            S_cand: Cached semantic token reprs (..., K, d_s)
            base_logits_cand: Base logits for candidates (..., K)

        Returns:
            Dict with 'crs_score', 'C', 'R', 'S', 'S_prob', 'S_gate'
        """
        C_raw = self.compute_C(v_ctx, kosha_ctx, V_cand, Kosha_cand)
        R_raw = self.compute_R(r_ctx, R_cand)

        bhava_ctx = o_ctx[..., 0:12]
        s_ctx = self.compute_S_context_repr(hidden, bhava_ctx)
        S_raw = self.compute_S(s_ctx, S_cand, base_logits_cand)

        combine_result = self.combine_crs(C_raw, R_raw, S_raw)

        return {
            "crs_score": combine_result["crs_score"],
            "C": C_raw,
            "R": R_raw,
            "S": S_raw,
            "S_prob": combine_result["S_prob"],
            "S_gate": combine_result["S_gate"],
        }
