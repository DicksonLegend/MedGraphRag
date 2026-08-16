import React from 'react';

interface EcgLoaderProps {
  label?: string;
  sublabel?: string;
  isCold?: boolean;
}

export const EcgLoader: React.FC<EcgLoaderProps> = ({
  label = 'Processing clinical query...',
  sublabel = 'Traversing medical knowledge graph and verifying evidence claims...',
  isCold = false,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center space-y-4 animate-fade-in" role="status" aria-live="polite">
      {/* ECG Heartbeat Line Animation SVG */}
      <div className="relative w-72 h-20 overflow-hidden rounded-xl bg-canvas border border-card-border p-2 flex items-center justify-center">
        {/* Background Grid Pattern */}
        <div 
          className="absolute inset-0 opacity-15"
          style={{
            backgroundImage: 'radial-gradient(var(--color-brand) 1px, transparent 1px)',
            backgroundSize: '12px 12px',
          }}
        />
        
        {/* Animated ECG Pulse Path */}
        <svg className="w-full h-full" viewBox="0 0 300 80" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Faded baseline trace */}
          <path
            d="M0 40 L60 40 L70 38 L80 42 L90 40 L110 40 L120 15 L130 65 L140 30 L150 45 L160 40 L180 40 L190 35 L200 40 L300 40"
            stroke="currentColor"
            strokeWidth="1.5"
            className="text-brand/20"
          />
          {/* Active sweeping ECG pulse wave */}
          <path
            d="M0 40 L60 40 L70 38 L80 42 L90 40 L110 40 L120 15 L130 65 L140 30 L150 45 L160 40 L180 40 L190 35 L200 40 L300 40"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-brand animate-ecg-pulse"
            style={{
              strokeDasharray: '200, 400',
              filter: 'drop-shadow(0 0 6px var(--color-brand))',
            }}
          />
        </svg>

        {/* Pulse Heart Dot */}
        <div className="absolute right-3 top-3 flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-brand animate-ping" />
          <span className="text-[10px] font-mono text-brand font-semibold uppercase tracking-wider">Telemetry</span>
        </div>
      </div>

      {/* Progress Labels */}
      <div className="space-y-1 max-w-md">
        <h4 className="font-heading font-semibold text-ink text-sm sm:text-base">
          {isCold ? 'Warming up the medical model (one-time, ~20 s)...' : label}
        </h4>
        <p className="text-xs text-ink-muted leading-relaxed font-sans">
          {sublabel}
        </p>
      </div>
    </div>
  );
};
