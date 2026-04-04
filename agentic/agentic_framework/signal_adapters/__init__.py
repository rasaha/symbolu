"""
Signal Adapters — Governance-time and output-time signal resolution.

These adapters bridge runtime signal modules (chitta_vritti, entropy,
DHA, guna_modulation, identity, motivation, temporal) into the
governance and output paths, with graceful fallback when real signals
are unavailable.

Phase 1: Governance signal rewiring.
Phase 2: Output modulation path wiring.
Phase 3: Session enrichment → governance integration.
"""

from agentic.agentic_framework.signal_adapters.vritti_adapter import (
    resolve_vritti_signal,
    VrittiResolution,
    VrittiSignalSource,
)
from agentic.agentic_framework.signal_adapters.entropy_adapter import (
    resolve_entropy_signal,
    EntropyResolution,
)
from agentic.agentic_framework.signal_adapters.output_modulation_adapter import (
    resolve_output_modulation,
    OutputModulationResolution,
)
from agentic.agentic_framework.signal_adapters.session_enrichment_adapter import (
    resolve_session_enrichment,
    SessionEnrichmentResolution,
)
from agentic.agentic_framework.signal_adapters.insight_adapter import (
    resolve_insight_signal,
    InsightResolution,
)
from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
    resolve_sovereign_health,
    SovereignHealthResolution,
)
from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
    resolve_guna_anomaly,
    GunaAnomalyResolution,
)
from agentic.agentic_framework.signal_adapters.coherence_state_adapter import (
    resolve_core_coherence,
    CoreCoherenceResolution,
)
from agentic.agentic_framework.signal_adapters.ucf_adapter import (
    resolve_ucf_signal,
    UCFResolution,
)
from agentic.agentic_framework.signal_adapters.predictive_signals_adapter import (
    resolve_predictive_signals,
    PredictiveSignalsResolution,
)
from agentic.agentic_framework.signal_adapters.counterfactual_bridge import (
    run_counterfactual_simulation,
    create_standard_scenarios,
    CounterfactualBridgeResult,
)
from agentic.agentic_framework.signal_adapters.ontology_adapter import (
    resolve_ontology_encoding,
    resolve_ontology_similarity,
    OntologyEncodingResolution,
    OntologySimilarityResolution,
)

__all__ = [
    "resolve_vritti_signal",
    "VrittiResolution",
    "VrittiSignalSource",
    "resolve_entropy_signal",
    "EntropyResolution",
    "resolve_output_modulation",
    "OutputModulationResolution",
    "resolve_session_enrichment",
    "SessionEnrichmentResolution",
    "resolve_insight_signal",
    "InsightResolution",
    "resolve_sovereign_health",
    "SovereignHealthResolution",
    "resolve_guna_anomaly",
    "GunaAnomalyResolution",
    "resolve_core_coherence",
    "CoreCoherenceResolution",
    "resolve_ucf_signal",
    "UCFResolution",
    "resolve_predictive_signals",
    "PredictiveSignalsResolution",
    "run_counterfactual_simulation",
    "create_standard_scenarios",
    "CounterfactualBridgeResult",
    # Ontology (O2)
    "resolve_ontology_encoding",
    "resolve_ontology_similarity",
    "OntologyEncodingResolution",
    "OntologySimilarityResolution",
]
