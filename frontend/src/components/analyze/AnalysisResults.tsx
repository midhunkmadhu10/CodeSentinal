'use client';

import React from 'react';
import { AlertCircle, ShieldAlert } from 'lucide-react';
import type { Finding } from '@/types';
import FindingCard from './FindingCard';

interface AnalysisResultsProps {
  findings: Finding[];
  loading: boolean;
  error: string | null;
  onDismissError: () => void;
}

export default function AnalysisResults({ findings, loading, error, onDismissError }: AnalysisResultsProps) {
  if (findings.length === 0 && !loading && !error) return null;

  const high = findings.filter(f => f.severity === 'High').length;
  const medium = findings.filter(f => f.severity === 'Medium').length;
  const low = findings.filter(f => f.severity === 'Low').length;

  return (
    <section className="scroll-mt-32 animate-slide-up" id="results">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h2 className="text-2xl font-medium tracking-tight mb-2">Report</h2>
          <p className="text-foreground-muted font-light text-[14px]">
            {loading ? 'AI is processing the diff...' : `Found ${findings.length} actionable items.`}
          </p>
        </div>
        {!loading && findings.length > 0 && (
          <div className="flex items-center gap-3 bg-surface-card border border-border px-4 py-2 rounded-2xl">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-danger/10 text-danger border border-danger/20">
                {high} High
              </span>
              <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-warning/10 text-warning border border-warning/20">
                {medium} Medium
              </span>
              <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-success/10 text-success border border-success/20">
                {low} Low
              </span>
            </div>
            <div className="w-px h-6 bg-border"></div>
            <ShieldAlert className={`w-5 h-5 ${high > 0 ? 'text-danger' : medium > 0 ? 'text-warning' : 'text-success'}`} />
          </div>
        )}
      </div>

      {loading ? (
        <div className="glass-card rounded-2xl p-12 text-center border border-border">
          <div className="w-12 h-12 rounded-full border-2 border-border border-t-primary animate-spin mx-auto mb-6"></div>
          <h3 className="text-[16px] font-medium mb-2">Analyzing Architecture</h3>
          <p className="text-[14px] text-foreground-muted font-light">Cross-referencing diff against security context...</p>
        </div>
      ) : error ? (
        <div className="glass-card rounded-2xl p-8 border border-danger/30 bg-danger/5 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-danger shrink-0" />
          <div>
            <h3 className="text-[15px] font-medium text-danger mb-1">Analysis Failed</h3>
            <p className="text-[14px] text-danger/80 mb-4">{error}</p>
            <button onClick={onDismissError} className="text-[12px] px-3 py-1.5 rounded-lg border border-danger/30 hover:bg-danger/10 transition-colors">Dismiss</button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {findings.map((f, i) => (
            <FindingCard key={i} finding={f} index={i} />
          ))}
        </div>
      )}
    </section>
  );
}
