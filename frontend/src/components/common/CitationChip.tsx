import React, { useState, useRef, useEffect } from 'react';
import type { CitationMeta } from '../../api/types';
import { Tag, BookOpen, Layers, X, ExternalLink } from 'lucide-react';

interface CitationChipProps {
  label: string;
  citation?: CitationMeta;
  onSelect?: (label: string) => void;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  label,
  citation,
  onSelect,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsOpen(!isOpen);
    if (onSelect) {
      onSelect(label);
    }
  };

  if (!citation) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-xs font-mono font-medium rounded bg-card-border/60 text-ink-muted border border-card-border">
        {label}
      </span>
    );
  }

  return (
    <span className="relative inline-block mx-0.5 my-0.5 align-baseline">
      {/* Specimen-Tag Style Chip Button */}
      <button
        type="button"
        onClick={handleClick}
        className="inline-flex items-center space-x-1 px-2 py-0.5 rounded border border-brand-border bg-brand-surface text-brand hover:bg-brand hover:text-white transition-all text-xs font-mono font-semibold shadow-2xs group focus:outline-hidden cursor-pointer"
        title="View clinical evidence citation in proof console"
        aria-expanded={isOpen}
      >
        <Tag className="w-3 h-3 opacity-70 group-hover:opacity-100" />
        <span>{label}</span>
      </button>

      {/* Interactive Evidence Popover */}
      {isOpen && (
        <div
          ref={popoverRef}
          className="absolute z-50 bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-80 sm:w-96 p-4 rounded-xl border border-card-border bg-card shadow-xl backdrop-blur-md text-left animate-fade-in"
          role="dialog"
          aria-label={`Citation details for ${label}`}
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-card-border">
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-brand-surface text-brand rounded border border-brand-border">
                {citation.label}
              </span>
              <span className="text-xs font-heading font-semibold text-ink capitalize">
                {citation.category || 'Evidence Chunk'}
              </span>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsOpen(false);
              }}
              className="p-1 rounded-md text-ink-subtle hover:text-ink hover:bg-canvas transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-2 text-xs mb-3 font-mono">
            <div className="bg-canvas p-2 rounded border border-card-border">
              <span className="block text-[10px] uppercase tracking-wider text-ink-subtle">RRF Fused Score</span>
              <span className="font-bold text-ink tabular-nums">{citation.fused_score?.toFixed(4) || '—'}</span>
            </div>
            <div className="bg-canvas p-2 rounded border border-card-border">
              <span className="block text-[10px] uppercase tracking-wider text-ink-subtle">Retrieval Origin</span>
              <span className="font-bold text-ink uppercase">{citation.source_type || 'hybrid'}</span>
            </div>
          </div>

          {/* Document Source */}
          <div className="space-y-1 text-xs mb-3">
            <div className="flex items-center space-x-1.5 text-ink-muted">
              <BookOpen className="w-3.5 h-3.5 text-brand" />
              <span className="font-medium text-ink truncate">{citation.title || citation.document_id}</span>
            </div>
            <p className="text-[11px] font-mono text-ink-subtle truncate">
              Dataset: {citation.source}
            </p>
          </div>

          {/* Evidence Snippet */}
          <div className="bg-canvas p-2.5 rounded-lg border border-card-border text-xs text-ink leading-relaxed max-h-36 overflow-y-auto font-sans mb-2">
            "{citation.snippet}"
          </div>

          {onSelect && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsOpen(false);
                onSelect(label);
              }}
              className="w-full py-1.5 px-2.5 rounded-lg bg-brand-surface border border-brand-border text-brand text-[11px] font-heading font-semibold hover:bg-brand hover:text-white transition-colors flex items-center justify-center space-x-1"
            >
              <ExternalLink className="w-3 h-3" />
              <span>Inspect in Evidence Console</span>
            </button>
          )}
        </div>
      )}
    </span>
  );
};
