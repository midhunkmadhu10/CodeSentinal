'use client';

import React, { useState } from 'react';
import { Check, Copy, FileCode2, Sparkles, Shield, Cpu, CheckCircle2 } from 'lucide-react';
import type { Finding } from '@/types';

interface FindingCardProps {
  finding: Finding;
  index: number;
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors = {
    High: 'bg-danger/10 text-danger border border-danger/20',
    Medium: 'bg-warning/10 text-warning border border-warning/20',
    Low: 'bg-success/10 text-success border border-success/20',
  };
  return (
    <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${colors[severity as keyof typeof colors] || colors.Low}`}>
      {severity}
    </span>
  );
}

function SourceBadge({ source, agent, scanner }: { source?: string; agent?: string | null; scanner?: string | null }) {
  if (source === 'scanner' && scanner) {
    return (
      <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-blue/10 text-blue border-blue/20 flex items-center gap-1.5">
        <Shield className="w-3.5 h-3.5" />
        Scanner: {scanner}
      </span>
    );
  }
  if (source === 'agent' && agent) {
    return (
      <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-purple/10 text-purple border-purple/20 flex items-center gap-1.5">
        <Cpu className="w-3.5 h-3.5" />
        Agent: {agent}
      </span>
    );
  }
  if (source === 'scanner' && !scanner) {
    return (
      <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-blue/10 text-blue border-blue/20 flex items-center gap-1.5">
        <Shield className="w-3.5 h-3.5" />
        Scanner
      </span>
    );
  }
  if (source === 'agent' && !agent) {
    return (
      <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-purple/10 text-purple border-purple/20 flex items-center gap-1.5">
        <Cpu className="w-3.5 h-3.5" />
        Agent
      </span>
    );
  }
  // Legacy fallback
  return (
    <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-surface-card text-foreground-muted border-border">
      Legacy Analysis
    </span>
  );
}

function CorroboratedBadge({ corroborated }: { corroborated?: boolean }) {
  if (!corroborated) return null;
  return (
    <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-green/10 text-green border-green/20 flex items-center gap-1.5">
      <CheckCircle2 className="w-3.5 h-3.5" />
      Corroborated
    </span>
  );
}

export default function FindingCard({ finding, index }: FindingCardProps) {
  const [copied, setCopied] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const copy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  };

  const hasFix = finding.fix_code && finding.fix_code.trim().length > 0;
  const hasTests = finding.tests && finding.tests.length > 0;
  const hasSnippet = finding.snippet && finding.snippet.trim().length > 0;

  return (
    <div className="glass-card rounded-2xl border border-border overflow-hidden animate-slide-up" style={{ animationDelay: `${index * 0.1}s` }}>
      <div className="p-6 border-b border-border flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <SeverityBadge severity={finding.severity} />
            {finding.title && <h3 className="text-[16px] font-medium">{finding.title}</h3>}
            {finding.risk && !finding.title && <h3 className="text-[16px] font-medium">{finding.risk}</h3>}
            <SourceBadge source={finding.source} agent={finding.agent} scanner={finding.scanner} />
            <CorroboratedBadge corroborated={finding.corroborated} />
            {finding.confidence !== null && finding.confidence !== undefined && (
              <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-accent/10 text-accent border-accent/20 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                {Math.round(finding.confidence * 100)}%
              </span>
            )}
          </div>
          <p className="text-[14px] text-foreground-muted leading-relaxed max-w-3xl">
            {finding.description || finding.rule_violation}
          </p>
          {finding.rule && (
            <p className="mt-2 text-[12px] text-foreground-muted">
              <strong>Rule:</strong> {finding.rule}
              {finding.cwe && <span className="ml-2"><strong>CWE:</strong> {finding.cwe}</span>}
              {finding.category && <span className="ml-2"><strong>Category:</strong> {finding.category}</span>}
            </p>
          )}
        </div>
        <div className="bg-surface rounded-lg px-3 py-1.5 border border-border text-[12px] font-mono text-foreground-muted shrink-0 flex items-center gap-2">
                  <FileCode2 className="w-3.5 h-3.5" /> {finding.file_line}
                </div>
      </div>

      {/* Expandable Details */}
      {(hasFix || hasTests || hasSnippet) && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full px-6 py-3 bg-surface/30 border-t border-border/50 flex items-center justify-between text-sm font-medium text-foreground-muted hover:text-foreground hover:bg-surface/50 transition-colors"
        >
          <span className="flex items-center gap-2">
            {expanded ? <span className="text-[11px]">Hide details</span> : <span className="text-[11px]">Show details</span>}
            {expanded ? <CheckCircle2 className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
          </span>
        </button>
      )}

      {expanded && (
        <div className="p-6 space-y-6 animate-slide-down">
          {/* Code Snippet */}
          {hasSnippet && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-foreground flex items-center gap-2">
                  <FileCode2 className="w-4 h-4" />
                  Code Snippet
                </h4>
                <button
                  onClick={() => copy(finding.snippet || '', 'snippet')}
                  className="px-2 py-1 rounded text-[11px] text-foreground-muted hover:text-foreground transition-colors flex items-center gap-1"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {copied === 'snippet' ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre className="bg-background/50 border border-border/50 rounded-xl p-4 overflow-x-auto text-sm font-mono text-foreground"><code>{finding.snippet}</code></pre>
            </div>
          )}

          {/* Suggested Fix */}
          {hasFix && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-foreground flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-success" />
                  Suggested Fix
                </h4>
                <button
                  onClick={() => copy(finding.fix_code || '', 'fix')}
                  className="px-2 py-1 rounded text-[11px] text-foreground-muted hover:text-foreground transition-colors flex items-center gap-1"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {copied === 'fix' ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre className="bg-success/5 border border-success/20 rounded-xl p-4 overflow-x-auto text-sm font-mono text-foreground"><code>{finding.fix_code}</code></pre>
            </div>
          )}

          {/* Tests */}
          {hasTests && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-foreground flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-accent" />
                  Suggested Tests ({finding.tests!.length})
                </h4>
              </div>
              <div className="space-y-3">
                {finding.tests!.map((test, i) => (
                  <div key={i} className="bg-accent/5 border border-accent/20 rounded-xl p-4 overflow-x-auto">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] text-foreground-muted">Test {i + 1}</span>
                      <button
                        onClick={() => copy(test, `test-${i}`)}
                        className="px-2 py-1 rounded text-[11px] text-foreground-muted hover:text-foreground transition-colors flex items-center gap-1"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        {copied === `test-${i}` ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                    <pre className="text-sm font-mono text-foreground"><code>{test}</code></pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Legacy: just show fix code if no expanded details */}
      {!expanded && !hasFix && !hasTests && !hasSnippet && finding.safer_code && (
        <div className="bg-surface/50 p-6 relative group">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-2 text-[12px] font-medium text-primary">
              <Sparkles className="w-3.5 h-3.5" /> Suggested Fix
            </div>
            <button
              onClick={() => copy(finding.safer_code, 'legacy')}
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
      )}
    </div>
  );
}