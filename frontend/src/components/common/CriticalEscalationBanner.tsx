import React from 'react';
import { AlertOctagon, PhoneCall } from 'lucide-react';

interface CriticalEscalationBannerProps {
  message?: string;
}

export const CriticalEscalationBanner: React.FC<CriticalEscalationBannerProps> = ({
  message = 'URGENT CLINICAL NOTICE: One or more lab values are in the CRITICAL range. Please contact your healthcare provider or emergency services immediately.',
}) => {
  return (
    <div
      className="p-4 sm:p-5 rounded-xl border-2 border-status-danger bg-status-danger-bg/90 text-status-danger shadow-md animate-code-blue"
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-start space-x-3 sm:space-x-4">
        <div className="p-2 rounded-lg bg-status-danger text-white shrink-0 mt-0.5">
          <AlertOctagon className="w-5 h-5 animate-pulse" />
        </div>
        <div className="space-y-1.5 flex-1">
          <div className="flex items-center space-x-2">
            <h3 className="font-heading font-extrabold text-sm sm:text-base uppercase tracking-wide text-status-danger">
              Critical Lab Alert
            </h3>
            <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-status-danger text-white rounded uppercase tracking-wider">
              Emergency Action Required
            </span>
          </div>
          <p className="text-xs sm:text-sm font-semibold leading-relaxed text-ink">
            {message}
          </p>
          <div className="flex items-center space-x-2 pt-1 text-xs font-bold text-status-danger">
            <PhoneCall className="w-3.5 h-3.5" />
            <span>Consult your treating physician or urgent care center without delay.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
