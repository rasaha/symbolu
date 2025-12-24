/**
 * Dashboard Store - State Management for Analytics Dashboard
 *
 * Manages dashboard data, what-if simulations, and session analytics
 * for the Admin tier view.
 */

import { create } from 'zustand';
import { api } from '@/api/client';
import type {
  DashboardData,
  WhatIfResult,
  SessionSummary,
} from '@/api/types';

// ============================================
// Types
// ============================================

interface DashboardState {
  // Data state
  dashboardData: DashboardData | null;
  sessionSummary: SessionSummary | null;
  whatIfResult: WhatIfResult | null;

  // UI state
  isLoading: boolean;
  selectedSessionId: string | null;
  selectedPreset: string;
  autoRefresh: boolean;
  refreshInterval: number;

  // Available presets
  presets: string[];

  // Actions
  loadDashboard: (sessionId: string) => Promise<void>;
  loadSessionSummary: (sessionId: string) => Promise<void>;
  runWhatIf: (sessionId: string, preset: string) => Promise<void>;
  setSelectedSession: (sessionId: string) => void;
  setSelectedPreset: (preset: string) => void;
  toggleAutoRefresh: () => void;
  setRefreshInterval: (interval: number) => void;
  clearDashboard: () => void;
}

// ============================================
// Store Implementation
// ============================================

export const useDashboardStore = create<DashboardState>((set, get) => ({
  // Initial state
  dashboardData: null,
  sessionSummary: null,
  whatIfResult: null,
  isLoading: false,
  selectedSessionId: null,
  selectedPreset: 'balanced',
  autoRefresh: false,
  refreshInterval: 5000,
  presets: [
    'safety_first',
    'insight_heavy',
    'balanced',
    'performance',
    'creative',
    'analytical',
  ],

  // Actions
  loadDashboard: async (sessionId: string) => {
    set({ isLoading: true, selectedSessionId: sessionId });
    try {
      const data = await api.getSessionDashboard(sessionId);
      set({ dashboardData: data, isLoading: false });
    } catch (error) {
      console.error('Failed to load dashboard:', error);
      set({ isLoading: false });

      // Set mock data for demo/development
      set({
        dashboardData: {
          session_id: sessionId,
          turn_count: 5,
          coherence_history: [
            { turn: 1, stability: 0.75, drift: 0.1 },
            { turn: 2, stability: 0.82, drift: 0.08 },
            { turn: 3, stability: 0.79, drift: 0.12 },
            { turn: 4, stability: 0.85, drift: 0.06 },
            { turn: 5, stability: 0.88, drift: 0.05 },
          ],
          entropy_history: [
            { turn: 1, H_norm: 0.45 },
            { turn: 2, H_norm: 0.42 },
            { turn: 3, H_norm: 0.44 },
            { turn: 4, H_norm: 0.38 },
            { turn: 5, H_norm: 0.36 },
          ],
          risk_bands: {
            stability: 'low',
            drift: 'low',
            semantic: 'medium',
            motivation: 'low',
          },
          timeline: [
            { turn: 1, domain: 'philosophy', coherence: 0.75, highlights: ['Initial exploration'] },
            { turn: 2, domain: 'philosophy', coherence: 0.82, highlights: ['Deepening insight'] },
            { turn: 3, domain: 'ethics', coherence: 0.79, highlights: ['Domain shift'] },
            { turn: 4, domain: 'ethics', coherence: 0.85, highlights: ['Stabilizing'] },
            { turn: 5, domain: 'ethics', coherence: 0.88, highlights: ['High coherence'] },
          ],
        },
      });
    }
  },

  loadSessionSummary: async (sessionId: string) => {
    try {
      const summary = await api.getSessionSummary(sessionId);
      set({ sessionSummary: summary });
    } catch (error) {
      console.error('Failed to load session summary:', error);
      // Set mock data
      set({
        sessionSummary: {
          session_id: sessionId,
          turn_count: 5,
          avg_coherence: 0.82,
          coherence_trend: 'improving',
          domain_distribution: { philosophy: 2, ethics: 3 },
          highlights: ['Strong coherence', 'Stable session'],
        },
      });
    }
  },

  runWhatIf: async (sessionId: string, preset: string) => {
    set({ isLoading: true });
    try {
      const result = await api.runWhatIfSimulation(sessionId, preset);
      set({ whatIfResult: result, isLoading: false });
    } catch (error) {
      console.error('Failed to run what-if:', error);
      // Set mock data
      set({
        whatIfResult: {
          original: { entropy: 0.42, dominant_dimension: 'O5_COGNITION' },
          simulated: { entropy: 0.36, dominant_dimension: 'O9_WITNESSES' },
          preset,
          delta: -0.06,
        },
        isLoading: false,
      });
    }
  },

  setSelectedSession: (sessionId: string) => set({ selectedSessionId: sessionId }),
  setSelectedPreset: (preset: string) => set({ selectedPreset: preset }),
  toggleAutoRefresh: () => set((state) => ({ autoRefresh: !state.autoRefresh })),
  setRefreshInterval: (interval: number) => set({ refreshInterval: interval }),

  clearDashboard: () => set({
    dashboardData: null,
    sessionSummary: null,
    whatIfResult: null,
    selectedSessionId: null,
  }),
}));
