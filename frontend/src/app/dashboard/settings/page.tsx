'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import {
  fetchSettingsStatus,
  fetchMetricsSnapshot,
  fetchPrometheusMetrics,
  listEvals,
  triggerEval,
  type SettingsStatus,
  type MetricsSnapshot,
  type EvalRun,
} from '@/lib/api';
import {
  Shield, Brain, Zap, Database, Globe, Key,
  RefreshCw, Download, ExternalLink, AlertTriangle,
  CheckCircle, AlertCircle, Clock, DollarSign,
  BarChart2, Settings, ChevronDown, ChevronUp,
  Terminal, FileText, TrendingUp,
} from 'lucide-react';

function StatusIndicator({ label, status, description }: { label: string; status: 'success' | 'warning' | 'danger' | 'unknown'; description?: string }) {
  const statusConfig = {
    success: { color: 'text-success bg-success/10 border-success/20', icon: <CheckCircle className="w-4 h-4" />, label: 'Configured' },
    warning: { color: 'text-warning bg-warning/10 border-warning/20', icon: <AlertTriangle className="w-4 h-4" />, label: 'Partial' },
    danger: { color: 'text-danger bg-danger/10 border-danger/20', icon: <AlertCircle className="w-4 h-4" />, label: 'Not Configured' },
    unknown: { color: 'text-foreground-muted bg-surface-card border-border', icon: <Clock className="w-4 h-4" />, label: 'Unknown' },
  };

  const config = statusConfig[status];

  return (
    <div className="glass-panel rounded-2xl p-5 border flex items-center gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${config.color}`}>
        {config.icon}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-3">
          <span className="font-medium text-foreground">{label}</span>
          <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${config.color}`}>
            {config.label}
          </span>
        </div>
        {description && <p className="text-[13px] text-foreground-muted mt-1">{description}</p>}
      </div>
    </div>
  );
}

function ConfigSection({ title, icon, children, description }: { title: string; icon: React.ReactNode; children: React.ReactNode; description?: string }) {
  return (
    <div className="glass-panel rounded-2xl border p-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
          {icon}
        </div>
        <div>
          <h3 className="text-lg font-medium tracking-tight text-foreground">{title}</h3>
          {description && <p className="text-[13px] text-foreground-muted">{description}</p>}
        </div>
      </div>
      <div className="ml-10 mt-2 border-l border-border/50 pl-6 space-y-4">
        {children}
      </div>
    </div>
  );
}

function KeyValueRow({ key, value, copyable = false, monospace = false }: { key: string; value: string; copyable?: boolean; monospace?: boolean }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
      <span className="text-foreground-muted text-sm">{key}</span>
      <div className="flex items-center gap-3">
        <code className={`text-sm text-foreground font-mono ${monospace ? '' : 'truncate max-w-xs'}`}>{value || '—'}</code>
        {copyable && value && (
          <button onClick={handleCopy} className="p-1.5 rounded text-foreground-muted hover:text-foreground transition-colors" aria-label="Copy">
            {copied ? <CheckCircle className="w-4 h-4 text-success" /> : <FileText className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  );
}

function ModelTierCard({ tier, config }: { tier: 'fast' | 'deep'; config: SettingsStatus['routing'][typeof tier] }) {
  return (
    <div className="glass-panel rounded-2xl p-5 border bg-surface-card/50">
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${tier === 'fast' ? 'bg-green/10 text-green' : 'bg-purple/10 text-purple'}`}>
          {tier === 'fast' ? <Zap className="w-4 h-4" /> : <Brain className="w-4 h-4" />}
        </div>
        <div>
          <h4 className="font-medium text-foreground capitalize">{tier} tier</h4>
          <p className="text-[12px] text-foreground-muted">Used for {tier === 'fast' ? 'routine reviews' : 'complex diffs'}</p>
        </div>
      </div>
      <div className="space-y-2 text-sm">
        <KeyValueRow key="model" value={config.model} />
        <KeyValueRow key="cost_in" value={`$${config.cost_per_1m_in}/1M in`} />
        <KeyValueRow key="cost_out" value={`$${config.cost_per_1m_out}/1M out`} />
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { isAuthenticated } = useAuth();
  const [settings, setSettings] = useState<SettingsStatus | null>(null);
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [evals, setEvals] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalRunning, setEvalRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMetrics, setShowMetrics] = useState(false);
  const [prometheusText, setPrometheusText] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    const loadData = async () => {
      try {
        setLoading(true);
        const [settingsData, metricsData, evalsData] = await Promise.all([
          fetchSettingsStatus().catch(() => null),
          fetchMetricsSnapshot().catch(() => null),
          listEvals(10).catch(() => []),
        ]);
        setSettings(settingsData);
        setMetrics(metricsData);
        setEvals(evalsData);
      } catch (err) {
        setError('Failed to load settings');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [isAuthenticated]);

  const handleRunEval = async () => {
    setEvalRunning(true);
    try {
      const run = await triggerEval(true, 'Manual run from dashboard');
      setEvals(prev => [run, ...prev]);
    } catch (err) {
      setError('Failed to run evaluation');
    } finally {
      setEvalRunning(false);
    }
  };

  const handleFetchPrometheus = async () => {
    try {
      const text = await fetchPrometheusMetrics();
      setPrometheusText(text);
      setShowMetrics(true);
    } catch (err) {
      setError('Failed to fetch Prometheus metrics');
    }
  };

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
              <a href="/dashboard/reviews" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Reviews</a>
              <a href="/dashboard/repositories" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Repositories</a>
              <a href="/dashboard/settings" className="px-3 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium">Settings</a>
            </nav>
          </div>
        </div>
      </header>

      <main className="pt-20 sm:pt-16 pb-16 content-wrapper relative z-10 animate-fade-in max-w-6xl">
        <div className="mb-10 sm:mb-14">
          <h1 className="text-3xl sm:text-4xl font-medium tracking-tight text-foreground mb-2">Settings</h1>
          <p className="text-foreground-muted font-light text-[15px]">Configure models, view system status, and manage integrations.</p>
        </div>

        {error && (
          <div className="mb-8 p-4 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* System Status */}
        <ConfigSection
          title="System Status"
          icon={<Database className="w-5 h-5" />}
          description="Current backend configuration and health indicators."
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <StatusIndicator
              label="LLM Service"
              status={settings?.llm_configured ? 'success' : 'danger'}
              description={settings?.llm_endpoint ? `${settings.llm_model} @ ${settings.llm_endpoint}` : 'No LLM endpoint configured'}
            />
            <StatusIndicator
              label="Embeddings"
              status={settings?.embeddings_configured ? 'success' : 'warning'}
              description={settings?.embeddings_configured ? 'Vector similarity search enabled' : 'Falling back to TF-IDF'}
            />
            <StatusIndicator
              label="Database"
              status={settings?.database === 'postgres' ? 'success' : 'warning'}
              description={settings?.database === 'postgres' ? 'PostgreSQL with pgvector' : 'SQLite (development fallback)'}
            />
            <StatusIndicator
              label="Vector Search"
              status={settings?.pgvector_enabled ? 'success' : 'warning'}
              description={settings?.pgvector_enabled ? 'pgvector extension active' : 'Using in-process cosine similarity'}
            />
            <StatusIndicator
              label="Background Worker"
              status={settings?.worker_running ? 'success' : 'danger'}
              description={settings?.worker_running ? 'Processing async jobs' : 'Worker disabled or stopped'}
            />
            <StatusIndicator
              label="Model Routing"
              status={settings?.routing ? 'success' : 'warning'}
              description={settings?.routing ? `Threshold: ${Math.round(settings.routing.threshold * 100)}%` : 'Using single model'}
            />
          </div>
        </ConfigSection>

        {/* Model Routing Configuration */}
        {settings?.routing && (
          <ConfigSection
            title="Model Routing"
            icon={<Brain className="w-5 h-5" />}
            description="Two-tier routing: fast (cheap) for routine reviews, deep (powerful) for complex diffs."
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <ModelTierCard tier="fast" config={settings.routing.fast} />
              <ModelTierCard tier="deep" config={settings.routing.deep} />
            </div>
            <div className="glass-panel rounded-xl p-4 border bg-surface-card/30">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Settings className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <p className="font-medium text-foreground">Complexity Threshold</p>
                  <p className="text-[13px] text-foreground-muted">Diffs scoring above <strong>{Math.round(settings.routing.threshold * 100)}%</strong> route to the deep tier. Score is based on diff size, file breadth, and scanner hits.</p>
                </div>
              </div>
            </div>
          </ConfigSection>
        )}

        {/* Usage Metrics */}
        {metrics && (
          <ConfigSection
            title="Usage Metrics"
            icon={<BarChart2 className="w-5 h-5" />}
            description="Aggregate statistics across all reviews."
          >
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
              <div className="glass-panel rounded-xl p-4 border text-center">
                <p className="text-3xl font-medium text-foreground">{metrics.usage.total_reviews}</p>
                <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Total Reviews</p>
              </div>
              <div className="glass-panel rounded-xl p-4 border text-center">
                <p className="text-3xl font-medium text-warning">{metrics.usage.total_findings}</p>
                <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Total Findings</p>
              </div>
              <div className="glass-panel rounded-xl p-4 border text-center">
                <p className="text-3xl font-medium text-danger">{metrics.usage.high_findings}</p>
                <p className="text-[11px] text-foreground-muted uppercase tracking-wider">High Severity</p>
              </div>
              <div className="glass-panel rounded-xl p-4 border text-center">
                <p className="text-3xl font-medium text-accent">${metrics.usage.estimated_cost_usd.toFixed(4)}</p>
                <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Est. Cost</p>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="glass-panel rounded-xl p-4 border text-center">
                <p className="text-2xl font-medium text-foreground">{metrics.usage.avg_review_latency_seconds.toFixed(1)}s</p>
                <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Avg Latency</p>
              </div>
              <div className="glass-panel rounded-xl p-4 border text-center">
                <p className="text-2xl font-medium text-foreground">{Object.keys(metrics.counters).length}</p>
                <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Active Counters</p>
              </div>
              <div className="glass-panel rounded-xl p-4 border text-center">
                <p className="text-2xl font-medium text-foreground">{Object.keys(metrics.histograms).length}</p>
                <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Active Histograms</p>
              </div>
            </div>
          </ConfigSection>
        )}

        {/* Prometheus Metrics */}
        <ConfigSection
          title="Observability"
          icon={<TrendingUp className="w-5 h-5" />}
          description="Prometheus-compatible metrics endpoint for scraping."
        >
          <div className="flex flex-col sm:flex-row gap-4">
            <button
              onClick={handleFetchPrometheus}
              className="px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium text-sm hover:bg-primary/90 transition-colors flex items-center justify-center gap-2"
            >
              <Terminal className="w-4 h-4" />
              View Prometheus Metrics
            </button>
            <a
              href="/api/metrics/snapshot"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 bg-surface-card border border-border text-foreground rounded-xl font-medium text-sm hover:bg-white/5 transition-colors flex items-center justify-center gap-2"
            >
              <ExternalLink className="w-4 h-4" />
              JSON Snapshot
            </a>
          </div>
          {prometheusText && (
            <details className="mt-4 glass-panel rounded-xl border bg-background/50">
              <summary className="p-4 cursor-pointer flex items-center justify-between list-none">
                <span className="font-medium text-foreground">Prometheus Output ({prometheusText.split('\n').length} lines)</span>
                <ChevronDown className="w-5 h-5 text-foreground-muted" />
              </summary>
              <div className="px-4 pb-4">
                <pre className="bg-background border border-border/50 rounded-lg p-4 overflow-x-auto text-[11px] font-mono text-foreground max-h-96 overflow-y-auto"><code>{prometheusText}</code></pre>
              </div>
            </details>
          )}
        </ConfigSection>

        {/* Evaluation History */}
        <ConfigSection
          title="Evaluation Runs"
          icon={<FileText className="w-5 h-5" />}
          description="Golden-case evaluation suite results (precision/recall/F1 over expected findings)."
        >
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <button
              onClick={handleRunEval}
              disabled={evalRunning}
              className="px-6 py-3 bg-accent text-accent-foreground rounded-xl font-medium text-sm hover:bg-accent/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {evalRunning ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <TrendingUp className="w-4 h-4" />
                  Run Evaluation Suite
                </>
              )}
            </button>
          </div>

          {evals.length === 0 ? (
            <div className="text-center py-8 text-foreground-muted">
              <BarChart2 className="w-12 h-12 mx-auto mb-3 text-foreground-muted/30" />
              <p>No evaluation runs yet. Click &ldquo;Run Evaluation Suite&rdquo; to execute the golden-case tests.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {evals.map(run => (
                <div key={run.id} className="glass-panel rounded-xl p-4 border hover:border-primary/30 transition-colors">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                        <FileText className="w-5 h-5 text-accent" />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">Run #{run.id}</p>
                        <p className="text-[12px] text-foreground-muted">{run.created_at ? new Date(run.created_at).toLocaleString() : 'Unknown time'}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      {(run.scores?.precision !== undefined || run.scores?.recall !== undefined || run.scores?.f1 !== undefined) && (
                        <>
                          {run.scores.precision !== undefined && (
                            <span className="px-2 py-1 rounded bg-blue/10 text-blue border border-blue/20 text-[11px] font-medium">
                              Precision: {(run.scores.precision * 100).toFixed(1)}%
                            </span>
                          )}
                          {run.scores.recall !== undefined && (
                            <span className="px-2 py-1 rounded bg-green/10 text-green border border-green/20 text-[11px] font-medium">
                              Recall: {(run.scores.recall * 100).toFixed(1)}%
                            </span>
                          )}
                          {run.scores.f1 !== undefined && (
                            <span className="px-2 py-1 rounded bg-purple/10 text-purple border border-purple/20 text-[11px] font-medium">
                              F1: {(run.scores.f1 * 100).toFixed(1)}%
                            </span>
                          )}
                        </>
                      )}
                      {run.notes && (
                        <span className="px-2 py-1 rounded bg-surface-card border border-border text-[11px] text-foreground-muted">
                          {run.notes}
                        </span>
                      )}
                    </div>
                  </div>
                  {run.details && Object.keys(run.details).length > 0 && (
                    <details className="mt-3">
                      <summary className="text-sm text-foreground-muted hover:text-foreground cursor-pointer flex items-center gap-1">
                        <ChevronDown className="w-3.5 h-3.5" />
                        View details
                      </summary>
                      <pre className="mt-2 bg-background/50 border border-border/50 rounded-lg p-3 overflow-x-auto text-[11px] font-mono text-foreground"><code>{JSON.stringify(run.details, null, 2)}</code></pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}
        </ConfigSection>

        {/* Environment Variables Reference */}
        <ConfigSection
          title="Required Environment Variables"
          icon={<Key className="w-5 h-5" />}
          description="These must be set in backend/.env for the SaaS features to work."
        >
          <div className="space-y-2">
            {[
              { key: 'AUTH_USERNAME', desc: 'Admin username for demo login', required: true },
              { key: 'AUTH_TOKEN', desc: 'Static bearer token (legacy compat)', required: true },
              { key: 'JWT_SECRET', desc: 'HS256 signing key for JWT tokens', required: true },
              { key: 'LLM_ENDPOINT', desc: 'OpenAI-compatible API endpoint', required: true },
              { key: 'LLM_MODEL', desc: 'Model name for LLM calls', required: true },
              { key: 'LLM_API_KEY', desc: 'API key for LLM provider', required: true },
              { key: 'DATABASE_URL', desc: 'PostgreSQL connection string (pgvector)', required: false },
              { key: 'EMBEDDINGS_ENDPOINT', desc: 'Embeddings API endpoint', required: false },
              { key: 'EMBEDDINGS_MODEL', desc: 'Embeddings model name', required: false },
              { key: 'MODEL_FAST', desc: 'Fast tier model override', required: false },
              { key: 'MODEL_DEEP', desc: 'Deep tier model override', required: false },
              { key: 'GITHUB_TOKEN', desc: 'GitHub bot/installation token', required: false },
              { key: 'GITHUB_WEBHOOK_SECRET', desc: 'HMAC secret for webhook verification', required: false },
              { key: 'WORKER_ENABLED', desc: 'Enable background worker (default: true)', required: false },
            ].map(env => (
              <div key={env.key} className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
                <div className="flex items-center gap-3">
                  <code className="text-sm font-mono text-foreground bg-surface-card px-2 py-1 rounded border">{env.key}</code>
                  <span className="text-[13px] text-foreground-muted">{env.desc}</span>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${env.required ? 'bg-danger/10 text-danger border-danger/20' : 'bg-warning/10 text-warning border-warning/20'}`}>
                  {env.required ? 'Required' : 'Optional'}
                </span>
              </div>
            ))}
          </div>
        </ConfigSection>
      </main>
    </div>
  );
}