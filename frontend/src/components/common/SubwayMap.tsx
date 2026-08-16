import React from 'react';
import { GitCommit, ArrowRight, Activity, FileText, Pill, AlertCircle, Database } from 'lucide-react';

interface SubwayMapProps {
  paths: string[];
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
  // Matches segments like: Entity(Name) -[EDGE]-> Entity(Name)
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

function getNodeIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes('lab') || t.includes('test')) return <Activity className="w-3.5 h-3.5 text-brand" />;
  if (t.includes('drug') || t.includes('med')) return <Pill className="w-3.5 h-3.5 text-status-info" />;
  if (t.includes('disease') || t.includes('condition')) return <AlertCircle className="w-3.5 h-3.5 text-status-danger" />;
  if (t.includes('doc') || t.includes('chunk')) return <FileText className="w-3.5 h-3.5 text-ink-muted" />;
  return <Database className="w-3.5 h-3.5 text-ink-muted" />;
}

export const SubwayMap: React.FC<SubwayMapProps> = ({ paths }) => {
  if (!paths || paths.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 p-4 rounded-xl border border-card-border bg-card/60">
      <div className="flex items-center space-x-2 pb-2 border-b border-card-border">
        <GitCommit className="w-4 h-4 text-brand" />
        <h4 className="text-xs font-heading font-bold text-ink uppercase tracking-wider">
          Knowledge Graph Traversal Provenance ({paths.length})
        </h4>
      </div>

      <div className="space-y-2.5 overflow-x-auto pb-1">
        {paths.map((pathStr, idx) => {
          const segments = parsePathString(pathStr);

          if (segments.length === 0) {
            return (
              <div key={idx} className="p-2 rounded bg-canvas border border-card-border font-mono text-xs text-ink-muted">
                {pathStr}
              </div>
            );
          }

          return (
            <div
              key={idx}
              className="flex items-center space-x-2 p-2.5 rounded-lg bg-canvas border border-card-border text-xs min-w-max"
            >
              {segments.map((seg, sIdx) => (
                <React.Fragment key={sIdx}>
                  {/* Source Node (only on first segment) */}
                  {sIdx === 0 && (
                    <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-card border border-card-border shadow-2xs">
                      {getNodeIcon(seg.source.type)}
                      <span className="font-semibold text-ink font-heading">{seg.source.name}</span>
                      <span className="text-[10px] font-mono text-ink-subtle">({seg.source.type})</span>
                    </div>
                  )}

                  {/* Relationship Edge Line */}
                  <div className="flex items-center space-x-1 px-1 text-ink-subtle">
                    <span className="h-0.5 w-3 bg-brand/40" />
                    <span className="px-1.5 py-0.5 text-[10px] font-mono font-medium rounded bg-brand-surface text-brand border border-brand-border/60 uppercase">
                      {seg.edge}
                    </span>
                    <ArrowRight className="w-3 h-3 text-brand/60" />
                  </div>

                  {/* Target Node */}
                  <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-card border border-card-border shadow-2xs">
                    {getNodeIcon(seg.target.type)}
                    <span className="font-semibold text-ink font-heading">{seg.target.name}</span>
                    <span className="text-[10px] font-mono text-ink-subtle">({seg.target.type})</span>
                  </div>
                </React.Fragment>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
};
