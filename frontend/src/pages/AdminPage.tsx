import React, { useState, useEffect } from 'react';
import { healthApi } from '../api/health';
import type { HealthResponse } from '../api/types';
import { useAuthStore } from '../stores/authStore';
import { EcgLoader } from '../components/common/EcgLoader';
import { DisclaimerFooter } from '../components/common/DisclaimerFooter';
import { ErrorState } from '../components/common/ErrorState';
import {
  Shield,
  Server,
  Database,
  Cpu,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Lock,
} from 'lucide-react';

export const AdminPage: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { user_id, role, expires_in_minutes } = useAuthStore();

  const fetchHealth = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await healthApi.getHealth();
      setHealth(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to retrieve system component telemetry.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-brand text-white shadow-xs">
              <Shield className="w-5 h-5" />
            </div>
            <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink">
              System Administration & Readiness Console
            </h2>
          </div>
          <p className="text-xs text-ink-muted mt-1 font-sans">
            Real-time component health checks, session metadata inspection, and system architecture status.
          </p>
        </div>

        <button
          onClick={fetchHealth}
          className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-card-border bg-canvas text-xs font-heading font-semibold text-ink-muted hover:text-ink transition-colors shadow-2xs self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Readiness</span>
        </button>
      </div>

      {/* Mandatory Scope Boundary Notice */}
      <div className="p-5 rounded-2xl border border-brand-border bg-brand-surface text-ink space-y-2">
        <div className="flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-brand" />
          <h3 className="font-heading font-bold text-xs uppercase tracking-wider text-brand">
            Admin Capabilities & Scope Boundary
          </h3>
        </div>
        <p className="text-xs leading-relaxed text-ink-muted font-sans">
          <strong>Global Ingestion Scope:</strong> Admin runtime global knowledge base re-indexing and document ingestion is <strong>DEFERRED to v2</strong>. The v1 global index (FAISS vector store and Kùzu graph) is mounted strictly <strong>READ-ONLY</strong> to guarantee deterministic retrieval latency and GPU memory protection.
        </p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="p-8 rounded-2xl border border-card-border bg-card shadow-xs">
          <EcgLoader
            label="Probing System Components..."
            sublabel="Checking FAISS vector store, Kùzu graph database, and GPU LLM weight residency..."
          />
        </div>
      )}

      {/* Error State */}
      {errorMsg && (
        <ErrorState
          title="Component Probe Failure"
          message={errorMsg}
          onRetry={fetchHealth}
        />
      )}

      {/* Component Telemetry Cards */}
      {health && !isLoading && (
        <div className="space-y-6 animate-fade-in">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Component 1: Retrieval Vector Index */}
            <div className="p-5 rounded-2xl border border-card-border bg-card shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Database className="w-4 h-4 text-brand" />
                  <h4 className="font-heading font-bold text-xs text-ink uppercase">
                    Vector Retrieval
                  </h4>
                </div>
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-status-success-bg text-status-success border border-status-success/30">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>{health.components.retrieval}</span>
                </span>
              </div>
              <p className="text-xs text-ink-muted">
                MedCPT 768-dim FAISS IndexFlatIP store status.
              </p>
            </div>

            {/* Component 2: Kùzu Graph Engine */}
            <div className="p-5 rounded-2xl border border-card-border bg-card shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Server className="w-4 h-4 text-brand" />
                  <h4 className="font-heading font-bold text-xs text-ink uppercase">
                    Graph Engine
                  </h4>
                </div>
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-status-success-bg text-status-success border border-status-success/30">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>{health.components.graph}</span>
                </span>
              </div>
              <p className="text-xs text-ink-muted">
                Kùzu biomedical knowledge graph database status.
              </p>
            </div>

            {/* Component 3: LLM Weight State */}
            <div className="p-5 rounded-2xl border border-card-border bg-card shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Cpu className="w-4 h-4 text-brand" />
                  <h4 className="font-heading font-bold text-xs text-ink uppercase">
                    LLM GPU Weights
                  </h4>
                </div>
                <span
                  className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border ${
                    health.components.llm_loaded
                      ? 'bg-status-success-bg text-status-success border-status-success/30'
                      : 'bg-canvas text-ink-muted border-card-border'
                  }`}
                >
                  <span>{health.components.llm_loaded ? 'VRAM Resident' : 'Lazy Idle'}</span>
                </span>
              </div>
              <p className="text-xs text-ink-muted">
                Qwen2.5-7B GGUF weights ({health.components.llm_loaded ? 'active in GPU memory' : 'unloaded, 0 MB VRAM'}).
              </p>
            </div>
          </div>

          {/* Session Details */}
          <div className="p-6 rounded-2xl border border-card-border bg-card shadow-xs space-y-4">
            <h3 className="text-sm font-heading font-bold text-ink">
              Active Administrative Session
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 rounded-xl bg-canvas border border-card-border">
                <span className="block text-[10px] text-ink-subtle uppercase">Authenticated Admin</span>
                <span className="font-bold text-ink">{user_id || '—'}</span>
              </div>
              <div className="p-3 rounded-xl bg-canvas border border-card-border">
                <span className="block text-[10px] text-ink-subtle uppercase">Role Privilege</span>
                <span className="font-bold text-brand uppercase">{role || '—'}</span>
              </div>
              <div className="p-3 rounded-xl bg-canvas border border-card-border">
                <span className="block text-[10px] text-ink-subtle uppercase">API Version</span>
                <span className="font-bold text-ink">{health.version || '1.0.0'}</span>
              </div>
              <div className="p-3 rounded-xl bg-canvas border border-card-border">
                <span className="block text-[10px] text-ink-subtle uppercase">Token TTL</span>
                <span className="font-bold text-ink tabular-nums">{expires_in_minutes || '—'} min</span>
              </div>
            </div>
          </div>

          {/* Disclaimer */}
          <DisclaimerFooter />
        </div>
      )}
    </div>
  );
};
