/**
 * Chat Store - State Management for Symbol-U Chat
 *
 * Manages conversation state, messages, and session context
 * using Zustand for reactive state management.
 */

import { create } from 'zustand';
import { api } from '@/api/client';
import type {
  Message,
  Badge,
  Hint,
  CoherenceData,
  SessionPolicy,
  PresentationTier,
  BADGE_CONFIG,
  LayerData,
} from '@/api/types';

// ============================================
// Types
// ============================================

interface ChatState {
  // Session state
  sessionId: string | null;
  domain: string;
  tier: PresentationTier;
  insightMode: 'recent_memory' | 'domain_relative' | 'new_possibilities';

  // Message state
  messages: Message[];
  isLoading: boolean;

  // Session metrics
  coherence: CoherenceData | null;
  turnCount: number;
  sessionPolicy: SessionPolicy | null;

  // UI state
  expandedMessageId: string | null;
  showInsightsPanel: boolean;

  // Actions
  startSession: (domain: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  setDomain: (domain: string) => void;
  setTier: (tier: PresentationTier) => void;
  setInsightMode: (mode: ChatState['insightMode']) => void;
  toggleMessageExpand: (messageId: string) => void;
  toggleInsightsPanel: () => void;
  clearMessages: () => void;
  resetSession: () => void;
}

// ============================================
// Badge Processor
// ============================================

const BADGE_CONFIG_MAP: Record<string, { icon: string; color: string; description: string }> = {
  coherent: { icon: 'check-circle', color: 'text-green-500', description: 'High coherence score' },
  grounded: { icon: 'anchor', color: 'text-blue-500', description: 'Well-grounded in context' },
  reflective: { icon: 'brain', color: 'text-purple-500', description: 'Deep reflection mode' },
  deep: { icon: 'layers', color: 'text-indigo-500', description: 'Multi-layer analysis' },
  practical: { icon: 'wrench', color: 'text-orange-500', description: 'Actionable response' },
  caution: { icon: 'alert-triangle', color: 'text-yellow-500', description: 'Needs attention' },
};

function processBadges(badgeNames: string[]): Badge[] {
  return badgeNames.map((name) => ({
    name,
    icon: BADGE_CONFIG_MAP[name]?.icon || 'circle',
    color: BADGE_CONFIG_MAP[name]?.color || 'text-gray-500',
    description: BADGE_CONFIG_MAP[name]?.description,
  }));
}

function processHints(hintTexts: string[]): Hint[] {
  return hintTexts.map((text) => ({
    text,
    type: text.toLowerCase().includes('caution') ? 'warning' :
          text.toLowerCase().includes('explore') ? 'action' : 'insight',
  }));
}

// ============================================
// Store Implementation
// ============================================

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  sessionId: null,
  domain: 'general',
  tier: 'consumer',
  insightMode: 'domain_relative',
  messages: [],
  isLoading: false,
  coherence: null,
  turnCount: 0,
  sessionPolicy: null,
  expandedMessageId: null,
  showInsightsPanel: false,

  // Actions
  startSession: async (domain: string) => {
    try {
      const response = await api.startSession({ domain });
      set({
        sessionId: response.session_id,
        domain,
        messages: [],
        turnCount: 0,
        coherence: null,
        sessionPolicy: null,
      });
    } catch (error) {
      console.error('Failed to start session:', error);
      // Continue without session for graceful degradation
      set({ domain, messages: [], turnCount: 0 });
    }
  },

  sendMessage: async (text: string) => {
    const { sessionId, domain, tier, messages } = get();

    // Add user message immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      text,
      timestamp: new Date(),
    };

    set({
      messages: [...messages, userMessage],
      isLoading: true,
    });

    try {
      // Call appropriate API based on tier
      let response;
      if (tier === 'admin') {
        // Admin gets unified response
        const unified = await (sessionId
          ? api.analyzeInSession(sessionId, { text, domain })
          : api.analyze({ text, domain }));
        response = unified;
      } else {
        // Consumer and Power User get DILchat response
        response = sessionId
          ? await api.analyzeInSession(sessionId, { text, domain })
          : await api.analyze({ text, domain });
      }

      // Process response into assistant message
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        text: response.text,
        timestamp: new Date(),
        badges: processBadges(response.badges),
        hints: processHints(response.hints),
        coherence: response.coherence,
        layers: response.layers ? {
          symbolic: response.layers.symbolic ? JSON.parse(response.layers.symbolic) : null,
          practical: response.layers.practical ? JSON.parse(response.layers.practical) : null,
          mirror: response.layers.mirror ? JSON.parse(response.layers.mirror) : null,
        } : undefined,
        metadata: response.metadata,
      };

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
        coherence: response.coherence,
        turnCount: state.turnCount + 1,
        sessionPolicy: response.session_policy,
      }));
    } catch (error) {
      console.error('Failed to send message:', error);
      set({ isLoading: false });

      // Add error message
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        text: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        badges: [{ name: 'error', icon: 'alert-circle', color: 'text-red-500' }],
      };

      set((state) => ({
        messages: [...state.messages, errorMessage],
      }));
    }
  },

  setDomain: (domain: string) => set({ domain }),
  setTier: (tier: PresentationTier) => set({ tier }),
  setInsightMode: (insightMode) => set({ insightMode }),

  toggleMessageExpand: (messageId: string) => {
    set((state) => ({
      expandedMessageId: state.expandedMessageId === messageId ? null : messageId,
    }));
  },

  toggleInsightsPanel: () => {
    set((state) => ({ showInsightsPanel: !state.showInsightsPanel }));
  },

  clearMessages: () => set({ messages: [], turnCount: 0 }),

  resetSession: () => set({
    sessionId: null,
    messages: [],
    turnCount: 0,
    coherence: null,
    sessionPolicy: null,
    expandedMessageId: null,
  }),
}));
