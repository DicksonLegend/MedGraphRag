import React from 'react';
import { useAuthStore } from '../../stores/authStore';
import { AlertCircle, Trash2 } from 'lucide-react';

export const GuestBanner: React.FC = () => {
  const { ephemeral, user_id } = useAuthStore();

  if (!ephemeral) return null;

  return (
    <div className="bg-status-caution-bg/80 border-b border-status-caution/30 px-4 py-2 text-xs text-status-caution flex items-center justify-between animate-fade-in">
      <div className="flex items-center space-x-2">
        <AlertCircle className="w-4 h-4 text-status-caution shrink-0" />
        <span className="font-medium">
          <strong>Guest Session ({user_id}):</strong> Your private uploaded reports and transient session data are automatically purged upon logout.
        </span>
      </div>
      <div className="hidden sm:flex items-center space-x-1 font-mono text-[10px] uppercase font-bold text-status-caution/90">
        <Trash2 className="w-3 h-3" />
        <span>Auto-Purge Active</span>
      </div>
    </div>
  );
};
