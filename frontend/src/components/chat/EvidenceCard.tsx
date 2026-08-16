import React, { useState } from 'react';
import type { CitationMeta } from '../../api/types';
import { BookOpen, Database, GitCommit, Layers, ChevronDown, ChevronUp, Tag } from 'lucide-react';

interface EvidenceCardProps {
  citation: CitationMeta;
  isHighlighted?: boolean;
  onCardClick?: () => void;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({
  citation,
  isHighlighted = false,
  onCardClick,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getCategoryBadgeClass = (cat?: string) => {
    switch (cat?.toLowerCase()) {
      case 'guideline':
        return 'bg-brand-surface text-brand border-brand-border';
      case 'drug':
        return 'bg-status-info-bg text-status-info border-status-info/30';
      case 'research_paper':
        return 'bg-status-caution-bg text-status-caution border-status-caution/30';
      case 'private_report':
        return 'bg-status-success-bg text-status-success border-status-success/30';
      default:
        return 'bg-canvas text-ink-muted border-card-border';
    }
  };

  const getSourceTypeIcon = (srcType?: string) => {
    const st = srcType?.toLowerCase();
    if (st === 'both') {
      return (
        <span className="inline-flex items-center space-x-1 text-[10px] font-mono text-brand font-semibold">
          <Layers className="w-3 h-3" />
          <span>Hybrid (FAISS + Graph)</span>
        </span>
      );
    }
    if (st === 'graph') {
      return (
        <span className="inline-flex items-center space-x-1 text-[10px] font-mono text-status-info font-semibold">
          <GitCommit className="w-3 h-3" />
          <span>Kùzu Graph</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 text-[10px] font-mono text-ink-subtle font-semibold">
        <Database className="w-3 h-3" />
        <span>FAISS Vector</span>
      </span>
    );
  };

  // Normalized progress percentage for fused_score (e.g. 0.0 - 0.25 range scaled to 0-100%)
  const scorePercent = Math.min(100, Math.max(8, Math.round((citation.fused_score || 0) * 450)));

  return (
    <div
      id={`citation-${citation.label.replace(/[^a-zA-Z0-9]/g, '')}`}
      onClick={onCardClick}
      className={`p-4 rounded-xl border transition-all duration-300 bg-card shadow-xs hover:shadow-md ${
        isHighlighted
          ? 'border-brand ring-2 ring-brand/30 bg-brand-surface/30'
          : 'border-card-border hover:border-brand/40'
      }`}
    >
      {/* Header Row */}
      <div className="flex items-start justify-between gap-2 pb-2.5 mb-2.5 border-b border-card-border/80">
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Specimen-Tag Label Chip */}
          <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-brand-surface text-brand border border-brand-border shadow-2xs">
            {citation.label}
          </span>
          {/* Category Badge */}
          <span className={`px-2 py-0.5 text-[10px] font-heading font-bold uppercase tracking-wider rounded border ${getCategoryBadgeClass(citation.category)}`}>
            {citation.category || 'Evidence'}
          </span>
        </div>

        {/* Source Type Indicator */}
        <div className="shrink-0">
          {getSourceTypeIcon(citation.source_type)}
        </div>
      </div>

      {/* Document ID & Source Dataset */}
      <div className="mb-2 space-y-0.5">
        <div className="flex items-center space-x-1.5 text-xs text-ink font-semibold truncate" title={citation.title || citation.document_id}>
          <BookOpen className="w-3.5 h-3.5 text-brand shrink-0" />
          <span className="truncate">{citation.title || citation.document_id}</span>
        </div>
        <p className="text-[10px] font-mono text-ink-subtle truncate pl-5">
          Source: {citation.source}
        </p>
      </div>

      {/* Snippet Body */}
      <div className="bg-canvas p-3 rounded-lg border border-card-border text-xs text-ink leading-relaxed font-sans relative">
        <p className={isExpanded ? '' : 'line-clamp-3'}>
          "{citation.snippet}"
        </p>
        {citation.snippet.length > 180 && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="mt-1.5 flex items-center space-x-1 text-[11px] font-heading font-semibold text-brand hover:underline"
          >
            <span>{isExpanded ? 'Show less' : 'Read full snippet'}</span>
            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        )}
      </div>

      {/* Fused Score Meter */}
      <div className="mt-3 pt-2 flex items-center justify-between gap-3 text-xs font-mono">
        <span className="text-[10px] uppercase text-ink-subtle tracking-wider shrink-0">
          RRF Fused Score:
        </span>
        <div className="flex-1 flex items-center space-x-2">
          <div className="flex-1 h-1.5 rounded-full bg-card-border overflow-hidden">
            <div
              className="h-full rounded-full bg-brand transition-all duration-500"
              style={{ width: `${scorePercent}%` }}
            />
          </div>
          <span className="font-bold text-ink tabular-nums text-[11px]">
            {citation.fused_score?.toFixed(4) || '—'}
          </span>
        </div>
      </div>
    </div>
  );
};
