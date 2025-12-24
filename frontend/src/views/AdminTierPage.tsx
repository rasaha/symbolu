/**
 * Admin Tier Page
 *
 * TIER 3: Full analytics dashboard with simulations
 * - Complete chat with all features
 * - Coherence trend charts
 * - Risk bands visualization
 * - Session timeline
 * - What-if simulator
 * - Diagnostic information
 *
 * Target: Admins and developers who need full visibility
 * Backend: Uses /symbolu/analyze with DEVELOPMENT config
 */

import React, { useEffect, useRef, useState } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useDashboardStore } from '@/stores/dashboardStore';
import { Header } from '@/components/common/Header';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { InputArea } from '@/components/chat/InputArea';
import { SessionStatusBar } from '@/components/indicators/SessionStatusBar';
import { CoherenceIndicator } from '@/components/indicators/CoherenceIndicator';
import { EntropyMetrics } from '@/components/insights/EntropyMetrics';
import { OntologicalRadar } from '@/components/insights/OntologicalRadar';
import { CoherenceTrendChart } from '@/components/dashboard/CoherenceTrendChart';
import { RiskBandsPanel } from '@/components/dashboard/RiskBandsPanel';
import { SessionTimeline } from '@/components/dashboard/SessionTimeline';
import { WhatIfSimulator } from '@/components/dashboard/WhatIfSimulator';
import {
  MessageCircle,
  LayoutDashboard,
  MessageSquare,
  BarChart3,
  Settings,
  RefreshCw,
} from 'lucide-react';

type ViewMode = 'chat' | 'dashboard' | 'split';

export function AdminTierPage() {
  const {
    messages,
    isLoading,
    domain,
    coherence,
    turnCount,
    sessionPolicy,
    sessionId,
    expandedMessageId,
    sendMessage,
    setDomain,
    startSession,
    toggleMessageExpand,
  } = useChatStore();

  const {
    dashboardData,
    whatIfResult,
    presets,
    selectedPreset,
    isLoading: dashboardLoading,
    loadDashboard,
    runWhatIf,
    setSelectedPreset,
  } = useDashboardStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [selectedTurn, setSelectedTurn] = useState<number | undefined>();

  // Start session on mount
  useEffect(() => {
    startSession('general');
  }, [startSession]);

  // Load dashboard when session changes
  useEffect(() => {
    if (sessionId) {
      loadDashboard(sessionId);
    }
  }, [sessionId, loadDashboard, turnCount]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Mock entropy and ontological data
  const mockEntropy = { H_D: 0.42, H_G: 0.38, H_K: 0.45, H_norm: 0.41 };
  const mockOntological = {
    O1_THINKING: 0.62, O2_FORMING: 0.21, O3_ACTING: 0.15, O4_TAGGING: 0.28,
    O5_DIRECTING: 0.35, O6_REASONING: 0.55, O7_PURPOSING: 0.42,
    O8_META_OBSERVING: 0.45, O9_UNIFYING: 0.32, O10_ABSOLVING: 0.18,
  };

  const handleRunWhatIf = () => {
    if (sessionId) {
      runWhatIf(sessionId, selectedPreset);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-amber-50 flex flex-col">
      {/* Header */}
      <Header tier="admin" showTierSelector={false} />

      {/* View Mode Toggle */}
      <div className="bg-white/80 backdrop-blur border-b border-gray-200 px-4 py-2">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode('chat')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                viewMode === 'chat'
                  ? 'bg-orange-100 text-orange-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Chat
            </button>
            <button
              onClick={() => setViewMode('split')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                viewMode === 'split'
                  ? 'bg-orange-100 text-orange-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              Split View
            </button>
            <button
              onClick={() => setViewMode('dashboard')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                viewMode === 'dashboard'
                  ? 'bg-orange-100 text-orange-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              Dashboard
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-xs text-gray-500">
              Session: <span className="font-mono text-gray-700">{sessionId?.slice(0, 8) || 'N/A'}</span>
            </div>
            <button
              onClick={() => sessionId && loadDashboard(sessionId)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            >
              <RefreshCw className={`w-4 h-4 ${dashboardLoading ? 'animate-spin' : ''}`} />
            </button>
            <Settings className="w-4 h-4 text-gray-400" />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Panel */}
        {(viewMode === 'chat' || viewMode === 'split') && (
          <div className={`flex flex-col ${viewMode === 'split' ? 'w-1/2 border-r border-gray-200' : 'flex-1'}`}>
            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
              {messages.length === 0 ? (
                <div className="h-full min-h-[300px] flex flex-col items-center justify-center text-center">
                  <LayoutDashboard className="w-16 h-16 text-orange-300 mb-4" />
                  <h3 className="text-lg font-semibold text-gray-700 mb-2">Admin Console</h3>
                  <p className="text-sm text-gray-500 max-w-sm">
                    Full visibility into the Symbol-U pipeline. Chat to generate data for analysis.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-w-2xl mx-auto">
                  {messages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      tier="admin"
                      isExpanded={expandedMessageId === message.id}
                      onToggleExpand={() => toggleMessageExpand(message.id)}
                    />
                  ))}
                  {isLoading && (
                    <div className="flex items-center gap-2 text-orange-500 text-sm animate-pulse">
                      <MessageCircle className="w-4 h-4" />
                      <span>Processing through unified pipeline...</span>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input */}
            <InputArea
              onSend={sendMessage}
              isLoading={isLoading}
              domain={domain}
              onDomainChange={setDomain}
              placeholder="Enter query for analysis..."
            />

            {/* Status Bar */}
            <SessionStatusBar
              coherence={coherence}
              turnCount={turnCount}
              sessionPolicy={sessionPolicy}
            />
          </div>
        )}

        {/* Dashboard Panel */}
        {(viewMode === 'dashboard' || viewMode === 'split') && (
          <div className={`overflow-y-auto bg-gray-50 ${viewMode === 'split' ? 'w-1/2' : 'flex-1'}`}>
            <div className="p-4 space-y-4">
              {/* Dashboard Header */}
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-800">Analytics Dashboard</h2>
                <div className="text-xs text-gray-500">
                  {dashboardData?.turn_count || 0} turns analyzed
                </div>
              </div>

              {/* Grid Layout */}
              <div className="grid grid-cols-2 gap-4">
                {/* Coherence Trend */}
                <div className="col-span-2">
                  <CoherenceTrendChart data={dashboardData?.coherence_history || []} />
                </div>

                {/* Risk Bands */}
                <RiskBandsPanel bands={dashboardData?.risk_bands || null} />

                {/* Entropy Metrics */}
                <EntropyMetrics entropy={mockEntropy} />

                {/* Session Timeline */}
                <div className="col-span-2">
                  <SessionTimeline
                    timeline={dashboardData?.timeline || []}
                    selectedTurn={selectedTurn}
                    onTurnSelect={setSelectedTurn}
                  />
                </div>

                {/* Ontological Profile */}
                <OntologicalRadar dimensions={mockOntological} />

                {/* What-If Simulator */}
                <WhatIfSimulator
                  presets={presets}
                  selectedPreset={selectedPreset}
                  onPresetChange={setSelectedPreset}
                  onRunSimulation={handleRunWhatIf}
                  result={whatIfResult}
                  isLoading={dashboardLoading}
                />
              </div>

              {/* Diagnostics Section */}
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-800 mb-3">Diagnostic Information</h3>
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-gray-500">Engine Tier:</span>
                    <span className="ml-2 font-mono text-gray-700">DEVELOPMENT</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Session ID:</span>
                    <span className="ml-2 font-mono text-gray-700">{sessionId || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Domain:</span>
                    <span className="ml-2 font-mono text-gray-700">{domain}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Session Stable:</span>
                    <span className={`ml-2 font-mono ${sessionPolicy?.session_is_stable ? 'text-green-600' : 'text-amber-600'}`}>
                      {sessionPolicy?.session_is_stable ? 'Yes' : 'No'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
