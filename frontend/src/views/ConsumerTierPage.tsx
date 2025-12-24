/**
 * Consumer Tier Page
 *
 * TIER 1: Simple, clean chat experience
 * - Basic chat interface with message bubbles
 * - Simple badges indicating response quality
 * - Hint cards for actionable insights
 * - Compact session status bar
 *
 * Target: End users who want straightforward interaction
 * Backend: Uses /dilchat/analyze with CONSUMER config
 */

import React, { useEffect, useRef } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { Header } from '@/components/common/Header';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { InputArea } from '@/components/chat/InputArea';
import { SessionStatusBar } from '@/components/indicators/SessionStatusBar';
import { MessageCircle, Sparkles } from 'lucide-react';

export function ConsumerTierPage() {
  const {
    messages,
    isLoading,
    domain,
    coherence,
    turnCount,
    sessionPolicy,
    sendMessage,
    setDomain,
    startSession,
  } = useChatStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Start session on mount
  useEffect(() => {
    startSession('general');
  }, [startSession]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex flex-col">
      {/* Header */}
      <Header tier="consumer" showTierSelector={false} />

      {/* Main Content */}
      <main className="flex-1 max-w-3xl w-full mx-auto flex flex-col">
        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            /* Welcome State */
            <div className="h-full flex flex-col items-center justify-center text-center px-8">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center mb-6 shadow-lg">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-3">
                Welcome to Symbol-U
              </h2>
              <p className="text-gray-600 max-w-md mb-6">
                Start a conversation and explore ideas together.
                I'll provide thoughtful responses with helpful insights.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {['What is consciousness?', 'Explain AI ethics', 'Tell me about creativity'].map(
                  (prompt) => (
                    <button
                      key={prompt}
                      onClick={() => sendMessage(prompt)}
                      className="px-4 py-2 rounded-full bg-white border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"
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
                <MessageBubble
                  key={message.id}
                  message={message}
                  tier="consumer"
                />
              ))}
              {isLoading && (
                <div className="flex items-center gap-2 text-gray-500 text-sm animate-pulse">
                  <MessageCircle className="w-4 h-4" />
                  <span>Symbol-U is thinking...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <InputArea
          onSend={sendMessage}
          isLoading={isLoading}
          domain={domain}
          onDomainChange={setDomain}
          placeholder="Ask me anything..."
          showDomainSelector={true}
        />

        {/* Status Bar */}
        <SessionStatusBar
          coherence={coherence}
          turnCount={turnCount}
          sessionPolicy={sessionPolicy}
          compact={true}
        />
      </main>

      {/* Footer */}
      <footer className="py-3 text-center text-xs text-gray-400">
        Symbol-U Consumer Experience v0.1
      </footer>
    </div>
  );
}
