import React from 'react';
import { Info } from 'lucide-react';

interface DisclaimerFooterProps {
  customText?: string;
}

export const DisclaimerFooter: React.FC<DisclaimerFooterProps> = ({
  customText = 'This is information, not medical advice — consult your physician.',
}) => {
  return (
    <footer className="mt-6 pt-4 border-t border-card-border/80 flex items-center space-x-2 text-xs text-ink-muted">
      <Info className="w-4 h-4 text-brand shrink-0" />
      <p className="font-sans leading-relaxed">
        {customText}
      </p>
    </footer>
  );
};
