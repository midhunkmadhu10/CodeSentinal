'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
  fetchMetricsSnapshot,
  listReviews,
  listRepositories,
  listJobs,
  type Review,
  type Repository,
  type Job,
} from '@/lib/api';
import {
  Shield, AlertTriangle, AlertCircle, CheckCircle,
  Clock, DollarSign, TrendingUp, Database,
  ExternalLink, Settings, Plus, RefreshCw,
  FileText, FolderGit2, Briefcase,
  BarChart2, Zap, Brain,
} from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: string;
  icon: React.ReactNode;
  color: 'primary' | 'danger' | 'warning' | 'success' | 'accent';
  href?: string;
}

function StatCard({ title, value, change, icon, color, href }: StatCardProps) {
  const colorMap = {
    primary: 'bg-primary/10 border-primary/20 text-primary',
    danger: 'bg-danger/10 border-danger/20 text-danger',
    warning: 'bg-warning/10 border-warning/20 text-warning',
    success: 'bg-success/10 border-success/20 text-success',
    accent: 'bg-accent/10 border-accent/20 text-accent',
  };

  const cardContent = (
    <div className="glass-panel rounded-2xl p-6 border transition-all hover:border-primary/30 group relative">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[12px] text-foreground-muted uppercase tracking-wider font-medium mb-2">{title}</p>
          <p className="text-3xl font-medium tracking-tight text-foreground">{value}</p>
          {change && <p className="text-[12px] text-foreground-muted mt-1">{change}</p>}
        </div>
        <div className={`${colorMap[color]} w-10 h-10 rounded-xl flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform`}>
          {icon}
        </div>
      </div>
    </div>
  );

  if (href) {
    return (
      <a href={href} className="block" aria-label={`View ${title}`}>
        {cardContent}
      </a>
    );
  }
  return <div>{cardContent}</div>;
}

function RecentActivity({ reviews, jobs }: { reviews: Review[]; jobs: Job[] }) {
  const activities = [
    ...reviews.slice(0, 5).map(r => ({
      id: `review-${r.id}`,
      type: 'review' as const,
      title: r.title || `Review of ${r.repository}`,
      time: r.created_at,
      status: r.status,
      repo: r.repository,
    })),
    ...jobs.slice(0, 3).map(j => ({
      id: `job-${j.id}`,
      type: 'job' as const,
      title: j.type.replace('_', ' '),
      time: j.created_at,
      status: j.status,
      repo: '',
    })),
  ].sort((a, b) => new Date(b.time || 0).getTime() - new Date(a.time || 0).getTime())
   .slice(0, 8);

  const getStatusColor = (status: string) => {
    if (status === 'completed' || status === 'success') return 'text-success';
    if (status === 'failed' || status === 'error') return 'text-danger';
    if (status === 'running' || status === 'indexing') return 'text-primary animate-pulse';
    return 'text-warning';
  };

  const getStatusIcon = (status: string) => {
    if (status === 'completed' || status === 'success') return <CheckCircle className="w-3.5 h-3.5" />;
    if (status === 'failed' || status === 'error') return <AlertCircle className="w-3.5 h-3.5" />;
    if (status === 'running' || status === 'indexing') return <RefreshCw className="w-3.5 h-3.5 animate-spin" />;
    return <Clock className="w-3.5 h-3.5" />;
  };

  if (activities.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-8 text-center border">
        <Briefcase className="w-12 h-12 mx-auto text-foreground-muted/30 mb-4" />
        <p className="text-foreground-muted">No activity yet. Run your first review or connect a repository.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {activities.map(activity => (
        <div key={activity.id} className="flex items-center gap-4 p-3 rounded-xl glass-panel border hover:bg-white/5 transition-colors">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${getStatusColor(activity.status)} bg-current/10`}>
            {getStatusIcon(activity.status)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{activity.title}</p>
            <p className="text-[12px] text-foreground-muted flex items-center gap-2">
              {activity.repo && <span className="px-2 py-0.5 rounded bg-surface-card border">{activity.repo}</span>}
              <span>{activity.time ? new Date(activity.time).toLocaleString() : 'Unknown time'}</span>
            </p>
          </div>
          <span className={`text-[11px] font-medium px-2 py-1 rounded-full ${getStatusColor(activity.status)} bg-current/10`}>
            {activity.status}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const { isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const [metrics, setMetrics] = useState<any>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [metricsData, reviewsData, reposData, jobsData] = await Promise.all([
          fetchMetricsSnapshot().catch(() => null),
          listReviews({ limit: 10 }).catch(() => []),
          listRepositories().catch(() => []),
          listJobs(10).catch(() => []),
        ]);
        setMetrics(metricsData);
        setReviews(reviewsData);
        setRepos(reposData);
        setJobs(jobsData);
      } catch (err) {
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (!isAuthenticated) return null;

  const totalReviews = metrics?.usage?.total_reviews ?? reviews.length;
  const totalFindings = metrics?.usage?.total_findings ?? 0;
  const highFindings = metrics?.usage?.high_findings ?? 0;
  const estimatedCost = metrics?.usage?.estimated_cost_usd ?? 0;
  const avgLatency = metrics?.usage?.avg_review_latency_seconds ?? 0;
  const indexedRepos = repos.filter(r => r.index_status === 'completed').length;
  const pendingJobs = jobs.filter(j => j.status === 'queued' || j.status === 'running').length;

  const handleLogout = () => {
    logout();
    router.replace('/');
  };

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden selection:bg-primary/30 selection:text-primary">
      {/* Dynamic Backgrounds */}
      <div className="ambient-glow bg-primary w-[800px] h-[800px] -top-[400px] -right-[200px]" />
      <div className="ambient-glow bg-accent w-[600px] h-[600px] -bottom-[200px] -left-[300px] opacity-20" />

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-40 glass-panel border-b border-border/50 backdrop-blur-xl">
        <div className="content-wrapper flex items-center justify-between h-16 sm:h-14">
          <div className="flex items-center gap-8">
            <a href="/dashboard" className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" strokeWidth={1.5} />
              <span className="font-medium tracking-tight text-foreground">CodeSentinal</span>
            </a>
            <nav className="hidden md:flex items-center gap-1">
              <a href="/dashboard" className="px-3 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium">Overview</a>
              <a href="/dashboard/reviews" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Reviews</a>
              <a href="/dashboard/repositories" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Repositories</a>
              <a href="/dashboard/settings" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Settings</a>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={handleLogout} className="px-4 py-2 text-sm font-medium text-foreground-muted hover:text-foreground transition-colors">
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="pt-20 sm:pt-16 pb-16 content-wrapper relative z-10 animate-fade-in">
        {/* Page Title */}
        <div className="mb-10 sm:mb-14">
          <h1 className="text-3xl sm:text-4xl font-medium tracking-tight text-foreground mb-2">Dashboard</h1>
          <p className="text-foreground-muted font-light text-[15px]">Overview of your security reviews, repositories, and system health.</p>
        </div>

        {error && (
          <div className="mb-8 p-4 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-10 sm:mb-12">
          <StatCard
            title="Total Reviews"
            value={totalReviews}
            change={`${reviews.filter(r => r.status === 'completed').length} completed`}
            icon={<FileText className="w-5 h-5" />}
            color="primary"
            href="/dashboard/reviews"
          />
          <StatCard
            title="Total Findings"
            value={totalFindings}
            change={`${highFindings} high severity`}
            icon={<AlertTriangle className="w-5 h-5" />}
            color="warning"
            href="/dashboard/reviews"
          />
          <StatCard
            title="High Severity"
            value={highFindings}
            change={highFindings > 0 ? 'Requires attention' : 'All clear'}
            icon={<AlertCircle className="w-5 h-5" />}
            color={highFindings > 0 ? 'danger' : 'success'}
            href="/dashboard/reviews"
          />
          <StatCard
            title="Est. Cost"
            value={`$${estimatedCost.toFixed(4)}`}
            change={`Avg ${avgLatency.toFixed(1)}s/review`}
            icon={<DollarSign className="w-5 h-5" />}
            color="accent"
            href="/dashboard/settings"
          />
        </div>

        {/* Secondary Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-10 sm:mb-12">
          <StatCard
            title="Repositories"
            value={repos.length}
            change={`${indexedRepos} indexed`}
            icon={<FolderGit2 className="w-5 h-5" />}
            color="primary"
            href="/dashboard/repositories"
          />
          <StatCard
            title="Active Jobs"
            value={pendingJobs}
            change={pendingJobs > 0 ? 'Processing...' : 'Idle'}
            icon={<Zap className="w-5 h-5" />}
            color={pendingJobs > 0 ? 'warning' : 'success'}
            href="/dashboard/reviews"
          />
          <StatCard
            title="Model Routing"
            value={metrics?.routing?.threshold ? `${Math.round(metrics.routing.threshold * 100)}%` : '\u2014'}
            change={metrics?.routing ? `${metrics.routing.fast.model} / ${metrics.routing.deep.model}` : 'Not configured'}
            icon={<Brain className="w-5 h-5" />}
            color="accent"
            href="/dashboard/settings"
          />
        </div>

        {/* Quick Actions & Recent Activity */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Quick Actions */}
          <div className="lg:col-span-1 space-y-4">
            <div className="glass-panel rounded-2xl p-6 border">
              <h3 className="text-lg font-medium tracking-tight mb-4 flex items-center gap-2">
                <Zap className="w-4 h-4 text-primary" />
                Quick Actions
              </h3>
              <div className="space-y-3">
                <a href="/analyze" className="block w-full p-4 rounded-xl glass-panel border hover:border-primary/30 transition-all text-left group">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                      <Shield className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Run Analysis</p>
                      <p className="text-[12px] text-foreground-muted">Analyze a PR diff against your security policy</p>
                    </div>
                  </div>
                </a>
                <a href="/dashboard/repositories" className="block w-full p-4 rounded-xl glass-panel border hover:border-primary/30 transition-all text-left group">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                      <Plus className="w-5 h-5 text-accent" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Connect Repository</p>
                      <p className="text-[12px] text-foreground-muted">Link a GitHub repo for automatic PR reviews</p>
                    </div>
                  </div>
                </a>
                <a href="/dashboard/reviews" className="block w-full p-4 rounded-xl glass-panel border hover:border-primary/30 transition-all text-left group">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                      <FileText className="w-5 h-5 text-warning" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">View Reviews</p>
                      <p className="text-[12px] text-foreground-muted">Browse review history and findings</p>
                    </div>
                  </div>
                </a>
                <a href="/dashboard/settings" className="block w-full p-4 rounded-xl glass-panel border hover:border-primary/30 transition-all text-left group">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-surface-card flex items-center justify-center group-hover:scale-110 transition-transform">
                      <Settings className="w-5 h-5 text-foreground-muted" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Settings</p>
                      <p className="text-[12px] text-foreground-muted">Configure models, routing, and integrations</p>
                    </div>
                  </div>
                </a>
              </div>
            </div>

            {/* System Status */}
            <div className="glass-panel rounded-2xl p-6 border">
              <h3 className="text-lg font-medium tracking-tight mb-4 flex items-center gap-2">
                <Database className="w-4 h-4 text-accent" />
                System Status
              </h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-foreground-muted">Database</span>
                  <span className={`flex items-center gap-1.5 text-sm font-medium ${metrics?.database === 'postgres' ? 'text-success' : 'text-warning'}`}>
                    <span className={`w-2 h-2 rounded-full ${metrics?.database === 'postgres' ? 'bg-success' : 'bg-warning'}`} />
                    {metrics?.database === 'postgres' ? 'PostgreSQL + pgvector' : 'SQLite (fallback)'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-foreground-muted">Vector Search</span>
                  <span className={`flex items-center gap-1.5 text-sm font-medium ${metrics?.pgvector_enabled ? 'text-success' : 'text-warning'}`}>
                    <span className={`w-2 h-2 rounded-full ${metrics?.pgvector_enabled ? 'bg-success' : 'bg-warning'}`} />
                    {metrics?.pgvector_enabled ? 'pgvector enabled' : 'TF-IDF fallback'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-foreground-muted">Worker</span>
                  <span className={`flex items-center gap-1.5 text-sm font-medium ${metrics?.worker_running ? 'text-success' : 'text-danger'}`}>
                    <span className={`w-2 h-2 rounded-full ${metrics?.worker_running ? 'bg-success' : 'bg-danger'}`} />
                    {metrics?.worker_running ? 'Running' : 'Stopped'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-foreground-muted">LLM</span>
                  <span className={`flex items-center gap-1.5 text-sm font-medium ${metrics?.llm_configured ? 'text-success' : 'text-danger'}`}>
                    <span className={`w-2 h-2 rounded-full ${metrics?.llm_configured ? 'bg-success' : 'bg-danger'}`} />
                    {metrics?.llm_configured ? 'Configured' : 'Not configured'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="lg:col-span-2">
            <div className="glass-panel rounded-2xl p-6 border">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-medium tracking-tight flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-primary" />
                  Recent Activity
                </h3>
              </div>
              <RecentActivity reviews={reviews} jobs={jobs} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}