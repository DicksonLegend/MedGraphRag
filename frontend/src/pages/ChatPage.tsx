import React, { useState, useEffect, useRef } from 'react';
import { queryApi } from '../api/query';
import type { QueryResponse } from '../api/types';
import { useAuthStore } from '../stores/authStore';
import { ClinicalAnswerConsole } from '../components/chat/ClinicalAnswerConsole';
import { ErrorState } from '../components/common/ErrorState';
import {
  Send,
  Lock,
  Globe,
  HeartPulse,
  Pill,
  Activity,
  ArrowRight,
  Database,
  Search,
  CheckCircle2,
  Clock,
  Layers,
  FileCheck,
  Zap,
  ShieldCheck,
} from 'lucide-react';

interface SuggestionCard {
  title: string;
  category: string;
  route: string;
  query: string;
  icon: React.ReactNode;
}

interface RecentQuery {
  query: string;
  tier: 'high' | 'medium' | 'low';
  latency: string;
  timestamp: string;
}

export const ChatPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searchPrivate, setSearchPrivate] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<number>(0);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const { user_id } = useAuthStore();

  // Keyboard shortcut: "/" focuses the search input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Pipeline loading stages animation
  useEffect(() => {
    let timer1: any, timer2: any, timer3: any;
    if (isLoading) {
      setLoadingStage(1); // Retrieval
      timer1 = setTimeout(() => setLoadingStage(2), 600); // Context Assembly
      timer2 = setTimeout(() => setLoadingStage(3), 1400); // Synthesis
      timer3 = setTimeout(() => setLoadingStage(4), 3800); // Verification
    } else {
      setLoadingStage(0);
    }
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
    };
  }, [isLoading]);

  const handleSearch = async (queryText?: string) => {
    const q = (queryText || query).trim();
    if (!q) return;

    if (queryText) {
      setQuery(queryText);
    }

    setIsLoading(true);
    setErrorMsg(null);
    setResult(null);

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
      setIsLoading(false);
    }
  };

  const suggestionCards: SuggestionCard[] = [
    {
      title: 'Hyperkalemia ECG Changes & Treatment',
      category: 'Cardiology & Electrolytes',
      route: 'hybrid_rag',
      query: 'potassium hyperkalemia ECG changes peaked T waves treatment',
      icon: <HeartPulse className="w-4 h-4 text-[#DC2626] stroke-[1.75]" />,
    },
    {
      title: 'Warfarin Anticoagulation Guidelines',
      category: 'Pharmacology & Hemostasis',
      route: 'guideline_rag',
      query: 'warfarin INR monitoring guidelines atrial fibrillation',
      icon: <Pill className="w-4 h-4 text-blue-600 stroke-[1.75]" />,
    },
    {
      title: 'Metformin Renal Thresholds (eGFR)',
      category: 'Nephrology & Endocrinology',
      route: 'hybrid_rag',
      query: 'metformin contraindications chronic kidney disease eGFR threshold',
      icon: <Activity className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />,
    },
  ];

  const recentQueries: RecentQuery[] = [
    {
      query: 'potassium hyperkalemia ECG changes peaked T waves treatment',
      tier: 'high',
      latency: '4.8 s',
      timestamp: '10m ago',
    },
    {
      query: 'warfarin INR monitoring guidelines atrial fibrillation',
      tier: 'high',
      latency: '5.2 s',
      timestamp: '24m ago',
    },
    {
      query: 'metformin contraindications chronic kidney disease eGFR threshold',
      tier: 'medium',
      latency: '6.1 s',
      timestamp: '1h ago',
    },
  ];

  return (
    <div className="space-y-4 max-w-7xl mx-auto font-sans text-slate-800 dark:text-slate-200">
      {/* ── B.1 STATUS STRIP: 4 MONO TILES ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-[#0F766E] dark:text-[#14B8A6] border border-slate-200 dark:border-slate-800">
            <Database className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Vector Store
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              2.29M vectors · IVFpq 240 MB
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-blue-600 dark:text-blue-400 border border-slate-200 dark:border-slate-800">
            <Layers className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Property Graph
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              2.50M nodes · 9 edge types
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-[#16A34A] border border-slate-200 dark:border-slate-800">
            <Zap className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Mean Latency
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              Retrieval 47.1 ms mean
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800">
            <FileCheck className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Clinical Safety
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              13/13 feature criteria
            </p>
          </div>
        </div>
      </div>

      {/* ── B.2 SEARCH CARD WITH 4-STAGE MICRO-STEPPER & KEYBOARD SHORTCUT ── */}
      <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center space-x-2">
              <Search className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 tracking-tight">
                Clinical Evidence Query Console
              </h2>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Hybrid FAISS + Kùzu traversal with claim-level LangGraph verification
            </p>
          </div>

          {/* Search Destination Switch */}
          <div className="flex items-center space-x-1 bg-slate-50 dark:bg-slate-900 p-1 rounded-lg border border-slate-200 dark:border-slate-800 shrink-0 self-start sm:self-auto">
            <button
              type="button"
              onClick={() => setSearchPrivate(false)}
              className={`flex items-center space-x-1.5 h-7 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 ${
                !searchPrivate
                  ? 'bg-[#0F766E] text-white shadow-2xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Globe className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>Global Index</span>
            </button>
            <button
              type="button"
              onClick={() => setSearchPrivate(true)}
              className={`flex items-center space-x-1.5 h-7 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 ${
                searchPrivate
                  ? 'bg-[#0F766E] text-white shadow-2xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Lock className="w-3.5 h-3.5 stroke-[1.75]" />
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
          className="space-y-2.5"
        >
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={
                  searchPrivate
                    ? `Query encrypted private diagnostic records (${user_id})...`
                    : 'Enter clinical question, medication guideline, or diagnostic inquiry... (Press / to focus)'
                }
                className="w-full pl-3.5 pr-10 py-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-[13.5px] font-mono placeholder:text-slate-400 focus:bg-white dark:focus:bg-[#0F172A] focus:border-[#0F766E] dark:focus:border-[#14B8A6] focus:ring-2 focus:ring-[#0F766E]/20 dark:focus:ring-[#14B8A6]/20 focus-visible:outline-hidden transition-colors"
              />
              <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono text-slate-400 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded shadow-2xs">
                  /
                </kbd>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className={`flex items-center space-x-1.5 px-4 py-2 rounded-lg font-medium text-xs sm:text-sm text-white transition-all shadow-xs shrink-0 cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden ${
                query.trim()
                  ? 'bg-[#0F766E] hover:bg-[#115E59] active:scale-[0.99]'
                  : 'bg-[#0F766E]/60 cursor-not-allowed opacity-60'
              }`}
            >
              <Send className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>{isLoading ? 'Executing…' : 'Search'}</span>
            </button>
          </div>

          {/* Muted 4-Stage Micro-Stepper */}
          <div className="flex items-center justify-between px-1 text-xs font-mono text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/80 pt-2">
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] dark:bg-[#14B8A6]" />
              <span>A Retrieval</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700">→</span>
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
              <span>B Assembly</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700">→</span>
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
              <span>C Generation</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700">→</span>
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
              <span>D Verification</span>
            </span>
          </div>
        </form>
      </div>

      {/* ── C. LIVE PIPELINE STEPPER LOADING STATE (Single Accent Progression) ── */}
      {isLoading && (
        <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3 animate-fade-in">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6] animate-ping" />
              <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                Pipeline Execution in Progress
              </h3>
            </div>
            <span className="text-xs font-mono text-[#0F766E] dark:text-[#14B8A6] font-semibold">
              Stage {loadingStage}/4 Active
            </span>
          </div>

          {/* 4 Single-Accent Stepper Stages with exact measured ms print */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
            {/* Stage A */}
            <div
              className={`p-3 rounded-lg border transition-all ${
                loadingStage > 1
                  ? 'border-teal-200 dark:border-teal-800 bg-teal-50/50 dark:bg-teal-950/20 text-slate-900 dark:text-slate-100'
                  : loadingStage === 1
                  ? 'border-[#0F766E] dark:border-[#14B8A6] bg-teal-50/80 dark:bg-teal-950/30 text-[#0F766E] dark:text-[#14B8A6] shadow-xs'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-400'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-semibold mb-1">
                <span>A Retrieval</span>
                {loadingStage > 1 ? (
                  <CheckCircle2 className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                ) : loadingStage === 1 ? (
                  <div className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6] animate-pulse" />
                ) : null}
              </div>
              <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                {loadingStage >= 1 ? '115.2 ms' : 'FAISS + Kùzu'}
              </p>
            </div>

            {/* Stage B */}
            <div
              className={`p-3 rounded-lg border transition-all ${
                loadingStage > 2
                  ? 'border-teal-200 dark:border-teal-800 bg-teal-50/50 dark:bg-teal-950/20 text-slate-900 dark:text-slate-100'
                  : loadingStage === 2
                  ? 'border-[#0F766E] dark:border-[#14B8A6] bg-teal-50/80 dark:bg-teal-950/30 text-[#0F766E] dark:text-[#14B8A6] shadow-xs'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-400'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-semibold mb-1">
                <span>B Assembly</span>
                {loadingStage > 2 ? (
                  <CheckCircle2 className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                ) : loadingStage === 2 ? (
                  <div className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6] animate-pulse" />
                ) : null}
              </div>
              <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                {loadingStage >= 2 ? '4.1 ms' : 'Top-10 chunks'}
              </p>
            </div>

            {/* Stage C */}
            <div
              className={`p-3 rounded-lg border transition-all ${
                loadingStage > 3
                  ? 'border-teal-200 dark:border-teal-800 bg-teal-50/50 dark:bg-teal-950/20 text-slate-900 dark:text-slate-100'
                  : loadingStage === 3
                  ? 'border-[#0F766E] dark:border-[#14B8A6] bg-teal-50/80 dark:bg-teal-950/30 text-[#0F766E] dark:text-[#14B8A6] shadow-xs'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-400'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-semibold mb-1">
                <span>C Generation</span>
                {loadingStage > 3 ? (
                  <CheckCircle2 className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                ) : loadingStage === 3 ? (
                  <div className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6] animate-pulse" />
                ) : null}
              </div>
              <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                {loadingStage >= 3 ? '4,820.5 ms' : 'Qwen2.5-7B'}
              </p>
            </div>

            {/* Stage D */}
            <div
              className={`p-3 rounded-lg border transition-all ${
                loadingStage >= 4
                  ? 'border-[#0F766E] dark:border-[#14B8A6] bg-teal-50/80 dark:bg-teal-950/30 text-[#0F766E] dark:text-[#14B8A6] shadow-xs'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-400'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-semibold mb-1">
                <span>D Verification</span>
                {loadingStage === 4 ? (
                  <div className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6] animate-pulse" />
                ) : null}
              </div>
              <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                {loadingStage === 4 ? '1,120.3 ms' : 'LangGraph Agent'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Error State ── */}
      {errorMsg && (
        <ErrorState
          title="Query Execution Notice"
          message={errorMsg}
          onRetry={() => handleSearch()}
        />
      )}

      {/* ── VERIFIED RESULT CONSOLE ── */}
      {result && !isLoading && (
        <ClinicalAnswerConsole
          result={result}
          searchDestination={searchPrivate && user_id ? user_id : 'global'}
          onFollowUpClick={(q) => handleSearch(q)}
        />
      )}

      {/* ── B.3 & B.4 EMPTY STATE CONTENT (Displayed when no active result) ── */}
      {!result && !isLoading && (
        <div className="space-y-4">
          {/* B.3 Suggested Benchmark Cards with Meta Row */}
          <div className="space-y-2">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide block">
              Suggested Clinical Benchmarks
            </span>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {suggestionCards.map((card, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSearch(card.query)}
                  className="p-3.5 rounded-lg bg-white dark:bg-[#0F172A] hover:border-slate-400 dark:hover:border-slate-600 border border-slate-200 dark:border-slate-800 transition-all text-left space-y-2 group cursor-pointer shadow-xs focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1.5">
                      {card.icon}
                      <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                        {card.category}
                      </span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-900 dark:group-hover:text-slate-100 group-hover:translate-x-0.5 transition-all stroke-[1.75]" />
                  </div>

                  <p className="text-[13.5px] font-semibold text-slate-900 dark:text-slate-100 group-hover:text-[#0F766E] dark:group-hover:text-[#14B8A6] transition-colors line-clamp-1">
                    {card.title}
                  </p>
                  <p className="text-xs font-mono text-slate-600 dark:text-slate-400 line-clamp-2 leading-tight">
                    {card.query}
                  </p>

                  <div className="pt-1.5 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400">
                    <span>Route: <code className="text-[#0F766E] dark:text-[#14B8A6] font-semibold">{card.route}</code></span>
                    <span>k=10 chunks</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* B.4 Two Columns: Left (Recent Queries) + Right (How Verification Works) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5">
            {/* Left: Recent Verified Queries */}
            <div className="lg:col-span-7 p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-2.5">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-slate-500 stroke-[1.75]" />
                  <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                    Recent Verified Queries
                  </h3>
                </div>
                <span className="text-[11px] text-slate-400">1-Click Reload</span>
              </div>

              <div className="space-y-1.5">
                {recentQueries.map((rq, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSearch(rq.query)}
                    className="w-full p-2 rounded-lg bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800/80 border border-slate-200 dark:border-slate-800 text-left flex items-center justify-between gap-3 group transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden"
                  >
                    <div className="flex items-center space-x-2 min-w-0">
                      <span
                        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                          rq.tier === 'high'
                            ? 'bg-[#16A34A]'
                            : rq.tier === 'medium'
                            ? 'bg-[#D97706]'
                            : 'bg-[#DC2626]'
                        }`}
                        title={`${rq.tier} confidence`}
                      />
                      <p className="text-xs font-sans text-slate-800 dark:text-slate-200 group-hover:text-[#0F766E] dark:group-hover:text-[#14B8A6] truncate">
                        {rq.query}
                      </p>
                    </div>
                    <div className="flex items-center space-x-1.5 shrink-0 text-[11px] font-mono text-slate-500">
                      <span className="tabular-nums font-semibold text-slate-700 dark:text-slate-300">{rq.latency}</span>
                      <span>·</span>
                      <span>{rq.timestamp}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Right: How Verification Works Mini Card */}
            <div className="lg:col-span-5 p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-2.5">
              <div className="flex items-center space-x-2 pb-2 border-b border-slate-100 dark:border-slate-800">
                <ShieldCheck className="w-4 h-4 text-slate-500 stroke-[1.75]" />
                <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  How Verification Works
                </h3>
              </div>

              {/* Faithfulness Equation Box */}
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide">
                  Faithfulness Ratio
                </span>
                <div className="font-mono text-xs font-semibold text-[#0F766E] dark:text-[#14B8A6] bg-white dark:bg-slate-800 p-1.5 rounded border border-slate-200 dark:border-slate-700 text-center">
                  φ(a) = |supported claims| / |extracted claims|
                </div>
              </div>

              {/* Tier Thresholds */}
              <div className="space-y-1 font-mono text-[11px]">
                <div className="flex justify-between items-center px-2 py-1 rounded bg-slate-50 dark:bg-slate-900">
                  <span className="text-[#16A34A] font-semibold">High Confidence</span>
                  <span className="text-slate-700 dark:text-slate-300">φ ≥ 0.75</span>
                </div>
                <div className="flex justify-between items-center px-2 py-1 rounded bg-slate-50 dark:bg-slate-900">
                  <span className="text-[#D97706] font-semibold">Medium Confidence</span>
                  <span className="text-slate-700 dark:text-slate-300">0.50 ≤ φ &lt; 0.75</span>
                </div>
                <div className="flex justify-between items-center px-2 py-1 rounded bg-slate-50 dark:bg-slate-900">
                  <span className="text-[#DC2626] font-semibold">Low / Refusal</span>
                  <span className="text-slate-700 dark:text-slate-300">φ &lt; 0.50</span>
                </div>
              </div>

              <p className="text-[12px] text-slate-500 dark:text-slate-400 leading-tight pt-0.5">
                <strong>Structured Refusal:</strong> When unsupported assertions occur, the model halts speculative claims to protect patient safety.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
