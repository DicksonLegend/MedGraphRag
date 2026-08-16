import React, { useState, useEffect, useRef } from 'react';
import { reportsApi } from '../api/reports';
import type { ReportResponse, ReportSummaryItem } from '../api/types';
import { EcgLoader } from '../components/common/EcgLoader';
import { SubwayMap } from '../components/common/SubwayMap';
import { CriticalEscalationBanner } from '../components/common/CriticalEscalationBanner';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { MarkdownAnswer } from '../components/chat/MarkdownAnswer';
import { ReportDrawer } from '../components/reports/ReportDrawer';
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  AlertOctagon,
  Calendar,
  Layers,
  CheckCircle2,
  RefreshCw,
  Clock,
  ChevronRight,
} from 'lucide-react';

const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.xlsx', '.csv'];
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // 20 MB

export const ReportsPage: React.FC = () => {
  const [reports, setReports] = useState<ReportSummaryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<ReportResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

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

    // 3. Upload and Interpret
    setIsUploading(true);
    try {
      const res = await reportsApi.uploadReport(file);
      setUploadResult(res);
      // Refresh historical report list
      await fetchReports();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process diagnostic report.');
    } finally {
      setIsUploading(false);
    }
  };

  const isCriticalReport = (text: string) => {
    return (
      text.startsWith('⚠️ URGENT CLINICAL NOTICE') ||
      text.includes('CRITICAL_HIGH') ||
      text.includes('CRITICAL_LOW') ||
      text.includes('CRITICAL')
    );
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Upload Zone Card */}
      <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-4">
        <div>
          <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink">
            Diagnostic Lab Report Ingestion
          </h2>
          <p className="text-xs text-ink-muted">
            Upload PDF, PNG, JPG, XLSX, or CSV diagnostic panels for automated normalization, reference range evaluation, and AES-256 encrypted storage.
          </p>
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
          className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${
            isDragOver
              ? 'border-brand bg-brand-surface/40 scale-[1.01]'
              : 'border-card-border hover:border-brand/40 bg-canvas/40'
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
          <div className="flex flex-col items-center space-y-3">
            <div className="p-3.5 rounded-full bg-brand-surface text-brand shadow-xs">
              <UploadCloud className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-heading font-bold text-ink">
                Drag and drop your diagnostic report here, or{' '}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-brand hover:underline font-bold focus:outline-hidden cursor-pointer"
                >
                  browse files
                </button>
              </p>
              <p className="text-[11px] font-mono text-ink-subtle mt-1">
                Supported: PDF, PNG, JPG, XLSX, CSV (Max 20 MB)
              </p>
            </div>
          </div>
        </div>

        {errorMsg && (
          <ErrorState
            title="Upload Rejected"
            message={errorMsg}
            onRetry={() => fileInputRef.current?.click()}
          />
        )}
      </div>

      {/* Uploading Telemetry Loader */}
      {isUploading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs">
          <EcgLoader
            label="Analyzing Diagnostic Lab Report..."
            sublabel="Extracting optical tabular data, standardizing canonical test names & units, and checking critical thresholds..."
          />
        </div>
      )}

      {/* Upload Output Result */}
      {uploadResult && !isUploading && (
        <div className="space-y-6 animate-fade-in">
          {/* Critical Emergency Banner (if critical values detected) */}
          {isCriticalReport(uploadResult.answer_text) && (
            <CriticalEscalationBanner
              message="One or more lab values meet critical emergency thresholds requiring immediate clinical attention."
            />
          )}

          {/* Interpretation Output Card */}
          <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-card-border">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-brand" />
                <h3 className="text-sm font-heading font-bold text-ink">
                  Diagnostic Report Interpretation
                </h3>
              </div>
              <span className="text-xs font-mono text-ink-subtle">
                Status: {uploadResult.answer_status}
              </span>
            </div>

            {/* Answer Content */}
            <div className="bg-canvas/50 p-4 rounded-xl border border-card-border">
              <MarkdownAnswer
                content={uploadResult.answer_text}
                citations={uploadResult.citations || []}
              />
            </div>

            {/* Subway Map for Associated Conditions */}
            {uploadResult.graph_paths && uploadResult.graph_paths.length > 0 && (
              <SubwayMap paths={uploadResult.graph_paths} />
            )}

            {/* Medical Disclaimer */}
            <DisclaimerFooter />
          </div>
        </div>
      )}

      {/* Historical Uploads Table */}
      <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-brand" />
            <h3 className="text-base font-heading font-extrabold text-ink">
              Your Diagnostic Reports ({reports.length})
            </h3>
          </div>
          <button
            onClick={fetchReports}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-card-border bg-canvas text-xs font-heading font-semibold text-ink-muted hover:text-ink transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {isLoadingHistory ? (
          <div className="p-8 text-center text-xs font-mono text-ink-subtle">
            Loading private report records...
          </div>
        ) : reports.length === 0 ? (
          <EmptyState
            title="No reports uploaded yet"
            description="Upload your first diagnostic lab report above to start tracking longitudinal trends and clinical guidelines."
            actionLabel="Upload Diagnostic Report"
            onAction={() => fileInputRef.current?.click()}
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-card-border">
            <table className="w-full text-left text-xs font-sans">
              <thead className="bg-canvas border-b border-card-border text-ink font-heading font-bold">
                <tr>
                  <th className="px-4 py-3">Report Date</th>
                  <th className="px-4 py-3">Filename</th>
                  <th className="px-4 py-3">Lab Values Extracted</th>
                  <th className="px-4 py-3">Critical Status</th>
                  <th className="px-4 py-3">Report ID</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-card-border/60">
                {reports.map((rep) => (
                  <tr
                    key={rep.report_id}
                    onClick={() => setSelectedReportId(rep.report_id)}
                    className="hover:bg-canvas/60 transition-colors cursor-pointer group"
                  >
                    <td className="px-4 py-3 font-mono font-medium text-ink flex items-center space-x-2">
                      <Calendar className="w-3.5 h-3.5 text-brand" />
                      <span>{rep.report_date || '—'}</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-ink-muted">
                      {rep.filename || '—'}
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-ink tabular-nums">
                      {rep.n_lab_values} tests
                    </td>
                    <td className="px-4 py-3">
                      {rep.critical_flag ? (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-status-danger-bg text-status-danger border border-status-danger/30">
                          <AlertOctagon className="w-3 h-3" />
                          <span>Critical Range</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-mono font-medium bg-status-success-bg text-status-success border border-status-success/30">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Normal / Monitored</span>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-ink-subtle">
                      {rep.report_id}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="inline-flex items-center space-x-1 text-xs font-heading font-semibold text-brand group-hover:underline">
                        <span>Inspect</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Slide-over Right Drawer for Report Inspection */}
      <ReportDrawer
        reportId={selectedReportId}
        onClose={() => setSelectedReportId(null)}
      />
    </div>
  );
};
