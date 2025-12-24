/**
 * Session Status Bar Component
 *
 * Bottom status bar showing session health metrics.
 */

import React from 'react';
import { CoherenceIndicator } from './CoherenceIndicator';
import type { CoherenceData, SessionPolicy } from '@/api/types';
import { Activity, Hash, AlertCircle, CheckCircle } from 'lucide-react';

interface SessionStatusBarProps {
  coherence: CoherenceData | null;
  turnCount: number;
  sessionPolicy: SessionPolicy | null;
  compact?: boolean;
}

export function SessionStatusBar({
  coherence,
  turnCount,
  sessionPolicy,
  compact = false,
}: SessionStatusBarProps) {
  const isStable = sessionPolicy?.session_is_stable ?? true;
  const needsGrounding = sessionPolicy?.session_needs_grounding ?? false;

  if (compact) {
    return (
      <div className="flex items-center gap-4 px-4 py-2 bg-gray-50 border-t border-gray-200 text-sm">
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${isStable ? 'bg-green-500' : 'bg-amber-500'}`} />
          <span className="text-gray-600">{isStable ? 'Stable' : 'Unstable'}</span>
        </div>
        <div className="w-px h-4 bg-gray-300" />
        <CoherenceIndicator coherence={coherence} size="sm" showLabel={false} showTrend={false} />
        <div className="w-px h-4 bg-gray-300" />
        <span className="text-gray-500 text-xs">{turnCount} turns</span>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 border-t border-gray-200 px-4 py-3">
      <div className="flex items-center justify-between gap-4">
        {/* Session Status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {isStable ? (
              <CheckCircle className="w-4 h-4 text-green-500" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-500" />
            )}
            <span className={`text-sm font-medium ${isStable ? 'text-green-700' : 'text-amber-700'}`}>
              SESSION: {isStable ? 'Stable' : 'Needs Attention'}
            </span>
          </div>

          {needsGrounding && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
              Grounding recommended
            </span>
          )}
        </div>

        {/* Coherence */}
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-gray-400" />
          <span className="text-xs text-gray-500 font-medium">COHERENCE:</span>
          <CoherenceIndicator coherence={coherence} size="sm" showLabel={false} />
        </div>

        {/* Turn Count */}
        <div className="flex items-center gap-2">
          <Hash className="w-4 h-4 text-gray-400" />
          <span className="text-xs text-gray-500 font-medium">TURNS:</span>
          <span className="text-sm font-mono text-gray-700">{turnCount}</span>
        </div>

        {/* Recommended Style */}
        {sessionPolicy?.session_recommended_style && (
          <div className="text-xs text-gray-500">
            Style: <span className="font-medium text-gray-700">{sessionPolicy.session_recommended_style}</span>
          </div>
        )}
      </div>
    </div>
  );
}
