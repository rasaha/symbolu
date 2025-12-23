/**
 * Entropy Metrics Component
 *
 * Displays H_D, H_G, H_K, and H_norm entropy metrics.
 * Power User tier and above.
 */

import React from 'react';
import type { EntropyMetrics as EntropyMetricsType } from '@/api/types';

interface EntropyMetricsProps {
  entropy?: EntropyMetricsType;
  compact?: boolean;
}

const ENTROPY_CONFIG = {
  H_D: { label: 'Domain', description: 'Domain-specific entropy', color: 'bg-blue-500' },
  H_G: { label: 'Global', description: 'Global entropy', color: 'bg-emerald-500' },
  H_K: { label: 'Knowledge', description: 'Knowledge entropy', color: 'bg-purple-500' },
  H_norm: { label: 'Normalized', description: 'Normalized entropy', color: 'bg-amber-500' },
};

export function EntropyMetrics({ entropy, compact = false }: EntropyMetricsProps) {
  if (!entropy) {
    return (
      <div className="text-sm text-gray-400 italic p-4">
        No entropy metrics available
      </div>
    );
  }

  if (compact) {
    return (
      <div className="flex items-center gap-4 text-xs">
        {Object.entries(entropy).map(([key, value]) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className="text-gray-500">{key}:</span>
            <span className="font-mono font-medium">{value.toFixed(2)}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-800 mb-3">Entropy Metrics</h3>
      <div className="space-y-3">
        {(Object.entries(entropy) as Array<[keyof typeof ENTROPY_CONFIG, number]>).map(
          ([key, value]) => {
            const config = ENTROPY_CONFIG[key];
            const percentage = Math.round(value * 100);

            return (
              <div key={key}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-600" title={config.description}>
                    {config.label} ({key})
                  </span>
                  <span className="font-mono font-medium text-gray-800">
                    {value.toFixed(2)}
                  </span>
                </div>
                <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${config.color} transition-all duration-500`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          }
        )}
      </div>
    </div>
  );
}
