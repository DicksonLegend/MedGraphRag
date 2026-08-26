import React from 'react';
import { Compass, Database, GitFork, HelpCircle, Lightbulb, Search, ShieldAlert } from 'lucide-react';
import { KnowledgeGap } from '../../api/types';

interface KnowledgeGapCardProps {
  gaps?: KnowledgeGap[];
  onQueryClick?: (query: string) => void;
}

export const KnowledgeGapCard: React.FC<KnowledgeGapCardProps> = ({ gaps, onQueryClick }) => {
  if (!gaps || gaps.length === 0) {
    return null;
  }

  const getGapTypeBadge = (gapType: string) => {
    switch (gapType) {
      case 'corpus_retrieval':
        return {
          label: 'Corpus Retrieval Boundary',
          icon: <Database className="w-3.5 h-3.5" />,
          colorClass: 'bg-indigo-950/40 text-indigo-300 border-indigo-700/50',
          tagClass: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
        };
      case 'graph_coverage':
        return {
          label: 'Graph Relation Boundary',
          icon: <GitFork className="w-3.5 h-3.5" />,
          colorClass: 'bg-teal-950/40 text-teal-300 border-teal-700/50',
          tagClass: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
        };
      case 'evidence_faithfulness':
        return {
          label: 'Faithfulness & Support Gap',
          icon: <ShieldAlert className="w-3.5 h-3.5" />,
          colorClass: 'bg-rose-950/40 text-rose-300 border-rose-700/50',
          tagClass: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
        };
      default:
        return {
          label: 'Epistemic Uncertainty',
          icon: <Compass className="w-3.5 h-3.5" />,
          colorClass: 'bg-slate-900/60 text-slate-300 border-slate-700/50',
          tagClass: 'bg-slate-700/30 text-slate-300 border-slate-600/30',
        };
    }
  };

  return (
    <div className="space-y-3 my-3">
      {gaps.map((gap, idx) => {
        const badge = getGapTypeBadge(gap.gap_type);

        return (
          <div
            key={idx}
            className={`p-4 rounded-xl border ${badge.colorClass} shadow-md space-y-3 transition-all duration-200`}
            role="region"
            aria-label="Epistemic Knowledge Gap Analysis"
          >
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-slate-800/80 text-white shrink-0">
                  {badge.icon}
                </div>
                <div>
                  <span className="text-[10px] font-mono font-bold tracking-wider uppercase opacity-75 block">
                    Epistemic Diagnostic
                  </span>
                  <h4 className="text-xs sm:text-sm font-semibold text-white">
                    {badge.label}
                  </h4>
                </div>
              </div>

              <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded-md border ${badge.tagClass}`}>
                {gap.gap_type}
              </span>
            </div>

            {/* Gap Detail */}
            <p className="text-xs text-slate-300 leading-relaxed font-sans bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60">
              {gap.detail}
            </p>

            {/* Suggested Query Reformulations */}
            {gap.suggested_queries && gap.suggested_queries.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
                  <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
                  <span>Targeted Query Reformulations:</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {gap.suggested_queries.map((sq, qIdx) => (
                    <button
                      key={qIdx}
                      type="button"
                      onClick={() => onQueryClick?.(sq)}
                      className="px-2.5 py-1 text-xs font-mono bg-slate-900/90 hover:bg-slate-800 text-teal-300 hover:text-teal-200 border border-slate-700/60 rounded-lg transition-colors flex items-center gap-1 text-left cursor-pointer"
                      title="Click to search this query"
                    >
                      <Search className="w-3 h-3 shrink-0 opacity-70" />
                      <span>{sq}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested Authoritative Sources */}
            {gap.suggested_sources && gap.suggested_sources.length > 0 && (
              <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60 text-[11px] text-slate-400">
                <Compass className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                <span className="shrink-0 font-medium">Recommended Reference Sources:</span>
                <div className="flex flex-wrap gap-1.5">
                  {gap.suggested_sources.map((src, sIdx) => (
                    <span
                      key={sIdx}
                      className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-300 font-mono text-[10px] border border-slate-700/40"
                    >
                      {src}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
