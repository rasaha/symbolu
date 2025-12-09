"""
SOULPI v2.8.3 - LLM Integration Module
======================================

This module provides the integration layer between:
- SOULPI v2.8.3 Core Engine (deterministic analysis)
- LLM Renderer Enhancement Layer (presentation polish)

Version: 2.8.3
Author: Rakesh Mohan (Symbol-U AGI Patent)
"""

import os
import sys
from typing import Dict, Optional, Any
from dataclasses import dataclass

# Import LLM Renderer components
from soulpi_llm_renderer_v2_8_3_fixed import (
    LLMRenderer, RenderMode, Domain,
    CoreTruth, RenderContext, RenderedOutput,
    LLMProviderManager, IntegrityChecker, AuditLogger,
    SoulpiCoreIntegration, EmbeddingModel,
    REGULATED_DOMAINS
)

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class IntegrationConfig:
    """Configuration for SOULPI + LLM integration"""
    # LLM API Keys (set via environment or constructor)
    claude_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    grok_api_key: Optional[str] = None
    
    # Rendering defaults
    default_mode: RenderMode = RenderMode.STANDARD
    default_pipeline_mode: str = "hybrid"  # "deterministic" or "hybrid"
    
    # Embedding model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Audit logging
    enable_audit_logging: bool = True
    audit_log_file: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> 'IntegrationConfig':
        """Create config from environment variables"""
        return cls(
            claude_api_key=os.environ.get('ANTHROPIC_API_KEY'),
            openai_api_key=os.environ.get('OPENAI_API_KEY'),
            grok_api_key=os.environ.get('GROK_API_KEY'),
            audit_log_file=os.environ.get('SOULPI_AUDIT_LOG')
        )

# ============================================================================
# INTEGRATED SOULPI CLASS
# ============================================================================

class IntegratedSOULPI:
    """
    Integrated SOULPI system with optional LLM rendering
    
    This class combines:
    1. SOULPI v2.8.3 Core Engine (deterministic analysis)
    2. LLM Renderer (optional presentation enhancement)
    
    The system follows the "stylist, not thinker" principle:
    - Core analysis is always deterministic and patent-protected
    - LLM only polishes presentation (optional)
    - All safety gates apply before LLM is called
    """
    
    def __init__(
        self,
        config: Optional[IntegrationConfig] = None,
        core_engine=None  # SoulpiCoreEngine from v2.8.3
    ):
        """
        Initialize integrated SOULPI system
        
        Args:
            config: Integration configuration (uses defaults if None)
            core_engine: SOULPI v2.8.3 core engine instance
        """
        self.config = config or IntegrationConfig.from_environment()
        self.core_engine = core_engine
        
        # Initialize components
        self._init_components()
    
    def _init_components(self):
        """Initialize all integration components"""
        # LLM Provider Manager
        self.provider_manager = LLMProviderManager(
            claude_api_key=self.config.claude_api_key,
            openai_api_key=self.config.openai_api_key,
            grok_api_key=self.config.grok_api_key
        )
        
        # Embedding Model
        self.embedding_model = EmbeddingModel(self.config.embedding_model)
        
        # Integrity Checker
        self.integrity_checker = IntegrityChecker(self.embedding_model)
        
        # SOULPI Core Integration (for backward integrity)
        self.soulpi_integration = SoulpiCoreIntegration(self.core_engine)
        
        # LLM Renderer
        self.renderer = LLMRenderer(
            mode=self.config.default_mode,
            integrity_checker=self.integrity_checker,
            provider_manager=self.provider_manager,
            soulpi_integration=self.soulpi_integration,
            pipeline_mode=self.config.default_pipeline_mode
        )
        
        # Audit Logger
        if self.config.enable_audit_logging:
            self.audit_logger = AuditLogger(self.config.audit_log_file)
        else:
            self.audit_logger = None
    
    def analyze(
        self,
        text: str,
        domain: Domain = Domain.GENERAL,
        persona: str = "Witness",
        audience_level: str = "general",
        format_style: str = "narrative",
        enable_llm: bool = True,
        render_mode: Optional[RenderMode] = None,
        tone_weights: Optional[Dict[str, float]] = None,
        constraints: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Complete analysis with optional LLM rendering
        
        Args:
            text: Input text to analyze
            domain: Application domain (GENERAL, FINANCE, MEDICAL, etc.)
            persona: Analysis persona (Witness, Ego, Soul, etc.)
            audience_level: Target audience (executive, technical, general)
            format_style: Output format (narrative, bullet, table, report)
            enable_llm: Whether to use LLM rendering
            render_mode: Override default render mode
            tone_weights: DHA tone weights for provider routing
            constraints: Additional rendering constraints
        
        Returns:
            Dictionary with analysis results and rendered output
        """
        # Step 1: Core Analysis (Deterministic)
        if self.core_engine:
            core_result = self.core_engine.analyze(text)
            core_truth = self._convert_to_core_truth(text, core_result)
        else:
            # Demo/test mode without actual core engine
            core_truth = self._create_demo_core_truth(text)
        
        result = {
            "text": text,
            "core_analysis": {
                "smi": core_truth.smi,
                "bhava": core_truth.bhava,
                "bhava_direction": core_truth.bhava_direction,
                "persona": core_truth.persona,
                "kosha_profile": core_truth.kosha_profile,
                "ontology_profile": core_truth.ontology_profile,
                "entropy": core_truth.entropy,
                "mirror_time": core_truth.mirror_time,
                "ladder_layer": core_truth.ladder_layer
            },
            "core_truth_hash": core_truth.to_hash()
        }
        
        # Step 2: LLM Rendering (Optional)
        if enable_llm:
            context = RenderContext(
                domain=domain,
                persona=persona,
                audience_level=audience_level,
                format_style=format_style,
                tone_weights=tone_weights or {},
                constraints=constraints or []
            )
            
            # Override render mode if specified
            if render_mode:
                self.renderer.mode = render_mode
            
            rendered_output = self.renderer.render(core_truth, context)
            
            result["rendered"] = {
                "text": rendered_output.rendered_text,
                "mode": rendered_output.render_mode.value,
                "similarity_score": rendered_output.similarity_score,
                "integrity_hash": rendered_output.integrity_hash,
                "audit_trail": rendered_output.audit_trail
            }
            
            # Log if audit enabled
            if self.audit_logger:
                self.audit_logger.log_render_event(
                    "analyze_with_render",
                    core_truth,
                    rendered_output,
                    {"domain": domain.value, "enable_llm": enable_llm}
                )
        else:
            result["rendered"] = None
        
        return result
    
    def _convert_to_core_truth(self, text: str, core_result: Dict) -> CoreTruth:
        """Convert SOULPI core engine result to CoreTruth dataclass"""
        return CoreTruth(
            text=text,
            smi=core_result.get('smi', 0.0),
            bhava=core_result.get('bhava', 'Dharma'),
            bhava_direction=core_result.get('bhava_direction', 'neutral'),
            persona=core_result.get('persona', 'Witness'),
            kosha_profile=core_result.get('kosha_profile', {}),
            ontology_profile=core_result.get('ontology_profile', {}),
            entropy=core_result.get('entropy', 0.5),
            mirror_time=core_result.get('mirror_time', 0.5),
            ladder_layer=core_result.get('ladder_layer', 'Action')
        )
    
    def _create_demo_core_truth(self, text: str) -> CoreTruth:
        """Create demo CoreTruth when no core engine available"""
        # Simple heuristic-based analysis for demo
        word_count = len(text.split())
        char_count = len(text)
        
        return CoreTruth(
            text=text,
            smi=min(0.3 + (word_count * 0.01), 0.8),
            bhava="Dharma",
            bhava_direction="neutral",
            persona="Witness",
            kosha_profile={
                "Annamaya": 0.20,
                "Pranamaya": 0.20,
                "Manomaya": 0.25,
                "Vijnanamaya": 0.20,
                "Anandamaya": 0.15
            },
            ontology_profile={
                "Physical": 0.10,
                "Sensory": 0.10,
                "Emotional": 0.15,
                "Cognitive": 0.20,
                "Social": 0.15,
                "Economic": 0.10,
                "Ethical": 0.10,
                "Aesthetic": 0.05,
                "Existential": 0.05
            },
            entropy=0.5,
            mirror_time=0.5,
            ladder_layer="Action"
        )
    
    def set_pipeline_mode(self, mode: str):
        """
        Set pipeline mode for all subsequent analyses
        
        Args:
            mode: "deterministic" (no LLM) or "hybrid" (with LLM)
        """
        self.renderer.pipeline_mode = mode
    
    def set_render_mode(self, mode: RenderMode):
        """Set default render mode"""
        self.renderer.mode = mode
    
    def export_audit_report(self, output_file: str) -> str:
        """Export audit report to file"""
        if self.audit_logger:
            return self.audit_logger.export_audit_report(output_file)
        raise RuntimeError("Audit logging not enabled")

# ============================================================================
# ENTERPRISE DEPLOYMENT CLASS
# ============================================================================

class EnterpriseSOULPI(IntegratedSOULPI):
    """
    Enterprise-ready SOULPI with pre-configured safety settings
    
    Features:
    - Automatic domain detection
    - Strict validation for regulated domains
    - Complete audit trail
    - Compliance-ready logging
    """
    
    def __init__(
        self,
        domain: Domain = Domain.GENERAL,
        config: Optional[IntegrationConfig] = None,
        core_engine=None
    ):
        # Ensure audit logging is enabled for enterprise
        if config is None:
            config = IntegrationConfig.from_environment()
        config.enable_audit_logging = True
        
        # Set stricter defaults for regulated domains
        if domain in REGULATED_DOMAINS:
            config.default_mode = RenderMode.REGULATED
        
        super().__init__(config, core_engine)
        self.domain = domain
    
    def analyze(
        self,
        text: str,
        persona: str = "Witness",
        audience_level: str = "executive",
        **kwargs
    ) -> Dict[str, Any]:
        """Enterprise analysis with pre-configured domain"""
        return super().analyze(
            text,
            domain=self.domain,
            persona=persona,
            audience_level=audience_level,
            **kwargs
        )

# ============================================================================
# DEMO
# ============================================================================

def demo_integration():
    """Demonstrate integrated SOULPI system"""
    print("=" * 70)
    print("SOULPI v2.8.3 - Integrated System Demo")
    print("=" * 70)
    print()
    
    # Create integrated system (demo mode without actual core)
    soulpi = IntegratedSOULPI()
    
    # Test 1: General analysis with LLM
    print("TEST 1: General Analysis with LLM Rendering")
    print("-" * 50)
    result1 = soulpi.analyze(
        text="The market conditions require strategic adaptation.",
        domain=Domain.GENERAL,
        enable_llm=True
    )
    print(f"SMI: {result1['core_analysis']['smi']:.3f}")
    print(f"Bhava: {result1['core_analysis']['bhava']}")
    print(f"Render Mode: {result1['rendered']['mode']}")
    print()
    
    # Test 2: Finance domain (regulated)
    print("TEST 2: Finance Domain (Regulated)")
    print("-" * 50)
    result2 = soulpi.analyze(
        text="Q3 revenue exceeded expectations with 15% growth.",
        domain=Domain.FINANCE,
        enable_llm=True,
        render_mode=RenderMode.REGULATED
    )
    print(f"SMI: {result2['core_analysis']['smi']:.3f}")
    print(f"Bhava: {result2['core_analysis']['bhava']}")
    print(f"Render Mode: {result2['rendered']['mode']}")
    print()
    
    # Test 3: Deterministic mode (no LLM)
    print("TEST 3: Deterministic Mode (No LLM)")
    print("-" * 50)
    soulpi.set_pipeline_mode("deterministic")
    result3 = soulpi.analyze(
        text="Core analysis without LLM enhancement.",
        domain=Domain.GENERAL,
        enable_llm=True  # Will be overridden by pipeline mode
    )
    print(f"SMI: {result3['core_analysis']['smi']:.3f}")
    print(f"Render Mode: {result3['rendered']['mode']}")
    print()
    
    # Test 4: Enterprise deployment
    print("TEST 4: Enterprise Deployment (Finance)")
    print("-" * 50)
    enterprise = EnterpriseSOULPI(domain=Domain.FINANCE)
    result4 = enterprise.analyze(
        text="Investment strategy requires risk assessment."
    )
    print(f"SMI: {result4['core_analysis']['smi']:.3f}")
    print(f"Default Render Mode: {result4['rendered']['mode']}")
    print()
    
    print("=" * 70)
    print("Integration Demo Complete")
    print("=" * 70)

if __name__ == "__main__":
    demo_integration()
