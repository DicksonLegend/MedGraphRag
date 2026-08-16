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
