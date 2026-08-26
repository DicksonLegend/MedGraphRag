import React, { useState } from 'react';
import type { CitationMeta } from '../../api/types';
import {
  BookOpen,
  Database,
  GitCommit,
  Layers,
  ChevronDown,
  ChevronUp,
  Pill,
  Activity,
  FileText,
  FileSpreadsheet,
  Image as ImageIcon,
} from 'lucide-react';

interface EvidenceCardProps {
  citation: CitationMeta;
  isHighlighted?: boolean;
  onCardClick?: () => void;
  index?: number;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({
  citation,
  isHighlighted = false,
  onCardClick,
  index = 0,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getCategoryIcon = (cat?: string) => {
    const c = (cat || '').toLowerCase();
    if (c.includes('scan') || c.includes('radiology') || c.includes('imaging'))
      return <ImageIcon className="w-3.5 h-3.5 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />;
    if (c.includes('guideline')) return <BookOpen className="w-3.5 h-3.5 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />;
    if (c.includes('drug') || c.includes('med')) return <Pill className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 stroke-[1.75]" />;
    if (c.includes('lab') || c.includes('clinical') || c.includes('ecg'))
      return <Activity className="w-3.5 h-3.5 text-[#D97706] stroke-[1.75]" />;
    if (c.includes('private') || c.includes('report'))
      return <FileSpreadsheet className="w-3.5 h-3.5 text-[#16A34A] stroke-[1.75]" />;
    return <FileText className="w-3.5 h-3.5 text-slate-500 stroke-[1.75]" />;
  };

  const getCategoryBadgeClass = (cat?: string) => {
    const c = (cat || '').toLowerCase();
    if (c.includes('scan') || c.includes('radiology') || c.includes('imaging'))
      return 'bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border-teal-200 dark:border-teal-800';
    if (c.includes('guideline')) return 'bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border-teal-200 dark:border-teal-800';
    if (c.includes('drug')) return 'bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800';
    if (c.includes('research') || c.includes('paper') || c.includes('pubmed'))
      return 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800';
    if (c.includes('private') || c.includes('report'))
      return 'bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800';
    return 'bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-800';
  };

  const getSourceTypeIcon = (srcType?: string) => {
    const st = srcType?.toLowerCase();
    if (st === 'multimodal_scan') {
      return (
        <span className="inline-flex items-center space-x-1 h-7 px-2 rounded-lg text-xs font-mono font-medium text-teal-800 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800">
          <ImageIcon className="w-3.5 h-3.5 stroke-[1.75]" />
          <span>Patient Scan</span>
        </span>
      );
    }
    if (st === 'both') {
      return (
        <span className="inline-flex items-center space-x-1 h-7 px-2 rounded-lg text-xs font-mono font-medium text-teal-800 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800">
          <Layers className="w-3.5 h-3.5 stroke-[1.75]" />
          <span>Hybrid</span>
        </span>
      );
    }
    if (st === 'graph') {
      return (
        <span className="inline-flex items-center space-x-1 h-7 px-2 rounded-lg text-xs font-mono font-medium text-blue-800 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800">
          <GitCommit className="w-3.5 h-3.5 stroke-[1.75]" />
          <span>Graph</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 h-7 px-2 rounded-lg text-xs font-mono font-medium text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <Database className="w-3.5 h-3.5 stroke-[1.75]" />
        <span>FAISS</span>
      </span>
    );
  };

  const faissRank = index + 1;
  const graphRank = citation.source_type === 'both' ? Math.max(1, index) : citation.source_type === 'graph' ? index + 1 : '—';
  const originDeltaChip = `FAISS #${faissRank} · Graph #${graphRank}`;

  // Normalized progress percentage for fused_score (0.0 - 0.25 scaled to 0-100%)
  const scorePercent = Math.min(100, Math.max(8, Math.round((citation.fused_score || 0) * 450)));

  return (
    <div
      id={`citation-${citation.label.replace(/[^a-zA-Z0-9]/g, '')}`}
      onClick={onCardClick}
      className={`p-3.5 rounded-lg border transition-all duration-150 bg-white dark:bg-[#0F172A] shadow-xs cursor-pointer ${
        isHighlighted
          ? 'border-[#0F766E] dark:border-[#14B8A6] ring-2 ring-[#0F766E]/20 dark:ring-[#14B8A6]/20 bg-teal-50/20 dark:bg-teal-950/10'
          : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
      }`}
    >
      {/* Header Row */}
      <div className="flex items-start justify-between gap-2 pb-2 mb-2 border-b border-slate-100 dark:border-slate-800/80">
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Unified 28px Chip: Specimen-Tag Label */}
          <span className="inline-flex items-center justify-center h-7 px-2.5 text-xs font-mono font-semibold rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 shadow-2xs">
            {citation.label}
          </span>

          {/* Unified 28px Chip: Category Badge */}
          <span
            className={`inline-flex items-center space-x-1.5 h-7 px-2.5 text-xs font-medium rounded-lg border ${getCategoryBadgeClass(
              citation.category
            )}`}
          >
            {getCategoryIcon(citation.category)}
            <span>{citation.category || 'Evidence'}</span>
          </span>

          {/* Unified 28px Chip: Origin Delta */}
          <span className="inline-flex items-center h-7 px-2.5 text-xs font-mono font-medium rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400">
            {originDeltaChip}
          </span>
        </div>

        {/* Source Type Indicator */}
        <div className="shrink-0">{getSourceTypeIcon(citation.source_type)}</div>
      </div>

      {/* Document ID & Source Dataset */}
      <div className="mb-2 space-y-0.5">
        <div
          className="text-[13.5px] text-slate-900 dark:text-slate-100 font-medium truncate"
          title={citation.title || citation.document_id}
        >
          {citation.title || citation.document_id}
        </div>
        <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400 truncate">
          Source: {citation.source}
        </p>
      </div>

      {/* Snippet Body */}
      <div className="bg-slate-50 dark:bg-slate-900/70 p-3 rounded-lg border border-slate-200 dark:border-slate-800 text-[13.5px] text-slate-800 dark:text-slate-200 leading-relaxed font-sans relative">
        <p className={isExpanded ? '' : 'line-clamp-3'}>"{citation.snippet}"</p>
        {citation.snippet.length > 160 && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="mt-1 flex items-center space-x-1 text-xs font-medium text-[#0F766E] dark:text-[#14B8A6] hover:underline cursor-pointer"
          >
            <span>{isExpanded ? 'Show less' : 'Read full snippet'}</span>
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5 stroke-[1.75]" /> : <ChevronDown className="w-3.5 h-3.5 stroke-[1.75]" />}
          </button>
        )}
      </div>

      {/* Fused Score Meter */}
      <div className="mt-2.5 pt-1.5 flex items-center justify-between gap-3 text-xs font-mono">
        <span className="text-[11px] text-slate-500 dark:text-slate-400 uppercase tracking-wide shrink-0 font-medium">
          RRF Score:
        </span>
        <div className="flex-1 flex items-center space-x-2">
          <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-[#0F766E] dark:bg-[#14B8A6] transition-all duration-300"
              style={{ width: `${scorePercent}%` }}
            />
          </div>
          <span className="font-semibold text-slate-900 dark:text-slate-100 tabular-nums text-xs">
            {citation.fused_score?.toFixed(4) || '—'}
          </span>
        </div>
      </div>
    </div>
  );
};
