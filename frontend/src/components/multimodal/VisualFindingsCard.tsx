import React from 'react';
import { Activity, CheckCircle2, AlertCircle, ShieldCheck, ShieldAlert, Sparkles } from 'lucide-react';
import type { VisualFinding } from '../../api/types';

interface VisualFindingsCardProps {
  findings: VisualFinding[];
  confidenceScores: Record<string, number>;
  modelUsed?: string;
  refusalTier?: string;
}

export const VisualFindingsCard: React.FC<VisualFindingsCardProps> = ({
  findings,
  confidenceScores,
  modelUsed,
  refusalTier = 'ANSWERED',
}) => {
  // Sort findings by confidence descending
  const sortedFindings = [...findings].sort((a, b) => {
    const scoreA = confidenceScores[a.label] ?? a.confidence;
    const scoreB = confidenceScores[b.label] ?? b.confidence;
    return scoreB - scoreA;
  });

  const detectedCount = sortedFindings.filter(
    (f) => !f.negated && f.label !== 'no finding' && (confidenceScores[f.label] ?? f.confidence) >= 0.2
  ).length;

  const ruledOutCount = sortedFindings.filter((f) => f.negated).length;

  return (
    <div className="bg-canvas-card border border-edge rounded-xl p-5 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-edge pb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-teal-accent" />
          <h3 className="text-sm font-semibold text-ink">14-Class Zero-Shot Visual Pathology Triage</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono bg-canvas-subtle text-ink-muted px-2 py-0.5 rounded border border-edge">
            {detectedCount > 0 ? `${detectedCount} Elevated` : 'All Clear'}
          </span>
          <span className="text-[11px] font-mono bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">
            {ruledOutCount} Ruled Out
          </span>
          {modelUsed && (
            <span className="text-[10px] font-mono bg-teal-accent/10 text-teal-accent px-2 py-0.5 rounded border border-teal-accent/20">
              {modelUsed}
            </span>
          )}
        </div>
      </div>

      {/* Pathology Progress Bars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3.5">
        {sortedFindings.map((finding) => {
          const score = confidenceScores[finding.label] ?? finding.confidence;
          const pct = Math.round(score * 1000) / 10;
          const isElevated = !finding.negated && finding.label !== 'no finding' && score >= 0.2;
          const isHigh = score >= 0.5;

          let barColor = 'bg-teal-500/70';
          let textColor = 'text-ink-muted';

          if (finding.negated) {
            barColor = 'bg-slate-500/40';
            textColor = 'text-slate-400';
          } else if (isHigh) {
            barColor = 'bg-rose-500';
            textColor = 'text-rose-400 font-semibold';
          } else if (isElevated) {
            barColor = 'bg-amber-500';
            textColor = 'text-amber-400 font-medium';
          }

          return (
            <div key={finding.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="font-medium text-ink capitalize truncate">
                    {finding.label}
                  </span>
                  {finding.negated && (
                    <span className="text-[9px] font-mono uppercase bg-slate-500/20 text-slate-300 px-1.5 py-0.2 rounded border border-slate-500/30">
                      Absent
                    </span>
                  )}
                  {finding.auc_reference && (
                    <span className="text-[9px] font-mono text-ink-muted/80" title="Validation AUC">
                      (AUC {finding.auc_reference.toFixed(2)})
                    </span>
                  )}
                </div>
                <span className={`font-mono text-xs ${textColor}`}>
                  {pct.toFixed(1)}%
                </span>
              </div>

              {/* Progress Bar Container */}
              <div className="h-2 w-full bg-canvas-subtle rounded-full overflow-hidden border border-edge/60">
                <div
                  className={`h-full rounded-full transition-all duration-500 ease-out ${barColor}`}
                  style={{ width: `${Math.max(pct, 2)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="pt-2 border-t border-edge flex items-center justify-between text-[11px] text-ink-muted">
        <span>CheXzero prompt ensembles calibrated against VQA-RAD ground truth (AUC &gt; 0.65)</span>
        <span className="font-mono">Refusal: {refusalTier}</span>
      </div>
    </div>
  );
};
