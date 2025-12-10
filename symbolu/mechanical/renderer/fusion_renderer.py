"""
SOULPI Fusion Renderer v3.0
============================

The deterministic bridge between FusionEngine cognition and presentation layers.
Structures raw fusion output into three clean layers without LLM interpretation.

Core Purpose:
- Transform FusionOutput into structured, human-interpretable format
- Maintain 100% deterministic behavior (no LLM)
- Preserve meaning without modification
- Expose contradictions, don't resolve them

Architecture:
- Symbolic Layer: The "WHY" (theme, archetype, causal patterns, meaning vectors)
- Practical Layer: The "WHAT/HOW" (domain facts, constraints, procedures, coherence)
- Mirror-Truth Layer: Reflective synthesis (contradictions, entropy, tensions, alignment)

Operating Modes:
- minimal: practical layer only
- standard: all 3 layers (default)
- symbolic: symbolic expanded, practical condensed
- regulated: compliance-safe, minimal metaphors

Version: 3.0
Author: Rakesh Mohan (Symbol-U AGI)
Patent Protected: Core algorithms immutable
"""

import json
import hashlib
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import MapperProfile


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class RenderMode(Enum):
    """Operating modes for different use cases"""
    MINIMAL = "minimal"           # Practical layer only
    STANDARD = "standard"         # All 3 layers (default)
    SYMBOLIC = "symbolic"         # Symbolic expanded, practical condensed
    REGULATED = "regulated"       # Compliance-safe, minimal metaphors


class Domain(Enum):
    """Application domains with different rendering requirements"""
    GENERAL = "general"
    FINANCE = "finance"
    MEDICAL = "medical"
    LEGAL = "legal"
    EDUCATION = "education"
    PSYCHOLOGY = "psychology"


# Regulated domains requiring strict controls
REGULATED_DOMAINS = {Domain.FINANCE, Domain.MEDICAL, Domain.LEGAL}

# Layer weight defaults for mode overrides
MODE_WEIGHTS = {
    RenderMode.MINIMAL: {"symbolic": 0.0, "practical": 1.0, "mirror": 0.0},
    RenderMode.STANDARD: {"symbolic": 0.33, "practical": 0.34, "mirror": 0.33},
    RenderMode.SYMBOLIC: {"symbolic": 0.6, "practical": 0.2, "mirror": 0.2},
    RenderMode.REGULATED: {"symbolic": 0.1, "practical": 0.8, "mirror": 0.1}
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FusionOutput:
    """Input from FusionEngine (upstream module)"""
    query: str
    merged_response: str
    hrm_content: Dict[str, Any]
    lcm_content: Dict[str, Any]
    moe_content: Dict[str, Any]
    channel_weights: Dict[str, float]
    conflict_resolution: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class SymbolicLayer:
    """The 'WHY' - Theme, archetype, causal patterns, meaning vectors"""
    theme: str
    archetype: str
    causal_patterns: List[str]
    meaning_vectors: Dict[str, float]
    dominant_channel: str
    reasoning_depth: float
    
    def to_dict(self) -> Dict:
        return {
            "theme": self.theme,
            "archetype": self.archetype,
            "causal_patterns": self.causal_patterns,
            "meaning_vectors": self.meaning_vectors,
            "dominant_channel": self.dominant_channel,
            "reasoning_depth": self.reasoning_depth
        }


@dataclass
class PracticalLayer:
    """The 'WHAT/HOW' - Domain facts, constraints, procedures, coherence"""
    key_facts: List[str]
    constraints: List[str]
    procedures: List[str]
    coherence_score: float
    domain: str
    actionable_items: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "key_facts": self.key_facts,
            "constraints": self.constraints,
            "procedures": self.procedures,
            "coherence_score": self.coherence_score,
            "domain": self.domain,
            "actionable_items": self.actionable_items
        }


@dataclass
class MirrorTruthLayer:
    """Reflective synthesis - Contradictions, entropy, tensions, alignment"""
    contradictions: List[Dict[str, Any]]
    entropy_measures: Dict[str, float]
    tensions: List[str]
    alignment_score: float
    stability_indicator: str
    reflection: str
    
    def to_dict(self) -> Dict:
        return {
            "contradictions": self.contradictions,
            "entropy_measures": self.entropy_measures,
            "tensions": self.tensions,
            "alignment_score": self.alignment_score,
            "stability_indicator": self.stability_indicator,
            "reflection": self.reflection
        }


@dataclass
class RenderedOutput:
    """Final structured output from Fusion Renderer"""
    query: str
    mode: str
    symbolic_layer: Optional[SymbolicLayer]
    practical_layer: Optional[PracticalLayer]
    mirror_truth_layer: Optional[MirrorTruthLayer]
    metadata: Dict[str, Any]
    render_timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "mode": self.mode,
            "symbolic_layer": self.symbolic_layer.to_dict() if self.symbolic_layer else None,
            "practical_layer": self.practical_layer.to_dict() if self.practical_layer else None,
            "mirror_truth_layer": self.mirror_truth_layer.to_dict() if self.mirror_truth_layer else None,
            "metadata": self.metadata,
            "render_timestamp": self.render_timestamp
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ============================================================================
# FUSION RENDERER CORE
# ============================================================================

class FusionRenderer:
    """
    Deterministic bridge between FusionEngine and presentation layers.
    
    Algorithm (6 steps):
    1. Validate FusionOutput input
    2. Build Symbolic Layer (theme, archetype, patterns)
    3. Build Practical Layer (facts, constraints, actions)
    4. Build Mirror-Truth Layer (contradictions, tensions)
    5. Propagate metadata exactly
    6. Apply mode-specific rendering rules
    
    Constraints:
    - 100% deterministic (no LLM)
    - Preserve meaning without modification
    - Expose contradictions, don't resolve them
    - Metadata propagation exact
    """
    
    def __init__(
        self,
        mode: RenderMode = RenderMode.STANDARD,
        domain: Domain = Domain.GENERAL
    ):
        self.mode = mode
        self.domain = domain
        self.is_regulated = domain in REGULATED_DOMAINS
        
        # Mode-specific weights
        self.layer_weights = MODE_WEIGHTS[mode]
        
        # Statistics tracking
        self.stats = {
            "total_renders": 0,
            "mode_counts": {m.value: 0 for m in RenderMode},
            "avg_render_time_ms": 0.0
        }
    
    def render(self, fusion_output: FusionOutput) -> RenderedOutput:
        """
        Main rendering pipeline - transforms FusionOutput into RenderedOutput.
        
        Args:
            fusion_output: Raw output from FusionEngine
            
        Returns:
            RenderedOutput: Structured 3-layer output
        """
        start_time = datetime.now().timestamp()
        
        # Step 1: Validate input
        self._validate_input(fusion_output)
        
        # Step 2: Build Symbolic Layer
        symbolic_layer = None
        if self.layer_weights["symbolic"] > 0:
            symbolic_layer = self._build_symbolic_layer(fusion_output)
        
        # Step 3: Build Practical Layer
        practical_layer = None
        if self.layer_weights["practical"] > 0:
            practical_layer = self._build_practical_layer(fusion_output)
        
        # Step 4: Build Mirror-Truth Layer
        mirror_layer = None
        if self.layer_weights["mirror"] > 0:
            mirror_layer = self._build_mirror_truth_layer(fusion_output)
        
        # Step 5: Propagate metadata
        metadata = self._propagate_metadata(fusion_output)
        
        # Step 6: Apply mode overrides
        symbolic_layer, practical_layer, mirror_layer = self._apply_mode_overrides(
            symbolic_layer, practical_layer, mirror_layer
        )
        
        # Create output
        rendered = RenderedOutput(
            query=fusion_output.query,
            mode=self.mode.value,
            symbolic_layer=symbolic_layer,
            practical_layer=practical_layer,
            mirror_truth_layer=mirror_layer,
            metadata=metadata
        )
        
        # Update statistics
        render_time = (datetime.now().timestamp() - start_time) * 1000
        self._update_stats(render_time)
        
        return rendered
    
    # ========================================================================
    # LAYER BUILDERS
    # ========================================================================
    
    def _build_symbolic_layer(self, fusion_output: FusionOutput) -> SymbolicLayer:
        """
        Build the Symbolic Layer - the 'WHY'.
        
        Extracts:
        - Theme: Core meaning/purpose
        - Archetype: Universal pattern
        - Causal patterns: Cause-effect chains
        - Meaning vectors: Semantic dimensions
        - Dominant channel: Primary reasoning source
        - Reasoning depth: Abstraction level
        """
        # Extract theme from HRM (symbolic reasoning)
        theme = self._extract_theme(fusion_output.hrm_content)
        
        # Identify archetype from channel dominance
        archetype = self._identify_archetype(fusion_output.channel_weights)
        
        # Extract causal patterns from HRM
        causal_patterns = self._extract_causal_patterns(fusion_output.hrm_content)
        
        # Compute meaning vectors across channels
        meaning_vectors = self._compute_meaning_vectors(fusion_output)
        
        # Determine dominant channel
        dominant_channel = max(
            fusion_output.channel_weights.items(),
            key=lambda x: x[1]
        )[0]
        
        # Infer reasoning depth from HRM weight
        reasoning_depth = fusion_output.channel_weights.get("hrm", 0.0)
        
        return SymbolicLayer(
            theme=theme,
            archetype=archetype,
            causal_patterns=causal_patterns,
            meaning_vectors=meaning_vectors,
            dominant_channel=dominant_channel,
            reasoning_depth=reasoning_depth
        )
    
    def _build_practical_layer(self, fusion_output: FusionOutput) -> PracticalLayer:
        """
        Build the Practical Layer - the 'WHAT/HOW'.
        
        Extracts:
        - Key facts: Essential information
        - Constraints: Limitations/boundaries
        - Procedures: Step-by-step actions
        - Coherence score: Logical consistency
        - Domain: Application area
        - Actionable items: Concrete next steps
        """
        # Extract key facts from LCM (linguistic clarity)
        key_facts = self._extract_key_facts(fusion_output.lcm_content)
        
        # Extract constraints from MoE (domain expertise)
        constraints = self._extract_constraints(fusion_output.moe_content)
        
        # Extract procedures from MoE
        procedures = self._extract_procedures(fusion_output.moe_content)
        
        # Compute coherence from LCM weight
        coherence_score = fusion_output.channel_weights.get("lcm", 0.0)
        
        # Infer domain from MoE metadata
        domain = fusion_output.moe_content.get("domain", "general")
        
        # Extract actionable items
        actionable_items = self._extract_actionable_items(fusion_output)
        
        return PracticalLayer(
            key_facts=key_facts,
            constraints=constraints,
            procedures=procedures,
            coherence_score=coherence_score,
            domain=domain,
            actionable_items=actionable_items
        )
    
    def _build_mirror_truth_layer(self, fusion_output: FusionOutput) -> MirrorTruthLayer:
        """
        Build the Mirror-Truth Layer - reflective synthesis.
        
        Extracts:
        - Contradictions: Conflicts between channels
        - Entropy measures: Uncertainty/disorder
        - Tensions: Unresolved opposing forces
        - Alignment score: Channel agreement
        - Stability indicator: System state
        - Reflection: Meta-analysis
        """
        # Detect contradictions from conflict_resolution
        contradictions = fusion_output.conflict_resolution
        
        # Compute entropy measures
        entropy_measures = self._compute_entropy_measures(fusion_output)
        
        # Identify tensions between channels
        tensions = self._identify_tensions(fusion_output)
        
        # Compute alignment score
        alignment_score = self._compute_alignment(fusion_output.channel_weights)
        
        # Determine stability indicator
        stability_indicator = self._assess_stability(entropy_measures, alignment_score)
        
        # Generate reflection
        reflection = self._generate_reflection(
            contradictions, tensions, alignment_score
        )
        
        return MirrorTruthLayer(
            contradictions=contradictions,
            entropy_measures=entropy_measures,
            tensions=tensions,
            alignment_score=alignment_score,
            stability_indicator=stability_indicator,
            reflection=reflection
        )
    
    # ========================================================================
    # HELPER METHODS (DETERMINISTIC LOGIC)
    # ========================================================================
    
    def _extract_theme(self, hrm_content: Dict[str, Any]) -> str:
        """Extract core theme from HRM symbolic reasoning"""
        # Use HRM's primary reasoning or fallback to hash-based selection
        if "reasoning" in hrm_content:
            # Extract first sentence as theme
            text = hrm_content["reasoning"]
            sentences = text.split(".")
            if sentences:
                return sentences[0].strip() + "."
        
        # Fallback: deterministic theme from content hash
        content_hash = hashlib.md5(str(hrm_content).encode()).hexdigest()
        theme_index = int(content_hash[:8], 16) % 5
        themes = [
            "Exploration of possibilities",
            "Resolution of complexity",
            "Integration of perspectives",
            "Analysis of structure",
            "Synthesis of understanding"
        ]
        return themes[theme_index]
    
    def _identify_archetype(self, channel_weights: Dict[str, float]) -> str:
        """Identify universal pattern from channel dominance"""
        dominant = max(channel_weights.items(), key=lambda x: x[1])[0]
        
        archetype_map = {
            "hrm": "Philosopher - seeks deep understanding",
            "lcm": "Communicator - values clarity and precision",
            "moe": "Expert - applies domain knowledge"
        }
        
        return archetype_map.get(dominant, "Balanced - integrates multiple perspectives")
    
    def _extract_causal_patterns(self, hrm_content: Dict[str, Any]) -> List[str]:
        """Extract cause-effect chains from HRM reasoning"""
        patterns = []
        
        if "reasoning" in hrm_content:
            text = hrm_content["reasoning"]
            # Look for causal indicators
            causal_keywords = ["because", "therefore", "thus", "hence", "consequently"]
            sentences = text.split(".")
            
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in causal_keywords):
                    patterns.append(sentence.strip())
        
        # Ensure at least one pattern
        if not patterns:
            patterns.append("Direct causal relationship detected")
        
        return patterns[:3]  # Limit to top 3
    
    def _compute_meaning_vectors(self, fusion_output: FusionOutput) -> Dict[str, float]:
        """Compute semantic dimensions across channels"""
        vectors = {}
        
        # Abstractness: HRM weight
        vectors["abstractness"] = fusion_output.channel_weights.get("hrm", 0.0)
        
        # Clarity: LCM weight
        vectors["clarity"] = fusion_output.channel_weights.get("lcm", 0.0)
        
        # Practicality: MoE weight
        vectors["practicality"] = fusion_output.channel_weights.get("moe", 0.0)
        
        # Complexity: inverse of alignment (more channels = more complex)
        weights_std = np.std(list(fusion_output.channel_weights.values()))
        vectors["complexity"] = float(weights_std)
        
        return vectors
    
    def _extract_key_facts(self, lcm_content: Dict[str, Any]) -> List[str]:
        """Extract essential information from LCM"""
        facts = []
        
        if "content" in lcm_content:
            text = lcm_content["content"]
            sentences = text.split(".")
            
            # Extract declarative sentences
            for sentence in sentences[:5]:  # Limit to 5
                sentence = sentence.strip()
                if sentence and len(sentence) > 10:
                    facts.append(sentence + ".")
        
        return facts if facts else ["Core information preserved"]
    
    def _extract_constraints(self, moe_content: Dict[str, Any]) -> List[str]:
        """Extract limitations from MoE domain expertise"""
        constraints = []
        
        if "constraints" in moe_content:
            constraints = moe_content["constraints"]
        elif "content" in moe_content:
            # Look for constraint indicators
            text = moe_content["content"]
            constraint_keywords = ["must", "cannot", "limited", "restricted", "requires"]
            sentences = text.split(".")
            
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in constraint_keywords):
                    constraints.append(sentence.strip())
        
        return constraints[:3] if constraints else ["Standard constraints apply"]
    
    def _extract_procedures(self, moe_content: Dict[str, Any]) -> List[str]:
        """Extract step-by-step actions from MoE"""
        procedures = []
        
        if "procedures" in moe_content:
            procedures = moe_content["procedures"]
        elif "content" in moe_content:
            # Look for procedural indicators
            text = moe_content["content"]
            proc_keywords = ["first", "then", "next", "finally", "step"]
            sentences = text.split(".")
            
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in proc_keywords):
                    procedures.append(sentence.strip())
        
        return procedures[:3] if procedures else ["Follow standard procedures"]
    
    def _extract_actionable_items(self, fusion_output: FusionOutput) -> List[str]:
        """Extract concrete next steps from merged response"""
        items = []
        
        text = fusion_output.merged_response
        # Look for action verbs
        action_keywords = ["should", "must", "need to", "consider", "implement", "apply"]
        sentences = text.split(".")
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in action_keywords):
                items.append(sentence.strip())
        
        return items[:3] if items else ["Review and apply insights"]
    
    def _compute_entropy_measures(self, fusion_output: FusionOutput) -> Dict[str, float]:
        """Compute uncertainty/disorder measures"""
        measures = {}
        
        # Channel entropy: Shannon entropy of weights
        weights = list(fusion_output.channel_weights.values())
        weights_norm = np.array(weights) / sum(weights)
        measures["channel_entropy"] = float(-np.sum(weights_norm * np.log2(weights_norm + 1e-10)))
        
        # Conflict entropy: based on number of conflicts
        num_conflicts = len(fusion_output.conflict_resolution)
        measures["conflict_entropy"] = min(num_conflicts / 10.0, 1.0)
        
        # Response entropy: from metadata if available
        if "entropy" in fusion_output.metadata:
            measures["response_entropy"] = fusion_output.metadata["entropy"]
        else:
            measures["response_entropy"] = 0.5  # Default moderate
        
        return measures
    
    def _identify_tensions(self, fusion_output: FusionOutput) -> List[str]:
        """Identify unresolved opposing forces"""
        tensions = []
        
        # Check for conflicts
        for conflict in fusion_output.conflict_resolution:
            tension_desc = f"{conflict.get('source1', 'Channel A')} vs {conflict.get('source2', 'Channel B')}: {conflict.get('type', 'disagreement')}"
            tensions.append(tension_desc)
        
        # Check for weight imbalances
        weights = fusion_output.channel_weights
        max_weight = max(weights.values())
        min_weight = min(weights.values())
        
        if max_weight - min_weight > 0.5:
            tensions.append(f"Channel imbalance: dominant vs. suppressed perspectives")
        
        return tensions if tensions else ["System in equilibrium"]
    
    def _compute_alignment(self, channel_weights: Dict[str, float]) -> float:
        """
        Compute channel agreement score.
        
        Uses inverse of standard deviation:
        - Low std = high alignment (channels agree)
        - High std = low alignment (channels diverge)
        """
        weights = list(channel_weights.values())
        weights_std = np.std(weights)
        
        # Normalize to [0, 1] where 1 = perfect alignment
        alignment = 1.0 / (1.0 + weights_std)
        
        return float(alignment)
    
    def _assess_stability(
        self,
        entropy_measures: Dict[str, float],
        alignment_score: float
    ) -> str:
        """Determine system stability state"""
        avg_entropy = np.mean(list(entropy_measures.values()))
        
        if avg_entropy < 0.3 and alignment_score > 0.7:
            return "STABLE - Low entropy, high alignment"
        elif avg_entropy > 0.7 or alignment_score < 0.3:
            return "UNSTABLE - High entropy or low alignment"
        else:
            return "MODERATE - Balanced state"
    
    def _generate_reflection(
        self,
        contradictions: List[Dict[str, Any]],
        tensions: List[str],
        alignment_score: float
    ) -> str:
        """Generate meta-analysis of rendering"""
        if alignment_score > 0.8:
            base = "High coherence across reasoning channels."
        elif alignment_score > 0.5:
            base = "Moderate coherence with some divergence."
        else:
            base = "Significant divergence between channels."
        
        if contradictions:
            base += f" {len(contradictions)} conflict(s) detected and exposed."
        
        if len(tensions) > 2:
            base += " Multiple tensions remain unresolved."
        
        return base
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _validate_input(self, fusion_output: FusionOutput) -> None:
        """Validate FusionOutput structure"""
        required_fields = ["query", "merged_response", "hrm_content", 
                          "lcm_content", "moe_content", "channel_weights"]
        
        for field in required_fields:
            if not hasattr(fusion_output, field):
                raise ValueError(f"FusionOutput missing required field: {field}")
        
        # Validate channel weights sum
        total_weight = sum(fusion_output.channel_weights.values())
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"Channel weights must sum to 1.0, got {total_weight}")
    
    def _propagate_metadata(self, fusion_output: FusionOutput) -> Dict[str, Any]:
        """Propagate metadata exactly from FusionOutput"""
        metadata = fusion_output.metadata.copy()
        
        # Add rendering metadata
        metadata["render_mode"] = self.mode.value
        metadata["render_domain"] = self.domain.value
        metadata["is_regulated"] = self.is_regulated
        metadata["layer_weights"] = self.layer_weights
        
        return metadata
    
    def _apply_mode_overrides(
        self,
        symbolic: Optional[SymbolicLayer],
        practical: Optional[PracticalLayer],
        mirror: Optional[MirrorTruthLayer]
    ) -> Tuple[Optional[SymbolicLayer], Optional[PracticalLayer], Optional[MirrorTruthLayer]]:
        """Apply mode-specific rendering rules"""
        if self.mode == RenderMode.MINIMAL:
            # Only practical layer
            return None, practical, None
        
        elif self.mode == RenderMode.SYMBOLIC:
            # Expand symbolic, condense practical
            if practical:
                # Keep only top 2 facts and 1 action
                practical.key_facts = practical.key_facts[:2]
                practical.actionable_items = practical.actionable_items[:1]
            return symbolic, practical, mirror
        
        elif self.mode == RenderMode.REGULATED:
            # Minimize metaphors in symbolic layer
            if symbolic:
                # Use plain language for theme
                if "like" in symbolic.theme.lower() or "as" in symbolic.theme.lower():
                    symbolic.theme = "Core purpose identified"
                # Simplify archetype
                symbolic.archetype = symbolic.archetype.split("-")[0].strip()
            return symbolic, practical, mirror
        
        else:  # STANDARD
            return symbolic, practical, mirror
    
    def _update_stats(self, render_time_ms: float) -> None:
        """Update rendering statistics"""
        self.stats["total_renders"] += 1
        self.stats["mode_counts"][self.mode.value] += 1
        
        # Update average render time
        n = self.stats["total_renders"]
        old_avg = self.stats["avg_render_time_ms"]
        self.stats["avg_render_time_ms"] = (old_avg * (n - 1) + render_time_ms) / n
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rendering statistics"""
        return self.stats.copy()

    def apply_mapper_profile(
        self,
        rendered_output: RenderedOutput,
        mapper_profile: Optional["MapperProfile"]
    ) -> RenderedOutput:
        """
        Apply mapper profile modulation to rendered output.

        Modulates EXPRESSION only, not semantic truth.

        Rules:
        ------
        LCM Active (practical_bias high, resolution_level low):
            - Collapse symbolic layer (reduce complexity)
            - Prioritize concrete/task-oriented text in practical layer
            - Mirror-truth layer becomes minimal

        HRM Active (detail_bias high, resolution_level high):
            - Expand symbolic layer (add explanation + precision)
            - Increase specificity and nuance
            - Mirror-truth layer stays balanced

        LAM Active (reflective_bias high, arc_mode set):
            - Add long-arc framing to symbolic layer
            - Mirror-truth layer includes pattern/identity/trajectory markers

        Args:
            rendered_output: Original rendered output from render()
            mapper_profile: Mapper profile from MLCR/TTOR

        Returns:
            Modulated RenderedOutput (new instance)
        """
        if mapper_profile is None:
            return rendered_output

        # Create modulated copies of layers
        symbolic_layer = self._modulate_symbolic_layer(
            rendered_output.symbolic_layer,
            mapper_profile
        )

        practical_layer = self._modulate_practical_layer(
            rendered_output.practical_layer,
            mapper_profile
        )

        mirror_layer = self._modulate_mirror_layer(
            rendered_output.mirror_truth_layer,
            mapper_profile
        )

        # Create new rendered output with modulated layers
        return RenderedOutput(
            query=rendered_output.query,
            mode=rendered_output.mode,
            symbolic_layer=symbolic_layer,
            practical_layer=practical_layer,
            mirror_truth_layer=mirror_layer,
            metadata={
                **rendered_output.metadata,
                "mapper_profile_applied": mapper_profile.to_dict()
            },
            render_timestamp=rendered_output.render_timestamp
        )

    def _modulate_symbolic_layer(
        self,
        layer: Optional[SymbolicLayer],
        profile: "MapperProfile"
    ) -> Optional[SymbolicLayer]:
        """Modulate symbolic layer based on mapper profile."""
        if layer is None:
            return None

        # Phase 9: Apply Guna/Kosha resonance modulation FIRST
        # This provides subtle expression shaping before mapper-specific modulation
        if profile.guna_resonance_bias != 0.0 or profile.kosha_resonance_bias != 0.0:
            layer = self._apply_resonance_to_symbolic(layer, profile)

        # LCM: Collapse symbolic layer
        if profile.practical_bias > 0.6 and profile.resolution_level == "low":
            # Minimize symbolic content for LCM
            return SymbolicLayer(
                theme=self._simplify_text(layer.theme),
                archetype="Pragmatic - focuses on concrete outcomes",
                causal_patterns=layer.causal_patterns[:1],  # Keep only 1
                meaning_vectors={
                    k: v for k, v in layer.meaning_vectors.items()
                    if k == "practicality"
                },
                dominant_channel=layer.dominant_channel,
                reasoning_depth=max(0.2, layer.reasoning_depth - 0.3)
            )

        # HRM: Expand symbolic layer
        if profile.detail_bias > 0.6 and profile.resolution_level == "high":
            # Add granularity markers
            enhanced_theme = layer.theme
            if not any(marker in enhanced_theme for marker in ["specifically", "precisely", "in detail"]):
                enhanced_theme = f"{enhanced_theme} [Examined in detail]"

            return SymbolicLayer(
                theme=enhanced_theme,
                archetype=f"{layer.archetype} (high-resolution analysis)",
                causal_patterns=layer.causal_patterns + ["Fine-grained causal nuance detected"],
                meaning_vectors=layer.meaning_vectors,
                dominant_channel=layer.dominant_channel,
                reasoning_depth=min(1.0, layer.reasoning_depth + 0.2)
            )

        # LAM: Add long-arc framing
        if profile.reflective_bias > 0.6 and profile.arc_mode != "none":
            arc_theme = self._add_arc_framing(layer.theme, profile.arc_mode)
            arc_patterns = layer.causal_patterns + [
                self._get_arc_pattern_text(profile.arc_mode)
            ]

            return SymbolicLayer(
                theme=arc_theme,
                archetype=layer.archetype,
                causal_patterns=arc_patterns,
                meaning_vectors=layer.meaning_vectors,
                dominant_channel=layer.dominant_channel,
                reasoning_depth=layer.reasoning_depth
            )

        # Default: return unchanged
        return layer

    def _modulate_practical_layer(
        self,
        layer: Optional[PracticalLayer],
        profile: "MapperProfile"
    ) -> Optional[PracticalLayer]:
        """Modulate practical layer based on mapper profile."""
        if layer is None:
            return None

        # LCM: Prioritize concrete/actionable content
        if profile.practical_bias > 0.6 and profile.resolution_level == "low":
            return PracticalLayer(
                key_facts=layer.key_facts[:3],  # Keep top 3 only
                constraints=layer.constraints[:2],
                procedures=layer.procedures,
                coherence_score=min(1.0, layer.coherence_score + 0.1),
                domain=layer.domain,
                actionable_items=layer.actionable_items  # Keep all actionable items
            )

        # HRM: Expand with more detail
        if profile.detail_bias > 0.6 and profile.resolution_level == "high":
            enhanced_facts = [f"{fact} [with nuance]" for fact in layer.key_facts]

            return PracticalLayer(
                key_facts=enhanced_facts,
                constraints=layer.constraints,
                procedures=layer.procedures,
                coherence_score=layer.coherence_score,
                domain=layer.domain,
                actionable_items=layer.actionable_items
            )

        # Default: return unchanged
        return layer

    def _modulate_mirror_layer(
        self,
        layer: Optional[MirrorTruthLayer],
        profile: "MapperProfile"
    ) -> Optional[MirrorTruthLayer]:
        """Modulate mirror-truth layer based on mapper profile."""
        if layer is None:
            return None

        # Phase 9: Apply Kosha resonance modulation FIRST for reflective depth
        if profile.kosha_resonance_bias != 0.0:
            layer = self._apply_resonance_to_mirror(layer, profile)

        # LCM: Minimize mirror layer
        if profile.practical_bias > 0.6 and profile.resolution_level == "low":
            return MirrorTruthLayer(
                contradictions=[],
                entropy_measures={k: v for k, v in layer.entropy_measures.items() if v > 0.5},
                tensions=["Minimal reflection - focus on action"],
                alignment_score=layer.alignment_score,
                stability_indicator=layer.stability_indicator,
                reflection="Practical focus maintained."
            )

        # LAM: Add pattern/identity/trajectory markers
        if profile.reflective_bias > 0.6 and profile.arc_mode != "none":
            arc_markers = self._get_arc_markers(profile.arc_mode)
            enhanced_tensions = layer.tensions + arc_markers
            enhanced_reflection = f"{layer.reflection} {self._get_arc_reflection(profile.arc_mode)}"

            return MirrorTruthLayer(
                contradictions=layer.contradictions,
                entropy_measures=layer.entropy_measures,
                tensions=enhanced_tensions,
                alignment_score=layer.alignment_score,
                stability_indicator=layer.stability_indicator,
                reflection=enhanced_reflection
            )

        # Default: return unchanged
        return layer

    # Helper methods for mapper profile modulation

    def _simplify_text(self, text: str) -> str:
        """Simplify text for LCM."""
        # Remove bracketed content and complex phrases
        simplified = text.replace(" [", " - ").replace("]", "")
        return simplified.split(".")[0] + "."  # Keep first sentence only

    def _add_arc_framing(self, theme: str, arc_mode: str) -> str:
        """Add long-arc framing to theme."""
        arc_prefixes = {
            "temporal": "Across time and context: ",
            "identity": "In the context of identity evolution: ",
            "deep_context": "Within the broader pattern: "
        }
        prefix = arc_prefixes.get(arc_mode, "")
        return f"{prefix}{theme}"

    def _get_arc_pattern_text(self, arc_mode: str) -> str:
        """Get arc pattern text for symbolic layer."""
        patterns = {
            "temporal": "This fits a broader temporal pattern across sessions.",
            "identity": "This reflects ongoing identity development and evolution.",
            "deep_context": "This emerges from deep contextual understanding."
        }
        return patterns.get(arc_mode, "Long-arc pattern detected.")

    def _get_arc_markers(self, arc_mode: str) -> List[str]:
        """Get arc markers for mirror layer."""
        markers = {
            "temporal": ["Pattern continuity", "Temporal coherence"],
            "identity": ["Identity tension", "Self-concept evolution"],
            "deep_context": ["Trajectory contrast", "Context integration"]
        }
        return markers.get(arc_mode, ["Arc pattern present"])

    def _get_arc_reflection(self, arc_mode: str) -> str:
        """Get arc reflection text for mirror layer."""
        reflections = {
            "temporal": "Temporal patterns show coherence across sessions.",
            "identity": "Identity tensions reveal ongoing self-development.",
            "deep_context": "Deep context patterns suggest trajectory alignment."
        }
        return reflections.get(arc_mode, "Long-arc patterns detected.")

    def _apply_resonance_to_symbolic(
        self,
        layer: SymbolicLayer,
        profile: "MapperProfile"
    ) -> SymbolicLayer:
        """
        Apply Phase 9 Guna/Kosha resonance modulation to symbolic layer.

        Rules:
        - Positive guna_resonance_bias (> 0): Increase symbolic granularity markers
        - Negative guna_resonance_bias (< 0): Reduce symbolic embellishment
        - Positive kosha_resonance_bias (> 0): Increase mirror-truth reflective stitching
        - Negative kosha_resonance_bias (< 0): Reduce mirror-truth depth

        Args:
            layer: Symbolic layer to modulate
            profile: Mapper profile with resonance biases

        Returns:
            Modulated symbolic layer
        """
        theme = layer.theme
        archetype = layer.archetype
        causal_patterns = list(layer.causal_patterns)

        # Apply Guna resonance modulation
        if profile.guna_resonance_bias > 0:
            # Positive bias → increase symbolic granularity
            if "[symbolic nuance]" not in theme:
                theme = f"{theme} [symbolic nuance]"
        elif profile.guna_resonance_bias < 0:
            # Negative bias → reduce symbolic embellishment
            # Remove any bracketed embellishments
            import re
            theme = re.sub(r'\s*\[.*?\]', '', theme)

        # Apply Kosha resonance modulation (affects reflective depth)
        # This is subtle and only adds/removes pattern depth markers
        if profile.kosha_resonance_bias > 0:
            # Positive bias → add reflective pattern marker
            if len(causal_patterns) < 5:  # Don't over-add
                causal_patterns.append("Subtle reflective pattern detected")

        elif profile.kosha_resonance_bias < 0:
            # Negative bias → reduce pattern depth (remove last pattern if > 1)
            if len(causal_patterns) > 1:
                causal_patterns = causal_patterns[:-1]

        return SymbolicLayer(
            theme=theme,
            archetype=archetype,
            causal_patterns=causal_patterns,
            meaning_vectors=layer.meaning_vectors,
            dominant_channel=layer.dominant_channel,
            reasoning_depth=layer.reasoning_depth
        )

    def _apply_resonance_to_mirror(
        self,
        layer: MirrorTruthLayer,
        profile: "MapperProfile"
    ) -> MirrorTruthLayer:
        """
        Apply Phase 9 Kosha resonance modulation to mirror-truth layer.

        Rules:
        - Positive kosha_resonance_bias (> 0): Increase reflective depth
        - Negative kosha_resonance_bias (< 0): Reduce reflective depth

        Args:
            layer: Mirror-truth layer to modulate
            profile: Mapper profile with resonance biases

        Returns:
            Modulated mirror-truth layer
        """
        reflection = layer.reflection
        tensions = list(layer.tensions)

        # Apply Kosha resonance modulation
        if profile.kosha_resonance_bias > 0.05:
            # Positive bias → increase mirror-truth depth
            if "Reflective coherence" not in reflection:
                reflection = f"{reflection} Reflective coherence deepened."

        elif profile.kosha_resonance_bias < -0.05:
            # Negative bias → suppress reflective depth
            # Simplify reflection to first sentence only
            reflection = reflection.split('.')[0] + '.'

        return MirrorTruthLayer(
            contradictions=layer.contradictions,
            entropy_measures=layer.entropy_measures,
            tensions=tensions,
            alignment_score=layer.alignment_score,
            stability_indicator=layer.stability_indicator,
            reflection=reflection
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def render_fusion_output(
    fusion_output: FusionOutput,
    mode: RenderMode = RenderMode.STANDARD,
    domain: Domain = Domain.GENERAL
) -> RenderedOutput:
    """
    Convenience function to render FusionOutput.
    
    Args:
        fusion_output: Raw output from FusionEngine
        mode: Rendering mode
        domain: Application domain
        
    Returns:
        RenderedOutput: Structured 3-layer output
    """
    renderer = FusionRenderer(mode=mode, domain=domain)
    return renderer.render(fusion_output)


if __name__ == "__main__":
    # Simple test
    print("SOULPI Fusion Renderer v3.0")
    print("=" * 50)
    print("✓ Module loaded successfully")
    print(f"✓ Available modes: {[m.value for m in RenderMode]}")
    print(f"✓ Available domains: {[d.value for d in Domain]}")
    print("\nUse examples.py for usage examples")
