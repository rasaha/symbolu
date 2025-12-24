/**
 * Explorer Tier Product Page
 *
 * Detailed product page for the Explorer tier (RAG Lookup) with comprehensive
 * feature descriptions, design principles, and component showcases.
 */

import React from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Search,
  Database,
  CheckCircle,
  Smartphone,
  Heart,
  Zap,
  Shield,
  Eye,
  Sparkles,
  BadgeCheck,
  Lightbulb,
  Activity,
  Settings,
} from 'lucide-react';

interface ConsumerProductPageProps {
  onBack: () => void;
  onTryDemo: () => void;
}

export function ConsumerProductPage({ onBack, onTryDemo }: ConsumerProductPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-blue-950/20 to-slate-950 text-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-blue-500/10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={onBack}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm">Back to Products</span>
            </button>
            <button
              onClick={onTryDemo}
              className="px-5 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors"
            >
              Try Explorer Demo
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
              <Search className="w-8 h-8 text-white" />
            </div>
            <div>
              <span className="text-blue-400 text-sm font-medium">TIER 1 · RAG LOOKUP</span>
              <h1 className="text-4xl md:text-5xl font-bold">Explorer Experience</h1>
            </div>
          </div>
          <p className="text-xl text-gray-400 max-w-3xl mb-8">
            A simple, intuitive knowledge search experience designed for users who want straightforward
            RAG-powered queries with quality indicators. Focus on finding answers, get clear feedback.
          </p>
          <div className="flex gap-4">
            <button
              onClick={onTryDemo}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-500 transition-colors"
            >
              <span>Try Demo</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Design Principles */}
      <section className="py-20 px-6 bg-blue-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Design Principles</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Every element is crafted with these core principles in mind
          </p>

          <div className="grid md:grid-cols-5 gap-6">
            {[
              {
                icon: Sparkles,
                title: 'Simplicity First',
                description: 'Remove all non-essential elements; focus on search',
              },
              {
                icon: Heart,
                title: 'Friendly & Approachable',
                description: 'Warm colors, soft edges, conversational tone',
              },
              {
                icon: Shield,
                title: 'Progressive Trust',
                description: 'Build confidence through clear feedback indicators',
              },
              {
                icon: Zap,
                title: 'Zero Learning Curve',
                description: 'Familiar chat patterns; no training required',
              },
              {
                icon: Smartphone,
                title: 'Mobile-First',
                description: 'Responsive design that works on all devices',
              },
            ].map((principle, i) => (
              <div key={i} className="text-center">
                <div className="w-14 h-14 rounded-xl bg-blue-500/20 flex items-center justify-center mx-auto mb-4">
                  <principle.icon className="w-7 h-7 text-blue-400" />
                </div>
                <h3 className="font-semibold mb-2">{principle.title}</h3>
                <p className="text-sm text-gray-500">{principle.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Core Features */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Core Features</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Everything you need for a seamless chat experience
          </p>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Message Bubbles */}
            <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                  <MessageSquare className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold">Search Interface</h3>
              </div>
              <p className="text-gray-400 mb-6">
                Clean, familiar message bubbles with clear visual distinction between user and assistant.
                Right-aligned user messages, left-aligned assistant responses.
              </p>
              {/* Mock UI */}
              <div className="bg-slate-800/50 rounded-xl p-4 space-y-3">
                <div className="flex justify-end">
                  <div className="bg-blue-600 text-white text-sm px-4 py-2 rounded-2xl rounded-br-md max-w-[80%]">
                    What is the meaning of life?
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="bg-slate-700 text-gray-200 text-sm px-4 py-2 rounded-2xl rounded-bl-md max-w-[80%]">
                    The meaning of life is a deeply personal question...
                  </div>
                </div>
              </div>
            </div>

            {/* Response Badges */}
            <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                  <BadgeCheck className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold">Response Badges</h3>
              </div>
              <p className="text-gray-400 mb-6">
                Visual indicators showing response quality at a glance. Six badge types help you
                understand the nature of each response.
              </p>
              {/* Badge Examples */}
              <div className="flex flex-wrap gap-2">
                {[
                  { name: 'coherent', color: 'text-green-400 bg-green-500/20', icon: '✓' },
                  { name: 'grounded', color: 'text-blue-400 bg-blue-500/20', icon: '⚓' },
                  { name: 'reflective', color: 'text-purple-400 bg-purple-500/20', icon: '💭' },
                  { name: 'deep', color: 'text-indigo-400 bg-indigo-500/20', icon: '◉' },
                  { name: 'practical', color: 'text-orange-400 bg-orange-500/20', icon: '🔧' },
                  { name: 'caution', color: 'text-yellow-400 bg-yellow-500/20', icon: '⚠' },
                ].map((badge) => (
                  <span
                    key={badge.name}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${badge.color}`}
                  >
                    <span>{badge.icon}</span>
                    {badge.name}
                  </span>
                ))}
              </div>
            </div>

            {/* Hint Cards */}
            <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                  <Lightbulb className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold">Hint Cards</h3>
              </div>
              <p className="text-gray-400 mb-6">
                Actionable insights that help guide the conversation. Three types of hints:
                insights, actions, and warnings.
              </p>
              {/* Hint Examples */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
                  <Lightbulb className="w-4 h-4" />
                  Consider exploring: self-awareness, consciousness
                </div>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-sm text-emerald-300">
                  <ArrowRight className="w-4 h-4" />
                  Try asking about specific examples
                </div>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-sm text-amber-300">
                  <Eye className="w-4 h-4" />
                  This topic may need clarification
                </div>
              </div>
            </div>

            {/* Status Bar */}
            <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                  <Activity className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold">Session Status</h3>
              </div>
              <p className="text-gray-400 mb-6">
                Compact status bar showing session health at a glance. See stability,
                coherence score, and turn count.
              </p>
              {/* Status Bar Mock */}
              <div className="bg-slate-800/50 rounded-lg px-4 py-3 flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-gray-300">Stable</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div className="w-[85%] h-full bg-green-500" />
                  </div>
                  <span className="text-gray-400 font-mono">0.85</span>
                </div>
                <span className="text-gray-500">5 turns</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Layout Specifications */}
      <section className="py-20 px-6 bg-blue-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Layout Specifications</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Carefully designed dimensions for optimal user experience
          </p>

          <div className="grid md:grid-cols-4 gap-6">
            {[
              { element: 'Header', height: '64px', note: 'Fixed top' },
              { element: 'Message Area', height: 'Flexible', note: 'Max 768px wide, scrollable' },
              { element: 'Input Area', height: 'Auto', note: 'Fixed bottom' },
              { element: 'Status Bar', height: '40px', note: 'Compact, fixed bottom' },
            ].map((spec, i) => (
              <div key={i} className="bg-slate-900/60 border border-white/10 rounded-xl p-6 text-center">
                <h3 className="font-semibold text-blue-400 mb-2">{spec.element}</h3>
                <p className="text-2xl font-bold mb-1">{spec.height}</p>
                <p className="text-xs text-gray-500">{spec.note}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Domain Support */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Domain Support</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Switch between domains to get context-aware responses
          </p>

          <div className="flex flex-wrap justify-center gap-3">
            {[
              'General', 'Philosophy', 'Ethics', 'Psychology',
              'Science', 'Technology', 'Business', 'Creative'
            ].map((domain) => (
              <span
                key={domain}
                className="px-4 py-2 rounded-lg bg-slate-800 border border-white/10 text-gray-300 text-sm"
              >
                {domain}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-6">Ready to Experience Explorer Tier?</h2>
          <p className="text-gray-400 text-lg mb-8">
            Start chatting with Symbol-U's simple, intuitive interface.
          </p>
          <button
            onClick={onTryDemo}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-500 transition-all shadow-xl shadow-blue-500/25"
          >
            <span>Try Explorer Demo</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto text-center text-gray-500 text-sm">
          Symbol-U Explorer Tier | RAG Lookup
        </div>
      </footer>
    </div>
  );
}
