/**
 * Developer Tier Product Page
 *
 * Detailed product page for the Developer tier (Customer Chat) with comprehensive
 * dashboard features, simulations, and diagnostic tools.
 */

import React from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Code,
  LayoutDashboard,
  LineChart,
  AlertTriangle,
  Clock,
  Play,
  Settings,
  Eye,
  Zap,
  BarChart3,
  PanelLeftClose,
  MessageSquare,
  SplitSquareHorizontal,
  Activity,
  Gauge,
  CheckCircle,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';

interface AdminProductPageProps {
  onBack: () => void;
  onTryDemo: () => void;
}

export function AdminProductPage({ onBack, onTryDemo }: AdminProductPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-orange-950/20 to-slate-950 text-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-orange-500/10">
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
              className="px-5 py-2 rounded-lg bg-orange-600 text-white text-sm font-medium hover:bg-orange-500 transition-colors"
            >
              Try Developer Demo
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center shadow-lg shadow-orange-500/25">
              <Code className="w-8 h-8 text-white" />
            </div>
            <div>
              <span className="text-orange-400 text-sm font-medium">TIER 3 · CUSTOMER CHAT</span>
              <h1 className="text-4xl md:text-5xl font-bold">Developer Console</h1>
            </div>
          </div>
          <p className="text-xl text-gray-400 max-w-3xl mb-8">
            Customer-facing chat with full analytics dashboard and comprehensive pipeline visibility.
            Complete diagnostic information, trend analysis, and simulation capabilities.
          </p>
          <div className="flex gap-4">
            <button
              onClick={onTryDemo}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-orange-600 text-white font-medium hover:bg-orange-500 transition-colors"
            >
              <span>Try Demo</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Design Principles */}
      <section className="py-20 px-6 bg-orange-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Design Principles</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Built for developers managing customer-facing chat with complete control and visibility
          </p>

          <div className="grid md:grid-cols-5 gap-6">
            {[
              {
                icon: Eye,
                title: 'Full Visibility',
                description: 'All metrics, diagnostics, and data accessible',
              },
              {
                icon: LayoutDashboard,
                title: 'Data-Dense Layout',
                description: 'Efficient use of space for multiple panels',
              },
              {
                icon: SplitSquareHorizontal,
                title: 'Flexible Views',
                description: 'Switch between chat, dashboard, or split view',
              },
              {
                icon: BarChart3,
                title: 'Actionable Analytics',
                description: 'Charts and simulations for decision making',
              },
              {
                icon: Shield,
                title: 'Professional/Technical',
                description: 'Orange/amber theme for developer tools',
              },
            ].map((principle, i) => (
              <div key={i} className="text-center">
                <div className="w-14 h-14 rounded-xl bg-orange-500/20 flex items-center justify-center mx-auto mb-4">
                  <principle.icon className="w-7 h-7 text-orange-400" />
                </div>
                <h3 className="font-semibold mb-2">{principle.title}</h3>
                <p className="text-sm text-gray-500">{principle.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* View Modes */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Three View Modes</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Switch between modes based on your current task
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Chat Mode */}
            <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8 text-center">
              <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mx-auto mb-6">
                <MessageSquare className="w-8 h-8 text-orange-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Chat Mode</h3>
              <p className="text-gray-400 mb-4">Full-width chat for active conversations</p>
              <div className="bg-slate-800/50 rounded-lg p-4 h-24 flex items-center justify-center">
                <div className="w-full h-full border-2 border-dashed border-gray-700 rounded flex items-center justify-center text-gray-500 text-sm">
                  100% Chat
                </div>
              </div>
            </div>

            {/* Split Mode */}
            <div className="bg-slate-900/60 border border-orange-500/30 rounded-2xl p-8 text-center ring-2 ring-orange-500/20">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-orange-500 text-white text-xs font-semibold">
                DEFAULT
              </div>
              <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mx-auto mb-6">
                <SplitSquareHorizontal className="w-8 h-8 text-orange-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Split View</h3>
              <p className="text-gray-400 mb-4">50/50 chat + dashboard side by side</p>
              <div className="bg-slate-800/50 rounded-lg p-4 h-24 flex gap-2">
                <div className="flex-1 border-2 border-dashed border-gray-700 rounded flex items-center justify-center text-gray-500 text-sm">
                  Chat
                </div>
                <div className="flex-1 border-2 border-dashed border-orange-500/50 rounded flex items-center justify-center text-orange-400 text-sm">
                  Dashboard
                </div>
              </div>
            </div>

            {/* Dashboard Mode */}
            <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8 text-center">
              <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mx-auto mb-6">
                <LayoutDashboard className="w-8 h-8 text-orange-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Dashboard Mode</h3>
              <p className="text-gray-400 mb-4">Full analytics for session analysis</p>
              <div className="bg-slate-800/50 rounded-lg p-4 h-24 flex items-center justify-center">
                <div className="w-full h-full border-2 border-dashed border-orange-500/50 rounded flex items-center justify-center text-orange-400 text-sm">
                  100% Dashboard
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Coherence Trend Charts */}
      <section className="py-20 px-6 bg-orange-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Coherence Trend Charts</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Track stability and drift over time with interactive line charts
          </p>

          <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-semibold text-gray-300">Coherence Over Turns</h3>
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="text-gray-400">Stability</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-orange-500" />
                  <span className="text-gray-400">Drift</span>
                </div>
              </div>
            </div>

            {/* Mock Chart */}
            <div className="relative h-48 border-l border-b border-gray-700">
              {/* Y-axis labels */}
              <div className="absolute -left-8 top-0 text-xs text-gray-500">1.0</div>
              <div className="absolute -left-8 top-1/2 text-xs text-gray-500">0.5</div>
              <div className="absolute -left-8 bottom-0 text-xs text-gray-500">0.0</div>

              {/* Chart lines (SVG simulation) */}
              <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
                {/* Stability line */}
                <polyline
                  points="0,60 50,40 100,50 150,35 200,30"
                  fill="none"
                  stroke="#22c55e"
                  strokeWidth="2"
                  className="opacity-80"
                />
                {/* Drift line */}
                <polyline
                  points="0,150 50,160 100,145 150,165 200,170"
                  fill="none"
                  stroke="#f97316"
                  strokeWidth="2"
                  className="opacity-80"
                />
              </svg>

              {/* X-axis labels */}
              <div className="absolute -bottom-6 left-0 w-full flex justify-between text-xs text-gray-500">
                <span>1</span>
                <span>2</span>
                <span>3</span>
                <span>4</span>
                <span>5</span>
              </div>
            </div>

            <div className="mt-8 text-center text-sm text-gray-500">
              Powered by Recharts - Interactive tooltips, zoom, and time range selection
            </div>
          </div>
        </div>
      </section>

      {/* Risk Bands */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Risk Band Analysis</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Four dimensions of risk assessment with clear visual indicators
          </p>

          <div className="max-w-2xl mx-auto space-y-4">
            {[
              { name: 'Stability Risk', level: 'LOW', color: 'green' },
              { name: 'Drift Risk', level: 'LOW', color: 'green' },
              { name: 'Semantic Risk', level: 'MEDIUM', color: 'amber' },
              { name: 'Motivation Risk', level: 'LOW', color: 'green' },
            ].map((risk, i) => (
              <div
                key={i}
                className={`flex items-center justify-between p-4 rounded-xl border ${
                  risk.color === 'green'
                    ? 'bg-green-500/10 border-green-500/20'
                    : risk.color === 'amber'
                    ? 'bg-amber-500/10 border-amber-500/20'
                    : 'bg-red-500/10 border-red-500/20'
                }`}
              >
                <span className="text-gray-300">{risk.name}</span>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-sm font-semibold ${
                      risk.color === 'green'
                        ? 'text-green-400'
                        : risk.color === 'amber'
                        ? 'text-amber-400'
                        : 'text-red-400'
                    }`}
                  >
                    {risk.level}
                  </span>
                  {risk.color === 'green' ? (
                    <CheckCircle className="w-5 h-5 text-green-400" />
                  ) : risk.color === 'amber' ? (
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                  )}
                </div>
              </div>
            ))}

            <div className="mt-6 p-4 rounded-xl bg-slate-800/50 text-center">
              <span className="text-gray-400">Overall Assessment: </span>
              <span className="text-green-400 font-semibold">All Clear ✓</span>
            </div>
          </div>
        </div>
      </section>

      {/* Session Timeline */}
      <section className="py-20 px-6 bg-orange-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Interactive Session Timeline</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Click any turn to view detailed metrics and highlights
          </p>

          <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-8">
            {/* Timeline */}
            <div className="relative py-8">
              <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gray-700 -translate-y-1/2" />
              <div className="flex justify-between relative">
                {[
                  { turn: 1, domain: 'phil', coh: 0.75, selected: false },
                  { turn: 2, domain: 'phil', coh: 0.82, selected: false },
                  { turn: 3, domain: 'ethics', coh: 0.79, selected: true },
                  { turn: 4, domain: 'ethics', coh: 0.85, selected: false },
                  { turn: 5, domain: 'ethics', coh: 0.88, selected: false },
                ].map((item) => (
                  <div key={item.turn} className="flex flex-col items-center">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm ${
                        item.coh >= 0.8
                          ? 'bg-green-500 border-2 border-green-600'
                          : item.coh >= 0.7
                          ? 'bg-amber-500 border-2 border-amber-600'
                          : 'bg-red-500 border-2 border-red-600'
                      } ${item.selected ? 'ring-2 ring-offset-2 ring-offset-slate-900 ring-orange-500' : ''}`}
                    >
                      {item.turn}
                    </div>
                    <span className="mt-2 text-xs text-gray-500">[{item.domain}]</span>
                    <span className="text-xs text-gray-400">coh:{item.coh}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Selected Turn Details */}
            <div className="mt-6 p-4 rounded-xl bg-slate-800/50">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-gray-200">Turn 3</span>
                <span className="text-xs px-2 py-1 rounded-full bg-gray-700 text-gray-300">ethics</span>
              </div>
              <p className="text-sm text-gray-400">Coherence: 0.79 | Domain shift from philosophy</p>
            </div>
          </div>
        </div>
      </section>

      {/* What-If Simulator */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">What-If Simulator</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Run hypothetical simulations with different presets
          </p>

          <div className="max-w-2xl mx-auto bg-slate-900/60 border border-white/10 rounded-2xl p-8">
            {/* Preset Selector */}
            <div className="flex items-center gap-4 mb-6">
              <span className="text-gray-400">Preset:</span>
              <select className="flex-1 px-4 py-2 rounded-lg bg-slate-800 border border-white/10 text-gray-200">
                <option>safety_first</option>
                <option>insight_heavy</option>
                <option>balanced</option>
                <option>performance</option>
                <option>creative</option>
                <option>analytical</option>
              </select>
              <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-600 text-white font-medium hover:bg-orange-500">
                <Play className="w-4 h-4" />
                Run
              </button>
            </div>

            <p className="text-sm text-gray-500 mb-8">Prioritize safety and reliability</p>

            {/* Results */}
            <div className="border-t border-white/10 pt-6">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <span className="text-xs text-gray-500">ORIGINAL</span>
                  <div className="text-3xl font-bold text-gray-200 mt-1">0.42</div>
                  <div className="text-sm text-gray-400">THINKING</div>
                </div>
                <div className="flex items-center justify-center">
                  <ArrowRight className="w-6 h-6 text-gray-500" />
                </div>
                <div>
                  <span className="text-xs text-gray-500">SIMULATED</span>
                  <div className="text-3xl font-bold text-green-400 mt-1">0.36</div>
                  <div className="text-sm text-gray-400">OBSERVING</div>
                </div>
              </div>

              <div className="mt-6 p-4 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center gap-3">
                <TrendingDown className="w-5 h-5 text-green-400" />
                <span className="text-sm text-green-300">
                  Entropy decreased by 0.06. This preset improves coherence.
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Diagnostic Information */}
      <section className="py-20 px-6 bg-orange-950/20">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Diagnostic Information</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Complete technical details for debugging and analysis
          </p>

          <div className="max-w-3xl mx-auto bg-slate-900/60 border border-white/10 rounded-2xl p-8">
            <div className="grid md:grid-cols-2 gap-6">
              {[
                { label: 'Engine Tier', value: 'DEVELOPMENT' },
                { label: 'Session ID', value: 'abc12345-6789-...' },
                { label: 'Domain', value: 'philosophy' },
                { label: 'Session Stable', value: 'Yes', highlight: true },
                { label: 'Config', value: 'show_reasoning=true' },
                { label: 'Needs Grounding', value: 'No' },
                { label: 'API Endpoint', value: '/symbolu/analyze' },
                { label: 'Recommended Style', value: 'analytical' },
              ].map((item, i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-gray-500">{item.label}</span>
                  <span className={`font-mono ${item.highlight ? 'text-green-400' : 'text-gray-300'}`}>
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Keyboard Shortcuts */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Keyboard Shortcuts</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Power user efficiency with keyboard navigation
          </p>

          <div className="max-w-md mx-auto grid grid-cols-2 gap-4">
            {[
              { key: '1', action: 'Switch to Chat' },
              { key: '2', action: 'Switch to Split' },
              { key: '3', action: 'Switch to Dashboard' },
              { key: 'R', action: 'Refresh dashboard' },
              { key: '← →', action: 'Navigate timeline' },
              { key: 'Enter', action: 'Run simulation' },
            ].map((shortcut, i) => (
              <div key={i} className="flex items-center gap-4 p-3 rounded-lg bg-slate-800/50">
                <kbd className="px-2 py-1 rounded bg-slate-700 text-orange-400 font-mono text-sm">
                  {shortcut.key}
                </kbd>
                <span className="text-gray-400 text-sm">{shortcut.action}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-6">Ready for Full Control?</h2>
          <p className="text-gray-400 text-lg mb-8">
            Experience the complete Developer console for customer chat with all analytics and simulation tools.
          </p>
          <button
            onClick={onTryDemo}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-orange-600 text-white font-semibold hover:bg-orange-500 transition-all shadow-xl shadow-orange-500/25"
          >
            <span>Try Developer Demo</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto text-center text-gray-500 text-sm">
          Symbol-U Developer Tier | Customer Chat
        </div>
      </footer>
    </div>
  );
}
