import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { reportsApi } from '../api/reports';
import { multimodalApi } from '../api/multimodal';
import type { ReportResponse, ReportSummaryItem, ImageAnalysisResult } from '../api/types';
import { EcgLoader } from '../components/common/EcgLoader';
import { SubwayMap } from '../components/common/SubwayMap';
import { CriticalEscalationBanner } from '../components/common/CriticalEscalationBanner';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { MarkdownAnswer } from '../components/chat/MarkdownAnswer';
import { ReportDrawer } from '../components/reports/ReportDrawer';
import { ScanUploadDropzone } from '../components/multimodal/ScanUploadDropzone';
import { VisualFindingsCard } from '../components/multimodal/VisualFindingsCard';
import { RadiologyReportDrawer } from '../components/multimodal/RadiologyReportDrawer';
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
  Image as ImageIcon,
  Sparkles,
  Activity,
  MessageSquare,
} from 'lucide-react';

import { useSessionStore } from '../stores/sessionStore';

const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.xlsx', '.csv'];
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // 20 MB

type FilterStatus = 'all' | 'normal' | 'critical';
type MainTab = 'labs' | 'scans';

export const ReportsPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Top Tab selection
  const [activeMainTab, setActiveMainTab] = useState<MainTab>('labs');

  // ── Tab 1: Labs State ──
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

  // ── Tab 2: Scans State ──
  const [scans, setScans] = useState<ImageAnalysisResult[]>([]);
  const [isLoadingScans, setIsLoadingScans] = useState<boolean>(true);
  const [isUploadingScan, setIsUploadingScan] = useState<boolean>(false);
  const [uploadScanStage, setUploadScanStage] = useState<number>(0);
  const [selectedScan, setSelectedScan] = useState<ImageAnalysisResult | null>(null);
  const [isScanDrawerOpen, setIsScanDrawerOpen] = useState<boolean>(false);
  const [isRunningFullVlm, setIsRunningFullVlm] = useState<boolean>(false);
  const [scanPurgeTarget, setScanPurgeTarget] = useState<ImageAnalysisResult | null>(null);

  // Fetch labs
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

  // Fetch scans
  const fetchScans = async () => {
    setIsLoadingScans(true);
    try {
      const list = await multimodalApi.listScans();
      setScans(list);
    } catch {
      setScans([]);
    } finally {
      setIsLoadingScans(false);
    }
  };

  useEffect(() => {
    fetchReports();
    fetchScans();
  }, []);

  // Labs file upload handler
  const handleFileSelection = async (file: File) => {
    setErrorMsg(null);
    setUploadResult(null);

    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMsg(
        `Unsupported file format '${ext}'. Allowed formats: ${ALLOWED_EXTENSIONS.sort().join(', ')}`
      );
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      setErrorMsg('File size exceeds maximum allowed limit of 20 MB.');
      return;
    }

    setIsUploading(true);
    setUploadStage(1);
    const timer1 = setTimeout(() => setUploadStage(2), 700);
    const timer2 = setTimeout(() => setUploadStage(3), 1500);

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

  // Labs purge handler
  const handleConfirmPurge = async () => {
    if (!purgeTarget) return;
    const targetId = purgeTarget.report_id;
    try {
      await reportsApi.purgeReport(targetId);
      setReports((prev) => prev.filter((r) => r.report_id !== targetId));
      if (selectedReportId === targetId) {
        setSelectedReportId(null);
      }
      setPurgedNotification(
        `Report ${targetId} and all associated lab graph nodes have been permanently erased.`
      );
      setTimeout(() => setPurgedNotification(null), 5000);
    } catch (err: any) {
      setErrorMsg(err.message || `Failed to purge report ${targetId}`);
    } finally {
      setPurgeTarget(null);
    }
  };

  // ── Scans Handlers ──
  const handleScanUpload = async (file: File, mode: 'triage' | 'full' = 'triage') => {
    setIsUploadingScan(true);
    setUploadScanStage(1);
    const timer1 = setTimeout(() => setUploadScanStage(2), 600);
    const timer2 = setTimeout(() => setUploadScanStage(3), 1400);

    try {
      const res = await multimodalApi.analyzeImage(file, mode);
      setScans((prev) => [res, ...prev.filter((s) => s.image_id !== res.image_id)]);
      setSelectedScan(res);
      setIsScanDrawerOpen(true);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to analyze medical scan.');
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setIsUploadingScan(false);
      setUploadScanStage(0);
    }
  };

  const handleRunFullInterpretation = async (scan: ImageAnalysisResult) => {
    setIsRunningFullVlm(true);
    try {
      // Re-run mode="full" for the scan
      const blob = await multimodalApi.getPreviewBlob(scan.image_id);
      const file = new File([blob], scan.filename, { type: 'image/png' });
      const fullRes = await multimodalApi.analyzeImage(file, 'full');
      setScans((prev) => prev.map((s) => (s.image_id === scan.image_id ? fullRes : s)));
      setSelectedScan(fullRes);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed running full VLM interpretation.');
    } finally {
      setIsRunningFullVlm(false);
    }
  };

  const handleConfirmScanPurge = async () => {
    if (!scanPurgeTarget) return;
    const targetId = scanPurgeTarget.image_id;
    try {
      await multimodalApi.deleteScan(targetId);
      setScans((prev) => prev.filter((s) => s.image_id !== targetId));
      if (selectedScan?.image_id === targetId) {
        setSelectedScan(null);
        setIsScanDrawerOpen(false);
      }
      setPurgedNotification(
        `Scan ${targetId} and encrypted image data have been permanently erased.`
      );
      setTimeout(() => setPurgedNotification(null), 5000);
    } catch (err: any) {
      setErrorMsg(err.message || `Failed to purge scan ${targetId}`);
    } finally {
      setScanPurgeTarget(null);
    }
  };

  const handleAskInChat = (scan: ImageAnalysisResult) => {
    navigate('/chat', {
      state: {
        attachedScan: {
          image_id: scan.image_id,
          filename: scan.filename,
          modality: scan.modality,
          impression: scan.impression,
          findings: scan.findings,
        },
      },
    });
  };

  // Metrics
  const totalReports = reports.length;
  const totalLabValues = reports.reduce((sum, r) => sum + (r.n_lab_values || 0), 0);
  const criticalReportsCount = reports.filter((r) => r.critical_flag).length;

  const filteredReports = reports
    .filter((rep) => {
      if (filterStatus === 'normal') return !rep.critical_flag;
      if (filterStatus === 'critical') return rep.critical_flag;
      return true;
    })
    .sort((a, b) => new Date(b.report_date).getTime() - new Date(a.report_date).getTime());

  return (
    <div className="space-y-4 max-w-7xl mx-auto font-sans text-slate-800 dark:text-slate-200">
      {/* ── 1. TOP-LEVEL MAIN TABS SWITCHER ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveMainTab('labs')}
            className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 transition-all cursor-pointer ${
              activeMainTab === 'labs'
                ? 'bg-teal-600 text-white shadow-sm'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Laboratory Chemistry &amp; Biomarkers</span>
            <span className="text-[11px] font-mono px-1.5 py-0.2 rounded-full bg-white/20">
              {totalReports}
            </span>
          </button>

          <button
            onClick={() => setActiveMainTab('scans')}
            className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 transition-all cursor-pointer ${
              activeMainTab === 'scans'
                ? 'bg-teal-600 text-white shadow-sm'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            <span>Medical Imaging &amp; Scans (CXR / CT / MRI)</span>
            <span className="text-[11px] font-mono px-1.5 py-0.2 rounded-full bg-white/20">
              {scans.length}
            </span>
          </button>
        </div>

        <div className="flex items-center space-x-1.5 text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
          <Lock className="w-3.5 h-3.5 text-[#16A34A] stroke-[1.75]" />
          <span>AES-256-GCM Private Isolation</span>
        </div>
      </div>

      {/* Notifications */}
      {purgedNotification && (
        <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs flex items-center space-x-2 animate-fade-in shadow-2xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="font-medium">{purgedNotification}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200 text-xs flex items-center space-x-2 animate-fade-in shadow-2xs">
          <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0" />
          <span className="font-medium">{errorMsg}</span>
          <button
            onClick={() => setErrorMsg(null)}
            className="ml-auto text-red-500 hover:text-red-700"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: LABORATORY CHEMISTRY & BIOMARKERS                                  */}
      {/* ========================================================================= */}
      {activeMainTab === 'labs' && (
        <div className="space-y-4">
          {/* Vault Telemetry Ribbon */}
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
                    {criticalReportsCount} critical report{criticalReportsCount === 1 ? '' : 's'}
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

          {/* Ingestion Station Deck */}
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

              {isUploading ? (
                <div className="py-4">
                  <EcgLoader
                    label={
                      uploadStage === 1
                        ? 'Extracting & Normalizing Lab Parameters...'
                        : uploadStage === 2
                        ? 'Evaluating Reference Ranges & Delta Flags...'
                        : 'Encrypting and Updating Isolated Graph...'
                    }
                    sublabel="Self-verifying clinical validation active"
                  />
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center space-y-2.5">
                  <div className="p-3 rounded-full bg-teal-50 dark:bg-teal-950/60 text-[#0F766E] dark:text-[#14B8A6] border border-teal-200/80 dark:border-teal-800/80">
                    <UploadCloud className="w-6 h-6 stroke-[1.75]" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                      Drag &amp; drop diagnostic report file here
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      PDF, PNG, JPG, XLSX, CSV • Max 20 MB
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="h-8 px-4 inline-flex items-center justify-center rounded-lg bg-[#0F766E] dark:bg-[#14B8A6] text-white dark:text-slate-900 text-xs font-medium hover:bg-teal-700 dark:hover:bg-teal-400 cursor-pointer shadow-xs transition-colors"
                  >
                    Select File
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Upload Result Preview Card */}
          {uploadResult && (
            <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-md shadow-slate-900/5 p-4 sm:p-5 space-y-4 animate-fade-in">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-5 h-5 text-[#16A34A]" />
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    Diagnostic Report Ingested &amp; Encrypted
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">
                    Status: {uploadResult.answer_status}
                  </span>
                  <span className="text-[11px] font-mono bg-teal-500/10 text-teal-accent px-2 py-0.5 rounded border border-teal-500/20">
                    Confidence: {Math.round(uploadResult.final_confidence * 100)}%
                  </span>
                </div>
              </div>

              {uploadResult.answer_status === 'caution' && (
                <CriticalEscalationBanner
                  message="One or more parameters in the uploaded diagnostic report indicate abnormal or critical values. Review the detailed findings below."
                />
              )}

              {/* Synthesized Interpretation */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/80 border border-slate-200/80 dark:border-slate-800 text-xs">
                <MarkdownAnswer
                  content={uploadResult.answer_text}
                  citations={uploadResult.citations || []}
                />
              </div>
            </div>
          )}

          {/* Reports History Ledger */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-md shadow-slate-900/5 p-4 sm:p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Private Diagnostic Reports Ledger
                </h3>
              </div>

              {/* Status Filters */}
              <div className="flex items-center space-x-1.5">
                {(['all', 'normal', 'critical'] as FilterStatus[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilterStatus(f)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold capitalize transition-colors ${
                      filterStatus === f
                        ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
                    }`}
                  >
                    {f}
                  </button>
                ))}
                <button
                  onClick={fetchReports}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded"
                  title="Refresh Reports"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {isLoadingHistory ? (
              <div className="py-8">
                <EcgLoader label="Loading encrypted reports..." />
              </div>
            ) : filteredReports.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                No diagnostic reports matching filter. Upload a lab report above.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-50 dark:bg-slate-900 text-slate-500">
                    <tr>
                      <th className="py-2.5 px-4">Report ID / File</th>
                      <th className="py-2.5 px-4">Date</th>
                      <th className="py-2.5 px-4">Parameters</th>
                      <th className="py-2.5 px-4">Evaluation</th>
                      <th className="py-2.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {filteredReports.map((rep) => (
                      <tr
                        key={rep.report_id}
                        onClick={() => setSelectedReportId(rep.report_id)}
                        className="hover:bg-slate-50 dark:hover:bg-slate-900/50 cursor-pointer group transition-colors"
                      >
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-teal-600 dark:group-hover:text-teal-400">
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
                              className="h-6 px-2 rounded bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-700 dark:text-slate-300 hover:text-teal-600 cursor-pointer"
                            >
                              Inspect
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
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: MEDICAL IMAGING & SCANS (CXR / CT / MRI)                           */}
      {/* ========================================================================= */}
      {activeMainTab === 'scans' && (
        <div className="space-y-4">
          {/* Scan Dropzone */}
          <ScanUploadDropzone
            onUpload={handleScanUpload}
            isUploading={isUploadingScan}
            uploadStage={uploadScanStage}
          />

          {/* Scans Ledger / Grid */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800/90 bg-white dark:bg-[#0F172A] shadow-md shadow-slate-900/5 p-4 sm:p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <ImageIcon className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Medical Scans &amp; Radiograph Vault
                </h3>
              </div>
              <button
                onClick={fetchScans}
                className="p-1 text-slate-400 hover:text-slate-600 rounded"
                title="Refresh Scans"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            {isLoadingScans ? (
              <div className="py-8">
                <EcgLoader label="Loading encrypted scans..." />
              </div>
            ) : scans.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400 space-y-2">
                <ImageIcon className="w-8 h-8 opacity-30 mx-auto" />
                <p>No medical scans in private store yet. Drop a radiograph or DICOM slice above.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {scans.map((scan) => (
                  <div
                    key={scan.image_id}
                    onClick={() => {
                      setSelectedScan(scan);
                      setIsScanDrawerOpen(true);
                    }}
                    className="group border border-slate-200 dark:border-slate-800 rounded-xl p-4 bg-slate-50/50 dark:bg-slate-900/40 hover:border-teal-500/80 hover:bg-teal-50/10 transition-all cursor-pointer space-y-3 shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase bg-teal-accent/10 text-teal-accent px-2 py-0.5 rounded border border-teal-accent/20">
                        {scan.modality} • {scan.orientation}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        {scan.processing_time_ms} ms
                      </span>
                    </div>

                    <div>
                      <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate group-hover:text-teal-accent">
                        {scan.filename}
                      </h4>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2 mt-1 leading-relaxed">
                        {scan.impression}
                      </p>
                    </div>

                    {/* Findings chips */}
                    <div className="flex flex-wrap gap-1 pt-1">
                      {scan.findings.slice(0, 3).map((f, idx) => (
                        <span
                          key={idx}
                          className="text-[9px] font-mono bg-slate-200/80 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-1.5 py-0.5 rounded"
                        >
                          {f}
                        </span>
                      ))}
                      {scan.findings.length > 3 && (
                        <span className="text-[9px] font-mono text-slate-400 px-1 py-0.5">
                          +{scan.findings.length - 3} more
                        </span>
                      )}
                    </div>

                    <div className="pt-2 border-t border-slate-200/60 dark:border-slate-800 flex items-center justify-between text-xs">
                      <span className="text-[10px] font-mono text-slate-400">
                        {scan.mode === 'full' ? 'Generative VLM' : 'Fast Triage'}
                      </span>
                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleAskInChat(scan)}
                          className="px-2 py-1 bg-teal-accent/10 hover:bg-teal-accent/20 text-teal-accent text-[11px] font-medium rounded flex items-center gap-1"
                        >
                          <MessageSquare className="w-3 h-3" /> Chat
                        </button>
                        <button
                          onClick={() => setScanPurgeTarget(scan)}
                          className="p-1 text-red-400 hover:text-red-600 rounded"
                          title="Purge scan"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Drawers */}
      {selectedReportId && (
        <ReportDrawer
          reportId={selectedReportId}
          onClose={() => setSelectedReportId(null)}
        />
      )}

      <RadiologyReportDrawer
        scan={selectedScan}
        isOpen={isScanDrawerOpen}
        onClose={() => {
          setIsScanDrawerOpen(false);
          setSelectedScan(null);
        }}
        onRunFullInterpretation={handleRunFullInterpretation}
        isRunningFull={isRunningFullVlm}
        onAskInChat={handleAskInChat}
      />

      {/* GDPR Purge Confirmation Modal (Labs) */}
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

      {/* GDPR Purge Confirmation Modal (Scans) */}
      {scanPurgeTarget && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-5 space-y-3 shadow-xl animate-fade-in text-slate-800 dark:text-slate-200">
            <div className="flex items-center space-x-2 text-red-600 dark:text-red-400">
              <ShieldAlert className="w-5 h-5" />
              <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                Purge Medical Scan from Private Store?
              </h3>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              This action will permanently delete scan <strong>{scanPurgeTarget.image_id}</strong> ({scanPurgeTarget.filename}) and remove all encrypted image files and triage records from your private storage.
            </p>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setScanPurgeTarget(null)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-medium hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmScanPurge}
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
