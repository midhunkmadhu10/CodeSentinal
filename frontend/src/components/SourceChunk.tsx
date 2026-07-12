'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';

interface SourceChunkProps {
  chunk: string;
}

export default function SourceChunk({ chunk }: SourceChunkProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-surface hover:bg-surface-hover transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-foreground-muted shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-foreground-muted shrink-0" />
        )}
        <FileText className="w-3.5 h-3.5 text-primary shrink-0" />
        <span className="text-xs font-medium text-foreground-muted">Source Rule Chunk</span>
      </button>

      {expanded && (
        <div className="px-3 py-2.5 bg-background/50 border-t border-border">
          <pre className="text-xs text-foreground-muted leading-relaxed whitespace-pre-wrap font-mono">
            {chunk}
          </pre>
        </div>
      )}
    </div>
  );
}