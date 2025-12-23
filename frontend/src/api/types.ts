/**
 * Symbol-U Frontend API Types
 *
 * Aligned with backend presentation layer types:
 * - symbolu/presentation/types.py
 * - symbolu/presentation/config.py
 * - symbolu/adapter/dilchat_adapter.py
 */

// ============================================
// Tier Configuration Types
// ============================================

export type PresentationTier =
  | 'consumer'         // End users - simple, flow-optimized
  | 'power_user'       // Power users - insights, coherence metrics
  | 'admin';           // Admins/Developers - full dashboard, debugging

export type EngineTier =
  | 'enterprise_search'
  | 'enterprise_chat'
  | 'consumer'
  | 'development';

// ============================================
// Delivery & Confidence Types
// ============================================

export type DeliveryMode =
  | 'confident'      // Direct, assertive delivery
  | 'hedged'         // Qualified, tentative language
  | 'clarifying'     // Request user clarification
  | 'acknowledging'  // Acknowledge uncertainty
  | 'silent';        // Suppress output entirely

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'unknown';

// ============================================
// Badge & Hint Types
// ============================================

export interface Badge {
  name: string;
  icon: string;
  color: string;
  description?: string;
}

export interface Hint {
  text: string;
  type: 'insight' | 'action' | 'warning';
  actionLabel?: string;
}

// Badge metadata for rendering
export const BADGE_CONFIG: Record<string, Omit<Badge, 'name'>> = {
  coherent: { icon: 'check-circle', color: 'text-green-500', description: 'High coherence score' },
  grounded: { icon: 'anchor', color: 'text-blue-500', description: 'Well-grounded in context' },
  reflective: { icon: 'brain', color: 'text-purple-500', description: 'Deep reflection mode' },
  deep: { icon: 'layers', color: 'text-indigo-500', description: 'Multi-layer analysis' },
  practical: { icon: 'wrench', color: 'text-orange-500', description: 'Actionable response' },
  caution: { icon: 'alert-triangle', color: 'text-yellow-500', description: 'Needs attention' },
};

// ============================================
// Layer Data Types
// ============================================

export interface SymbolicLayer {
  fusion_score: number;
  selected_source: string;
  reasoning: string;
  theme?: string;
  archetype?: string;
  causal_patterns?: string[];
  meaning_vectors?: Record<string, number>;
}

export interface PracticalLayer {
  confidence: number;
  relevance: number;
  key_facts?: string[];
  constraints?: string[];
  procedures?: string[];
  coherence_score?: number;
}

export interface MirrorLayer {
  alignment_score: number;
  contradictions?: string[];
  entropy?: number;
  tensions?: string[];
}

export interface LayerData {
  symbolic: SymbolicLayer | null;
  practical: PracticalLayer | null;
  mirror: MirrorLayer | null;
}

// ============================================
// Coherence & Entropy Types
// ============================================

export interface CoherenceData {
  stability: number;
  drift: number;
  trend?: 'up' | 'down' | 'stable';
}

export interface EntropyMetrics {
  H_D: number;  // Domain entropy
  H_G: number;  // Global entropy
  H_K: number;  // Knowledge entropy
  H_norm: number;  // Normalized entropy
}

// ============================================
// Ontological Profile (10D)
// ============================================

export interface OntologicalDimensions {
  O1_THINKING: number;
  O2_FORMING: number;
  O3_ACTING: number;
  O4_TAGGING: number;
  O5_DIRECTING: number;
  O6_REASONING: number;
  O7_PURPOSING: number;
  O8_META_OBSERVING: number;
  O9_UNIFYING: number;
  O10_ABSOLVING: number;
}

export const ONTOLOGICAL_LABELS: Record<keyof OntologicalDimensions, string> = {
  O1_THINKING: 'Thinking',
  O2_FORMING: 'Forming',
  O3_ACTING: 'Acting',
  O4_TAGGING: 'Tagging',
  O5_DIRECTING: 'Directing',
  O6_REASONING: 'Reasoning',
  O7_PURPOSING: 'Purposing',
  O8_META_OBSERVING: 'Observing',
  O9_UNIFYING: 'Unifying',
  O10_ABSOLVING: 'Absolving',
};

// ============================================
// Session Types
// ============================================

export interface SessionPolicy {
  session_is_stable: boolean;
  session_is_fragmented: boolean;
  session_needs_grounding: boolean;
  session_recommended_style: string;
}

export interface SessionSummary {
  session_id: string;
  turn_count: number;
  avg_coherence: number;
  coherence_trend: 'improving' | 'declining' | 'stable';
  domain_distribution: Record<string, number>;
  highlights: string[];
}

export interface SessionState {
  session_id: string;
  domain: string;
  turn_count: number;
  coherence_history: number[];
  drift_history: number[];
  created_at: string;
}

// ============================================
// Request Types
// ============================================

export interface AnalyzeRequest {
  text: string;
  domain: string;
  user_id?: string;
  org_id?: string;
  metadata?: Record<string, unknown>;
}

export interface StartSessionRequest {
  domain: string;
  user_id?: string;
  org_id?: string;
}

export interface PreferenceRequest {
  user_id: string;
  preferred_interaction_mode: string;
}

// ============================================
// Response Types
// ============================================

export interface DILchatResponse {
  text: string;
  badges: string[];
  hints: string[];
  coherence: CoherenceData;
  domain: string;
  layers: {
    symbolic: string | null;
    practical: string | null;
    mirror: string | null;
  };
  session_policy: SessionPolicy;
  metadata: Record<string, unknown>;
}

export interface UnifiedResponse {
  unified_output: {
    text: string;
    layers: LayerData;
    entropy: EntropyMetrics;
    ontological_profile: OntologicalDimensions;
  };
  policy_flags: {
    delivery_mode: DeliveryMode;
    confidence: ConfidenceLevel;
    show_reasoning: boolean;
    escalate_to_human: boolean;
  };
  dilchat_payload: DILchatResponse;
}

export interface StartSessionResponse {
  session_id: string;
  domain: string;
  created_at: string;
}

// ============================================
// Dashboard Types
// ============================================

export interface DashboardData {
  session_id: string;
  turn_count: number;
  coherence_history: Array<{ turn: number; stability: number; drift: number }>;
  entropy_history: Array<{ turn: number; H_norm: number }>;
  risk_bands: {
    stability: 'low' | 'medium' | 'high';
    drift: 'low' | 'medium' | 'high';
    semantic: 'low' | 'medium' | 'high';
    motivation: 'low' | 'medium' | 'high';
  };
  timeline: Array<{
    turn: number;
    domain: string;
    coherence: number;
    highlights: string[];
  }>;
}

export interface WhatIfResult {
  original: {
    entropy: number;
    dominant_dimension: string;
  };
  simulated: {
    entropy: number;
    dominant_dimension: string;
  };
  preset: string;
  delta: number;
}

// ============================================
// Message Types (Frontend-only)
// ============================================

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  // Backend response data (assistant only)
  badges?: Badge[];
  hints?: Hint[];
  layers?: LayerData;
  coherence?: CoherenceData;
  deliveryMode?: DeliveryMode;
  metadata?: Record<string, unknown>;
}

// ============================================
// Tier Configuration
// ============================================

export interface TierConfig {
  tier: PresentationTier;
  label: string;
  description: string;
  features: {
    showBadges: boolean;
    showHints: boolean;
    showLayers: boolean;
    showCoherence: boolean;
    showEntropy: boolean;
    showOntological: boolean;
    showDashboard: boolean;
    showWhatIf: boolean;
    showDiagnostics: boolean;
  };
}

export const TIER_CONFIGS: Record<PresentationTier, TierConfig> = {
  consumer: {
    tier: 'consumer',
    label: 'Consumer',
    description: 'Simple chat experience with badges and hints',
    features: {
      showBadges: true,
      showHints: true,
      showLayers: false,
      showCoherence: true,
      showEntropy: false,
      showOntological: false,
      showDashboard: false,
      showWhatIf: false,
      showDiagnostics: false,
    },
  },
  power_user: {
    tier: 'power_user',
    label: 'Power User',
    description: 'Enhanced insights with layer analysis and metrics',
    features: {
      showBadges: true,
      showHints: true,
      showLayers: true,
      showCoherence: true,
      showEntropy: true,
      showOntological: true,
      showDashboard: false,
      showWhatIf: false,
      showDiagnostics: false,
    },
  },
  admin: {
    tier: 'admin',
    label: 'Admin',
    description: 'Full analytics dashboard with simulations',
    features: {
      showBadges: true,
      showHints: true,
      showLayers: true,
      showCoherence: true,
      showEntropy: true,
      showOntological: true,
      showDashboard: true,
      showWhatIf: true,
      showDiagnostics: true,
    },
  },
};
