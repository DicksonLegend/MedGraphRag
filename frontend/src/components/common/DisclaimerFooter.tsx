import React from 'react';
import { Info } from 'lucide-react';

interface DisclaimerFooterProps {
  customText?: string;
}

export const DisclaimerFooter: React.FC<DisclaimerFooterProps> = ({
  customText = 'MedGraphRAG is an information tool, not a diagnostic device. All responses require mandatory physician review.',
}) => {
  return (
    <div className="flex items-center space-x-2 pt-2 text-[12px] text-slate-500 dark:text-slate-400">
      <Info className="w-3.5 h-3.5 text-[#0F766E] dark:text-[#14B8A6] shrink-0 stroke-[1.75]" />
      <p className="font-sans leading-tight">
        {customText}
      </p>
    </div>
  );
};
