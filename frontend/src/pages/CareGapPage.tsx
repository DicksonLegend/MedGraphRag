import React, { useState, useEffect } from 'react';
import { featuresApi } from '../api/features';
import type { CareGapResult, GapItem } from '../api/types';
import { EcgLoader } from '../components/common/EcgLoader';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import {
  ShieldAlert,
  AlertTriangle,
  Search,
  BookOpen,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  CheckCircle,
  Tag,
} from 'lucide-react';

export const CareGapPage: React.FC = () => {
  const [data, setData] = useState<CareGapResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<{ [key: string]: boolean }>({});

  const fetchCareGaps = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await featuresApi.getCareGaps();
      setData(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to evaluate clinical care gaps.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCareGaps();
  }, []);

  const toggleExpand = (id: string) => {
    setExpandedIndex((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const outOfTargetGaps = data?.gaps.filter((g) => g.gap_type === 'out_of_target') || [];
  const missingCheckGaps = data?.gaps.filter((g) => g.gap_type === 'missing_recommended_check') || [];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header Card */}
      <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-status-caution-bg text-status-caution border border-status-caution/30 shadow-xs">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink">
              CareGap Evidence-Based Guideline Reconciliation
            </h2>
          </div>
          <p className="text-xs text-ink-muted mt-1 font-sans">
            Reconciles your latest lab report against evidence-based clinical practice guidelines (ADA, NICE, KDIGO) to identify out-of-target values and missing recommended monitoring checks.
          </p>
        </div>

        <button
          onClick={fetchCareGaps}
          className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-card-border bg-canvas text-xs font-heading font-semibold text-ink-muted hover:text-ink transition-colors shadow-2xs self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Reconcile Guidelines</span>
        </button>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs">
          <EcgLoader
            label="Reconciling Against Clinical Practice Guidelines..."
            sublabel="Querying ADA, NICE, and KDIGO guideline documents, checking reference targets, and mapping recommended monitoring protocols..."
          />
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="CareGap Reconciliation Error"
          message={errorMsg}
          onRetry={fetchCareGaps}
        />
      )}

      {/* Main Content */}
      {data && !isLoading && (
        <>
          {/* Summary Overview Card */}
          <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-card-border">
              <h3 className="text-xs font-heading font-bold text-ink uppercase tracking-wider">
                Reconciliation Metrics
              </h3>
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-canvas text-ink border border-card-border">
                  Total Discrepancies: {data.total_gaps}
                </span>
                <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-status-danger-bg text-status-danger border border-status-danger/30">
                  Out of Target: {data.out_of_target_count}
                </span>
                <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-status-info-bg text-status-info border border-status-info/30">
                  Missing Checks: {data.missing_check_count}
                </span>
              </div>
            </div>
            <p className="text-xs text-ink leading-relaxed whitespace-pre-line font-sans">
              {data.summary_text}
            </p>
          </div>

          {/* If No Gaps Found */}
          {data.gaps.length === 0 ? (
            <EmptyState
              title="No Clinical Care Gaps Identified"
              description="Your latest diagnostic lab values align with guideline-recommended monitoring targets, or no reports have been uploaded yet."
              actionLabel="Upload Diagnostic Report"
              onAction={() => window.location.href = '/reports'}
            />
          ) : (
            <div className="space-y-8">
              {/* DECK 1: Out-of-Target Values (Red/Amber) */}
              {outOfTargetGaps.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 text-status-danger" />
                    <h3 className="text-sm font-heading font-extrabold text-ink uppercase tracking-wide">
                      Out-of-Target Lab Values ({outOfTargetGaps.length})
                    </h3>
                  </div>

                  <div className="grid grid-cols-1 gap-4">
                    {outOfTargetGaps.map((gap, idx) => {
                      const cardId = `out_${idx}`;
                      const isExpanded = !!expandedIndex[cardId];
                      return (
                        <div
                          key={cardId}
                          className="p-5 rounded-2xl border border-status-danger/30 bg-status-danger-bg/20 shadow-xs space-y-3"
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div>
                              <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-status-danger-bg text-status-danger rounded border border-status-danger/30 uppercase mr-2">
                                Out of Target
                              </span>
                              <strong className="font-heading text-sm text-ink font-bold">
                                {gap.recommended_check}
                              </strong>
                              <span className="text-xs text-ink-muted ml-2">
                                Context: {gap.condition_or_topic}
                              </span>
                            </div>
                            <div className="text-xs font-mono font-bold text-status-danger">
                              Observed: {gap.observed_value || '—'}
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-canvas/60 p-3 rounded-xl border border-card-border font-mono">
                            <div>
                              <span className="text-[10px] text-ink-subtle uppercase block">Guideline Target</span>
                              <span className="font-semibold text-ink">{gap.guideline_target}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-ink-subtle uppercase block">Status</span>
                              <span className="font-semibold text-status-danger">{gap.status}</span>
                            </div>
                          </div>

                          <p className="text-xs text-ink font-sans leading-relaxed">
                            💡 <strong>Clinical Framing:</strong> {gap.recommendation_text}
                          </p>

                          {/* Expandable Guideline Evidence */}
                          {gap.guideline_provenance && gap.guideline_provenance.length > 0 && (
                            <div className="pt-1">
                              <button
                                onClick={() => toggleExpand(cardId)}
                                className="flex items-center space-x-1.5 text-xs font-mono text-brand hover:underline"
                              >
                                <BookOpen className="w-3.5 h-3.5" />
                                <span>
                                  {isExpanded ? 'Hide Guideline Citations' : `View Guideline Citations (${gap.guideline_provenance.length})`}
                                </span>
                                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              </button>

                              {isExpanded && (
                                <div className="mt-2 space-y-2 animate-fade-in">
                                  {gap.guideline_provenance.map((cit, cIdx) => (
                                    <div
                                      key={cIdx}
                                      className="p-3 rounded-xl bg-canvas border border-card-border text-xs space-y-1"
                                    >
                                      <div className="flex items-center justify-between text-[11px] font-mono text-ink-subtle">
                                        <span className="truncate">{cit.document_id}</span>
                                        {cit.fused_score != null && (
                                          <span className="font-bold text-ink">Score: {cit.fused_score.toFixed(4)}</span>
                                        )}
                                      </div>
                                      <p className="text-ink text-xs font-sans leading-relaxed italic">
                                        "{cit.snippet}"
                                      </p>
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
                </div>
              )}

              {/* DECK 2: Missing Recommended Checks (Blue/Slate) */}
              {missingCheckGaps.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center space-x-2">
                    <Search className="w-4 h-4 text-status-info" />
                    <h3 className="text-sm font-heading font-extrabold text-ink uppercase tracking-wide">
                      Missing Recommended Checks ({missingCheckGaps.length})
                    </h3>
                  </div>

                  <div className="grid grid-cols-1 gap-4">
                    {missingCheckGaps.map((gap, idx) => {
                      const cardId = `miss_${idx}`;
                      const isExpanded = !!expandedIndex[cardId];
                      return (
                        <div
                          key={cardId}
                          className="p-5 rounded-2xl border border-status-info/30 bg-status-info-bg/20 shadow-xs space-y-3"
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div>
                              <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-status-info-bg text-status-info rounded border border-status-info/30 uppercase mr-2">
                                Missing Check
                              </span>
                              <strong className="font-heading text-sm text-ink font-bold">
                                {gap.recommended_check}
                              </strong>
                              <span className="text-xs text-ink-muted ml-2">
                                Condition: {gap.condition_or_topic}
                              </span>
                            </div>
                            <div className="text-xs font-mono text-ink-subtle italic">
                              Observed: Not tested
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-canvas/60 p-3 rounded-xl border border-card-border font-mono">
                            <div>
                              <span className="text-[10px] text-ink-subtle uppercase block">Recommended Guideline Schedule</span>
                              <span className="font-semibold text-ink">{gap.guideline_target}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-ink-subtle uppercase block">Reconciliation Note</span>
                              <span className="font-semibold text-ink-muted">{gap.status}</span>
                            </div>
                          </div>

                          <p className="text-xs text-ink font-sans leading-relaxed">
                            💡 <strong>Clinical Framing:</strong> {gap.recommendation_text}
                          </p>

                          {/* Expandable Guideline Evidence */}
                          {gap.guideline_provenance && gap.guideline_provenance.length > 0 && (
                            <div className="pt-1">
                              <button
                                onClick={() => toggleExpand(cardId)}
                                className="flex items-center space-x-1.5 text-xs font-mono text-brand hover:underline"
                              >
                                <BookOpen className="w-3.5 h-3.5" />
                                <span>
                                  {isExpanded ? 'Hide Guideline Citations' : `View Guideline Citations (${gap.guideline_provenance.length})`}
                                </span>
                                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              </button>

                              {isExpanded && (
                                <div className="mt-2 space-y-2 animate-fade-in">
                                  {gap.guideline_provenance.map((cit, cIdx) => (
                                    <div
                                      key={cIdx}
                                      className="p-3 rounded-xl bg-canvas border border-card-border text-xs space-y-1"
                                    >
                                      <div className="flex items-center justify-between text-[11px] font-mono text-ink-subtle">
                                        <span className="truncate">{cit.document_id}</span>
                                        {cit.fused_score != null && (
                                          <span className="font-bold text-ink">Score: {cit.fused_score.toFixed(4)}</span>
                                        )}
                                      </div>
                                      <p className="text-ink text-xs font-sans leading-relaxed italic">
                                        "{cit.snippet}"
                                      </p>
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
                </div>
              )}
            </div>
          )}

          {/* Disclaimer */}
          <DisclaimerFooter />
        </>
      )}
    </div>
  );
};
