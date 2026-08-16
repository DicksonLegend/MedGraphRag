import React from 'react';
import { useThemeStore } from '../../stores/themeStore';
import { Sun, Moon, Sparkles, Activity } from 'lucide-react';

interface TopbarProps {
  title?: string;
  subtitle?: string;
}

export const Topbar: React.FC<TopbarProps> = ({
  title,
  subtitle,
}) => {
  const { theme, toggleTheme } = useThemeStore();

  return (
    <header className="h-16 px-6 border-b border-card-border bg-card/80 backdrop-blur-md flex items-center justify-between sticky top-0 z-30 transition-colors duration-200">
      {/* Title / Breadcrumb */}
      <div>
        {title && (
          <h2 className="text-base sm:text-lg font-heading font-extrabold text-ink tracking-tight">
            {title}
          </h2>
        )}
        {subtitle && (
          <p className="text-xs text-ink-muted hidden sm:block font-sans">
            {subtitle}
          </p>
        )}
      </div>

      {/* Action Controls & Theme Toggle */}
      <div className="flex items-center space-x-3">
        {/* Backend Live Status Beacon */}
        <div className="hidden md:flex items-center space-x-2 px-2.5 py-1 rounded-full bg-canvas border border-card-border text-[11px] font-mono text-ink-muted">
          <span className="w-2 h-2 rounded-full bg-status-success animate-pulse" />
          <span>Hybrid Index Ready</span>
        </div>

        {/* Dual-Tone Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center space-x-2 px-3 py-1.5 rounded-xl border border-card-border bg-canvas hover:bg-card text-ink transition-all shadow-2xs text-xs font-heading font-semibold"
          title={`Switch to ${theme === 'light' ? 'Vital Monitor (Dark)' : 'Clinical Calm (Light)'}`}
          aria-label="Toggle visual theme"
        >
          {theme === 'light' ? (
            <>
              <Moon className="w-3.5 h-3.5 text-brand" />
              <span className="hidden sm:inline">Vital Monitor</span>
            </>
          ) : (
            <>
              <Sun className="w-3.5 h-3.5 text-status-caution" />
              <span className="hidden sm:inline">Clinical Calm</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
};
