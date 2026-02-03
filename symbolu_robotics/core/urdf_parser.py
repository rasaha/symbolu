"""
URDF Parser Module
==================

Parse URDF (Unified Robot Description Format) files for robot models.

Implementation: Pure Python using xml.etree (stdlib)
No external URDF libraries required (urdf_parser_py, yourdfpy, etc.)

Supports:
- Link and joint parsing
- Origin transforms
- Joint types (revolute, prismatic, continuous, fixed)
- Joint limits
- Inertial properties (optional)
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import numpy as np
import logging
from pathlib import Path

from symbolu_robotics.core.kinematics import DHParams, JointType, ForwardKinematics

logger = logging.getLogger(__name__)


class URDFJointType(Enum):
    """URDF joint types."""
    REVOLUTE = "revolute"
    CONTINUOUS = "continuous"  # Like revolute but no limits
    PRISMATIC = "prismatic"
    FIXED = "fixed"
    FLOATING = "floating"
    PLANAR = "planar"


@dataclass
class URDFOrigin:
    """Transform origin (position + orientation)."""
    xyz: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rpy: np.ndarray = field(default_factory=lambda: np.zeros(3))  # roll, pitch, yaw

    def to_transform(self) -> np.ndarray:
        """Convert to 4x4 homogeneous transform."""
        # Rotation matrices for roll, pitch, yaw
        r, p, y = self.rpy

        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(r), -np.sin(r)],
            [0, np.sin(r), np.cos(r)]
        ])

        Ry = np.array([
            [np.cos(p), 0, np.sin(p)],
            [0, 1, 0],
            [-np.sin(p), 0, np.cos(p)]
        ])

        Rz = np.array([
            [np.cos(y), -np.sin(y), 0],
            [np.sin(y), np.cos(y), 0],
            [0, 0, 1]
        ])

        R = Rz @ Ry @ Rx

        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = self.xyz
        return T


@dataclass
class URDFInertial:
    """Inertial properties of a link."""
    mass: float = 0.0
    origin: URDFOrigin = field(default_factory=URDFOrigin)
    inertia: np.ndarray = field(default_factory=lambda: np.eye(3))  # 3x3 inertia matrix


@dataclass
class URDFLink:
    """URDF link definition."""
    name: str
    inertial: Optional[URDFInertial] = None
    # Visual and collision geometries omitted for simplicity
    # (would need mesh loading which requires external deps)


@dataclass
class URDFJoint:
    """URDF joint definition."""
    name: str
    joint_type: URDFJointType
    parent_link: str
    child_link: str
    origin: URDFOrigin = field(default_factory=URDFOrigin)
    axis: np.ndarray = field(default_factory=lambda: np.array([0, 0, 1]))

    # Limits (for revolute and prismatic)
    lower_limit: float = -np.pi
    upper_limit: float = np.pi
    velocity_limit: float = 1.0
    effort_limit: float = 100.0


@dataclass
class URDFRobot:
    """Parsed URDF robot model."""
    name: str
    links: Dict[str, URDFLink] = field(default_factory=dict)
    joints: Dict[str, URDFJoint] = field(default_factory=dict)
    root_link: Optional[str] = None

    # Kinematic chain (ordered from base to end-effector)
    kinematic_chain: List[str] = field(default_factory=list)


class URDFParser:
    """
    Parser for URDF robot description files.

    Uses only Python stdlib (xml.etree.ElementTree).
    """

    def __init__(self):
        self._robot: Optional[URDFRobot] = None

    def parse(self, urdf_path: str) -> URDFRobot:
        """
        Parse URDF file.

        Args:
            urdf_path: Path to URDF file

        Returns:
            Parsed robot model
        """
        path = Path(urdf_path)
        if not path.exists():
            raise FileNotFoundError(f"URDF file not found: {urdf_path}")

        tree = ET.parse(urdf_path)
        root = tree.getroot()

        if root.tag != 'robot':
            raise ValueError(f"Expected 'robot' root element, got '{root.tag}'")

        robot_name = root.get('name', 'unnamed_robot')
        self._robot = URDFRobot(name=robot_name)

        # Parse links
        for link_elem in root.findall('link'):
            link = self._parse_link(link_elem)
            self._robot.links[link.name] = link

        # Parse joints
        parent_links = set()
        child_links = set()

        for joint_elem in root.findall('joint'):
            joint = self._parse_joint(joint_elem)
            self._robot.joints[joint.name] = joint
            parent_links.add(joint.parent_link)
            child_links.add(joint.child_link)

        # Find root link (parent but never child)
        roots = parent_links - child_links
        if roots:
            self._robot.root_link = list(roots)[0]
        elif self._robot.links:
            # Fallback to first link
            self._robot.root_link = list(self._robot.links.keys())[0]

        # Build kinematic chain
        self._robot.kinematic_chain = self._build_kinematic_chain()

        logger.info(
            f"Parsed URDF '{robot_name}': {len(self._robot.links)} links, "
            f"{len(self._robot.joints)} joints, root='{self._robot.root_link}'"
        )

        return self._robot

    def parse_string(self, urdf_string: str) -> URDFRobot:
        """Parse URDF from string."""
        root = ET.fromstring(urdf_string)

        robot_name = root.get('name', 'unnamed_robot')
        self._robot = URDFRobot(name=robot_name)

        for link_elem in root.findall('link'):
            link = self._parse_link(link_elem)
            self._robot.links[link.name] = link

        parent_links = set()
        child_links = set()

        for joint_elem in root.findall('joint'):
            joint = self._parse_joint(joint_elem)
            self._robot.joints[joint.name] = joint
            parent_links.add(joint.parent_link)
            child_links.add(joint.child_link)

        roots = parent_links - child_links
        if roots:
            self._robot.root_link = list(roots)[0]

        self._robot.kinematic_chain = self._build_kinematic_chain()

        return self._robot

    def _parse_link(self, elem: ET.Element) -> URDFLink:
        """Parse a link element."""
        name = elem.get('name', 'unnamed_link')
        link = URDFLink(name=name)

        # Parse inertial if present
        inertial_elem = elem.find('inertial')
        if inertial_elem is not None:
            link.inertial = self._parse_inertial(inertial_elem)

        return link

    def _parse_joint(self, elem: ET.Element) -> URDFJoint:
        """Parse a joint element."""
        name = elem.get('name', 'unnamed_joint')
        joint_type_str = elem.get('type', 'fixed')

        try:
            joint_type = URDFJointType(joint_type_str)
        except ValueError:
            logger.warning(f"Unknown joint type '{joint_type_str}', defaulting to fixed")
            joint_type = URDFJointType.FIXED

        # Parent and child links
        parent_elem = elem.find('parent')
        child_elem = elem.find('child')
        parent_link = parent_elem.get('link', '') if parent_elem is not None else ''
        child_link = child_elem.get('link', '') if child_elem is not None else ''

        joint = URDFJoint(
            name=name,
            joint_type=joint_type,
            parent_link=parent_link,
            child_link=child_link,
        )

        # Parse origin
        origin_elem = elem.find('origin')
        if origin_elem is not None:
            joint.origin = self._parse_origin(origin_elem)

        # Parse axis
        axis_elem = elem.find('axis')
        if axis_elem is not None:
            xyz_str = axis_elem.get('xyz', '0 0 1')
            joint.axis = np.array([float(x) for x in xyz_str.split()])

        # Parse limits
        limit_elem = elem.find('limit')
        if limit_elem is not None:
            joint.lower_limit = float(limit_elem.get('lower', -np.pi))
            joint.upper_limit = float(limit_elem.get('upper', np.pi))
            joint.velocity_limit = float(limit_elem.get('velocity', 1.0))
            joint.effort_limit = float(limit_elem.get('effort', 100.0))
        elif joint_type == URDFJointType.CONTINUOUS:
            # Continuous joints have no limits
            joint.lower_limit = -np.inf
            joint.upper_limit = np.inf

        return joint

    def _parse_origin(self, elem: ET.Element) -> URDFOrigin:
        """Parse an origin element."""
        xyz_str = elem.get('xyz', '0 0 0')
        rpy_str = elem.get('rpy', '0 0 0')

        xyz = np.array([float(x) for x in xyz_str.split()])
        rpy = np.array([float(x) for x in rpy_str.split()])

        return URDFOrigin(xyz=xyz, rpy=rpy)

    def _parse_inertial(self, elem: ET.Element) -> URDFInertial:
        """Parse an inertial element."""
        inertial = URDFInertial()

        # Mass
        mass_elem = elem.find('mass')
        if mass_elem is not None:
            inertial.mass = float(mass_elem.get('value', 0))

        # Origin
        origin_elem = elem.find('origin')
        if origin_elem is not None:
            inertial.origin = self._parse_origin(origin_elem)

        # Inertia tensor
        inertia_elem = elem.find('inertia')
        if inertia_elem is not None:
            ixx = float(inertia_elem.get('ixx', 1))
            ixy = float(inertia_elem.get('ixy', 0))
            ixz = float(inertia_elem.get('ixz', 0))
            iyy = float(inertia_elem.get('iyy', 1))
            iyz = float(inertia_elem.get('iyz', 0))
            izz = float(inertia_elem.get('izz', 1))

            inertial.inertia = np.array([
                [ixx, ixy, ixz],
                [ixy, iyy, iyz],
                [ixz, iyz, izz],
            ])

        return inertial

    def _build_kinematic_chain(self) -> List[str]:
        """Build ordered kinematic chain from root to leaves."""
        if not self._robot or not self._robot.root_link:
            return []

        chain = []
        visited = set()

        def traverse(link_name: str):
            if link_name in visited:
                return
            visited.add(link_name)

            # Find joints where this link is the parent
            for joint_name, joint in self._robot.joints.items():
                if joint.parent_link == link_name:
                    chain.append(joint_name)
                    traverse(joint.child_link)

        traverse(self._robot.root_link)
        return chain

    def to_forward_kinematics(
        self,
        end_effector_link: Optional[str] = None,
    ) -> ForwardKinematics:
        """
        Convert parsed URDF to ForwardKinematics object.

        Note: This is an approximation - URDF uses a different convention
        than standard DH parameters. For precise kinematics, use the
        direct transform-based approach.

        Args:
            end_effector_link: Name of end-effector link (uses last link if None)

        Returns:
            ForwardKinematics object (approximate)
        """
        if not self._robot:
            raise ValueError("No URDF parsed yet")

        # Get joints in kinematic chain
        chain_joints = []
        for joint_name in self._robot.kinematic_chain:
            joint = self._robot.joints[joint_name]
            if joint.joint_type in (URDFJointType.REVOLUTE, URDFJointType.CONTINUOUS,
                                    URDFJointType.PRISMATIC):
                chain_joints.append(joint)

        # Convert to DH parameters (approximate)
        dh_params = []
        for joint in chain_joints:
            # Extract approximate DH parameters from origin
            origin = joint.origin
            T = origin.to_transform()

            # Approximate DH parameters
            # This is a simplification - proper conversion is complex
            d = T[2, 3]  # z translation
            a = np.sqrt(T[0, 3]**2 + T[1, 3]**2)  # xy distance
            theta = np.arctan2(T[1, 3], T[0, 3]) if a > 0.001 else 0  # xy angle

            # Alpha from rotation matrix (angle about x)
            alpha = np.arctan2(T[2, 1], T[2, 2])

            if joint.joint_type == URDFJointType.PRISMATIC:
                jtype = JointType.PRISMATIC
            else:
                jtype = JointType.REVOLUTE

            dh_params.append(DHParams(
                a=a,
                alpha=alpha,
                d=d,
                theta=theta,
                joint_type=jtype,
                lower_limit=joint.lower_limit,
                upper_limit=joint.upper_limit,
            ))

        return ForwardKinematics(dh_params, name=self._robot.name)

    def compute_transform_chain(
        self,
        joint_values: Dict[str, float],
    ) -> np.ndarray:
        """
        Compute end-effector transform using direct URDF transforms.

        This is more accurate than the DH approximation.

        Args:
            joint_values: Dict mapping joint name to value

        Returns:
            4x4 homogeneous transform
        """
        if not self._robot:
            raise ValueError("No URDF parsed yet")

        T = np.eye(4)

        for joint_name in self._robot.kinematic_chain:
            joint = self._robot.joints[joint_name]

            # Joint origin transform
            T_origin = joint.origin.to_transform()
            T = T @ T_origin

            # Joint transform
            q = joint_values.get(joint_name, 0.0)

            if joint.joint_type in (URDFJointType.REVOLUTE, URDFJointType.CONTINUOUS):
                # Rotation about axis
                T_joint = self._rotation_about_axis(joint.axis, q)
            elif joint.joint_type == URDFJointType.PRISMATIC:
                # Translation along axis
                T_joint = np.eye(4)
                T_joint[:3, 3] = joint.axis * q
            else:
                T_joint = np.eye(4)

            T = T @ T_joint

        return T

    def _rotation_about_axis(self, axis: np.ndarray, angle: float) -> np.ndarray:
        """Compute rotation matrix about arbitrary axis."""
        axis = axis / np.linalg.norm(axis)
        K = np.array([
            [0, -axis[2], axis[1]],
            [axis[2], 0, -axis[0]],
            [-axis[1], axis[0], 0],
        ])
        R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)

        T = np.eye(4)
        T[:3, :3] = R
        return T


def load_urdf(urdf_path: str) -> URDFRobot:
    """Convenience function to parse URDF file."""
    parser = URDFParser()
    return parser.parse(urdf_path)
