"""ACP safety adapters (Phase 2).

Integration layer between ACP's stdlib core and the repository's REAL safety
modules. Modules here import numpy + ``symbolu_robotics.safety.*`` and therefore
are NOT imported by the ACP core ``__init__`` — ``import
symbolu_robotics.autonomous_control_plane`` stays production-independent, while
``import ...autonomous_control_plane.safety_adapters`` pulls the heavy deps on
demand (milestone §3: environment-specific integrations live in adapter
packages, not the core).

No ROS / simulator / hardware dependency is introduced — only numpy and the
existing deterministic safety validators.
"""
