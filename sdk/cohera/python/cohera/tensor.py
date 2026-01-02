"""
COHERA Tensor and Cognitive State
"""

from typing import List, Optional, Union
from dataclasses import dataclass
from enum import IntEnum


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
