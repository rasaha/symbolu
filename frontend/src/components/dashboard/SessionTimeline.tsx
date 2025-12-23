/**
 * Session Timeline Component
 *
 * Horizontal timeline showing conversation turns with metrics.
 * Admin tier.
 */

import React from 'react';

interface TimelineItem {
  turn: number;
  domain: string;
  coherence: number;
  highlights: string[];
}

interface SessionTimelineProps {
  timeline: TimelineItem[];
  selectedTurn?: number;
  onTurnSelect?: (turn: number) => void;
}

function getCoherenceColor(value: number): string {
  if (value >= 0.7) return 'bg-green-500 border-green-600';
  if (value >= 0.4) return 'bg-amber-500 border-amber-600';
  return 'bg-red-500 border-red-600';
}

export function SessionTimeline({
  timeline,
  selectedTurn,
  onTurnSelect,
}: SessionTimelineProps) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Session Timeline</h3>
        <div className="text-sm text-gray-400 italic">No timeline data available</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-800 mb-4">Session Timeline</h3>

      {/* Timeline */}
      <div className="relative">
        {/* Connection Line */}
        <div className="absolute top-4 left-4 right-4 h-0.5 bg-gray-200" />

        {/* Turn Points */}
        <div className="relative flex justify-between">
          {timeline.map((item, index) => {
            const isSelected = selectedTurn === item.turn;
            const colorClass = getCoherenceColor(item.coherence);

            return (
              <div key={item.turn} className="flex flex-col items-center">
                {/* Turn Circle */}
                <button
                  onClick={() => onTurnSelect?.(item.turn)}
                  className={`
                    relative w-8 h-8 rounded-full border-2 flex items-center justify-center
                    transition-all duration-200 hover:scale-110
                    ${colorClass}
                    ${isSelected ? 'ring-2 ring-offset-2 ring-indigo-500' : ''}
                  `}
                >
                  <span className="text-xs font-bold text-white">{item.turn}</span>
                </button>

                {/* Domain Label */}
                <span className="mt-2 text-xs text-gray-500 truncate max-w-[60px]">
                  {item.domain}
                </span>

                {/* Coherence Value */}
                <span className="text-xs font-mono text-gray-400">
                  {item.coherence.toFixed(2)}
                </span>

                {/* Connection to next */}
                {index < timeline.length - 1 && (
                  <div className="absolute top-4 left-full w-full h-0.5 bg-gray-200" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Selected Turn Details */}
      {selectedTurn !== undefined && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          {(() => {
            const item = timeline.find((t) => t.turn === selectedTurn);
            if (!item) return null;

            return (
              <div className="text-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-800">Turn {item.turn}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                    {item.domain}
                  </span>
                </div>
                {item.highlights.length > 0 && (
                  <ul className="text-xs text-gray-600 space-y-1">
                    {item.highlights.map((h, i) => (
                      <li key={i} className="flex items-start gap-1">
                        <span className="text-gray-400">-</span>
                        {h}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
