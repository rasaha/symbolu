"""
SymbolU12 Pratyaksha Dashboard Module
======================================

"Pratyaksha" (Sanskrit: प्रत्यक्ष) means "Direct Perception."

This module provides real-time visualization of the 124-dim cognitive
manifold, serving as the "Clinical Monitor" for the AGI's soul.

Components:
    - Data Stream: Queue-based async data transfer between model and dashboard
    - Axiomatic Triggers: Real-time detection of axiom violations
    - Pratyaksha Dashboard: Streamlit-based visualization interface

Key Visualizations:
    1. Trace EKG - Phase-Lock integrity like a heartbeat monitor
    2. Bhava Radar - 12-pointed cognitive balance chart
    3. Dynamic Gauges - Confidence and Entropy thermometers
    4. Axiomatic Alerts - Circuit breaker notifications
    5. Output Log - Color-coded text by confidence level

Usage:
    # Start dashboard
    streamlit run -m symbolu.experimental.dashboard.pratyaksha

    # Or programmatically
    from symbolu_extensions.experimental.dashboard import (
        PratyakshaDashboard,
        get_dashboard_stream,
        StateSnapshotBuilder,
    )

    # Get global stream
    stream = get_dashboard_stream()

    # Build and push snapshots
    builder = StateSnapshotBuilder()
    snapshot = builder.build(
        trace=0.85,
        bhava_tensor=bhava,
        dynamics_tensor=dynamics,
    )
    stream.push(snapshot)

    # Create dashboard
    dashboard = PratyakshaDashboard(stream)
    dashboard.run_streamlit()

Why This Dashboard Matters:
    Standard AI dashboards show "Tokens per second."
    Pratyaksha shows "Logic per Token."

    This is the difference between monitoring a printer
    and monitoring a brain.
"""

# Data Stream Components
from .data_stream import (
    # Enums
    AlertLevel,
    AxiomType,
    # Data Classes
    BhavaSnapshot,
    DynamicsSnapshot,
    AlertSnapshot,
    StateSnapshot,
    # Stream
    DashboardStream,
    StateSnapshotBuilder,
    # Global access
    get_dashboard_stream,
    reset_dashboard_stream,
)

# Axiomatic Trigger Detection
from .axiomatic_triggers import (
    # Configuration
    TriggerThresholds,
    TriggerResult,
    # Individual Detectors
    IdentityBreachDetector,
    CausalDisconnectDetector,
    BoundaryCollisionDetector,
    PhaseLockDetector,
    CognitiveDissonanceDetector,
    # Unified System
    AxiomaticTriggerSystem,
)

# Visualization Components
from .pratyaksha import (
    # Components
    TraceEKG,
    BhavaRadar,
    DynamicGauges,
    AlertPanel,
    OutputLog,
    # Utilities
    render_truth_meter,
    # Main Dashboard
    PratyakshaDashboard,
    run_demo_dashboard,
)

# Production Guardrails
from .guardrails import (
    GuardrailAction,
    GuardrailResult,
    ProductionGuardrails,
    GUARDRAIL_SUMMARY,
)


__all__ = [
    # === Data Stream ===
    'AlertLevel',
    'AxiomType',
    'BhavaSnapshot',
    'DynamicsSnapshot',
    'AlertSnapshot',
    'StateSnapshot',
    'DashboardStream',
    'StateSnapshotBuilder',
    'get_dashboard_stream',
    'reset_dashboard_stream',

    # === Axiomatic Triggers ===
    'TriggerThresholds',
    'TriggerResult',
    'IdentityBreachDetector',
    'CausalDisconnectDetector',
    'BoundaryCollisionDetector',
    'PhaseLockDetector',
    'CognitiveDissonanceDetector',
    'AxiomaticTriggerSystem',

    # === Visualization ===
    'TraceEKG',
    'BhavaRadar',
    'DynamicGauges',
    'AlertPanel',
    'OutputLog',
    'render_truth_meter',
    'PratyakshaDashboard',
    'run_demo_dashboard',

    # === Production Guardrails ===
    'GuardrailAction',
    'GuardrailResult',
    'ProductionGuardrails',
    'GUARDRAIL_SUMMARY',
]
