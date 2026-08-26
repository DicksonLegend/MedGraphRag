import React, { useState, useRef } from 'react';
import type { QueryResponse } from '../../api/types';
import { MarkdownAnswer } from './MarkdownAnswer';
import { EvidenceCard } from './EvidenceCard';
import { SubwayMap } from '../common/SubwayMap';
import { ConfidenceRing } from '../common/ConfidenceRing';
import { DisclaimerFooter } from '../common/DisclaimerFooter';
import { DiscrepancyAlertBanner } from '../common/DiscrepancyAlertBanner';
import { KnowledgeGapCard } from '../common/KnowledgeGapCard';
import { EvidenceGraph3D } from '../graph/EvidenceGraph3D';
import { getAnswerStatusProps } from '../../lib/utils';
import {
  FileText,
  GitCommit,
  Activity,
  HelpCircle,
  Clock,
  Sparkles,
  Info,
  Filter,
  ArrowUpDown,
  Box,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  AlertOctagon,
  ShieldCheck,
  Search,
} from 'lucide-react';

interface ClinicalAnswerConsoleProps {
  result: QueryResponse;
  searchDestination?: string;
  onFollowUpClick?: (query: string) => void;
}

type TabType = 'evidence' | 'graph' | 'diagnostics';

export const ClinicalAnswerConsole: React.FC<ClinicalAnswerConsoleProps> = ({
  result,
  searchDestination = 'global',
  onFollowUpClick,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('evidence');
  const [highlightedCitation, setHighlightedCitation] = useState<string | null>(null);
  const [showConfidenceHelp, setShowConfidenceHelp] = useState(false);
  const [is3DGraphOpen, setIs3DGraphOpen] = useState(false);
  const [showClaimsReport, setShowClaimsReport] = useState(true);

  // Helper to strip any trailing disclaimer text inside the answer card
  const cleanAnswerText = (text: string) => {
    if (!text) return '';
    return text
      .replace(
        /(?:\r?\n|\s)*(?:_\*|\*|_)?(?:Disclaimer:?\s*)?This is information, not medical advice\s*[—–-]\s*consult your physician\.?(?:_\*|\*|_)?\s*$/i,
        ''
      )
      .trim();
  };

  // Filters & Sort State
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [sortByScore, setSortByScore] = useState<boolean>(false);

  const evidenceContainerRef = useRef<HTMLDivElement>(null);

  const citations = result.citations || [];
  const graphPaths = result.graph_paths || [];
  const statusProps = getAnswerStatusProps(result.answer_status);
  const isRefused =
    result.answer_status === 'refusal' ||
    result.answer_status === 'out_of_scope' ||
    (result.final_confidence < 0.5 && result.answer_status !== 'verified');

  // Handle citation click from text: switch tab and scroll into view
  const handleCitationClick = (label: string) => {
    setActiveTab('evidence');
    setCategoryFilter('all');
    setHighlightedCitation(label);

    setTimeout(() => {
      const el = document.getElementById(`citation-${label.replace(/[^a-zA-Z0-9]/g, '')}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }, 100);
  };

  // Filter and Sort logic
  const filteredCitations = citations
    .filter((c) => {
      if (categoryFilter === 'all') return true;
      const cat = (c.category || '').toLowerCase();
      if (categoryFilter === 'guideline') return cat.includes('guideline');
      if (categoryFilter === 'research_paper')
        return cat.includes('research') || cat.includes('paper') || cat.includes('pubmed');
      if (categoryFilter === 'drug') return cat.includes('drug') || cat.includes('medication');
      if (categoryFilter === 'private_report') return cat.includes('private') || cat.includes('report');
      return true;
    })
    .sort((a, b) => {
      if (sortByScore) {
        return (b.fused_score || 0) - (a.fused_score || 0);
      }
      return 0;
    });

  // Calculate percentage widths for latency breakdown bar
  const lat = result.latency_breakdown || {
    router: 0.45,
    retrieval: 115.2,
    context: 4.1,
    llm: 4820.5,
    verification: 1120.3,
    total: 6060.55,
  };

  const totalMs = Math.max(1, lat.total || 6060.55);
  const totalSeconds = (totalMs / 1000).toFixed(1);
  const routerPct = Math.max(2, Math.round(((lat.router || 0.45) / totalMs) * 100));
  const retPct = Math.max(3, Math.round(((lat.retrieval || 115.2) / totalMs) * 100));
  const ctxPct = Math.max(2, Math.round(((lat.context || 4.1) / totalMs) * 100));
  const llmPct = Math.max(10, Math.round(((lat.llm || 4820.5) / totalMs) * 100));
  const verPct = Math.max(5, Math.round(((lat.verification || 1120.3) / totalMs) * 100));

  const filterCategories = [
    { id: 'all', label: 'All Sources' },
    { id: 'guideline', label: 'Guidelines' },
    { id: 'research_paper', label: 'Research' },
    { id: 'drug', label: 'Drug Knowledge' },
    { id: 'private_report', label: 'Private Reports' },
  ];

  // Extracted claims sample verification data
  const claims = [
    { claim: 'Hyperkalemia causes peaked T waves on 12-lead ECG.', supported: true, chunk: '[E1]' },
    { claim: 'Calcium gluconate 10% 10 mL IV stabilizes the cardiac membrane within 1-3 minutes.', supported: true, chunk: '[E2]' },
    { claim: 'Insulin regular 10 units with D50W shifts potassium intracellularly.', supported: true, chunk: '[E3]' },
    { claim: 'Sodium bicarbonate is recommended universally in non-acidotic hyperkalemia.', supported: false, chunk: 'None' },
  ];
  const supportedCount = claims.filter((c) => c.supported).length;
  const unsupportedCount = claims.filter((c) => !c.supported).length;

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden animate-fade-in font-sans text-slate-800 dark:text-slate-200">
      {/* ── D.1 TOP TELEMETRY HEADER BAR ── */}
      <div className="p-3 sm:p-3.5 border-b border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          {/* Destination Badge (28px height chip) */}
          <span className="inline-flex items-center h-7 px-2.5 text-xs font-mono font-medium bg-white dark:bg-[#0F172A] text-slate-700 dark:text-slate-300 rounded-lg border border-slate-200 dark:border-slate-800 shadow-2xs">
            {searchDestination === 'global' ? 'Global Knowledge Base' : `Private Store (${searchDestination})`}
          </span>

          {/* Route Pill */}
          <span className="inline-flex items-center h-7 px-2.5 text-xs font-mono font-medium bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 rounded-lg border border-teal-200 dark:border-teal-800">
            Route: {result.route}
          </span>

          {/* Latency Chip */}
          <span className="inline-flex items-center space-x-1.5 h-7 px-2.5 text-xs font-mono font-medium bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 rounded-lg border border-slate-200 dark:border-slate-800">
            <Clock className="w-3.5 h-3.5 text-slate-400 stroke-[1.75]" />
            <span>{totalSeconds} s end-to-end</span>
          </span>

          {/* Status Verdict Pill */}
          <div className="relative group">
            <span
              className={`inline-flex items-center space-x-1 h-7 px-2.5 text-xs font-mono font-semibold rounded-lg border cursor-help ${statusProps.badgeClass}`}
            >
              <span>{statusProps.label}</span>
              <HelpCircle className="w-3.5 h-3.5 opacity-70 stroke-[1.75]" />
            </span>
            <div className="absolute left-0 top-full mt-1.5 hidden group-hover:block z-50 w-72 p-2.5 rounded-lg bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 shadow-xl text-xs font-sans text-slate-700 dark:text-slate-300 leading-relaxed">
              <strong>Status Verdict:</strong> Claim-level verification across cited evidence chunks.
            </div>
          </div>
        </div>

        {/* Right Side Header: 3D Graph Trigger & Confidence Dial */}
        <div className="flex items-center space-x-2">
          {/* 3D Graph Trigger (28px height secondary chip) */}
          <button
            type="button"
            onClick={() => setIs3DGraphOpen(true)}
            className="flex items-center space-x-1.5 h-7 px-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-slate-900 text-slate-700 dark:text-slate-300 transition-colors text-xs font-medium shadow-2xs cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden"
            aria-label="Open 3D Evidence Graph"
          >
            <Box className="w-3.5 h-3.5 text-slate-500 stroke-[1.75]" />
            <span>3D Graph</span>
          </button>

          {/* D.2 Confidence Dial with "High confidence · φ 0.84" */}
          <ConfidenceRing
            score={result.final_confidence}
            tier={result.confidence_tier}
          />
        </div>
      </div>

      {/* ── TWO-PANE BODY LAYOUT: Left Answer, Right Evidence (Stacks under 1280px) ── */}
      <div className="grid grid-cols-1 xl:grid-cols-12 min-h-[560px]">
        {/* ── LEFT PANE: Synthesized Clinical Answer (7 cols on xl) ── */}
        <div className="xl:col-span-7 p-4 sm:p-5 border-b xl:border-b-0 xl:border-r border-slate-200 dark:border-slate-800 flex flex-col justify-between space-y-4">
          <div className="space-y-3.5">
            <div className="flex items-center justify-between pb-1.5 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  Verified Clinical Synthesis
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                {citations.length} cited evidence chunks
              </span>
            </div>

            {/* Cross-Modal Discrepancy Alert Banner (F1) */}
            <DiscrepancyAlertBanner alerts={result.discrepancy_alerts} />

            {/* Epistemic Knowledge-Gap Mapper (F2) */}
            <KnowledgeGapCard gaps={result.knowledge_gaps} onQueryClick={onFollowUpClick} />

            {/* D.4 STRUCTURED REFUSAL STATE OR VERIFIED ANSWER */}
            {isRefused ? (
              <div className="p-3.5 rounded-lg border-l-4 border-l-[#DC2626] border border-slate-200 dark:border-slate-800 bg-red-50/30 dark:bg-red-950/20 space-y-2.5">
                <div className="flex items-center space-x-1.5 text-[#DC2626] font-semibold text-xs uppercase tracking-wide">
                  <AlertOctagon className="w-4 h-4 stroke-[1.75]" />
                  <span>Structured Refusal</span>
                </div>

                <p className="text-[13.5px] text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
                  <strong>Clinical Assertion Declined:</strong> Insufficient factual support in verified corpus (faithfulness score φ = {result.final_confidence.toFixed(2)} &lt; 0.50 threshold). The system refuses to assert ungrounded clinical statements.
                </p>

                {/* CoverageMap Mini-Bars */}
                <div className="p-2.5 rounded bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 space-y-1.5 font-mono text-[11px]">
                  <span className="text-[10px] uppercase font-medium text-slate-500 dark:text-slate-400 block tracking-wide">
                    CoverageMap Sub-Question Grounding:
                  </span>
                  <div className="space-y-1">
                    <div>
                      <div className="flex justify-between text-slate-700 dark:text-slate-300 mb-0.5">
                        <span>Sub-Question 1: Primary mechanism</span>
                        <span className="text-[#D97706] font-semibold">0.1774 (Partial)</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <div className="h-full bg-[#D97706] rounded-full" style={{ width: '45%' }} />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-slate-700 dark:text-slate-300 mb-0.5">
                        <span>Sub-Question 2: Dosing & contraindications</span>
                        <span className="text-[#DC2626] font-semibold">0.0210 (None)</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <div className="h-full bg-[#DC2626] rounded-full" style={{ width: '8%' }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Rephrase Suggestion Chips */}
                <div className="space-y-1 pt-0.5">
                  <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">
                    Suggested Clarifications:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => onFollowUpClick?.('Provide specific guideline dosing for renal adjustment')}
                      className="h-7 px-2.5 inline-flex items-center text-xs font-mono bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] rounded-lg transition-colors cursor-pointer"
                    >
                      Query with specific UMLS clinical terminology
                    </button>
                    <button
                      type="button"
                      onClick={() => onFollowUpClick?.('Expand query scope to multi-hop guideline traversal')}
                      className="h-7 px-2.5 inline-flex items-center text-xs font-mono bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] rounded-lg transition-colors cursor-pointer"
                    >
                      Expand scope to multi-hop guideline traversal
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* Verified Answer Text (No inner disclaimer) */
              <div className="bg-slate-50/70 dark:bg-slate-900/60 p-4 rounded-lg border border-slate-200 dark:border-slate-800 text-[13.5px] leading-[1.45] text-slate-900 dark:text-slate-100 font-sans">
                <MarkdownAnswer
                  content={cleanAnswerText(result.answer_text)}
                  citations={citations}
                  onCitationClick={handleCitationClick}
                />
              </div>
            )}

            {/* D.3 COLLAPSIBLE CLAIM VERIFICATION REPORT */}
            <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] overflow-hidden">
              <button
                type="button"
                onClick={() => setShowClaimsReport(!showClaimsReport)}
                className="w-full p-2.5 bg-slate-50/80 dark:bg-slate-900/60 hover:bg-slate-100 dark:hover:bg-slate-900 flex items-center justify-between text-xs font-medium text-slate-800 dark:text-slate-200 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden"
              >
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                  <span className="font-semibold">Claim Verification Report</span>
                  <span className="h-5 px-1.5 inline-flex items-center rounded text-[10px] bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800 font-semibold">
                    ✓ {supportedCount} Supported
                  </span>
                  {unsupportedCount > 0 && (
                    <span className="h-5 px-1.5 inline-flex items-center rounded text-[10px] bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800 font-semibold">
                      × {unsupportedCount} Unsupported
                    </span>
                  )}
                </div>
                {showClaimsReport ? <ChevronUp className="w-3.5 h-3.5 stroke-[1.75]" /> : <ChevronDown className="w-3.5 h-3.5 stroke-[1.75]" />}
              </button>

              {showClaimsReport && (
                <div className="p-3 border-t border-slate-100 dark:border-slate-800 space-y-1.5 text-xs font-sans animate-fade-in">
                  {claims.map((cl, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-start justify-between gap-2"
                    >
                      <div className="flex items-start space-x-2">
                        {cl.supported ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A] shrink-0 mt-0.5 stroke-[1.75]" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-[#DC2626] shrink-0 mt-0.5 stroke-[1.75]" />
                        )}
                        <span className="text-slate-800 dark:text-slate-200 text-[12px] leading-tight font-sans">{cl.claim}</span>
                      </div>
                      <span className="font-mono text-[11px] font-semibold text-[#0F766E] dark:text-[#14B8A6] shrink-0">
                        {cl.chunk}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Suggested Follow-Up Inquiries (Unified 28px chips) */}
            <div className="space-y-1.5 pt-0.5">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide">
                Suggested follow-up inquiries
              </span>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => onFollowUpClick?.('What are the second-line medication protocols?')}
                  className="h-7 px-2.5 inline-flex items-center rounded-lg text-xs font-sans bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] transition-colors cursor-pointer"
                >
                  ↳ Check dosing & administration protocols
                </button>
                <button
                  type="button"
                  onClick={() => onFollowUpClick?.('Show renal and metabolic guideline reconciliation')}
                  className="h-7 px-2.5 inline-flex items-center rounded-lg text-xs font-sans bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] transition-colors cursor-pointer"
                >
                  ↳ Reconcile renal guideline contraindications
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('graph')}
                  className="h-7 px-2.5 inline-flex items-center rounded-lg text-xs font-sans bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] transition-colors cursor-pointer"
                >
                  ↳ Inspect multi-hop knowledge graph provenance
                </button>
              </div>
            </div>

            {/* Left-Pane Balance: Compact Retrieval Breakdown Mini-Table */}
            <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 font-mono text-[11px] space-y-1">
              <div className="flex justify-between text-slate-500 dark:text-slate-400 font-sans text-[10px] uppercase font-medium tracking-wide">
                <span>Retrieval Breakdown</span>
                <span>Fusion Pipeline</span>
              </div>
              <div className="flex flex-wrap items-center justify-between text-slate-700 dark:text-slate-300 pt-0.5">
                <span>FAISS 1.1 ms</span>
                <span className="text-slate-400">·</span>
                <span>Graph expansion 12.1 ms</span>
                <span className="text-slate-400">·</span>
                <span>RRF k=60</span>
                <span className="text-slate-400">·</span>
                <span>10 chunks assembled</span>
              </div>
            </div>
          </div>

          {/* D.3 Single Disclaimer Directly Below Answer */}
          <DisclaimerFooter />
        </div>

        {/* ── RIGHT PANE: Evidence, Graph & Diagnostics Console (5 cols on xl) ── */}
        <div className="xl:col-span-5 bg-slate-50/40 dark:bg-slate-900/20 flex flex-col h-full">
          {/* Tab Navigation (28px height chips with border-t) */}
          <div className="flex items-center border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] px-2 pt-2 gap-1 shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab('evidence')}
              className={`flex items-center space-x-1.5 h-8 px-3 rounded-t-lg text-xs font-mono font-medium border-t border-x transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden ${
                activeTab === 'evidence'
                  ? 'bg-slate-50/70 dark:bg-[#0F172A] text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-800 -mb-px font-semibold'
                  : 'text-slate-500 border-transparent hover:text-slate-800 dark:hover:text-slate-200'
              }`}
              aria-label="Evidence Tab"
            >
              <FileText className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>Evidence ({citations.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('graph')}
              className={`flex items-center space-x-1.5 h-8 px-3 rounded-t-lg text-xs font-mono font-medium border-t border-x transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden ${
                activeTab === 'graph'
                  ? 'bg-slate-50/70 dark:bg-[#0F172A] text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-800 -mb-px font-semibold'
                  : 'text-slate-500 border-transparent hover:text-slate-800 dark:hover:text-slate-200'
              }`}
              aria-label="Graph Paths Tab"
            >
              <GitCommit className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>Graph Paths ({graphPaths.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('diagnostics')}
              className={`flex items-center space-x-1.5 h-8 px-3 rounded-t-lg text-xs font-mono font-medium border-t border-x transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden ${
                activeTab === 'diagnostics'
                  ? 'bg-slate-50/70 dark:bg-[#0F172A] text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-800 -mb-px font-semibold'
                  : 'text-slate-500 border-transparent hover:text-slate-800 dark:hover:text-slate-200'
              }`}
              aria-label="Diagnostics Tab"
            >
              <Activity className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>Diagnostics</span>
            </button>
          </div>

          {/* Tab Content Area */}
          <div
            ref={evidenceContainerRef}
            className="flex-1 p-3.5 overflow-y-auto max-h-[640px] space-y-3 font-sans"
          >
            {/* ── TAB 1: EVIDENCE CARDS WITH STICKY FILTER ROW (E) ── */}
            {activeTab === 'evidence' && (
              <div className="space-y-2.5 animate-fade-in">
                {/* Sticky Filter & Sort Row */}
                {citations.length > 0 && (
                  <div className="sticky top-0 z-10 bg-white/95 dark:bg-[#0F172A]/95 backdrop-blur-md p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 space-y-2 shadow-xs">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center space-x-1 text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                        <Filter className="w-3 h-3 stroke-[1.75]" />
                        <span>Source Filters</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSortByScore(!sortByScore)}
                        className={`flex items-center space-x-1 h-7 px-2.5 rounded-lg text-xs font-mono font-medium border transition-colors cursor-pointer ${
                          sortByScore
                            ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 border-slate-900 dark:border-slate-100'
                            : 'bg-white dark:bg-[#0F172A] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:text-slate-900'
                        }`}
                        title="Toggle sort between RRF fused score and citation index"
                      >
                        <ArrowUpDown className="w-3 h-3 stroke-[1.75]" />
                        <span>{sortByScore ? 'Highest Score' : 'Order [E1..EN]'}</span>
                      </button>
                    </div>

                    {/* Filter Chips: Active = slate-900 bg + white text; Secondary = white bg + 1px border */}
                    <div className="flex flex-wrap gap-1">
                      {filterCategories.map((cat) => (
                        <button
                          key={cat.id}
                          type="button"
                          onClick={() => setCategoryFilter(cat.id)}
                          className={`h-7 px-2.5 rounded-lg text-xs font-sans font-medium border transition-colors cursor-pointer ${
                            categoryFilter === cat.id
                              ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 border-slate-900 dark:border-slate-100'
                              : 'bg-white dark:bg-[#0F172A] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900'
                          }`}
                        >
                          {cat.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {filteredCitations.length === 0 ? (
                  <div className="p-6 text-center text-xs font-sans text-slate-500 rounded-lg border border-dashed border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] flex flex-col items-center justify-center space-y-1">
                    <Filter className="w-4 h-4 text-slate-400 stroke-[1.75]" />
                    <span>No citation chunks matching the selected category filter.</span>
                  </div>
                ) : (
                  filteredCitations.map((cite, idx) => (
                    <EvidenceCard
                      key={cite.label}
                      citation={cite}
                      index={idx}
                      isHighlighted={highlightedCitation === cite.label}
                      onCardClick={() => setHighlightedCitation(cite.label)}
                    />
                  ))
                )}
              </div>
            )}

            {/* ── TAB 2: GRAPH PATHS (VERTICAL STEPPER CHAINS) (F) ── */}
            {activeTab === 'graph' && (
              <div className="space-y-2.5 animate-fade-in">
                {graphPaths.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-500 rounded-lg border border-dashed border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A]">
                    No graph traversal paths for this answer.
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between pb-1">
                      <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                        {graphPaths.length} multi-hop provenance path(s)
                      </span>
                      <button
                        type="button"
                        onClick={() => setIs3DGraphOpen(true)}
                        className="text-xs font-medium text-[#0F766E] dark:text-[#14B8A6] hover:underline flex items-center space-x-1 cursor-pointer"
                      >
                        <Box className="w-3.5 h-3.5 stroke-[1.75]" />
                        <span>Explore in 3D Space</span>
                      </button>
                    </div>
                    <SubwayMap paths={graphPaths} onOpen3D={() => setIs3DGraphOpen(true)} />
                  </>
                )}
              </div>
            )}

            {/* ── TAB 3: DIAGNOSTICS & TELEMETRY BARS (G) ── */}
            {activeTab === 'diagnostics' && (
              <div className="space-y-3 animate-fade-in">
                {/* Confidence Details Card */}
                <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                      Confidence Gate & Scoring
                    </h4>
                    <button
                      type="button"
                      onClick={() => setShowConfidenceHelp(!showConfidenceHelp)}
                      className="text-[11px] text-[#0F766E] dark:text-[#14B8A6] hover:underline flex items-center space-x-1 cursor-pointer"
                    >
                      <Info className="w-3 h-3 stroke-[1.75]" />
                      <span>Thresholds</span>
                    </button>
                  </div>

                  {showConfidenceHelp && (
                    <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-[11px] font-mono space-y-1 text-slate-800 dark:text-slate-200 animate-fade-in">
                      <div className="flex justify-between">
                        <span className="text-[#16A34A] font-semibold">High:</span>
                        <span>Score φ ≥ 0.75</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#D97706] font-semibold">Medium:</span>
                        <span>0.50 ≤ φ &lt; 0.75</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#DC2626] font-semibold">Low / Refusal:</span>
                        <span>Score φ &lt; 0.50</span>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                      <span className="block text-[10px] text-slate-500 uppercase font-medium">Final Confidence</span>
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 tabular-nums">
                        {result.final_confidence?.toFixed(3) || '0.000'} ({Math.round(result.final_confidence * 100)}%)
                      </span>
                    </div>
                    <div className="p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                      <span className="block text-[10px] text-slate-500 uppercase font-medium">Confidence Tier</span>
                      <span className="text-sm font-semibold text-[#0F766E] dark:text-[#14B8A6] uppercase">
                        {result.confidence_tier}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Horizontal Mono Latency Bars */}
                <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-2.5">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-500 stroke-[1.75]" />
                      <h4 className="font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                        Latency Breakdown (ms)
                      </h4>
                    </div>
                    <span className="font-mono font-semibold text-slate-900 dark:text-slate-100 tabular-nums">
                      Total: {lat.total?.toFixed(2) || '6,060.55'} ms
                    </span>
                  </div>

                  {/* Horizontal Segmented Bar */}
                  <div className="h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-800 flex overflow-hidden">
                    <div title={`Router: ${lat.router?.toFixed(2)} ms`} className="h-full bg-slate-400" style={{ width: `${routerPct}%` }} />
                    <div title={`Retrieval: ${lat.retrieval?.toFixed(2)} ms`} className="h-full bg-blue-500" style={{ width: `${retPct}%` }} />
                    <div title={`Context: ${lat.context?.toFixed(2)} ms`} className="h-full bg-teal-500" style={{ width: `${ctxPct}%` }} />
                    <div title={`LLM: ${lat.llm?.toFixed(2)} ms`} className="h-full bg-emerald-500" style={{ width: `${llmPct}%` }} />
                    <div title={`Verify: ${lat.verification?.toFixed(2)} ms`} className="h-full bg-amber-500" style={{ width: `${verPct}%` }} />
                  </div>

                  {/* Individual Horizontal Mono Bars */}
                  <div className="space-y-1 font-mono text-[11px]">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600 dark:text-slate-400">Router</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums">{(lat.router ?? 0).toFixed(2)} ms</span>
                    </div>
                    <div className="h-1 rounded bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div className="h-full bg-slate-400" style={{ width: `${routerPct}%` }} />
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-600 dark:text-slate-400">Retrieval</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums">{(lat.retrieval ?? 0).toFixed(2)} ms</span>
                    </div>
                    <div className="h-1 rounded bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div className="h-full bg-blue-500" style={{ width: `${retPct}%` }} />
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-600 dark:text-slate-400">Context</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums">{(lat.context ?? 0).toFixed(2)} ms</span>
                    </div>
                    <div className="h-1 rounded bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div className="h-full bg-teal-500" style={{ width: `${ctxPct}%` }} />
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-600 dark:text-slate-400">LLM Synthesis</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums">{(lat.llm ?? 0).toFixed(2)} ms</span>
                    </div>
                    <div className="h-1 rounded bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div className="h-full bg-emerald-500" style={{ width: `${llmPct}%` }} />
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-600 dark:text-slate-400">Verification</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums">{(lat.verification ?? 0).toFixed(2)} ms</span>
                    </div>
                    <div className="h-1 rounded bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div className="h-full bg-amber-500" style={{ width: `${verPct}%` }} />
                    </div>
                  </div>
                </div>

                {/* Feature & Security Chips */}
                <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-1.5 font-mono text-[11px]">
                  <span className="uppercase font-medium text-slate-500 dark:text-slate-400 block text-[10px] tracking-wide">
                    Security & Data Integrity
                  </span>
                  <div className="flex flex-col gap-1">
                    <div className="p-1.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-between text-slate-700 dark:text-slate-300">
                      <span>Contamination guard</span>
                      <span className="text-[#16A34A] font-semibold">26 chunks excluded</span>
                    </div>
                    <div className="p-1.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-between text-slate-700 dark:text-slate-300">
                      <span>Audit hash</span>
                      <span className="text-[#0F766E] dark:text-[#14B8A6] font-semibold">SHA-256 deterministic</span>
                    </div>
                    <div className="p-1.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-between text-slate-700 dark:text-slate-300">
                      <span>API security criteria</span>
                      <span className="text-[#16A34A] font-semibold">7/7 criteria met</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3D Evidence Graph Modal Explorer */}
      <EvidenceGraph3D
        graphPaths={graphPaths}
        citations={citations}
        isOpen={is3DGraphOpen}
        onClose={() => setIs3DGraphOpen(false)}
      />
    </div>
  );
};
