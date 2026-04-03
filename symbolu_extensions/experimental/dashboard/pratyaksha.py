"""
SymbolU12 Pratyaksha Dashboard
===============================

"Pratyaksha" (Sanskrit: प्रत्यक्ष) means "Direct Perception" or "The Witness."

This dashboard provides real-time visualization of the 124-dim cognitive
manifold, allowing operators to witness the Phase-Lock in action.

Components:
    1. Trace EKG - Real-time Phase-Lock trace (τ) like a heartbeat monitor
    2. Bhava Radar - 12-pointed spider chart showing cognitive balance
    3. Dynamic Gauges - Confidence and Entropy thermometers
    4. Axiomatic Alerts - Real-time circuit breaker notifications
    5. Output Log - Color-coded text by confidence level

Usage:
    streamlit run pratyaksha.py

    Or programmatically:
    from symbolu.experimental.dashboard import PratyakshaDashboard
    dashboard = PratyakshaDashboard()
    dashboard.run()
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time
import math

# Dashboard dependencies (optional imports for flexibility)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from .data_stream import (
    StateSnapshot,
    BhavaSnapshot,
    DashboardStream,
    get_dashboard_stream,
    AlertLevel,
    AxiomType,
)
from .axiomatic_triggers import (
    AxiomaticTriggerSystem,
    TriggerThresholds,
)


# =============================================================================
# VISUALIZATION COMPONENTS
# =============================================================================

class TraceEKG:
    """
    Real-time Trace (τ) visualization like an EKG monitor.

    The "Pulse of Logic" - shows Phase-Lock integrity over time.
    """

    BHAVA_LABELS = [
        'Factual', 'Analytical', 'Instructive', 'Questioning',
        'Speculative', 'Argumentative', 'Narrative', 'Emotive',
        'Imperative', 'Uncertain', 'Metalinguistic', 'Sattvic',
    ]

    def __init__(
        self,
        threshold: float = 0.75,
        critical_threshold: float = 0.30,
        max_points: int = 200,
    ):
        self.threshold = threshold
        self.critical_threshold = critical_threshold
        self.max_points = max_points
        self.trace_history: List[float] = []
        self.time_history: List[int] = []

    def update(self, trace: float, step: int):
        """Add new trace value."""
        self.trace_history.append(trace)
        self.time_history.append(step)

        if len(self.trace_history) > self.max_points:
            self.trace_history.pop(0)
            self.time_history.pop(0)

    def create_figure(self) -> Optional['go.Figure']:
        """Create Plotly figure for trace EKG."""
        if not PLOTLY_AVAILABLE:
            return None

        fig = go.Figure()

        # Trace line
        fig.add_trace(go.Scatter(
            x=self.time_history,
            y=self.trace_history,
            mode='lines',
            name='Phase-Lock Trace (τ)',
            line=dict(color='cyan', width=2),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 255, 0.1)',
        ))

        # Threshold line
        fig.add_hline(
            y=self.threshold,
            line_dash="dash",
            line_color="yellow",
            annotation_text=f"τ threshold ({self.threshold})",
        )

        # Critical threshold
        fig.add_hline(
            y=self.critical_threshold,
            line_dash="dot",
            line_color="red",
            annotation_text=f"Critical ({self.critical_threshold})",
        )

        # Color regions
        fig.add_hrect(
            y0=0, y1=self.critical_threshold,
            fillcolor="red", opacity=0.1,
            line_width=0,
        )
        fig.add_hrect(
            y0=self.critical_threshold, y1=self.threshold,
            fillcolor="yellow", opacity=0.1,
            line_width=0,
        )

        fig.update_layout(
            title="Phase-Lock Trace (τ) - Integrity Monitor",
            xaxis_title="Step",
            yaxis_title="Trace Value",
            yaxis_range=[0, 1.1],
            template="plotly_dark",
            height=300,
            margin=dict(l=50, r=50, t=50, b=50),
        )

        return fig


class BhavaRadar:
    """
    12-pointed radar chart showing cognitive balance.

    The "Mind-Shape" - visualizes distribution across 12 Bhava states.
    """

    BHAVA_LABELS = [
        'Factual', 'Analytical', 'Instructive', 'Questioning',
        'Speculative', 'Argumentative', 'Narrative', 'Emotive',
        'Imperative', 'Uncertain', 'Meta', 'Sattvic',
    ]

    def __init__(self):
        self.current_bhava: Optional[BhavaSnapshot] = None

    def update(self, bhava: BhavaSnapshot):
        """Update current Bhava state."""
        self.current_bhava = bhava

    def create_figure(self) -> Optional['go.Figure']:
        """Create Plotly radar chart."""
        if not PLOTLY_AVAILABLE or self.current_bhava is None:
            return None

        values = self.current_bhava.to_list()
        # Close the polygon
        values_closed = values + [values[0]]
        labels_closed = self.BHAVA_LABELS + [self.BHAVA_LABELS[0]]

        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill='toself',
            fillcolor='rgba(0, 255, 255, 0.3)',
            line=dict(color='cyan', width=2),
            name='Current Bhava',
        ))

        # Add reference circle for balanced state
        balanced = [0.083] * 13  # 1/12 for each
        fig.add_trace(go.Scatterpolar(
            r=balanced,
            theta=labels_closed,
            fill=None,
            line=dict(color='gray', width=1, dash='dash'),
            name='Balanced',
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    tickfont=dict(size=10),
                ),
                angularaxis=dict(
                    tickfont=dict(size=10),
                ),
                bgcolor='rgba(0,0,0,0)',
            ),
            showlegend=False,
            title="Bhava Radar - Cognitive Balance",
            template="plotly_dark",
            height=350,
            margin=dict(l=80, r=80, t=50, b=50),
        )

        return fig


class DynamicGauges:
    """
    Vertical gauges for Confidence and Entropy.

    The "self-awareness thermometers" showing cognitive state.
    """

    def __init__(self):
        self.confidence: float = 0.5
        self.entropy: float = 0.5
        self.momentum: float = 0.5
        self.coherence: float = 0.5

    def update(self, confidence: float, entropy: float,
               momentum: float = 0.5, coherence: float = 0.5):
        """Update gauge values."""
        self.confidence = confidence
        self.entropy = entropy
        self.momentum = momentum
        self.coherence = coherence

    def create_confidence_gauge(self) -> Optional['go.Figure']:
        """Create confidence gauge."""
        if not PLOTLY_AVAILABLE:
            return None

        # Color based on confidence level
        if self.confidence >= 0.8:
            color = "green"
        elif self.confidence >= 0.5:
            color = "yellow"
        else:
            color = "red"

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=self.confidence,
            title={'text': "Confidence (d[2])"},
            gauge={
                'axis': {'range': [0, 1]},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, 0.4], 'color': "rgba(255,0,0,0.2)"},
                    {'range': [0.4, 0.7], 'color': "rgba(255,255,0,0.2)"},
                    {'range': [0.7, 1], 'color': "rgba(0,255,0,0.2)"},
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 2},
                    'thickness': 0.75,
                    'value': 0.5,
                },
            },
        ))

        fig.update_layout(
            template="plotly_dark",
            height=200,
            margin=dict(l=30, r=30, t=50, b=20),
        )

        return fig

    def create_entropy_gauge(self) -> Optional['go.Figure']:
        """Create entropy gauge (inverted - low is good)."""
        if not PLOTLY_AVAILABLE:
            return None

        # Color based on entropy level (inverted)
        if self.entropy <= 0.3:
            color = "green"
        elif self.entropy <= 0.6:
            color = "yellow"
        else:
            color = "magenta"

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=self.entropy,
            title={'text': "Entropy (d[1])"},
            gauge={
                'axis': {'range': [0, 1]},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, 0.3], 'color': "rgba(0,255,0,0.2)"},
                    {'range': [0.3, 0.6], 'color': "rgba(255,255,0,0.2)"},
                    {'range': [0.6, 1], 'color': "rgba(255,0,255,0.2)"},
                ],
            },
        ))

        fig.update_layout(
            template="plotly_dark",
            height=200,
            margin=dict(l=30, r=30, t=50, b=20),
        )

        return fig


class AlertPanel:
    """
    Real-time axiomatic alert display.

    Shows which axiom triggered and why.
    """

    ALERT_COLORS = {
        AlertLevel.NORMAL: "#00ff00",
        AlertLevel.WARNING: "#ffff00",
        AlertLevel.CRITICAL: "#ff6600",
        AlertLevel.EMERGENCY: "#ff0000",
    }

    AXIOM_ICONS = {
        AxiomType.NONE: "✓",
        AxiomType.IDENTITY: "🔵",      # Cyan for Identity
        AxiomType.CAUSALITY: "🟣",     # Magenta for Causality
        AxiomType.CATEGORY: "🟠",       # Amber for Category
        AxiomType.PHASE_LOCK: "🔴",    # Red for Phase-Lock
    }

    def __init__(self, max_alerts: int = 5):
        self.max_alerts = max_alerts
        self.alerts: List[Dict[str, Any]] = []

    def add_alert(self, axiom_type: AxiomType, level: AlertLevel,
                  message: str, trace: float):
        """Add new alert."""
        self.alerts.insert(0, {
            'axiom': axiom_type,
            'level': level,
            'message': message,
            'trace': trace,
            'time': time.strftime("%H:%M:%S"),
        })
        if len(self.alerts) > self.max_alerts:
            self.alerts.pop()

    def render_html(self) -> str:
        """Render alerts as HTML."""
        if not self.alerts:
            return '<div style="color: green;">✓ All Systems Nominal</div>'

        html_parts = []
        for alert in self.alerts:
            color = self.ALERT_COLORS[alert['level']]
            icon = self.AXIOM_ICONS[alert['axiom']]
            html_parts.append(
                f'<div style="color: {color}; padding: 5px; '
                f'border-left: 3px solid {color}; margin: 5px 0;">'
                f'{icon} [{alert["time"]}] {alert["message"]} '
                f'(τ={alert["trace"]:.3f})</div>'
            )

        return ''.join(html_parts)


class OutputLog:
    """
    Color-coded text output log.

    Colors based on confidence level:
    - Green: Grounded (confidence > 0.8)
    - Yellow: Speculative (confidence 0.5-0.8)
    - Red: Paradoxical (confidence < 0.5)
    """

    def __init__(self, max_entries: int = 20):
        self.max_entries = max_entries
        self.entries: List[Dict[str, Any]] = []

    def add_entry(self, text: str, confidence: float, trace: float):
        """Add log entry."""
        if confidence >= 0.8:
            color = "#00ff00"
            label = "GROUNDED"
        elif confidence >= 0.5:
            color = "#ffff00"
            label = "SPECULATIVE"
        else:
            color = "#ff0000"
            label = "PARADOXICAL"

        self.entries.append({
            'text': text,
            'confidence': confidence,
            'trace': trace,
            'color': color,
            'label': label,
            'time': time.strftime("%H:%M:%S"),
        })

        if len(self.entries) > self.max_entries:
            self.entries.pop(0)

    def render_html(self) -> str:
        """Render log as HTML."""
        if not self.entries:
            return '<div style="color: gray;">No output yet...</div>'

        html_parts = []
        for entry in reversed(self.entries):
            html_parts.append(
                f'<div style="color: {entry["color"]}; padding: 3px; '
                f'font-family: monospace; font-size: 12px;">'
                f'[{entry["time"]}] [{entry["label"]}] {entry["text"][:100]}'
                f'{"..." if len(entry["text"]) > 100 else ""}</div>'
            )

        return ''.join(html_parts)


# =============================================================================
# TRUTH METER
# =============================================================================

def render_truth_meter(trace: float) -> str:
    """
    Render ASCII truth meter for terminal/text display.

    Args:
        trace: Phase-Lock trace value (0.0 to 1.0)

    Returns:
        Formatted string showing truth meter
    """
    if trace >= 0.8:
        color = "🟢"
        label = "HIGH CONFIDENCE"
        bar = "████████████████████"
    elif trace >= 0.5:
        color = "🟡"
        label = "SPECULATIVE"
        filled = int(trace * 20)
        bar = "█" * filled + "░" * (20 - filled)
    elif trace >= 0.3:
        color = "🟠"
        label = "LOW CONFIDENCE"
        filled = int(trace * 20)
        bar = "█" * filled + "░" * (20 - filled)
    else:
        color = "🔴"
        label = "META TRIGGERED"
        bar = "░░░░░░░░░░░░░░░░░░░░"

    return f"""
┌──────────────────────────────┐
│ {color} TRUTH METER: {trace:.2f}         │
│ [{bar}] │
│ Status: {label:<18} │
└──────────────────────────────┘
"""


# =============================================================================
# MAIN DASHBOARD CLASS
# =============================================================================

class PratyakshaDashboard:
    """
    Complete Pratyaksha Dashboard for SymbolU12.

    "The Witness" - real-time visualization of the 124-dim cognitive manifold.
    """

    def __init__(
        self,
        stream: Optional[DashboardStream] = None,
        trigger_system: Optional[AxiomaticTriggerSystem] = None,
    ):
        self.stream = stream or get_dashboard_stream()
        self.trigger_system = trigger_system or AxiomaticTriggerSystem()

        # Visualization components
        self.trace_ekg = TraceEKG()
        self.bhava_radar = BhavaRadar()
        self.dynamic_gauges = DynamicGauges()
        self.alert_panel = AlertPanel()
        self.output_log = OutputLog()

        # State
        self.latest_snapshot: Optional[StateSnapshot] = None
        self.is_running = False

    def update(self, snapshot: StateSnapshot):
        """Update all components with new snapshot."""
        self.latest_snapshot = snapshot

        # Update visualizations
        self.trace_ekg.update(snapshot.trace, snapshot.step)
        self.bhava_radar.update(snapshot.bhava)
        self.dynamic_gauges.update(
            snapshot.dynamics.confidence,
            snapshot.dynamics.entropy,
            snapshot.dynamics.momentum,
            snapshot.dynamics.coherence,
        )

        # Check triggers
        alert = self.trigger_system.check_all(snapshot)
        if alert.axiom_type != AxiomType.NONE:
            self.alert_panel.add_alert(
                alert.axiom_type,
                alert.level,
                alert.message,
                snapshot.trace,
            )

        # Add to log if there's token text
        if snapshot.token_text:
            self.output_log.add_entry(
                snapshot.token_text,
                snapshot.dynamics.confidence,
                snapshot.trace,
            )

    def run_streamlit(self):
        """Run as Streamlit app."""
        if not STREAMLIT_AVAILABLE:
            raise ImportError("Streamlit not installed. Run: pip install streamlit")

        st.set_page_config(
            page_title="Pratyaksha - SymbolU12 Monitor",
            page_icon="👁️",
            layout="wide",
        )

        st.title("👁️ Pratyaksha - The Witness")
        st.markdown("*Real-time visualization of the 124-dim cognitive manifold*")

        # Layout
        col1, col2 = st.columns([2, 1])

        with col1:
            # Trace EKG
            st.subheader("Phase-Lock Trace (τ) - Integrity Monitor")
            trace_fig = self.trace_ekg.create_figure()
            if trace_fig:
                st.plotly_chart(trace_fig, use_container_width=True)

            # Alerts
            st.subheader("⚡ Axiomatic Triggers")
            st.markdown(self.alert_panel.render_html(), unsafe_allow_html=True)

        with col2:
            # Bhava Radar
            st.subheader("Bhava Radar - Cognitive Balance")
            radar_fig = self.bhava_radar.create_figure()
            if radar_fig:
                st.plotly_chart(radar_fig, use_container_width=True)

            # Gauges
            gauge_col1, gauge_col2 = st.columns(2)
            with gauge_col1:
                conf_fig = self.dynamic_gauges.create_confidence_gauge()
                if conf_fig:
                    st.plotly_chart(conf_fig, use_container_width=True)
            with gauge_col2:
                ent_fig = self.dynamic_gauges.create_entropy_gauge()
                if ent_fig:
                    st.plotly_chart(ent_fig, use_container_width=True)

        # Output log
        st.subheader("📜 Output Log (Color-coded by Confidence)")
        st.markdown(self.output_log.render_html(), unsafe_allow_html=True)

        # Current state metrics
        if self.latest_snapshot:
            st.sidebar.header("Current State")
            st.sidebar.metric("Trace (τ)", f"{self.latest_snapshot.trace:.3f}")
            st.sidebar.metric("Confidence", f"{self.latest_snapshot.dynamics.confidence:.3f}")
            st.sidebar.metric("Entropy", f"{self.latest_snapshot.dynamics.entropy:.3f}")
            st.sidebar.metric("Dominant Bhava", self.latest_snapshot.dominant_bhava)
            st.sidebar.metric("Vṛtti Mode", self.latest_snapshot.vritti_mode)

            if self.latest_snapshot.meta_triggered:
                st.sidebar.error("🔴 META TRIGGERED")
                st.sidebar.metric("META Latency", f"{self.latest_snapshot.meta_latency_us:.0f} μs")

    def get_terminal_display(self) -> str:
        """Get terminal-friendly display."""
        if not self.latest_snapshot:
            return "No data yet..."

        s = self.latest_snapshot
        truth_meter = render_truth_meter(s.trace)

        return f"""
╔══════════════════════════════════════════════════════════════════╗
║                    PRATYAKSHA - THE WITNESS                       ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  Step: {s.step:<10}  Phase: {s.training_phase:<15}              ║
║                                                                   ║
{truth_meter}
║                                                                   ║
║  DYNAMICS:                                                        ║
║    Confidence: {s.dynamics.confidence:.3f}    Entropy: {s.dynamics.entropy:.3f}              ║
║    Momentum:   {s.dynamics.momentum:.3f}    Coherence: {s.dynamics.coherence:.3f}            ║
║                                                                   ║
║  STATE:                                                           ║
║    Dominant Bhava: {s.dominant_bhava:<15}                        ║
║    Vṛtti Mode:     {s.vritti_mode:<15}                           ║
║    det(R_int):     {s.determinant:.4f}                                   ║
║                                                                   ║
║  ALERTS: {s.alert.message if s.alert.message else "None":<50} ║
║                                                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""


# =============================================================================
# STREAMLIT APP ENTRY POINT
# =============================================================================

def create_demo_snapshot(step: int) -> StateSnapshot:
    """Create demo snapshot for testing."""
    import random
    import math

    # Simulate trace with some variation
    base_trace = 0.85
    noise = random.gauss(0, 0.05)
    # Occasional dips
    if step % 50 == 0:
        noise -= 0.3
    trace = max(0.0, min(1.0, base_trace + noise))

    # Simulate Bhava
    bhava = BhavaSnapshot(
        factual=0.3 + random.gauss(0, 0.1),
        analytical=0.2 + random.gauss(0, 0.1),
        speculative=0.1 + random.gauss(0, 0.1),
        sattvic=0.2 + random.gauss(0, 0.1),
    )

    from .data_stream import DynamicsSnapshot
    dynamics = DynamicsSnapshot(
        momentum=0.5 + random.gauss(0, 0.1),
        entropy=0.3 + random.gauss(0, 0.1),
        confidence=0.7 + random.gauss(0, 0.1),
        coherence=0.8 + random.gauss(0, 0.1),
    )

    return StateSnapshot(
        step=step,
        trace=trace,
        bhava=bhava,
        dynamics=dynamics,
        dominant_bhava='factual',
        vritti_mode='Pramāṇa',
        token_text=f"token_{step}",
    )


def run_demo_dashboard():
    """Run demo dashboard with simulated data."""
    if not STREAMLIT_AVAILABLE:
        print("Streamlit not installed. Install with: pip install streamlit plotly")
        return

    dashboard = PratyakshaDashboard()

    # Simulate some data
    for i in range(100):
        snapshot = create_demo_snapshot(i)
        dashboard.update(snapshot)

    dashboard.run_streamlit()


# Entry point for streamlit run
if __name__ == "__main__":
    run_demo_dashboard()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'TraceEKG',
    'BhavaRadar',
    'DynamicGauges',
    'AlertPanel',
    'OutputLog',
    'render_truth_meter',
    'PratyakshaDashboard',
    'run_demo_dashboard',
]
