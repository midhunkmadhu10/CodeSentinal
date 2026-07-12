'use client';

import React from 'react';
import { AlertTriangle, Shield, CheckCircle } from 'lucide-react';
import type { Finding } from '@/types';
import SeverityBadge from './SeverityBadge';
import SourceChunk from './SourceChunk';

interface ResultsTableProps {
  findings: Finding[];
  loading: boolean;
  error: string | null;
}

export default function ResultsTable({ findings, loading, error }: ResultsTableProps) {
  // Empty state — no analysis yet
  if (!loading && !error && findings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center p-8">
        <div className="w-16 h-16 rounded-2xl bg-surface border border-border flex items-center justify-center mb-4">
          <Shield className="w-8 h-8 text-foreground-muted" />
        </div>
        <h3 className="text-lg font-semibold text-foreground mb-1">No Analysis Yet</h3>
        <p className="text-sm text-foreground-muted max-w-sm">
          Paste a diff, upload your security rules, and click <strong>Analyze</strong> to see findings here.
        </p>
        <p className="text-xs text-foreground-muted/50 mt-4">
          Or click <strong>Load Demo</strong> to try with sample data.
        </p>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center p-8">
        <div className="w-12 h-12 border-2 border-primary/30 border-t-primary rounded-full animate-spin mb-4" />
        <h3 className="text-lg font-semibold text-foreground mb-1">Analyzing...</h3>
        <p className="text-sm text-foreground-muted">
          Running RAG retrieval and LLM analysis
        </p>
        <div className="mt-6 space-y-2 w-full max-w-sm">
          <div className="h-3 bg-surface rounded-full animate-pulse" />
          <div className="h-3 bg-surface rounded-full animate-pulse w-3/4" />
          <div className="h-3 bg-surface rounded-full animate-pulse w-1/2" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center p-8">
        <div className="w-16 h-16 rounded-2xl bg-danger/10 border border-danger/20 flex items-center justify-center mb-4">
          <AlertTriangle className="w-8 h-8 text-danger" />
        </div>
        <h3 className="text-lg font-semibold text-foreground mb-1">Analysis Failed</h3>
        <p className="text-sm text-foreground-muted max-w-sm">{error}</p>
      </div>
    );
  }

  // Success state
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">
          Findings
          <span className="ml-2 text-sm font-normal text-foreground-muted">
            ({findings.length} issue{findings.length !== 1 ? 's' : ''} found)
          </span>
        </h3>
        <div className="flex gap-2">
          {findings.filter((f) => f.severity === 'High').length > 0 && (
            <span className="text-xs px-2 py-1 rounded-full bg-danger/15 text-danger">
              {findings.filter((f) => f.severity === 'High').length} High
            </span>
          )}
          {findings.filter((f) => f.severity === 'Medium').length > 0 && (
            <span className="text-xs px-2 py-1 rounded-full bg-warning/15 text-warning">
              {findings.filter((f) => f.severity === 'Medium').length} Medium
            </span>
          )}
          {findings.filter((f) => f.severity === 'Low').length > 0 && (
            <span className="text-xs px-2 py-1 rounded-full bg-success/15 text-success">
              {findings.filter((f) => f.severity === 'Low').length} Low
            </span>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {findings.map((finding, index) => (
          <div
            key={index}
            className="bg-surface border border-border rounded-xl overflow-hidden transition-all hover:border-primary/30"
          >
            {/* Header row */}
            <div className="flex items-start gap-3 p-4">
              <SeverityBadge severity={finding.severity} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <code className="text-xs font-mono text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                    {finding.file_line}
                  </code>
                </div>
                <p className="text-sm font-medium text-foreground">{finding.risk}</p>
              </div>
            </div>

            {/* Details */}
            <div className="px-4 pb-4 space-y-3">
              {/* Rule Violation */}
              <div>
                <p className="text-xs font-medium text-foreground-muted mb-1">Rule Violation</p>
                <p className="text-sm text-foreground">{finding.rule_violation}</p>
              </div>

              {/* Safer Code */}
              <div>
                <p className="text-xs font-medium text-foreground-muted mb-1">Safer Code Suggestion</p>
                <pre className="text-sm font-mono text-success bg-background/50 rounded-lg p-3 overflow-x-auto">
                  {finding.safer_code}
                </pre>
              </div>

              {/* Source Rule */}
              <SourceChunk chunk={finding.source_chunk} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}