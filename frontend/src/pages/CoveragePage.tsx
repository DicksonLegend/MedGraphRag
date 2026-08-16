import React, { useState } from 'react';
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
} from 'lucide-react';

export const CoveragePage: React.FC = () => {
  const [query, setQuery] = useState('warfarin INR monitoring guidelines atrial fibrillation');
  const [data, setData] = useState<CoverageMap | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [openAccordion, setOpenAccordion] = useState<{ [key: number]: boolean }>({ 0: true });

  const handleEvaluate = async (searchQuery?: string) => {
    const q = (searchQuery || query).trim();
    if (!q) return;

    setIsLoading(true);
    setErrorMsg(null);
    setData(null);

    try {
      const res = await featuresApi.getCoverageMap({ query: q });
      setData(res);
      // Open all accordions by default
      const initialOpen: { [key: number]: boolean } = {};
      res.sub_questions.forEach((_, idx) => {
        initialOpen[idx] = true;
      });
      setOpenAccordion(initialOpen);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to evaluate evidence coverage.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyRephrase = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleUseRephrase = (text: string) => {
    // Extract text from quotes if formatted like "Try searching: '...'"
    const match = text.match(/'([^']+)'/);
    const cleanQuery = match ? match[1] : text;
    setQuery(cleanQuery);
    handleEvaluate(cleanQuery);
  };

  const toggleAccordion = (index: number) => {
    setOpenAccordion((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Search and Evaluate Input Card */}
      <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-brand text-white shadow-xs">
              <MapPin className="w-5 h-5" />
            </div>
            <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink">
              Evidence Coverage Map
            </h2>
          </div>
          <p className="text-xs text-ink-muted mt-1 font-sans">
            Decomposes complex medical inquiries into atomic sub-questions, evaluates multi-document evidence density across our hybrid index, and generates query rephrases for low-coverage gaps.
          </p>
        </div>

        {/* Input Box */}
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
            placeholder="Enter clinical query to evaluate hybrid evidence depth..."
            className="flex-1 px-4 py-3 rounded-xl border border-card-border bg-canvas text-ink text-sm font-sans focus:border-brand focus:ring-1 focus:ring-brand transition-colors"
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center space-x-2 px-6 py-3 rounded-xl font-heading font-bold text-white bg-brand hover:bg-brand-hover active:scale-[0.98] disabled:opacity-50 transition-all shadow-sm shrink-0"
          >
            <Search className="w-4 h-4" />
            <span className="hidden sm:inline">{isLoading ? 'Evaluating...' : 'Map Coverage'}</span>
          </button>
        </form>

        {/* Quick Example */}
        <div className="flex items-center space-x-2 text-[11px] font-mono text-ink-subtle">
          <Sparkles className="w-3.5 h-3.5 text-brand" />
          <span>Try:</span>
          <button
            type="button"
            onClick={() => {
              const ex = 'warfarin INR monitoring guidelines atrial fibrillation';
              setQuery(ex);
              handleEvaluate(ex);
            }}
            className="text-brand hover:underline truncate"
          >
            warfarin INR monitoring guidelines atrial fibrillation
          </button>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs">
          <EcgLoader
            label="Decomposing & Mapping Evidence Density..."
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

      {/* Results Presentation */}
      {data && !isLoading && (
        <div className="space-y-6 animate-fade-in">
          {/* Overall Coverage Banner */}
          <div
            className={`p-6 rounded-2xl border flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm ${
              data.overall_coverage === 'strong'
                ? 'bg-status-success-bg/40 border-status-success/30'
                : data.overall_coverage === 'partial'
                ? 'bg-status-caution-bg/40 border-status-caution/30'
                : 'bg-status-danger-bg/40 border-status-danger/30'
            }`}
          >
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span
                  className={`px-3 py-1 text-xs font-mono font-bold rounded-full border uppercase ${
                    data.overall_coverage === 'strong'
                      ? 'bg-status-success-bg text-status-success border-status-success/30'
                      : data.overall_coverage === 'partial'
                      ? 'bg-status-caution-bg text-status-caution border-status-caution/30'
                      : 'bg-status-danger-bg text-status-danger border-status-danger/30'
                  }`}
                >
                  Overall: {data.overall_coverage} Coverage
                </span>
                <span className="text-xs font-mono text-ink-muted">
                  ({data.sub_questions.length} Atomic Sub-Questions)
                </span>
              </div>
              <p className="text-xs text-ink font-sans pt-1">
                Query: <strong className="font-heading text-ink">"{data.query}"</strong>
              </p>
            </div>

            {/* Breakdown Badges */}
            <div className="flex items-center space-x-2 text-xs font-mono">
              <span className="px-2.5 py-1 rounded-lg bg-status-success-bg text-status-success border border-status-success/30">
                {data.strong_count} Strong
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-status-caution-bg text-status-caution border border-status-caution/30">
                {data.partial_count} Partial
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-status-danger-bg text-status-danger border border-status-danger/30">
                {data.none_count} None
              </span>
            </div>
          </div>

          {/* Sub-Question Accordion List */}
          <div className="space-y-3">
            <h3 className="text-sm font-heading font-bold text-ink">
              Sub-Question Evidence Analysis
            </h3>

            {data.sub_questions.map((sq, idx) => {
              const covProps = getCoverageClassProps(sq.coverage_class);
              const isOpen = !!openAccordion[idx];

              return (
                <div
                  key={idx}
                  className="rounded-2xl border border-card-border bg-card shadow-xs overflow-hidden transition-all"
                >
                  {/* Accordion Header */}
                  <button
                    type="button"
                    onClick={() => toggleAccordion(idx)}
                    className="w-full p-4 flex items-center justify-between text-left hover:bg-canvas/50 transition-colors"
                  >
                    <div className="flex items-start space-x-3 pr-4">
                      <span className="px-2.5 py-1 text-[11px] font-mono font-bold rounded-md border shrink-0 mt-0.5"
                        style={{
                          backgroundColor:
                            sq.coverage_class === 'strong'
                              ? 'var(--color-status-success-bg)'
                              : sq.coverage_class === 'partial'
                              ? 'var(--color-status-caution-bg)'
                              : 'var(--color-status-danger-bg)',
                          color:
                            sq.coverage_class === 'strong'
                              ? 'var(--color-status-success)'
                              : sq.coverage_class === 'partial'
                              ? 'var(--color-status-caution)'
                              : 'var(--color-status-danger)',
                        }}
                      >
                        {covProps.label}
                      </span>
                      <div>
                        <h4 className="font-heading font-semibold text-xs sm:text-sm text-ink leading-snug">
                          {sq.sub_question}
                        </h4>
                        <div className="flex items-center space-x-3 mt-1 text-[11px] font-mono text-ink-subtle">
                          <span>Top Score: {sq.top_fused_score.toFixed(4)}</span>
                          <span>•</span>
                          <span>{sq.distinct_doc_count} Distinct Documents</span>
                          <span>•</span>
                          <span>{sq.evidence_count} Chunks</span>
                        </div>
                      </div>
                    </div>

                    <div className="text-ink-subtle shrink-0">
                      {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </div>
                  </button>

                  {/* Accordion Expanded Body */}
                  {isOpen && (
                    <div className="p-4 border-t border-card-border bg-canvas/40 space-y-3 animate-fade-in text-xs">
                      {/* Suggested Rephrase Box if Partial/None */}
                      {sq.suggested_rephrase && (
                        <div className="p-3.5 rounded-xl bg-status-caution-bg/40 border border-status-caution/30 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-mono font-bold text-status-caution uppercase tracking-wider">
                              Suggested Clinical Query Rephrase
                            </span>
                            <div className="flex items-center space-x-2">
                              <button
                                type="button"
                                onClick={() => handleCopyRephrase(sq.suggested_rephrase!, idx)}
                                className="inline-flex items-center space-x-1 px-2 py-1 rounded bg-card border border-card-border text-[11px] font-mono text-ink-muted hover:text-ink transition-colors shadow-2xs"
                              >
                                {copiedIndex === idx ? <Check className="w-3 h-3 text-status-success" /> : <Copy className="w-3 h-3" />}
                                <span>{copiedIndex === idx ? 'Copied' : 'Copy'}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => handleUseRephrase(sq.suggested_rephrase!)}
                                className="inline-flex items-center space-x-1 px-2 py-1 rounded bg-brand text-white text-[11px] font-heading font-semibold hover:bg-brand-hover transition-colors shadow-2xs"
                              >
                                <ArrowRight className="w-3 h-3" />
                                <span>Use this rephrase</span>
                              </button>
                            </div>
                          </div>
                          <p className="font-mono text-xs text-ink">
                            {sq.suggested_rephrase}
                          </p>
                        </div>
                      )}

                      {/* Top Citations Snippets */}
                      {sq.top_citations && sq.top_citations.length > 0 && (
                        <div className="space-y-1.5">
                          <span className="text-[10px] font-mono text-ink-subtle uppercase tracking-wider">
                            Top Evidence Sources:
                          </span>
                          {sq.top_citations.map((cite, cIdx) => (
                            <div
                              key={cIdx}
                              className="p-2.5 rounded-lg bg-card border border-card-border text-ink-muted text-xs leading-relaxed font-sans"
                            >
                              {cite}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Disclaimer */}
          <DisclaimerFooter />
        </div>
      )}
    </div>
  );
};
