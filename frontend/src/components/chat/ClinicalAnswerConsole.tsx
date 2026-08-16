import React, { useState, useEffect, useRef } from 'react';
import type { QueryResponse } from '../../api/types';
import { MarkdownAnswer } from './MarkdownAnswer';
import { EvidenceCard } from './EvidenceCard';
import { SubwayMap } from '../common/SubwayMap';
import { ConfidenceRing } from '../common/ConfidenceRing';
import { DisclaimerFooter } from '../common/DisclaimerFooter';
import { getAnswerStatusProps } from '../../lib/utils';
import {
  FileText,
  GitCommit,
  Activity,
  Layers,
  HelpCircle,
  Clock,
  Cpu,
  ShieldCheck,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Info,
} from 'lucide-react';

interface ClinicalAnswerConsoleProps {
  result: QueryResponse;
  searchDestination?: string;
}

type TabType = 'evidence' | 'graph' | 'diagnostics';

export const ClinicalAnswerConsole: React.FC<ClinicalAnswerConsoleProps> = ({
  result,
  searchDestination = 'global',
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('evidence');
  const [highlightedCitation, setHighlightedCitation] = useState<string | null>(null);
  const [showConfidenceHelp, setShowConfidenceHelp] = useState(false);
  const evidenceContainerRef = useRef<HTMLDivElement>(null);

  const citations = result.citations || [];
  const graphPaths = result.graph_paths || [];
  const statusProps = getAnswerStatusProps(result.answer_status);

  // Handle citation click from text: switch tab and scroll into view
  const handleCitationClick = (label: string) => {
    setActiveTab('evidence');
    setHighlightedCitation(label);

    setTimeout(() => {
      const el = document.getElementById(`citation-${label.replace(/[^a-zA-Z0-9]/g, '')}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }, 100);
  };

  // Calculate percentage widths for latency breakdown bar
  const lat = result.latency_breakdown || { total: 0 };
  const totalMs = Math.max(1, lat.total || 1);
  const routerPct = Math.max(1, Math.round(((lat.router || 0) / totalMs) * 100));
  const retPct = Math.max(2, Math.round(((lat.retrieval || 0) / totalMs) * 100));
  const ctxPct = Math.max(1, Math.round(((lat.context || 0) / totalMs) * 100));
  const llmPct = Math.max(5, Math.round(((lat.llm || 0) / totalMs) * 100));
  const verPct = Math.max(2, Math.round(((lat.verification || 0) / totalMs) * 100));

  return (
    <div className="rounded-2xl border border-card-border bg-card shadow-sm overflow-hidden animate-fade-in">
      {/* Top Telemetry Header Bar */}
      <div className="p-4 sm:p-5 border-b border-card-border bg-canvas/40 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Destination Badge */}
          <span className="px-2.5 py-1 text-xs font-mono font-bold bg-card text-ink rounded-lg border border-card-border shadow-2xs">
            {searchDestination === 'global' ? '🌐 Global Knowledge Base' : `🔒 Private Store (${searchDestination})`}
          </span>

          {/* Route Pill */}
          <span className="px-2.5 py-1 text-xs font-mono font-bold bg-brand-surface text-brand rounded-lg border border-brand-border">
            Route: {result.route}
          </span>

          {/* Status Verdict Pill */}
          <div className="relative group">
            <span className={`px-2.5 py-1 text-xs font-heading font-semibold rounded-lg border flex items-center space-x-1.5 cursor-help ${statusProps.badgeClass}`}>
              <span>{statusProps.label}</span>
              <HelpCircle className="w-3 h-3 opacity-60" />
            </span>
            {/* Tooltip */}
            <div className="absolute left-0 top-full mt-1.5 hidden group-hover:block z-50 w-64 p-2.5 rounded-xl bg-card border border-card-border shadow-xl text-[11px] font-sans text-ink leading-relaxed">
              <strong>Status Verdict:</strong> All extracted factual claims were checked against cited chunks.
            </div>
          </div>
        </div>

        {/* Right Side Header: Confidence Ring & Evidence Shortcut */}
        <div className="flex items-center space-x-3">
          <ConfidenceRing
            score={result.final_confidence}
            tier={result.confidence_tier}
          />
          {citations.length > 0 && (
            <button
              type="button"
              onClick={() => setActiveTab('evidence')}
              className="hidden sm:inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border border-brand-border bg-brand-surface text-brand hover:bg-brand hover:text-white transition-all text-xs font-heading font-bold shadow-2xs cursor-pointer"
            >
              <span>View Evidence ({citations.length})</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Two-Pane Body Layout (Left: Answer, Right: Evidence Console) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[580px]">
        {/* LEFT PANE: Synthesized Clinical Answer (7 cols on lg) */}
        <div className="lg:col-span-7 p-6 sm:p-7 border-b lg:border-b-0 lg:border-r border-card-border flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-card-border/60">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-brand" />
                <h3 className="text-xs font-heading font-bold text-ink uppercase tracking-wider">
                  Verified Clinical Synthesis
                </h3>
              </div>
              <span className="text-[11px] font-mono text-ink-subtle">
                {citations.length} cited evidence chunks
              </span>
            </div>

            {/* Answer Content */}
            <div className="bg-canvas/40 p-5 rounded-xl border border-card-border/80 text-ink leading-relaxed">
              <MarkdownAnswer
                content={result.answer_text}
                citations={citations}
                onCitationClick={handleCitationClick}
              />
            </div>
          </div>

          {/* Bottom Disclaimer */}
          <DisclaimerFooter />
        </div>

        {/* RIGHT PANE: Evidence & Verification Console (5 cols on lg) */}
        <div className="lg:col-span-5 bg-canvas/30 flex flex-col h-full">
          {/* Tab Navigation */}
          <div className="flex items-center border-b border-card-border bg-card/60 px-2 pt-2 gap-1 shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab('evidence')}
              className={`flex items-center space-x-1.5 px-3.5 py-2.5 rounded-t-xl text-xs font-heading font-bold border-t border-x transition-all ${
                activeTab === 'evidence'
                  ? 'bg-canvas text-brand border-card-border -mb-px'
                  : 'text-ink-muted border-transparent hover:text-ink hover:bg-canvas/50'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Evidence ({citations.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('graph')}
              className={`flex items-center space-x-1.5 px-3.5 py-2.5 rounded-t-xl text-xs font-heading font-bold border-t border-x transition-all ${
                activeTab === 'graph'
                  ? 'bg-canvas text-brand border-card-border -mb-px'
                  : 'text-ink-muted border-transparent hover:text-ink hover:bg-canvas/50'
              }`}
            >
              <GitCommit className="w-3.5 h-3.5" />
              <span>Graph Paths ({graphPaths.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('diagnostics')}
              className={`flex items-center space-x-1.5 px-3.5 py-2.5 rounded-t-xl text-xs font-heading font-bold border-t border-x transition-all ${
                activeTab === 'diagnostics'
                  ? 'bg-canvas text-brand border-card-border -mb-px'
                  : 'text-ink-muted border-transparent hover:text-ink hover:bg-canvas/50'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Diagnostics</span>
            </button>
          </div>

          {/* Tab Content Container */}
          <div
            ref={evidenceContainerRef}
            className="flex-1 p-4 sm:p-5 overflow-y-auto max-h-[640px] space-y-4 font-sans"
          >
            {/* TAB 1: EVIDENCE CARDS */}
            {activeTab === 'evidence' && (
              <div className="space-y-3 animate-fade-in">
                {citations.length === 0 ? (
                  <div className="p-8 text-center text-xs font-mono text-ink-subtle rounded-xl border border-dashed border-card-border bg-card/60">
                    No citation chunks associated with this output.
                  </div>
                ) : (
                  citations.map((cite) => (
                    <EvidenceCard
                      key={cite.label}
                      citation={cite}
                      isHighlighted={highlightedCitation === cite.label}
                      onCardClick={() => setHighlightedCitation(cite.label)}
                    />
                  ))
                )}
              </div>
            )}

            {/* TAB 2: GRAPH PATHS (Subway Map) */}
            {activeTab === 'graph' && (
              <div className="space-y-3 animate-fade-in">
                {graphPaths.length === 0 ? (
                  <div className="p-8 text-center text-xs font-mono text-ink-subtle rounded-xl border border-dashed border-card-border bg-card/60">
                    No graph traversal paths for this answer.
                  </div>
                ) : (
                  <SubwayMap paths={graphPaths} />
                )}
              </div>
            )}

            {/* TAB 3: DIAGNOSTICS & TELEMETRY */}
            {activeTab === 'diagnostics' && (
              <div className="space-y-4 animate-fade-in">
                {/* Confidence Details Card */}
                <div className="p-4 rounded-xl border border-card-border bg-card shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="font-heading font-bold text-xs text-ink uppercase tracking-wider">
                      Confidence Gate & Scoring
                    </h4>
                    <button
                      type="button"
                      onClick={() => setShowConfidenceHelp(!showConfidenceHelp)}
                      className="text-[11px] font-mono text-brand hover:underline flex items-center space-x-1"
                    >
                      <Info className="w-3 h-3" />
                      <span>Threshold Guidelines</span>
                    </button>
                  </div>

                  {showConfidenceHelp && (
                    <div className="p-3 rounded-lg bg-canvas border border-card-border text-[11px] font-mono space-y-1 text-ink animate-fade-in">
                      <div className="flex justify-between">
                        <span className="text-status-success font-bold">🟢 High Confidence:</span>
                        <span>Score ≥ 0.75</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-status-caution font-bold">🟡 Medium Confidence:</span>
                        <span>0.50 ≤ Score &lt; 0.75</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-status-danger font-bold">🔴 Low Confidence:</span>
                        <span>Score &lt; 0.50</span>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="p-2.5 rounded bg-canvas border border-card-border">
                      <span className="block text-[10px] text-ink-subtle uppercase">Final Confidence</span>
                      <span className="text-sm font-bold text-ink tabular-nums">
                        {result.final_confidence?.toFixed(3) || '0.000'} ({Math.round(result.final_confidence * 100)}%)
                      </span>
                    </div>
                    <div className="p-2.5 rounded bg-canvas border border-card-border">
                      <span className="block text-[10px] text-ink-subtle uppercase">Confidence Tier</span>
                      <span className="text-sm font-bold text-brand uppercase">
                        {result.confidence_tier}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Multi-Segment Latency Bar */}
                <div className="p-4 rounded-xl border border-card-border bg-card shadow-xs space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-1.5">
                      <Clock className="w-3.5 h-3.5 text-brand" />
                      <h4 className="font-heading font-bold text-ink uppercase tracking-wider">
                        Execution Latency Breakdown
                      </h4>
                    </div>
                    <span className="font-mono font-bold text-ink tabular-nums">
                      Total: {lat.total?.toFixed(1) || '0.0'} ms
                    </span>
                  </div>

                  {/* Horizontal Segmented Bar */}
                  <div className="h-3 w-full rounded-full bg-canvas border border-card-border flex overflow-hidden">
                    <div
                      title={`Router: ${lat.router?.toFixed(1)} ms`}
                      className="h-full bg-slate-400"
                      style={{ width: `${routerPct}%` }}
                    />
                    <div
                      title={`Retrieval: ${lat.retrieval?.toFixed(1)} ms`}
                      className="h-full bg-blue-500"
                      style={{ width: `${retPct}%` }}
                    />
                    <div
                      title={`Context: ${lat.context?.toFixed(1)} ms`}
                      className="h-full bg-teal-500"
                      style={{ width: `${ctxPct}%` }}
                    />
                    <div
                      title={`LLM Synthesis: ${lat.llm?.toFixed(1)} ms`}
                      className="h-full bg-emerald-500"
                      style={{ width: `${llmPct}%` }}
                    />
                    <div
                      title={`Verification: ${lat.verification?.toFixed(1)} ms`}
                      className="h-full bg-amber-500"
                      style={{ width: `${verPct}%` }}
                    />
                  </div>

                  {/* Latency Legend with Mono Numbers */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] font-mono pt-1">
                    <div className="flex items-center space-x-1.5 text-ink">
                      <span className="w-2 h-2 rounded-full bg-slate-400 shrink-0" />
                      <span className="truncate">Router: <strong>{lat.router?.toFixed(1) || '0.0'} ms</strong></span>
                    </div>
                    <div className="flex items-center space-x-1.5 text-ink">
                      <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                      <span className="truncate">Retrieval: <strong>{lat.retrieval?.toFixed(1) || '0.0'} ms</strong></span>
                    </div>
                    <div className="flex items-center space-x-1.5 text-ink">
                      <span className="w-2 h-2 rounded-full bg-teal-500 shrink-0" />
                      <span className="truncate">Context: <strong>{lat.context?.toFixed(1) || '0.0'} ms</strong></span>
                    </div>
                    <div className="flex items-center space-x-1.5 text-ink">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                      <span className="truncate">LLM: <strong>{lat.llm?.toFixed(1) || '0.0'} ms</strong></span>
                    </div>
                    <div className="flex items-center space-x-1.5 text-ink">
                      <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                      <span className="truncate">Verif: <strong>{lat.verification?.toFixed(1) || '0.0'} ms</strong></span>
                    </div>
                    <div className="flex items-center space-x-1.5 text-ink">
                      <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
                      <span className="truncate">Retries: <strong>{result.retry_count || 0}</strong></span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
