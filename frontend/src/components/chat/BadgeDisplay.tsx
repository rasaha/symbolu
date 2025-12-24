/**
 * Badge Display Component
 *
 * Renders response quality badges with icons and colors.
 */

import React from 'react';
import type { Badge } from '@/api/types';
import {
  CheckCircle,
  Anchor,
  Brain,
  Layers,
  Wrench,
  AlertTriangle,
  Circle,
  AlertCircle,
} from 'lucide-react';

interface BadgeDisplayProps {
  badges: Badge[];
  size?: 'sm' | 'md';
}

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  'check-circle': CheckCircle,
  anchor: Anchor,
  brain: Brain,
  layers: Layers,
  wrench: Wrench,
  'alert-triangle': AlertTriangle,
  'alert-circle': AlertCircle,
  circle: Circle,
};

export function BadgeDisplay({ badges, size = 'sm' }: BadgeDisplayProps) {
  const iconSize = size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4';
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';
  const padding = size === 'sm' ? 'px-2 py-0.5' : 'px-2.5 py-1';

  return (
    <div className="flex flex-wrap gap-1.5">
      {badges.map((badge, index) => {
        const IconComponent = ICON_MAP[badge.icon] || Circle;
        return (
          <span
            key={index}
            className={`inline-flex items-center gap-1 ${padding} rounded-full bg-gray-50 border border-gray-200 ${textSize} font-medium text-gray-700`}
            title={badge.description}
          >
            <IconComponent className={`${iconSize} ${badge.color}`} />
            <span className="capitalize">{badge.name}</span>
          </span>
        );
      })}
    </div>
  );
}
