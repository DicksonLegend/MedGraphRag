import React from 'react';
import { AlertTriangle, Eye, FileText, GitFork, ShieldAlert, UserCheck } from 'lucide-react';
import { DiscrepancyAlert } from '../../api/types';

interface DiscrepancyAlertBannerProps {
  alerts?: DiscrepancyAlert[];
}

export const DiscrepancyAlertBanner: React.FC<DiscrepancyAlertBannerProps> = ({ alerts }) => {
  if (!alerts || alerts.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 my-3">
      {alerts.map((alert, idx) => {
        const isHigh = alert.severity === 'HIGH';
        const borderColor = isHigh
          ? 'border-red-200 dark:border-red-700/50 bg-red-50/90 dark:bg-red-950/30 text-red-950 dark:text-red-200'
          : 'border-amber-200 dark:border-amber-700/50 bg-amber-50/90 dark:bg-amber-950/30 text-amber-950 dark:text-amber-200';
        const badgeBg = isHigh
          ? 'bg-red-100 text-red-800 border-red-300 dark:bg-red-500/20 dark:text-red-300 dark:border-red-500/40'
          : 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/40';

        return (
          <div
            key={idx}
            className={`p-4 rounded-xl border ${borderColor} shadow-xs transition-all duration-200`}
            role="alert"
            aria-live="assertive"
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-3">
              <div className="flex items-center gap-2.5">
                <div className={`p-1.5 rounded-lg shrink-0 shadow-2xs ${isHigh ? 'bg-red-600 text-white' : 'bg-amber-600 text-white'}`}>
                  {isHigh ? <ShieldAlert className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                </div>
                <div>
                  <span className="text-[10px] font-mono font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400 block">
                    Cross-Modal Conflict Detected
                  </span>
                  <h4 className="text-xs sm:text-sm font-semibold capitalize text-slate-900 dark:text-slate-100">
                    {alert.finding.replace(/_/g, ' ')}
                  </h4>
                </div>
              </div>

              <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded-md border ${badgeBg}`}>
                {alert.severity} Severity
              </span>
            </div>

            {/* Evidence Comparison Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3 text-xs">
              {/* Visual Finding Side */}
              <div className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
                <div className="flex items-center gap-1.5 text-sky-700 dark:text-sky-400 font-semibold">
                  <Eye className="w-3.5 h-3.5" />
                  <span>Visual Analysis (BiomedCLIP)</span>
                </div>
                <div className="flex items-center justify-between text-slate-700 dark:text-slate-300">
                  <span>Detected State:</span>
                  <span className={`font-mono font-bold ${alert.visual_evidence.negated ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
                    {alert.visual_evidence.negated ? 'NEGATED / ABSENT' : 'POSITIVE (Present)'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
                  <span>Model Confidence:</span>
                  <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold">
                    {(alert.visual_evidence.score * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Text Evidence Side */}
              <div className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
                <div className="flex items-center gap-1.5 text-purple-700 dark:text-purple-400 font-semibold">
                  <FileText className="w-3.5 h-3.5" />
                  <span>Clinical Text Evidence</span>
                </div>
                <p className="italic text-slate-800 dark:text-slate-300 line-clamp-2">
                  &ldquo;{alert.text_evidence.snippet}&rdquo;
                </p>
                <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 pt-0.5">
                  <span className="font-mono truncate max-w-[140px] text-slate-600 dark:text-slate-300">{alert.text_evidence.source_id}</span>
                  {alert.text_evidence.cue && (
                    <span className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded font-mono text-[10px] border border-slate-200 dark:border-transparent">
                      cue: {alert.text_evidence.cue}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Knowledge Graph Provenance (if available) */}
            {alert.graph_provenance && (
              <div className="flex items-center gap-1.5 text-[11px] font-mono text-cyan-800 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-950/30 border border-cyan-200 dark:border-cyan-800/40 rounded-lg p-2 mb-3 shadow-2xs">
                <GitFork className="w-3.5 h-3.5 shrink-0 text-cyan-600 dark:text-cyan-400" />
                <span className="truncate">Graph Provenance: {alert.graph_provenance}</span>
              </div>
            )}

            {/* Recommendation Footer */}
            <div className="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300 pt-2 border-t border-slate-200/80 dark:border-slate-800/80">
              <UserCheck className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>{alert.recommendation}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
