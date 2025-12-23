/**
 * Coherence Indicator Component
 *
 * Visual indicator for coherence score with trend.
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { CoherenceData } from '@/api/types';

interface CoherenceIndicatorProps {
  coherence: CoherenceData | null;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  showTrend?: boolean;
}

function getCoherenceLevel(value: number): 'high' | 'medium' | 'low' {
  if (value >= 0.7) return 'high';
  if (value >= 0.4) return 'medium';
  return 'low';
}

const LEVEL_CONFIG = {
  high: {
    color: 'text-coherence-high',
    bg: 'bg-coherence-high',
    bgLight: 'bg-green-100',
    label: 'Stable',
  },
  medium: {
    color: 'text-coherence-medium',
    bg: 'bg-coherence-medium',
    bgLight: 'bg-amber-100',
    label: 'Moderate',
  },
  low: {
    color: 'text-coherence-low',
    bg: 'bg-coherence-low',
    bgLight: 'bg-red-100',
    label: 'Unstable',
  },
};

export function CoherenceIndicator({
  coherence,
  size = 'md',
  showLabel = true,
  showTrend = true,
}: CoherenceIndicatorProps) {
  if (!coherence) {
    return (
      <div className="flex items-center gap-2 text-gray-400">
        <div className="w-2 h-2 rounded-full bg-gray-300" />
        <span className="text-xs">No data</span>
      </div>
    );
  }

  const level = getCoherenceLevel(coherence.stability);
  const config = LEVEL_CONFIG[level];
  const percentage = Math.round(coherence.stability * 100);

  const sizeClasses = {
    sm: { dot: 'w-2 h-2', text: 'text-xs', bar: 'h-1' },
    md: { dot: 'w-2.5 h-2.5', text: 'text-sm', bar: 'h-1.5' },
    lg: { dot: 'w-3 h-3', text: 'text-base', bar: 'h-2' },
  };

  const TrendIcon = coherence.trend === 'up'
    ? TrendingUp
    : coherence.trend === 'down'
    ? TrendingDown
    : Minus;

  return (
    <div className="flex items-center gap-2">
      {/* Status Dot */}
      <div className={`${sizeClasses[size].dot} rounded-full ${config.bg}`} />

      {/* Label */}
      {showLabel && (
        <span className={`${sizeClasses[size].text} font-medium ${config.color}`}>
          {config.label}
        </span>
      )}

      {/* Progress Bar */}
      <div className="flex-1 max-w-[80px]">
        <div className={`w-full ${sizeClasses[size].bar} bg-gray-200 rounded-full overflow-hidden`}>
          <div
            className={`h-full ${config.bg} transition-all duration-500`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Value */}
      <span className={`${sizeClasses[size].text} font-mono text-gray-600`}>
        {coherence.stability.toFixed(2)}
      </span>

      {/* Trend */}
      {showTrend && coherence.trend && (
        <TrendIcon
          className={`w-4 h-4 ${
            coherence.trend === 'up'
              ? 'text-green-500'
              : coherence.trend === 'down'
              ? 'text-red-500'
              : 'text-gray-400'
          }`}
        />
      )}
    </div>
  );
}
