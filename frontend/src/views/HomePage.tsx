/**
 * Symbol-U Home Page
 *
 * Landing page that introduces Symbol-U's vision and capabilities,
 * with a demo button linking to the tier selector.
 */

import React from 'react';
import {
  Layers,
  Brain,
  Shield,
  Sparkles,
  ArrowRight,
  Zap,
  Eye,
  GitBranch,
  Lock,
  BarChart3,
  Search,
  Code,
  Package,
  MessageSquare,
  Users,
} from 'lucide-react';

interface HomePageProps {
  onEnterDemo: () => void;
  onGoToProducts?: () => void;
  onGoToInvestorRelations?: () => void;
}

export function HomePage({ onEnterDemo, onGoToProducts, onGoToInvestorRelations }: HomePageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white overflow-x-hidden">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                <Layers className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold">Symbol-U</span>
            </div>
            <div className="flex items-center gap-3">
              {onGoToProducts && (
                <button
                  onClick={onGoToProducts}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg text-gray-300 text-sm font-medium hover:text-white transition-colors"
                >
                  <Package className="w-4 h-4" />
                  Products
                </button>
              )}
              {onGoToInvestorRelations && (
                <button
                  onClick={onGoToInvestorRelations}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg text-gray-300 text-sm font-medium hover:text-white transition-colors"
                >
                  <Users className="w-4 h-4" />
                  Investors
                </button>
              )}
              <button
                onClick={onEnterDemo}
                className="px-5 py-2 rounded-lg bg-white/10 text-white text-sm font-medium hover:bg-white/20 transition-colors"
              >
                Try Demo
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6">
        {/* Background Effects */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/20 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-conic from-indigo-500/10 via-purple-500/10 to-indigo-500/10 rounded-full blur-2xl opacity-50" />
        </div>

        <div className="relative max-w-5xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 mb-8">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span className="text-sm text-gray-300">Cognitive Intelligence Framework</span>
          </div>

          {/* Main Heading */}
          <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-100 to-gray-300">
              Understanding Beyond
            </span>
            <br />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400">
              Language Models
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-xl md:text-2xl text-gray-400 max-w-3xl mx-auto mb-10 leading-relaxed">
            Symbol-U provides a structured cognitive substrate that brings{' '}
            <span className="text-white">coherence</span>,{' '}
            <span className="text-white">transparency</span>, and{' '}
            <span className="text-white">accountability</span> to AI interactions.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={onEnterDemo}
              className="group flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold text-lg hover:from-indigo-500 hover:to-purple-500 transition-all shadow-xl shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:scale-105"
            >
              <span>Enter Demo</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <a
              href="#vision"
              className="flex items-center gap-2 px-8 py-4 rounded-xl bg-white/5 border border-white/10 text-white font-medium text-lg hover:bg-white/10 transition-colors"
            >
              Learn More
            </a>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-8 mt-20 pt-10 border-t border-white/10">
            <div>
              <div className="text-4xl font-bold text-white mb-2">10D</div>
              <div className="text-gray-500 text-sm">Ontological Layers</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-white mb-2">3</div>
              <div className="text-gray-500 text-sm">Semantic Renderers</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-white mb-2">4</div>
              <div className="text-gray-500 text-sm">Engine Tiers</div>
            </div>
          </div>
        </div>
      </section>

      {/* Vision Section */}
      <section id="vision" className="py-24 px-6 bg-gradient-to-b from-transparent to-slate-900/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">The Vision</h2>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              A cognitive framework that understands not just <em>what</em> to say,
              but <em>why</em>, <em>how</em>, and <em>when</em>.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Vision Card 1 */}
            <div className="p-8 rounded-2xl bg-gradient-to-br from-white/5 to-white/0 border border-white/10 hover:border-indigo-500/30 transition-colors">
              <div className="w-14 h-14 rounded-xl bg-indigo-500/20 flex items-center justify-center mb-6">
                <Brain className="w-7 h-7 text-indigo-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Structured Cognition</h3>
              <p className="text-gray-400 leading-relaxed">
                Unlike black-box LLMs, Symbol-U processes through a 10-layer ontological substrate,
                providing traceable reasoning from input to output. Each layer has defined contracts
                and invariants.
              </p>
            </div>

            {/* Vision Card 2 */}
            <div className="p-8 rounded-2xl bg-gradient-to-br from-white/5 to-white/0 border border-white/10 hover:border-purple-500/30 transition-colors">
              <div className="w-14 h-14 rounded-xl bg-purple-500/20 flex items-center justify-center mb-6">
                <Eye className="w-7 h-7 text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Transparent Operations</h3>
              <p className="text-gray-400 leading-relaxed">
                Every response includes coherence metrics, entropy measurements, and semantic layer
                breakdowns. See exactly how conclusions are formed and confidence is calculated.
              </p>
            </div>

            {/* Vision Card 3 */}
            <div className="p-8 rounded-2xl bg-gradient-to-br from-white/5 to-white/0 border border-white/10 hover:border-emerald-500/30 transition-colors">
              <div className="w-14 h-14 rounded-xl bg-emerald-500/20 flex items-center justify-center mb-6">
                <Shield className="w-7 h-7 text-emerald-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Governed Output</h3>
              <p className="text-gray-400 leading-relaxed">
                Built-in governance gates ensure outputs meet quality thresholds. Configurable
                presentation tiers adapt behavior for enterprise, consumer, or development contexts.
              </p>
            </div>

            {/* Vision Card 4 */}
            <div className="p-8 rounded-2xl bg-gradient-to-br from-white/5 to-white/0 border border-white/10 hover:border-amber-500/30 transition-colors">
              <div className="w-14 h-14 rounded-xl bg-amber-500/20 flex items-center justify-center mb-6">
                <BarChart3 className="w-7 h-7 text-amber-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Session Intelligence</h3>
              <p className="text-gray-400 leading-relaxed">
                Track coherence trends, persona drift, and semantic stability across multi-turn
                conversations. Real-time analytics enable proactive session management.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Architecture Overview */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Architecture</h2>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              A multi-layer pipeline transforming raw input into structured, auditable output.
            </p>
          </div>

          {/* Pipeline Visualization */}
          <div className="relative">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4 md:gap-0">
              {/* Stage 1 */}
              <div className="flex flex-col items-center">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
                  <MessageSquare className="w-10 h-10 text-white" />
                </div>
                <span className="mt-3 font-medium">Input</span>
                <span className="text-xs text-gray-500">Raw text</span>
              </div>

              <ArrowRight className="hidden md:block w-8 h-8 text-gray-600" />

              {/* Stage 2 */}
              <div className="flex flex-col items-center">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                  <Layers className="w-10 h-10 text-white" />
                </div>
                <span className="mt-3 font-medium">Ontological</span>
                <span className="text-xs text-gray-500">10 layers</span>
              </div>

              <ArrowRight className="hidden md:block w-8 h-8 text-gray-600" />

              {/* Stage 3 */}
              <div className="flex flex-col items-center">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-lg shadow-purple-500/25">
                  <GitBranch className="w-10 h-10 text-white" />
                </div>
                <span className="mt-3 font-medium">Fusion</span>
                <span className="text-xs text-gray-500">3 renderers</span>
              </div>

              <ArrowRight className="hidden md:block w-8 h-8 text-gray-600" />

              {/* Stage 4 */}
              <div className="flex flex-col items-center">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/25">
                  <Lock className="w-10 h-10 text-white" />
                </div>
                <span className="mt-3 font-medium">Governance</span>
                <span className="text-xs text-gray-500">Gate & audit</span>
              </div>

              <ArrowRight className="hidden md:block w-8 h-8 text-gray-600" />

              {/* Stage 5 */}
              <div className="flex flex-col items-center">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/25">
                  <Zap className="w-10 h-10 text-white" />
                </div>
                <span className="mt-3 font-medium">Presentation</span>
                <span className="text-xs text-gray-500">Tiered UX</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Three Tiers Preview */}
      <section className="py-24 px-6 bg-gradient-to-b from-slate-900/50 to-transparent">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Three Experience Tiers</h2>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              Choose the level of insight that matches your needs.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Explorer - RAG Lookup */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-blue-500/10 to-transparent border border-blue-500/20 hover:border-blue-500/40 transition-all hover:scale-105">
              <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Search className="w-6 h-6 text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold mb-1 text-blue-100">Explorer</h3>
              <p className="text-blue-400 text-xs font-medium mb-3">RAG Lookup</p>
              <p className="text-gray-400 text-sm mb-4">
                Simple knowledge search with quality indicators and hints.
              </p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li>- Search interface</li>
                <li>- Quality badges</li>
                <li>- Hint cards</li>
              </ul>
            </div>

            {/* Analyst - Enterprise Chat */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-purple-500/10 to-transparent border border-purple-500/20 hover:border-purple-500/40 transition-all hover:scale-105">
              <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Layers className="w-6 h-6 text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold mb-1 text-purple-100">Analyst</h3>
              <p className="text-purple-400 text-xs font-medium mb-3">Enterprise Chat</p>
              <p className="text-gray-400 text-sm mb-4">
                Internal employee chat with semantic insights and metrics.
              </p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li>- Layer tabs (Symbolic/Practical/Mirror)</li>
                <li>- Entropy metrics</li>
                <li>- Ontological profile</li>
              </ul>
            </div>

            {/* Developer - Customer Chat */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-orange-500/10 to-transparent border border-orange-500/20 hover:border-orange-500/40 transition-all hover:scale-105">
              <div className="w-12 h-12 rounded-xl bg-orange-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Code className="w-6 h-6 text-orange-400" />
              </div>
              <h3 className="text-lg font-semibold mb-1 text-orange-100">Developer</h3>
              <p className="text-orange-400 text-xs font-medium mb-3">Customer Chat</p>
              <p className="text-gray-400 text-sm mb-4">
                External customer chat with full analytics and diagnostics.
              </p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li>- Coherence trend charts</li>
                <li>- Risk band analysis</li>
                <li>- What-if simulator</li>
              </ul>
            </div>
          </div>

          {/* Demo CTA */}
          <div className="text-center mt-12">
            <button
              onClick={onEnterDemo}
              className="group inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold text-lg hover:from-indigo-500 hover:to-purple-500 transition-all shadow-xl shadow-indigo-500/25 hover:shadow-indigo-500/40"
            >
              <span>Explore All Tiers</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <Layers className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-bold">Symbol-U</span>
            </div>
            <div className="text-gray-500 text-sm">
              Cognitive Intelligence Framework | v0.1
            </div>
            <div className="text-gray-600 text-xs">
              &copy; 2025 Symbol-U Project
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
