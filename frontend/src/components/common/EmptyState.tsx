import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
  icon,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-2xl border border-dashed border-card-border bg-card/40 my-6 animate-fade-in">
      <div className="p-3.5 rounded-2xl bg-canvas border border-card-border text-brand mb-4 shadow-xs">
        {icon || <Inbox className="w-8 h-8 opacity-80" />}
      </div>
      <h3 className="text-base font-heading font-bold text-ink mb-1.5">{title}</h3>
      <p className="text-xs sm:text-sm text-ink-muted max-w-md mb-6 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center px-4 py-2 rounded-xl text-xs font-heading font-bold text-white bg-brand hover:bg-brand-hover transition-colors shadow-sm"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
