/**
 * Header Component
 *
 * Top navigation bar with tier-aware styling and navigation.
 * Includes Query Guide button for demo assistance.
 */

import React from 'react';
import type { PresentationTier } from '@/api/types';
import { QueryGuide } from '@/components/QueryGuide';

interface HeaderProps {
  tier: PresentationTier;
  onTierChange?: (tier: PresentationTier) => void;
  showTierSelector?: boolean;
  showQueryGuide?: boolean;
}

const TIER_STYLES: Record<PresentationTier, { bg: string; accent: string; label: string }> = {
  consumer: {
    bg: 'bg-gradient-to-r from-blue-600 to-blue-500',
    accent: 'text-blue-100',
    label: 'Consumer',
  },
  power_user: {
    bg: 'bg-gradient-to-r from-purple-600 to-violet-500',
    accent: 'text-purple-100',
    label: 'Power User',
  },
  admin: {
    bg: 'bg-gradient-to-r from-orange-600 to-amber-500',
    accent: 'text-orange-100',
    label: 'Admin',
  },
};

export function Header({ tier, onTierChange, showTierSelector = true, showQueryGuide = true }: HeaderProps) {
  const style = TIER_STYLES[tier];

  return (
    <header className={`${style.bg} text-white shadow-lg`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-white/20 flex items-center justify-center">
              <span className="text-2xl font-bold">S</span>
            </div>
            <div>
              <h1 className="text-xl font-bold">Symbol-U</h1>
              <p className={`text-xs ${style.accent}`}>{style.label} Experience</p>
            </div>
          </div>

          {/* Right Side Actions */}
          <div className="flex items-center gap-4">
            {/* Query Guide */}
            {showQueryGuide && <QueryGuide tier={tier} />}

            {/* Tier Selector */}
            {showTierSelector && onTierChange && (
              <div className="flex items-center gap-2">
                <span className="text-sm opacity-80">Tier:</span>
                <select
                  value={tier}
                  onChange={(e) => onTierChange(e.target.value as PresentationTier)}
                  className="bg-white/20 border border-white/30 rounded-lg px-3 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-white/50"
                >
                  <option value="consumer">Consumer</option>
                  <option value="power_user">Power User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
