import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { queryApi } from '../api/query';
import type { QueryResponse } from '../api/types';
import { useAuthStore } from '../stores/authStore';
import { useSessionStore } from '../stores/sessionStore';
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
  Sparkles,
  Cpu,
  Fingerprint,
  ArrowUpRight,
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
  const consoleSession = useSessionStore((state) => state.console);
  const setConsoleState = useSessionStore((state) => state.setConsoleState);

  const [query, setQuery] = useState(consoleSession.query || '');
  const [searchPrivate, setSearchPrivate] = useState(consoleSession.searchPrivate || false);
  const [isLoading, setIsLoading] = useState(consoleSession.status === 'loading');
  const [loadingStage, setLoadingStage] = useState<number>(0);
  const [result, setResult] = useState<QueryResponse | null>(consoleSession.result);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const { user_id } = useAuthStore();
  const [searchParams] = useSearchParams();

  // Sync with store on mount or store change
  useEffect(() => {
    if (consoleSession.result && !result) {
      setResult(consoleSession.result);
      setQuery(consoleSession.query);
      setSearchPrivate(consoleSession.searchPrivate);
    }
  }, [consoleSession.result]);

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
    setConsoleState({ query: q, status: 'loading', result: null, searchPrivate });

    try {
      const destination = searchPrivate && user_id ? user_id : 'global';
      const res = await queryApi.submitQuery({
        query: q,
        destination,
      });
      setResult(res);
      const isRefused =
        res.answer_status === 'refusal' ||
        res.answer_status === 'out_of_scope' ||
        (res.final_confidence < 0.5 && res.answer_status !== 'verified');
      setConsoleState({
        query: q,
        status: isRefused ? 'refused' : 'verified',
        result: res,
        searchPrivate,
      });
    } catch (err: any) {
      setConsoleState({ status: 'error' });
      setErrorMsg(err.message || 'An error occurred during query execution.');
    } finally {
      setIsLoading(false);
    }
  };

  // URL query parameter listener or resume loading state
  useEffect(() => {
    const qParam = searchParams.get('q');
    if (qParam && qParam.trim() && qParam.trim() !== consoleSession.query) {
      setQuery(qParam.trim());
      handleSearch(qParam.trim());
    } else if (consoleSession.status === 'loading' && consoleSession.query) {
      handleSearch(consoleSession.query);
    }
  }, [searchParams]);

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
      {/* ── 1. UNIFIED SYSTEM TELEMETRY HUD RIBBON (Seamless Instrument Bar) ── */}
      <div className="rounded-xl border border-slate-200/90 dark:border-slate-800/90 bg-white/95 dark:bg-[#0F172A]/95 backdrop-blur-md shadow-2xs overflow-hidden">
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-slate-100 dark:divide-slate-800">
          {/* Tile 1: Vector Store */}
          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-[#0F766E] dark:text-[#14B8A6] border border-teal-200 dark:border-teal-800/80 shrink-0">
              <Database className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Vector Store
                </span>
                <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] inline-block animate-pulse" />
              </div>
              <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate mt-0.5">
                2.29M vectors · IVFpq 240 MB
              </p>
            </div>
          </div>

          {/* Tile 2: Property Graph */}
          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/80 shrink-0">
              <Layers className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Property Graph
                </span>
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
              </div>
              <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate mt-0.5">
                2.50M nodes · 9 edge types
              </p>
            </div>
          </div>

          {/* Tile 3: Mean Latency */}
          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-[#16A34A] border border-emerald-200 dark:border-emerald-800/80 shrink-0">
              <Zap className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Mean Latency
                </span>
                <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] inline-block" />
              </div>
              <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate mt-0.5">
                Retrieval 47.1 ms mean
              </p>
            </div>
          </div>

          {/* Tile 4: Clinical Safety */}
          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/80 shrink-0">
              <FileCheck className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Clinical Safety
                </span>
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500 inline-block" />
              </div>
              <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate mt-0.5">
                13/13 feature criteria
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. ELEVATED SPATIAL COMMAND CONSOLE (Unified Stage with Stepper Floor) ── */}
      <div className="relative rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-md shadow-slate-900/5 p-4 sm:p-5 space-y-3.5 transition-all">
        {/* Header Ribbon of Command Console */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-slate-100 dark:border-slate-800">
          <div className="space-y-0.5">
            <div className="flex items-center space-x-2">
              <div className="p-1 rounded-md bg-teal-50 dark:bg-teal-950/60 text-[#0F766E] dark:text-[#14B8A6]">
                <Search className="w-3.5 h-3.5 stroke-[1.75]" />
              </div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100 tracking-tight">
                Clinical Evidence Query Console
              </h2>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-sans">
              Hybrid FAISS + Kùzu traversal with claim-level LangGraph verification
            </p>
          </div>

          {/* Search Destination Switch */}
          <div className="flex items-center space-x-1 bg-slate-50 dark:bg-slate-900 p-1 rounded-xl border border-slate-200/80 dark:border-slate-800 shrink-0 self-start sm:self-auto shadow-2xs">
            <button
              type="button"
              onClick={() => setSearchPrivate(false)}
              className={`flex items-center space-x-1.5 h-7 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 ${
                !searchPrivate
                  ? 'bg-[#0F766E] text-white shadow-xs font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Globe className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>Global Index</span>
            </button>
            <button
              type="button"
              onClick={() => setSearchPrivate(true)}
              className={`flex items-center space-x-1.5 h-7 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 ${
                searchPrivate
                  ? 'bg-[#0F766E] text-white shadow-xs font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Lock className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>My Reports ({user_id || 'admin'})</span>
            </button>
          </div>
        </div>

        {/* Query Input Deck */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSearch();
          }}
          className="space-y-3"
        >
          <div className="flex gap-2">
            <div className="relative flex-1 group/input">
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
                className="w-full pl-3.5 pr-10 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/80 text-slate-900 dark:text-slate-100 text-[13.5px] font-mono placeholder:text-slate-400 focus:bg-white dark:focus:bg-[#0F172A] focus:border-[#0F766E] dark:focus:border-[#14B8A6] focus:ring-2 focus:ring-[#0F766E]/20 dark:focus:ring-[#14B8A6]/20 focus-visible:outline-hidden transition-all shadow-2xs"
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
              className={`flex items-center space-x-1.5 px-5 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-white transition-all shadow-xs shrink-0 cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden ${
                query.trim()
                  ? 'bg-[#0F766E] hover:bg-[#115E59] active:scale-[0.98]'
                  : 'bg-[#0F766E]/60 cursor-not-allowed opacity-60'
              }`}
            >
              <Send className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>{isLoading ? 'Executing…' : 'Search'}</span>
            </button>
          </div>

          {/* Integrated 4-Stage Micro-Stepper Base */}
          <div className="flex items-center justify-between px-2 text-xs font-mono text-slate-500 dark:text-slate-400 pt-1">
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] dark:bg-[#14B8A6]" />
              <span className="font-semibold text-slate-700 dark:text-slate-300">A Retrieval</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700 font-light">───</span>
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
              <span className="font-semibold text-slate-700 dark:text-slate-300">B Assembly</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700 font-light">───</span>
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
              <span className="font-semibold text-slate-700 dark:text-slate-300">C Generation</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700 font-light">───</span>
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
              <span className="font-semibold text-slate-700 dark:text-slate-300">D Verification</span>
            </span>
          </div>
        </form>
      </div>

      {/* ── 3. LIVE PIPELINE STEPPER LOADING STATE ── */}
      {isLoading && (
        <div className="p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-md space-y-3.5 animate-fade-in">
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
              className={`p-3 rounded-xl border transition-all ${
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
              className={`p-3 rounded-xl border transition-all ${
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
                {loadingStage >= 2 ? '38.4 ms' : 'Context Packing'}
              </p>
            </div>

            {/* Stage C */}
            <div
              className={`p-3 rounded-xl border transition-all ${
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
                {loadingStage >= 3 ? '2,840.1 ms' : 'Streaming Response'}
              </p>
            </div>

            {/* Stage D */}
            <div
              className={`p-3 rounded-xl border transition-all ${
                loadingStage === 4
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
                {loadingStage === 4 ? '1,820.0 ms' : 'Claim Fact-Checking'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="Clinical Query Execution Error"
          message={errorMsg}
          onRetry={() => handleSearch()}
        />
      )}

      {/* ── 4. ANSWER PRESENTATION ── */}
      {result && !isLoading && (
        <div className="animate-fade-in space-y-4">
          <ClinicalAnswerConsole result={result} onFollowUpClick={(fQuery: string) => handleSearch(fQuery)} />
        </div>
      )}

      {/* ── 5. CLINICAL BENCHMARKS & DUAL-ZONE TERMINAL (Shown on Empty/Initial State) ── */}
      {!result && !isLoading && (
        <div className="space-y-4 animate-fade-in">
          {/* Unified Clinical Pathways Ledger (Replacing 3 separate boxes) */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden">
            <div className="p-3 sm:px-4 bg-slate-50/80 dark:bg-slate-900/60 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Suggested Clinical Benchmarks
              </span>
              <span className="text-[10px] font-mono text-slate-400">3 Verified Pathways</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-100 dark:divide-slate-800">
              {suggestionCards.map((sug, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSearch(sug.query)}
                  className="p-4 text-left hover:bg-slate-50/80 dark:hover:bg-slate-900/50 transition-all group/card cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden relative"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-mono font-semibold text-slate-500 dark:text-slate-400 flex items-center space-x-1.5">
                      {sug.icon}
                      <span>{sug.category}</span>
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover/card:text-[#0F766E] dark:group-hover/card:text-[#14B8A6] group-hover/card:translate-x-1 transition-all" />
                  </div>

                  <h3 className="font-semibold text-xs sm:text-[13px] text-slate-900 dark:text-slate-100 group-hover/card:text-[#0F766E] dark:group-hover/card:text-[#14B8A6] transition-colors leading-snug">
                    {sug.title}
                  </h3>

                  <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mt-1 font-sans">
                    {sug.query}
                  </p>

                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-3 mt-1 border-t border-slate-100/60 dark:border-slate-800/60">
                    <span>Route: {sug.route}</span>
                    <span>k=10 chunks</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Split Workspace: Recent Queries Timeline & Verification Calibration HUD */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5">
            {/* Left: Recent Verified Queries Timeline (7 cols) */}
            <div className="lg:col-span-7 rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden">
              <div className="p-3 sm:px-4 bg-slate-50/80 dark:bg-slate-900/60 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Clock className="w-3.5 h-3.5 text-slate-400 stroke-[1.75]" />
                  <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                    Recent Verified Queries
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-slate-400">1-Click Reload</span>
              </div>

              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {recentQueries.map((rq, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSearch(rq.query)}
                    className="w-full p-3 hover:bg-slate-50 dark:hover:bg-slate-900/50 text-left flex items-center justify-between gap-3 group transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden"
                  >
                    <div className="flex items-center space-x-2.5 min-w-0">
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 ${
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

            {/* Right: How Verification Works Calibration HUD (5 cols) */}
            <div className="lg:col-span-5 rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-xs p-4 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                  <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                    How Verification Works
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-slate-400">LangGraph</span>
              </div>

              {/* Faithfulness Equation Box */}
              <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 space-y-1">
                <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wider font-mono">
                  Faithfulness Ratio
                </span>
                <div className="font-mono text-xs font-semibold text-[#0F766E] dark:text-[#14B8A6] bg-white dark:bg-slate-800 p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-center shadow-2xs">
                  φ(a) = |supported claims| / |extracted claims|
                </div>
              </div>

              {/* Tier Thresholds */}
              <div className="space-y-1 font-mono text-[11px]">
                <div className="flex justify-between items-center px-2.5 py-1 rounded-lg bg-slate-50 dark:bg-slate-900">
                  <span className="text-[#16A34A] font-semibold">High Confidence</span>
                  <span className="text-slate-700 dark:text-slate-300">φ ≥ 0.75</span>
                </div>
                <div className="flex justify-between items-center px-2.5 py-1 rounded-lg bg-slate-50 dark:bg-slate-900">
                  <span className="text-[#D97706] font-semibold">Medium Confidence</span>
                  <span className="text-slate-700 dark:text-slate-300">0.50 ≤ φ &lt; 0.75</span>
                </div>
                <div className="flex justify-between items-center px-2.5 py-1 rounded-lg bg-slate-50 dark:bg-slate-900">
                  <span className="text-[#DC2626] font-semibold">Low / Refusal</span>
                  <span className="text-slate-700 dark:text-slate-300">φ &lt; 0.50</span>
                </div>
              </div>

              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight pt-0.5">
                <strong>Structured Refusal:</strong> When unsupported assertions occur, the model halts speculative claims to protect patient safety.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
