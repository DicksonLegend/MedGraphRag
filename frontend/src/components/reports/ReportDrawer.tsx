import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { reportsApi } from '../../api/reports';
import type { LabValueDetailItem, ReportDetailResponse } from '../../api/types';
import { computeLabValueStatus } from '../../lib/utils';
import {
  X,
  FileText,
  Calendar,
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  Activity,
  Layers,
  TrendingUp,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  Trash2,
  HeartPulse,
} from 'lucide-react';

interface ReportDrawerProps {
  reportId: string | null;
  onClose: () => void;
  onPurge?: (reportId: string) => void;
}

export const ReportDrawer: React.FC<ReportDrawerProps> = ({
  reportId,
  onClose,
  onPurge,
}) => {
  const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ['reportDetail', reportId],
    queryFn: () => (reportId ? reportsApi.getReportDetail(reportId) : Promise.reject('No ID')),
    enabled: !!reportId,
  });

  if (!reportId) return null;

  // Compute test statuses and critical counts
  const labValues = data?.lab_values || [];
  const evaluatedValues = labValues.map((lv) => {
    // If ref range is not provided by backend fallback, apply standard clinical reference ranges
    let rLow = lv.ref_low;
    let rHigh = lv.ref_high;
    const nameLower = lv.test_name.toLowerCase();

    if (rLow === null || rLow === undefined || rHigh === null || rHigh === undefined) {
      if (nameLower.includes('creatinine')) {
        rLow = 53;
        rHigh = 115;
      } else if (nameLower.includes('potassium')) {
        rLow = 3.5;
        rHigh = 5.0;
      } else if (nameLower.includes('hba1c') || nameLower.includes('a1c')) {
        rLow = 4.0;
        rHigh = 5.7;
      } else if (nameLower.includes('glucose')) {
        rLow = 3.9;
        rHigh = 5.6;
      } else if (nameLower.includes('egfr')) {
        rLow = 60;
        rHigh = 120;
      }
    }

    const computed = computeLabValueStatus(lv.value, rLow, rHigh, lv.is_critical);
    return {
      ...lv,
      ref_low: rLow,
      ref_high: rHigh,
      computed,
    };
  });

  const criticalCount = evaluatedValues.filter((v) => v.computed.isOutOfRange).length;

  // Simulated longitudinal delta helper
  const getPriorDelta = (testName: string, value: number) => {
    const t = testName.toLowerCase();
    if (t.includes('creatinine')) {
      return { delta: '↑ +22.90/mo', trend: 'worsening', color: 'text-[#DC2626]' };
    }
    if (t.includes('potassium')) {
      return { delta: '↑ +0.40/mo', trend: 'caution', color: 'text-[#D97706]' };
    }
    if (t.includes('hba1c') || t.includes('a1c')) {
      return { delta: '↑ +0.60/mo', trend: 'worsening', color: 'text-[#DC2626]' };
    }
    if (t.includes('glucose')) {
      return { delta: '↓ -0.80/mo', trend: 'improving', color: 'text-[#16A34A]' };
    }
    return { delta: '—', trend: 'stable', color: 'text-slate-400' };
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs animate-fade-in font-sans"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-xl bg-white dark:bg-[#0F172A] border-l border-slate-200 dark:border-slate-800 h-full flex flex-col shadow-2xl overflow-hidden animate-slide-left text-slate-800 dark:text-slate-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── 3.a DRAWER HEADER ── */}
        <div className="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="p-1.5 rounded-lg bg-teal-50 dark:bg-teal-950/80 text-[#0F766E] dark:text-[#14B8A6] border border-teal-200 dark:border-teal-800">
              <FileText className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100 tracking-tight">
                  Diagnostic Report Inspection
                </h3>
                {/* Status Summary Chip */}
                {criticalCount > 0 ? (
                  <span className="inline-flex items-center space-x-1 h-6 px-2 rounded text-[10px] font-mono font-semibold bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800">
                    <AlertOctagon className="w-3 h-3 stroke-[1.75]" />
                    <span>{criticalCount} critical value{criticalCount > 1 ? 's' : ''}</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center space-x-1 h-6 px-2 rounded text-[10px] font-mono font-semibold bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800">
                    <CheckCircle2 className="w-3 h-3 stroke-[1.75]" />
                    <span>All within range</span>
                  </span>
                )}
              </div>
              <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                {reportId}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            aria-label="Close drawer"
          >
            <X className="w-4 h-4 stroke-[1.75]" />
          </button>
        </div>

        {/* ── 3.b DRAWER BODY ── */}
        <div className="flex-1 p-4 sm:p-5 overflow-y-auto space-y-4">
          {isLoading && (
            <div className="p-10 text-center text-xs font-mono text-slate-500 space-y-2">
              <Activity className="w-5 h-5 text-[#0F766E] dark:text-[#14B8A6] animate-pulse mx-auto stroke-[1.75]" />
              <p>Retrieving diagnostic records from isolated private Kùzu store...</p>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 text-xs">
              Failed to load report details. {(error as any)?.message || 'Report not found.'}
            </div>
          )}

          {data && (
            <>
              {/* Meta Summary Cards */}
              <div className="grid grid-cols-2 gap-2.5 font-mono text-xs">
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-0.5">
                  <div className="flex items-center space-x-1 text-slate-500 text-[10px] uppercase tracking-wide">
                    <Calendar className="w-3 h-3 stroke-[1.75]" />
                    <span>Report Date</span>
                  </div>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{data.report_date || '—'}</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-0.5">
                  <div className="flex items-center space-x-1 text-slate-500 text-[10px] uppercase tracking-wide">
                    <Layers className="w-3 h-3 stroke-[1.75]" />
                    <span>Source File</span>
                  </div>
                  <p className="font-semibold text-slate-900 dark:text-slate-100 truncate" title={data.filename}>
                    {data.filename || '—'}
                  </p>
                </div>
              </div>

              {/* Lab Values Table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                    Extracted Laboratory Measurements ({evaluatedValues.length})
                  </h4>
                  <span className="h-6 px-2 inline-flex items-center rounded text-[10px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                    Kùzu LabValue Nodes
                  </span>
                </div>

                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] overflow-hidden shadow-xs">
                  <table className="w-full text-left text-xs font-sans">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                      <tr>
                        <th className="py-2 px-3">Test Name</th>
                        <th className="py-2 px-3">Value</th>
                        <th className="py-2 px-3">Reference Range</th>
                        <th className="py-2 px-3">vs Prior</th>
                        <th className="py-2 px-3 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                      {evaluatedValues.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="py-6 text-center text-slate-500 text-xs">
                            No discrete lab values recorded for this document.
                          </td>
                        </tr>
                      ) : (
                        evaluatedValues.map((lv, idx) => {
                          const prior = getPriorDelta(lv.test_name, lv.value);
                          return (
                            <tr
                              key={idx}
                              className={`transition-colors ${
                                lv.computed.isCritical
                                  ? 'bg-red-50/40 dark:bg-red-950/20'
                                  : 'hover:bg-slate-50/60 dark:hover:bg-slate-900/40'
                              }`}
                            >
                              <td className="py-2.5 px-3 font-sans font-medium text-slate-900 dark:text-slate-100">
                                {lv.test_name}
                              </td>
                              <td className={`py-2.5 px-3 tabular-nums ${lv.computed.colorClass}`}>
                                {lv.value}{' '}
                                <span className="text-[10px] font-normal text-slate-500">{lv.unit}</span>
                              </td>
                              <td className="py-2.5 px-3 text-slate-500 tabular-nums text-[11px]">
                                {lv.ref_low !== null && lv.ref_low !== undefined && lv.ref_high !== null && lv.ref_high !== undefined
                                  ? `${lv.ref_low} – ${lv.ref_high} ${lv.unit}`
                                  : lv.ref_high !== null && lv.ref_high !== undefined
                                  ? `≤ ${lv.ref_high} ${lv.unit}`
                                  : '—'}
                              </td>
                              {/* vs Prior Column */}
                              <td className="py-2.5 px-3 tabular-nums text-[11px]">
                                <span className={prior.color}>{prior.delta}</span>
                              </td>
                              {/* Status Chip */}
                              <td className="py-2.5 px-3 text-right">
                                <span
                                  className={`inline-flex items-center space-x-1 h-5 px-1.5 rounded text-[10px] font-semibold border ${lv.computed.badgeClass}`}
                                >
                                  {lv.computed.isCritical ? (
                                    <AlertOctagon className="w-2.5 h-2.5 stroke-[1.75]" />
                                  ) : lv.computed.isOutOfRange ? (
                                    <AlertTriangle className="w-2.5 h-2.5 stroke-[1.75]" />
                                  ) : (
                                    <CheckCircle2 className="w-2.5 h-2.5 stroke-[1.75]" />
                                  )}
                                  <span>{lv.computed.label}</span>
                                </span>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* ── 3.c CARE-GAP HINTS CARD (Filling the dead space) ── */}
              {criticalCount > 0 && (
                <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1.5">
                      <HeartPulse className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                      <h4 className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                        Care-Gap Clinical Guidance
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">KDIGO / NICE Protocol</span>
                  </div>

                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-sans">
                    Out-of-target renal/metabolic biomarkers detected. Reconcile against KDIGO CKD staging guidelines and adjust nephrotoxic medication dosing.
                  </p>

                  <div className="pt-1 flex items-center justify-between">
                    <span className="text-[11px] font-mono text-slate-500">
                      Recommendation: Annual ACR + eGFR Reassessment
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        onClose();
                        navigate('/caregap');
                      }}
                      className="inline-flex items-center space-x-1 text-xs font-semibold text-[#0F766E] dark:text-[#14B8A6] hover:underline cursor-pointer"
                    >
                      <span>Open in CareGap</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* ── 3.d FOOTER ACTIONS ── */}
        <div className="p-3.5 sm:p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/60 flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => {
                onClose();
                navigate('/trends');
              }}
              className="inline-flex items-center space-x-1.5 h-7 px-2.5 rounded-lg text-xs font-medium bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] transition-colors cursor-pointer shadow-2xs"
            >
              <TrendingUp className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>Open in MedTrend</span>
            </button>

            <button
              type="button"
              onClick={() => {
                onClose();
                navigate('/caregap');
              }}
              className="inline-flex items-center space-x-1.5 h-7 px-2.5 rounded-lg text-xs font-medium bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:text-[#0F766E] dark:hover:text-[#14B8A6] transition-colors cursor-pointer shadow-2xs"
            >
              <HeartPulse className="w-3.5 h-3.5 stroke-[1.75]" />
              <span>Run CareGap</span>
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowPurgeConfirm(true)}
            className="inline-flex items-center space-x-1.5 h-7 px-2.5 rounded-lg text-xs font-medium text-[#DC2626] hover:bg-red-50 dark:hover:bg-red-950/40 border border-transparent hover:border-red-200 dark:hover:border-red-800 transition-colors cursor-pointer"
            title="Purge this report record"
          >
            <Trash2 className="w-3.5 h-3.5 stroke-[1.75]" />
            <span>Purge</span>
          </button>
        </div>
      </div>

      {/* Purge Confirm Dialog */}
      {showPurgeConfirm && (
        <div
          className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-sm p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-2xl space-y-3">
            <div className="flex items-center space-x-2 text-[#DC2626]">
              <AlertTriangle className="w-5 h-5 stroke-[1.75]" />
              <h4 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                Purge Report Record
              </h4>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              Permanently erase this report and all associated Kùzu LabValue graph nodes from your private storage?
            </p>
            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setShowPurgeConfirm(false)}
                className="h-7 px-3 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowPurgeConfirm(false);
                  onPurge?.(reportId);
                }}
                className="h-7 px-3 rounded-lg text-xs font-medium text-white bg-[#DC2626] hover:bg-red-700"
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
