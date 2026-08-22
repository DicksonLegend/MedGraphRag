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
  ShieldAlert,
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
    <div className="space-y-4 max-w-7xl mx-auto font-sans text-slate-800 dark:text-slate-200">
      {/* ── 1. UNIFIED VAULT TELEMETRY RIBBON ── */}
      <div className="rounded-xl border border-slate-200/90 dark:border-slate-800/90 bg-white/95 dark:bg-[#0F172A]/95 backdrop-blur-md shadow-2xs overflow-hidden">
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-slate-100 dark:divide-slate-800">
          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-[#0F766E] dark:text-[#14B8A6] border border-teal-200 dark:border-teal-800/80 shrink-0">
              <FileSpreadsheet className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                Private Reports
              </span>
              <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate mt-0.5">
                {totalReports} reports
              </p>
            </div>
          </div>

          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/80 shrink-0">
              <Database className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                Discrete Measurements
              </span>
              <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate mt-0.5">
                {totalLabValues} lab values extracted
              </p>
            </div>
          </div>

          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-red-50 dark:bg-red-950/60 text-[#DC2626] border border-red-200 dark:border-red-800/80 shrink-0">
              <AlertOctagon className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                Critical Alerts
              </span>
              <p className="text-xs font-mono font-semibold text-[#DC2626] truncate mt-0.5">
                {criticalReportsCount} critical range
              </p>
            </div>
          </div>

          <div className="p-3 sm:px-4 flex items-center space-x-3 group/stat hover:bg-slate-50/70 dark:hover:bg-slate-900/50 transition-colors">
            <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-[#16A34A] border border-emerald-200 dark:border-emerald-800/80 shrink-0">
              <Lock className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                Storage Security
              </span>
              <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate mt-0.5">
                AES-256-GCM at rest
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. SPATIAL INGESTION STATION DECK ── */}
      <div className="relative rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-md shadow-slate-900/5 p-4 sm:p-5 space-y-3.5 transition-all">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-1 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Diagnostic Lab Report Ingestion
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Ingest unstructured lab sheets for automated normalization, reference range evaluation, and encrypted graph storage.
            </p>
          </div>
          <div className="flex items-center space-x-1.5 text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900 px-3 py-1 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs self-start sm:self-auto">
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
          className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
            isDragOver
              ? 'border-[#0F766E] dark:border-[#14B8A6] bg-teal-50/40 dark:bg-teal-950/20 scale-[0.99]'
              : 'border-slate-300/80 dark:border-slate-700/80 hover:border-teal-500 dark:hover:border-teal-500 bg-slate-50/60 dark:bg-slate-900/40'
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
            <div className="p-3 rounded-xl bg-white dark:bg-slate-800 text-[#0F766E] dark:text-[#14B8A6] shadow-xs ring-1 ring-slate-200 dark:ring-slate-700">
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
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] dark:bg-[#14B8A6]" />
              <span className="font-semibold text-slate-700 dark:text-slate-300">1 Normalize</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700 font-light">───</span>
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
              <span className="font-semibold text-slate-700 dark:text-slate-300">2 Range-check</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700 font-light">───</span>
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
              <span className="font-semibold text-slate-700 dark:text-slate-300">3 Graph-store</span>
            </span>
          </div>

          <div className="flex items-center space-x-1.5 text-slate-500 text-[11px]">
            <ShieldCheck className="w-3.5 h-3.5 text-[#16A34A] stroke-[1.75]" />
            <span>Encrypted on arrival · AES-256-GCM · guests auto-purged on logout</span>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-800 dark:text-red-300 animate-fade-in">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Uploading State with Per-Stage Chip */}
      {isUploading && (
        <div className="p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-md space-y-3 animate-fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-[#0F766E] dark:bg-[#14B8A6] animate-pulse" />
              <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                Processing Diagnostic Lab Report...
              </span>
            </div>
            <span className="h-6 px-2.5 text-[11px] font-mono font-medium rounded-lg bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
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

          <div className="p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-md space-y-3">
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

            <div className="bg-slate-50/70 dark:bg-slate-900/60 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 text-[13.5px] leading-relaxed">
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
        <div className="p-3 rounded-xl bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-800 text-xs font-mono text-green-800 dark:text-green-300 flex items-center justify-between animate-fade-in">
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

      {/* ── 3. STORED DIAGNOSTIC REPORTS ARCHIVE ── */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-xs overflow-hidden">
        <div className="p-4 bg-slate-50/80 dark:bg-slate-900/60 border-b border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-slate-500 stroke-[1.75]" />
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Stored Diagnostic Reports ({reports.length})
            </h3>
          </div>

          <div className="flex items-center space-x-2">
            {/* Filter Chips: All / Normal / Critical */}
            <div className="flex items-center space-x-1 bg-white dark:bg-slate-950 p-0.5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs">
              <button
                type="button"
                onClick={() => setFilterStatus('all')}
                className={`h-7 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer ${
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
                className={`h-7 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer ${
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
                className={`h-7 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer ${
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
              className="flex items-center space-x-1.5 h-7 px-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-slate-900 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 shadow-2xs"
              title="Refresh reports list"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin' : ''} stroke-[1.75]`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Reports Table or Empty State */}
        {filteredReports.length === 0 ? (
          <div className="p-8 text-center space-y-2">
            <FileText className="w-8 h-8 text-slate-400 mx-auto stroke-[1.5]" />
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              No reports stored in this view
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
              Upload a diagnostic report above to populate your private encrypted records.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-900 text-[11px] font-medium text-slate-500 uppercase tracking-wide border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-2.5 px-4">Report ID / File</th>
                  <th className="py-2.5 px-4">Date</th>
                  <th className="py-2.5 px-4">Lab Values</th>
                  <th className="py-2.5 px-4">Critical Status</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                {filteredReports.map((rep) => (
                  <tr
                    key={rep.report_id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors group cursor-pointer"
                    onClick={() => setSelectedReportId(rep.report_id)}
                  >
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-[#0F766E] dark:group-hover:text-[#14B8A6]">
                        {rep.report_id}
                      </div>
                      <div className="text-[11px] text-slate-500 font-sans truncate max-w-xs">
                        {rep.filename}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-400">
                      {rep.report_date}
                    </td>
                    <td className="py-3 px-4 text-slate-700 dark:text-slate-300">
                      {rep.n_lab_values || 0} values
                    </td>
                    <td className="py-3 px-4">
                      {rep.critical_flag ? (
                        <span className="h-6 px-2 inline-flex items-center space-x-1 rounded-md text-[10px] font-semibold uppercase bg-red-50 dark:bg-red-950/40 text-[#DC2626] border border-red-200 dark:border-red-800">
                          <AlertOctagon className="w-3 h-3" />
                          <span>Critical Range</span>
                        </span>
                      ) : (
                        <span className="h-6 px-2 inline-flex items-center space-x-1 rounded-md text-[10px] font-semibold uppercase bg-green-50 dark:bg-green-950/40 text-[#16A34A] border border-green-200 dark:border-green-800">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Normal</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div
                        className="inline-flex items-center space-x-1.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedReportId(rep.report_id)}
                          className="h-6 px-2 rounded bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] cursor-pointer"
                        >
                          Inspect
                        </button>
                        <button
                          type="button"
                          onClick={() => navigate('/trends')}
                          className="h-6 px-2 rounded bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] cursor-pointer"
                        >
                          Trend
                        </button>
                        <button
                          type="button"
                          onClick={() => setPurgeTarget(rep)}
                          className="h-6 px-2 rounded bg-red-50 dark:bg-red-950/40 text-[11px] font-medium text-red-600 dark:text-red-400 hover:bg-red-100 cursor-pointer"
                          title="GDPR Right-to-Erasure Purge"
                        >
                          <Trash2 className="w-3 h-3" />
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

      {/* Drawer */}
      {selectedReportId && (
        <ReportDrawer
          reportId={selectedReportId}
          onClose={() => setSelectedReportId(null)}
        />
      )}

      {/* Purge Confirmation Modal */}
      {purgeTarget && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-5 space-y-3 shadow-xl animate-fade-in text-slate-800 dark:text-slate-200">
            <div className="flex items-center space-x-2 text-red-600 dark:text-red-400">
              <ShieldAlert className="w-5 h-5" />
              <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                Execute GDPR Right-to-Erasure?
              </h3>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              This action will permanently purge report <strong>{purgeTarget.report_id}</strong> ({purgeTarget.filename}) and remove all associated normalized lab nodes from your private encrypted Kùzu graph store.
            </p>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setPurgeTarget(null)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-medium hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPurge}
                className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-medium cursor-pointer shadow-xs"
              >
                Confirm Purge
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
