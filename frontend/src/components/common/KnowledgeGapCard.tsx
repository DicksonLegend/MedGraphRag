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
          label: 'Limited Document Coverage',
          icon: <Database className="w-3.5 h-3.5" />,
          colorClass: 'bg-indigo-50/90 dark:bg-indigo-950/40 text-indigo-950 dark:text-indigo-200 border-indigo-200 dark:border-indigo-700/50',
          tagClass: 'bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-500/20 dark:text-indigo-300 dark:border-indigo-500/40',
          iconBg: 'bg-indigo-600 text-white dark:bg-indigo-500/30 dark:text-indigo-300',
        };
      case 'graph_coverage':
        return {
          label: 'Knowledge Graph Gap',
          icon: <GitFork className="w-3.5 h-3.5" />,
          colorClass: 'bg-teal-50/90 dark:bg-teal-950/40 text-teal-950 dark:text-teal-200 border-teal-200 dark:border-teal-700/50',
          tagClass: 'bg-teal-100 text-teal-800 border-teal-300 dark:bg-teal-500/20 dark:text-teal-300 dark:border-teal-500/40',
          iconBg: 'bg-teal-600 text-white dark:bg-teal-500/30 dark:text-teal-300',
        };
      case 'evidence_faithfulness':
        return {
          label: 'Incomplete Evidence Support',
          icon: <ShieldAlert className="w-3.5 h-3.5" />,
          colorClass: 'bg-rose-50/90 dark:bg-rose-950/40 text-rose-950 dark:text-rose-200 border-rose-200 dark:border-rose-700/50',
          tagClass: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-500/20 dark:text-rose-300 dark:border-rose-500/40',
          iconBg: 'bg-rose-600 text-white dark:bg-rose-500/30 dark:text-rose-300',
        };
      default:
        return {
          label: 'Knowledge Uncertainty',
          icon: <Compass className="w-3.5 h-3.5" />,
          colorClass: 'bg-slate-50 dark:bg-slate-900/60 text-slate-900 dark:text-slate-200 border-slate-200 dark:border-slate-700/50',
          tagClass: 'bg-slate-200 text-slate-800 border-slate-300 dark:bg-slate-700/30 dark:text-slate-300 dark:border-slate-600/40',
          iconBg: 'bg-slate-700 text-white dark:bg-slate-800 dark:text-slate-300',
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
            className={`p-4 rounded-xl border ${badge.colorClass} shadow-xs space-y-3 transition-all duration-200`}
            role="region"
            aria-label="Clinical Knowledge Gap Analysis"
          >
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className={`p-1.5 rounded-lg ${badge.iconBg} shrink-0 shadow-2xs`}>
                  {badge.icon}
                </div>
                <div>
                  <span className="text-[10px] font-mono font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400 block">
                    Knowledge Diagnostic
                  </span>
                  <h4 className="text-xs sm:text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {badge.label}
                  </h4>
                </div>
              </div>

              <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded-md border ${badge.tagClass}`}>
                {gap.gap_type}
              </span>
            </div>

            {/* Gap Detail */}
            <p className="text-xs text-slate-800 dark:text-slate-200 leading-relaxed font-sans bg-white/90 dark:bg-slate-950/50 p-3 rounded-lg border border-slate-200/80 dark:border-slate-800/80 shadow-2xs">
              {gap.detail}
            </p>

            {/* Suggested Query Reformulations */}
            {gap.suggested_queries && gap.suggested_queries.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                  <Lightbulb className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" />
                  <span>Targeted Query Reformulations:</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {gap.suggested_queries.map((sq, qIdx) => (
                    <button
                      key={qIdx}
                      type="button"
                      onClick={() => onQueryClick?.(sq)}
                      className="px-2.5 py-1.5 text-xs font-mono bg-white hover:bg-teal-50 dark:bg-slate-900 dark:hover:bg-slate-800 text-teal-800 hover:text-teal-900 dark:text-teal-300 dark:hover:text-teal-200 border border-teal-200 dark:border-slate-700/60 rounded-lg transition-colors flex items-center gap-1.5 text-left cursor-pointer shadow-2xs"
                      title="Click to search this query"
                    >
                      <Search className="w-3 h-3 shrink-0 text-teal-600 dark:text-teal-400 opacity-80" />
                      <span>{sq}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested Authoritative Sources */}
            {gap.suggested_sources && gap.suggested_sources.length > 0 && (
              <div className="flex items-center gap-2 pt-2 border-t border-slate-200/80 dark:border-slate-800/60 text-[11px] text-slate-600 dark:text-slate-400">
                <Compass className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 shrink-0" />
                <span className="shrink-0 font-medium">Recommended Reference Sources:</span>
                <div className="flex flex-wrap gap-1.5">
                  {gap.suggested_sources.map((src, sIdx) => (
                    <span
                      key={sIdx}
                      className="px-2 py-0.5 rounded bg-white dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 font-mono text-[10px] border border-slate-200 dark:border-slate-700/60 shadow-2xs"
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
