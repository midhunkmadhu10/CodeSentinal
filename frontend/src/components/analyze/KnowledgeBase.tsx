'use client';

import React from 'react';
import { FileText, Layers, Plus, Upload, X } from 'lucide-react';

interface KnowledgeBaseProps {
  rules: string;
  rulesFileName: string | null;
  onClear: () => void;
  onAddContext: () => void;
}

export default function KnowledgeBase({ rules, rulesFileName, onClear, onAddContext }: KnowledgeBaseProps) {
  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="flex items-end justify-between mb-10">
        <div>
          <h2 className="text-3xl font-medium tracking-tight mb-3">Knowledge Base</h2>
          <p className="text-foreground-muted font-light">Provide context, security rules, and code standards for the AI.</p>
        </div>
        <button
          onClick={onAddContext}
          className="bg-surface-card border border-border hover:bg-white/10 px-5 py-2.5 rounded-xl text-[13px] font-medium transition-all flex items-center gap-2"
        >
          <Plus className="w-4 h-4" /> Add Context
        </button>
      </div>

      {rules.trim() ? (
        <div className="glass-card rounded-2xl overflow-hidden border border-border">
          <div className="bg-surface-card border-b border-border px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5 text-primary" />
              <div>
                <h3 className="text-[14px] font-medium">{rulesFileName || 'Context Rules'}</h3>
                <p className="text-[12px] text-foreground-muted">{rules.split('\n').length} lines active</p>
              </div>
            </div>
            <button
              onClick={onClear}
              className="text-foreground-muted hover:text-danger transition-colors p-2"
              aria-label="Clear rules"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="p-6 bg-surface/50 max-h-[600px] overflow-y-auto">
            <pre className="text-[13px] font-mono text-foreground-muted whitespace-pre-wrap leading-relaxed">{rules}</pre>
          </div>
        </div>
      ) : (
        <div className="glass-card border border-border border-dashed rounded-2xl p-16 text-center">
          <div className="w-16 h-16 rounded-2xl bg-surface-card border border-border mx-auto flex items-center justify-center mb-6">
            <Layers className="w-8 h-8 text-foreground-muted" />
          </div>
          <h3 className="text-lg font-medium mb-2">No context loaded</h3>
          <p className="text-foreground-muted font-light max-w-sm mx-auto mb-8">
            Upload your organization&apos;s security guidelines, OWASP rules, or coding standards.
          </p>
          <button
            onClick={onAddContext}
            className="bg-foreground text-background px-6 py-2.5 rounded-xl font-medium text-[14px] hover:bg-white transition-all shadow-premium hover:shadow-premium-hover inline-flex items-center gap-2"
          >
            <Upload className="w-4 h-4" /> Upload Document
          </button>
        </div>
      )}
    </div>
  );
}
