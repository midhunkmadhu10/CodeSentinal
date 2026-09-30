'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { listReviews, type Review, type ReviewFinding } from '@/lib/api';
import {
  Shield, Search, Filter, ChevronLeft, ChevronRight,
  AlertTriangle, AlertCircle, CheckCircle, FileText,
  Clock, ExternalLink, MoreVertical,
} from 'lucide-react';

const SEVERITY_COLORS: Record<string, string> = {
  High: 'text-danger bg-danger/10 border-danger/20',
  Medium: 'text-warning bg-warning/10 border-warning/20',
  Low: 'text-success bg-success/10 border-success/20',
};

const SEVERITY_ICONS: Record<string, React.ReactNode> = {
  High: <AlertTriangle className="w-3.5 h-3.5" />,
  Medium: <AlertCircle className="w-3.5 h-3.5" />,
  Low: <CheckCircle className="w-3.5 h-3.5" />,
};

const SOURCE_BADGES: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  scanner: { label: 'Scanner', color: 'bg-blue/10 text-blue border-blue/20', icon: <Shield className="w-3 h-3" /> },
  agent: { label: 'Agent', color: 'bg-purple/10 text-purple border-purple/20', icon: <FileText className="w-3 h-3" /> },
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${SEVERITY_COLORS[severity] || SEVERITY_COLORS.Low} flex items-center gap-1`}>
      {SEVERITY_ICONS[severity] || SEVERITY_ICONS.Low}
      {severity}
    </span>
  );
}

function SourceBadge({ source, agent, scanner }: { source: string; agent?: string | null; scanner?: string | null }) {
  if (source === 'scanner' && scanner) {
    return (
      <span className="px-2 py-0.5 rounded-full text-[11px] font-medium border bg-blue/10 text-blue border-blue/20 flex items-center gap-1">
        <Shield className="w-3 h-3" />
        {scanner}
      </span>
    );
  }
  if (source === 'agent' && agent) {
    return (
      <span className="px-2 py-0.5 rounded-full text-[11px] font-medium border bg-purple/10 text-purple border-purple/20 flex items-center gap-1">
        <FileText className="w-3 h-3" />
        {agent}
      </span>
    );
  }
  return (
    <span className="px-2 py-0.5 rounded-full text-[11px] font-medium border bg-surface-card text-foreground-muted border-border">
      {source}
    </span>
  );
}

function CorroboratedBadge({ corroborated }: { corroborated: boolean }) {
  if (!corroborated) return null;
  return (
    <span className="px-2 py-0.5 rounded-full text-[11px] font-medium border bg-green/10 text-green border-green/20 flex items-center gap-1">
      <CheckCircle className="w-3 h-3" />
      Corroborated
    </span>
  );
}

function FindingRow({ finding }: { finding: ReviewFinding }) {
  return (
    <tr className="border-t border-border/50 hover:bg-white/5 transition-colors">
      <td className="px-4 py-3">
        <SeverityBadge severity={finding.severity} />
      </td>
      <td className="px-4 py-3">
        <SourceBadge source={finding.source} agent={finding.agent} scanner={finding.scanner} />
      </td>
      <td className="px-4 py-3">
        <CorroboratedBadge corroborated={finding.corroborated} />
      </td>
      <td className="px-4 py-3 font-mono text-sm text-foreground-muted">{finding.file_line || finding.file}</td>
      <td className="px-4 py-3">
        <p className="font-medium text-foreground truncate max-w-xs">{finding.title}</p>
        <p className="text-[12px] text-foreground-muted truncate max-w-xs">{finding.description}</p>
      </td>
      <td className="px-4 py-3 text-right">
        {finding.confidence !== null && finding.confidence !== undefined && (
          <span className="text-[11px] text-foreground-muted">{Math.round(finding.confidence * 100)}%</span>
        )}
      </td>
    </tr>
  );
}

export default function ReviewsPage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState<'all' | 'High' | 'Medium' | 'Low'>('all');
  const [page, setPage] = useState(0);
  const pageSize = 10;

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    const loadReviews = async () => {
      try {
        setLoading(true);
        const data = await listReviews({ limit: 100 });
        setReviews(data);
      } catch (err) {
        setError('Failed to load reviews');
      } finally {
        setLoading(false);
      }
    };
    loadReviews();
  }, []);

  const filteredReviews = reviews
    .filter(r => {
      if (search) {
        const s = search.toLowerCase();
        return r.repository.toLowerCase().includes(s) ||
          r.title.toLowerCase().includes(s) ||
          r.summary.toLowerCase().includes(s);
      }
      return true;
    })
    .filter(r => {
      if (severityFilter === 'all') return true;
      return r.counts?.[severityFilter] > 0;
    });

  const paginatedReviews = filteredReviews.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(filteredReviews.length / pageSize);

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden selection:bg-primary/30 selection:text-primary">
      <div className="ambient-glow bg-primary w-[800px] h-[800px] -top-[400px] -right-[200px]" />
      <div className="ambient-glow bg-accent w-[600px] h-[600px] -bottom-[200px] -left-[300px] opacity-20" />

      <header className="fixed top-0 left-0 right-0 z-40 glass-panel border-b border-border/50 backdrop-blur-xl">
        <div className="content-wrapper flex items-center justify-between h-16 sm:h-14">
          <div className="flex items-center gap-8">
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

      <main className="pt-20 sm:pt-16 pb-16 content-wrapper relative z-10 animate-fade-in">
        <div className="mb-10 sm:mb-14">
          <h1 className="text-3xl sm:text-4xl font-medium tracking-tight text-foreground mb-2">Reviews</h1>
          <p className="text-foreground-muted font-light text-[15px]">Browse and manage your security review history.</p>
        </div>

        {error && (
          <div className="mb-8 p-4 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Filters */}
        <div className="glass-panel rounded-2xl p-4 border mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
            <input
              type="text"
              placeholder="Search reviews..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0); }}
              className="w-full pl-10 pr-4 py-2 bg-surface-card border border-border rounded-xl text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-foreground-muted" />
            <select
              value={severityFilter}
              onChange={e => { setSeverityFilter(e.target.value as any); setPage(0); }}
              className="px-3 py-2 bg-surface-card border border-border rounded-xl text-foreground text-sm focus:outline-none focus:border-primary"
            >
              <option value="all">All Severities</option>
              <option value="High">High Only</option>
              <option value="Medium">Medium Only</option>
              <option value="Low">Low Only</option>
            </select>
          </div>
        </div>

        {/* Reviews Table */}
        <div className="glass-panel rounded-2xl border overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-foreground-muted">Loading reviews...</div>
          ) : filteredReviews.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="w-12 h-12 mx-auto text-foreground-muted/30 mb-4" />
              <p className="text-foreground-muted">No reviews found. Run your first analysis from the <a href="/analyze" className="text-primary hover:underline">Analyze</a> page.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border/50 bg-surface-card/50">
                      <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-foreground-muted">Severity</th>
                      <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-foreground-muted">Source</th>
                      <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-foreground-muted">Verified</th>
                      <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-foreground-muted">Location</th>
                      <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-foreground-muted">Finding</th>
                      <th className="px-4 py-3 text-right text-[11px] font-medium uppercase tracking-wider text-foreground-muted">Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedReviews.flatMap(review =>
                      (review.findings || []).map(finding => (
                        <FindingRow key={finding.id} finding={finding} />
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="px-4 py-4 border-t border-border/50 flex items-center justify-between">
                  <p className="text-sm text-foreground-muted">
                    Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, filteredReviews.length)} of {filteredReviews.length} findings
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage(p => Math.max(0, p - 1))}
                      disabled={page === 0}
                      className="px-3 py-1.5 rounded-lg text-sm font-medium text-foreground-muted hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors bg-surface-card border border-border hover:bg-white/5"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="px-3 py-1.5 text-sm font-medium text-foreground">
                      Page {page + 1} of {totalPages}
                    </span>
                    <button
                      onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                      disabled={page >= totalPages - 1}
                      className="px-3 py-1.5 rounded-lg text-sm font-medium text-foreground-muted hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors bg-surface-card border border-border hover:bg-white/5"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Review Summary Cards */}
        {filteredReviews.length > 0 && (
          <div className="mt-8">
            <h2 className="text-xl font-medium tracking-tight mb-4">Review Summary</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {paginatedReviews.map(review => (
                <a key={review.id} href={`/dashboard/reviews/${review.id}`} className="block glass-panel rounded-2xl p-6 border hover:border-primary/30 transition-all">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <p className="text-[11px] text-foreground-muted uppercase tracking-wider font-medium">{review.trigger}</p>
                      <p className="text-lg font-medium text-foreground truncate">{review.title || review.repository}</p>
                    </div>
                    <span className={`px-2 py-1 rounded-full text-[11px] font-medium ${review.status === 'completed' ? 'bg-success/10 text-success border-success/20' : 'bg-warning/10 text-warning border-warning/20'} border`}>
                      {review.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="flex items-center gap-1 text-foreground-muted">
                      <FileText className="w-4 h-4" /> {review.repository}
                    </span>
                    <span className="flex items-center gap-1 text-foreground-muted">
                      <Clock className="w-4 h-4" /> {review.created_at ? new Date(review.created_at).toLocaleDateString() : '—'}
                    </span>
                  </div>
                  <div className="mt-4 flex items-center gap-2 flex-wrap">
                    {review.counts?.High > 0 && <SeverityBadge severity="High" />}
                    {review.counts?.Medium > 0 && <SeverityBadge severity="Medium" />}
                    {review.counts?.Low > 0 && <SeverityBadge severity="Low" />}
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}