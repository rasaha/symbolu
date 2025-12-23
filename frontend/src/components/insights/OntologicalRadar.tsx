/**
 * Ontological Radar Component
 *
 * Displays the 10D ontological profile as a visual radar/bar chart.
 * Power User tier and above.
 */

import React from 'react';
import type { OntologicalDimensions, ONTOLOGICAL_LABELS } from '@/api/types';

interface OntologicalRadarProps {
  dimensions?: OntologicalDimensions;
  compact?: boolean;
}

const DIMENSION_CONFIG: Record<keyof OntologicalDimensions, { label: string; color: string }> = {
  O1_THINKING: { label: 'Thinking', color: 'bg-blue-500' },
  O2_FORMING: { label: 'Forming', color: 'bg-cyan-500' },
  O3_ACTING: { label: 'Acting', color: 'bg-emerald-500' },
  O4_TAGGING: { label: 'Tagging', color: 'bg-teal-500' },
  O5_DIRECTING: { label: 'Directing', color: 'bg-green-500' },
  O6_REASONING: { label: 'Reasoning', color: 'bg-yellow-500' },
  O7_PURPOSING: { label: 'Purposing', color: 'bg-orange-500' },
  O8_META_OBSERVING: { label: 'Observing', color: 'bg-red-500' },
  O9_UNIFYING: { label: 'Unifying', color: 'bg-pink-500' },
  O10_ABSOLVING: { label: 'Absolving', color: 'bg-purple-500' },
};

export function OntologicalRadar({ dimensions, compact = false }: OntologicalRadarProps) {
  if (!dimensions) {
    return (
      <div className="text-sm text-gray-400 italic p-4">
        No ontological profile available
      </div>
    );
  }

  // Find dominant dimension
  const entries = Object.entries(dimensions) as Array<[keyof OntologicalDimensions, number]>;
  const sorted = [...entries].sort((a, b) => b[1] - a[1]);
  const dominant = sorted[0];

  if (compact) {
    // Show top 3 dimensions
    return (
      <div className="space-y-2">
        <div className="text-xs text-gray-500 mb-2">
          Dominant: <span className="font-medium text-gray-700">{DIMENSION_CONFIG[dominant[0]].label}</span>
        </div>
        {sorted.slice(0, 3).map(([key, value]) => {
          const config = DIMENSION_CONFIG[key];
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="text-xs text-gray-600 w-16 truncate">{config.label}</span>
              <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${config.color}`}
                  style={{ width: `${Math.round(value * 100)}%` }}
                />
              </div>
              <span className="text-xs font-mono text-gray-500 w-8">{value.toFixed(2)}</span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-800">10D Ontological Profile</h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
          Dominant: {DIMENSION_CONFIG[dominant[0]].label}
        </span>
      </div>

      <div className="space-y-2.5">
        {entries.map(([key, value]) => {
          const config = DIMENSION_CONFIG[key];
          const percentage = Math.round(value * 100);
          const isDominant = key === dominant[0];

          return (
            <div key={key} className={isDominant ? 'bg-gray-50 rounded-lg p-1.5 -mx-1.5' : ''}>
              <div className="flex items-center gap-2">
                <span className={`text-xs w-20 truncate ${isDominant ? 'font-medium text-gray-800' : 'text-gray-600'}`}>
                  {config.label}
                </span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${config.color} transition-all duration-500`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
                <span className={`text-xs font-mono w-10 text-right ${isDominant ? 'font-medium text-gray-800' : 'text-gray-500'}`}>
                  {value.toFixed(2)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
