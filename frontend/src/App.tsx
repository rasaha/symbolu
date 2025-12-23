/**
 * Symbol-U Frontend App
 *
 * Main application with three-tier UX routing.
 * Each tier provides progressively more features:
 *
 * - Consumer: Simple chat with badges & hints
 * - Power User: Chat + insights panel with metrics
 * - Admin: Full dashboard with analytics & simulations
 */

import React, { useState, useEffect } from 'react';
import type { PresentationTier } from '@/api/types';
import { ConsumerTierPage } from '@/views/ConsumerTierPage';
import { PowerUserTierPage } from '@/views/PowerUserTierPage';
import { AdminTierPage } from '@/views/AdminTierPage';
import { useChatStore } from '@/stores/chatStore';
import { Layers, User, Shield, Settings } from 'lucide-react';

// Landing page for tier selection
function TierSelector({ onSelectTier }: { onSelectTier: (tier: PresentationTier) => void }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-slate-900 flex items-center justify-center p-6">
      <div className="max-w-4xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 mb-6 shadow-2xl">
            <Layers className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-4">Symbol-U</h1>
          <p className="text-gray-400 text-lg max-w-md mx-auto">
            Choose your experience level to begin exploring
          </p>
        </div>

        {/* Tier Cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {/* Consumer Tier */}
          <button
            onClick={() => onSelectTier('consumer')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-blue-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-blue-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <User className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Consumer</h3>
            <p className="text-gray-400 text-sm mb-4">
              Simple, clean chat experience with helpful insights and badges.
            </p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Chat interface
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Response badges
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                Hint cards
              </li>
            </ul>
            <div className="absolute bottom-4 right-4 text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity">
              →
            </div>
          </button>

          {/* Power User Tier */}
          <button
            onClick={() => onSelectTier('power_user')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-purple-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-purple-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Layers className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Power User</h3>
            <p className="text-gray-400 text-sm mb-4">
              Enhanced insights with layer analysis and coherence metrics.
            </p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                Layer tabs (Symbolic/Practical/Mirror)
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                Entropy metrics
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                Ontological profile
              </li>
            </ul>
            <div className="absolute bottom-4 right-4 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity">
              →
            </div>
          </button>

          {/* Admin Tier */}
          <button
            onClick={() => onSelectTier('admin')}
            className="group relative bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 hover:border-orange-500/50 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-orange-500/20"
          >
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Admin</h3>
            <p className="text-gray-400 text-sm mb-4">
              Full analytics dashboard with simulations and diagnostics.
            </p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                Coherence trend charts
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                Risk bands & timeline
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                What-if simulator
              </li>
            </ul>
            <div className="absolute bottom-4 right-4 text-orange-400 opacity-0 group-hover:opacity-100 transition-opacity">
              →
            </div>
          </button>
        </div>

        {/* Footer */}
        <div className="text-center mt-12 text-gray-500 text-sm">
          <p>Symbol-U Frontend v0.1 | Three-Tier UX</p>
        </div>
      </div>
    </div>
  );
}

// Main App Component
export function App() {
  const [selectedTier, setSelectedTier] = useState<PresentationTier | null>(null);
  const setTier = useChatStore((state) => state.setTier);

  // Check URL for tier parameter
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tierParam = params.get('tier');
    if (tierParam && ['consumer', 'power_user', 'admin'].includes(tierParam)) {
      setSelectedTier(tierParam as PresentationTier);
      setTier(tierParam as PresentationTier);
    }
  }, [setTier]);

  // Handle tier selection
  const handleSelectTier = (tier: PresentationTier) => {
    setSelectedTier(tier);
    setTier(tier);
    // Update URL without reload
    const url = new URL(window.location.href);
    url.searchParams.set('tier', tier);
    window.history.pushState({}, '', url.toString());
  };

  // Handle back to tier selection
  const handleBackToSelector = () => {
    setSelectedTier(null);
    const url = new URL(window.location.href);
    url.searchParams.delete('tier');
    window.history.pushState({}, '', url.toString());
  };

  // Render tier selector if no tier selected
  if (!selectedTier) {
    return <TierSelector onSelectTier={handleSelectTier} />;
  }

  // Render appropriate tier page with back navigation
  const tierComponents: Record<PresentationTier, React.ReactNode> = {
    consumer: <ConsumerTierPage />,
    power_user: <PowerUserTierPage />,
    admin: <AdminTierPage />,
  };

  return (
    <div className="relative">
      {/* Back Button */}
      <button
        onClick={handleBackToSelector}
        className="fixed top-4 left-4 z-50 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/20 backdrop-blur text-white/80 text-xs font-medium hover:bg-black/30 transition-colors"
      >
        ← Change Tier
      </button>

      {/* Tier Page */}
      {tierComponents[selectedTier]}
    </div>
  );
}

export default App;
