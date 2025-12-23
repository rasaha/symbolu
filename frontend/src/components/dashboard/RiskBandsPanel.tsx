/**
 * Risk Bands Panel Component
 *
 * Visual display of risk levels across different dimensions.
 * Admin tier.
 */

import React from 'react';
import { Shield, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';

interface RiskBands {
  stability: 'low' | 'medium' | 'high';
  drift: 'low' | 'medium' | 'high';
  semantic: 'low' | 'medium' | 'high';
  motivation: 'low' | 'medium' | 'high';
}

interface RiskBandsPanelProps {
  bands: RiskBands | null;
}

const RISK_CONFIG = {
  low: {
    color: 'bg-green-500',
    bgLight: 'bg-green-50',
    textColor: 'text-green-700',
    borderColor: 'border-green-200',
    icon: CheckCircle,
    label: 'LOW',
  },
  medium: {
    color: 'bg-amber-500',
    bgLight: 'bg-amber-50',
    textColor: 'text-amber-700',
    borderColor: 'border-amber-200',
    icon: AlertTriangle,
    label: 'MEDIUM',
  },
  high: {
    color: 'bg-red-500',
    bgLight: 'bg-red-50',
    textColor: 'text-red-700',
    borderColor: 'border-red-200',
    icon: AlertCircle,
    label: 'HIGH',
  },
};

const BAND_LABELS: Record<keyof RiskBands, string> = {
  stability: 'Stability Risk',
  drift: 'Drift Risk',
  semantic: 'Semantic Risk',
  motivation: 'Motivation Risk',
};

export function RiskBandsPanel({ bands }: RiskBandsPanelProps) {
  if (!bands) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Risk Bands</h3>
        <div className="text-sm text-gray-400 italic">No risk data available</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-gray-500" />
        <h3 className="text-sm font-semibold text-gray-800">Risk Bands</h3>
      </div>

      <div className="space-y-3">
        {(Object.entries(bands) as Array<[keyof RiskBands, 'low' | 'medium' | 'high']>).map(
          ([key, level]) => {
            const config = RISK_CONFIG[level];
            const IconComponent = config.icon;

            return (
              <div
                key={key}
                className={`flex items-center justify-between p-2.5 rounded-lg border ${config.borderColor} ${config.bgLight}`}
              >
                <span className="text-sm text-gray-700">{BAND_LABELS[key]}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold ${config.textColor}`}>
                    {config.label}
                  </span>
                  <IconComponent className={`w-4 h-4 ${config.textColor}`} />
                </div>
              </div>
            );
          }
        )}
      </div>

      {/* Summary */}
      <div className="mt-4 pt-3 border-t border-gray-100">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Overall Assessment</span>
          {Object.values(bands).some((v) => v === 'high') ? (
            <span className="font-medium text-red-600">Attention Required</span>
          ) : Object.values(bands).some((v) => v === 'medium') ? (
            <span className="font-medium text-amber-600">Monitor Closely</span>
          ) : (
            <span className="font-medium text-green-600">All Clear</span>
          )}
        </div>
      </div>
    </div>
  );
}
