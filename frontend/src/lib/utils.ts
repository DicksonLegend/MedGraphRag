import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { AnswerStatus, ConfidenceTier, CoverageClass, TrendDirection } from '../api/types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format confidence tier styling and labels
 */
export function getConfidenceBadgeProps(tier: ConfidenceTier, score: number) {
  const percent = Math.round(score * 100);
  switch (tier) {
    case 'high':
      return {
        label: `High Confidence (${percent}%)`,
        colorClass: 'text-status-success bg-status-success-bg border-status-success/30',
        ringColor: '#15803D',
        darkRingColor: '#4ADE80',
      };
    case 'medium':
      return {
        label: `Medium Confidence (${percent}%)`,
        colorClass: 'text-status-caution bg-status-caution-bg border-status-caution/30',
        ringColor: '#B45309',
        darkRingColor: '#FBBF24',
      };
    case 'low':
    default:
      return {
        label: `Low Confidence (${percent}%)`,
        colorClass: 'text-status-danger bg-status-danger-bg border-status-danger/30',
        ringColor: '#B91C1C',
        darkRingColor: '#F87171',
      };
  }
}

/**
 * Format answer status styling and icons
 */
export function getAnswerStatusProps(status: AnswerStatus) {
  switch (status) {
    case 'verified':
      return {
        label: 'Verified Claim Evidence',
        badgeClass: 'bg-status-success-bg text-status-success border-status-success/30',
        icon: 'check',
      };
    case 'caution':
      return {
        label: 'Caution / Partial Verification',
        badgeClass: 'bg-status-caution-bg text-status-caution border-status-caution/30',
        icon: 'alert-triangle',
      };
    case 'uncertain':
      return {
        label: 'Uncertain / Limited Grounding',
        badgeClass: 'bg-status-caution-bg text-status-caution border-status-caution/40',
        icon: 'help-circle',
      };
    case 'contradiction_detected':
      return {
        label: 'Contradiction Detected',
        badgeClass: 'bg-status-danger-bg text-status-danger border-status-danger/40 border-2',
        icon: 'x-circle',
      };
    case 'refusal':
      return {
        label: 'Evidence Insufficient (Refusal)',
        badgeClass: 'bg-ink-subtle/10 text-ink-muted border-card-border',
        icon: 'shield-alert',
      };
    case 'out_of_scope':
      return {
        label: 'Non-Medical Inquiry (Out of Scope)',
        badgeClass: 'bg-ink-subtle/10 text-ink-muted border-card-border',
        icon: 'info',
      };
    case 'error':
    default:
      return {
        label: 'Processing Notice',
        badgeClass: 'bg-status-danger-bg text-status-danger border-status-danger/30',
        icon: 'alert-octagon',
      };
  }
}

/**
 * Format Trend Direction badge styling
 */
export function getTrendDirectionProps(direction: TrendDirection) {
  switch (direction) {
    case 'worsening':
      return {
        label: 'Worsening',
        className: 'bg-status-danger-bg text-status-danger border-status-danger/30',
      };
    case 'improving':
      return {
        label: 'Improving',
        className: 'bg-status-success-bg text-status-success border-status-success/30',
      };
    case 'stable':
      return {
        label: 'Stable',
        className: 'bg-brand-surface text-brand border-brand-border',
      };
    case 'new':
      return {
        label: 'New Baseline',
        className: 'bg-status-info-bg text-status-info border-status-info/30',
      };
    case 'resolved':
      return {
        label: 'Resolved',
        className: 'bg-status-success-bg text-status-success border-status-success/30',
      };
  }
}

/**
 * Format Coverage Class badge styling
 */
export function getCoverageClassProps(covClass: CoverageClass) {
  switch (covClass) {
    case 'strong':
      return {
        label: 'Strong Evidence',
        badgeClass: 'bg-status-success-bg text-status-success border-status-success/30',
      };
    case 'partial':
      return {
        label: 'Partial Evidence',
        badgeClass: 'bg-status-caution-bg text-status-caution border-status-caution/30',
      };
    case 'none':
    default:
      return {
        label: 'No Direct Evidence',
        badgeClass: 'bg-status-danger-bg text-status-danger border-status-danger/30',
      };
  }
}

/**
 * Enterprise Lab Value Reference Range Comparator
 * Compares value vs [ref_low, ref_high] and is_critical flag.
 */
export interface ComputedLabStatus {
  status: 'normal' | 'high' | 'low' | 'critical_high' | 'critical_low' | 'critical';
  label: string;
  isCritical: boolean;
  isOutOfRange: boolean;
  colorClass: string;
  badgeClass: string;
}

export function computeLabValueStatus(
  value: number,
  ref_low?: number | null,
  ref_high?: number | null,
  is_critical?: boolean
): ComputedLabStatus {
  if (is_critical) {
    return {
      status: 'critical',
      label: 'Critical Range',
      isCritical: true,
      isOutOfRange: true,
      colorClass: 'text-[#DC2626] font-semibold',
      badgeClass:
        'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800 font-semibold',
    };
  }

  if (ref_high !== undefined && ref_high !== null && value > ref_high) {
    const isSevere = value >= ref_high * 1.5;
    return {
      status: isSevere ? 'critical_high' : 'high',
      label: isSevere ? 'Critical · High' : 'High',
      isCritical: isSevere,
      isOutOfRange: true,
      colorClass: isSevere ? 'text-[#DC2626] font-semibold' : 'text-[#D97706] font-semibold',
      badgeClass: isSevere
        ? 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800 font-semibold'
        : 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800 font-semibold',
    };
  }

  if (ref_low !== undefined && ref_low !== null && value < ref_low) {
    const isSevere = value <= ref_low * 0.7;
    return {
      status: isSevere ? 'critical_low' : 'low',
      label: isSevere ? 'Critical · Low' : 'Low',
      isCritical: isSevere,
      isOutOfRange: true,
      colorClass: isSevere ? 'text-[#DC2626] font-semibold' : 'text-[#D97706] font-semibold',
      badgeClass: isSevere
        ? 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800 font-semibold'
        : 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800 font-semibold',
    };
  }

  return {
    status: 'normal',
    label: 'Normal',
    isCritical: false,
    isOutOfRange: false,
    colorClass: 'text-slate-800 dark:text-slate-200',
    badgeClass:
      'bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800 font-medium',
  };
}
