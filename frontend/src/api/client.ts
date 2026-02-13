/**
 * Symbol-U API Client
 *
 * Connects to backend presentation layer endpoints:
 * - /dilchat/analyze - DILchat-formatted analysis
 * - /symbolu/analyze - Full unified pipeline
 * - /session/* - Session management
 * - /sessions/*/dashboard - Analytics
 */

import type {
  AnalyzeRequest,
  DILchatResponse,
  UnifiedResponse,
  StartSessionRequest,
  StartSessionResponse,
  SessionSummary,
  DashboardData,
  WhatIfResult,
  PreferenceRequest,
} from './types';

// ============================================
// Configuration
// ============================================

const API_BASE = import.meta.env.VITE_API_URL || '/api';

interface ApiError {
  message: string;
  status: number;
  detail?: string;
}

class ApiClientError extends Error {
  status: number;
  detail?: string;

  constructor(error: ApiError) {
    super(error.message);
    this.name = 'ApiClientError';
    this.status = error.status;
    this.detail = error.detail;
  }
}

// ============================================
// Helper Functions
// ============================================

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiClientError({
      message: errorData.detail || `HTTP error ${response.status}`,
      status: response.status,
      detail: errorData.detail,
    });
  }
  return response.json();
}

function buildHeaders(additionalHeaders?: Record<string, string>): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...additionalHeaders,
  };
}

// ============================================
// API Client
// ============================================

export const api = {
  // ----------------------------------------
  // Analysis Endpoints
  // ----------------------------------------

  /**
   * Basic DILchat analysis - used for Consumer and Power User tiers
   */
  async analyze(request: AnalyzeRequest): Promise<DILchatResponse> {
    const response = await fetch(`${API_BASE}/dilchat/analyze`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(request),
    });
    return handleResponse<DILchatResponse>(response);
  },

  /**
   * Full unified analysis - used for Admin tier
   */
  async analyzeUnified(request: AnalyzeRequest): Promise<UnifiedResponse> {
    const response = await fetch(`${API_BASE}/symbolu/analyze`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(request),
    });
    return handleResponse<UnifiedResponse>(response);
  },

  // ----------------------------------------
  // Session Management
  // ----------------------------------------

  /**
   * Start a new conversation session
   */
  async startSession(request: StartSessionRequest): Promise<StartSessionResponse> {
    const response = await fetch(`${API_BASE}/session/start`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(request),
    });
    return handleResponse<StartSessionResponse>(response);
  },

  /**
   * Analyze within an existing session context
   */
  async analyzeInSession(
    sessionId: string,
    request: AnalyzeRequest
  ): Promise<DILchatResponse> {
    const response = await fetch(`${API_BASE}/session/${sessionId}/analyze`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(request),
    });
    return handleResponse<DILchatResponse>(response);
  },

  /**
   * Get session summary with trends
   */
  async getSessionSummary(sessionId: string): Promise<SessionSummary> {
    const response = await fetch(`${API_BASE}/session/${sessionId}/summary`);
    return handleResponse<SessionSummary>(response);
  },

  /**
   * End a session
   */
  async endSession(sessionId: string): Promise<void> {
    await fetch(`${API_BASE}/session/${sessionId}/end`, {
      method: 'POST',
      headers: buildHeaders(),
    });
  },

  // ----------------------------------------
  // Dashboard & Analytics
  // ----------------------------------------

  /**
   * Get dashboard data for a session
   */
  async getSessionDashboard(sessionId: string): Promise<DashboardData> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/dashboard`);
    return handleResponse<DashboardData>(response);
  },

  /**
   * Run what-if simulation
   */
  async runWhatIfSimulation(
    sessionId: string,
    preset: string
  ): Promise<WhatIfResult> {
    const response = await fetch(
      `${API_BASE}/sessions/${sessionId}/resonance/what_if?preset=${encodeURIComponent(preset)}`
    );
    return handleResponse<WhatIfResult>(response);
  },

  // ----------------------------------------
  // Preferences
  // ----------------------------------------

  /**
   * Set user preference for interaction mode
   */
  async setUserPreference(request: PreferenceRequest): Promise<void> {
    await fetch(`${API_BASE}/preferences/user`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(request),
    });
  },

  /**
   * Get user preference
   */
  async getUserPreference(userId: string): Promise<{ preferred_interaction_mode: string }> {
    const response = await fetch(`${API_BASE}/preferences/user/${userId}`);
    return handleResponse(response);
  },

  // ----------------------------------------
  // Demo Endpoints (for testing)
  // ----------------------------------------

  /**
   * Demo intent classification
   */
  async demoClassify(text: string, domain: string): Promise<{ intent: string; confidence: number }> {
    const response = await fetch(`${API_BASE}/demo/classify`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({ text, domain }),
    });
    return handleResponse(response);
  },

  /**
   * Demo semantic search
   */
  async demoSearch(query: string, domain: string): Promise<{ results: Array<{ text: string; score: number }> }> {
    const response = await fetch(`${API_BASE}/demo/search`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({ query, domain }),
    });
    return handleResponse(response);
  },

  // ----------------------------------------
  // Health Check
  // ----------------------------------------

  /**
   * Check API health
   */
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${API_BASE}/health`);
    return handleResponse(response);
  },

  // ----------------------------------------
  // Video Generation (Remotion + Phase Quad LLM)
  // ----------------------------------------

  /**
   * Generate a video from natural language description.
   * Uses Phase Quad LLM to generate Remotion TSX code.
   */
  async generateVideo(request: {
    description: string;
    template?: string | null;
    style?: Record<string, unknown> | null;
    duration_seconds?: number;
    fps?: number;
    output_format?: string;
    render?: boolean;
  }): Promise<{
    video_id: string;
    status: string;
    tsx_code: string;
    video_path: string | null;
    generation_time_ms: number;
    render_time_ms: number;
    total_time_ms: number;
    error: string | null;
    metadata: Record<string, unknown>;
  }> {
    const response = await fetch(`${API_BASE}/video/generate`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(request),
    });
    return handleResponse(response);
  },

  /**
   * Generate a coherence metrics visualization video
   */
  async generateCoherenceVideo(request: {
    session_id?: string | null;
    metrics?: Record<string, number> | null;
  }): Promise<{
    video_id: string;
    status: string;
    tsx_code: string;
    video_path: string | null;
    generation_time_ms: number;
    render_time_ms: number;
    total_time_ms: number;
    error: string | null;
    metadata: Record<string, unknown>;
  }> {
    const response = await fetch(`${API_BASE}/video/coherence`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(request),
    });
    return handleResponse(response);
  },

  /**
   * Get available video templates
   */
  async getVideoTemplates(): Promise<{ templates: Record<string, string> }> {
    const response = await fetch(`${API_BASE}/video/templates`);
    return handleResponse(response);
  },
};

export { ApiClientError };
export type { ApiError };
