import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';
import { Activity, ShieldCheck, UserCheck, Sparkles, Sun, Moon, ArrowRight } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('demo_user');
  const [password, setPassword] = useState('password123');
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
      setErrorMsg(err.message || 'Invalid credentials.');
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

  return (
    <div className="min-h-screen flex flex-col justify-center items-center p-4 bg-canvas text-ink transition-colors duration-200">
      {/* Top Theme Switcher */}
      <div className="absolute top-4 right-4">
        <button
          onClick={toggleTheme}
          className="p-2.5 rounded-xl border border-card-border bg-card text-ink hover:bg-canvas transition-colors shadow-2xs"
          title="Toggle Theme"
        >
          {theme === 'light' ? <Moon className="w-4 h-4 text-brand" /> : <Sun className="w-4 h-4 text-status-caution" />}
        </button>
      </div>

      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex p-3 rounded-2xl bg-brand text-white shadow-md mb-2">
            <Activity className="w-8 h-8" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-heading font-extrabold text-ink tracking-tight">
            MedGraph<span className="text-brand">RAG</span>
          </h1>
          <p className="text-xs sm:text-sm text-ink-muted">
            Clinical Hybrid Vector-Graph Intelligence & Decision Support
          </p>
        </div>

        {/* Login Card */}
        <div className="p-6 sm:p-8 rounded-2xl border border-card-border bg-card shadow-lg backdrop-blur-md space-y-6">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-status-danger-bg border border-status-danger/30 text-status-danger text-xs font-semibold" role="alert">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <label className="block text-xs font-heading font-bold text-ink uppercase tracking-wider">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 rounded-xl border border-card-border bg-canvas text-ink text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand transition-colors"
                placeholder="demo_user or admin"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-heading font-bold text-ink uppercase tracking-wider">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 rounded-xl border border-card-border bg-canvas text-ink text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand transition-colors"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-xl text-sm font-heading font-bold text-white bg-brand hover:bg-brand-hover active:scale-[0.99] disabled:opacity-50 transition-all shadow-md"
            >
              <UserCheck className="w-4 h-4" />
              <span>{isLoading ? 'Authenticating...' : 'Sign In'}</span>
            </button>
          </form>

          <div className="relative flex items-center justify-center my-4">
            <div className="border-t border-card-border w-full" />
            <span className="bg-card px-3 text-[11px] font-mono text-ink-subtle uppercase">Or</span>
          </div>

          {/* Ephemeral Guest Button */}
          <button
            type="button"
            onClick={handleGuestLogin}
            disabled={isLoading}
            className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl text-xs font-heading font-semibold text-ink hover:text-brand bg-canvas hover:bg-card-border/40 border border-card-border transition-colors shadow-2xs"
          >
            <Sparkles className="w-3.5 h-3.5 text-brand" />
            <span>Continue as Guest (Auto-Purged Session)</span>
          </button>

          {/* Quick Demo Credentials Tip */}
          <div className="p-3 rounded-xl bg-canvas border border-card-border text-[11px] font-mono text-ink-muted space-y-1">
            <div className="flex items-center space-x-1.5 font-bold text-ink">
              <ShieldCheck className="w-3.5 h-3.5 text-brand" />
              <span>Demo Account Credentials:</span>
            </div>
            <div className="flex justify-between pt-1">
              <span>Standard: <code className="text-brand">demo_user</code> / <code className="text-brand">password123</code></span>
            </div>
            <div className="flex justify-between">
              <span>Admin: <code className="text-brand">admin</code> / <code className="text-brand">password123</code></span>
            </div>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-center text-[11px] text-ink-subtle">
          This is information, not medical advice — consult your physician.
        </p>
      </div>
    </div>
  );
};
