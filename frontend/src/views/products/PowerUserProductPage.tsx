/**
 * Analyst Tier Product Page
 *
 * Detailed product page for the Analyst tier (Enterprise Chat) with comprehensive
 * feature descriptions focusing on insights, metrics, and layers.
 */

import React from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Layers,
  Eye,
  BarChart3,
  Brain,
  Sparkles,
  Target,
  Gauge,
  PanelRight,
  Activity,
  Zap,
  Settings,
  CheckCircle,
} from 'lucide-react';

interface PowerUserProductPageProps {
  onBack: () => void;
  onTryDemo: () => void;
}

export function PowerUserProductPage({ onBack, onTryDemo }: PowerUserProductPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-purple-950/20 to-slate-950 text-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-purple-500/10">
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
              className="px-5 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium hover:bg-purple-500 transition-colors"
            >
              Try Analyst Demo
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center shadow-lg shadow-purple-500/25">
              <Layers className="w-8 h-8 text-white" />
            </div>
            <div>
              <span className="text-purple-400 text-sm font-medium">TIER 2 · ENTERPRISE CHAT</span>
              <h1 className="text-4xl md:text-5xl font-bold">Analyst Experience</h1>
            </div>
          </div>
          <p className="text-xl text-gray-400 max-w-3xl mb-8">
            An enterprise chat experience for internal employees with deeper insights into response quality,
            semantic layers, and cognitive metrics. Understand the "why" behind every response.
          </p>
          <div className="flex gap-4">
            <button
              onClick={onTryDemo}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-purple-600 text-white font-medium hover:bg-purple-500 transition-colors"
            >
              <span>Try Demo</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Design Principles */}
      <section className="py-20 px-6 bg-purple-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Design Principles</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Balancing depth with usability for the curious mind
          </p>

          <div className="grid md:grid-cols-5 gap-6">
            {[
              {
                icon: Eye,
                title: 'Insight Depth',
                description: 'Surface meaningful metrics without overwhelming',
              },
              {
                icon: Layers,
                title: 'Progressive Disclosure',
                description: 'Show more details on demand',
              },
              {
                icon: BarChart3,
                title: 'Visual Clarity',
                description: 'Use charts and indicators for complex data',
              },
              {
                icon: Sparkles,
                title: 'Professional Aesthetic',
                description: 'Purple/violet theme for sophistication',
              },
              {
                icon: PanelRight,
                title: 'Dual-Panel Layout',
                description: 'Chat + Insights side-by-side',
              },
            ].map((principle, i) => (
              <div key={i} className="text-center">
                <div className="w-14 h-14 rounded-xl bg-purple-500/20 flex items-center justify-center mx-auto mb-4">
                  <principle.icon className="w-7 h-7 text-purple-400" />
                </div>
                <h3 className="font-semibold mb-2">{principle.title}</h3>
                <p className="text-sm text-gray-500">{principle.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Semantic Layer Tabs */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Semantic Layer Tabs</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Three layers of semantic understanding for every response
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Symbolic Layer */}
            <div className="bg-slate-900/60 border border-indigo-500/20 rounded-2xl p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                  <Sparkles className="w-6 h-6 text-indigo-400" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold">Symbolic</h3>
                  <p className="text-indigo-400 text-sm">WHY - Meaning & Themes</p>
                </div>
              </div>
              <p className="text-gray-400 mb-6">
                Understand the deeper meaning behind responses. View themes, archetypes,
                causal patterns, and meaning vectors.
              </p>
              <div className="bg-slate-800/50 rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Fusion Score</span>
                  <span className="text-indigo-400 font-mono">0.82</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Source</span>
                  <span className="text-gray-300">reasoning_model</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Theme</span>
                  <span className="text-gray-300">contemplative</span>
                </div>
              </div>
            </div>

            {/* Practical Layer */}
            <div className="bg-slate-900/60 border border-emerald-500/20 rounded-2xl p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                  <Target className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold">Practical</h3>
                  <p className="text-emerald-400 text-sm">WHAT/HOW - Actions & Facts</p>
                </div>
              </div>
              <p className="text-gray-400 mb-6">
                Focus on actionable information. Key facts, constraints, procedures,
                and coherence scores.
              </p>
              <div className="bg-slate-800/50 rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Confidence</span>
                  <span className="text-emerald-400 font-mono">0.78</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Relevance</span>
                  <span className="text-emerald-400 font-mono">0.85</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Coherence</span>
                  <span className="text-emerald-400 font-mono">0.82</span>
                </div>
              </div>
            </div>

            {/* Mirror Layer */}
            <div className="bg-slate-900/60 border border-purple-500/20 rounded-2xl p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center">
                  <Brain className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold">Mirror</h3>
                  <p className="text-purple-400 text-sm">Reflection - Contradictions</p>
                </div>
              </div>
              <p className="text-gray-400 mb-6">
                See tensions and contradictions. Alignment score, entropy levels,
                and identified tensions.
              </p>
              <div className="bg-slate-800/50 rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Alignment</span>
                  <span className="text-purple-400 font-mono">0.88</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Entropy</span>
                  <span className="text-purple-400 font-mono">0.32</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tensions</span>
                  <span className="text-gray-300">None detected</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Entropy Metrics */}
      <section className="py-20 px-6 bg-purple-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Entropy Metrics</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Four dimensions of entropy measurement for response analysis
          </p>

          <div className="max-w-2xl mx-auto bg-slate-900/60 border border-white/10 rounded-2xl p-8">
            <div className="space-y-6">
              {[
                { label: 'H_D (Domain)', value: 0.42, color: 'bg-blue-500', description: 'Domain-specific entropy' },
                { label: 'H_G (Global)', value: 0.38, color: 'bg-emerald-500', description: 'Global entropy' },
                { label: 'H_K (Knowledge)', value: 0.45, color: 'bg-purple-500', description: 'Knowledge entropy' },
                { label: 'H_norm (Normalized)', value: 0.41, color: 'bg-amber-500', description: 'Normalized entropy' },
              ].map((metric, i) => (
                <div key={i}>
                  <div className="flex justify-between items-center mb-2">
                    <div>
                      <span className="text-gray-300 font-medium">{metric.label}</span>
                      <span className="text-gray-500 text-sm ml-2">- {metric.description}</span>
                    </div>
                    <span className="text-gray-300 font-mono">{metric.value.toFixed(2)}</span>
                  </div>
                  <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${metric.color} transition-all duration-500`}
                      style={{ width: `${metric.value * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Ontological Profile */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">10D Ontological Profile</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Ten dimensions of cognitive processing, sorted by activation strength
          </p>

          <div className="max-w-3xl mx-auto bg-slate-900/60 border border-white/10 rounded-2xl p-8">
            <div className="mb-6">
              <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-400 text-sm font-medium">
                Dominant: O5_COGNITION
              </span>
            </div>

            <div className="space-y-3">
              {[
                { dim: 'O5_COGNITION', value: 0.62, label: 'Thinking' },
                { dim: 'O7_REASONING', value: 0.55, label: 'Reasoning' },
                { dim: 'O9_WITNESSES', value: 0.45, label: 'Observing' },
                { dim: 'O8_PURPOSE', value: 0.42, label: 'Purposing' },
                { dim: 'O6_AGENCY', value: 0.35, label: 'Directing' },
                { dim: 'O10_UNIFYING', value: 0.32, label: 'Unifying' },
                { dim: 'O4_TAGGING', value: 0.28, label: 'Tagging' },
                { dim: 'O4_STRUCTURE', value: 0.21, label: 'Forming' },
                { dim: 'O12_ABSOLVING', value: 0.18, label: 'Absolving' },
                { dim: 'O3_EXECUTION', value: 0.15, label: 'Acting' },
              ].map((item, i) => (
                <div
                  key={item.dim}
                  className={`flex items-center gap-4 ${i === 0 ? 'bg-purple-500/10 rounded-lg p-2 -mx-2' : ''}`}
                >
                  <span className="w-24 text-sm text-gray-400">{item.label}</span>
                  <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-violet-500 transition-all duration-500"
                      style={{ width: `${item.value * 100}%` }}
                    />
                  </div>
                  <span className="w-12 text-right text-sm font-mono text-gray-300">{item.value.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Insights Panel */}
      <section className="py-20 px-6 bg-purple-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Collapsible Insights Panel</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            320px side panel with all metrics, toggleable for focused chat mode
          </p>

          <div className="flex justify-center gap-4">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500/20 text-purple-400">
              <PanelRight className="w-5 h-5" />
              <span className="font-medium">Panel Open</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 text-gray-400">
              <PanelRight className="w-5 h-5" />
              <span>Panel Closed</span>
            </div>
          </div>

          <div className="mt-8 grid md:grid-cols-2 gap-6">
            {[
              { title: 'Response Coherence', description: 'Real-time stability and drift indicators' },
              { title: 'Entropy Breakdown', description: 'H_D, H_G, H_K, and normalized values' },
              { title: 'Ontological Profile', description: '10D cognitive dimension visualization' },
              { title: 'Click to Select', description: 'Click any message to see its insights' },
            ].map((feature, i) => (
              <div key={i} className="flex items-start gap-4 bg-slate-900/60 rounded-xl p-4">
                <CheckCircle className="w-5 h-5 text-purple-400 mt-0.5" />
                <div>
                  <h4 className="font-medium text-gray-200">{feature.title}</h4>
                  <p className="text-sm text-gray-500">{feature.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Enhanced Status Bar */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Enhanced Status Bar</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            52px two-row status bar with comprehensive session metrics
          </p>

          <div className="max-w-3xl mx-auto bg-slate-800/50 rounded-xl overflow-hidden">
            <div className="px-6 py-3 flex items-center justify-between border-b border-white/5">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <span className="text-sm text-gray-300">SESSION: Stable</span>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">COHERENCE:</span>
                  <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div className="w-[85%] h-full bg-green-500" />
                  </div>
                  <span className="text-xs font-mono text-gray-300">0.85 ↑</span>
                </div>
                <div className="text-xs text-gray-500">TURNS: <span className="text-gray-300">5</span></div>
              </div>
            </div>
            <div className="px-6 py-2 flex items-center justify-between text-xs">
              <span className="text-gray-500">Drift: <span className="text-gray-300">0.08</span></span>
              <span className="text-gray-500">Recommended Style: <span className="text-purple-400">deep</span></span>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-6">Ready to Explore Deeper Insights?</h2>
          <p className="text-gray-400 text-lg mb-8">
            Experience the Analyst tier with full layer analysis and metrics for internal employees.
          </p>
          <button
            onClick={onTryDemo}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-purple-600 text-white font-semibold hover:bg-purple-500 transition-all shadow-xl shadow-purple-500/25"
          >
            <span>Try Analyst Demo</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto text-center text-gray-500 text-sm">
          Symbol-U Analyst Tier | Enterprise Chat
        </div>
      </footer>
    </div>
  );
}
