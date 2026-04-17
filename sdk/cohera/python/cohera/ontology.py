"""COHERA Ontology Operations"""

from typing import Optional

from .tensor import CognitiveState, KoshaMode, SovereignState


class OntologyProjector:
    """Projects hidden states to 124-dim cognitive state."""
    def __init__(self, hidden_dim: int = 768, state_dim: int = 124):
        self.hidden_dim = hidden_dim
        self.state_dim = state_dim

    def __call__(self, hidden) -> CognitiveState:
        # TODO: Call cohera_ontology_project()
        return CognitiveState()


def project_to_cognitive_state(hidden, stream=None) -> CognitiveState:
    """Functional interface for ontology projection."""
    return OntologyProjector()(hidden)


class SovereignStateProjector:
    """
    Projects hidden states to the 32-D Sovereign State used by mistral_cg.

    Mirrors ``symbolu_training`` SovereignStateProjector:
      - Bhava(12):    softmax
      - Kosha(5):     sigmoid (default) or softmax (``kosha_mode``)
      - Vritti(5):    softmax
      - Guna(6):      sigmoid
      - Reserved(4):  tanh

    Intermediate projection is 1/4 of hidden_dim (matches reference impl:
    4096 -> 1024 -> 32).
    """
    def __init__(
        self,
        hidden_dim: int = 4096,
        intermediate_dim: Optional[int] = None,
        kosha_mode: KoshaMode = KoshaMode.SIGMOID,
    ):
        self.hidden_dim = hidden_dim
        self.intermediate_dim = (
            intermediate_dim if intermediate_dim is not None else max(1, hidden_dim // 4)
        )
        self.kosha_mode = kosha_mode
        # Device weights populated by runtime binding
        self.w_in = None   # [hidden_dim, intermediate_dim]
        self.w_out = None  # [intermediate_dim, 32]

    def __call__(self, hidden, stream=None) -> SovereignState:
        # Runtime path: cohera_ontology_project_sovereign(&out, hidden, kosha_mode, stream)
        return SovereignState()


def project_to_sovereign_state(
    hidden,
    kosha_mode: KoshaMode = KoshaMode.SIGMOID,
    hidden_dim: int = 4096,
    stream=None,
) -> SovereignState:
    """Functional interface for 32-D Sovereign State projection (mistral_cg)."""
    return SovereignStateProjector(hidden_dim=hidden_dim, kosha_mode=kosha_mode)(
        hidden, stream=stream
    )
