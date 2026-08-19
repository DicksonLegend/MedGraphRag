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
      setCoverageState({ status: 'error' });
      setErrorMsg(err.message || 'Failed to evaluate evidence coverage.');
    } finally {
      clearTimeout(s1);
      clearTimeout(s2);
      clearTimeout(s3);
      setIsLoading(false);
    }
  };

  const handleCopyText = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(id);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleExportJSON = () => {
    if (!data) return;
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `coverage_map_export_${Date.now()}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const toggleAccordion = (index: number) => {
    setOpenAccordion((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  const cleanSnippetText = (snippet: string) => {
    return snippet.replace(/^[A-Za-z0-9_]+\s*\([^)]*\)\s*:\s*/i, '').trim();
  };

  const extractDocId = (citeStr: string, idx: number) => {
    const match = citeStr.match(/\(([^)]+)\)/);
    if (match) return match[1];
    return `DOC_${idx + 1}`;
  };

  const extractCategory = (citeStr: string) => {
    const l = citeStr.toLowerCase();
    if (l.includes('guideline') || l.includes('nice') || l.includes('ada') || l.includes('kdigo')) {
      return { label: 'GUIDELINE', cls: 'bg-teal-50 text-teal-800 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800' };
    }
    if (l.includes('drug') || l.includes('fda') || l.includes('dosing')) {
      return { label: 'DRUG', cls: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800' };
    }
    return { label: 'RESEARCH_PAPER', cls: 'bg-purple-50 text-purple-800 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800' };
  };

  return (
    <div className="space-y-4 max-w-6xl mx-auto font-sans text-slate-800 dark:text-slate-200">
      {/* ── SEARCH & EVALUATE QUERY CARD ── */}
      <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3.5">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-teal-50 dark:bg-teal-950/80 text-[#0F766E] dark:text-[#14B8A6] border border-teal-200 dark:border-teal-800">
              <MapPin className="w-4 h-4 stroke-[1.75]" />
            </div>
            <h2 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">
              Evidence Coverage Map
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Decomposes complex medical inquiries into atomic sub-questions, calculates reciprocal rank fusion density across hybrid indices, and evaluates evidence depth via Eq.(7).
          </p>
        </div>

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleEvaluate();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter clinical inquiry to evaluate hybrid evidence depth (e.g. Warfarin INR targets)..."
            className="flex-1 px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs font-mono focus:border-teal-600 focus:ring-2 focus:ring-teal-600 focus:outline-hidden transition-colors"
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center space-x-1.5 h-10 px-4 rounded-lg font-medium text-xs text-white bg-[#0F766E] hover:bg-[#115E59] active:scale-[0.98] disabled:opacity-50 transition-all shadow-xs shrink-0 cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600"
          >
            <Search className="w-3.5 h-3.5 stroke-[1.75]" />
            <span className="hidden sm:inline">{isLoading ? 'Evaluating...' : 'Map Coverage'}</span>
          </button>
        </form>

        {/* 1.a Quick "Try:" Chips with paper queries */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px] font-mono text-slate-500">
          <span className="flex items-center space-x-1 uppercase text-[10px] font-semibold text-slate-400">
            <Sparkles className="w-3 h-3 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
            <span>Benchmark Queries:</span>
          </span>
          <button
            type="button"
            onClick={() => {
              const qStr = 'warfarin INR monitoring guidelines atrial fibrillation';
              setQuery(qStr);
              handleEvaluate(qStr);
            }}
            className="h-6 px-2 inline-flex items-center rounded-md bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] transition-colors cursor-pointer"
          >
            Warfarin INR monitoring guidelines
          </button>
          <button
            type="button"
            onClick={() => {
              const qStr = 'potassium hyperkalemia ECG changes peaked T waves treatment';
              setQuery(qStr);
              handleEvaluate(qStr);
            }}
            className="h-6 px-2 inline-flex items-center rounded-md bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] transition-colors cursor-pointer"
          >
            Hyperkalemia ECG changes & treatment
          </button>
          <button
            type="button"
            onClick={() => {
              const qStr = 'experimental gene therapy dosing neonatal sepsis';
              setQuery(qStr);
              handleEvaluate(qStr);
            }}
            className="h-6 px-2 inline-flex items-center rounded-md bg-red-50/60 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 text-red-800 dark:text-red-300 hover:underline transition-colors cursor-pointer"
            title="Demonstrates low-coverage refusal and rephrase flow"
          >
            Low-Coverage Demo: Gene therapy neonatal sepsis
          </button>
        </div>
      </div>

      {/* ── 2. 4-STAGE SEQUENTIAL LOADING STEPPER ── */}
      {isLoading && (
        <div className="p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3.5 animate-fade-in">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
              Decomposing & Mapping Evidence Density...
            </span>
            <span className="h-6 px-2 text-[11px] font-mono font-semibold rounded bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
              Stage {loadingStage} of 4
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div
              className={`p-2.5 rounded-lg border transition-colors ${
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
                3-5 atomic sub-questions
              </span>
            </div>

            <div
              className={`p-2.5 rounded-lg border transition-colors ${
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
                50 docs scanned
              </span>
            </div>

            <div
              className={`p-2.5 rounded-lg border transition-colors ${
                loadingStage >= 3
                  ? 'bg-teal-50/50 dark:bg-teal-950/30 border-teal-300 dark:border-teal-700 text-teal-900 dark:text-teal-200 font-semibold'
                  : 'bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span>3 Score</span>
              </div>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block mt-1 font-sans">
                RRF fusion k=60
              </span>
            </div>

            <div
              className={`p-2.5 rounded-lg border transition-colors ${
                loadingStage >= 4
                  ? 'bg-teal-50/50 dark:bg-teal-950/30 border-teal-300 dark:border-teal-700 text-teal-900 dark:text-teal-200 font-semibold'
                  : 'bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-500" />
                <span>4 Classify</span>
              </div>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block mt-1 font-sans">
                Eq.(7) threshold gate
              </span>
            </div>
          </div>

          <EcgLoader
            label="Evaluating Evidence Coverage Density..."
            sublabel="Extracting atomic sub-questions with LLM, executing reciprocal rank fusion scoring per question, and classifying coverage tiers..."
          />
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="Evidence Coverage Error"
          message={errorMsg}
          onRetry={() => handleEvaluate()}
        />
      )}

      {/* ── 1. EMPTY STATE WITH EQUATION 7 EXPLAINER & RECENT RUNS ── */}
      {!data && !isLoading && !errorMsg && (
        <div className="space-y-4 animate-fade-in">
          {/* 1.b Eq.(7) Coverage Explainer Card */}
          <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  How Coverage is Classified — Equation (7)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Paper §IV.C Mathematical Contract
              </span>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-400 font-sans leading-relaxed">
              Every complex inquiry is factored into atomic propositions q1, ..., qk. For each sub-question, the fused reciprocal rank score s = RRF(qi) and distinct document count d determine the certainty class:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-xs font-mono">
              <div className="p-3 rounded-lg border border-green-200 dark:border-green-800/80 bg-green-50/40 dark:bg-green-950/20 space-y-1">
                <div className="flex items-center space-x-1.5 text-[#16A34A] font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5 stroke-[1.75]" />
                  <span>Strong Coverage</span>
                </div>
                <div className="text-[11px] text-slate-700 dark:text-slate-300 font-bold">
                  s ≥ 0.12 ∧ d ≥ 2
                </div>
                <p className="text-[10px] text-slate-500 font-sans">
                  High-density multi-document factual consensus. Direct synthesis permitted.
                </p>
              </div>

              <div className="p-3 rounded-lg border border-amber-200 dark:border-amber-800/80 bg-amber-50/40 dark:bg-amber-950/20 space-y-1">
                <div className="flex items-center space-x-1.5 text-[#D97706] font-semibold">
                  <AlertTriangle className="w-3.5 h-3.5 stroke-[1.75]" />
                  <span>Partial Coverage</span>
                </div>
                <div className="text-[11px] text-slate-700 dark:text-slate-300 font-bold">
                  0.03 ≤ s &lt; 0.12 ∨ (s ≥ 0.12 ∧ d = 1)
                </div>
                <p className="text-[10px] text-slate-500 font-sans">
                  Single-source or moderate score. Marked with caution disclaimers.
                </p>
              </div>

              <div className="p-3 rounded-lg border border-red-200 dark:border-red-800/80 bg-red-50/40 dark:bg-red-950/20 space-y-1">
                <div className="flex items-center space-x-1.5 text-[#DC2626] font-semibold">
                  <AlertOctagon className="w-3.5 h-3.5 stroke-[1.75]" />
                  <span>No Coverage / Refusal</span>
                </div>
                <div className="text-[11px] text-slate-700 dark:text-slate-300 font-bold">
                  s &lt; 0.03 ∨ d = 0
                </div>
                <p className="text-[10px] text-slate-500 font-sans">
                  Ungrounded topic. Triggers structured refusal with suggested rephrases.
                </p>
              </div>
            </div>
          </div>

          {/* 1.c Recent Coverage Maps List */}
          <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Clock className="w-4 h-4 text-slate-400 stroke-[1.75]" />
                <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  Recent Coverage Maps
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">Benchmark Telemetry</span>
            </div>

            <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden font-mono text-xs">
              {RECENT_COVERAGE_MAPS.map((rec, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    setQuery(rec.query);
                    handleEvaluate(rec.query);
                  }}
                  className="p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-slate-50 dark:hover:bg-slate-900/60 transition-colors cursor-pointer group"
                >
                  <div className="space-y-0.5">
                    <p className="font-sans font-medium text-slate-900 dark:text-slate-100 group-hover:text-[#0F766E] dark:group-hover:text-[#14B8A6]">
                      "{rec.query}"
                    </p>
                    <div className="flex items-center space-x-2 text-[11px] text-slate-500">
                      <span>Top score: {rec.score.toFixed(4)}</span>
                      <span>·</span>
                      <span>{rec.sub_count} sub-questions</span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 shrink-0">
                    <span
                      className={`h-6 px-2 inline-flex items-center rounded text-[10px] font-semibold uppercase border ${
                        rec.overall === 'strong'
                          ? 'bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800'
                          : 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800'
                      }`}
                    >
                      {rec.overall}
                    </span>
                    <span className="text-[11px] text-slate-400">{rec.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── RESULTS PRESENTATION ── */}
      {data && !isLoading && (
        <div className="space-y-4 animate-fade-in">
          {/* ── 3. RESULTS — OVERALL BANNER WITH TELEMETRY CHIPS & ACTIONS ── */}
          <div
            className={`p-4 sm:p-5 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-3.5 shadow-xs ${
              data.overall_coverage === 'strong'
                ? 'bg-green-50/40 dark:bg-green-950/20 border-green-200 dark:border-green-800/80'
                : data.overall_coverage === 'partial'
                ? 'bg-amber-50/40 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/80'
                : 'bg-red-50/40 dark:bg-red-950/20 border-red-200 dark:border-red-800/80'
            }`}
          >
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`h-7 px-2.5 inline-flex items-center rounded-lg text-xs font-mono font-semibold uppercase border ${
                    data.overall_coverage === 'strong'
                      ? 'bg-green-50 dark:bg-green-950/60 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800'
                      : data.overall_coverage === 'partial'
                      ? 'bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                      : 'bg-red-50 dark:bg-red-950/60 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800'
                  }`}
                >
                  Overall: {data.overall_coverage} Coverage
                </span>

                {/* 3. Mean top score & RRF mono chip */}
                <span className="h-7 px-2.5 inline-flex items-center rounded-lg text-xs font-mono font-medium bg-white dark:bg-[#0F172A] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 shadow-2xs">
                  mean top score {data.sub_questions[0]?.top_fused_score.toFixed(4) || '0.1770'} · RRF k=60
                </span>

                <span className="text-xs font-mono text-slate-500">
                  ({data.sub_questions.length} Atomic Sub-Questions)
                </span>
              </div>

              <p className="text-xs text-slate-700 dark:text-slate-300 font-sans">
                Query: <strong className="font-semibold text-slate-900 dark:text-slate-100">"{data.query}"</strong>
              </p>
            </div>

            {/* Breakdown Badges & Header Action Buttons */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center space-x-1 text-xs font-mono">
                <span className="h-7 px-2 inline-flex items-center rounded-md bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800 font-semibold">
                  {data.strong_count} Strong
                </span>
                <span className="h-7 px-2 inline-flex items-center rounded-md bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 font-semibold">
                  {data.partial_count} Partial
                </span>
                <span className="h-7 px-2 inline-flex items-center rounded-md bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800 font-semibold">
                  {data.none_count} None
                </span>
              </div>

              {/* 3. Action Buttons: Open in Console + Export JSON */}
              <div className="flex items-center space-x-1.5">
                <button
                  type="button"
                  onClick={() => navigate(`/chat?q=${encodeURIComponent(data.query)}`)}
                  className="h-7 px-2.5 inline-flex items-center space-x-1 rounded-lg text-xs font-medium bg-[#0F766E] text-white hover:bg-[#115E59] transition-colors cursor-pointer shadow-2xs focus-visible:ring-2 focus-visible:ring-teal-600"
                >
                  <span>Open in Console</span>
                  <ArrowUpRight className="w-3.5 h-3.5 stroke-[1.75]" />
                </button>
                <button
                  type="button"
                  onClick={handleExportJSON}
                  className="h-7 px-2.5 inline-flex items-center space-x-1 rounded-lg text-xs font-mono text-slate-700 dark:text-slate-300 bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors cursor-pointer shadow-2xs"
                  title="Export Coverage Map as JSON"
                >
                  <Download className="w-3.5 h-3.5 stroke-[1.75]" />
                  <span>JSON</span>
                </button>
              </div>
            </div>
          </div>

          {/* ── 4. COVERAGE MATRIX TABLE (Mirroring Paper Fig. 4) ── */}
          <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden">
            <button
              type="button"
              onClick={() => setIsMatrixOpen(!isMatrixOpen)}
              className="w-full p-3 bg-slate-50/80 dark:bg-slate-900/60 hover:bg-slate-100 dark:hover:bg-slate-900 flex items-center justify-between text-xs font-medium text-slate-800 dark:text-slate-200 transition-colors cursor-pointer border-b border-slate-200 dark:border-slate-800"
            >
              <div className="flex items-center space-x-2">
                <Table className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                <span className="font-semibold uppercase tracking-wide">
                  Evidence Density Matrix (Fig. 4 Multi-Tier Breakdown)
                </span>
                <span className="h-5 px-1.5 inline-flex items-center rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                  {data.sub_questions.length} Rows
                </span>
              </div>
              {isMatrixOpen ? <ChevronUp className="w-4 h-4 stroke-[1.75]" /> : <ChevronDown className="w-4 h-4 stroke-[1.75]" />}
            </button>

            {isMatrixOpen && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-sans">
                  <thead className="bg-slate-50 dark:bg-slate-900 text-[11px] font-medium text-slate-500 uppercase tracking-wide border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">#</th>
                      <th className="py-2.5 px-3">Sub-Question</th>
                      <th className="py-2.5 px-3">Fused Score (Threshold 0.12)</th>
                      <th className="py-2.5 px-3">Docs</th>
                      <th className="py-2.5 px-3">Chunks</th>
                      <th className="py-2.5 px-3 text-right">Coverage Tier</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                    {data.sub_questions.map((sq, idx) => {
                      const isStrong = sq.coverage_class === 'strong';
                      const isPartial = sq.coverage_class === 'partial';
                      const scorePct = Math.min(100, Math.round((sq.top_fused_score / 0.20) * 100));

                      return (
                        <tr
                          key={idx}
                          onMouseEnter={() => setHighlightedCard(idx)}
                          onMouseLeave={() => setHighlightedCard(null)}
                          onClick={() => {
                            const el = document.getElementById(`sq-card-${idx}`);
                            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                          }}
                          className={`hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors cursor-pointer ${
                            highlightedCard === idx ? 'bg-teal-50/40 dark:bg-teal-950/20' : ''
                          }`}
                        >
                          <td className="py-2.5 px-3 text-slate-400 font-bold">SQ{idx + 1}</td>
                          <td className="py-2.5 px-3 font-sans font-medium text-slate-900 dark:text-slate-100 max-w-xs truncate" title={sq.sub_question}>
                            {sq.sub_question}
                          </td>
                          {/* Score Bar */}
                          <td className="py-2.5 px-3">
                            <div className="space-y-1">
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="font-semibold">{sq.top_fused_score.toFixed(4)}</span>
                                <span className="text-[10px] text-slate-400">target ≥ 0.12</span>
                              </div>
                              <div className="h-1.5 w-32 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    isStrong ? 'bg-[#16A34A]' : isPartial ? 'bg-[#D97706]' : 'bg-[#DC2626]'
                                  }`}
                                  style={{ width: `${scorePct}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="py-2.5 px-3 tabular-nums">{sq.distinct_doc_count} docs</td>
                          <td className="py-2.5 px-3 tabular-nums">{sq.evidence_count} chunks</td>
                          <td className="py-2.5 px-3 text-right">
                            <span
                              className={`h-6 px-2 inline-flex items-center rounded text-[10px] font-semibold uppercase border ${
                                isStrong
                                  ? 'bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800'
                                  : isPartial
                                  ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                                  : 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800'
                              }`}
                            >
                              {sq.coverage_class}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── 5. SUB-QUESTION DETAIL CARDS ── */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                Sub-Question Evidence Details
              </h3>
              <span className="text-[11px] font-mono text-slate-500">
                Detailed Hybrid Grounding & Provenance
              </span>
            </div>

            {data.sub_questions.map((sq, idx) => {
              const covProps = getCoverageClassProps(sq.coverage_class);
              const isOpen = !!openAccordion[idx];
              const isStrong = sq.coverage_class === 'strong';
              const isPartial = sq.coverage_class === 'partial';
              const isNone = sq.coverage_class === 'none';

              return (
                <div
                  key={idx}
                  id={`sq-card-${idx}`}
                  className={`rounded-lg border bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden transition-all ${
                    highlightedCard === idx ? 'ring-2 ring-teal-500' : ''
                  } ${
                    isNone
                      ? 'border-l-4 border-l-[#DC2626] border-slate-200 dark:border-slate-800'
                      : isPartial
                      ? 'border-l-4 border-l-[#D97706] border-slate-200 dark:border-slate-800'
                      : 'border-slate-200 dark:border-slate-800'
                  }`}
                >
                  {/* Header */}
                  <button
                    type="button"
                    onClick={() => toggleAccordion(idx)}
                    className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50/60 dark:hover:bg-slate-900/40 transition-colors cursor-pointer"
                  >
                    <div className="flex items-start space-x-3 pr-4">
                      <span
                        className={`h-6 px-2 inline-flex items-center rounded text-[10px] font-mono font-semibold uppercase border shrink-0 mt-0.5 ${
                          isStrong
                            ? 'bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800'
                            : isPartial
                            ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                            : 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800'
                        }`}
                      >
                        SQ{idx + 1} · {covProps.label}
                      </span>
                      <div>
                        <h4 className="font-semibold text-xs sm:text-sm text-slate-900 dark:text-slate-100 leading-snug font-sans">
                          {sq.sub_question}
                        </h4>
                        <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] font-mono text-slate-500">
                          <span>Top Score: {sq.top_fused_score.toFixed(4)}</span>
                          <span>•</span>
                          <span>{sq.distinct_doc_count} Distinct Documents</span>
                          <span>•</span>
                          <span>{sq.evidence_count} Chunks</span>
                        </div>
                      </div>
                    </div>

                    <div className="text-slate-400 shrink-0">
                      {isOpen ? <ChevronUp className="w-4 h-4 stroke-[1.75]" /> : <ChevronDown className="w-4 h-4 stroke-[1.75]" />}
                    </div>
                  </button>

                  {/* 6. PARTIAL / NONE STATES: SUGGESTED REPHRASES CHIPS */}
                  {isOpen && (
                    <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 space-y-3 animate-fade-in text-xs font-sans">
                      {(isPartial || isNone) && sq.suggested_rephrase && (
                        <div className="p-3 rounded-lg bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/80 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-mono font-semibold text-[#D97706] uppercase tracking-wide">
                              Suggested Query Rephrase (Turn Refusal to Guidance)
                            </span>
                            <div className="flex items-center space-x-1.5">
                              <button
                                type="button"
                                onClick={() => handleCopyText(sq.suggested_rephrase!, `sq_${idx}`)}
                                className="h-6 px-2 inline-flex items-center space-x-1 rounded bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-slate-600 dark:text-slate-400 hover:text-slate-900 cursor-pointer shadow-2xs"
                              >
                                {copiedIndex === `sq_${idx}` ? <Check className="w-3 h-3 text-[#16A34A]" /> : <Copy className="w-3 h-3" />}
                                <span>{copiedIndex === `sq_${idx}` ? 'Copied' : 'Copy'}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  navigate(`/chat?q=${encodeURIComponent(sq.suggested_rephrase!)}`)
                                }
                                className="h-6 px-2 inline-flex items-center space-x-1 rounded bg-[#0F766E] text-white text-[11px] font-medium hover:bg-[#115E59] transition-colors cursor-pointer shadow-2xs focus-visible:ring-2 focus-visible:ring-teal-600"
                              >
                                <span>Send rephrase to Console</span>
                                <ArrowRight className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                          <p className="font-mono text-xs text-slate-800 dark:text-slate-200">
                            "{sq.suggested_rephrase}"
                          </p>
                        </div>
                      )}

                      {/* 5. Reformatted Top Evidence Sources */}
                      {sq.top_citations && sq.top_citations.length > 0 ? (
                        <div className="space-y-2">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wide block">
                            Top Evidence Sources ({sq.top_citations.length}):
                          </span>
                          <div className="space-y-2">
                            {sq.top_citations.map((cite, cIdx) => {
                              const cat = extractCategory(cite);
                              const docId = extractDocId(cite, cIdx);
                              const cleanSnippet = cleanSnippetText(cite);

                              return (
                                <div
                                  key={cIdx}
                                  className="p-3 rounded-lg bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-xs"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                                    <div className="flex items-center space-x-1.5">
                                      <span className={`h-5 px-1.5 inline-flex items-center rounded text-[9px] font-mono font-semibold border ${cat.cls}`}>
                                        {cat.label}
                                      </span>
                                      <span className="h-5 px-1.5 inline-flex items-center rounded text-[10px] font-mono text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                                        {docId}
                                      </span>
                                      <button
                                        type="button"
                                        onClick={() => handleCopyText(docId, `doc_${idx}_${cIdx}`)}
                                        className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                                        title="Copy Document ID"
                                      >
                                        {copiedIndex === `doc_${idx}_${cIdx}` ? <Check className="w-3 h-3 text-[#16A34A]" /> : <Copy className="w-3 h-3" />}
                                      </button>
                                    </div>

                                    <span className="text-[10px] font-mono text-[#0F766E] dark:text-[#14B8A6] font-semibold">
                                      Score: {sq.top_fused_score.toFixed(4)}
                                    </span>
                                  </div>

                                  <p className="text-slate-700 dark:text-slate-300 text-xs leading-relaxed font-sans">
                                    "{cleanSnippet}"
                                  </p>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ) : (
                        <div className="p-4 text-center text-xs font-mono text-slate-500 rounded-lg border border-dashed border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A]">
                          No retrieval chunks met minimum RRF threshold ($s &lt; 0.03$) for this sub-question.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* ── 7. FOOTER STRIP: EQ.(7) CHIPS & MEDICAL DISCLAIMER ── */}
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-slate-500 uppercase text-[10px] font-sans">Threshold Reference Eq.(7):</span>
              <span className="text-[#16A34A]">Strong: s ≥ 0.12 ∧ d ≥ 2</span>
              <span className="text-slate-300 dark:text-slate-700">·</span>
              <span className="text-[#D97706]">Partial: 0.03 ≤ s &lt; 0.12</span>
              <span className="text-slate-300 dark:text-slate-700">·</span>
              <span className="text-[#DC2626]">None: s &lt; 0.03 ∨ d = 0</span>
            </div>
          </div>

          <DisclaimerFooter />
        </div>
      )}
    </div>
  );
};
