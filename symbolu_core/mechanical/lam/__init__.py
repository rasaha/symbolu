"""
LAM (Long-Arc Mapper) Module v1.0

A deterministic, LLM-free sub-engine that produces temporal-longitudinal
cognitive maps for long-arc trajectory reasoning by Fusion/DHA engines.

LAM completes the TTOR mapper triad:
    HRM -> high-resolution snapshot
    LCM -> low-context procedural focus
    LAM -> long-arc temporal trajectory reasoning

LAM integrates temporal reasoning into the AGI pipeline using:
    - TemporalBhavaTracker for consciousness state evolution tracking
    - CrossDomainIntelligence for universal pattern detection and transfer
    - TTOR long_arc_tension signals for activation

LAM runs when:
    - TTOR sets `use_lam=True` in the RoutingPlan
    - Or when router_context.long_arc_tension > threshold

LAM answers:
    - Where is the user coming from?
    - Where is the user going emotionally/mentally?
    - Is the trajectory rising, falling, stable?
    - Is the system in tension or recovery?
    - Which universal patterns are active?
    - How do we map these patterns to the current domain?

Usage:
    from symbolu_core.mechanical.lam import LAMEngine, LAMInput, LongArcMap
    from agentic.temporal.temporal_bhava_tracker import TemporalBhavaTracker
    from agentic.temporal.cross_domain_intelligence import CrossDomainIntelligence

    tracker = TemporalBhavaTracker(window_size=10)
    cdi = CrossDomainIntelligence()
    engine = LAMEngine()

    lam_input = LAMInput(
        text="I feel like I'm finally making progress",
        smi=0.3,
        bhava_id=7,
        bhava_direction="upward",
        kosha_id=4,
        ontology_id=6,
        domain="psychology",
        long_arc_tension=0.4,
        temporal_tracker=tracker,
        cdi=cdi,
    )
    lam_map = engine.build_map(lam_input)
"""

from .models import LAMInput, LongArcMap
from .lam_engine import LAMEngine

__all__ = [
    "LAMEngine",
    "LAMInput",
    "LongArcMap",
]

__version__ = "1.0.0"
