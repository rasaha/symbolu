/**
 * Hint Card Component
 *
 * Displays actionable hints and insights from the response.
 */

import React from 'react';
import type { Hint } from '@/api/types';
import { Lightbulb, ArrowRight, AlertTriangle } from 'lucide-react';

interface HintCardProps {
  hint: Hint;
  compact?: boolean;
  onAction?: () => void;
}

const TYPE_STYLES = {
  insight: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: Lightbulb,
    iconColor: 'text-blue-500',
    textColor: 'text-blue-800',
  },
  action: {
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    icon: ArrowRight,
    iconColor: 'text-emerald-500',
    textColor: 'text-emerald-800',
  },
  warning: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    icon: AlertTriangle,
    iconColor: 'text-amber-500',
    textColor: 'text-amber-800',
  },
};

export function HintCard({ hint, compact = false, onAction }: HintCardProps) {
  const style = TYPE_STYLES[hint.type];
  const IconComponent = style.icon;

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-2 py-1 rounded-md ${style.bg} ${style.border} border`}>
        <IconComponent className={`w-3.5 h-3.5 ${style.iconColor}`} />
        <span className={`text-xs ${style.textColor}`}>{hint.text}</span>
      </div>
    );
  }

  return (
    <div className={`rounded-lg ${style.bg} ${style.border} border p-3`}>
      <div className="flex items-start gap-2">
        <IconComponent className={`w-4 h-4 ${style.iconColor} mt-0.5 flex-shrink-0`} />
        <div className="flex-1">
          <p className={`text-sm ${style.textColor}`}>{hint.text}</p>
          {hint.actionLabel && onAction && (
            <button
              onClick={onAction}
              className={`mt-2 text-xs font-medium ${style.iconColor} hover:underline flex items-center gap-1`}
            >
              {hint.actionLabel}
              <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
