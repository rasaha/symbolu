/**
 * Input Area Component
 *
 * Message input with domain selector and send button.
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface InputAreaProps {
  onSend: (text: string) => void;
  isLoading?: boolean;
  domain: string;
  onDomainChange: (domain: string) => void;
  placeholder?: string;
  showDomainSelector?: boolean;
}

const DOMAINS = [
  { value: 'general', label: 'General' },
  { value: 'philosophy', label: 'Philosophy' },
  { value: 'ethics', label: 'Ethics' },
  { value: 'psychology', label: 'Psychology' },
  { value: 'science', label: 'Science' },
  { value: 'technology', label: 'Technology' },
  { value: 'business', label: 'Business' },
  { value: 'creative', label: 'Creative' },
];

export function InputArea({
  onSend,
  isLoading = false,
  domain,
  onDomainChange,
  placeholder = 'Type your message...',
  showDomainSelector = true,
}: InputAreaProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [text]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim() && !isLoading) {
      onSend(text.trim());
      setText('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-gray-200 bg-white p-4">
      {/* Domain Selector */}
      {showDomainSelector && (
        <div className="flex items-center gap-2 mb-3">
          <label className="text-xs font-medium text-gray-500">Domain:</label>
          <select
            value={domain}
            onChange={(e) => onDomainChange(e.target.value)}
            className="text-xs px-2 py-1 rounded-md border border-gray-200 bg-gray-50 text-gray-700 focus:outline-none focus:ring-2 focus:ring-symbolu-primary/20"
          >
            {DOMAINS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Input Row */}
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isLoading}
            rows={1}
            className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-gray-800 text-sm placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-symbolu-primary/20 focus:border-symbolu-primary disabled:opacity-50"
          />
        </div>
        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          className="p-3 rounded-xl bg-symbolu-primary text-white hover:bg-symbolu-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Hint */}
      <p className="text-xs text-gray-400 mt-2">
        Press Enter to send, Shift+Enter for new line
      </p>
    </form>
  );
}
