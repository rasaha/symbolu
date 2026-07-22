"""U1-U5 peer-to-peer phase-coherence dynamics, as a detached post-inference observer.

Given phases Phi [Q, N, W] (Q queries, N channels, W window positions) extracted from the frozen
inference states, this computes the original USE sequence on a DETACHED copy — it never touches
the model:

  U1 pairwise correlation   C_ij = (1/W) sum_k cos(phi_i(t-k) - phi_j(t-k))
  U2 global coherence       C_total = sum_{i<j} w_ij C_ij            (uniform w_ij)
  U3 local gradient         dC/dphi_i = - sum_j w_ij sin(phi_i - phi_j)
  U4 counterfactual demand  dphi_i = alpha * (- sum_j w_ij sin(phi_i - phi_j))   (NOT applied to model)
  U5 convergence diagnostics run the peer update on the detached instantaneous phases and record
     initial/final coherence, iterations to converge, correction energy, per-channel demand, and
     unresolved incoherence.

Weights are uniform (any learned/topology weighting would be a separately tested extension). The
relaxation acts on the instantaneous phase vector at the query position (the "current state"); U1
/U2 windowed coherence is reported separately as the completed inference's temporal phase-locking.
"""

from __future__ import annotations

from typing import Dict

import torch


def _wrap(x: torch.Tensor) -> torch.Tensor:
    """Wrap angles to (-pi, pi]."""
    return (x + torch.pi) % (2 * torch.pi) - torch.pi


def windowed_pairwise_coherence(Phi: torch.Tensor) -> torch.Tensor:
    """U1/U2. Phi [Q,N,W] -> C_total [Q] in [-1,1] (mean over unordered channel pairs)."""
    Q, N, W = Phi.shape
    di = Phi.unsqueeze(2) - Phi.unsqueeze(1)            # [Q,N,N,W]
    C = torch.cos(di).mean(dim=-1)                       # [Q,N,N] pairwise windowed coherence
    iu = torch.triu_indices(N, N, offset=1)
    pairs = C[:, iu[0], iu[1]]                            # [Q, N*(N-1)/2]
    return pairs.mean(dim=-1)                             # uniform-weight global coherence


def order_parameter(phi: torch.Tensor) -> torch.Tensor:
    """Kuramoto order parameter R in [0,1]. phi [Q,N] -> [Q]."""
    return torch.sqrt(torch.cos(phi).mean(-1) ** 2 + torch.sin(phi).mean(-1) ** 2)


@torch.no_grad()
def relax(phi0: torch.Tensor, alpha: float = 0.1, max_iter: int = 200, eps: float = 1e-5
          ) -> Dict[str, torch.Tensor]:
    """U4/U5. Peer-to-peer Kuramoto relaxation on detached phases phi0 [Q,N].

    Uniform normalized coupling (w_ij = 1/N). Records per-query convergence diagnostics. Nothing
    here is applied to the model; this is a counterfactual 'how much correction would be needed'.
    """
    Q, N = phi0.shape
    phi = phi0.clone()
    R_prev = order_parameter(phi)
    R_init = R_prev.clone()
    converged_at = torch.full((Q,), float(max_iter), dtype=torch.float32)
    done = torch.zeros(Q, dtype=torch.bool)
    for r in range(1, max_iter + 1):
        diff = phi.unsqueeze(2) - phi.unsqueeze(1)       # [Q,N,N] = phi_i - phi_j
        # dphi_i = -alpha * mean_j sin(phi_i - phi_j)  (Kuramoto consensus coupling)
        dphi = -alpha * torch.sin(diff).mean(dim=2)      # [Q,N]
        phi = _wrap(phi + dphi)
        R = order_parameter(phi)
        newly = (~done) & ((R - R_prev).abs() < eps)
        converged_at = torch.where(newly, torch.full_like(converged_at, float(r)), converged_at)
        done = done | newly
        R_prev = R
        if bool(done.all()):
            break
    R_final = order_parameter(phi)
    disp = _wrap(phi - phi0)                              # per-channel correction demand D_i
    D = disp.abs()
    return {
        "R_initial": R_init,
        "R_final": R_final,
        "delta_R": R_final - R_init,
        "E_correction": (disp ** 2).sum(dim=1),           # total correction energy
        "D_max": D.max(dim=1).values,
        "D_mean": D.mean(dim=1),
        "T_conv": converged_at,
        "R_unresolved": 1.0 - R_final,
    }
