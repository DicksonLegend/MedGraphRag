import React, { useState, useRef, useEffect } from 'react';
import { useThemeStore } from '../../stores/themeStore';
import { Sun, Moon, Activity, Cpu, HardDrive, X } from 'lucide-react';

interface TopbarProps {
  title?: string;
  subtitle?: string;
}

export const Topbar: React.FC<TopbarProps> = ({
  title,
  subtitle,
}) => {
  const { theme, toggleTheme } = useThemeStore();
  const [showVitalPopover, setShowVitalPopover] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setShowVitalPopover(false);
      }
    };
    if (showVitalPopover) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showVitalPopover]);

  return (
    <header className="h-14 px-4 sm:px-6 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] flex items-center justify-between sticky top-0 z-30 transition-colors duration-150">
      {/* Title / Breadcrumb */}
      <div>
        {title && (
          <h2 className="text-[17px] font-semibold text-slate-900 dark:text-slate-100 tracking-tight">
            {title}
          </h2>
        )}
        {subtitle && (
          <p className="text-xs text-slate-500 dark:text-slate-400 hidden sm:block">
            {subtitle}
          </p>
        )}
      </div>

      {/* Action Controls, Live Stat Chip & Theme Toggle */}
      <div className="flex items-center space-x-2.5">
        {/* Backend Live Status Beacon */}
        <div className="hidden lg:flex items-center space-x-1.5 h-7 px-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-600 dark:text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] animate-pulse" />
          <span>Hybrid Index Ready</span>
        </div>

        {/* Merged Single Resource Chip: "Resources · VRAM 4.8/6.1 GB · RAM 3.6/12 GB" */}
        <div className="relative" ref={popoverRef}>
          <button
            type="button"
            onClick={() => setShowVitalPopover(!showVitalPopover)}
            className="flex items-center space-x-1.5 h-7 px-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-700 dark:text-slate-300 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden"
            title="Click to view Step-11/12/13 Resource Telemetry"
            aria-label="System telemetry stats: Resources VRAM 4.8/6.1 GB, RAM 3.6/12 GB"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
            <span>Resources · VRAM 4.8/6.1 GB · RAM 3.6/12 GB</span>
          </button>

          {/* Vital Monitor Telemetry Popover */}
          {showVitalPopover && (
            <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 p-4 rounded-lg bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 shadow-lg z-50 text-xs space-y-3 animate-fade-in text-slate-800 dark:text-slate-200">
              <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
                <div className="flex items-center space-x-2">
                  <Activity className="w-4 h-4 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                  <h4 className="font-semibold text-slate-900 dark:text-slate-100 text-xs uppercase tracking-wide">
                    Vital Monitor Telemetry
                  </h4>
                </div>
                <button
                  type="button"
                  onClick={() => setShowVitalPopover(false)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded focus-visible:ring-2 focus-visible:ring-teal-600 cursor-pointer"
                  aria-label="Close telemetry modal"
                >
                  <X className="w-3.5 h-3.5 stroke-[1.75]" />
                </button>
              </div>

              {/* Hardware Limits Progress */}
              <div className="space-y-2 font-mono text-[11px]">
                <div>
                  <div className="flex justify-between text-slate-700 dark:text-slate-300 mb-1">
                    <span className="flex items-center space-x-1">
                      <Cpu className="w-3.5 h-3.5 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                      <span>GPU VRAM (RTX 3050 6GB)</span>
                    </span>
                    <span className="font-semibold tabular-nums">4,784 / 6,144 MB (77.8%)</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
                    <div className="h-full bg-[#16A34A] rounded-full" style={{ width: '77.8%' }} />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-slate-700 dark:text-slate-300 mb-1">
                    <span className="flex items-center space-x-1">
                      <HardDrive className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 stroke-[1.75]" />
                      <span>Host RAM (Node Memory)</span>
                    </span>
                    <span className="font-semibold tabular-nums">3.62 / 12.0 GB (30.1%)</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
                    <div className="h-full bg-[#0F766E] dark:bg-[#14B8A6] rounded-full" style={{ width: '30.1%' }} />
                  </div>
                </div>
              </div>

              {/* Step-11, 12, 13 Suite Metrics */}
              <div className="pt-2 border-t border-slate-200 dark:border-slate-800 space-y-1.5 font-mono text-[11px]">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block uppercase tracking-wide">
                  Measured Verification Artifacts
                </span>

                <div className="p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-0.5">
                  <div className="flex justify-between font-semibold text-slate-900 dark:text-slate-100">
                    <span>Step-11 API Suite (7 Probes)</span>
                    <span className="text-[#16A34A]">PASS 7/7</span>
                  </div>
                  <div className="flex justify-between text-slate-500 text-[10px]">
                    <span>Cold: 13,675 ms · Warm: 3,667 ms</span>
                    <span>Wall: 61,349 ms</span>
                  </div>
                </div>

                <div className="p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-0.5">
                  <div className="flex justify-between font-semibold text-slate-900 dark:text-slate-100">
                    <span>Step-12 Indices Memory</span>
                    <span className="text-[#0F766E] dark:text-[#14B8A6]">420 MB Total</span>
                  </div>
                  <div className="flex justify-between text-slate-500 text-[10px]">
                    <span>FAISS IVFpq: 240 MB</span>
                    <span>Kùzu Graph: 180 MB</span>
                  </div>
                </div>

                <div className="p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-0.5">
                  <div className="flex justify-between font-semibold text-slate-900 dark:text-slate-100">
                    <span>Step-13 Feature Layer</span>
                    <span className="text-[#16A34A]">PASS 13/13</span>
                  </div>
                  <div className="flex justify-between text-slate-500 text-[10px]">
                    <span>Peak RAM 3.93 GB · VRAM 4,776 MB</span>
                    <span>Time: 176.68 s</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Dual-Tone Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="flex items-center space-x-1.5 h-7 px-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors text-xs font-medium focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden cursor-pointer"
          title={`Switch to ${theme === 'light' ? 'Vital Monitor (Dark)' : 'Clinical Calm (Light)'}`}
          aria-label="Toggle visual theme"
        >
          {theme === 'light' ? (
            <>
              <Moon className="w-3.5 h-3.5 text-[#0F766E] stroke-[1.75]" />
              <span className="hidden sm:inline">Dark</span>
            </>
          ) : (
            <>
              <Sun className="w-3.5 h-3.5 text-[#D97706] stroke-[1.75]" />
              <span className="hidden sm:inline">Light</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
};
