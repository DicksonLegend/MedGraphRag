import React, { useState } from 'react';
import { queryApi } from '../api/query';
import type { QueryResponse } from '../api/types';
import { useAuthStore } from '../stores/authStore';
import { EcgLoader } from '../components/common/EcgLoader';
import { ClinicalAnswerConsole } from '../components/chat/ClinicalAnswerConsole';
import { ErrorState } from '../components/common/ErrorState';
import {
  Send,
  Lock,
  Globe,
  Sparkles,
  HeartPulse,
  Pill,
  Activity,
  ArrowRight,
  Database,
  Search,
} from 'lucide-react';

interface SuggestionCard {
  title: string;
  category: string;
  query: string;
  icon: React.ReactNode;
}

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

    // Warm-up detection notice
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

  const suggestionCards: SuggestionCard[] = [
    {
      title: 'Hyperkalemia ECG Changes & Treatment',
      category: 'Cardiology & Electrolytes',
      query: 'potassium hyperkalemia ECG changes peaked T waves treatment',
      icon: <HeartPulse className="w-4 h-4 text-status-danger" />,
    },
    {
      title: 'Warfarin Anticoagulation Guidelines',
      category: 'Pharmacology & Hemostasis',
      query: 'warfarin INR monitoring guidelines atrial fibrillation',
      icon: <Pill className="w-4 h-4 text-status-info" />,
    },
    {
      title: 'Metformin Renal Thresholds (eGFR)',
      category: 'Nephrology & Endocrinology',
      query: 'metformin contraindications chronic kidney disease eGFR threshold',
      icon: <Activity className="w-4 h-4 text-brand" />,
    },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Clinical Query Header & Search Console */}
      <div className="p-6 sm:p-7 rounded-2xl border border-card-border bg-card shadow-xs space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-xl bg-brand text-white shadow-xs">
                <Search className="w-5 h-5" />
              </div>
              <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink tracking-tight">
                Clinical Evidence Search & Verification Console
              </h2>
            </div>
            <p className="text-xs text-ink-muted leading-relaxed font-sans max-w-3xl">
              Cross-examines FAISS MedCPT article vectors and Kùzu biomedical knowledge graph connections with strict claim-by-claim faithfulness verification.
            </p>
          </div>

          {/* Search Destination Switch */}
          <div className="flex items-center space-x-2 bg-canvas p-1.5 rounded-xl border border-card-border shrink-0 self-start lg:self-auto">
            <button
              type="button"
              onClick={() => setSearchPrivate(false)}
              className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-heading font-semibold transition-all cursor-pointer ${
                !searchPrivate
                  ? 'bg-brand text-white shadow-xs'
                  : 'text-ink-muted hover:text-ink hover:bg-card/50'
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Global Index</span>
            </button>
            <button
              type="button"
              onClick={() => setSearchPrivate(true)}
              className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-heading font-semibold transition-all cursor-pointer ${
                searchPrivate
                  ? 'bg-brand text-white shadow-xs'
                  : 'text-ink-muted hover:text-ink hover:bg-card/50'
              }`}
            >
              <Lock className="w-3.5 h-3.5" />
              <span>My Reports ({user_id || 'User'})</span>
            </button>
          </div>
        </div>

        {/* Query Input Box */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSearch();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              searchPrivate
                ? `Query your private diagnostic records (${user_id})...`
                : 'Enter biomedical question, medication protocol, or diagnostic inquiry...'
            }
            className="flex-1 px-4 py-3 rounded-xl border border-card-border bg-canvas text-ink text-sm font-sans focus:border-brand focus:ring-1 focus:ring-brand transition-colors"
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center space-x-2 px-6 py-3 rounded-xl font-heading font-bold text-white bg-brand hover:bg-brand-hover active:scale-[0.98] disabled:opacity-50 transition-all shadow-md shrink-0 cursor-pointer"
          >
            <Send className="w-4 h-4" />
            <span className="hidden sm:inline">{isLoading ? 'Synthesizing...' : 'Search'}</span>
          </button>
        </form>

        {/* Suggestion Cards with Hover Lift */}
        <div className="space-y-2 pt-1">
          <span className="text-[11px] font-mono text-ink-subtle uppercase tracking-wider block">
            Suggested Clinical Benchmarks:
          </span>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {suggestionCards.map((card, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setQuery(card.query);
                  handleSearch(card.query);
                }}
                className="p-3.5 rounded-xl bg-canvas hover:bg-card border border-card-border hover:border-brand/40 transition-all duration-200 text-left space-y-1.5 group cursor-pointer shadow-2xs hover:shadow-xs transform hover:-translate-y-0.5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    {card.icon}
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-ink-subtle">
                      {card.category}
                    </span>
                  </div>
                  <ArrowRight className="w-3 h-3 text-ink-subtle opacity-0 group-hover:opacity-100 group-hover:text-brand transition-opacity" />
                </div>
                <p className="text-xs font-heading font-semibold text-ink group-hover:text-brand transition-colors line-clamp-1">
                  {card.title}
                </p>
                <p className="text-[11px] font-mono text-ink-muted line-clamp-1">
                  {card.query}
                </p>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading State: EXACT ECG TELEMETRY LOADER */}
      {isLoading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs">
          <EcgLoader
            isCold={isColdModel}
            label="Executing Hybrid Vector-Graph Synthesis & Verification..."
            sublabel="Retrieving reciprocal-rank fused evidence, traversing Kùzu knowledge graph, and verifying claim-by-claim faithfulness..."
          />
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="Query Execution Notice"
          message={errorMsg}
          onRetry={() => handleSearch()}
        />
      )}

      {/* Result Presentation: Two-Pane Clinical Answer Console */}
      {result && !isLoading && (
        <ClinicalAnswerConsole
          result={result}
          searchDestination={searchPrivate && user_id ? user_id : 'global'}
        />
      )}
    </div>
  );
};
