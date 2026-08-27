import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';
import {
  Activity,
  ShieldCheck,
  UserCheck,
  Sparkles,
  Sun,
  Moon,
  Lock,
  User,
  Eye,
  EyeOff,
  Database,
  Network,
  ArrowRight,
  HeartPulse,
  Key,
  ShieldAlert,
} from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('demo_user');
  const [password, setPassword] = useState('password123');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { login, guestLogin, isLoading } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await login({ username, password });
      navigate('/chat');
    } catch (err: any) {
      setErrorMsg(err.message || 'Invalid credentials. Please verify your login details.');
    }
  };

  const handleGuestLogin = async () => {
    setErrorMsg(null);
    try {
      await guestLogin();
      navigate('/chat');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to initiate guest session.');
    }
  };

  const setCredentials = (user: string, pass: string) => {
    setUsername(user);
    setPassword(pass);
    setErrorMsg(null);
  };

  return (
    <div className="relative h-screen max-h-screen w-full flex flex-col justify-between items-center p-3 sm:p-4 overflow-hidden bg-canvas text-ink transition-colors duration-500 font-sans select-none">
      {/* ── Background Decorative Ambient Layer ── */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {/* Soft Radial Ambient Glow Spheres */}
        <div
          className="absolute -top-20 -left-20 w-80 h-80 rounded-full bg-brand/15 dark:bg-brand/20 blur-[100px] animate-pulse"
          style={{ animationDuration: '7s' }}
        />
        <div
          className="absolute -bottom-20 -right-20 w-96 h-96 rounded-full bg-brand-secondary/15 dark:bg-brand-secondary/20 blur-[120px] animate-pulse"
          style={{ animationDuration: '10s' }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[38rem] h-[38rem] rounded-full bg-brand/5 blur-[140px]" />

        {/* Precision Medical Isometric Grid Pattern */}
        <svg
          className="absolute inset-0 w-full h-full opacity-35 dark:opacity-20"
          xmlns="http://www.w3.org/2000/svg"
          width="100%"
          height="100%"
        >
          <defs>
            <pattern id="medical-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="currentColor"
                strokeWidth="0.65"
                className="text-brand/40 dark:text-brand/35"
              />
              <circle cx="40" cy="0" r="1.2" className="fill-brand/50 dark:fill-brand/60" />
              <circle cx="0" cy="40" r="1.2" className="fill-brand/50 dark:fill-brand/60" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#medical-grid)" />
        </svg>

        {/* Ambient Medical ECG Waveform */}
        <div className="absolute bottom-0 left-0 right-0 h-24 opacity-25 dark:opacity-35 flex items-end">
          <svg className="w-full h-16" viewBox="0 0 1200 120" fill="none" preserveAspectRatio="none">
            <path
              d="M0,60 L200,60 L220,60 L235,15 L245,105 L260,35 L270,75 L285,60 L500,60 L520,60 L535,10 L545,110 L560,30 L570,80 L585,60 L800,60 L820,60 L835,15 L845,105 L860,35 L870,75 L885,60 L1200,60"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-brand animate-ecg-pulse"
              style={{ strokeDasharray: '600', strokeDashoffset: '600' }}
            />
          </svg>
        </div>
      </div>

      {/* ── Top Header Controls & Live Telemetry Pill ── */}
      <header className="w-full max-w-4xl flex items-center justify-between z-20 shrink-0 pt-1">
        <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-card/85 backdrop-blur-xl border border-card-border shadow-xs">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-success opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-status-success" />
          </span>
          <span className="text-[10px] sm:text-[11px] font-mono font-semibold text-ink-muted uppercase tracking-wider">
            Local Cluster RTX 3050 Online
          </span>
        </div>

        {/* Theme Toggle Button with Glassmorphism */}
        <button
          type="button"
          onClick={toggleTheme}
          className="group p-2 rounded-full bg-card/85 backdrop-blur-xl border border-card-border text-ink hover:text-brand hover:scale-105 active:scale-95 focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-hidden transition-all shadow-xs cursor-pointer"
          title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
          aria-label="Toggle Theme"
        >
          {theme === 'light' ? (
            <Moon className="w-4 h-4 text-brand transition-transform duration-300 group-hover:-rotate-12" />
          ) : (
            <Sun className="w-4 h-4 text-status-caution transition-transform duration-300 group-hover:rotate-45" />
          )}
        </button>
      </header>

      {/* ── Center Main Content Container ── */}
      <main className="relative z-10 w-full max-w-md my-auto flex flex-col items-center">
        {/* Brand Header */}
        <div className="text-center mb-3 space-y-1">
          <div className="inline-flex relative items-center justify-center p-2.5 rounded-2xl bg-brand text-white shadow-lg shadow-brand/25 border border-white/20 dark:border-brand/40 group mb-1">
            <Activity className="w-6 h-6 transition-transform duration-300 group-hover:scale-110" />
            <div className="absolute -inset-1 rounded-2xl bg-brand/30 blur-md -z-10 group-hover:blur-lg transition-all" />
          </div>

          <h1 className="text-2xl sm:text-3xl font-heading font-extrabold text-ink tracking-tight leading-none drop-shadow-xs">
            MedGraph
            <span className="bg-gradient-to-r from-brand via-brand-hover to-brand-secondary bg-clip-text text-transparent">
              RAG
            </span>
          </h1>

          <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-brand-surface border border-brand-border text-[9px] sm:text-[10px] font-mono font-semibold text-brand tracking-wider uppercase shadow-xs">
            <Sparkles className="w-2.5 h-2.5 text-brand" />
            <span>Self-Verifying Clinical AI</span>
            <span className="text-[8px] opacity-75 font-mono px-1 py-0.2 rounded bg-brand/10 border border-brand/20">v2.0.0</span>
          </div>
        </div>

        {/* ── Glassmorphism Login Card ── */}
        <div className="w-full rounded-2xl p-5 sm:p-6 bg-card/90 backdrop-blur-2xl border border-card-border shadow-xl dark:shadow-2xl dark:shadow-black/70 transition-all duration-300 relative">
          {/* Top Specular Glow Line */}
          <div className="absolute top-0 left-1/4 right-1/4 h-[1.5px] bg-gradient-to-r from-transparent via-brand/60 to-transparent" />

          {/* Error Alert Box */}
          {errorMsg && (
            <div
              className="mb-3 p-2.5 rounded-xl bg-status-danger-bg border border-status-danger/40 text-status-danger text-xs font-medium flex items-center space-x-2 animate-fade-in shadow-xs"
              role="alert"
            >
              <ShieldAlert className="w-4 h-4 shrink-0 text-status-danger" />
              <div className="flex-1 text-[11px]">{errorMsg}</div>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleLogin} className="space-y-3">
            {/* Username Input */}
            <div className="space-y-1">
              <label className="block text-[10px] sm:text-[11px] font-heading font-bold text-ink uppercase tracking-wider">
                Clinical Identifier / Username
              </label>
              <div className="relative rounded-xl shadow-inner">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-subtle">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                  className="w-full pl-9 pr-3.5 py-2 rounded-xl border border-card-border bg-canvas text-ink text-xs sm:text-sm font-mono placeholder:text-ink-subtle/60 focus:bg-card focus:border-brand focus:ring-2 focus:ring-brand focus-visible:outline-hidden transition-all shadow-2xs"
                  placeholder="demo_user or admin"
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="space-y-1">
              <div className="flex justify-between items-center">
                <label className="block text-[10px] sm:text-[11px] font-heading font-bold text-ink uppercase tracking-wider">
                  Passcode / Token
                </label>
                <span className="text-[9px] font-mono text-ink-subtle flex items-center space-x-1">
                  <Lock className="w-2.5 h-2.5 inline" />
                  <span>AES-256 Protected</span>
                </span>
              </div>
              <div className="relative rounded-xl shadow-inner">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-subtle">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="w-full pl-9 pr-9 py-2 rounded-xl border border-card-border bg-canvas text-ink text-xs sm:text-sm font-mono placeholder:text-ink-subtle/60 focus:bg-card focus:border-brand focus:ring-2 focus:ring-brand focus-visible:outline-hidden transition-all shadow-2xs"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-ink-subtle hover:text-ink focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-hidden rounded-md transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* Sign In Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-1 relative group overflow-hidden flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-heading font-bold text-white dark:text-[#0A1120] bg-brand hover:bg-brand-hover active:scale-[0.99] disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:outline-hidden transition-all shadow-md shadow-brand/25 cursor-pointer"
            >
              <div className="absolute inset-0 w-1/2 h-full bg-white/20 skew-x-12 -translate-x-full group-hover:translate-x-[300%] transition-transform duration-1000 ease-out pointer-events-none" />
              {isLoading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Verifying token…</span>
                </>
              ) : (
                <>
                  <UserCheck className="w-4 h-4" />
                  <span>Access Clinical Console</span>
                  <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative flex items-center justify-center my-3">
            <div className="border-t border-card-border w-full" />
            <span className="bg-card px-2.5 text-[9px] font-mono font-semibold text-ink-subtle uppercase tracking-wider whitespace-nowrap">
              Or Instant Access
            </span>
          </div>

          {/* Ephemeral Guest Button */}
          <button
            type="button"
            onClick={handleGuestLogin}
            disabled={isLoading}
            className="w-full group flex items-center justify-between py-2 px-3.5 rounded-xl text-xs font-heading font-semibold text-ink bg-canvas hover:bg-brand-surface hover:text-brand border border-card-border hover:border-brand-border active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-hidden transition-all cursor-pointer shadow-2xs"
          >
            <div className="flex items-center space-x-2">
              <div className="p-1 rounded-md bg-brand-surface text-brand group-hover:bg-brand group-hover:text-white dark:group-hover:text-[#0A1120] transition-colors">
                <Sparkles className="w-3 h-3" />
              </div>
              <span className="text-[11px] sm:text-xs">Guest Sandbox (Auto-Purged Session)</span>
            </div>
            <ArrowRight className="w-3.5 h-3.5 text-ink-subtle group-hover:text-brand group-hover:translate-x-0.5 transition-all" />
          </button>

          {/* 1-Click Demo Credentials Quick Fill */}
          <div className="mt-3 p-2.5 rounded-xl bg-brand-surface/60 border border-brand-border space-y-1.5 shadow-2xs">
            <div className="flex items-center justify-between text-[10px] font-heading font-bold text-ink">
              <div className="flex items-center space-x-1.5">
                <Key className="w-3 h-3 text-brand" />
                <span>Quick Fill Credentials:</span>
              </div>
              <span className="text-[9px] font-mono text-brand uppercase">1-Click</span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setCredentials('demo_user', 'password123')}
                className="flex flex-col text-left p-1.5 px-2.5 rounded-lg border border-card-border bg-card hover:border-brand hover:bg-brand-surface focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-hidden transition-all group cursor-pointer shadow-2xs"
              >
                <div className="flex items-center justify-between text-[10px] font-heading font-semibold text-ink group-hover:text-brand">
                  <span>Clinician Demo</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-brand opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <span className="text-[9px] font-mono text-ink-muted">demo_user</span>
              </button>

              <button
                type="button"
                onClick={() => setCredentials('admin', 'password123')}
                className="flex flex-col text-left p-1.5 px-2.5 rounded-lg border border-card-border bg-card hover:border-brand hover:bg-brand-surface focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-hidden transition-all group cursor-pointer shadow-2xs"
              >
                <div className="flex items-center justify-between text-[10px] font-heading font-semibold text-ink group-hover:text-brand">
                  <span>Administrator</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-brand opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <span className="text-[9px] font-mono text-ink-muted">admin</span>
              </button>
            </div>
          </div>
        </div>

        {/* ── Architecture Telemetry Indicators Directly Under Card ── */}
        <div className="grid grid-cols-3 gap-2 w-full mt-2.5 px-1">
          <div className="flex items-center justify-center space-x-1.5 py-1 px-2 rounded-lg bg-card/85 backdrop-blur-md border border-card-border text-[10px] font-mono text-ink-muted shadow-2xs">
            <Database className="w-3 h-3 text-brand shrink-0" />
            <span className="truncate">2.29M Vectors</span>
          </div>
          <div className="flex items-center justify-center space-x-1.5 py-1 px-2 rounded-lg bg-card/85 backdrop-blur-md border border-card-border text-[10px] font-mono text-ink-muted shadow-2xs">
            <Network className="w-3 h-3 text-brand-secondary shrink-0" />
            <span className="truncate">2.50M Graph</span>
          </div>
          <div className="flex items-center justify-center space-x-1.5 py-1 px-2 rounded-lg bg-card/85 backdrop-blur-md border border-card-border text-[10px] font-mono text-ink-muted shadow-2xs">
            <ShieldCheck className="w-3 h-3 text-status-success shrink-0" />
            <span className="truncate">AES-256 Enc</span>
          </div>
        </div>
      </main>

      {/* ── Regulatory Clinical Disclaimer at Absolute Bottom ── */}
      <footer className="w-full text-center shrink-0 z-20 pb-1">
        <div className="inline-flex items-center space-x-1.5 px-3 py-0.5 rounded-full bg-card/75 backdrop-blur-md border border-card-border text-[9px] sm:text-[10px] font-sans text-ink-subtle shadow-2xs">
          <HeartPulse className="w-3 h-3 text-brand shrink-0" />
          <span>Clinical Information Tool — Not a Diagnostic Device. Mandatory Physician Review.</span>
        </div>
      </footer>
    </div>
  );
};
