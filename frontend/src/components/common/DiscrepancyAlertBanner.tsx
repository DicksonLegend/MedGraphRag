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
          ? 'border-red-500/80 bg-red-950/20 text-red-300'
          : 'border-amber-500/80 bg-amber-950/20 text-amber-300';
        const badgeBg = isHigh
          ? 'bg-red-500/20 text-red-400 border-red-500/40'
          : 'bg-amber-500/20 text-amber-400 border-amber-500/40';

        return (
          <div
            key={idx}
            className={`p-4 rounded-xl border ${borderColor} shadow-lg transition-all duration-200`}
            role="alert"
            aria-live="assertive"
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <div className={`p-1.5 rounded-lg ${isHigh ? 'bg-red-500 text-white' : 'bg-amber-500 text-slate-950'}`}>
                  {isHigh ? <ShieldAlert className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                </div>
                <div>
                  <span className="text-xs font-mono font-bold tracking-wider uppercase opacity-75">
                    Cross-Modal Conflict Detected
                  </span>
                  <h4 className="text-sm font-semibold capitalize text-white">
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
              <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1.5">
                <div className="flex items-center gap-1.5 text-sky-400 font-semibold">
                  <Eye className="w-3.5 h-3.5" />
                  <span>Visual Analysis (BiomedCLIP)</span>
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span>Detected State:</span>
                  <span className={`font-mono font-bold ${alert.visual_evidence.negated ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {alert.visual_evidence.negated ? 'NEGATED / ABSENT' : 'POSITIVE (Present)'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-400">
                  <span>Model Confidence:</span>
                  <span className="font-mono text-slate-200">
                    {(alert.visual_evidence.score * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Text Evidence Side */}
              <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1.5">
                <div className="flex items-center gap-1.5 text-purple-400 font-semibold">
                  <FileText className="w-3.5 h-3.5" />
                  <span>Clinical Text Evidence</span>
                </div>
                <p className="italic text-slate-300 line-clamp-2">
                  &ldquo;{alert.text_evidence.snippet}&rdquo;
                </p>
                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-0.5">
                  <span className="font-mono truncate max-w-[140px]">{alert.text_evidence.source_id}</span>
                  {alert.text_evidence.cue && (
                    <span className="px-1.5 py-0.2 bg-slate-800 text-slate-300 rounded font-mono text-[10px]">
                      cue: {alert.text_evidence.cue}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Knowledge Graph Provenance (if available) */}
            {alert.graph_provenance && (
              <div className="flex items-center gap-1.5 text-[11px] font-mono text-cyan-400 bg-cyan-950/30 border border-cyan-800/40 rounded-lg p-2 mb-3">
                <GitFork className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">Graph Provenance: {alert.graph_provenance}</span>
              </div>
            )}

            {/* Recommendation Footer */}
            <div className="flex items-center gap-2 text-xs font-medium text-slate-300 pt-2 border-t border-slate-800/80">
              <UserCheck className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span>{alert.recommendation}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
