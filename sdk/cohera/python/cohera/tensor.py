"""
COHERA Tensor and Cognitive State
"""

from typing import List, Optional, Union
from dataclasses import dataclass
from enum import IntEnum


class KoshaMode(IntEnum):
    """Normalization mode for the 5-D Kosha component of Sovereign State."""
    SIGMOID = 0
    SOFTMAX = 1


class DType(IntEnum):
    """Data types supported by COHERA."""
    FP16 = 0
    BF16 = 1
    FP32 = 2
    INT8 = 3


class Tensor:
    """
    COHERA Tensor on device memory (HBM3).

    Example:
        >>> t = Tensor([32, 1024, 768], dtype=DType.FP16)
        >>> t.copy_from_host(numpy_array)
    """

    def __init__(
        self,
        shape: List[int],
        dtype: DType = DType.FP16,
        device: Optional["Device"] = None,
        ontology_layer: int = -1,
    ):
        self.shape = list(shape)
        self.dtype = dtype
        self.device = device
        self.ontology_layer = ontology_layer
        self._data = None  # Device pointer (stub)
        self._allocate()

    def _allocate(self) -> None:
        """Allocate device memory."""
        # TODO: Call cohera_tensor_create()
        pass

    @property
    def size(self) -> int:
        """Total number of elements."""
        result = 1
        for dim in self.shape:
            result *= dim
        return result

    @property
    def nbytes(self) -> int:
        """Size in bytes."""
        dtype_sizes = {DType.FP16: 2, DType.BF16: 2, DType.FP32: 4, DType.INT8: 1}
        return self.size * dtype_sizes[self.dtype]

    def copy_from_host(self, data) -> None:
        """Copy data from host (numpy array)."""
        # TODO: Call cohera_tensor_copy_from_host()
        pass

    def copy_to_host(self, data=None):
        """Copy data to host (returns numpy array)."""
        # TODO: Call cohera_tensor_copy_to_host()
        import numpy as np
        return np.zeros(self.shape, dtype=np.float16)

    def __del__(self):
        """Free device memory."""
        # TODO: Call cohera_tensor_destroy()
        pass

    def __repr__(self) -> str:
        return f"Tensor(shape={self.shape}, dtype={self.dtype.name})"


@dataclass
class CognitiveState:
    """
    124-dimensional cognitive state output from OPU.

    Dimensions:
        - phoneme_energy[44]: Phonemic layer activations
        - topic_embedding[64]: Semantic topic embedding
        - ontology_probs[12]: 12-layer activation probabilities
        - dynamics[4]: coherence, entropy, confidence, momentum
    """
    phoneme_energy: List[float] = None
    topic_embedding: List[float] = None
    ontology_probs: List[float] = None
    coherence: float = 0.0
    entropy: float = 0.0
    confidence: float = 0.0
    momentum: float = 0.0

    def __post_init__(self):
        if self.phoneme_energy is None:
            self.phoneme_energy = [0.0] * 44
        if self.topic_embedding is None:
            self.topic_embedding = [0.0] * 64
        if self.ontology_probs is None:
            self.ontology_probs = [0.0] * 12

    def to_vector(self) -> List[float]:
        """Convert to 124-dimensional vector."""
        return (
            self.phoneme_energy +
            self.topic_embedding +
            self.ontology_probs +
            [self.coherence, self.entropy, self.confidence, self.momentum]
        )

    @classmethod
    def from_vector(cls, vec: List[float]) -> "CognitiveState":
        """Create from 124-dimensional vector."""
        assert len(vec) == 124
        return cls(
            phoneme_energy=vec[0:44],
            topic_embedding=vec[44:108],
            ontology_probs=vec[108:120],
            coherence=vec[120],
            entropy=vec[121],
            confidence=vec[122],
            momentum=vec[123],
        )

    @property
    def dominant_layer(self) -> int:
        """Get index of most active ontology layer."""
        return max(range(12), key=lambda i: self.ontology_probs[i])


# Sovereign State layout (mistral_cg SovereignStateProjector): 12 + 5 + 5 + 6 + 4 = 32
SOVEREIGN_BHAVA_DIM = 12
SOVEREIGN_KOSHA_DIM = 5
SOVEREIGN_VRITTI_DIM = 5
SOVEREIGN_GUNA_DIM = 6
SOVEREIGN_RESERVED_DIM = 4
SOVEREIGN_TOTAL_DIM = (
    SOVEREIGN_BHAVA_DIM
    + SOVEREIGN_KOSHA_DIM
    + SOVEREIGN_VRITTI_DIM
    + SOVEREIGN_GUNA_DIM
    + SOVEREIGN_RESERVED_DIM
)


@dataclass
class SovereignState:
    """
    32-dimensional Sovereign State for mistral_cg.

    Layout matches ``symbolu_training`` SovereignStateProjector:
        bhava[12]    - softmax over 12 ontology Bhavas
        kosha[5]     - sigmoid / softmax over Pancha Kosha
        vritti[5]    - softmax over 5 Vritti modes
        guna[6]      - sigmoid over Guna components
        reserved[4]  - tanh (coherence, entropy, confidence, momentum surrogate)
    """
    bhava: List[float] = None
    kosha: List[float] = None
    vritti: List[float] = None
    guna: List[float] = None
    reserved: List[float] = None

    def __post_init__(self):
        if self.bhava is None:
            self.bhava = [0.0] * SOVEREIGN_BHAVA_DIM
        if self.kosha is None:
            self.kosha = [0.0] * SOVEREIGN_KOSHA_DIM
        if self.vritti is None:
            self.vritti = [0.0] * SOVEREIGN_VRITTI_DIM
        if self.guna is None:
            self.guna = [0.0] * SOVEREIGN_GUNA_DIM
        if self.reserved is None:
            self.reserved = [0.0] * SOVEREIGN_RESERVED_DIM
        for name, vec, dim in (
            ("bhava", self.bhava, SOVEREIGN_BHAVA_DIM),
            ("kosha", self.kosha, SOVEREIGN_KOSHA_DIM),
            ("vritti", self.vritti, SOVEREIGN_VRITTI_DIM),
            ("guna", self.guna, SOVEREIGN_GUNA_DIM),
            ("reserved", self.reserved, SOVEREIGN_RESERVED_DIM),
        ):
            if len(vec) != dim:
                raise ValueError(
                    f"SovereignState.{name} must have {dim} elements, got {len(vec)}"
                )

    def to_vector(self) -> List[float]:
        """Flatten to 32-D vector in canonical order."""
        return (
            list(self.bhava)
            + list(self.kosha)
            + list(self.vritti)
            + list(self.guna)
            + list(self.reserved)
        )

    @classmethod
    def from_vector(cls, vec: List[float]) -> "SovereignState":
        if len(vec) != SOVEREIGN_TOTAL_DIM:
            raise ValueError(
                f"SovereignState vector must be {SOVEREIGN_TOTAL_DIM}-D, got {len(vec)}"
            )
        b_end = SOVEREIGN_BHAVA_DIM
        k_end = b_end + SOVEREIGN_KOSHA_DIM
        v_end = k_end + SOVEREIGN_VRITTI_DIM
        g_end = v_end + SOVEREIGN_GUNA_DIM
        return cls(
            bhava=list(vec[0:b_end]),
            kosha=list(vec[b_end:k_end]),
            vritti=list(vec[k_end:v_end]),
            guna=list(vec[v_end:g_end]),
            reserved=list(vec[g_end:SOVEREIGN_TOTAL_DIM]),
        )

    @property
    def dominant_bhava(self) -> int:
        return max(range(SOVEREIGN_BHAVA_DIM), key=lambda i: self.bhava[i])

    @property
    def dominant_vritti(self) -> int:
        return max(range(SOVEREIGN_VRITTI_DIM), key=lambda i: self.vritti[i])
