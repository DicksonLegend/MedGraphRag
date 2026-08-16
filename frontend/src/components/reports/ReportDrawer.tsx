import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { reportsApi } from '../../api/reports';
import type { LabValueDetailItem, ReportDetailResponse } from '../../api/types';
import {
  X,
  FileText,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Activity,
  Layers,
  ArrowRight,
} from 'lucide-react';

interface ReportDrawerProps {
  reportId: string | null;
  onClose: () => void;
}

export const ReportDrawer: React.FC<ReportDrawerProps> = ({
  reportId,
  onClose,
}) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['reportDetail', reportId],
    queryFn: () => (reportId ? reportsApi.getReportDetail(reportId) : Promise.reject('No ID')),
    enabled: !!reportId,
  });

  if (!reportId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-card border-l border-card-border h-full flex flex-col shadow-2xl overflow-hidden animate-slide-left"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="p-5 border-b border-card-border bg-canvas/40 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-brand text-white shadow-xs">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-heading font-extrabold text-base text-ink tracking-tight">
                Diagnostic Report Details
              </h3>
              <p className="text-xs font-mono text-ink-muted">
                {reportId}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl text-ink-muted hover:text-ink hover:bg-canvas border border-card-border transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          {isLoading && (
            <div className="p-12 text-center text-xs font-mono text-ink-muted space-y-3">
              <Activity className="w-6 h-6 text-brand animate-pulse mx-auto" />
              <p>Retrieving diagnostic records from isolated private Kùzu store...</p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl border border-status-danger/30 bg-status-danger-bg text-status-danger text-xs font-sans">
              Failed to load report details. {(error as any)?.message || 'Report not found.'}
            </div>
          )}

          {data && (
            <>
              {/* Meta Summary Cards */}
              <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                <div className="p-3 rounded-xl bg-canvas border border-card-border space-y-1">
                  <div className="flex items-center space-x-1.5 text-ink-subtle text-[10px] uppercase tracking-wider">
                    <Calendar className="w-3 h-3" />
                    <span>Report Date</span>
                  </div>
                  <p className="font-bold text-ink">{data.report_date || '—'}</p>
                </div>
                <div className="p-3 rounded-xl bg-canvas border border-card-border space-y-1">
                  <div className="flex items-center space-x-1.5 text-ink-subtle text-[10px] uppercase tracking-wider">
                    <Layers className="w-3 h-3" />
                    <span>Source File</span>
                  </div>
                  <p className="font-bold text-ink truncate" title={data.filename}>
                    {data.filename || '—'}
                  </p>
                </div>
              </div>

              {/* Lab Values Table */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-heading font-bold text-xs text-ink uppercase tracking-wider">
                    Extracted Laboratory Measurements ({data.lab_values.length})
                  </h4>
                  <span className="text-[10px] font-mono text-ink-subtle">
                    Kùzu LabValue Nodes
                  </span>
                </div>

                <div className="rounded-xl border border-card-border bg-card overflow-hidden shadow-2xs">
                  <table className="w-full text-left text-xs font-sans">
                    <thead className="bg-canvas border-b border-card-border font-heading font-bold text-ink-muted text-[11px] uppercase tracking-wider">
                      <tr>
                        <th className="py-2.5 px-3">Test Name</th>
                        <th className="py-2.5 px-3">Value</th>
                        <th className="py-2.5 px-3">Reference Range</th>
                        <th className="py-2.5 px-3 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-card-border/60 font-mono">
                      {data.lab_values.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="py-6 text-center text-ink-subtle text-xs">
                            No discrete lab values recorded for this document.
                          </td>
                        </tr>
                      ) : (
                        data.lab_values.map((lv: LabValueDetailItem, idx: number) => (
                          <tr
                            key={idx}
                            className={`transition-colors ${
                              lv.is_critical
                                ? 'bg-status-danger-bg/50 text-status-danger font-semibold'
                                : 'hover:bg-canvas/50 text-ink'
                            }`}
                          >
                            <td className="py-3 px-3 font-sans font-medium">
                              {lv.test_name}
                            </td>
                            <td className="py-3 px-3 font-bold tabular-nums">
                              {lv.value} <span className="text-[11px] font-normal text-ink-subtle">{lv.unit}</span>
                            </td>
                            <td className="py-3 px-3 text-ink-muted tabular-nums">
                              {lv.ref_low !== null && lv.ref_low !== undefined && lv.ref_high !== null && lv.ref_high !== undefined
                                ? `${lv.ref_low} – ${lv.ref_high} ${lv.unit}`
                                : lv.ref_high !== null && lv.ref_high !== undefined
                                ? `≤ ${lv.ref_high} ${lv.unit}`
                                : '—'}
                            </td>
                            <td className="py-3 px-3 text-right">
                              {lv.is_critical ? (
                                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-status-danger-bg text-status-danger border border-status-danger/30">
                                  <AlertTriangle className="w-3 h-3" />
                                  <span>CRITICAL</span>
                                </span>
                              ) : (
                                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-status-success-bg text-status-success border border-status-success/30">
                                  <CheckCircle2 className="w-3 h-3" />
                                  <span>Normal</span>
                                </span>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
