import React from 'react';
import type { ConfidenceTier } from '../../api/types';
import { getConfidenceBadgeProps } from '../../lib/utils';
import { ShieldCheck, AlertCircle, AlertTriangle } from 'lucide-react';

interface ConfidenceRingProps {
  score: number;
  tier: ConfidenceTier;
  size?: 'sm' | 'md' | 'lg';
}

export const ConfidenceRing: React.FC<ConfidenceRingProps> = ({
  score,
  tier,
  size = 'md',
}) => {
  const props = getConfidenceBadgeProps(tier, score);
  const clampedScore = Math.max(0, Math.min(1, score));
  const percent = Math.round(clampedScore * 100);

  const radius = size === 'sm' ? 14 : size === 'lg' ? 24 : 18;
  const stroke = size === 'sm' ? 2.5 : size === 'lg' ? 4 : 3;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - clampedScore * circumference;

  const IconComponent = tier === 'high' ? ShieldCheck : tier === 'medium' ? AlertTriangle : AlertCircle;

  return (
    <div className="inline-flex items-center space-x-2.5 px-3 py-1.5 rounded-full border bg-card/80 backdrop-blur-sm shadow-sm" title={`Verified Confidence: ${percent}%`}>
      {/* SVG Ring Gauge */}
      <div className="relative flex items-center justify-center">
        <svg
          height={radius * 2}
          width={radius * 2}
          className="transform -rotate-90"
        >
          {/* Background Track */}
          <circle
            stroke="currentColor"
            fill="transparent"
            strokeWidth={stroke}
            r={normalizedRadius}
            cx={radius}
            cy={radius}
            className="text-card-border"
          />
          {/* Active Fill Ring */}
          <circle
            stroke="currentColor"
            fill="transparent"
            strokeWidth={stroke}
            strokeDasharray={`${circumference} ${circumference}`}
            style={{ strokeDashoffset }}
            strokeLinecap="round"
            r={normalizedRadius}
            cx={radius}
            cy={radius}
            className={`transition-all duration-700 ease-out ${
              tier === 'high'
                ? 'text-status-success'
                : tier === 'medium'
                ? 'text-status-caution'
                : 'text-status-danger'
            }`}
          />
        </svg>
        <span className="absolute text-[9px] font-mono font-bold text-ink tabular-nums">
          {percent}
        </span>
      </div>

      {/* Label and Tier Icon */}
      <div className="flex items-center space-x-1.5">
        <IconComponent className={`w-3.5 h-3.5 ${
          tier === 'high'
            ? 'text-status-success'
            : tier === 'medium'
            ? 'text-status-caution'
            : 'text-status-danger'
        }`} />
        <span className="text-xs font-semibold text-ink font-heading capitalize">
          {tier} Confidence
        </span>
      </div>
    </div>
  );
};
