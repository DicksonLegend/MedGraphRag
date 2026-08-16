import React, { useState, useEffect } from 'react';
import { featuresApi } from '../api/features';
import type { TrendItem, TrendResult } from '../api/types';
import { EcgLoader } from '../components/common/EcgLoader';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { getTrendDirectionProps } from '../lib/utils';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import {
  TrendingUp,
  AlertTriangle,
  Activity,
  ArrowRight,
  RefreshCw,
  Sparkles,
  GitCommit,
  Printer,
  Calendar,
  CheckCircle2,
} from 'lucide-react';

export const TrendsPage: React.FC = () => {
  const [data, setData] = useState<TrendResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchTrends = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await featuresApi.getTrends();
      setData(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch longitudinal trend analysis.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTrends();
  }, []);

  const handlePrint = () => {
    window.print();
  };

  // Custom Recharts Tooltip for U2
  const CustomChartTooltip = ({ active, payload, unit }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
      return (
        <div className="p-3 rounded-xl bg-card border border-card-border shadow-xl text-xs font-mono space-y-1 backdrop-blur-md">
          <div className="flex items-center space-x-1 text-ink-subtle text-[10px]">
            <Calendar className="w-3 h-3 text-brand" />
            <span>{dataPoint.date}</span>
          </div>
          <p className="text-sm font-bold text-ink">
            {dataPoint.value} <span className="text-xs font-normal text-ink-subtle">{unit}</span>
          </p>
          {dataPoint.ref_low !== null && dataPoint.ref_high !== null && (
            <p className="text-[10px] text-status-success">
              Normal Target: {dataPoint.ref_low} – {dataPoint.ref_high} {unit}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto print:max-w-none print:space-y-4 print:p-0">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4 print:border-none print:shadow-none print:p-0">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-brand text-white shadow-xs print:hidden">
              <TrendingUp className="w-5 h-5" />
            </div>
            <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink">
              MedTrend Longitudinal Trajectory Analytics
            </h2>
          </div>
          <p className="text-xs text-ink-muted mt-1 font-sans">
            Tracks longitudinal drift across your private diagnostic reports, calculates monthly rates of change, flags boundary crossings, and correlates with global clinical disease paths.
          </p>
        </div>

        <div className="flex items-center space-x-2 print:hidden self-start md:self-auto">
          {/* U5: Print for My Doctor Button */}
          <button
            type="button"
            onClick={handlePrint}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-card-border bg-canvas text-xs font-heading font-semibold text-ink-muted hover:text-ink transition-colors shadow-2xs cursor-pointer"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print for my doctor</span>
          </button>

          <button
            type="button"
            onClick={fetchTrends}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-brand-border bg-brand-surface text-xs font-heading font-bold text-brand hover:bg-brand hover:text-white transition-all shadow-2xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh Analytics</span>
          </button>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs print:hidden">
          <EcgLoader
            label="Evaluating Longitudinal Lab Trajectories..."
            sublabel="Traversing private Kùzu database, aligning canonical units, computing rate of change, and evaluating boundary shifts..."
          />
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="MedTrend Analysis Error"
          message={errorMsg}
          onRetry={fetchTrends}
        />
      )}

      {/* Main Results */}
      {data && !isLoading && (
        <>
          {/* Summary Overview Card */}
          <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-3 print:border-gray-200">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-card-border">
              <h3 className="text-xs font-heading font-bold text-ink uppercase tracking-wider">
                Longitudinal Overview Summary
              </h3>
              <div className="flex items-center space-x-2">
                <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-canvas text-ink border border-card-border">
                  {data.trends.length} Tests Evaluated
                </span>
                {data.significant_count > 0 && (
                  <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-status-caution-bg text-status-caution border border-status-caution/30 flex items-center space-x-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>{data.significant_count} Notable Shifts</span>
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-ink leading-relaxed whitespace-pre-line font-sans">
              {data.summary_text}
            </p>
          </div>

          {/* Longitudinal Test Trajectories Table */}
          {data.trends.length === 0 ? (
            <EmptyState
              title="No Longitudinal Trends Available"
              description="Upload at least two diagnostic reports to automatically track multi-point trajectories, drift velocity, and target boundaries."
            />
          ) : (
            <>
              <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-4 print:border-gray-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-heading font-bold text-ink">
                    All Tracked Laboratory Trajectories ({data.trends.length})
                  </h3>
                  <span className="text-[11px] font-mono text-ink-subtle">
                    Chronological Delta Analysis
                  </span>
                </div>

                <div className="overflow-x-auto rounded-xl border border-card-border">
                  <table className="w-full text-left text-xs font-sans">
                    <thead className="bg-canvas border-b border-card-border font-heading font-bold text-ink-muted text-[11px] uppercase tracking-wider">
                      <tr>
                        <th className="py-3 px-4">Test Name</th>
                        <th className="py-3 px-4">Earliest</th>
                        <th className="py-3 px-4">Latest</th>
                        <th className="py-3 px-4">Total Shift (Δ)</th>
                        <th className="py-3 px-4">Rate / Month</th>
                        <th className="py-3 px-4">Direction</th>
                        <th className="py-3 px-4">Clinical Significance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-card-border/60 font-mono">
                      {data.trends.map((item) => {
                        const dirProps = getTrendDirectionProps(item.direction);
                        const isResolved = item.direction === 'resolved';

                        return (
                          <tr
                            key={item.test_name}
                            className={`hover:bg-canvas/50 transition-colors ${
                              item.is_significant ? (isResolved ? 'bg-status-success-bg/20' : 'bg-status-caution-bg/20') : ''
                            }`}
                          >
                            <td className="py-3.5 px-4 font-sans font-bold text-ink">
                              {item.test_name}
                            </td>
                            <td className="py-3.5 px-4 text-ink-muted">
                              <span className="font-bold text-ink">{item.earliest_value ?? '—'}</span>{' '}
                              <span className="text-[10px]">{item.canonical_unit}</span>
                              <span className="block text-[10px] text-ink-subtle">{item.earliest_date || '—'}</span>
                            </td>
                            <td className="py-3.5 px-4 text-ink-muted">
                              <span className="font-bold text-ink">{item.latest_value ?? '—'}</span>{' '}
                              <span className="text-[10px]">{item.canonical_unit}</span>
                              <span className="block text-[10px] text-ink-subtle">{item.latest_date || '—'}</span>
                            </td>
                            <td className="py-3.5 px-4 font-bold tabular-nums">
                              {item.delta != null ? (
                                <span className={item.delta > 0 ? 'text-brand' : item.delta < 0 ? 'text-status-info' : 'text-ink-muted'}>
                                  {item.delta > 0 ? `+${item.delta}` : item.delta} {item.canonical_unit}
                                </span>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td className="py-3.5 px-4 text-ink-muted tabular-nums">
                              {item.rate_per_month != null
                                ? `${item.rate_per_month > 0 ? '+' : ''}${item.rate_per_month} /mo`
                                : '—'}
                            </td>
                            <td className="py-3.5 px-4">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-heading font-bold uppercase tracking-wider border ${dirProps.className}`}>
                                {dirProps.label}
                              </span>
                            </td>
                            <td className="py-3.5 px-4 font-sans">
                              {item.is_significant ? (
                                <div className="space-y-0.5">
                                  <div className="flex items-center space-x-1 font-bold text-[11px]">
                                    {isResolved ? (
                                      <span className="text-status-success flex items-center space-x-1">
                                        <CheckCircle2 className="w-3 h-3" />
                                        <span>Normalized Target</span>
                                      </span>
                                    ) : (
                                      <span className="text-status-caution flex items-center space-x-1">
                                        <AlertTriangle className="w-3 h-3" />
                                        <span>Notable Shift</span>
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-[11px] text-ink-muted">
                                    {item.significance_reason || '—'}
                                  </p>
                                </div>
                              ) : (
                                <span className="text-ink-subtle font-mono text-[11px]">Within Normal Baseline</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* U2: Sparkline Charts with Custom Tooltip, Reference Area & Clean X-Axis */}
              {data.trends.some((t) => t.is_significant && t.measurements.length >= 2) && (
                <div className="space-y-6">
                  <h3 className="text-sm font-heading font-bold text-ink">
                    Notable Trajectory Charts with Reference Bands
                  </h3>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 print:grid-cols-1">
                    {data.trends
                      .filter((t) => t.is_significant && t.measurements.length >= 2)
                      .map((t) => {
                        // Deduplicate measurements by report_id
                        const seenReports = new Set();
                        const uniqueMeasurements = t.measurements.filter((m) => {
                          if (seenReports.has(m.report_id)) return false;
                          seenReports.add(m.report_id);
                          return true;
                        });

                        const chartData = uniqueMeasurements.map((m) => ({
                          date: m.report_date,
                          value: m.value,
                          ref_low: m.ref_low,
                          ref_high: m.ref_high,
                        }));

                        const refLow = uniqueMeasurements[0]?.ref_low;
                        const refHigh = uniqueMeasurements[0]?.ref_high;
                        const firstDate = chartData[0]?.date;
                        const lastDate = chartData[chartData.length - 1]?.date;

                        return (
                          <div
                            key={t.test_name}
                            className="p-5 rounded-2xl border border-card-border bg-card shadow-xs space-y-4 print:border-gray-200"
                          >
                            <div className="flex items-center justify-between pb-2 border-b border-card-border">
                              <div>
                                <h4 className="font-heading font-bold text-sm text-ink">
                                  {t.test_name} Trajectory
                                </h4>
                                <p className="text-[11px] font-mono text-ink-muted">
                                  Unit: {t.canonical_unit} {t.rate_per_month != null ? `| Rate: ${t.rate_per_month}/mo` : ''}
                                </p>
                              </div>
                              <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-status-caution-bg text-status-caution rounded border border-status-caution/30 uppercase">
                                {t.direction}
                              </span>
                            </div>

                            {/* Recharts Sparkline with Shaded ReferenceArea and Custom Tooltip */}
                            <div className="h-56 w-full font-mono text-xs pt-2">
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData} margin={{ top: 15, right: 25, bottom: 20, left: 5 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-card-border)" opacity={0.6} />
                                  <XAxis
                                    dataKey="date"
                                    stroke="var(--color-ink-subtle)"
                                    fontSize={10}
                                    ticks={[firstDate, lastDate].filter(Boolean)}
                                  />
                                  <YAxis stroke="var(--color-ink-subtle)" fontSize={10} domain={['auto', 'auto']} />
                                  <Tooltip content={<CustomChartTooltip unit={t.canonical_unit} />} />

                                  {/* U2: Shaded ReferenceArea Band */}
                                  {refLow != null && refHigh != null && (
                                    <ReferenceArea
                                      y1={refLow}
                                      y2={refHigh}
                                      fill="#10b981"
                                      fillOpacity={0.12}
                                      stroke="none"
                                    />
                                  )}

                                  {refLow != null && (
                                    <ReferenceLine
                                      y={refLow}
                                      stroke="#10B981"
                                      strokeDasharray="4 4"
                                      label={{ value: `Low (${refLow})`, fill: '#10B981', fontSize: 9 }}
                                    />
                                  )}
                                  {refHigh != null && (
                                    <ReferenceLine
                                      y={refHigh}
                                      stroke="#EF4444"
                                      strokeDasharray="4 4"
                                      label={{ value: `High (${refHigh})`, fill: '#EF4444', fontSize: 9 }}
                                    />
                                  )}
                                  <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="var(--color-brand)"
                                    strokeWidth={3}
                                    dot={{ r: 5, fill: 'var(--color-brand)' }}
                                    activeDot={{ r: 7 }}
                                  />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>

                            {/* Knowledge Graph Causes */}
                            {t.possible_causes && t.possible_causes.length > 0 && (
                              <div className="p-3 rounded-xl bg-canvas border border-card-border space-y-1.5">
                                <div className="flex items-center space-x-1 text-[11px] font-mono text-ink-subtle">
                                  <GitCommit className="w-3 h-3 text-brand" />
                                  <span>Associated Conditions (Knowledge Graph):</span>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                  {t.possible_causes.map((cause, cIdx) => (
                                    <span
                                      key={cIdx}
                                      className="px-2 py-0.5 text-[11px] font-sans font-medium rounded bg-card border border-card-border text-ink"
                                    >
                                      {cause.disease_name}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Mandatory Medical Disclaimer */}
          <DisclaimerFooter />
        </>
      )}
    </div>
  );
};
