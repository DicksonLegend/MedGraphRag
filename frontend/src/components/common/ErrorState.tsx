import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Service Communication Notice',
  message = 'Unable to complete request. Please verify your connection or retry.',
  onRetry,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-2xl border border-status-danger/30 bg-status-danger-bg/40 my-6 animate-fade-in" role="alert">
      <div className="p-3 rounded-full bg-status-danger-bg text-status-danger mb-3 border border-status-danger/20">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <h3 className="text-sm sm:text-base font-heading font-bold text-ink mb-1">{title}</h3>
      <p className="text-xs sm:text-sm text-ink-muted max-w-md mb-4 leading-relaxed font-sans">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-heading font-semibold text-white bg-status-danger hover:bg-status-danger/90 transition-colors shadow-xs"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Operation</span>
        </button>
      )}
    </div>
  );
};
