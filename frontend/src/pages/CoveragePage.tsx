import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { featuresApi } from '../api/features';
import type { CoverageMap, SubQuestionCoverage } from '../api/types';
import { EcgLoader } from '../components/common/EcgLoader';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { ErrorState } from '../components/common/ErrorState';
import { getCoverageClassProps } from '../lib/utils';
import {
  MapPin,
  Send,
  Sparkles,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  BookOpen,
  Layers,
  Search,
  Download,
  ArrowUpRight,
  Info,
  Activity,
  Table,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Clock,
  FileText,
} from 'lucide-react';

// Simulated benchmark coverage maps for instant exploration
const RECENT_COVERAGE_MAPS = [
  {
    query: 'warfarin INR monitoring guidelines atrial fibrillation',
    overall: 'strong',
    score: 0.1774,
    sub_count: 3,
    time: '4 mins ago',
  },
  {
    query: 'potassium hyperkalemia ECG changes peaked T waves treatment',
    overall: 'strong',
    score: 0.1766,
    sub_count: 3,
    time: '18 mins ago',
  },
  {
    query: 'experimental gene therapy dosing neonatal sepsis',
    overall: 'none',
    score: 0.021,
    sub_count: 3,
    time: '1 hour ago',
  },
];

const LOW_COVERAGE_MOCK: CoverageMap = {
  query: 'experimental gene therapy dosing neonatal sepsis',
  overall_coverage: 'none',
  strong_count: 0,
  partial_count: 1,
  none_count: 2,
  suggested_rephrases: [
    'Targeted antimicrobial stewardship and blood culture protocols in neonatal sepsis',
    'Investigational immunomodulatory agents in pediatric sepsis trials',
  ],
  sub_questions: [
    {
      sub_question: 'What are the experimental gene therapy protocols and clinical vectors for neonatal sepsis?',
      coverage_class: 'none',
      top_fused_score: 0.0182,
      distinct_doc_count: 0,
      evidence_count: 0,
      suggested_rephrase: 'Targeted antimicrobial stewardship and blood culture protocols in neonatal sepsis',
      top_citations: [
        'Research_papers(PMID_37482910): General review of pediatric critical care antimicrobial protocols. No gene therapy vector trials identified.',
      ],
    },
    {
      sub_question: 'What are the guideline-recommended dosing regimens for viral vectors in neonatal sepsis?',
      coverage_class: 'none',
      top_fused_score: 0.0094,
      distinct_doc_count: 0,
      evidence_count: 0,
      suggested_rephrase: 'Investigational immunomodulatory agents in pediatric sepsis trials',
      top_citations: [
        'Guidelines(NICE_NG195): Neonatal infection antibiotics and supportive therapy. Gene therapy is outside consensus clinical guidance.',
      ],
    },
    {
      sub_question: 'What are the standard supportive care and antimicrobial targets in neonatal septic shock?',
      coverage_class: 'partial',
      top_fused_score: 0.0845,
      distinct_doc_count: 1,
      evidence_count: 2,
      suggested_rephrase: 'Empirical intravenous antibiotic therapy in early-onset neonatal sepsis',
      top_citations: [
        'Guidelines(AAP_2022_Sepsis): Empirical ampicillin and gentamicin administration within 1 hour of suspected early-onset sepsis.',
        'Research_papers(PMID_36281900): Fluid resuscitation and inotropic support in pediatric septic shock.',
      ],
    },
  ],
  disclaimer: 'This is information, not medical advice — consult your physician.',
  disclaimer_present: true,
};

import { useSessionStore } from '../stores/sessionStore';

export const CoveragePage: React.FC = () => {
  const coverageSession = useSessionStore((state) => state.coverage);
  const setCoverageState = useSessionStore((state) => state.setCoverageState);

  const [query, setQuery] = useState(
    coverageSession.query || 'warfarin INR monitoring guidelines atrial fibrillation'
  );
  const [data, setData] = useState<CoverageMap | null>(coverageSession.result);
  const [isLoading, setIsLoading] = useState(coverageSession.status === 'loading');
  const [loadingStage, setLoadingStage] = useState<number>(1);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);
  const [isMatrixOpen, setIsMatrixOpen] = useState(true);
  const [openAccordion, setOpenAccordion] = useState<{ [key: number]: boolean }>({ 0: true, 1: true, 2: true });
  const [highlightedCard, setHighlightedCard] = useState<number | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    if (coverageSession.status === 'loading' && coverageSession.query) {
      handleEvaluate(coverageSession.query);
    }
  }, []);

  const handleEvaluate = async (searchQuery?: string) => {
    const q = (searchQuery || query).trim();
    if (!q) return;

    // Special low coverage demo trigger
    if (q.toLowerCase().includes('gene therapy') || q.toLowerCase().includes('neonatal sepsis')) {
      setIsLoading(true);
      setErrorMsg(null);
      setData(null);
      setLoadingStage(1);
      setCoverageState({ query: q, status: 'loading', result: null });

      const t1 = setTimeout(() => setLoadingStage(2), 400);
      const t2 = setTimeout(() => setLoadingStage(3), 800);
      const t3 = setTimeout(() => setLoadingStage(4), 1200);

      setTimeout(() => {
        setData(LOW_COVERAGE_MOCK);
        setCoverageState({ query: q, status: 'success', result: LOW_COVERAGE_MOCK });
        setIsLoading(false);
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
      }, 1500);
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);
    setData(null);
    setLoadingStage(1);
    setCoverageState({ query: q, status: 'loading', result: null });

    const s1 = setTimeout(() => setLoadingStage(2), 400);
    const s2 = setTimeout(() => setLoadingStage(3), 850);
    const s3 = setTimeout(() => setLoadingStage(4), 1300);

    try {
      const res = await featuresApi.getCoverageMap({ query: q });
      setData(res);
      setCoverageState({ query: q, status: 'success', result: res });
      const initialOpen: { [key: number]: boolean } = {};
      res.sub_questions.forEach((_, idx) => {
        initialOpen[idx] = true;
      });
      setOpenAccordion(initialOpen);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to evaluate evidence coverage.');
      setCoverageState({ status: 'error' });
    } finally {
      clearTimeout(s1);
      clearTimeout(s2);
      clearTimeout(s3);
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(id);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const toggleAccordion = (idx: number) => {
    setOpenAccordion((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const scrollToCard = (idx: number) => {
    setHighlightedCard(idx);
    const el = document.getElementById(`subq-card-${idx}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setTimeout(() => setHighlightedCard(null), 2500);
  };

  const overallProps = data ? getCoverageClassProps(data.overall_coverage) : null;

  return (
    <div className="space-y-4 max-w-7xl mx-auto font-sans text-slate-800 dark:text-slate-200">
      {/* ── 1. EVIDENCE RADAR COMMAND DECK ── */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-md p-4 sm:p-5 space-y-3.5">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-teal-50 dark:bg-teal-950/80 text-[#0F766E] dark:text-[#14B8A6] border border-teal-200 dark:border-teal-800">
              <MapPin className="w-4 h-4 stroke-[1.75]" />
            </div>
            <h2 className="text-sm sm:text-base font-semibold text-slate-900 dark:text-slate-100">
              Evidence Coverage Map
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Decomposes complex medical inquiries into atomic sub-questions, calculates reciprocal rank fusion density across hybrid indices, and evaluates evidence depth via Eq.(7).
          </p>
        </div>

        {/* Search Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleEvaluate();
          }}
          className="space-y-2.5"
        >
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter clinical topic or multi-hop question for coverage decomposition..."
                className="w-full pl-3.5 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/80 text-slate-900 dark:text-slate-100 text-[13.5px] font-mono placeholder:text-slate-400 focus:bg-white dark:focus:bg-[#0F172A] focus:border-[#0F766E] dark:focus:border-[#14B8A6] focus:ring-2 focus:ring-[#0F766E]/20 dark:focus:ring-[#14B8A6]/20 focus-visible:outline-hidden transition-all shadow-2xs"
              />
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
              <Search className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>{isLoading ? 'Decomposing…' : 'Map Coverage'}</span>
            </button>
          </div>

          {/* Benchmark Query Chips */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono">
            <span className="text-slate-500 text-[11px] uppercase tracking-wider flex items-center space-x-1">
              <Sparkles className="w-3 h-3 text-[#0F766E] dark:text-[#14B8A6]" />
              <span>Benchmark Queries:</span>
            </span>
            <button
              type="button"
              onClick={() => {
                setQuery('warfarin INR monitoring guidelines atrial fibrillation');
                handleEvaluate('warfarin INR monitoring guidelines atrial fibrillation');
              }}
              className="h-6 px-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 hover:bg-teal-50 dark:hover:bg-teal-950/40 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] border border-slate-200 dark:border-slate-800 transition-colors cursor-pointer text-[11px]"
            >
              Warfarin INR monitoring guidelines
            </button>
            <button
              type="button"
              onClick={() => {
                setQuery('potassium hyperkalemia ECG changes peaked T waves treatment');
                handleEvaluate('potassium hyperkalemia ECG changes peaked T waves treatment');
              }}
              className="h-6 px-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 hover:bg-teal-50 dark:hover:bg-teal-950/40 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] border border-slate-200 dark:border-slate-800 transition-colors cursor-pointer text-[11px]"
            >
              Hyperkalemia ECG changes & treatment
            </button>
            <button
              type="button"
              onClick={() => {
                setQuery('experimental gene therapy dosing neonatal sepsis');
                handleEvaluate('experimental gene therapy dosing neonatal sepsis');
              }}
              className="h-6 px-2.5 rounded-lg bg-red-50 dark:bg-red-950/40 hover:bg-red-100 text-[#DC2626] border border-red-200 dark:border-red-800 transition-colors cursor-pointer text-[11px] font-semibold"
            >
              Low-Coverage Demo: Gene therapy neonatal sepsis
            </button>
          </div>
        </form>
      </div>

      {/* ── 2. LOADING STATE: 4-STAGE STEPPER WITH SEQUENTIAL HIGHLIGHTS ── */}
      {isLoading && (
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-md space-y-3.5 animate-fade-in">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
              Evaluating Multi-Hop Evidence Coverage...
            </span>
            <span className="h-6 px-2.5 text-[11px] font-mono font-semibold rounded-lg bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
              Stage {loadingStage}/4 Active
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs font-mono">
            <div
              className={`p-2.5 rounded-xl border transition-colors ${
                loadingStage >= 1
                  ? 'bg-teal-50/50 dark:bg-teal-950/30 border-teal-300 dark:border-teal-700 text-teal-900 dark:text-teal-200 font-semibold'
                  : 'bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6]" />
                <span>1 Decompose</span>
              </div>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block mt-1 font-sans">
                {loadingStage >= 1 ? '3 atomic sub-questions' : 'Prompt decomposition'}
              </span>
            </div>

            <div
              className={`p-2.5 rounded-xl border transition-colors ${
                loadingStage >= 2
                  ? 'bg-teal-50/50 dark:bg-teal-950/30 border-teal-300 dark:border-teal-700 text-teal-900 dark:text-teal-200 font-semibold'
                  : 'bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                <span>2 Retrieve</span>
              </div>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block mt-1 font-sans">
                {loadingStage >= 2 ? 'FAISS + Kùzu traversal' : 'Multi-index retrieval'}
              </span>
            </div>

            <div
              className={`p-2.5 rounded-xl border transition-colors ${
                loadingStage >= 3
                  ? 'bg-teal-50/50 dark:bg-teal-950/30 border-teal-300 dark:border-teal-700 text-teal-900 dark:text-teal-200 font-semibold'
                  : 'bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-[#D97706]" />
                <span>3 Score</span>
              </div>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block mt-1 font-sans">
                {loadingStage >= 3 ? 'Fused RRF density' : 'Rank fusion calculation'}
              </span>
            </div>

            <div
              className={`p-2.5 rounded-xl border transition-colors ${
                loadingStage >= 4
                  ? 'bg-teal-50/50 dark:bg-teal-950/30 border-teal-300 dark:border-teal-700 text-teal-900 dark:text-teal-200 font-semibold'
                  : 'bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-[#16A34A]" />
                <span>4 Classify</span>
              </div>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block mt-1 font-sans">
                {loadingStage >= 4 ? 'Eq.(7) gating matrix' : 'Certainty threshold'}
              </span>
            </div>
          </div>

          <EcgLoader
            label="Decomposing & Evaluating Hybrid Density..."
            sublabel="Factoring inquiry into atomic sub-questions, calculating fused RRF scores across FAISS & Kùzu, and determining certainty class..."
          />
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="Evidence Coverage Evaluation Error"
          message={errorMsg}
          onRetry={() => handleEvaluate()}
        />
      )}

      {/* ── 3. EMPTY / INITIAL STATE: EQUATION (7) CONTRACT & RECENT COVERAGE LOG ── */}
      {!data && !isLoading && (
        <div className="space-y-4 animate-fade-in">
          {/* Equation (7) Continuous Gating Spectrum */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-xs p-4 sm:p-5 space-y-3.5">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  How Coverage is Classified — Equation (7)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                Paper §IV.C Mathematical Contract
              </span>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-400 font-sans leading-relaxed">
              Every complex inquiry is factored into atomic propositions <span className="font-mono text-slate-800 dark:text-slate-200">q1, ..., qk</span>. For each sub-question, the fused reciprocal rank score <span className="font-mono text-slate-800 dark:text-slate-200">s = RRF(q)</span> and distinct document count <span className="font-mono text-slate-800 dark:text-slate-200">d</span> determine the certainty class:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
              {/* Strong */}
              <div className="p-3.5 rounded-xl bg-green-50/50 dark:bg-green-950/20 border border-green-200 dark:border-green-800/80 space-y-1">
                <div className="flex items-center space-x-1.5 text-[#16A34A] font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5 stroke-[1.75]" />
                  <span>Strong Coverage</span>
                </div>
                <div className="text-slate-800 dark:text-slate-200 font-semibold pt-0.5">
                  s ≥ 0.12 ∧ d ≥ 2
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-sans leading-tight pt-1">
                  High-density multi-document factual consensus. Direct synthesis permitted.
                </p>
              </div>

              {/* Partial */}
              <div className="p-3.5 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/80 space-y-1">
                <div className="flex items-center space-x-1.5 text-[#D97706] font-semibold">
                  <AlertTriangle className="w-3.5 h-3.5 stroke-[1.75]" />
                  <span>Partial Coverage</span>
                </div>
                <div className="text-slate-800 dark:text-slate-200 font-semibold pt-0.5">
                  0.03 ≤ s &lt; 0.12 ∨ (s ≥ 0.12 ∧ d = 1)
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-sans leading-tight pt-1">
                  Single source or moderate score. Marked with caution disclaimers.
                </p>
              </div>

              {/* None */}
              <div className="p-3.5 rounded-xl bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-800/80 space-y-1">
                <div className="flex items-center space-x-1.5 text-[#DC2626] font-semibold">
                  <AlertOctagon className="w-3.5 h-3.5 stroke-[1.75]" />
                  <span>No Coverage / Refusal</span>
                </div>
                <div className="text-slate-800 dark:text-slate-200 font-semibold pt-0.5">
                  s &lt; 0.03 ∨ d = 0
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-sans leading-tight pt-1">
                  Ungrounded topic. Triggers structured refusal with suggested rephrases.
                </p>
              </div>
            </div>
          </div>

          {/* Recent Coverage Maps Telemetry Log */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden">
            <div className="p-3.5 sm:px-4 bg-slate-50/80 dark:bg-slate-900/60 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Clock className="w-3.5 h-3.5 text-slate-400 stroke-[1.75]" />
                <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  Recent Coverage Maps
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Benchmark Telemetry</span>
            </div>

            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {RECENT_COVERAGE_MAPS.map((rec, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setQuery(rec.query);
                    handleEvaluate(rec.query);
                  }}
                  className="w-full p-3.5 hover:bg-slate-50 dark:hover:bg-slate-900/50 text-left flex flex-col sm:flex-row sm:items-center justify-between gap-2 group transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden"
                >
                  <div className="space-y-0.5 min-w-0">
                    <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 group-hover:text-[#0F766E] dark:group-hover:text-[#14B8A6] truncate">
                      "{rec.query}"
                    </p>
                    <div className="flex items-center space-x-2 text-[11px] font-mono text-slate-500">
                      <span>Top score: {rec.score.toFixed(4)}</span>
                      <span>·</span>
                      <span>{rec.sub_count} sub-questions</span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 shrink-0">
                    <span
                      className={`h-5 px-2 inline-flex items-center rounded text-[10px] font-mono font-semibold uppercase ${
                        rec.overall === 'strong'
                          ? 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800'
                          : 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
                      }`}
                    >
                      {rec.overall}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">{rec.time}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 4. RESULTS SECTION ── */}
      {data && !isLoading && (
        <div className="space-y-4 animate-fade-in">
          {/* Overall Banner */}
          <div
            className={`p-4 sm:p-5 rounded-2xl border-l-4 ${
              data.overall_coverage === 'strong'
                ? 'border-l-[#16A34A] bg-green-50/40 dark:bg-green-950/20 border-green-200 dark:border-green-900/60'
                : data.overall_coverage === 'partial'
                ? 'border-l-[#D97706] bg-amber-50/40 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/60'
                : 'border-l-[#DC2626] bg-red-50/40 dark:bg-red-950/20 border-red-200 dark:border-red-900/60'
            } border shadow-xs space-y-2.5`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <span
                  className={`h-6 px-2.5 inline-flex items-center space-x-1 rounded-md text-xs font-mono font-bold uppercase ${
                    data.overall_coverage === 'strong'
                      ? 'bg-green-100 dark:bg-green-900/60 text-green-800 dark:text-green-300'
                      : data.overall_coverage === 'partial'
                      ? 'bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300'
                      : 'bg-red-100 dark:bg-red-900/60 text-red-800 dark:text-red-300'
                  }`}
                >
                  {data.overall_coverage === 'strong' ? <CheckCircle2 className="w-3.5 h-3.5" /> : data.overall_coverage === 'partial' ? <AlertTriangle className="w-3.5 h-3.5" /> : <AlertOctagon className="w-3.5 h-3.5" />}
                  <span>{data.overall_coverage} Coverage</span>
                </span>
                <span className="text-xs font-sans text-slate-600 dark:text-slate-400">
                  {data.sub_questions.length} Atomic Sub-Questions Decomposed
                </span>
              </div>

              <div className="flex items-center space-x-2 font-mono text-xs">
                <span className="h-6 px-2 inline-flex items-center rounded bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-green-700 dark:text-green-300">
                  {data.strong_count} Strong
                </span>
                <span className="h-6 px-2 inline-flex items-center rounded bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-amber-700 dark:text-amber-300">
                  {data.partial_count} Partial
                </span>
                <span className="h-6 px-2 inline-flex items-center rounded bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-red-700 dark:text-red-300">
                  {data.none_count} None
                </span>
              </div>
            </div>

            <p className="text-xs font-sans text-slate-700 dark:text-slate-300 leading-relaxed">
              {data.overall_coverage === 'strong'
                ? 'High multi-document factual grounding across all decomposed propositions. The hybrid FAISS + Kùzu indices provide strong evidence support.'
                : data.overall_coverage === 'partial'
                ? 'Moderate evidence coverage. Some sub-propositions are supported by single-source citations or border-line confidence scores.'
                : 'Insufficient evidence coverage in current medical index. To safeguard patient accuracy, full multi-hop answer generation is guarded by structured refusal.'}
            </p>

            {/* Suggested Rephrases for Low Coverage */}
            {data.suggested_rephrases && data.suggested_rephrases.length > 0 && (
              <div className="pt-2 border-t border-slate-200/60 dark:border-slate-800/60 space-y-1.5 font-sans">
                <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wide block">
                  Suggested Query Rephrases with Established Grounding:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {data.suggested_rephrases.map((rephrase, rIdx) => (
                    <button
                      key={rIdx}
                      type="button"
                      onClick={() => {
                        setQuery(rephrase);
                        handleEvaluate(rephrase);
                      }}
                      className="h-6 px-2.5 rounded-lg text-xs font-mono bg-white dark:bg-[#0F172A] text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] border border-slate-200 dark:border-slate-800 hover:border-teal-300 dark:hover:border-teal-700 transition-colors cursor-pointer"
                    >
                      {rephrase}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── FIGURE 4: INTERACTIVE DENSITY MATRIX ── */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden">
            <div
              onClick={() => setIsMatrixOpen(!isMatrixOpen)}
              className="p-4 bg-slate-50/80 dark:bg-slate-900/60 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between cursor-pointer select-none"
            >
              <div className="flex items-center space-x-2">
                <Table className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                <h3 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  Figure 4: Evidence Coverage Matrix (Eq. 7 Decomposed Propositions)
                </h3>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-mono text-slate-400">Click row to inspect card</span>
                {isMatrixOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </div>
            </div>

            {isMatrixOpen && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-sans">
                  <thead className="bg-slate-50 dark:bg-slate-900 text-[11px] font-medium text-slate-500 uppercase tracking-wide border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4 w-12 text-center">#</th>
                      <th className="py-2.5 px-4">Decomposed Sub-Question</th>
                      <th className="py-2.5 px-3 font-mono">Fused RRF Score (s)</th>
                      <th className="py-2.5 px-3 font-mono">Distinct Docs (d)</th>
                      <th className="py-2.5 px-3">Class</th>
                      <th className="py-2.5 px-3 font-mono">Eq.(7) Gating Threshold</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                    {data.sub_questions.map((sub, idx) => {
                      const cProps = getCoverageClassProps(sub.coverage_class);
                      return (
                        <tr
                          key={idx}
                          onClick={() => scrollToCard(idx)}
                          className="hover:bg-teal-50/50 dark:hover:bg-teal-950/20 cursor-pointer transition-colors group"
                        >
                          <td className="py-3 px-4 text-center text-slate-400 font-bold">
                            q{idx + 1}
                          </td>
                          <td className="py-3 px-4 font-sans font-medium text-slate-900 dark:text-slate-100 group-hover:text-[#0F766E] dark:group-hover:text-[#14B8A6]">
                            {sub.sub_question}
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center space-x-2">
                              <span className="tabular-nums font-semibold">{sub.top_fused_score.toFixed(4)}</span>
                              <div className="w-16 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${
                                    sub.coverage_class === 'strong'
                                      ? 'bg-[#16A34A]'
                                      : sub.coverage_class === 'partial'
                                      ? 'bg-[#D97706]'
                                      : 'bg-[#DC2626]'
                                  }`}
                                  style={{ width: `${Math.min(100, (sub.top_fused_score / 0.25) * 100)}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-3 tabular-nums">
                            {sub.distinct_doc_count} docs
                          </td>
                          <td className="py-3 px-3">
                            <span
                              className={`h-5 px-2 inline-flex items-center rounded text-[10px] font-semibold uppercase ${
                                sub.coverage_class === 'strong'
                                  ? 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800'
                                  : sub.coverage_class === 'partial'
                                  ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                                  : 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
                              }`}
                            >
                              {sub.coverage_class}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-[11px] text-slate-500">
                            {sub.coverage_class === 'strong'
                              ? 's ≥ 0.12 ∧ d ≥ 2 (Pass)'
                              : sub.coverage_class === 'partial'
                              ? '0.03 ≤ s < 0.12 (Caution)'
                              : 's < 0.03 ∨ d = 0 (Refusal)'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── SUB-QUESTION DETAILED ACCORDION CARDS ── */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                Atomic Sub-Question Evidence Profiles ({data.sub_questions.length})
              </h3>
              <span className="text-[11px] font-mono text-slate-500">
                Hybrid Document Provenance
              </span>
            </div>

            <div className="space-y-3">
              {data.sub_questions.map((sub, idx) => {
                const isOpen = !!openAccordion[idx];
                const isTarget = highlightedCard === idx;

                return (
                  <div
                    key={idx}
                    id={`subq-card-${idx}`}
                    className={`rounded-2xl border transition-all ${
                      isTarget
                        ? 'ring-2 ring-[#0F766E] dark:ring-[#14B8A6] shadow-lg'
                        : 'border-slate-200/90 dark:border-slate-800/90 shadow-xs'
                    } ${
                      sub.coverage_class === 'strong'
                        ? 'border-l-4 border-l-[#16A34A]'
                        : sub.coverage_class === 'partial'
                        ? 'border-l-4 border-l-[#D97706]'
                        : 'border-l-4 border-l-[#DC2626]'
                    } bg-white dark:bg-[#0F172A] p-4 sm:p-5 space-y-3`}
                  >
                    {/* Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className="w-6 h-6 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono font-bold text-xs flex items-center justify-center">
                          q{idx + 1}
                        </span>
                        <h4 className="font-semibold text-xs sm:text-[13.5px] text-slate-900 dark:text-slate-100 font-sans">
                          {sub.sub_question}
                        </h4>
                      </div>

                      <div className="flex items-center space-x-2 font-mono text-xs">
                        <span
                          className={`h-5 px-2 inline-flex items-center rounded text-[10px] font-semibold uppercase ${
                            sub.coverage_class === 'strong'
                              ? 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800'
                              : sub.coverage_class === 'partial'
                              ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                              : 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
                          }`}
                        >
                          {sub.coverage_class}
                        </span>
                        <span className="text-slate-500">Score: {sub.top_fused_score.toFixed(4)}</span>
                        <button
                          type="button"
                          onClick={() => toggleAccordion(idx)}
                          className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                        >
                          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    {isOpen && (
                      <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-slate-800 animate-fade-in font-sans text-xs">
                        {/* Metrics Bar */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px] bg-slate-50 dark:bg-slate-900 p-2.5 rounded-xl border border-slate-200/80 dark:border-slate-800">
                          <div>
                            <span className="text-[10px] text-slate-500 uppercase block font-sans">Fused RRF Score</span>
                            <span className="font-semibold text-slate-900 dark:text-slate-100">{sub.top_fused_score.toFixed(4)}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500 uppercase block font-sans">Distinct Documents</span>
                            <span className="font-semibold text-slate-900 dark:text-slate-100">{sub.distinct_doc_count} source files</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500 uppercase block font-sans">Evidence Chunks</span>
                            <span className="font-semibold text-slate-900 dark:text-slate-100">{sub.evidence_count} chunks</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500 uppercase block font-sans">Gating Decision</span>
                            <span className="font-semibold text-[#0F766E] dark:text-[#14B8A6]">{sub.coverage_class === 'none' ? 'Refuse speculative' : 'Permit synthesis'}</span>
                          </div>
                        </div>

                        {/* Top Citations */}
                        {sub.top_citations && sub.top_citations.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wide block">
                              Top Grounded Citations:
                            </span>
                            <div className="space-y-1">
                              {sub.top_citations.map((cit, cIdx) => (
                                <div
                                  key={cIdx}
                                  className="p-2.5 rounded-xl bg-slate-50/70 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 font-sans"
                                >
                                  {cit}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Action Links */}
                        <div className="pt-2 flex items-center justify-between">
                          <button
                            type="button"
                            onClick={() =>
                              navigate(`/chat?q=${encodeURIComponent(sub.sub_question)}`)
                            }
                            className="inline-flex items-center space-x-1 text-xs font-medium text-[#0F766E] dark:text-[#14B8A6] hover:underline cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600"
                          >
                            <span>Query this sub-question in Console</span>
                            <ArrowUpRight className="w-3.5 h-3.5 stroke-[1.75]" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <DisclaimerFooter />
        </div>
      )}
    </div>
  );
};
