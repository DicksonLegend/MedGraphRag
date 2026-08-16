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
} from 'recharts';
import {
  TrendingUp,
  AlertTriangle,
  Activity,
  ArrowRight,
  RefreshCw,
  Sparkles,
  GitCommit,
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

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-brand text-white shadow-xs">
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

        <button
          onClick={fetchTrends}
          className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-card-border bg-canvas text-xs font-heading font-semibold text-ink-muted hover:text-ink transition-colors shadow-2xs self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Analytics</span>
        </button>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs">
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
          <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-3">
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
                    <span>{data.significant_count} Significant Shifts</span>
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-ink leading-relaxed whitespace-pre-line font-sans">
              {data.summary_text}
            </p>
          </div>

          {/* If No Trends Found */}
          {data.trends.length === 0 ? (
            <EmptyState
              title="No Longitudinal Lab Trends Found"
              description="Upload two or more diagnostic lab reports in the Diagnostic Reports tab to view longitudinal trajectories and rates of change."
              actionLabel="Go to Reports"
              onAction={() => window.location.href = '/reports'}
            />
          ) : (
            <>
              {/* Trends Data Table */}
              <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-4">
                <h3 className="text-sm font-heading font-bold text-ink">
                  Lab Test Trajectory Summary
                </h3>

                <div className="overflow-x-auto rounded-xl border border-card-border">
                  <table className="w-full text-left text-xs font-sans">
                    <thead className="bg-canvas border-b border-card-border text-ink font-heading font-bold">
                      <tr>
                        <th className="px-4 py-3">Lab Test</th>
                        <th className="px-4 py-3">Chronological Trajectory</th>
                        <th className="px-4 py-3">Absolute Delta (Δ)</th>
                        <th className="px-4 py-3">Rate / Month</th>
                        <th className="px-4 py-3">Direction</th>
                        <th className="px-4 py-3">Clinical Significance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-card-border/60">
                      {data.trends.map((item) => {
                        const dirProps = getTrendDirectionProps(item.direction);
                        return (
                          <tr
                            key={item.test_name}
                            className={`transition-colors ${
                              item.is_significant
                                ? 'bg-status-caution-bg/20 hover:bg-status-caution-bg/30'
                                : 'hover:bg-canvas/50'
                            }`}
                          >
                            <td className="px-4 py-3 font-heading font-bold text-ink">
                              {item.test_name}
                            </td>
                            <td className="px-4 py-3 font-mono">
                              {item.earliest_value != null && item.latest_value != null ? (
                                <span className="flex items-center space-x-1.5 tabular-nums">
                                  <span className="text-ink-muted">{item.earliest_value}</span>
                                  <ArrowRight className="w-3 h-3 text-ink-subtle" />
                                  <strong className="text-ink font-bold">{item.latest_value}</strong>
                                  <span className="text-ink-subtle text-[11px]">{item.canonical_unit}</span>
                                </span>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td className="px-4 py-3 font-mono font-bold text-ink tabular-nums">
                              {item.delta != null
                                ? `${item.delta > 0 ? '+' : ''}${item.delta.toFixed(2)} ${item.canonical_unit}`
                                : '—'}
                            </td>
                            <td className="px-4 py-3 font-mono tabular-nums text-ink">
                              {item.rate_per_month != null
                                ? `${item.rate_per_month > 0 ? '+' : ''}${item.rate_per_month.toFixed(2)} / mo`
                                : '—'}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-mono font-semibold border ${dirProps.className}`}>
                                {dirProps.label}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              {item.is_significant ? (
                                <div className="space-y-0.5">
                                  <div className="flex items-center space-x-1 text-status-caution font-heading font-bold text-[11px]">
                                    <AlertTriangle className="w-3 h-3" />
                                    <span>Notable Shift</span>
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

              {/* Sparkline Charts for Significant Shifts */}
              {data.trends.some((t) => t.is_significant && t.measurements.length >= 2) && (
                <div className="space-y-6">
                  <h3 className="text-sm font-heading font-bold text-ink">
                    Notable Trajectory Charts with Reference Bands
                  </h3>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {data.trends
                      .filter((t) => t.is_significant && t.measurements.length >= 2)
                      .map((t) => {
                        const chartData = t.measurements.map((m) => ({
                          date: m.report_date,
                          value: m.value,
                          ref_low: m.ref_low,
                          ref_high: m.ref_high,
                        }));

                        const refLow = t.measurements[0]?.ref_low;
                        const refHigh = t.measurements[0]?.ref_high;

                        return (
                          <div
                            key={t.test_name}
                            className="p-5 rounded-2xl border border-card-border bg-card shadow-xs space-y-4"
                          >
                            <div className="flex items-center justify-between pb-2 border-b border-card-border">
                              <div>
                                <h4 className="font-heading font-bold text-sm text-ink">
                                  {t.test_name} Trajectory
                                </h4>
                                <p className="text-[11px] font-mono text-ink-muted">
                                  Unit: {t.canonical_unit} | Rate: {t.rate_per_month?.toFixed(2)}/mo
                                </p>
                              </div>
                              <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-status-caution-bg text-status-caution rounded border border-status-caution/30 uppercase">
                                {t.direction}
                              </span>
                            </div>

                            {/* Recharts Sparkline */}
                            <div className="h-52 w-full font-mono text-xs pt-2">
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-card-border)" opacity={0.6} />
                                  <XAxis dataKey="date" stroke="var(--color-ink-subtle)" fontSize={10} />
                                  <YAxis stroke="var(--color-ink-subtle)" fontSize={10} domain={['auto', 'auto']} />
                                  <Tooltip
                                    contentStyle={{
                                      backgroundColor: 'var(--color-card)',
                                      borderColor: 'var(--color-card-border)',
                                      borderRadius: '8px',
                                      color: 'var(--color-ink)',
                                      fontSize: '11px',
                                    }}
                                  />
                                  {refLow != null && (
                                    <ReferenceLine
                                      y={refLow}
                                      stroke="#10B981"
                                      strokeDasharray="4 4"
                                      label={{ value: `Ref Low (${refLow})`, fill: '#10B981', fontSize: 9 }}
                                    />
                                  )}
                                  {refHigh != null && (
                                    <ReferenceLine
                                      y={refHigh}
                                      stroke="#EF4444"
                                      strokeDasharray="4 4"
                                      label={{ value: `Ref High (${refHigh})`, fill: '#EF4444', fontSize: 9 }}
                                    />
                                  )}
                                  <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="var(--color-brand)"
                                    strokeWidth={3}
                                    dot={{ r: 4, fill: 'var(--color-brand)' }}
                                    activeDot={{ r: 6 }}
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
