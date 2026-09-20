'use client';

import React, { useState } from 'react';
import { Check, Copy, FileCode2, Sparkles } from 'lucide-react';
import type { Finding } from '@/types';

interface FindingCardProps {
  finding: Finding;
  index: number;
}

export default function FindingCard({ finding, index }: FindingCardProps) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(finding.safer_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="glass-card rounded-2xl border border-border overflow-hidden animate-slide-up" style={{ animationDelay: `${index * 0.1}s` }}>
      <div className="p-6 border-b border-border flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${
              finding.severity === 'High' ? 'bg-danger/10 text-danger border border-danger/20' :
              finding.severity === 'Medium' ? 'bg-warning/10 text-warning border border-warning/20' :
              'bg-success/10 text-success border border-success/20'
            }`}>
              {finding.severity}
            </span>
            <h3 className="text-[16px] font-medium">{finding.risk}</h3>
          </div>
          <p className="text-[14px] text-foreground-muted leading-relaxed max-w-3xl">{finding.rule_violation}</p>
        </div>
        <div className="bg-surface rounded-lg px-3 py-1.5 border border-border text-[12px] font-mono text-foreground-muted shrink-0 flex items-center gap-2">
          <FileCode2 className="w-3.5 h-3.5" /> {finding.file_line}
        </div>
      </div>

      <div className="bg-surface/50 p-6 relative group">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 text-[12px] font-medium text-primary">
            <Sparkles className="w-3.5 h-3.5" /> Suggested Fix
          </div>
          <button
            onClick={copy}
            className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity bg-surface-card border border-border px-3 py-1.5 rounded-lg text-[11px] flex items-center gap-1.5 hover:bg-white/10"
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <pre className="text-[13px] font-mono text-foreground/90 overflow-x-auto p-4 rounded-xl bg-[#09090B] border border-border/50 shadow-inner">
          {finding.safer_code}
        </pre>
      </div>
    </div>
  );
}
