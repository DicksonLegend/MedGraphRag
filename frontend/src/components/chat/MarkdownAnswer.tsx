import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { CitationMeta } from '../../api/types';
import { CitationChip } from '../common/CitationChip';

interface MarkdownAnswerProps {
  content: string;
  citations: CitationMeta[];
  onCitationClick?: (label: string) => void;
}

export const MarkdownAnswer: React.FC<MarkdownAnswerProps> = ({
  content,
  citations,
  onCitationClick,
}) => {
  // Helper to render text with embedded citation chips
  const renderTextWithCitations = (text: string) => {
    const parts = text.split(/(\[E\d+\])/g);
    return parts.map((part, index) => {
      const match = part.match(/^\[E(\d+)\]$/);
      if (match) {
        const citation = citations.find(
          (c) => c.label === part || c.label === `[E${match[1]}]`
        );
        return (
          <CitationChip
            key={index}
            label={part}
            citation={citation}
            onSelect={onCitationClick}
          />
        );
      }
      return part;
    });
  };

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none text-ink leading-relaxed font-sans">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => {
            return (
              <p className="mb-3 last:mb-0 leading-relaxed text-sm">
                {React.Children.map(children, (child) => {
                  if (typeof child === 'string') {
                    return renderTextWithCitations(child);
                  }
                  return child;
                })}
              </p>
            );
          },
          li: ({ children }) => {
            return (
              <li className="mb-1.5 leading-relaxed text-sm">
                {React.Children.map(children, (child) => {
                  if (typeof child === 'string') {
                    return renderTextWithCitations(child);
                  }
                  return child;
                })}
              </li>
            );
          },
          strong: ({ children }) => {
            return (
              <strong className="font-bold text-ink">
                {children}
              </strong>
            );
          },
          code: ({ children }) => {
            return (
              <code className="px-1.5 py-0.5 rounded bg-canvas border border-card-border font-mono text-xs text-brand font-semibold tabular-nums">
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-4 rounded-xl border border-card-border">
              <table className="w-full text-xs text-left">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 bg-canvas font-heading font-bold text-ink border-b border-card-border">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 border-b border-card-border/60 text-ink font-mono">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
