'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { getReview, type Review, type ReviewFinding } from '@/lib/api';
import {
  Shield, AlertTriangle, AlertCircle, CheckCircle, ArrowLeft,
  FileText, Clock, Copy, Download, ExternalLink,
  ChevronDown, ChevronUp, Info, Bug, Code2,
} from 'lucide-react';

const SEVERITY_COLORS: Record<string, string> = {
  High: 'text-danger bg-danger/10 border-danger/20',
  Medium: 'text-warning bg-warning/10 border-warning/20',
  Low: 'text-success bg-success/10 border-success/20',
};

const SEVERITY_ICONS: Record<string, React.ReactNode> = {
  High: <AlertTriangle className="w-4 h-4" />,
  Medium: <AlertCircle className="w-4 h-4" />,
  Low: <CheckCircle className="w-4 h-4" />,
};

function SeverityBadge({ severity, size = 'md' }: { severity: string; size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-[11px]',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-2 text-base',
  };
  return (
    <span className={`rounded-full font-medium border flex items-center gap-1.5 ${SEVERITY_COLORS[severity] || SEVERITY_COLORS.Low} ${sizeClasses[size]}`}>
      {SEVERITY_ICONS[severity] || SEVERITY_ICONS.Low}
      {severity}
    </span>
  );
}

function SourceBadge({ finding }: { finding: ReviewFinding }) {
  if (finding.source === 'scanner' && finding.scanner) {
    return (
      <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-blue/10 text-blue border-blue/20 flex items-center gap-1.5">
        <Shield className="w-3.5 h-3.5" />
        Scanner: {finding.scanner}
      </span>
    );
  }
  if (finding.source === 'agent' && finding.agent) {
    return (
      <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-purple/10 text-purple border-purple/20 flex items-center gap-1.5">
        <Code2 className="w-3.5 h-3.5" />
        Agent: {finding.agent}
      </span>
    );
  }
  return (
    <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-surface-card text-foreground-muted border-border">
      {finding.source}
    </span>
  );
}

function FindingCard({ finding, index }: { finding: ReviewFinding; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="glass-panel rounded-2xl border overflow-hidden animate-fade-in" style={{ animationDelay: `${index * 50}ms` }}>
      {/* Header */}
      <div className="p-5 border-b border-border/50 bg-surface-card/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <SeverityBadge severity={finding.severity} size="md" />
            <SourceBadge finding={finding} />
            {finding.corroborated && (
              <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-green/10 text-green border-green/20 flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5" />
                Corroborated
              </span>
            )}
            {finding.confidence !== null && finding.confidence !== undefined && (
              <span className="px-2 py-1 rounded-lg text-[11px] font-medium border bg-accent/10 text-accent border-accent/20 flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5" />
                {Math.round(finding.confidence * 100)}% confidence
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setExpanded(!expanded)}
              className="px-3 py-1.5 rounded-lg text-sm font-medium text-foreground-muted hover:text-foreground transition-colors bg-surface-card border border-border hover:bg-white/5 flex items-center gap-1.5"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              {expanded ? 'Collapse' : 'Details'}
            </button>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="p-5 border-b border-border/50">
        <h3 className="text-lg font-medium text-foreground mb-2">{finding.title}</h3>
        <div className="flex flex-wrap gap-3 text-sm text-foreground-muted mb-3">
          <span className="flex items-center gap-1.5">
            <FileText className="w-4 h-4" />
            {finding.file_line || finding.file}
          </span>
          {finding.category && (
            <span className="flex items-center gap-1.5">
              <Bug className="w-4 h-4" />
              {finding.category}
            </span>
          )}
          {finding.cwe && (
            <span className="flex items-center gap-1.5">
              <Info className="w-4 h-4" />
              CWE-{finding.cwe}
            </span>
          )}
        </div>
        <p className="text-foreground-muted leading-relaxed">{finding.description}</p>
        {finding.rule && (
          <p className="mt-2 text-[13px] text-foreground-muted">
            <strong>Rule:</strong> {finding.rule}
          </p>
        )}
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="p-5 space-y-6 animate-slide-down">
          {/* Code Snippet */}
          {finding.snippet && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-foreground">Code Snippet</h4>
                <button
                  onClick={() => copyToClipboard(finding.snippet || '', 'snippet')}
                  className="px-2 py-1 rounded text-[11px] text-foreground-muted hover:text-foreground transition-colors flex items-center gap-1"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {copied === 'snippet' ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre className="bg-background/50 border border-border/50 rounded-xl p-4 overflow-x-auto text-sm font-mono text-foreground"><code>{finding.snippet}</code></pre>
            </div>
          )}

          {/* Fix Code */}
          {finding.fix_code && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-foreground flex items-center gap-2">
                  <Code2 className="w-4 h-4 text-success" />
                  Suggested Fix
                </h4>
                <button
                  onClick={() => copyToClipboard(finding.fix_code, 'fix')}
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
          {finding.tests && finding.tests.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-foreground flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-accent" />
                  Suggested Tests ({finding.tests.length})
                </h4>
              </div>
              <div className="space-y-3">
                {finding.tests.map((test, i) => (
                  <div key={i} className="bg-accent/5 border border-accent/20 rounded-xl p-4 overflow-x-auto">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] text-foreground-muted">Test {i + 1}</span>
                      <button
                        onClick={() => copyToClipboard(test, `test-${i}`)}
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
    </div>
  );
}

export default function ReviewDetailPage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const params = useParams();
  const reviewId = params.id as string;
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/');
      return;
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    const loadReview = async () => {
      try {
        setLoading(true);
        const data = await getReview(parseInt(reviewId, 10));
        setReview(data);
      } catch (err) {
        setError('Failed to load review');
      } finally {
        setLoading(false);
      }
    };
    loadReview();
  }, [reviewId]);

  if (!isAuthenticated) return null;

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !review) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 mx-auto text-danger/50 mb-4" />
          <h2 className="text-xl font-medium text-foreground mb-2">Review not found</h2>
          <p className="text-foreground-muted mb-6">{error || 'The review could not be loaded.'}</p>
          <a href="/dashboard/reviews" className="text-primary hover:underline">Back to reviews</a>
        </div>
      </div>
    );
  }

  const totalFindings = review.findings?.length || 0;
  const highCount = review.counts?.High || 0;
  const mediumCount = review.counts?.Medium || 0;
  const lowCount = review.counts?.Low || 0;

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden selection:bg-primary/30 selection:text-primary">
      <div className="ambient-glow bg-primary w-[800px] h-[800px] -top-[400px] -right-[200px]" />
      <div className="ambient-glow bg-accent w-[600px] h-[600px] -bottom-[200px] -left-[300px] opacity-20" />

      <header className="fixed top-0 left-0 right-0 z-40 glass-panel border-b border-border/50 backdrop-blur-xl">
        <div className="content-wrapper flex items-center justify-between h-16 sm:h-14">
          <div className="flex items-center gap-8">
            <a href="/dashboard/reviews" className="flex items-center gap-2">
              <ArrowLeft className="w-5 h-5 text-foreground-muted" />
            </a>
            <a href="/dashboard" className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" strokeWidth={1.5} />
              <span className="font-medium tracking-tight text-foreground">CodeSentinal</span>
            </a>
            <nav className="hidden md:flex items-center gap-1">
              <a href="/dashboard" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Overview</a>
              <a href="/dashboard/reviews" className="px-3 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium">Reviews</a>
              <a href="/dashboard/repositories" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Repositories</a>
              <a href="/dashboard/settings" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Settings</a>
            </nav>
          </div>
        </div>
      </header>

      <main className="pt-20 sm:pt-16 pb-16 content-wrapper relative z-10 animate-fade-in max-w-5xl">
        {/* Review Header */}
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span className={`px-3 py-1 rounded-full text-[11px] font-medium border ${review.status === 'completed' ? 'bg-success/10 text-success border-success/20' : 'bg-warning/10 text-warning border-warning/20'}`}>
                  {review.status}
                </span>
                <span className="px-3 py-1 rounded-full text-[11px] font-medium border bg-primary/10 text-primary border-primary/20">
                  {review.trigger}
                </span>
              </div>
              <h1 className="text-3xl font-medium tracking-tight text-foreground">{review.title || review.repository}</h1>
              <p className="text-foreground-muted mt-1">{review.repository} {review.pr_number && `#${review.pr_number}`}</p>
            </div>
            <div className="flex items-center gap-3">
              <a href="/analyze" className="px-4 py-2 bg-primary text-primary-foreground rounded-xl font-medium text-sm hover:bg-primary/90 transition-colors">
                New Analysis
              </a>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <div className="glass-panel rounded-2xl p-4 border">
              <p className="text-[11px] text-foreground-muted uppercase tracking-wider font-medium mb-1">Total Findings</p>
              <p className="text-3xl font-medium text-foreground">{totalFindings}</p>
            </div>
            <div className="glass-panel rounded-2xl p-4 border">
              <SeverityBadge severity="High" size="lg" />
              <p className="text-[11px] text-foreground-muted uppercase tracking-wider font-medium mt-1">High Severity</p>
            </div>
            <div className="glass-panel rounded-2xl p-4 border">
              <SeverityBadge severity="Medium" size="lg" />
              <p className="text-[11px] text-foreground-muted uppercase tracking-wider font-medium mt-1">Medium Severity</p>
            </div>
            <div className="glass-panel rounded-2xl p-4 border">
              <SeverityBadge severity="Low" size="lg" />
              <p className="text-[11px] text-foreground-muted uppercase tracking-wider font-medium mt-1">Low Severity</p>
            </div>
          </div>

          {/* Metadata */}
          <div className="glass-panel rounded-2xl p-4 border flex flex-wrap gap-6 text-sm">
            <div className="flex items-center gap-2 text-foreground-muted">
              <Clock className="w-4 h-4" />
              <span>Created: {review.created_at ? new Date(review.created_at).toLocaleString() : '—'}</span>
            </div>
            {review.finished_at && (
              <div className="flex items-center gap-2 text-foreground-muted">
                <CheckCircle className="w-4 h-4 text-success" />
                <span>Finished: {new Date(review.finished_at).toLocaleString()}</span>
              </div>
            )}
            {review.metrics?.latency_seconds && (
              <div className="flex items-center gap-2 text-foreground-muted">
                <Clock className="w-4 h-4" />
                <span>Duration: {review.metrics.latency_seconds}s</span>
              </div>
            )}
            {review.metrics?.estimated_cost_usd !== undefined && (
              <div className="flex items-center gap-2 text-foreground-muted">
                <span className="text-accent">$</span>
                <span>Est. Cost: ${review.metrics.estimated_cost_usd.toFixed(4)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Summary */}
        {review.summary && (
          <div className="glass-panel rounded-2xl p-6 border mb-8">
            <h2 className="text-lg font-medium tracking-tight mb-3 flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              Summary
            </h2>
            <p className="text-foreground-muted whitespace-pre-wrap">{review.summary}</p>
          </div>
        )}

        {/* Findings */}
        <div className="mb-8">
          <h2 className="text-xl font-medium tracking-tight mb-4 flex items-center gap-2">
            <Bug className="w-5 h-5 text-warning" />
            Findings ({totalFindings})
          </h2>
          {totalFindings === 0 ? (
            <div className="glass-panel rounded-2xl p-12 text-center border">
              <CheckCircle className="w-12 h-12 mx-auto text-success/50 mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">No issues found</h3>
              <p className="text-foreground-muted">The review completed without detecting any security issues.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {review.findings?.map((finding, i) => (
                <FindingCard key={finding.id} finding={finding} index={i} />
              ))}
            </div>
          )}
        </div>

        {/* Metrics Details */}
        {review.metrics && Object.keys(review.metrics).length > 0 && (
          <details className="glass-panel rounded-2xl border">
            <summary className="p-5 cursor-pointer flex items-center justify-between list-none">
              <h2 className="text-lg font-medium tracking-tight flex items-center gap-2">
                <FileText className="w-5 h-5 text-accent" />
                Review Metrics
              </h2>
              <ChevronDown className="w-5 h-5 text-foreground-muted" />
            </summary>
            <div className="px-5 pb-5">
              <pre className="bg-background/50 border border-border/50 rounded-xl p-4 overflow-x-auto text-sm font-mono text-foreground"><code>{JSON.stringify(review.metrics, null, 2)}</code></pre>
            </div>
          </details>
        )}
      </main>
    </div>
  );
}