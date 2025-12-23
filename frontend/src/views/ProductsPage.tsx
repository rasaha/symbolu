/**
 * Products Page
 *
 * Main product overview page showing all three tiers
 * with "Learn More" links to detailed tier pages.
 */

import React from 'react';
import {
  Layers,
  User,
  Shield,
  ArrowRight,
  ArrowLeft,
  CheckCircle,
  MessageSquare,
  BarChart3,
  Zap,
  Eye,
  Settings,
  Gauge,
  Brain,
  Target,
  Sparkles,
} from 'lucide-react';

interface ProductsPageProps {
  onBackToHome: () => void;
  onSelectProductTier: (tier: 'consumer' | 'power_user' | 'admin') => void;
  onTryDemo: (tier: 'consumer' | 'power_user' | 'admin') => void;
}

export function ProductsPage({ onBackToHome, onSelectProductTier, onTryDemo }: ProductsPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={onBackToHome}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm">Back to Home</span>
            </button>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <Layers className="w-4 h-4 text-white" />
              </div>
              <span className="font-semibold">Symbol-U Products</span>
            </div>
            <div className="w-24" /> {/* Spacer for centering */}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-16 px-6">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 mb-6">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-gray-300">Three Tiers, One Vision</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold mb-6">
            Choose Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">Experience Level</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Symbol-U offers three distinct experience tiers, each designed for different user needs.
            From simple chat to full analytics dashboard.
          </p>
        </div>
      </section>

      {/* Comparison Overview */}
      <section className="py-12 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-3 gap-8">
            {/* Consumer Tier */}
            <div className="relative group">
              <div className="absolute inset-0 bg-gradient-to-b from-blue-500/20 to-transparent rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative bg-slate-900/80 border border-white/10 rounded-3xl p-8 hover:border-blue-500/50 transition-all">
                {/* Icon */}
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mb-6 shadow-lg shadow-blue-500/25">
                  <User className="w-8 h-8 text-white" />
                </div>

                {/* Title */}
                <h2 className="text-2xl font-bold mb-2">Consumer</h2>
                <p className="text-blue-400 text-sm font-medium mb-4">Simple & Intuitive</p>

                {/* Description */}
                <p className="text-gray-400 mb-6">
                  A clean, focused chat experience designed for everyday users who want straightforward
                  interaction without technical complexity.
                </p>

                {/* Key Features */}
                <div className="space-y-3 mb-8">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-blue-400" />
                    <span className="text-gray-300">Conversational chat interface</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-blue-400" />
                    <span className="text-gray-300">Response quality badges</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-blue-400" />
                    <span className="text-gray-300">Actionable hint cards</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-blue-400" />
                    <span className="text-gray-300">Session status at a glance</span>
                  </div>
                </div>

                {/* Ideal For */}
                <div className="text-xs text-gray-500 mb-6">
                  <span className="font-medium text-gray-400">Ideal for:</span> End users, general conversations
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  <button
                    onClick={() => onSelectProductTier('consumer')}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-medium hover:bg-white/10 transition-colors"
                  >
                    Learn More
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onTryDemo('consumer')}
                    className="px-4 py-3 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-500 transition-colors"
                  >
                    Try Demo
                  </button>
                </div>
              </div>
            </div>

            {/* Power User Tier */}
            <div className="relative group">
              <div className="absolute inset-0 bg-gradient-to-b from-purple-500/20 to-transparent rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative bg-slate-900/80 border border-white/10 rounded-3xl p-8 hover:border-purple-500/50 transition-all">
                {/* Popular Badge */}
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-gradient-to-r from-purple-500 to-violet-500 text-white text-xs font-semibold">
                  MOST POPULAR
                </div>

                {/* Icon */}
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center mb-6 shadow-lg shadow-purple-500/25">
                  <Layers className="w-8 h-8 text-white" />
                </div>

                {/* Title */}
                <h2 className="text-2xl font-bold mb-2">Power User</h2>
                <p className="text-purple-400 text-sm font-medium mb-4">Enhanced Insights</p>

                {/* Description */}
                <p className="text-gray-400 mb-6">
                  Deep analytical experience with semantic layer views, coherence metrics,
                  and cognitive profiling for users who want to understand the "why".
                </p>

                {/* Key Features */}
                <div className="space-y-3 mb-8">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-purple-400" />
                    <span className="text-gray-300">Semantic layer tabs</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-purple-400" />
                    <span className="text-gray-300">Entropy metrics visualization</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-purple-400" />
                    <span className="text-gray-300">10D Ontological profile</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-purple-400" />
                    <span className="text-gray-300">Collapsible insights panel</span>
                  </div>
                </div>

                {/* Ideal For */}
                <div className="text-xs text-gray-500 mb-6">
                  <span className="font-medium text-gray-400">Ideal for:</span> Researchers, analysts, curious minds
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  <button
                    onClick={() => onSelectProductTier('power_user')}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-medium hover:bg-white/10 transition-colors"
                  >
                    Learn More
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onTryDemo('power_user')}
                    className="px-4 py-3 rounded-xl bg-purple-600 text-white font-medium hover:bg-purple-500 transition-colors"
                  >
                    Try Demo
                  </button>
                </div>
              </div>
            </div>

            {/* Admin Tier */}
            <div className="relative group">
              <div className="absolute inset-0 bg-gradient-to-b from-orange-500/20 to-transparent rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative bg-slate-900/80 border border-white/10 rounded-3xl p-8 hover:border-orange-500/50 transition-all">
                {/* Icon */}
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center mb-6 shadow-lg shadow-orange-500/25">
                  <Shield className="w-8 h-8 text-white" />
                </div>

                {/* Title */}
                <h2 className="text-2xl font-bold mb-2">Admin</h2>
                <p className="text-orange-400 text-sm font-medium mb-4">Full Analytics</p>

                {/* Description */}
                <p className="text-gray-400 mb-6">
                  Complete analytics dashboard with trend charts, risk assessment,
                  what-if simulations, and diagnostic tools for full pipeline visibility.
                </p>

                {/* Key Features */}
                <div className="space-y-3 mb-8">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-orange-400" />
                    <span className="text-gray-300">Coherence trend charts</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-orange-400" />
                    <span className="text-gray-300">Risk band analysis</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-orange-400" />
                    <span className="text-gray-300">What-if simulator</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-orange-400" />
                    <span className="text-gray-300">Full diagnostic panel</span>
                  </div>
                </div>

                {/* Ideal For */}
                <div className="text-xs text-gray-500 mb-6">
                  <span className="font-medium text-gray-400">Ideal for:</span> Admins, developers, analysts
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  <button
                    onClick={() => onSelectProductTier('admin')}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-medium hover:bg-white/10 transition-colors"
                  >
                    Learn More
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onTryDemo('admin')}
                    className="px-4 py-3 rounded-xl bg-orange-600 text-white font-medium hover:bg-orange-500 transition-colors"
                  >
                    Try Demo
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Comparison Table */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Feature Comparison</h2>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-4 px-4 text-gray-400 font-medium">Feature</th>
                  <th className="text-center py-4 px-4">
                    <span className="text-blue-400 font-semibold">Consumer</span>
                  </th>
                  <th className="text-center py-4 px-4">
                    <span className="text-purple-400 font-semibold">Power User</span>
                  </th>
                  <th className="text-center py-4 px-4">
                    <span className="text-orange-400 font-semibold">Admin</span>
                  </th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {[
                  { feature: 'Chat Interface', consumer: true, power: true, admin: true },
                  { feature: 'Response Badges', consumer: true, power: true, admin: true },
                  { feature: 'Hint Cards', consumer: true, power: true, admin: true },
                  { feature: 'Coherence Indicator', consumer: true, power: true, admin: true },
                  { feature: 'Semantic Layer Tabs', consumer: false, power: true, admin: true },
                  { feature: 'Entropy Metrics', consumer: false, power: true, admin: true },
                  { feature: 'Ontological Profile', consumer: false, power: true, admin: true },
                  { feature: 'Insights Panel', consumer: false, power: true, admin: true },
                  { feature: 'Trend Charts', consumer: false, power: false, admin: true },
                  { feature: 'Risk Band Analysis', consumer: false, power: false, admin: true },
                  { feature: 'Session Timeline', consumer: false, power: false, admin: true },
                  { feature: 'What-If Simulator', consumer: false, power: false, admin: true },
                  { feature: 'Diagnostic Info', consumer: false, power: false, admin: true },
                  { feature: 'Split View Mode', consumer: false, power: false, admin: true },
                ].map((row, i) => (
                  <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-3 px-4 text-gray-300">{row.feature}</td>
                    <td className="py-3 px-4 text-center">
                      {row.consumer ? (
                        <CheckCircle className="w-5 h-5 text-blue-400 mx-auto" />
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      {row.power ? (
                        <CheckCircle className="w-5 h-5 text-purple-400 mx-auto" />
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      {row.admin ? (
                        <CheckCircle className="w-5 h-5 text-orange-400 mx-auto" />
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-6">Ready to Get Started?</h2>
          <p className="text-gray-400 text-lg mb-8">
            Try any tier for free and experience the future of cognitive AI interaction.
          </p>
          <button
            onClick={onBackToHome}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold hover:from-indigo-500 hover:to-purple-500 transition-all shadow-xl shadow-indigo-500/25"
          >
            <span>Enter Demo</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto text-center text-gray-500 text-sm">
          Symbol-U Products | v0.1
        </div>
      </footer>
    </div>
  );
}
