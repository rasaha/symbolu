"""
Spatial-Causal Module (V10.11) for Phase-Quad LLM.

This module extends the Causal World Model (V10.10) with spatial reasoning
capabilities, enabling understanding of how spatial configurations cause
effects in the physical world.

Key Components:
    - Spatial State Tracking: Objects with position, orientation, scale
    - Physics-Grounded Causal Edges: Contact, gravity, collision, propagation
    - Spatial Intervention Operators: move, rotate, place, remove
    - Spatial Counterfactual Reasoning: "What if X was at position Y?"

Architecture:
    SpatialObject → SpatialWorld → SpatialRelationGraph
                          ↓
    PhysicsCausalEdge → PhysicsCausalLayer
                          ↓
    SpatialIntervention → SpatialInterventionModule
                          ↓
    SpatialCounterfactual → SpatialCounterfactualReasoner
                          ↓
    SpatialCausalPhaseQuadBlock (integrates with Phase-Quad)

Example Usage:
    >>> config = SpatialCausalConfig(hidden_dim=256, max_objects=64)
    >>> module = SpatialCausalModule(config)
    >>> spatial_state = module.encode_world(objects, relations)
    >>> counterfactual = module.spatial_counterfactual(
    ...     world=spatial_state,
    ...     intervention=MoveIntervention(obj_id="ball", new_position=[0, 1, 0])
    ... )

Version: 10.11
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class SpatialCausalConfig:
    """Configuration for Spatial-Causal Module."""

    # Core dimensions
    hidden_dim: int = 256
    num_heads: int = 8
    num_layers: int = 4

    # Spatial parameters
    max_objects: int = 64
    spatial_dim: int = 3  # 3D space
    position_encoding_dim: int = 64
    orientation_encoding_dim: int = 32

    # Physics parameters
    gravity: Tuple[float, float, float] = (0.0, -9.81, 0.0)
    simulation_dt: float = 0.01
    max_simulation_steps: int = 100

    # Relation parameters
    num_relation_types: int = 17  # Number of spatial relation types
    relation_threshold: float = 0.5
    max_relation_distance: float = 10.0

    # Physics causal parameters
    num_physics_types: int = 9  # Number of physics causal types
    propagation_radius: float = 2.0
    contact_threshold: float = 0.1

    # Intervention parameters
    intervention_hidden_dim: int = 128

    # Counterfactual parameters
    counterfactual_steps: int = 10
    abduction_hidden_dim: int = 128

    # Training parameters
    dropout: float = 0.1
    layer_norm_eps: float = 1e-6

    # Integration with Phase-Quad
    phase_dim: int = 64
    integrate_with_causal_world_model: bool = True


# =============================================================================
# ENUMERATIONS
# =============================================================================


class SpatialRelation(Enum):
    """Types of spatial relations between objects."""

    ABOVE = "above"
    BELOW = "below"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    IN_FRONT_OF = "in_front_of"
    BEHIND = "behind"
    INSIDE = "inside"
    OUTSIDE = "outside"
    ON = "on"
    UNDER = "under"
    NEAR = "near"
    FAR = "far"
    TOUCHING = "touching"
    CONTAINS = "contains"
    SUPPORTED_BY = "supported_by"
    ALIGNED_WITH = "aligned_with"
    BLOCKS = "blocks"


class PhysicsCausalType(Enum):
    """Types of physics-based causation."""

    CONTACT = "contact"  # A touches B → force transfer
    GRAVITY = "gravity"  # unsupported object → falls
    COLLISION = "collision"  # paths intersect → impact
    PROPAGATION = "propagation"  # effect spreads through space
    CONTAINMENT = "containment"  # A inside B → constrained by B
    OCCLUSION = "occlusion"  # A blocks B from C
    SUPPORT = "support"  # A supports B → B doesn't fall
    FRICTION = "friction"  # surface contact → resistance
    ELASTICITY = "elasticity"  # collision → bounce


class InterventionType(Enum):
    """Types of spatial interventions."""

    MOVE = "move"
    ROTATE = "rotate"
    PLACE = "place"
    REMOVE = "remove"
    RESIZE = "resize"
    CONNECT = "connect"
    APPLY_FORCE = "apply_force"


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class SpatialObject:
    """Represents an object in 3D space with full geometric state."""

    id: str
    position: torch.Tensor  # [x, y, z]
    orientation: torch.Tensor  # [qw, qx, qy, qz] quaternion
    scale: torch.Tensor  # [sx, sy, sz]
    velocity: torch.Tensor  # [vx, vy, vz]
    angular_velocity: torch.Tensor  # [wx, wy, wz]
    mass: float = 1.0
    is_static: bool = False
    bbox: Optional[torch.Tensor] = None  # [min_x, min_y, min_z, max_x, max_y, max_z]
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[torch.Tensor] = None  # learned embedding

    def clone(self) -> "SpatialObject":
        """Create a deep copy of this object."""
        return SpatialObject(
            id=self.id,
            position=self.position.clone(),
            orientation=self.orientation.clone(),
            scale=self.scale.clone(),
            velocity=self.velocity.clone(),
            angular_velocity=self.angular_velocity.clone(),
            mass=self.mass,
            is_static=self.is_static,
            bbox=self.bbox.clone() if self.bbox is not None else None,
            properties=dict(self.properties),
            embedding=self.embedding.clone() if self.embedding is not None else None,
        )

    def get_world_bbox(self) -> torch.Tensor:
        """Get axis-aligned bounding box in world coordinates."""
        if self.bbox is None:
            # Default unit cube centered at position
            half_scale = self.scale / 2
            return torch.cat(
                [self.position - half_scale, self.position + half_scale]
            )
        # Transform bbox by position and scale
        local_min = self.bbox[:3] * self.scale
        local_max = self.bbox[3:] * self.scale
        return torch.cat(
            [self.position + local_min, self.position + local_max]
        )


@dataclass
class SpatialRelationEdge:
    """Edge in the spatial relation graph."""

    source_id: str
    target_id: str
    relation: SpatialRelation
    confidence: float = 1.0
    distance: Optional[float] = None
    direction: Optional[torch.Tensor] = None  # unit vector from source to target


@dataclass
class PhysicsCausalEdge:
    """Causal edge grounded in physics."""

    source_id: str
    target_id: str
    physics_type: PhysicsCausalType
    strength: float = 1.0  # causal strength [0, 1]
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpatialWorld:
    """Container for all spatial objects and their relationships."""

    objects: Dict[str, SpatialObject] = field(default_factory=dict)
    relation_edges: List[SpatialRelationEdge] = field(default_factory=list)
    causal_edges: List[PhysicsCausalEdge] = field(default_factory=list)
    bounds: Optional[torch.Tensor] = None  # [min_x, min_y, min_z, max_x, max_y, max_z]
    gravity: torch.Tensor = field(
        default_factory=lambda: torch.tensor([0.0, -9.81, 0.0])
    )
    time: float = 0.0

    def clone(self) -> "SpatialWorld":
        """Create a deep copy of this world."""
        return SpatialWorld(
            objects={k: v.clone() for k, v in self.objects.items()},
            relation_edges=[
                SpatialRelationEdge(
                    source_id=e.source_id,
                    target_id=e.target_id,
                    relation=e.relation,
                    confidence=e.confidence,
                    distance=e.distance,
                    direction=e.direction.clone() if e.direction is not None else None,
                )
                for e in self.relation_edges
            ],
            causal_edges=[
                PhysicsCausalEdge(
                    source_id=e.source_id,
                    target_id=e.target_id,
                    physics_type=e.physics_type,
                    strength=e.strength,
                    is_active=e.is_active,
                    metadata=dict(e.metadata),
                )
                for e in self.causal_edges
            ],
            bounds=self.bounds.clone() if self.bounds is not None else None,
            gravity=self.gravity.clone(),
            time=self.time,
        )

    def add_object(self, obj: SpatialObject) -> None:
        """Add an object to the world."""
        self.objects[obj.id] = obj

    def remove_object(self, obj_id: str) -> Optional[SpatialObject]:
        """Remove an object from the world."""
        if obj_id in self.objects:
            obj = self.objects.pop(obj_id)
            # Remove associated edges
            self.relation_edges = [
                e
                for e in self.relation_edges
                if e.source_id != obj_id and e.target_id != obj_id
            ]
            self.causal_edges = [
                e
                for e in self.causal_edges
                if e.source_id != obj_id and e.target_id != obj_id
            ]
            return obj
        return None

    def get_relations(
        self, obj_id: str, relation_type: Optional[SpatialRelation] = None
    ) -> List[SpatialRelationEdge]:
        """Get all relations involving an object."""
        edges = [
            e
            for e in self.relation_edges
            if e.source_id == obj_id or e.target_id == obj_id
        ]
        if relation_type is not None:
            edges = [e for e in edges if e.relation == relation_type]
        return edges


@dataclass
class SpatialIntervention:
    """Represents a spatial intervention."""

    intervention_type: InterventionType
    obj_id: str
    value: Optional[torch.Tensor] = None  # new position, rotation, scale, force
    reference_id: Optional[str] = None  # for PLACE intervention
    relation: Optional[SpatialRelation] = None  # for PLACE intervention


@dataclass
class SpatialCausalState:
    """State output from spatial-causal reasoning."""

    spatial_world: SpatialWorld
    causal_graph_embedding: torch.Tensor
    spatial_embedding: torch.Tensor
    relation_matrix: torch.Tensor  # [num_objects, num_objects, num_relations]
    physics_causal_matrix: torch.Tensor  # [num_objects, num_objects, num_physics_types]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def quaternion_multiply(q1: torch.Tensor, q2: torch.Tensor) -> torch.Tensor:
    """Multiply two quaternions. q = [w, x, y, z]."""
    w1, x1, y1, z1 = q1[..., 0], q1[..., 1], q1[..., 2], q1[..., 3]
    w2, x2, y2, z2 = q2[..., 0], q2[..., 1], q2[..., 2], q2[..., 3]

    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2

    return torch.stack([w, x, y, z], dim=-1)


def quaternion_to_rotation_matrix(q: torch.Tensor) -> torch.Tensor:
    """Convert quaternion to 3x3 rotation matrix."""
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]

    # Normalize quaternion
    norm = torch.sqrt(w * w + x * x + y * y + z * z + 1e-8)
    w, x, y, z = w / norm, x / norm, y / norm, z / norm

    # Build rotation matrix
    r00 = 1 - 2 * (y * y + z * z)
    r01 = 2 * (x * y - z * w)
    r02 = 2 * (x * z + y * w)
    r10 = 2 * (x * y + z * w)
    r11 = 1 - 2 * (x * x + z * z)
    r12 = 2 * (y * z - x * w)
    r20 = 2 * (x * z - y * w)
    r21 = 2 * (y * z + x * w)
    r22 = 1 - 2 * (x * x + y * y)

    return torch.stack(
        [
            torch.stack([r00, r01, r02], dim=-1),
            torch.stack([r10, r11, r12], dim=-1),
            torch.stack([r20, r21, r22], dim=-1),
        ],
        dim=-2,
    )


def euler_to_quaternion(euler: torch.Tensor) -> torch.Tensor:
    """Convert Euler angles (roll, pitch, yaw) to quaternion."""
    roll, pitch, yaw = euler[..., 0], euler[..., 1], euler[..., 2]

    cy = torch.cos(yaw * 0.5)
    sy = torch.sin(yaw * 0.5)
    cp = torch.cos(pitch * 0.5)
    sp = torch.sin(pitch * 0.5)
    cr = torch.cos(roll * 0.5)
    sr = torch.sin(roll * 0.5)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy

    return torch.stack([w, x, y, z], dim=-1)


def compute_distance(pos1: torch.Tensor, pos2: torch.Tensor) -> torch.Tensor:
    """Compute Euclidean distance between two positions."""
    return torch.norm(pos1 - pos2, dim=-1)


def compute_direction(pos1: torch.Tensor, pos2: torch.Tensor) -> torch.Tensor:
    """Compute unit direction vector from pos1 to pos2."""
    diff = pos2 - pos1
    norm = torch.norm(diff, dim=-1, keepdim=True) + 1e-8
    return diff / norm


def check_bbox_overlap(bbox1: torch.Tensor, bbox2: torch.Tensor) -> bool:
    """Check if two axis-aligned bounding boxes overlap."""
    # bbox format: [min_x, min_y, min_z, max_x, max_y, max_z]
    min1, max1 = bbox1[:3], bbox1[3:]
    min2, max2 = bbox2[:3], bbox2[3:]

    # Check overlap in all three dimensions
    overlap_x = (min1[0] <= max2[0]) and (max1[0] >= min2[0])
    overlap_y = (min1[1] <= max2[1]) and (max1[1] >= min2[1])
    overlap_z = (min1[2] <= max2[2]) and (max1[2] >= min2[2])

    return overlap_x and overlap_y and overlap_z


# =============================================================================
# SPATIAL ENCODING
# =============================================================================


class PositionalEncoding3D(nn.Module):
    """3D positional encoding for spatial coordinates."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config
        self.encoding_dim = config.position_encoding_dim

        # Learnable frequency bands
        self.freq_bands = nn.Parameter(
            torch.linspace(1.0, 100.0, self.encoding_dim // 6)
        )

        # Projection to hidden dim
        self.proj = nn.Linear(self.encoding_dim, config.hidden_dim)

    def forward(self, positions: torch.Tensor) -> torch.Tensor:
        """
        Encode 3D positions.

        Args:
            positions: [batch, num_objects, 3] or [num_objects, 3]

        Returns:
            Positional embeddings [batch, num_objects, hidden_dim]
        """
        # Ensure 3D input
        if positions.dim() == 2:
            positions = positions.unsqueeze(0)

        batch_size, num_objects, _ = positions.shape

        # Apply frequency encoding to each dimension
        encodings = []
        for dim in range(3):
            pos_dim = positions[..., dim : dim + 1]  # [batch, num_objects, 1]
            # Sinusoidal encoding
            sin_enc = torch.sin(pos_dim * self.freq_bands)
            cos_enc = torch.cos(pos_dim * self.freq_bands)
            encodings.extend([sin_enc, cos_enc])

        # Concatenate all encodings
        encoding = torch.cat(encodings, dim=-1)  # [batch, num_objects, encoding_dim]

        # Project to hidden dim
        return self.proj(encoding)


class OrientationEncoding(nn.Module):
    """Encoding for quaternion orientations."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # MLP to encode quaternion
        self.mlp = nn.Sequential(
            nn.Linear(4, config.orientation_encoding_dim),
            nn.ReLU(),
            nn.Linear(config.orientation_encoding_dim, config.hidden_dim),
        )

    def forward(self, orientations: torch.Tensor) -> torch.Tensor:
        """
        Encode quaternion orientations.

        Args:
            orientations: [batch, num_objects, 4] quaternions

        Returns:
            Orientation embeddings [batch, num_objects, hidden_dim]
        """
        if orientations.dim() == 2:
            orientations = orientations.unsqueeze(0)

        return self.mlp(orientations)


class SpatialStateEncoder(nn.Module):
    """Encodes spatial state of objects into embeddings."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # Position encoding
        self.position_encoder = PositionalEncoding3D(config)

        # Orientation encoding
        self.orientation_encoder = OrientationEncoding(config)

        # Velocity encoding (reuse position encoder structure)
        self.velocity_encoder = nn.Linear(3, config.hidden_dim)

        # Scale encoding
        self.scale_encoder = nn.Linear(3, config.hidden_dim)

        # Property encoder (for categorical properties)
        self.property_encoder = nn.Linear(32, config.hidden_dim)  # 32-dim property vec

        # Fusion layer
        self.fusion = nn.Sequential(
            nn.Linear(config.hidden_dim * 5, config.hidden_dim * 2),
            nn.LayerNorm(config.hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim * 2, config.hidden_dim),
        )

    def forward(
        self,
        positions: torch.Tensor,
        orientations: torch.Tensor,
        velocities: torch.Tensor,
        scales: torch.Tensor,
        properties: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Encode spatial state.

        Args:
            positions: [batch, num_objects, 3]
            orientations: [batch, num_objects, 4]
            velocities: [batch, num_objects, 3]
            scales: [batch, num_objects, 3]
            properties: [batch, num_objects, 32] optional

        Returns:
            Spatial embeddings [batch, num_objects, hidden_dim]
        """
        pos_enc = self.position_encoder(positions)
        orient_enc = self.orientation_encoder(orientations)
        vel_enc = self.velocity_encoder(velocities)
        scale_enc = self.scale_encoder(scales)

        if properties is not None:
            prop_enc = self.property_encoder(properties)
        else:
            prop_enc = torch.zeros_like(pos_enc)

        # Concatenate and fuse
        combined = torch.cat(
            [pos_enc, orient_enc, vel_enc, scale_enc, prop_enc], dim=-1
        )
        return self.fusion(combined)

    def encode_world(self, world: SpatialWorld) -> torch.Tensor:
        """Encode a SpatialWorld into embeddings."""
        if not world.objects:
            return torch.zeros(1, 0, self.config.hidden_dim)

        objects = list(world.objects.values())
        num_objects = len(objects)

        # Stack object properties
        positions = torch.stack([obj.position for obj in objects]).unsqueeze(0)
        orientations = torch.stack([obj.orientation for obj in objects]).unsqueeze(0)
        velocities = torch.stack([obj.velocity for obj in objects]).unsqueeze(0)
        scales = torch.stack([obj.scale for obj in objects]).unsqueeze(0)

        return self.forward(positions, orientations, velocities, scales)


# =============================================================================
# SPATIAL RELATION PREDICTION
# =============================================================================


class SpatialRelationPredictor(nn.Module):
    """Predicts spatial relations between objects."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config
        self.num_relations = config.num_relation_types

        # Pairwise feature extractor
        self.pair_encoder = nn.Sequential(
            nn.Linear(config.hidden_dim * 2 + 7, config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.hidden_dim),
        )

        # Relation classifier
        self.relation_classifier = nn.Linear(config.hidden_dim, self.num_relations)

        # Distance regressor
        self.distance_regressor = nn.Linear(config.hidden_dim, 1)

    def forward(
        self,
        object_embeddings: torch.Tensor,
        positions: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predict spatial relations between all pairs of objects.

        Args:
            object_embeddings: [batch, num_objects, hidden_dim]
            positions: [batch, num_objects, 3]

        Returns:
            relation_logits: [batch, num_objects, num_objects, num_relations]
            distances: [batch, num_objects, num_objects]
        """
        batch_size, num_objects, hidden_dim = object_embeddings.shape

        # Compute pairwise features
        # Expand for pairwise computation
        emb_i = object_embeddings.unsqueeze(2).expand(-1, -1, num_objects, -1)
        emb_j = object_embeddings.unsqueeze(1).expand(-1, num_objects, -1, -1)

        pos_i = positions.unsqueeze(2).expand(-1, -1, num_objects, -1)
        pos_j = positions.unsqueeze(1).expand(-1, num_objects, -1, -1)

        # Relative position features
        rel_pos = pos_j - pos_i  # [batch, n, n, 3]
        distance = torch.norm(rel_pos, dim=-1, keepdim=True)  # [batch, n, n, 1]
        direction = rel_pos / (distance + 1e-8)  # [batch, n, n, 3]

        # Concatenate pairwise features
        pair_features = torch.cat(
            [emb_i, emb_j, rel_pos, direction, distance], dim=-1
        )  # [batch, n, n, hidden*2 + 7]

        # Encode pairs
        pair_encoded = self.pair_encoder(pair_features)

        # Predict relations
        relation_logits = self.relation_classifier(pair_encoded)

        # Predict distances
        distances = self.distance_regressor(pair_encoded).squeeze(-1)

        return relation_logits, distances

    def compute_relations(
        self, world: SpatialWorld, threshold: float = 0.5
    ) -> List[SpatialRelationEdge]:
        """
        Compute spatial relations for a world using geometric rules.

        Args:
            world: SpatialWorld to analyze
            threshold: confidence threshold for relations

        Returns:
            List of SpatialRelationEdge
        """
        edges = []
        objects = list(world.objects.values())

        for i, obj_i in enumerate(objects):
            for j, obj_j in enumerate(objects):
                if i == j:
                    continue

                pos_i = obj_i.position
                pos_j = obj_j.position
                diff = pos_j - pos_i
                distance = torch.norm(diff).item()
                direction = diff / (distance + 1e-8)

                # Compute various spatial relations

                # ABOVE/BELOW
                if diff[1].item() > obj_i.scale[1].item() * 0.5:
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.ABOVE,
                            confidence=min(1.0, abs(diff[1].item()) / 2.0),
                            distance=distance,
                            direction=direction,
                        )
                    )
                elif diff[1].item() < -obj_i.scale[1].item() * 0.5:
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.BELOW,
                            confidence=min(1.0, abs(diff[1].item()) / 2.0),
                            distance=distance,
                            direction=direction,
                        )
                    )

                # LEFT_OF/RIGHT_OF
                if diff[0].item() > obj_i.scale[0].item() * 0.5:
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.RIGHT_OF,
                            confidence=min(1.0, abs(diff[0].item()) / 2.0),
                            distance=distance,
                            direction=direction,
                        )
                    )
                elif diff[0].item() < -obj_i.scale[0].item() * 0.5:
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.LEFT_OF,
                            confidence=min(1.0, abs(diff[0].item()) / 2.0),
                            distance=distance,
                            direction=direction,
                        )
                    )

                # NEAR/FAR
                if distance < self.config.max_relation_distance * 0.3:
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.NEAR,
                            confidence=1.0 - distance / (self.config.max_relation_distance * 0.3),
                            distance=distance,
                            direction=direction,
                        )
                    )
                elif distance > self.config.max_relation_distance * 0.7:
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.FAR,
                            confidence=min(1.0, distance / self.config.max_relation_distance),
                            distance=distance,
                            direction=direction,
                        )
                    )

                # TOUCHING (bbox overlap or very close)
                if distance < self.config.contact_threshold:
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.TOUCHING,
                            confidence=1.0,
                            distance=distance,
                            direction=direction,
                        )
                    )

                # ON (object i is on top of object j)
                if (
                    diff[1].item() > 0
                    and diff[1].item() < obj_j.scale[1].item()
                    and abs(diff[0].item()) < obj_j.scale[0].item() * 0.5
                    and abs(diff[2].item()) < obj_j.scale[2].item() * 0.5
                ):
                    edges.append(
                        SpatialRelationEdge(
                            source_id=obj_i.id,
                            target_id=obj_j.id,
                            relation=SpatialRelation.ON,
                            confidence=0.9,
                            distance=distance,
                            direction=direction,
                        )
                    )

        return edges


# =============================================================================
# PHYSICS-GROUNDED CAUSAL LAYER
# =============================================================================


class PhysicsCausalRule:
    """A rule that determines when a physics-based causal edge is active."""

    def __init__(
        self,
        physics_type: PhysicsCausalType,
        condition: Callable[[SpatialObject, SpatialObject, SpatialWorld], bool],
        effect: Callable[[SpatialObject, SpatialObject, SpatialWorld, float], None],
        strength: float = 1.0,
    ):
        self.physics_type = physics_type
        self.condition = condition
        self.effect = effect
        self.strength = strength


class PhysicsCausalLayer(nn.Module):
    """Layer that computes physics-grounded causal edges."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # Learnable physics parameters
        self.gravity_strength = nn.Parameter(torch.tensor(1.0))
        self.contact_strength = nn.Parameter(torch.tensor(1.0))
        self.propagation_decay = nn.Parameter(torch.tensor(0.5))

        # Neural edge predictor for learned physics
        self.edge_predictor = nn.Sequential(
            nn.Linear(config.hidden_dim * 2 + 10, config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.num_physics_types),
        )

        # Edge strength predictor
        self.strength_predictor = nn.Sequential(
            nn.Linear(config.hidden_dim * 2 + 10, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

        # Define physics rules
        self.rules = self._create_physics_rules()

    def _create_physics_rules(self) -> List[PhysicsCausalRule]:
        """Create the set of physics-based causal rules."""
        rules = []

        # Gravity rule: unsupported objects fall
        rules.append(
            PhysicsCausalRule(
                physics_type=PhysicsCausalType.GRAVITY,
                condition=lambda obj, _, world: not obj.is_static and not self._is_supported(obj, world),
                effect=lambda obj, _, world, dt: self._apply_gravity(obj, world, dt),
                strength=1.0,
            )
        )

        # Contact rule: touching objects transfer force
        rules.append(
            PhysicsCausalRule(
                physics_type=PhysicsCausalType.CONTACT,
                condition=lambda obj1, obj2, world: self._are_touching(obj1, obj2),
                effect=lambda obj1, obj2, world, dt: self._apply_contact(obj1, obj2, dt),
                strength=0.8,
            )
        )

        # Support rule: object on surface is supported
        rules.append(
            PhysicsCausalRule(
                physics_type=PhysicsCausalType.SUPPORT,
                condition=lambda obj1, obj2, world: self._is_on(obj1, obj2),
                effect=lambda obj1, obj2, world, dt: self._apply_support(obj1, obj2),
                strength=1.0,
            )
        )

        # Collision rule: objects with intersecting paths collide
        rules.append(
            PhysicsCausalRule(
                physics_type=PhysicsCausalType.COLLISION,
                condition=lambda obj1, obj2, world: self._will_collide(obj1, obj2, self.config.simulation_dt),
                effect=lambda obj1, obj2, world, dt: self._apply_collision(obj1, obj2),
                strength=1.0,
            )
        )

        # Propagation rule: effects spread to nearby objects
        rules.append(
            PhysicsCausalRule(
                physics_type=PhysicsCausalType.PROPAGATION,
                condition=lambda obj1, obj2, world: (
                    obj1.properties.get("propagates", False)
                    and compute_distance(obj1.position, obj2.position).item()
                    < self.config.propagation_radius
                ),
                effect=lambda obj1, obj2, world, dt: self._apply_propagation(obj1, obj2),
                strength=0.6,
            )
        )

        return rules

    def _is_supported(self, obj: SpatialObject, world: SpatialWorld) -> bool:
        """Check if object is supported by another object or ground."""
        if obj.position[1].item() <= 0:  # On ground
            return True
        for other in world.objects.values():
            if other.id != obj.id and self._is_on(obj, other):
                return True
        return False

    def _are_touching(self, obj1: SpatialObject, obj2: SpatialObject) -> bool:
        """Check if two objects are touching."""
        distance = compute_distance(obj1.position, obj2.position).item()
        combined_radius = (obj1.scale.max().item() + obj2.scale.max().item()) / 2
        return distance < combined_radius + self.config.contact_threshold

    def _is_on(self, obj1: SpatialObject, obj2: SpatialObject) -> bool:
        """Check if obj1 is on top of obj2."""
        diff = obj1.position - obj2.position
        # obj1 is above obj2
        if diff[1].item() <= 0:
            return False
        # obj1 is within horizontal bounds of obj2
        horizontal_dist = torch.sqrt(diff[0] ** 2 + diff[2] ** 2).item()
        return horizontal_dist < obj2.scale.max().item() * 0.5

    def _will_collide(
        self, obj1: SpatialObject, obj2: SpatialObject, dt: float
    ) -> bool:
        """Check if objects will collide in the next timestep."""
        if obj1.is_static and obj2.is_static:
            return False

        # Predict next positions
        next_pos1 = obj1.position + obj1.velocity * dt
        next_pos2 = obj2.position + obj2.velocity * dt

        # Check if they'll be touching
        distance = compute_distance(next_pos1, next_pos2).item()
        combined_radius = (obj1.scale.max().item() + obj2.scale.max().item()) / 2
        return distance < combined_radius

    def _apply_gravity(
        self, obj: SpatialObject, world: SpatialWorld, dt: float
    ) -> None:
        """Apply gravity to an object."""
        obj.velocity = obj.velocity + world.gravity * self.gravity_strength * dt

    def _apply_contact(
        self, obj1: SpatialObject, obj2: SpatialObject, dt: float
    ) -> None:
        """Apply contact force between objects."""
        if obj1.is_static or obj2.is_static:
            return

        # Simple elastic collision response
        direction = compute_direction(obj1.position, obj2.position)
        relative_vel = obj1.velocity - obj2.velocity
        impact = torch.dot(relative_vel, direction)

        if impact > 0:  # Objects approaching
            restitution = 0.8  # Bounce coefficient
            impulse = direction * impact * (1 + restitution) * self.contact_strength

            m1, m2 = obj1.mass, obj2.mass
            obj1.velocity = obj1.velocity - impulse * (m2 / (m1 + m2))
            obj2.velocity = obj2.velocity + impulse * (m1 / (m1 + m2))

    def _apply_support(self, obj1: SpatialObject, obj2: SpatialObject) -> None:
        """Apply support constraint - obj1 is supported by obj2."""
        # Zero out downward velocity
        if obj1.velocity[1].item() < 0:
            obj1.velocity[1] = 0.0

    def _apply_collision(self, obj1: SpatialObject, obj2: SpatialObject) -> None:
        """Apply collision response."""
        self._apply_contact(obj1, obj2, self.config.simulation_dt)

    def _apply_propagation(self, source: SpatialObject, target: SpatialObject) -> None:
        """Propagate effect from source to target."""
        for key, value in source.properties.items():
            if key.startswith("propagate_"):
                prop_name = key[10:]  # Remove "propagate_" prefix
                if prop_name not in target.properties:
                    target.properties[prop_name] = value * self.propagation_decay.item()

    def forward(
        self,
        object_embeddings: torch.Tensor,
        positions: torch.Tensor,
        velocities: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predict physics-causal edges between objects.

        Args:
            object_embeddings: [batch, num_objects, hidden_dim]
            positions: [batch, num_objects, 3]
            velocities: [batch, num_objects, 3]

        Returns:
            edge_logits: [batch, num_objects, num_objects, num_physics_types]
            edge_strengths: [batch, num_objects, num_objects]
        """
        batch_size, num_objects, hidden_dim = object_embeddings.shape

        # Pairwise features
        emb_i = object_embeddings.unsqueeze(2).expand(-1, -1, num_objects, -1)
        emb_j = object_embeddings.unsqueeze(1).expand(-1, num_objects, -1, -1)

        pos_i = positions.unsqueeze(2).expand(-1, -1, num_objects, -1)
        pos_j = positions.unsqueeze(1).expand(-1, num_objects, -1, -1)

        vel_i = velocities.unsqueeze(2).expand(-1, -1, num_objects, -1)
        vel_j = velocities.unsqueeze(1).expand(-1, num_objects, -1, -1)

        # Compute relative features
        rel_pos = pos_j - pos_i
        rel_vel = vel_j - vel_i
        distance = torch.norm(rel_pos, dim=-1, keepdim=True)

        # Concatenate features
        pair_features = torch.cat(
            [emb_i, emb_j, rel_pos, rel_vel, distance], dim=-1
        )

        # Predict edge types and strengths
        edge_logits = self.edge_predictor(pair_features)
        edge_strengths = self.strength_predictor(pair_features).squeeze(-1)

        return edge_logits, edge_strengths

    def compute_causal_edges(
        self, world: SpatialWorld
    ) -> List[PhysicsCausalEdge]:
        """
        Compute physics-causal edges for a world using rules.

        Args:
            world: SpatialWorld to analyze

        Returns:
            List of PhysicsCausalEdge
        """
        edges = []
        objects = list(world.objects.values())

        for rule in self.rules:
            for obj1 in objects:
                for obj2 in objects:
                    if obj1.id == obj2.id:
                        continue

                    if rule.condition(obj1, obj2, world):
                        edges.append(
                            PhysicsCausalEdge(
                                source_id=obj1.id,
                                target_id=obj2.id,
                                physics_type=rule.physics_type,
                                strength=rule.strength,
                                is_active=True,
                            )
                        )

        return edges


# =============================================================================
# SPATIAL INTERVENTION MODULE
# =============================================================================


class SpatialInterventionModule(nn.Module):
    """Module for applying spatial interventions (do-calculus with spatial operations)."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # Intervention encoder
        self.intervention_encoder = nn.Sequential(
            nn.Linear(config.hidden_dim + 10, config.intervention_hidden_dim),
            nn.ReLU(),
            nn.Linear(config.intervention_hidden_dim, config.hidden_dim),
        )

        # Effect predictor
        self.effect_predictor = nn.Sequential(
            nn.Linear(config.hidden_dim * 2, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
        )

    def do_move(
        self,
        world: SpatialWorld,
        obj_id: str,
        new_position: torch.Tensor,
    ) -> SpatialWorld:
        """
        Apply move intervention: do(position(X) = new_position).

        Surgically sets object position, breaking incoming position-related
        causal edges, then propagates effects.
        """
        new_world = world.clone()

        if obj_id not in new_world.objects:
            return new_world

        obj = new_world.objects[obj_id]
        old_position = obj.position.clone()

        # Set new position
        obj.position = new_position.clone()

        # Update bounding box
        if obj.bbox is not None:
            # Recompute world bbox
            pass  # bbox is recomputed on demand

        # Remove incoming causal edges that depend on position
        new_world.causal_edges = [
            edge
            for edge in new_world.causal_edges
            if not (
                edge.target_id == obj_id
                and edge.physics_type
                in [PhysicsCausalType.COLLISION, PhysicsCausalType.CONTACT]
            )
        ]

        return new_world

    def do_rotate(
        self,
        world: SpatialWorld,
        obj_id: str,
        rotation: torch.Tensor,
    ) -> SpatialWorld:
        """
        Apply rotation intervention: do(orientation(X) = rotation).

        Rotates object and updates orientation-dependent relations.
        """
        new_world = world.clone()

        if obj_id not in new_world.objects:
            return new_world

        obj = new_world.objects[obj_id]

        # Apply rotation (multiply quaternions)
        obj.orientation = quaternion_multiply(obj.orientation, rotation)

        return new_world

    def do_place(
        self,
        world: SpatialWorld,
        obj_id: str,
        reference_id: str,
        relation: SpatialRelation,
    ) -> SpatialWorld:
        """
        Apply place intervention: do(place(X, relative_to=Y, relation=R)).

        Places object X in specified spatial relation to Y.
        """
        new_world = world.clone()

        if obj_id not in new_world.objects or reference_id not in new_world.objects:
            return new_world

        obj = new_world.objects[obj_id]
        reference = new_world.objects[reference_id]

        # Compute target position based on relation
        target_position = self._compute_relation_position(obj, reference, relation)

        # Apply move intervention
        return self.do_move(new_world, obj_id, target_position)

    def do_remove(self, world: SpatialWorld, obj_id: str) -> SpatialWorld:
        """
        Apply remove intervention: do(remove(X)).

        Removes object from the world.
        """
        new_world = world.clone()
        new_world.remove_object(obj_id)
        return new_world

    def do_apply_force(
        self,
        world: SpatialWorld,
        obj_id: str,
        force: torch.Tensor,
        dt: float = 0.1,
    ) -> SpatialWorld:
        """
        Apply force intervention: do(apply_force(X, F)).

        Applies instantaneous force to object.
        """
        new_world = world.clone()

        if obj_id not in new_world.objects:
            return new_world

        obj = new_world.objects[obj_id]

        if not obj.is_static:
            # F = ma, so a = F/m, and Δv = a*dt
            acceleration = force / obj.mass
            obj.velocity = obj.velocity + acceleration * dt

        return new_world

    def _compute_relation_position(
        self,
        obj: SpatialObject,
        reference: SpatialObject,
        relation: SpatialRelation,
    ) -> torch.Tensor:
        """Compute position for obj to satisfy relation with reference."""
        ref_pos = reference.position
        ref_scale = reference.scale
        obj_scale = obj.scale

        offset = torch.zeros(3)

        if relation == SpatialRelation.ON:
            # Place on top of reference
            offset[1] = ref_scale[1] / 2 + obj_scale[1] / 2

        elif relation == SpatialRelation.ABOVE:
            offset[1] = ref_scale[1] + obj_scale[1]

        elif relation == SpatialRelation.BELOW:
            offset[1] = -(ref_scale[1] + obj_scale[1])

        elif relation == SpatialRelation.LEFT_OF:
            offset[0] = -(ref_scale[0] / 2 + obj_scale[0] / 2 + 0.1)

        elif relation == SpatialRelation.RIGHT_OF:
            offset[0] = ref_scale[0] / 2 + obj_scale[0] / 2 + 0.1

        elif relation == SpatialRelation.IN_FRONT_OF:
            offset[2] = ref_scale[2] / 2 + obj_scale[2] / 2 + 0.1

        elif relation == SpatialRelation.BEHIND:
            offset[2] = -(ref_scale[2] / 2 + obj_scale[2] / 2 + 0.1)

        elif relation == SpatialRelation.NEAR:
            # Place nearby (just offset slightly)
            offset[0] = ref_scale[0] + 0.5

        elif relation == SpatialRelation.INSIDE:
            # Place at center of reference
            pass  # offset stays zero

        return ref_pos + offset

    def apply_intervention(
        self, world: SpatialWorld, intervention: SpatialIntervention
    ) -> SpatialWorld:
        """Apply a spatial intervention to the world."""
        if intervention.intervention_type == InterventionType.MOVE:
            return self.do_move(world, intervention.obj_id, intervention.value)
        elif intervention.intervention_type == InterventionType.ROTATE:
            return self.do_rotate(world, intervention.obj_id, intervention.value)
        elif intervention.intervention_type == InterventionType.PLACE:
            return self.do_place(
                world,
                intervention.obj_id,
                intervention.reference_id,
                intervention.relation,
            )
        elif intervention.intervention_type == InterventionType.REMOVE:
            return self.do_remove(world, intervention.obj_id)
        elif intervention.intervention_type == InterventionType.APPLY_FORCE:
            return self.do_apply_force(world, intervention.obj_id, intervention.value)
        else:
            return world


# =============================================================================
# PHYSICS SIMULATOR
# =============================================================================


class PhysicsSimulator(nn.Module):
    """Simulates physics forward in time."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config
        self.physics_causal_layer = PhysicsCausalLayer(config)

    def step(self, world: SpatialWorld, dt: Optional[float] = None) -> SpatialWorld:
        """
        Advance world state by one timestep.

        Args:
            world: Current world state
            dt: Timestep (uses config default if not provided)

        Returns:
            New world state after physics step
        """
        if dt is None:
            dt = self.config.simulation_dt

        new_world = world.clone()
        new_world.time += dt

        # Get active physics rules and apply effects
        for rule in self.physics_causal_layer.rules:
            for obj1 in list(new_world.objects.values()):
                for obj2 in list(new_world.objects.values()):
                    if obj1.id == obj2.id:
                        continue
                    if rule.condition(obj1, obj2, new_world):
                        rule.effect(obj1, obj2, new_world, dt)

        # Apply gravity to all non-static objects
        for obj in new_world.objects.values():
            if not obj.is_static:
                if not self.physics_causal_layer._is_supported(obj, new_world):
                    obj.velocity = obj.velocity + new_world.gravity * dt

        # Update positions based on velocities
        for obj in new_world.objects.values():
            if not obj.is_static:
                obj.position = obj.position + obj.velocity * dt

                # Simple ground collision
                if obj.position[1].item() < obj.scale[1].item() / 2:
                    obj.position[1] = obj.scale[1] / 2
                    obj.velocity[1] = -obj.velocity[1] * 0.5  # Bounce

        return new_world

    def simulate(
        self,
        world: SpatialWorld,
        steps: Optional[int] = None,
        dt: Optional[float] = None,
    ) -> List[SpatialWorld]:
        """
        Simulate world forward for multiple steps.

        Args:
            world: Initial world state
            steps: Number of simulation steps
            dt: Timestep per step

        Returns:
            List of world states (trajectory)
        """
        if steps is None:
            steps = self.config.max_simulation_steps
        if dt is None:
            dt = self.config.simulation_dt

        trajectory = [world]
        current_world = world

        for _ in range(steps):
            current_world = self.step(current_world, dt)
            trajectory.append(current_world)

        return trajectory

    def predict_outcome(
        self,
        world: SpatialWorld,
        obj_id: str,
        steps: int = 10,
    ) -> Dict[str, Any]:
        """
        Predict outcome for a specific object.

        Returns:
            Dictionary with predicted final state and events
        """
        trajectory = self.simulate(world, steps)
        final_world = trajectory[-1]

        # Track events
        events = []
        for i in range(1, len(trajectory)):
            prev_world = trajectory[i - 1]
            curr_world = trajectory[i]

            if obj_id in curr_world.objects and obj_id in prev_world.objects:
                obj_prev = prev_world.objects[obj_id]
                obj_curr = curr_world.objects[obj_id]

                # Check for significant position change
                pos_change = torch.norm(obj_curr.position - obj_prev.position).item()
                if pos_change > 0.5:
                    events.append({"step": i, "type": "moved", "distance": pos_change})

                # Check for ground contact
                if (
                    obj_prev.position[1].item() > obj_prev.scale[1].item() / 2 + 0.1
                    and obj_curr.position[1].item()
                    <= obj_curr.scale[1].item() / 2 + 0.1
                ):
                    events.append({"step": i, "type": "hit_ground"})

        result = {
            "final_position": (
                final_world.objects[obj_id].position
                if obj_id in final_world.objects
                else None
            ),
            "final_velocity": (
                final_world.objects[obj_id].velocity
                if obj_id in final_world.objects
                else None
            ),
            "events": events,
            "trajectory_length": len(trajectory),
        }

        return result


# =============================================================================
# SPATIAL COUNTERFACTUAL REASONING
# =============================================================================


class SpatialAbductor(nn.Module):
    """Infers spatial configuration from observations."""

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # Observation encoder
        self.obs_encoder = nn.Sequential(
            nn.Linear(config.hidden_dim, config.abduction_hidden_dim),
            nn.ReLU(),
            nn.Linear(config.abduction_hidden_dim, config.abduction_hidden_dim),
        )

        # Position inference network
        self.position_inference = nn.Sequential(
            nn.Linear(config.abduction_hidden_dim + config.hidden_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, 3),  # x, y, z
        )

        # Velocity inference network
        self.velocity_inference = nn.Sequential(
            nn.Linear(config.abduction_hidden_dim + config.hidden_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, 3),  # vx, vy, vz
        )

    def forward(
        self,
        observation_embedding: torch.Tensor,
        object_embeddings: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Infer spatial state from observation.

        Args:
            observation_embedding: [batch, hidden_dim] encoded observation
            object_embeddings: [batch, num_objects, hidden_dim]

        Returns:
            inferred_positions: [batch, num_objects, 3]
            inferred_velocities: [batch, num_objects, 3]
        """
        batch_size, num_objects, _ = object_embeddings.shape

        # Encode observation
        obs_encoded = self.obs_encoder(observation_embedding)  # [batch, abd_hidden]

        # Expand observation for each object
        obs_expanded = obs_encoded.unsqueeze(1).expand(-1, num_objects, -1)

        # Concatenate with object embeddings
        combined = torch.cat([obs_expanded, object_embeddings], dim=-1)

        # Infer positions and velocities
        positions = self.position_inference(combined)
        velocities = self.velocity_inference(combined)

        return positions, velocities


class SpatialCounterfactualReasoner(nn.Module):
    """
    Reasons about spatial counterfactuals using three-step process:
    1. Abduction: Infer spatial configuration from observation
    2. Action: Apply spatial intervention
    3. Prediction: Simulate with modified spatial state
    """

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # Components
        self.abductor = SpatialAbductor(config)
        self.intervention_module = SpatialInterventionModule(config)
        self.simulator = PhysicsSimulator(config)

        # Outcome comparator
        self.outcome_comparator = nn.Sequential(
            nn.Linear(config.hidden_dim * 2, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, 1),
            nn.Sigmoid(),
        )

    def reason(
        self,
        world: SpatialWorld,
        intervention: SpatialIntervention,
        observation_embedding: Optional[torch.Tensor] = None,
        steps: int = 10,
    ) -> Dict[str, Any]:
        """
        Perform spatial counterfactual reasoning.

        Process:
            1. (Optional) Abduce: If observation provided, infer spatial state
            2. Intervene: Apply spatial intervention to create counterfactual world
            3. Predict: Simulate counterfactual world forward

        Args:
            world: Current/observed world state
            intervention: Spatial intervention to apply
            observation_embedding: Optional observation to abduce from
            steps: Simulation steps for prediction

        Returns:
            Dictionary containing:
                - factual_trajectory: Simulation of original world
                - counterfactual_trajectory: Simulation of intervened world
                - outcome_difference: Comparison of outcomes
        """
        # Step 1: Abduction (optional)
        # If we have an observation, we might update our world state
        # For now, we use the provided world state directly

        # Step 2: Intervention - create counterfactual world
        counterfactual_world = self.intervention_module.apply_intervention(
            world, intervention
        )

        # Step 3: Prediction - simulate both worlds
        factual_trajectory = self.simulator.simulate(world, steps)
        counterfactual_trajectory = self.simulator.simulate(counterfactual_world, steps)

        # Compare outcomes
        factual_final = factual_trajectory[-1]
        counterfactual_final = counterfactual_trajectory[-1]

        # Compute outcome differences for the intervened object
        obj_id = intervention.obj_id
        outcome_diff = {}

        if obj_id in factual_final.objects and obj_id in counterfactual_final.objects:
            fact_obj = factual_final.objects[obj_id]
            cf_obj = counterfactual_final.objects[obj_id]

            outcome_diff = {
                "position_diff": (cf_obj.position - fact_obj.position).tolist(),
                "velocity_diff": (cf_obj.velocity - fact_obj.velocity).tolist(),
                "position_distance": torch.norm(
                    cf_obj.position - fact_obj.position
                ).item(),
            }

        return {
            "factual_trajectory": factual_trajectory,
            "counterfactual_trajectory": counterfactual_trajectory,
            "factual_final": factual_final,
            "counterfactual_final": counterfactual_final,
            "outcome_difference": outcome_diff,
            "intervention": intervention,
        }

    def answer_counterfactual(
        self,
        world: SpatialWorld,
        question: str,
        intervention: SpatialIntervention,
    ) -> Dict[str, Any]:
        """
        Answer a spatial counterfactual question.

        Example:
            question: "Would the vase have broken if it was in the center?"
            intervention: do(position(vase) = center_of_table)

        Returns:
            Answer with reasoning trace
        """
        # Perform counterfactual reasoning
        result = self.reason(world, intervention)

        # Analyze outcome
        obj_id = intervention.obj_id

        factual_events = self.simulator.predict_outcome(world, obj_id)["events"]
        cf_events = self.simulator.predict_outcome(
            result["counterfactual_final"], obj_id
        )["events"]

        # Determine answer based on event differences
        factual_fell = any(e["type"] == "hit_ground" for e in factual_events)
        cf_fell = any(e["type"] == "hit_ground" for e in cf_events)

        answer = {
            "question": question,
            "intervention": str(intervention),
            "factual_outcome": factual_events,
            "counterfactual_outcome": cf_events,
            "factual_fell": factual_fell,
            "counterfactual_fell": cf_fell,
            "outcome_changed": factual_fell != cf_fell,
            "reasoning": self._generate_reasoning(
                intervention, factual_events, cf_events
            ),
        }

        return answer

    def _generate_reasoning(
        self,
        intervention: SpatialIntervention,
        factual_events: List[Dict],
        cf_events: List[Dict],
    ) -> str:
        """Generate human-readable reasoning for the counterfactual."""
        reasoning_parts = []

        reasoning_parts.append(
            f"Intervention: {intervention.intervention_type.value} "
            f"on object '{intervention.obj_id}'"
        )

        if intervention.value is not None:
            reasoning_parts.append(f"New value: {intervention.value.tolist()}")

        reasoning_parts.append(f"Factual events: {len(factual_events)}")
        reasoning_parts.append(f"Counterfactual events: {len(cf_events)}")

        factual_fell = any(e["type"] == "hit_ground" for e in factual_events)
        cf_fell = any(e["type"] == "hit_ground" for e in cf_events)

        if factual_fell and not cf_fell:
            reasoning_parts.append(
                "Conclusion: The intervention prevented the object from falling."
            )
        elif not factual_fell and cf_fell:
            reasoning_parts.append(
                "Conclusion: The intervention caused the object to fall."
            )
        elif factual_fell and cf_fell:
            reasoning_parts.append(
                "Conclusion: The object fell in both cases, "
                "intervention did not prevent falling."
            )
        else:
            reasoning_parts.append(
                "Conclusion: The object did not fall in either case."
            )

        return " | ".join(reasoning_parts)


# =============================================================================
# SPATIAL-CAUSAL PHASE-QUAD INTEGRATION
# =============================================================================


class SpatialCausalPhaseQuadBlock(nn.Module):
    """
    Phase-Quad block with spatial-causal reasoning.

    Integrates:
        - Phase-Quad attention (from base model)
        - Spatial state encoding
        - Physics-grounded causal edges
        - Spatial intervention capability
        - Spatial counterfactual reasoning
    """

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # Spatial encoding
        self.spatial_encoder = SpatialStateEncoder(config)

        # Spatial relation prediction
        self.relation_predictor = SpatialRelationPredictor(config)

        # Physics causal layer
        self.physics_causal_layer = PhysicsCausalLayer(config)

        # Spatial intervention module
        self.intervention_module = SpatialInterventionModule(config)

        # Spatial counterfactual reasoner
        self.counterfactual_reasoner = SpatialCounterfactualReasoner(config)

        # Physics simulator
        self.simulator = PhysicsSimulator(config)

        # Output projection
        self.output_proj = nn.Linear(config.hidden_dim * 2, config.hidden_dim)

        # Layer norm
        self.layer_norm = nn.LayerNorm(config.hidden_dim, eps=config.layer_norm_eps)

    def forward(
        self,
        hidden_states: torch.Tensor,
        positions: torch.Tensor,
        orientations: torch.Tensor,
        velocities: torch.Tensor,
        scales: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass with spatial-causal reasoning.

        Args:
            hidden_states: [batch, seq_len, hidden_dim] from previous layer
            positions: [batch, num_objects, 3]
            orientations: [batch, num_objects, 4]
            velocities: [batch, num_objects, 3]
            scales: [batch, num_objects, 3]
            attention_mask: Optional attention mask

        Returns:
            output: [batch, seq_len, hidden_dim]
            relation_logits: [batch, num_objects, num_objects, num_relations]
            physics_logits: [batch, num_objects, num_objects, num_physics_types]
        """
        # Encode spatial state
        spatial_embeddings = self.spatial_encoder(
            positions, orientations, velocities, scales
        )

        # Predict spatial relations
        relation_logits, distances = self.relation_predictor(
            spatial_embeddings, positions
        )

        # Predict physics-causal edges
        physics_logits, physics_strengths = self.physics_causal_layer(
            spatial_embeddings, positions, velocities
        )

        # Combine spatial info with hidden states
        # Assuming hidden_states has objects embedded in sequence
        num_objects = spatial_embeddings.size(1)
        if hidden_states.size(1) >= num_objects:
            object_hidden = hidden_states[:, :num_objects, :]
            combined = torch.cat([object_hidden, spatial_embeddings], dim=-1)
            combined = self.output_proj(combined)

            # Residual connection
            output = self.layer_norm(object_hidden + combined)

            # Pad back to original sequence length if needed
            if hidden_states.size(1) > num_objects:
                padding = hidden_states[:, num_objects:, :]
                output = torch.cat([output, padding], dim=1)
        else:
            output = hidden_states

        return output, relation_logits, physics_logits


# =============================================================================
# COMPLETE SPATIAL-CAUSAL MODULE
# =============================================================================


class SpatialCausalModule(nn.Module):
    """
    Complete Spatial-Causal Module (V10.11).

    Provides:
        - Spatial state tracking
        - Physics-grounded causal reasoning
        - Spatial interventions
        - Spatial counterfactual reasoning
        - Physics simulation
    """

    def __init__(self, config: SpatialCausalConfig):
        super().__init__()
        self.config = config

        # Core components
        self.spatial_encoder = SpatialStateEncoder(config)
        self.relation_predictor = SpatialRelationPredictor(config)
        self.physics_causal_layer = PhysicsCausalLayer(config)
        self.intervention_module = SpatialInterventionModule(config)
        self.counterfactual_reasoner = SpatialCounterfactualReasoner(config)
        self.simulator = PhysicsSimulator(config)

        # Phase-Quad integration block
        self.phase_quad_block = SpatialCausalPhaseQuadBlock(config)

    def encode_world(self, world: SpatialWorld) -> torch.Tensor:
        """Encode a spatial world into embeddings."""
        return self.spatial_encoder.encode_world(world)

    def compute_relations(self, world: SpatialWorld) -> List[SpatialRelationEdge]:
        """Compute spatial relations in the world."""
        return self.relation_predictor.compute_relations(world)

    def compute_causal_edges(self, world: SpatialWorld) -> List[PhysicsCausalEdge]:
        """Compute physics-causal edges in the world."""
        return self.physics_causal_layer.compute_causal_edges(world)

    def intervene(
        self, world: SpatialWorld, intervention: SpatialIntervention
    ) -> SpatialWorld:
        """Apply a spatial intervention."""
        return self.intervention_module.apply_intervention(world, intervention)

    def simulate(
        self, world: SpatialWorld, steps: int = 10
    ) -> List[SpatialWorld]:
        """Simulate world forward."""
        return self.simulator.simulate(world, steps)

    def counterfactual(
        self,
        world: SpatialWorld,
        intervention: SpatialIntervention,
        steps: int = 10,
    ) -> Dict[str, Any]:
        """Perform counterfactual reasoning."""
        return self.counterfactual_reasoner.reason(world, intervention, steps=steps)

    def forward(
        self,
        hidden_states: torch.Tensor,
        world: Optional[SpatialWorld] = None,
        positions: Optional[torch.Tensor] = None,
        orientations: Optional[torch.Tensor] = None,
        velocities: Optional[torch.Tensor] = None,
        scales: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Optional[SpatialCausalState]]:
        """
        Forward pass integrating spatial-causal reasoning with hidden states.

        Can accept either a SpatialWorld object or explicit tensors.
        """
        if world is not None:
            # Extract tensors from world
            objects = list(world.objects.values())
            if objects:
                positions = torch.stack([o.position for o in objects]).unsqueeze(0)
                orientations = torch.stack([o.orientation for o in objects]).unsqueeze(0)
                velocities = torch.stack([o.velocity for o in objects]).unsqueeze(0)
                scales = torch.stack([o.scale for o in objects]).unsqueeze(0)

        if positions is None:
            # No spatial info, return hidden states unchanged
            return hidden_states, None

        # Run through Phase-Quad block
        output, relation_logits, physics_logits = self.phase_quad_block(
            hidden_states, positions, orientations, velocities, scales
        )

        # Build state object
        spatial_embedding = self.spatial_encoder(
            positions, orientations, velocities, scales
        )

        state = SpatialCausalState(
            spatial_world=world if world is not None else SpatialWorld(),
            causal_graph_embedding=physics_logits.mean(dim=(1, 2)),
            spatial_embedding=spatial_embedding.mean(dim=1),
            relation_matrix=F.softmax(relation_logits, dim=-1),
            physics_causal_matrix=F.softmax(physics_logits, dim=-1),
        )

        return output, state


# =============================================================================
# BENCHMARK UTILITIES
# =============================================================================


class SpatialCausalBenchmark:
    """Benchmarking utilities for Spatial-Causal Module."""

    def __init__(self, config: Optional[SpatialCausalConfig] = None):
        self.config = config or SpatialCausalConfig()
        self.module = SpatialCausalModule(self.config)

    def create_test_world(self) -> SpatialWorld:
        """Create a test world with some objects."""
        world = SpatialWorld()

        # Table (static surface)
        table = SpatialObject(
            id="table",
            position=torch.tensor([0.0, 0.5, 0.0]),
            orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
            scale=torch.tensor([2.0, 0.1, 1.0]),
            velocity=torch.tensor([0.0, 0.0, 0.0]),
            angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
            mass=100.0,
            is_static=True,
        )
        world.add_object(table)

        # Ball on table edge
        ball = SpatialObject(
            id="ball",
            position=torch.tensor([0.9, 0.65, 0.0]),  # Near edge
            orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
            scale=torch.tensor([0.1, 0.1, 0.1]),
            velocity=torch.tensor([0.0, 0.0, 0.0]),
            angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
            mass=0.5,
            is_static=False,
        )
        world.add_object(ball)

        # Cup on table
        cup = SpatialObject(
            id="cup",
            position=torch.tensor([-0.5, 0.65, 0.3]),
            orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
            scale=torch.tensor([0.1, 0.15, 0.1]),
            velocity=torch.tensor([0.0, 0.0, 0.0]),
            angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
            mass=0.3,
            is_static=False,
        )
        world.add_object(cup)

        return world

    def run_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmarks."""
        results = {}

        # Test 1: World encoding
        print("  TEST 1: World Encoding")
        world = self.create_test_world()
        encoding = self.module.encode_world(world)
        results["encoding_shape"] = list(encoding.shape)
        print(f"    Encoding shape: {encoding.shape}")

        # Test 2: Relation computation
        print("  TEST 2: Relation Computation")
        relations = self.module.compute_relations(world)
        results["num_relations"] = len(relations)
        print(f"    Found {len(relations)} spatial relations")
        for rel in relations[:5]:
            print(f"      {rel.source_id} --[{rel.relation.value}]--> {rel.target_id}")

        # Test 3: Physics causal edges
        print("  TEST 3: Physics Causal Edges")
        causal_edges = self.module.compute_causal_edges(world)
        results["num_causal_edges"] = len(causal_edges)
        print(f"    Found {len(causal_edges)} physics-causal edges")
        for edge in causal_edges[:5]:
            print(
                f"      {edge.source_id} --[{edge.physics_type.value}]--> {edge.target_id}"
            )

        # Test 4: Intervention
        print("  TEST 4: Spatial Intervention")
        intervention = SpatialIntervention(
            intervention_type=InterventionType.MOVE,
            obj_id="ball",
            value=torch.tensor([0.0, 0.65, 0.0]),  # Move to center
        )
        new_world = self.module.intervene(world, intervention)
        ball_pos = new_world.objects["ball"].position
        results["intervention_result"] = ball_pos.tolist()
        print(f"    Ball moved to: {ball_pos.tolist()}")

        # Test 5: Physics simulation
        print("  TEST 5: Physics Simulation")
        # Give ball a push
        world.objects["ball"].velocity = torch.tensor([0.5, 0.0, 0.0])
        trajectory = self.module.simulate(world, steps=20)
        final_pos = trajectory[-1].objects["ball"].position
        results["simulation_steps"] = len(trajectory)
        results["final_position"] = final_pos.tolist()
        print(f"    Simulated {len(trajectory)} steps")
        print(f"    Ball final position: {final_pos.tolist()}")

        # Test 6: Counterfactual reasoning
        print("  TEST 6: Counterfactual Reasoning")
        world = self.create_test_world()
        world.objects["ball"].velocity = torch.tensor([0.5, 0.0, 0.0])

        cf_intervention = SpatialIntervention(
            intervention_type=InterventionType.MOVE,
            obj_id="ball",
            value=torch.tensor([0.0, 0.65, 0.0]),  # Center of table
        )
        cf_result = self.module.counterfactual(world, cf_intervention, steps=20)
        results["counterfactual"] = {
            "factual_final": cf_result["factual_final"].objects["ball"].position.tolist(),
            "cf_final": cf_result["counterfactual_final"].objects["ball"].position.tolist(),
            "outcome_diff": cf_result["outcome_difference"],
        }
        print(f"    Factual final: {results['counterfactual']['factual_final']}")
        print(f"    Counterfactual final: {results['counterfactual']['cf_final']}")

        # Test 7: Forward pass integration
        print("  TEST 7: Forward Pass Integration")
        world = self.create_test_world()
        batch_size = 2
        seq_len = 10
        hidden_states = torch.randn(batch_size, seq_len, self.config.hidden_dim)
        output, state = self.module(hidden_states, world=world)
        results["forward_pass"] = {
            "output_shape": list(output.shape),
            "has_state": state is not None,
        }
        print(f"    Output shape: {output.shape}")
        print(f"    State computed: {state is not None}")

        return results


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_spatial_causal_module(
    hidden_dim: int = 256,
    max_objects: int = 64,
    **kwargs,
) -> SpatialCausalModule:
    """Factory function to create a Spatial-Causal Module."""
    config = SpatialCausalConfig(
        hidden_dim=hidden_dim,
        max_objects=max_objects,
        **kwargs,
    )
    return SpatialCausalModule(config)


def create_test_world_with_scenario(scenario: str = "falling_ball") -> SpatialWorld:
    """Create test worlds for different scenarios."""
    world = SpatialWorld()

    if scenario == "falling_ball":
        # Ball at table edge that will fall
        table = SpatialObject(
            id="table",
            position=torch.tensor([0.0, 0.5, 0.0]),
            orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
            scale=torch.tensor([2.0, 0.1, 1.0]),
            velocity=torch.tensor([0.0, 0.0, 0.0]),
            angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
            is_static=True,
        )
        ball = SpatialObject(
            id="ball",
            position=torch.tensor([0.95, 0.65, 0.0]),
            orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
            scale=torch.tensor([0.1, 0.1, 0.1]),
            velocity=torch.tensor([0.2, 0.0, 0.0]),  # Moving toward edge
            angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
            is_static=False,
        )
        world.add_object(table)
        world.add_object(ball)

    elif scenario == "collision":
        # Two balls about to collide
        ball1 = SpatialObject(
            id="ball1",
            position=torch.tensor([-1.0, 0.5, 0.0]),
            orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
            scale=torch.tensor([0.2, 0.2, 0.2]),
            velocity=torch.tensor([1.0, 0.0, 0.0]),
            angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
            is_static=False,
        )
        ball2 = SpatialObject(
            id="ball2",
            position=torch.tensor([1.0, 0.5, 0.0]),
            orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
            scale=torch.tensor([0.2, 0.2, 0.2]),
            velocity=torch.tensor([-1.0, 0.0, 0.0]),
            angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
            is_static=False,
        )
        world.add_object(ball1)
        world.add_object(ball2)

    elif scenario == "domino":
        # Domino chain
        for i in range(5):
            domino = SpatialObject(
                id=f"domino_{i}",
                position=torch.tensor([i * 0.3, 0.25, 0.0]),
                orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
                scale=torch.tensor([0.05, 0.5, 0.2]),
                velocity=torch.tensor([0.0, 0.0, 0.0]),
                angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
                is_static=False,
            )
            world.add_object(domino)

        # First domino gets pushed
        world.objects["domino_0"].angular_velocity = torch.tensor([0.0, 0.0, 2.0])

    elif scenario == "stacking":
        # Stacked blocks
        for i in range(3):
            block = SpatialObject(
                id=f"block_{i}",
                position=torch.tensor([0.0, 0.15 + i * 0.3, 0.0]),
                orientation=torch.tensor([1.0, 0.0, 0.0, 0.0]),
                scale=torch.tensor([0.3, 0.3, 0.3]),
                velocity=torch.tensor([0.0, 0.0, 0.0]),
                angular_velocity=torch.tensor([0.0, 0.0, 0.0]),
                is_static=False,
            )
            world.add_object(block)

    return world


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    "SpatialCausalConfig",
    # Enums
    "SpatialRelation",
    "PhysicsCausalType",
    "InterventionType",
    # Data structures
    "SpatialObject",
    "SpatialRelationEdge",
    "PhysicsCausalEdge",
    "SpatialWorld",
    "SpatialIntervention",
    "SpatialCausalState",
    # Utilities
    "quaternion_multiply",
    "quaternion_to_rotation_matrix",
    "euler_to_quaternion",
    "compute_distance",
    "compute_direction",
    "check_bbox_overlap",
    # Encoding
    "PositionalEncoding3D",
    "OrientationEncoding",
    "SpatialStateEncoder",
    # Relations
    "SpatialRelationPredictor",
    # Physics
    "PhysicsCausalRule",
    "PhysicsCausalLayer",
    # Interventions
    "SpatialInterventionModule",
    # Simulation
    "PhysicsSimulator",
    # Counterfactuals
    "SpatialAbductor",
    "SpatialCounterfactualReasoner",
    # Integration
    "SpatialCausalPhaseQuadBlock",
    "SpatialCausalModule",
    # Benchmark
    "SpatialCausalBenchmark",
    # Factory
    "create_spatial_causal_module",
    "create_test_world_with_scenario",
]
