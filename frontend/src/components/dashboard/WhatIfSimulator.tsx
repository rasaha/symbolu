/**
 * What-If Simulator Component
 *
 * Run hypothetical simulations with different presets.
 * Admin tier.
 */

import React from 'react';
import { Play, RefreshCw, ArrowRight, TrendingDown, TrendingUp } from 'lucide-react';
import type { WhatIfResult } from '@/api/types';

interface WhatIfSimulatorProps {
  presets: string[];
  selectedPreset: string;
  onPresetChange: (preset: string) => void;
  onRunSimulation: () => void;
  result: WhatIfResult | null;
  isLoading?: boolean;
}

const PRESET_DESCRIPTIONS: Record<string, string> = {
  safety_first: 'Prioritize safety and reliability',
  insight_heavy: 'Maximize depth of insights',
  balanced: 'Balance between all dimensions',
  performance: 'Optimize for quick responses',
  creative: 'Encourage creative exploration',
  analytical: 'Focus on analytical reasoning',
};

export function WhatIfSimulator({
  presets,
  selectedPreset,
  onPresetChange,
  onRunSimulation,
  result,
  isLoading = false,
}: WhatIfSimulatorProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-800 mb-4">What-If Simulator</h3>

      {/* Preset Selection */}
      <div className="flex items-center gap-3 mb-4">
        <label className="text-xs text-gray-500">Preset:</label>
        <select
          value={selectedPreset}
          onChange={(e) => onPresetChange(e.target.value)}
          className="flex-1 text-sm px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
        >
          {presets.map((preset) => (
            <option key={preset} value={preset}>
              {preset.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </option>
          ))}
        </select>
        <button
          onClick={onRunSimulation}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          Run
        </button>
      </div>

      {/* Preset Description */}
      <p className="text-xs text-gray-500 mb-4">
        {PRESET_DESCRIPTIONS[selectedPreset] || 'Run simulation with this preset'}
      </p>

      {/* Results */}
      {result && (
        <div className="border-t border-gray-100 pt-4">
          <div className="grid grid-cols-3 gap-4">
            {/* Original */}
            <div className="text-center">
              <div className="text-xs text-gray-500 mb-1">ORIGINAL</div>
              <div className="text-2xl font-bold text-gray-800">
                {result.original.entropy.toFixed(2)}
              </div>
              <div className="text-xs text-gray-600 truncate">
                {result.original.dominant_dimension.replace('_', ' ')}
              </div>
            </div>

            {/* Arrow */}
            <div className="flex flex-col items-center justify-center">
              <ArrowRight className="w-6 h-6 text-gray-400" />
              <div
                className={`text-sm font-semibold mt-1 ${
                  result.delta < 0 ? 'text-green-600' : result.delta > 0 ? 'text-red-600' : 'text-gray-500'
                }`}
              >
                {result.delta > 0 ? '+' : ''}
                {result.delta.toFixed(2)}
              </div>
            </div>

            {/* Simulated */}
            <div className="text-center">
              <div className="text-xs text-gray-500 mb-1">SIMULATED</div>
              <div
                className={`text-2xl font-bold ${
                  result.simulated.entropy < result.original.entropy
                    ? 'text-green-600'
                    : result.simulated.entropy > result.original.entropy
                    ? 'text-red-600'
                    : 'text-gray-800'
                }`}
              >
                {result.simulated.entropy.toFixed(2)}
              </div>
              <div className="text-xs text-gray-600 truncate">
                {result.simulated.dominant_dimension.replace('_', ' ')}
              </div>
            </div>
          </div>

          {/* Insight */}
          <div className="mt-4 p-3 rounded-lg bg-gray-50 text-xs text-gray-600">
            {result.delta < 0 ? (
              <div className="flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-green-500" />
                <span>
                  Entropy decreased by {Math.abs(result.delta).toFixed(2)}. This preset improves coherence.
                </span>
              </div>
            ) : result.delta > 0 ? (
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-red-500" />
                <span>
                  Entropy increased by {result.delta.toFixed(2)}. Consider a different preset.
                </span>
              </div>
            ) : (
              <span>No significant change in entropy. This preset has neutral effect.</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
