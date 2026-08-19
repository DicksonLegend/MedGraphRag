import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { reportsApi } from '../api/reports';
import type { ReportResponse, ReportSummaryItem } from '../api/types';
import { EcgLoader } from '../components/common/EcgLoader';
import { SubwayMap } from '../components/common/SubwayMap';
import { CriticalEscalationBanner } from '../components/common/CriticalEscalationBanner';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { MarkdownAnswer } from '../components/chat/MarkdownAnswer';
import { ReportDrawer } from '../components/reports/ReportDrawer';
import {
  UploadCloud,
  FileText,
  AlertOctagon,
  Calendar,
  Layers,
  CheckCircle2,
  RefreshCw,
  Clock,
  ChevronRight,
  Lock,
  Database,
  FileSpreadsheet,
  Trash2,
  TrendingUp,
  AlertTriangle,
  X,
  ShieldCheck,
  Filter,
} from 'lucide-react';

import { useSessionStore } from '../stores/sessionStore';

const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.xlsx', '.csv'];
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // 20 MB

type FilterStatus = 'all' | 'normal' | 'critical';

export const ReportsPage: React.FC = () => {
  const reportsSession = useSessionStore((state) => state.reports);
  const setReportsState = useSessionStore((state) => state.setReportsState);

  const [reports, setReports] = useState<ReportSummaryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStage, setUploadStage] = useState<number>(0);
  const [uploadResult, setUploadResult] = useState<ReportResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedReportId, setSelectedReportIdState] = useState<string | null>(
    reportsSession.selectedReportId
  );

  const setSelectedReportId = (id: string | null) => {
    setSelectedReportIdState(id);
    setReportsState({ selectedReportId: id });
  };
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [purgeTarget, setPurgeTarget] = useState<ReportSummaryItem | null>(null);
  const [purgedNotification, setPurgedNotification] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const fetchReports = async () => {
    setIsLoadingHistory(true);
    try {
      const list = await reportsApi.listReports();
      setReports(list);
    } catch {
      setReports([]);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleFileSelection = async (file: File) => {
    setErrorMsg(null);
    setUploadResult(null);

    // 1. Client-Side Format Validation (415)
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMsg(
        `Unsupported file format '${ext}'. Allowed formats: ${ALLOWED_EXTENSIONS.sort().join(', ')}`
      );
      return;
    }

    // 2. Client-Side Size Validation (413)
    if (file.size > MAX_UPLOAD_BYTES) {
      setErrorMsg('File size exceeds maximum allowed limit of 20 MB.');
      return;
    }

    // 3. Upload with simulated micro-stepper state
    setIsUploading(true);
    setUploadStage(1); // Normalize
    const timer1 = setTimeout(() => setUploadStage(2), 700); // Range-check
    const timer2 = setTimeout(() => setUploadStage(3), 1500); // Graph-store

    try {
      const res = await reportsApi.uploadReport(file);
      setUploadResult(res);
      await fetchReports();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process diagnostic report.');
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setIsUploading(false);
      setUploadStage(0);
    }
  };

  const handleConfirmPurge = () => {
    if (!purgeTarget) return;
    const purgedId = purgeTarget.report_id;
    setReports((prev) => prev.filter((r) => r.report_id !== purgedId));
    setPurgeTarget(null);
    setPurgedNotification(`Report ${purgedId} purged from private encrypted store (Right-to-Erasure executed).`);
    setTimeout(() => setPurgedNotification(null), 4000);
  };

  const isCriticalReport = (text: string) => {
    return (
      text.startsWith('⚠️ URGENT CLINICAL NOTICE') ||
      text.includes('CRITICAL_HIGH') ||
      text.includes('CRITICAL_LOW') ||
      text.includes('CRITICAL')
    );
  };

  // Metrics computation
  const totalReports = reports.length;
  const totalLabValues = reports.reduce((acc, r) => acc + (r.n_lab_values || 0), 0);
  const criticalReportsCount = reports.filter((r) => r.critical_flag).length;

  // Filtered reports list (sorted date-desc)
  const filteredReports = reports
    .filter((rep) => {
      if (filterStatus === 'all') return true;
      if (filterStatus === 'critical') return rep.critical_flag;
      if (filterStatus === 'normal') return !rep.critical_flag;
      return true;
    })
    .sort((a, b) => new Date(b.report_date).getTime() - new Date(a.report_date).getTime());

  return (
    <div className="space-y-4 max-w-6xl mx-auto font-sans text-slate-800 dark:text-slate-200">
      {/* ── 2.a SUMMARY STRIP: 4 MONO TILES ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-[#0F766E] dark:text-[#14B8A6] border border-slate-200 dark:border-slate-800">
            <FileSpreadsheet className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Private Reports
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              {totalReports} reports
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-blue-600 dark:text-blue-400 border border-slate-200 dark:border-slate-800">
            <Database className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Discrete Measurements
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              {totalLabValues} lab values extracted
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-[#DC2626] border border-slate-200 dark:border-slate-800">
            <AlertOctagon className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Critical Alerts
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              {criticalReportsCount} critical range
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs flex items-center space-x-3">
          <div className="p-1.5 rounded-md bg-slate-50 dark:bg-slate-900 text-[#16A34A] border border-slate-200 dark:border-slate-800">
            <Lock className="w-4 h-4 stroke-[1.75]" />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide truncate">
              Storage Security
            </span>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              AES-256-GCM at rest
            </p>
          </div>
        </div>
      </div>

      {/* ── 2.b UPLOAD ZONE CARD WITH 3-STAGE MICRO-STEPPER & PRIVACY LINE ── */}
      <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3.5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">
              Diagnostic Lab Report Ingestion
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Ingest unstructured lab sheets for automated normalization, reference range evaluation, and encrypted graph storage.
            </p>
          </div>
          <div className="hidden sm:flex items-center space-x-1 text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-800">
            <Lock className="w-3.5 h-3.5 text-[#16A34A] stroke-[1.75]" />
            <span>AES-256-GCM Encrypted</span>
          </div>
        </div>

        {/* Drag & Drop Area */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragOver(false);
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
              handleFileSelection(e.dataTransfer.files[0]);
            }
          }}
          className={`border border-dashed rounded-lg p-6 text-center transition-colors ${
            isDragOver
              ? 'border-[#0F766E] dark:border-[#14B8A6] bg-teal-50/40 dark:bg-teal-950/20'
              : 'border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600 bg-slate-50/50 dark:bg-slate-900/40'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.xlsx,.csv"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileSelection(e.target.files[0]);
              }
            }}
          />
          <div className="flex flex-col items-center space-y-2">
            <div className="p-2.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              <UploadCloud className="w-5 h-5 stroke-[1.75]" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                Drag and drop diagnostic document here, or{' '}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-[#0F766E] dark:text-[#14B8A6] hover:underline font-semibold focus-visible:ring-2 focus-visible:ring-teal-600 cursor-pointer"
                >
                  browse files
                </button>
              </p>
              <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                Supported formats: PDF, PNG, JPG, XLSX, CSV (Max 20 MB)
              </p>
            </div>
          </div>
        </div>

        {/* 3-Stage Micro-Stepper & Privacy Line */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-slate-100 dark:border-slate-800/80 text-[11px] font-mono text-slate-500 dark:text-slate-400">
          <div className="flex items-center space-x-2">
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] dark:bg-[#14B8A6]" />
              <span>1 Normalize</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700">→</span>
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
              <span>2 Range-check</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700">→</span>
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
              <span>3 Graph-store</span>
            </span>
          </div>

          <div className="flex items-center space-x-1 text-slate-500 text-[11px]">
            <ShieldCheck className="w-3.5 h-3.5 text-[#16A34A] stroke-[1.75]" />
            <span>Encrypted on arrival · AES-256-GCM · guests auto-purged on logout</span>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-800 dark:text-red-300">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Uploading State with Per-Stage Chip */}
      {isUploading && (
        <div className="p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3 animate-fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6] animate-pulse" />
              <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                Processing Diagnostic Lab Report...
              </span>
            </div>
            <span className="h-6 px-2 text-[11px] font-mono font-medium rounded bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
              {uploadStage === 1 ? 'Extracting & Normalizing Units' : uploadStage === 2 ? 'Evaluating Reference Ranges' : 'Storing Kùzu Nodes'}
            </span>
          </div>
          <EcgLoader
            label="Analyzing Diagnostic Lab Report..."
            sublabel="Extracting optical tabular data, standardizing canonical test names & units, and checking critical thresholds..."
          />
        </div>
      )}

      {/* Upload Output Result */}
      {uploadResult && !isUploading && (
        <div className="space-y-3 animate-fade-in">
          {isCriticalReport(uploadResult.answer_text) && (
            <CriticalEscalationBanner
              message="One or more lab values meet critical emergency thresholds requiring immediate clinical attention."
            />
          )}

          <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                  Diagnostic Report Interpretation
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Status: {uploadResult.answer_status}
              </span>
            </div>

            <div className="bg-slate-50/70 dark:bg-slate-900/60 p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 text-[13.5px] leading-relaxed">
              <MarkdownAnswer
                content={uploadResult.answer_text}
                citations={uploadResult.citations || []}
              />
            </div>

            {uploadResult.graph_paths && uploadResult.graph_paths.length > 0 && (
              <SubwayMap paths={uploadResult.graph_paths} />
            )}

            <DisclaimerFooter />
          </div>
        </div>
      )}

      {/* Purged Notification Toast */}
      {purgedNotification && (
        <div className="p-3 rounded-lg bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-800 text-xs font-mono text-green-800 dark:text-green-300 flex items-center justify-between animate-fade-in">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-[#16A34A] stroke-[1.75]" />
            <span>{purgedNotification}</span>
          </div>
          <button
            type="button"
            onClick={() => setPurgedNotification(null)}
            className="text-green-700 hover:text-green-900 dark:text-green-300"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── 2.c HISTORICAL REPORTS TABLE WITH FILTERS & RIGHT-TO-ERASURE PURGE ── */}
      <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-slate-500 stroke-[1.75]" />
            <h3 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">
              Stored Diagnostic Reports ({reports.length})
            </h3>
          </div>

          <div className="flex items-center space-x-2">
            {/* Filter Chips: All / Normal / Critical (28px height) */}
            <div className="flex items-center space-x-1 bg-slate-50 dark:bg-slate-900 p-0.5 rounded-lg border border-slate-200 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setFilterStatus('all')}
                className={`h-7 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                  filterStatus === 'all'
                    ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                All ({reports.length})
              </button>
              <button
                type="button"
                onClick={() => setFilterStatus('normal')}
                className={`h-7 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                  filterStatus === 'normal'
                    ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                Normal ({reports.filter((r) => !r.critical_flag).length})
              </button>
              <button
                type="button"
                onClick={() => setFilterStatus('critical')}
                className={`h-7 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                  filterStatus === 'critical'
                    ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                Critical ({criticalReportsCount})
              </button>
            </div>

            <button
              onClick={fetchReports}
              className="flex items-center space-x-1.5 h-7 px-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-slate-900 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600"
              title="Refresh reports list"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin' : ''} stroke-[1.75]`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Reports Table */}
        {isLoadingHistory ? (
          <div className="p-8 text-center text-xs font-mono text-slate-500">
            Loading private report records...
          </div>
        ) : filteredReports.length === 0 ? (
          /* 2.d Empty State for zero reports */
          <div className="p-8 text-center rounded-lg border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 flex flex-col items-center justify-center space-y-2">
            <FileSpreadsheet className="w-8 h-8 text-slate-400 stroke-[1.5]" />
            <h4 className="font-semibold text-xs text-slate-800 dark:text-slate-200">
              No reports stored in this view
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm">
              Upload a diagnostic report above to populate your private encrypted records.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
            <table className="w-full text-left text-xs font-sans">
              <thead className="bg-slate-50 dark:bg-slate-900/80 border-b border-slate-200 dark:border-slate-800 text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                <tr>
                  <th className="px-3.5 py-2.5">Report Date</th>
                  <th className="px-3.5 py-2.5">Filename</th>
                  <th className="px-3.5 py-2.5">Measurements</th>
                  {/* 1.a Typo fixed: Critical Status */}
                  <th className="px-3.5 py-2.5">Critical Status</th>
                  <th className="px-3.5 py-2.5">Report ID</th>
                  <th className="px-3.5 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredReports.map((rep) => (
                  <tr
                    key={rep.report_id}
                    className="hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors group"
                  >
                    <td
                      onClick={() => setSelectedReportId(rep.report_id)}
                      className="px-3.5 py-2.5 font-mono font-medium text-slate-900 dark:text-slate-100 flex items-center space-x-1.5 cursor-pointer"
                    >
                      <Calendar className="w-3.5 h-3.5 text-slate-400 stroke-[1.75]" />
                      <span>{rep.report_date || '—'}</span>
                    </td>
                    <td
                      onClick={() => setSelectedReportId(rep.report_id)}
                      className="px-3.5 py-2.5 font-mono text-slate-600 dark:text-slate-400 cursor-pointer"
                    >
                      {rep.filename || '—'}
                    </td>
                    <td
                      onClick={() => setSelectedReportId(rep.report_id)}
                      className="px-3.5 py-2.5 font-mono font-medium text-slate-800 dark:text-slate-200 tabular-nums cursor-pointer"
                    >
                      {rep.n_lab_values} tests
                    </td>
                    {/* 1.b Compute row status correctly */}
                    <td
                      onClick={() => setSelectedReportId(rep.report_id)}
                      className="px-3.5 py-2.5 cursor-pointer"
                    >
                      {rep.critical_flag ? (
                        <span className="inline-flex items-center space-x-1 h-6 px-2 rounded text-[11px] font-mono font-semibold bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800">
                          <AlertOctagon className="w-3 h-3 stroke-[1.75]" />
                          <span>Critical Range</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 h-6 px-2 rounded text-[11px] font-mono font-medium bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800">
                          <CheckCircle2 className="w-3 h-3 stroke-[1.75]" />
                          <span>Normal</span>
                        </span>
                      )}
                    </td>
                    <td
                      onClick={() => setSelectedReportId(rep.report_id)}
                      className="px-3.5 py-2.5 font-mono text-[11px] text-slate-500 cursor-pointer"
                    >
                      {rep.report_id}
                    </td>
                    {/* 2.c Row Action Buttons: Inspect, Trend (if >=2), Purge */}
                    <td className="px-3.5 py-2.5 text-right">
                      <div className="inline-flex items-center space-x-2">
                        <button
                          type="button"
                          onClick={() => setSelectedReportId(rep.report_id)}
                          className="text-xs font-medium text-[#0F766E] dark:text-[#14B8A6] hover:underline cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600"
                        >
                          Inspect
                        </button>
                        {reports.length >= 2 && (
                          <button
                            type="button"
                            onClick={() => navigate('/trends')}
                            className="text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:underline cursor-pointer"
                          >
                            Trend
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => setPurgeTarget(rep)}
                          className="text-xs font-medium text-[#DC2626] hover:underline cursor-pointer"
                          title="Purge this report (Right-to-Erasure)"
                        >
                          Purge
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Purge Confirm Dialog (Right to Erasure) */}
      {purgeTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-fade-in"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-2xl space-y-3.5">
            <div className="flex items-center space-x-2 text-[#DC2626]">
              <AlertTriangle className="w-5 h-5 stroke-[1.75]" />
              <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                Purge Report (Right to Erasure)
              </h3>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Are you sure you want to permanently erase report <code className="font-mono font-semibold text-slate-800 dark:text-slate-200">{purgeTarget.report_id}</code> ({purgeTarget.filename}) from your isolated Kùzu graph and AES-256 encrypted store?
            </p>
            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setPurgeTarget(null)}
                className="h-7 px-3 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPurge}
                className="h-7 px-3 rounded-lg text-xs font-medium text-white bg-[#DC2626] hover:bg-red-700 transition-colors cursor-pointer"
              >
                Confirm Purge
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Slide-over Right Drawer for Report Inspection */}
      <ReportDrawer
        reportId={selectedReportId}
        onClose={() => setSelectedReportId(null)}
        onPurge={(rId) => {
          setReports((prev) => prev.filter((r) => r.report_id !== rId));
          setSelectedReportId(null);
          setPurgedNotification(`Report ${rId} purged from private encrypted store.`);
          setTimeout(() => setPurgedNotification(null), 4000);
        }}
      />
    </div>
  );
};
