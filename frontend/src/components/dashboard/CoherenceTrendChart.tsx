/**
 * Coherence Trend Chart Component
 *
 * Line chart showing coherence stability and drift over turns.
 * Admin tier.
 */

import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface CoherenceTrendChartProps {
  data: Array<{ turn: number; stability: number; drift: number }>;
}

export function CoherenceTrendChart({ data }: CoherenceTrendChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-gray-400">
        No coherence data available
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-800 mb-4">Coherence Trend</h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="turn"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickFormatter={(v) => v.toFixed(1)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(value: number) => [value.toFixed(3), '']}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px' }}
            iconSize={8}
          />
          <Line
            type="monotone"
            dataKey="stability"
            name="Stability"
            stroke="#22c55e"
            strokeWidth={2}
            dot={{ r: 3, fill: '#22c55e' }}
            activeDot={{ r: 5 }}
          />
          <Line
            type="monotone"
            dataKey="drift"
            name="Drift"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={{ r: 3, fill: '#f59e0b' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
