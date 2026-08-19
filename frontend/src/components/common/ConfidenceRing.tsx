import React from 'react';
import type { ConfidenceTier } from '../../api/types';
import { ShieldCheck, AlertCircle, AlertTriangle } from 'lucide-react';

interface ConfidenceRingProps {
  score: number;
  tier: ConfidenceTier;
  size?: 'sm' | 'md' | 'lg';
}

export const ConfidenceRing: React.FC<ConfidenceRingProps> = ({
  score,
  tier,
  size = 'sm',
}) => {
  const clampedScore = Math.max(0, Math.min(1, score));
  const percent = Math.round(clampedScore * 100);

  const radius = size === 'sm' ? 10 : size === 'lg' ? 20 : 14;
  const stroke = size === 'sm' ? 2 : size === 'lg' ? 3.5 : 2.5;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - clampedScore * circumference;

  const IconComponent = tier === 'high' ? ShieldCheck : tier === 'medium' ? AlertTriangle : AlertCircle;

  const getTierColor = () => {
    if (clampedScore >= 0.75) return 'text-[#16A34A]';
    if (clampedScore >= 0.50) return 'text-[#D97706]';
    return 'text-[#DC2626]';
  };

  const getTierBorder = () => {
    if (clampedScore >= 0.75) return 'border-green-200 dark:border-green-900/60 bg-green-50/50 dark:bg-green-950/30';
    if (clampedScore >= 0.50) return 'border-amber-200 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/30';
    return 'border-red-200 dark:border-red-900/60 bg-red-50/50 dark:bg-red-950/30';
  };

  return (
    <div
      className={`inline-flex items-center space-x-2 h-7 px-2.5 rounded-lg border text-xs shadow-xs cursor-help ${getTierBorder()}`}
      title="φ → tier mapping: High ≥ 0.75, Medium 0.50–0.75, Low < 0.50"
      aria-label={`Verified Confidence score: ${percent}%, Tier: ${tier}`}
    >
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
            className="text-slate-200 dark:text-slate-800"
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
            className={`transition-all duration-700 ease-out ${getTierColor()}`}
          />
        </svg>
      </div>

      {/* Label format: "High confidence · φ 0.84" */}
      <div className="flex items-center space-x-1.5 text-xs">
        <IconComponent className={`w-3.5 h-3.5 stroke-[1.75] ${getTierColor()}`} />
        <span className="font-semibold capitalize text-slate-900 dark:text-slate-100">
          {tier} confidence
        </span>
        <span className="text-slate-400 dark:text-slate-500">·</span>
        <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
          φ {clampedScore.toFixed(2)}
        </span>
      </div>
    </div>
  );
};
