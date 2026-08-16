import React, { useState } from 'react';
import type { LatencyBreakdown } from '../../api/types';
import { ChevronDown, ChevronUp, Cpu, Clock, CheckCircle2 } from 'lucide-react';

interface TechnicalDetailsProps {
  latency: LatencyBreakdown;
  retryCount: number;
  route: string;
}

export const TechnicalDetails: React.FC<TechnicalDetailsProps> = ({
  latency,
  retryCount,
  route,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-4 border border-card-border rounded-xl bg-canvas/60 overflow-hidden text-xs">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 flex items-center justify-between font-heading font-semibold text-ink-muted hover:text-ink hover:bg-card/60 transition-colors"
        aria-expanded={isOpen}
      >
        <div className="flex items-center space-x-2">
          <Cpu className="w-3.5 h-3.5 text-brand" />
          <span>Technical Diagnostics & Latency Breakdown</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="font-mono text-ink-subtle">
            Total: <strong className="text-ink font-bold">{latency.total?.toFixed(1) || '0.0'} ms</strong>
          </span>
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {isOpen && (
        <div className="p-4 border-t border-card-border bg-card/40 space-y-3 animate-fade-in font-mono">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="p-2 rounded bg-canvas border border-card-border">
              <span className="block text-[10px] text-ink-subtle uppercase">Intent Route</span>
              <span className="font-bold text-ink">{route}</span>
            </div>
            <div className="p-2 rounded bg-canvas border border-card-border">
              <span className="block text-[10px] text-ink-subtle uppercase">Verification Retries</span>
              <span className="font-bold text-ink">{retryCount}</span>
            </div>
            <div className="p-2 rounded bg-canvas border border-card-border">
              <span className="block text-[10px] text-ink-subtle uppercase">Hybrid Retrieval</span>
              <span className="font-bold text-ink tabular-nums">{latency.retrieval?.toFixed(1) || '0.0'} ms</span>
            </div>
            <div className="p-2 rounded bg-canvas border border-card-border">
              <span className="block text-[10px] text-ink-subtle uppercase">LLM Synthesis</span>
              <span className="font-bold text-ink tabular-nums">{latency.llm?.toFixed(1) || '0.0'} ms</span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 rounded bg-canvas border border-card-border">
              <span className="block text-[10px] text-ink-subtle uppercase">Router Latency</span>
              <span className="font-bold text-ink tabular-nums">{latency.router?.toFixed(1) || '0.0'} ms</span>
            </div>
            <div className="p-2 rounded bg-canvas border border-card-border">
              <span className="block text-[10px] text-ink-subtle uppercase">Context Pack</span>
              <span className="font-bold text-ink tabular-nums">{latency.context?.toFixed(1) || '0.0'} ms</span>
            </div>
            <div className="p-2 rounded bg-canvas border border-card-border">
              <span className="block text-[10px] text-ink-subtle uppercase">Verification Pass</span>
              <span className="font-bold text-ink tabular-nums">{latency.verification?.toFixed(1) || '0.0'} ms</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
