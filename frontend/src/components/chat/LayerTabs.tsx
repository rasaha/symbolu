/**
 * Layer Tabs Component
 *
 * Displays the 3-layer semantic rendering (Symbolic, Practical, Mirror).
 * Power User tier and above.
 */

import React from 'react';
import type { LayerData } from '@/api/types';
import { Sparkles, Target, Mirror } from 'lucide-react';

interface LayerTabsProps {
  layers: {
    symbolic: string | null;
    practical: string | null;
    mirror: string | null;
  };
  activeTab: 'symbolic' | 'practical' | 'mirror';
  onTabChange: (tab: 'symbolic' | 'practical' | 'mirror') => void;
  showDetails?: boolean;
}

const TAB_CONFIG = {
  symbolic: {
    label: 'Symbolic',
    icon: Sparkles,
    color: 'indigo',
    description: 'WHY - Meaning & themes',
  },
  practical: {
    label: 'Practical',
    icon: Target,
    color: 'emerald',
    description: 'WHAT/HOW - Actions & facts',
  },
  mirror: {
    label: 'Mirror',
    icon: Mirror,
    color: 'purple',
    description: 'Reflection - Contradictions',
  },
};

export function LayerTabs({
  layers,
  activeTab,
  onTabChange,
  showDetails = false,
}: LayerTabsProps) {
  const activeConfig = TAB_CONFIG[activeTab];

  return (
    <div className="space-y-2">
      {/* Tab Buttons */}
      <div className="flex gap-1 p-1 bg-gray-100 rounded-lg">
        {(Object.keys(TAB_CONFIG) as Array<keyof typeof TAB_CONFIG>).map((tab) => {
          const config = TAB_CONFIG[tab];
          const IconComponent = config.icon;
          const isActive = activeTab === tab;
          const hasContent = layers[tab] !== null;

          return (
            <button
              key={tab}
              onClick={() => onTabChange(tab)}
              disabled={!hasContent}
              className={`
                flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium
                transition-all duration-200
                ${
                  isActive
                    ? `bg-white text-${config.color}-600 shadow-sm`
                    : hasContent
                    ? 'text-gray-600 hover:bg-gray-200'
                    : 'text-gray-400 cursor-not-allowed'
                }
              `}
            >
              <IconComponent className="w-3.5 h-3.5" />
              {config.label}
              {hasContent && (
                <span className={`w-1.5 h-1.5 rounded-full ${isActive ? `bg-${config.color}-400` : 'bg-gray-400'}`} />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="bg-gray-50 rounded-lg p-3 min-h-[60px]">
        {showDetails && (
          <div className="text-xs text-gray-500 mb-2">{activeConfig.description}</div>
        )}

        {layers[activeTab] ? (
          <div className="text-sm text-gray-700 leading-relaxed">
            {typeof layers[activeTab] === 'string'
              ? layers[activeTab]
              : JSON.stringify(layers[activeTab], null, 2)}
          </div>
        ) : (
          <div className="text-sm text-gray-400 italic">No {activeConfig.label.toLowerCase()} data available</div>
        )}
      </div>
    </div>
  );
}
