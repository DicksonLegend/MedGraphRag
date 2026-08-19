import React, { useState } from 'react';
import {
  GitCommit,
  ArrowDown,
  Activity,
  FileText,
  Pill,
  AlertCircle,
  Database,
  Copy,
  Check,
} from 'lucide-react';

interface SubwayMapProps {
  paths: string[];
  onOpen3D?: () => void;
}

interface ParsedNode {
  type: string;
  name: string;
}

interface ParsedSegment {
  source: ParsedNode;
  edge: string;
  target: ParsedNode;
}

function parsePathString(pathStr: string): ParsedSegment[] {
  const segments: ParsedSegment[] = [];
  const parts = pathStr.split(/\s*-\[([^\]]+)\]->\s*/);

  for (let i = 0; i < parts.length - 2; i += 2) {
    const srcStr = parts[i];
    const edge = parts[i + 1];
    const tgtStr = parts[i + 2];

    const srcMatch = srcStr.match(/([a-zA-Z0-9_]+)\(([^)]+)\)/);
    const tgtMatch = tgtStr.match(/([a-zA-Z0-9_]+)\(([^)]+)\)/);

    const srcNode: ParsedNode = srcMatch
      ? { type: srcMatch[1], name: srcMatch[2] }
      : { type: 'Node', name: srcStr };

    const tgtNode: ParsedNode = tgtMatch
      ? { type: tgtMatch[1], name: tgtMatch[2] }
      : { type: 'Node', name: tgtStr };

    segments.push({ source: srcNode, edge, target: tgtNode });
  }

  return segments;
}

function getNodeTypeColor(type: string) {
  const t = type.toLowerCase();
  if (t.includes('lab') || t.includes('test'))
    return 'border-teal-200 dark:border-teal-800 bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300';
  if (t.includes('drug') || t.includes('med'))
    return 'border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300';
  if (t.includes('disease') || t.includes('condition'))
    return 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300';
  if (t.includes('doc') || t.includes('chunk'))
    return 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300';
  return 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300';
}

function getNodeIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes('lab') || t.includes('test'))
    return <Activity className="w-3.5 h-3.5 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />;
  if (t.includes('drug') || t.includes('med'))
    return <Pill className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 stroke-[1.75]" />;
  if (t.includes('disease') || t.includes('condition'))
    return <AlertCircle className="w-3.5 h-3.5 text-[#DC2626] stroke-[1.75]" />;
  if (t.includes('doc') || t.includes('chunk'))
    return <FileText className="w-3.5 h-3.5 text-slate-500 stroke-[1.75]" />;
  return <Database className="w-3.5 h-3.5 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />;
}

export const SubwayMap: React.FC<SubwayMapProps> = ({ paths }) => {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  if (!paths || paths.length === 0) {
    return null;
  }

  const handleCopyPath = (pathStr: string, idx: number) => {
    navigator.clipboard.writeText(pathStr);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 1500);
  };

  return (
    <div className="space-y-3 font-sans">
      {paths.map((pathStr, idx) => {
        const segments = parsePathString(pathStr);

        return (
          <div
            key={idx}
            className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] shadow-xs space-y-2.5 transition-all"
          >
            {/* Header: Path Index & Copy Button */}
            <div className="flex items-center justify-between pb-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                Provenance Path #{idx + 1}
              </span>
              <button
                type="button"
                onClick={() => handleCopyPath(pathStr, idx)}
                className="flex items-center space-x-1 h-7 px-2.5 rounded-lg text-xs font-mono text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600"
                title="Copy raw path string"
                aria-label={`Copy provenance path ${idx + 1}`}
              >
                {copiedIdx === idx ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-[#16A34A] stroke-[1.75]" />
                    <span className="text-[#16A34A] font-semibold">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 stroke-[1.75]" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>

            {/* Vertical Stepper Chain */}
            <div className="space-y-1.5 pl-2 border-l border-slate-200 dark:border-slate-700 ml-2 font-mono text-xs">
              {segments.map((seg, sIdx) => (
                <div key={sIdx} className="space-y-1.5">
                  {/* Source Node (rendered on first segment) */}
                  {sIdx === 0 && (
                    <div
                      className={`inline-flex items-center space-x-1.5 h-7 px-2.5 rounded-lg border shadow-2xs max-w-full ${getNodeTypeColor(
                        seg.source.type
                      )}`}
                      title={`${seg.source.type}: ${seg.source.name}`}
                    >
                      {getNodeIcon(seg.source.type)}
                      <span className="font-semibold truncate">{seg.source.name}</span>
                      <span className="text-[10px] opacity-75 font-mono">({seg.source.type})</span>
                    </div>
                  )}

                  {/* Vertical Edge Connector */}
                  <div className="flex items-center space-x-2 py-0.5 pl-2">
                    <ArrowDown className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 stroke-[1.75] shrink-0" />
                    <span className="h-6 px-2 flex items-center rounded text-[11px] font-mono font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                      {seg.edge}
                    </span>
                  </div>

                  {/* Target Node */}
                  <div
                    className={`inline-flex items-center space-x-1.5 h-7 px-2.5 rounded-lg border shadow-2xs max-w-full ${getNodeTypeColor(
                      seg.target.type
                    )}`}
                    title={`${seg.target.type}: ${seg.target.name}`}
                  >
                    {getNodeIcon(seg.target.type)}
                    <span className="font-semibold truncate">{seg.target.name}</span>
                    <span className="text-[10px] opacity-75 font-mono">({seg.target.type})</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};
