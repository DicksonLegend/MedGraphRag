import React, { useState, useEffect } from 'react';
import {
  X,
  Image as ImageIcon,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Sun,
  Moon,
  Sparkles,
  Layers,
  Network,
  FileText,
  AlertCircle,
  CheckCircle2,
  Activity,
  MessageSquare,
  Lock,
  Clock,
  ShieldCheck,
  ChevronRight,
  RefreshCw,
  Info,
} from 'lucide-react';
import { VisualFindingsCard } from './VisualFindingsCard';
import { EcgLoader } from '../common/EcgLoader';
import { DiscrepancyAlertBanner } from '../common/DiscrepancyAlertBanner';
import { multimodalApi } from '../../api/multimodal';
import type { ImageAnalysisResult } from '../../api/types';

interface RadiologyReportDrawerProps {
  scan: ImageAnalysisResult | null;
  isOpen: boolean;
  onClose: () => void;
  onRunFullInterpretation: (scan: ImageAnalysisResult) => Promise<void>;
  isRunningFull: boolean;
  onAskInChat?: (scan: ImageAnalysisResult) => void;
}

export const RadiologyReportDrawer: React.FC<RadiologyReportDrawerProps> = ({
  scan,
  isOpen,
  onClose,
  onRunFullInterpretation,
  isRunningFull,
  onAskInChat,
}) => {
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [isInverted, setIsInverted] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'findings' | 'impression' | 'graph'>('findings');
  const [imageBlobUrl, setImageBlobUrl] = useState<string | null>(null);
  const [isLoadingImage, setIsLoadingImage] = useState<boolean>(false);
  const [isSlowInterpreting, setIsSlowInterpreting] = useState<boolean>(false);

  // FIX 1: Soft timeout listener for slow VLM interpretation (after 15s)
  useEffect(() => {
    let timer: any;
    if (isRunningFull) {
      setIsSlowInterpreting(false);
      timer = setTimeout(() => {
        setIsSlowInterpreting(true);
      }, 15000);
    } else {
      setIsSlowInterpreting(false);
    }
    return () => clearTimeout(timer);
  }, [isRunningFull]);

  // Load preview image blob on scan change
  useEffect(() => {
    if (!scan || !isOpen) {
      setImageBlobUrl(null);
      return;
    }

    let isMounted = true;
    setIsLoadingImage(true);

    multimodalApi
      .getPreviewBlob(scan.image_id)
      .then((blob) => {
        if (isMounted) {
          const url = URL.createObjectURL(blob);
          setImageBlobUrl(url);
        }
      })
      .catch(() => {
        if (isMounted) {
          setImageBlobUrl(null);
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingImage(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [scan?.image_id, isOpen]);

  if (!isOpen || !scan) {
    return null;
  }

  const toggleZoom = () => {
    setZoomLevel((prev) => (prev === 1 ? 1.5 : prev === 1.5 ? 2 : 1));
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end animate-fade-in">
      <div className="w-full max-w-4xl bg-canvas border-l border-edge flex flex-col h-full shadow-2xl overflow-hidden">
        {/* Drawer Header */}
        <div className="px-6 py-4 border-b border-edge flex items-center justify-between bg-canvas-card">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-teal-accent/10 border border-teal-accent/20 flex items-center justify-center text-teal-accent">
              <ImageIcon className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-ink truncate max-w-md">
                  {scan.filename || `Scan ${scan.image_id}`}
                </h2>
                <span className="text-[10px] font-mono uppercase bg-teal-accent/10 text-teal-accent px-2 py-0.5 rounded border border-teal-accent/20">
                  {scan.modality} • {scan.orientation}
                </span>
                <span className="text-[10px] font-mono bg-canvas-subtle text-ink-muted px-2 py-0.5 rounded border border-edge">
                  {scan.mode === 'full' ? 'Generative VLM' : 'Fast Triage'}
                </span>
              </div>
              <p className="text-xs text-ink-muted flex items-center gap-3 mt-0.5">
                <span>ID: {scan.image_id.slice(0, 8)}...</span>
                <span>Latency: {scan.processing_time_ms} ms</span>
                <span className="flex items-center gap-1 text-emerald-400">
                  <Lock className="w-3 h-3" /> AES-256-GCM Private
                </span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {onAskInChat && (
              <button
                onClick={() => onAskInChat(scan)}
                className="px-3 py-1.5 bg-teal-accent text-slate-900 text-xs font-semibold rounded-lg hover:bg-teal-accent/90 transition-all flex items-center gap-1.5 shadow-sm"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Ask in Chat
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-ink-muted hover:text-ink hover:bg-canvas-subtle rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* FIX 2: Permanent Privacy & Isolation Banner (Always visible for private scans) */}
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center justify-between gap-3 text-xs text-emerald-400 shadow-2xs">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 shrink-0 text-emerald-400" />
              <span>
                <strong className="text-emerald-300">Isolated Private Storage:</strong> Stored in your private encrypted store; never shared or used for training.
              </span>
            </div>
            <span className="text-[10px] font-mono bg-emerald-500/20 px-2 py-0.5 rounded border border-emerald-500/30 text-emerald-300 shrink-0">
              AES-256-GCM
            </span>
          </div>

          {/* 1. Image Viewer & Interactive Controls */}
          <div className="bg-black rounded-xl border border-edge/80 overflow-hidden shadow-inner flex flex-col items-center relative group">
            {/* Viewer Toolbar */}
            <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 bg-black/70 backdrop-blur-md px-2 py-1 rounded-lg border border-white/10 text-white text-xs">
              <button
                onClick={toggleZoom}
                className="p-1.5 hover:bg-white/20 rounded transition-colors flex items-center gap-1"
                title="Toggle Zoom (1x, 1.5x, 2x)"
              >
                <ZoomIn className="w-3.5 h-3.5" />
                <span className="font-mono text-[10px]">{zoomLevel}x</span>
              </button>
              <button
                onClick={() => setIsInverted(!isInverted)}
                className={`p-1.5 hover:bg-white/20 rounded transition-colors ${
                  isInverted ? 'text-amber-400' : 'text-white'
                }`}
                title="Invert Grayscale Contrast"
              >
                <Sun className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Image Canvas */}
            <div className="w-full h-80 flex items-center justify-center overflow-auto p-4 bg-zinc-950">
              {isLoadingImage ? (
                <EcgLoader label="Loading High-Res Scan Preview..." />
              ) : imageBlobUrl ? (
                <img
                  src={imageBlobUrl}
                  alt={scan.filename}
                  className={`max-h-full object-contain transition-transform duration-200 ${
                    isInverted ? 'invert' : ''
                  }`}
                  style={{ transform: `scale(${zoomLevel})` }}
                />
              ) : (
                <div className="text-zinc-500 text-xs flex flex-col items-center gap-2">
                  <ImageIcon className="w-8 h-8 opacity-40" />
                  <span>Preview loading via AES-256-GCM private decrypt...</span>
                </div>
              )}
            </div>

            {/* Image Footer Caption */}
            <div className="w-full px-4 py-2 bg-zinc-900 border-t border-white/5 flex items-center justify-between text-[11px] text-zinc-400 font-mono">
              <span>{scan.filename}</span>
              <span>Anatomy: {scan.body_part || 'Chest'} • View: {scan.orientation}</span>
            </div>
          </div>

          {/* 2. Navigation Tabs */}
          <div className="flex border-b border-edge gap-6 text-sm font-medium">
            <button
              onClick={() => setActiveTab('findings')}
              className={`pb-2.5 flex items-center gap-2 transition-colors relative ${
                activeTab === 'findings' ? 'text-teal-accent' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <Activity className="w-4 h-4" />
              Pathology Triage (14 Classes)
              {activeTab === 'findings' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-accent rounded-full" />
              )}
            </button>

            <button
              onClick={() => setActiveTab('impression')}
              className={`pb-2.5 flex items-center gap-2 transition-colors relative ${
                activeTab === 'impression' ? 'text-teal-accent' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              Generative Impression &amp; Plan
              {scan.mode === 'full' && (
                <span className="w-2 h-2 rounded-full bg-teal-accent" />
              )}
              {activeTab === 'impression' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-accent rounded-full" />
              )}
            </button>

            <button
              onClick={() => setActiveTab('graph')}
              className={`pb-2.5 flex items-center gap-2 transition-colors relative ${
                activeTab === 'graph' ? 'text-teal-accent' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <Network className="w-4 h-4" />
              Knowledge Graph Links
              {scan.has_graph_links && (
                <span className="text-[10px] font-mono bg-teal-accent/10 text-teal-accent px-1.5 py-0.2 rounded">
                  {scan.graph_paths.length}
                </span>
              )}
              {activeTab === 'graph' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-accent rounded-full" />
              )}
            </button>
          </div>

          {/* Cross-Modal Discrepancy Alerts (F1) */}
          <DiscrepancyAlertBanner alerts={scan.discrepancy_alerts} />

          {/* 3. Tab Contents */}

          {/* TAB 1: Visual Findings Triage */}
          {activeTab === 'findings' && (
            <div className="space-y-4">
              <VisualFindingsCard
                findings={scan.findings_detailed}
                confidenceScores={scan.confidence_scores}
                modelUsed={scan.model_used}
                refusalTier={scan.refusal_tier}
              />

              {/* Triage summary callout */}
              <div className="bg-canvas-card border border-edge rounded-xl p-4 space-y-2">
                <h4 className="text-xs font-semibold text-ink uppercase tracking-wider">
                  Screening Summary
                </h4>
                <p className="text-sm text-ink-muted leading-relaxed">
                  {scan.impression}
                </p>
              </div>

              {/* Action Banner to upgrade to Full Interpretation */}
              {scan.mode !== 'full' && (
                <div className="p-4 bg-teal-accent/5 border border-teal-accent/20 rounded-xl space-y-3">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h4 className="text-sm font-semibold text-ink flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-teal-accent" />
                        Request Full Generative Interpretation
                      </h4>
                      <p className="text-xs text-ink-muted mt-0.5">
                        Runs Qwen2-VL-2B Vision-Language Model on CPU to synthesize formal radiological findings, impression, and recommendations.
                      </p>
                    </div>
                    <button
                      onClick={() => onRunFullInterpretation(scan)}
                      disabled={isRunningFull}
                      className="px-4 py-2 bg-teal-accent text-slate-900 text-xs font-semibold rounded-lg hover:bg-teal-accent/90 disabled:opacity-50 transition-all flex items-center gap-2 whitespace-nowrap shadow-sm"
                    >
                      {isRunningFull ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          Generating VLM...
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5" />
                          Run Qwen2-VL (CPU)
                        </>
                      )}
                    </button>
                  </div>

                  {/* FIX 1: Non-blocking slow notice after 15s */}
                  {isRunningFull && isSlowInterpreting && (
                    <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs text-amber-300 flex items-center gap-2 animate-fade-in">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400 shrink-0" />
                      <span>Still interpreting… complex films can take a little longer.</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Generative Impression */}
          {activeTab === 'impression' && (
            <div className="space-y-5">
              {scan.mode !== 'full' ? (
                <div className="bg-canvas-card border border-edge rounded-xl p-8 text-center space-y-4">
                  <div className="w-12 h-12 rounded-full bg-teal-accent/10 text-teal-accent flex items-center justify-center mx-auto">
                    <Sparkles className="w-6 h-6 animate-pulse" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-ink">
                      Full Generative Interpretation Not Yet Executed
                    </h3>
                    <p className="text-xs text-ink-muted max-w-md mx-auto mt-1">
                      Fast zero-shot triage is complete. Click below to generate formal structured radiological impressions and clinical recommendations using Qwen2-VL-2B.
                    </p>
                  </div>
                  <button
                    onClick={() => onRunFullInterpretation(scan)}
                    disabled={isRunningFull}
                    className="px-5 py-2.5 bg-teal-accent text-slate-900 text-sm font-semibold rounded-xl hover:bg-teal-accent/90 disabled:opacity-50 transition-all inline-flex items-center gap-2 shadow-md"
                  >
                    {isRunningFull ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Generating (CPU Isolated)...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Generate Full Radiology Report
                      </>
                    )}
                  </button>

                  {/* FIX 1: Non-blocking slow notice after 15s */}
                  {isRunningFull && isSlowInterpreting && (
                    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-300 flex items-center justify-center gap-2 animate-fade-in max-w-md mx-auto">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400 shrink-0" />
                      <span>Still interpreting… complex films can take a little longer.</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Generated Report Card */}
                  <div className="bg-canvas-card border border-edge rounded-xl p-5 space-y-4 shadow-sm">
                    <div className="flex items-center justify-between border-b border-edge pb-3">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-teal-accent" />
                        <h3 className="text-sm font-semibold text-ink">
                          Formal Generative Radiology Impression
                        </h3>
                      </div>
                      <span className="text-[11px] font-mono bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">
                        Tier: {scan.refusal_tier}
                      </span>
                    </div>

                    <div className="p-4 bg-canvas-subtle/60 rounded-lg border border-edge font-sans text-xs text-ink leading-relaxed whitespace-pre-wrap">
                      {scan.impression}
                    </div>

                    {/* Recommendations */}
                    {scan.recommendations && scan.recommendations.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-edge">
                        <h4 className="text-xs font-semibold text-ink uppercase tracking-wider flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-teal-accent" />
                          Clinical Recommendations
                        </h4>
                        <ul className="space-y-1.5">
                          {scan.recommendations.map((rec, idx) => (
                            <li key={idx} className="text-xs text-ink-muted flex items-start gap-2">
                              <span className="text-teal-accent font-mono">•</span>
                              <span>{rec}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Knowledge Graph Links (A3) */}
          {activeTab === 'graph' && (
            <div className="space-y-4">
              {/* FIX 3: Limitation Note */}
              <div className="p-3 bg-slate-500/10 border border-slate-500/20 rounded-xl text-xs text-ink-muted flex items-start gap-2">
                <Info className="w-4 h-4 text-teal-accent shrink-0 mt-0.5" />
                <span>
                  <strong>Study Linkage Coverage:</strong> Report linkage currently matches 48/100 sample studies; unmatched scans still return visual findings but without a linked report.
                </span>
              </div>

              {scan.has_graph_links && scan.graph_paths.length > 0 ? (
                <div className="space-y-3">
                  <div className="p-3 bg-teal-accent/5 border border-teal-accent/20 rounded-lg text-xs text-teal-accent flex items-center gap-2">
                    <Network className="w-4 h-4 flex-shrink-0" />
                    <span>{scan.graph_notice || 'Matched OpenI knowledge graph entities.'}</span>
                  </div>

                  <div className="grid grid-cols-1 gap-3">
                    {scan.graph_paths.map((gp, idx) => (
                      <div key={idx} className="bg-canvas-card border border-edge rounded-xl p-4 space-y-3 shadow-sm">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-semibold text-ink capitalize">
                              {gp.finding_label}
                            </span>
                            <span className={`text-[10px] font-mono px-2 py-0.2 rounded border ${
                              gp.finding_negated
                                ? 'bg-slate-500/20 text-slate-300 border-slate-500/30'
                                : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            }`}>
                              {gp.finding_negated ? 'FINDING_NEGATES' : 'IMAGE_SHOWS'}
                            </span>
                          </div>
                          <span className="text-[10px] font-mono text-ink-muted">
                            Study: {gp.source_image_id}
                          </span>
                        </div>

                        {gp.matched_reports && gp.matched_reports.length > 0 && (
                          <div className="space-y-1.5 pl-3 border-l-2 border-teal-accent/40">
                            <span className="text-[11px] font-semibold text-ink-muted">
                              Cross-linked OpenI Radiology Report Snippet:
                            </span>
                            {gp.matched_reports.map((rep, rIdx) => (
                              <p key={rIdx} className="text-xs text-ink-muted/90 italic bg-canvas-subtle p-2.5 rounded border border-edge/60">
                                &quot;{rep.text_snippet}&quot;
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-8 bg-canvas-card border border-edge rounded-xl text-center space-y-3">
                  <div className="w-10 h-10 rounded-full bg-slate-500/10 text-slate-400 flex items-center justify-center mx-auto">
                    <Lock className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-ink">
                      No Linked Knowledge Graph Report
                    </h4>
                    <p className="text-xs text-ink-muted max-w-sm mx-auto mt-1">
                      Report linkage currently matches 48/100 sample studies; unmatched scans still return visual findings but without a linked report. Private scans are stored in isolated AES-256-GCM encrypted private store.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
