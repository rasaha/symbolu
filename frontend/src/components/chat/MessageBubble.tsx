/**
 * Message Bubble Component
 *
 * Displays chat messages with tier-appropriate decorations.
 * Consumer: Basic badges and hints
 * Power User: + Layer tabs
 * Admin: + Full diagnostics
 */

import React, { useState } from 'react';
import type { Message, PresentationTier } from '@/api/types';
import { BadgeDisplay } from './BadgeDisplay';
import { HintCard } from './HintCard';
import { LayerTabs } from './LayerTabs';

interface MessageBubbleProps {
  message: Message;
  tier: PresentationTier;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

export function MessageBubble({
  message,
  tier,
  isExpanded = false,
  onToggleExpand,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const [activeTab, setActiveTab] = useState<'symbolic' | 'practical' | 'mirror'>('practical');

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${
          isUser
            ? 'bg-symbolu-primary text-white rounded-br-md'
            : 'bg-white border border-gray-200 rounded-bl-md'
        }`}
      >
        {/* Role Label */}
        <div className={`text-xs font-medium mb-1 ${isUser ? 'text-blue-100' : 'text-gray-400'}`}>
          {isUser ? 'You' : 'Symbol-U'}
        </div>

        {/* Message Text */}
        <div className={`text-sm leading-relaxed ${isUser ? 'text-white' : 'text-gray-800'}`}>
          {message.text}
        </div>

        {/* Assistant-only content */}
        {!isUser && (
          <div className="mt-3 space-y-2">
            {/* Badges (Consumer+) */}
            {message.badges && message.badges.length > 0 && (
              <BadgeDisplay badges={message.badges} />
            )}

            {/* Hints (Consumer+) */}
            {message.hints && message.hints.length > 0 && (
              <div className="space-y-1">
                {message.hints.map((hint, i) => (
                  <HintCard key={i} hint={hint} compact={tier === 'consumer'} />
                ))}
              </div>
            )}

            {/* Layer Tabs (Power User+) */}
            {(tier === 'power_user' || tier === 'admin') && message.layers && (
              <div className="mt-3 border-t border-gray-100 pt-3">
                <LayerTabs
                  layers={message.layers}
                  activeTab={activeTab}
                  onTabChange={setActiveTab}
                  showDetails={tier === 'admin'}
                />
              </div>
            )}

            {/* Expand Button (Power User+) */}
            {(tier === 'power_user' || tier === 'admin') && onToggleExpand && (
              <button
                onClick={onToggleExpand}
                className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 mt-2"
              >
                {isExpanded ? '▲ Collapse' : '▼ Details'}
              </button>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div
          className={`text-xs mt-2 ${isUser ? 'text-blue-200' : 'text-gray-400'}`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
}
