/**
 * Query Guide Modal
 *
 * A help popup that displays tier-specific example queries and use cases
 * to guide users on what to search for in the demo.
 */

import React, { useState } from 'react';
import {
  HelpCircle,
  X,
  MessageSquare,
  Layers,
  Shield,
  Copy,
  Check,
  Search,
  ChevronRight,
} from 'lucide-react';
import type { PresentationTier } from '@/api/types';

interface QueryGuideProps {
  tier: PresentationTier;
}

interface QueryCategory {
  name: string;
  description: string;
  queries: {
    text: string;
    feature: string;
  }[];
}

// Tier-specific query examples
const queryGuides: Record<PresentationTier, QueryCategory[]> = {
  consumer: [
    {
      name: 'General Questions',
      description: 'Start simple to see how responses are structured',
      queries: [
        { text: 'What is the meaning of life?', feature: 'Basic coherent response with badges' },
        { text: 'How can I improve my productivity?', feature: 'Practical advice with quality indicators' },
        { text: 'Explain quantum computing simply', feature: 'Complexity adaptation' },
      ],
    },
    {
      name: 'Trust & Quality',
      description: 'Watch for trust badges and confidence indicators',
      queries: [
        { text: 'Is climate change real?', feature: 'Trust badge visibility' },
        { text: 'What are the side effects of aspirin?', feature: 'Caution indicators for health topics' },
        { text: 'Should I invest in cryptocurrency?', feature: 'Uncertainty acknowledgment' },
      ],
    },
    {
      name: 'Hints & Guidance',
      description: 'See how hint cards suggest follow-up questions',
      queries: [
        { text: 'Tell me about machine learning', feature: 'Topic expansion hints' },
        { text: 'How do I start a business?', feature: 'Step-by-step guidance hints' },
        { text: 'What is meditation?', feature: 'Related topic suggestions' },
      ],
    },
  ],
  power_user: [
    {
      name: 'Semantic Layer Analysis',
      description: 'Explore the three semantic perspectives on your queries',
      queries: [
        { text: 'What is truth?', feature: 'Symbolic layer - philosophical interpretation' },
        { text: 'How do I cook pasta?', feature: 'Practical layer - actionable steps' },
        { text: 'Why do I feel anxious?', feature: 'Mirror layer - personal reflection' },
      ],
    },
    {
      name: 'Entropy Metrics',
      description: 'Observe how different queries affect entropy measurements',
      queries: [
        { text: 'Define the word "set"', feature: 'High H_D (domain entropy) - multiple meanings' },
        { text: 'What is 2 + 2?', feature: 'Low entropy - high certainty' },
        { text: 'What should I do with my life?', feature: 'High H_norm - normalized uncertainty' },
      ],
    },
    {
      name: 'Ontological Profile',
      description: 'See how queries activate different dimensions of the 10D profile',
      queries: [
        { text: 'Is stealing ever justified?', feature: 'Ethics dimension activation' },
        { text: 'Explain the theory of relativity', feature: 'Knowledge dimension' },
        { text: 'How do relationships work?', feature: 'Social/emotional dimensions' },
      ],
    },
    {
      name: 'Complex Reasoning',
      description: 'Test multi-step reasoning and layer coherence',
      queries: [
        { text: 'Compare democracy and authoritarianism', feature: 'Multi-perspective analysis' },
        { text: 'What are the pros and cons of AI?', feature: 'Balanced reasoning' },
        { text: 'How might society change in 50 years?', feature: 'Speculative synthesis' },
      ],
    },
  ],
  admin: [
    {
      name: 'Coherence Tracking',
      description: 'Monitor how coherence evolves across conversations',
      queries: [
        { text: 'Start with: Tell me about yourself', feature: 'Baseline coherence establishment' },
        { text: 'Follow up: What did we discuss?', feature: 'Context retention tracking' },
        { text: 'Challenge: That contradicts what you said', feature: 'Coherence stress testing' },
      ],
    },
    {
      name: 'Risk Band Analysis',
      description: 'Explore queries that trigger different risk levels',
      queries: [
        { text: 'How do I make a bomb?', feature: 'HIGH risk band - blocked content' },
        { text: 'Explain nuclear fission', feature: 'MEDIUM risk - educational context' },
        { text: 'What is chemistry?', feature: 'LOW risk - general knowledge' },
      ],
    },
    {
      name: 'Session Timeline',
      description: 'See how session events are tracked over time',
      queries: [
        { text: 'Ask multiple questions rapidly', feature: 'Response time tracking' },
        { text: 'Ask contradictory questions', feature: 'Persona drift detection' },
        { text: 'Request long detailed explanations', feature: 'Token usage patterns' },
      ],
    },
    {
      name: 'What-If Simulation',
      description: 'Test parameter adjustments and their effects',
      queries: [
        { text: 'Any query, then adjust "Confidence" slider', feature: 'Threshold sensitivity' },
        { text: 'Enable stricter governance mode', feature: 'Response restriction patterns' },
        { text: 'Simulate high entropy scenario', feature: 'Fallback behavior testing' },
      ],
    },
    {
      name: 'Diagnostic Deep Dive',
      description: 'Examine internal system metrics',
      queries: [
        { text: 'Ask a very long question (100+ words)', feature: 'Processing time analysis' },
        { text: 'Ask in different languages', feature: 'Multi-language handling' },
        { text: 'Use technical jargon', feature: 'Domain classification accuracy' },
      ],
    },
  ],
};

// Tier styling configuration
const tierConfig: Record<PresentationTier, { color: string; icon: React.ReactNode; name: string }> = {
  consumer: {
    color: 'blue',
    icon: <MessageSquare className="w-5 h-5" />,
    name: 'Consumer',
  },
  power_user: {
    color: 'purple',
    icon: <Layers className="w-5 h-5" />,
    name: 'Power User',
  },
  admin: {
    color: 'orange',
    icon: <Shield className="w-5 h-5" />,
    name: 'Admin',
  },
};

export function QueryGuide({ tier }: QueryGuideProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedQuery, setCopiedQuery] = useState<string | null>(null);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  const config = tierConfig[tier];
  const categories = queryGuides[tier];

  const handleCopy = (query: string) => {
    navigator.clipboard.writeText(query);
    setCopiedQuery(query);
    setTimeout(() => setCopiedQuery(null), 2000);
  };

  const colorClasses = {
    blue: {
      button: 'bg-blue-500/20 hover:bg-blue-500/30 text-blue-400',
      accent: 'text-blue-400',
      border: 'border-blue-500/30',
      bg: 'bg-blue-500/10',
      hover: 'hover:bg-blue-500/20',
    },
    purple: {
      button: 'bg-purple-500/20 hover:bg-purple-500/30 text-purple-400',
      accent: 'text-purple-400',
      border: 'border-purple-500/30',
      bg: 'bg-purple-500/10',
      hover: 'hover:bg-purple-500/20',
    },
    orange: {
      button: 'bg-orange-500/20 hover:bg-orange-500/30 text-orange-400',
      accent: 'text-orange-400',
      border: 'border-orange-500/30',
      bg: 'bg-orange-500/10',
      hover: 'hover:bg-orange-500/20',
    },
  };

  const colors = colorClasses[config.color as keyof typeof colorClasses];

  return (
    <>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${colors.button} transition-colors`}
        title="Query Guide"
      >
        <HelpCircle className="w-4 h-4" />
        <span className="text-sm font-medium">Query Guide</span>
      </button>

      {/* Modal Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
          />

          {/* Modal Content */}
          <div className="relative w-full max-w-2xl max-h-[80vh] bg-slate-900 border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Header */}
            <div className={`flex items-center justify-between p-6 border-b ${colors.border}`}>
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center ${colors.accent}`}>
                  {config.icon}
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">Query Guide</h2>
                  <p className="text-sm text-gray-400">{config.name} Tier Examples</p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* Introduction */}
              <div className={`p-4 rounded-xl ${colors.bg} ${colors.border} border`}>
                <div className="flex items-center gap-2 mb-2">
                  <Search className={`w-4 h-4 ${colors.accent}`} />
                  <span className="text-sm font-medium text-white">How to Use This Guide</span>
                </div>
                <p className="text-sm text-gray-400">
                  Try these example queries to explore the features of the {config.name} tier.
                  Click any query to copy it, then paste it into the chat to see the feature in action.
                </p>
              </div>

              {/* Categories */}
              {categories.map((category) => (
                <div key={category.name} className="border border-white/10 rounded-xl overflow-hidden">
                  {/* Category Header */}
                  <button
                    onClick={() => setExpandedCategory(
                      expandedCategory === category.name ? null : category.name
                    )}
                    className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
                  >
                    <div>
                      <h3 className="text-sm font-medium text-white text-left">{category.name}</h3>
                      <p className="text-xs text-gray-500 text-left">{category.description}</p>
                    </div>
                    <ChevronRight
                      className={`w-4 h-4 text-gray-400 transition-transform ${
                        expandedCategory === category.name ? 'rotate-90' : ''
                      }`}
                    />
                  </button>

                  {/* Category Queries */}
                  {expandedCategory === category.name && (
                    <div className="border-t border-white/10 p-4 space-y-3 bg-black/20">
                      {category.queries.map((query, idx) => (
                        <div
                          key={idx}
                          className={`group p-3 rounded-lg border ${colors.border} ${colors.hover} transition-colors cursor-pointer`}
                          onClick={() => handleCopy(query.text)}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1">
                              <p className="text-sm text-white mb-1">"{query.text}"</p>
                              <p className={`text-xs ${colors.accent}`}>{query.feature}</p>
                            </div>
                            <button
                              className={`p-1.5 rounded-md ${colors.bg} ${colors.accent} opacity-0 group-hover:opacity-100 transition-opacity`}
                              title="Copy query"
                            >
                              {copiedQuery === query.text ? (
                                <Check className="w-3.5 h-3.5" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/10 bg-slate-900/80">
              <p className="text-xs text-gray-500 text-center">
                Click on a query to copy it to your clipboard, then paste it into the chat input.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
