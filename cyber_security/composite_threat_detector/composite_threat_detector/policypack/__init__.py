"""Enterprise Story Policy Pack — a governed, customer-configurable onboarding layer
over the *frozen* StoryGraph vertical slice.

This package adds NO matching algorithm, weight, or detection behavior. It only lets an
enterprise DECLARE (and a compiler faithfully encode) which action is controlled, which
observed events form a harmful story, which relationships are mandatory, which verified
legitimate workflows explain those events, which trusted systems supply evidence, and
how advisory StoryGraph findings map to ActionGate policy consequences — plus the
governance lifecycle, enterprise event/provider mappings, and a deterministic
historical-replay path over sanitized fixtures.

The StoryGraph layer remains advisory: it never emits ALLOW/DENY.
"""

from __future__ import annotations

from . import compiler, event_mapping, lifecycle, providers_mapping, reference, schema
from .compiler import CompiledPolicyBundle, CompilerError, compile_pack
from .lifecycle import LIFECYCLE_STATES, LifecycleError, transition
from .schema import SCHEMA_VERSION, validate_pack

__all__ = [
    "schema", "compiler", "lifecycle", "event_mapping", "providers_mapping",
    "reference", "SCHEMA_VERSION", "validate_pack", "compile_pack",
    "CompiledPolicyBundle", "CompilerError", "LIFECYCLE_STATES", "LifecycleError",
    "transition",
]
