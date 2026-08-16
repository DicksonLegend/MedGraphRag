import React, { useState } from 'react';
import { queryApi } from '../api/query';
import type { QueryResponse } from '../api/types';
import { useAuthStore } from '../stores/authStore';
import { EcgLoader } from '../components/common/EcgLoader';
import { ConfidenceRing } from '../components/common/ConfidenceRing';
import { SubwayMap } from '../components/common/SubwayMap';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { ErrorState } from '../components/common/ErrorState';
import { MarkdownAnswer } from '../components/chat/MarkdownAnswer';
import { TechnicalDetails } from '../components/chat/TechnicalDetails';
import { getAnswerStatusProps } from '../lib/utils';
import {
  Send,
  Lock,
  Globe,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  XCircle,
  ShieldAlert,
  Info,
} from 'lucide-react';

export const ChatPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searchPrivate, setSearchPrivate] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isColdModel, setIsColdModel] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { user_id } = useAuthStore();

  const handleSearch = async (queryText?: string) => {
    const q = (queryText || query).trim();
    if (!q) return;

    setIsLoading(true);
    setErrorMsg(null);
    setResult(null);

    // If first query or cold start, inform user
    const coldTimer = setTimeout(() => {
      setIsColdModel(true);
    }, 3000);

    try {
      const destination = searchPrivate && user_id ? user_id : 'global';
      const res = await queryApi.submitQuery({
        query: q,
        destination,
      });
      setResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred during query execution.');
    } finally {
      clearTimeout(coldTimer);
      setIsLoading(false);
      setIsColdModel(false);
    }
  };

  const sampleQueries = [
    'potassium hyperkalemia ECG changes peaked T waves treatment',
    'warfarin INR monitoring guidelines atrial fibrillation',
    'metformin contraindications chronic kidney disease eGFR threshold',
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Description Card */}
      <div className="p-5 rounded-2xl border border-card-border bg-card shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink">
              Self-Verifying Medical Query & Evidence Search
            </h2>
            <p className="text-xs text-ink-muted leading-relaxed font-sans">
              Combines FAISS MedCPT vector retrieval with Kùzu biomedical knowledge graph reasoning and claim-by-claim verification.
            </p>
          </div>

          {/* Search Destination Switch */}
          <div className="flex items-center space-x-2 bg-canvas p-1.5 rounded-xl border border-card-border shrink-0">
            <button
              type="button"
              onClick={() => setSearchPrivate(false)}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-heading font-semibold transition-all ${
                !searchPrivate
                  ? 'bg-brand text-white shadow-xs'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Global Index</span>
            </button>
            <button
              type="button"
              onClick={() => setSearchPrivate(true)}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-heading font-semibold transition-all ${
                searchPrivate
                  ? 'bg-brand text-white shadow-xs'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              <Lock className="w-3.5 h-3.5" />
              <span>My Private Reports</span>
            </button>
          </div>
        </div>

        {/* Query Input Box */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSearch();
          }}
          className="mt-4 flex gap-2"
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              searchPrivate
                ? `Query your private diagnostic records (${user_id})...`
                : 'Enter medical inquiry, drug interaction, or clinical guideline query...'
            }
            className="flex-1 px-4 py-3 rounded-xl border border-card-border bg-canvas text-ink text-sm font-sans focus:border-brand focus:ring-1 focus:ring-brand transition-colors"
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center space-x-2 px-6 py-3 rounded-xl font-heading font-bold text-white bg-brand hover:bg-brand-hover active:scale-[0.98] disabled:opacity-50 transition-all shadow-sm shrink-0"
          >
            <Send className="w-4 h-4" />
            <span className="hidden sm:inline">{isLoading ? 'Searching...' : 'Search'}</span>
          </button>
        </form>

        {/* Quick Sample Queries */}
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-mono text-ink-subtle flex items-center space-x-1 mr-1">
            <Sparkles className="w-3 h-3 text-brand" />
            <span>Example queries:</span>
          </span>
          {sampleQueries.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setQuery(sample);
                handleSearch(sample);
              }}
              className="text-[11px] font-sans px-2.5 py-1 rounded-lg bg-canvas hover:bg-card-border text-ink-muted hover:text-ink border border-card-border transition-colors text-left truncate max-w-xs"
            >
              {sample}
            </button>
          ))}
        </div>
      </div>

      {/* Loading State with ECG Wave */}
      {isLoading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs">
          <EcgLoader
            isCold={isColdModel}
            label="Executing Hybrid Vector-Graph Retrieval..."
            sublabel="Retrieving evidence chunks, exploring Kùzu knowledge graph relationships, and synthesizing verified answer..."
          />
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="Query Processing Error"
          message={errorMsg}
          onRetry={() => handleSearch()}
        />
      )}

      {/* Result Presentation */}
      {result && !isLoading && (
        <div className="p-6 sm:p-8 rounded-2xl border border-card-border bg-card shadow-sm space-y-6 animate-fade-in">
          {/* Header Metadata Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-card-border">
            <div className="flex flex-wrap items-center gap-2">
              {/* Route Badge */}
              <span className="px-2.5 py-1 text-xs font-mono font-bold bg-canvas text-ink rounded-lg border border-card-border uppercase">
                Route: {result.route}
              </span>

              {/* Status Pill */}
              {(() => {
                const statusProps = getAnswerStatusProps(result.answer_status);
                return (
                  <span className={`px-2.5 py-1 text-xs font-heading font-semibold rounded-lg border flex items-center space-x-1.5 ${statusProps.badgeClass}`}>
                    <span>{statusProps.label}</span>
                  </span>
                );
              })()}
            </div>

            {/* Confidence Ring Gauge */}
            <ConfidenceRing
              score={result.final_confidence}
              tier={result.confidence_tier}
            />
          </div>

          {/* Synthesized Answer Text with Specimen-Tag Citations */}
          <div className="bg-canvas/50 p-5 rounded-xl border border-card-border/80">
            <h3 className="text-xs font-heading font-bold text-ink uppercase tracking-wider mb-3">
              Verified Clinical Synthesis
            </h3>
            <MarkdownAnswer
              content={result.answer_text}
              citations={result.citations}
            />
          </div>

          {/* Subway Map for Knowledge Graph Paths */}
          {result.graph_paths && result.graph_paths.length > 0 && (
            <SubwayMap paths={result.graph_paths} />
          )}

          {/* Technical Diagnostics */}
          <TechnicalDetails
            latency={result.latency_breakdown}
            retryCount={result.retry_count}
            route={result.route}
          />

          {/* Medical Disclaimer */}
          <DisclaimerFooter />
        </div>
      )}
    </div>
  );
};
