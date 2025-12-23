/**
 * Power User Tier Page
 *
 * TIER 2: Enhanced chat with insights and analytics
 * - Full chat interface with layer tabs
 * - Coherence metrics and trends
 * - Entropy visualization
 * - Ontological profile display
 * - Collapsible insights panel
 *
 * Target: Users who want deeper understanding
 * Backend: Uses /dilchat/analyze with ENTERPRISE_CHAT config
 */

import React, { useEffect, useRef, useState } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { Header } from '@/components/common/Header';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { InputArea } from '@/components/chat/InputArea';
import { SessionStatusBar } from '@/components/indicators/SessionStatusBar';
import { CoherenceIndicator } from '@/components/indicators/CoherenceIndicator';
import { EntropyMetrics } from '@/components/insights/EntropyMetrics';
import { OntologicalRadar } from '@/components/insights/OntologicalRadar';
import {
  MessageCircle,
  Sparkles,
  ChevronRight,
  ChevronLeft,
  Layers,
  Activity,
  Brain,
} from 'lucide-react';

export function PowerUserTierPage() {
  const {
    messages,
    isLoading,
    domain,
    coherence,
    turnCount,
    sessionPolicy,
    expandedMessageId,
    showInsightsPanel,
    sendMessage,
    setDomain,
    startSession,
    toggleMessageExpand,
    toggleInsightsPanel,
  } = useChatStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  // Start session on mount
  useEffect(() => {
    startSession('general');
  }, [startSession]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Get selected message for insights panel
  const selectedMessage = messages.find((m) => m.id === selectedMessageId && m.role === 'assistant');
  const latestAssistantMessage = [...messages].reverse().find((m) => m.role === 'assistant');

  // Mock entropy and ontological data (would come from unified response in real app)
  const mockEntropy = {
    H_D: 0.42,
    H_G: 0.38,
    H_K: 0.45,
    H_norm: 0.41,
  };

  const mockOntological = {
    O1_THINKING: 0.62,
    O2_FORMING: 0.21,
    O3_ACTING: 0.15,
    O4_TAGGING: 0.28,
    O5_DIRECTING: 0.35,
    O6_REASONING: 0.55,
    O7_PURPOSING: 0.42,
    O8_META_OBSERVING: 0.45,
    O9_UNIFYING: 0.32,
    O10_ABSOLVING: 0.18,
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-violet-50 flex flex-col">
      {/* Header */}
      <Header tier="power_user" showTierSelector={false} />

      <div className="flex-1 flex overflow-hidden">
        {/* Main Chat Area */}
        <main className={`flex-1 flex flex-col transition-all duration-300 ${showInsightsPanel ? 'mr-80' : ''}`}>
          {/* Metrics Bar */}
          <div className="bg-white/80 backdrop-blur border-b border-gray-200 px-4 py-2">
            <div className="max-w-3xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-purple-500" />
                  <span className="text-xs font-medium text-gray-500">Coherence:</span>
                  <CoherenceIndicator coherence={coherence} size="sm" />
                </div>
              </div>
              <button
                onClick={toggleInsightsPanel}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-100 text-purple-700 text-xs font-medium hover:bg-purple-200 transition-colors"
              >
                <Layers className="w-3.5 h-3.5" />
                Insights
                {showInsightsPanel ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Chat Area */}
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-4 py-6">
              {messages.length === 0 ? (
                /* Welcome State */
                <div className="h-full min-h-[400px] flex flex-col items-center justify-center text-center px-8">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center mb-6 shadow-lg">
                    <Brain className="w-10 h-10 text-white" />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800 mb-3">
                    Power User Experience
                  </h2>
                  <p className="text-gray-600 max-w-md mb-6">
                    Explore deeper insights with layer analysis, coherence metrics,
                    and ontological profiling. Click any response to see detailed breakdowns.
                  </p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {['Analyze consciousness', 'Explore ethical frameworks', 'Dive into epistemology'].map(
                      (prompt) => (
                        <button
                          key={prompt}
                          onClick={() => sendMessage(prompt)}
                          className="px-4 py-2 rounded-full bg-white border border-purple-200 text-sm text-purple-700 hover:bg-purple-50 hover:border-purple-300 transition-colors"
                        >
                          {prompt}
                        </button>
                      )
                    )}
                  </div>
                </div>
              ) : (
                /* Messages */
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      onClick={() => message.role === 'assistant' && setSelectedMessageId(message.id)}
                      className={`cursor-pointer rounded-xl transition-all ${
                        selectedMessageId === message.id
                          ? 'ring-2 ring-purple-300 ring-offset-2'
                          : ''
                      }`}
                    >
                      <MessageBubble
                        message={message}
                        tier="power_user"
                        isExpanded={expandedMessageId === message.id}
                        onToggleExpand={() => toggleMessageExpand(message.id)}
                      />
                    </div>
                  ))}
                  {isLoading && (
                    <div className="flex items-center gap-2 text-purple-500 text-sm animate-pulse">
                      <MessageCircle className="w-4 h-4" />
                      <span>Analyzing response...</span>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* Input Area */}
          <div className="max-w-3xl mx-auto w-full">
            <InputArea
              onSend={sendMessage}
              isLoading={isLoading}
              domain={domain}
              onDomainChange={setDomain}
              placeholder="Ask something profound..."
              showDomainSelector={true}
            />
          </div>

          {/* Status Bar */}
          <SessionStatusBar
            coherence={coherence}
            turnCount={turnCount}
            sessionPolicy={sessionPolicy}
            compact={false}
          />
        </main>

        {/* Insights Panel */}
        {showInsightsPanel && (
          <aside className="fixed right-0 top-16 bottom-0 w-80 bg-white border-l border-gray-200 overflow-y-auto shadow-lg">
            <div className="p-4 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-500" />
                Response Insights
              </h2>

              {selectedMessage || latestAssistantMessage ? (
                <>
                  {/* Coherence Card */}
                  <div className="bg-gray-50 rounded-lg p-3">
                    <h3 className="text-xs font-semibold text-gray-500 mb-2">COHERENCE</h3>
                    <CoherenceIndicator
                      coherence={(selectedMessage || latestAssistantMessage)?.coherence || null}
                      size="md"
                    />
                  </div>

                  {/* Entropy Metrics */}
                  <EntropyMetrics entropy={mockEntropy} />

                  {/* Ontological Profile */}
                  <OntologicalRadar dimensions={mockOntological} />
                </>
              ) : (
                <div className="text-center text-gray-400 py-8">
                  <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p className="text-sm">Send a message to see insights</p>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
