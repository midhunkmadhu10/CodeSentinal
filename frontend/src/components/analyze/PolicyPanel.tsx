'use client';

import React from 'react';
import { Check, Zap } from 'lucide-react';

interface PolicyPanelProps {
  rules: string;
  rulesFileName: string | null;
  llmConfigured: boolean | null;
  llmModel: string;
  loading: boolean;
  canAnalyze: boolean;
  onAnalyze: () => void;
  onAddContext: () => void;
}

export default function PolicyPanel({
  rules,
  rulesFileName,
  llmConfigured,
  llmModel,
  loading,
  canAnalyze,
  onAnalyze,
  onAddContext,
}: PolicyPanelProps) {
  return (
    <div className="w-full lg:w-80 bg-surface/30 p-6 flex flex-col">
      <div className="flex-1 space-y-6">
        <div>
          <div className="text-[11px] font-medium text-foreground-muted uppercase tracking-wider mb-3">Security Policy</div>
          {rules ? (
            <div className="p-3 rounded-xl bg-surface-card border border-border flex items-start gap-3">
              <Check className="w-4 h-4 text-success mt-0.5" />
              <div>
                <div className="text-[13px] font-medium">{rulesFileName || 'Active Policy'}</div>
                <div className="text-[11px] text-foreground-muted">{rules.split('\n').length} policy lines</div>
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-xl border border-dashed border-border text-center">
              <p className="text-[12px] text-foreground-muted mb-3">No policy loaded</p>
              <button onClick={onAddContext} className="text-[12px] font-medium text-foreground hover:text-primary transition-colors">
                Add Rules
              </button>
            </div>
          )}
        </div>

        <div>
          <div className="text-[11px] font-medium text-foreground-muted uppercase tracking-wider mb-3">Configuration</div>
          <div className="space-y-2 text-[12px]">
            <div className="flex items-center justify-between gap-3">
              <span className="text-foreground-muted">Model</span>
              <span className="min-w-0 max-w-[11rem] truncate text-right font-mono" title={llmModel || 'Default'}>{llmModel || 'Default'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-foreground-muted">Server key</span>
              <span>{llmConfigured === null ? 'Checking…' : llmConfigured ? 'Configured' : 'Missing'}</span>
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={onAnalyze}
        disabled={loading || !canAnalyze}        className="w-full bg-foreground text-background py-3.5 rounded-xl font-medium text-[14px] hover:bg-white transition-all shadow-premium hover:shadow-premium-hover active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-6"
      >
        {loading ? <span className="w-4 h-4 border-2 border-background/30 border-t-background rounded-full animate-spin" /> : <Zap className="w-4 h-4" />}
        {loading ? 'Analyzing...' : 'Run Analysis'}
      </button>
    </div>
  );
}
