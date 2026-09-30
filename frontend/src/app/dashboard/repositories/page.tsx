'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
  listRepositories,
  connectRepository,
  deleteRepository,
  triggerRepositoryIndex,
  getRepository,
  type Repository,
} from '@/lib/api';
import {
  Shield, Plus, Trash2, RefreshCw, ExternalLink,
  AlertTriangle, AlertCircle, CheckCircle, Clock,
  FileText, FolderGit2, Database, Search, Zap,
  MoreVertical, Settings,
} from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-success bg-success/10 border-success/20',
  pending: 'text-warning bg-warning/10 border-warning/20',
  indexing: 'text-primary bg-primary/10 border-primary/20 animate-pulse',
  failed: 'text-danger bg-danger/10 border-danger/20',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle className="w-4 h-4" />,
  pending: <Clock className="w-4 h-4" />,
  indexing: <RefreshCw className="w-4 h-4 animate-spin" />,
  failed: <AlertCircle className="w-4 h-4" />,
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-1 rounded-full text-[11px] font-medium border flex items-center gap-1.5 ${STATUS_COLORS[status] || STATUS_COLORS.pending}`}>
      {STATUS_ICONS[status] || STATUS_ICONS.pending}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function RepositoryCard({ repo, onRefresh, onDelete, indexing }: { repo: Repository; onRefresh: () => void; onDelete: (id: number) => void; indexing: Set<number> }) {
  const isIndexing = indexing.has(repo.id);
  const status = isIndexing ? 'indexing' : repo.index_status;

  return (
    <div className="glass-panel rounded-2xl p-6 border hover:border-primary/30 transition-all group relative">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <FolderGit2 className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h3 className="font-medium text-foreground">{repo.full_name}</h3>
            <p className="text-[13px] text-foreground-muted">{repo.default_branch} branch • {repo.is_private ? 'Private' : 'Public'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={status} />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-4 p-4 bg-surface-card/50 rounded-xl border border-border/50">
        <div className="text-center">
          <p className="text-2xl font-medium text-foreground">{repo.chunk_count}</p>
          <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Chunks</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-medium text-foreground">{repo.symbol_count}</p>
          <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Symbols</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-medium text-foreground">{repo.file_count}</p>
          <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Files</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-medium text-foreground">{repo.graph_nodes + repo.graph_edges}</p>
          <p className="text-[11px] text-foreground-muted uppercase tracking-wider">Graph</p>
        </div>
      </div>

      {/* Index Info */}
      {(repo.indexed_at || repo.last_error) && (
        <div className="mb-4 p-3 bg-surface-card/50 rounded-xl border border-border/50 text-sm">
          {repo.indexed_at && (
            <div className="flex items-center gap-2 text-foreground-muted mb-1">
              <Clock className="w-3.5 h-3.5" />
              <span>Last indexed: {new Date(repo.indexed_at).toLocaleString()}</span>
            </div>
          )}
          {repo.last_error && (
            <div className="flex items-center gap-2 text-danger">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span className="truncate">Error: {repo.last_error}</span>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2 pt-4 border-t border-border/50">
        <button
          onClick={() => onRefresh()}
          disabled={isIndexing}
          className="flex-1 sm:flex-none px-4 py-2 rounded-lg text-sm font-medium text-foreground-muted hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors bg-surface-card border border-border hover:bg-white/5 flex items-center justify-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${isIndexing ? 'animate-spin' : ''}`} />
          {isIndexing ? 'Indexing...' : 'Re-index'}
        </button>
        <a
          href={`https://github.com/${repo.full_name}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 sm:flex-none px-4 py-2 rounded-lg text-sm font-medium text-primary hover:bg-primary/10 transition-colors text-center flex items-center justify-center gap-2"
        >
          <ExternalLink className="w-4 h-4" />
          View on GitHub
        </a>
        <button
          onClick={() => {
            if (confirm(`Delete ${repo.full_name}? This cannot be undone.`)) {
              onDelete(repo.id);
            }
          }}
          disabled={isIndexing}
          className="flex-1 sm:flex-none px-4 py-2 rounded-lg text-sm font-medium text-danger hover:bg-danger/10 transition-colors border border-danger/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <Trash2 className="w-4 h-4" />
          Delete
        </button>
      </div>
    </div>
  );
}

function ConnectRepositoryForm({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [repository, setRepository] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!repository.trim()) {
      setError('Please enter a repository (e.g., owner/name)');
      return;
    }

    setLoading(true);
    try {
      await connectRepository({ repository, access_token: accessToken || undefined });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to connect repository');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div className="glass-card w-full max-w-md max-h-[calc(100vh-2rem)] overflow-y-auto rounded-3xl p-5 sm:p-8 border border-border shadow-premium" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-medium tracking-tight">Connect Repository</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-surface-card flex items-center justify-center hover:bg-white/10 transition-colors">
            <MoreVertical className="w-4 h-4" style={{ transform: 'rotate(90deg)' }} />
          </button>
        </div>

        <p className="text-[14px] text-foreground-muted mb-6 font-light">
          Enter a GitHub repository in the format <code className="bg-surface px-1.5 py-0.5 rounded text-sm font-mono">owner/name</code>.
          Optionally provide a GitHub token for private repos or higher rate limits.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="repository" className="block text-sm font-medium text-foreground mb-2">Repository</label>
            <input
              id="repository"
              type="text"
              value={repository}
              onChange={e => setRepository(e.target.value)}
              placeholder="owner/name"
              className="w-full px-4 py-3 bg-surface-card border border-border rounded-xl text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all"
              disabled={loading}
            />
          </div>
          <div>
            <label htmlFor="accessToken" className="block text-sm font-medium text-foreground mb-2">GitHub Token (optional)</label>
            <input
              id="accessToken"
              type="password"
              value={accessToken}
              onChange={e => setAccessToken(e.target.value)}
              placeholder="ghp_..."
              className="w-full px-4 py-3 bg-surface-card border border-border rounded-xl text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all"
              disabled={loading}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 rounded-xl font-medium text-foreground-muted hover:text-foreground transition-colors bg-surface-card border border-border hover:bg-white/5"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-xl font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  Connect
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function RepositoriesPage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConnect, setShowConnect] = useState(false);
  const [indexing, setIndexing] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    const loadRepos = async () => {
      try {
        setLoading(true);
        const data = await listRepositories();
        setRepos(data);
      } catch (err) {
        setError('Failed to load repositories');
      } finally {
        setLoading(false);
      }
    };
    loadRepos();
  }, []);

  const handleRefresh = async (repoId: number) => {
    setIndexing(prev => new Set(prev).add(repoId));
    try {
      await triggerRepositoryIndex(repoId);
      // Reload to get updated status
      const data = await listRepositories();
      setRepos(data);
    } catch (err) {
      setError('Failed to trigger indexing');
    } finally {
      setIndexing(prev => {
        const next = new Set(prev);
        next.delete(repoId);
        return next;
      });
    }
  };

  const handleDelete = async (repoId: number) => {
    try {
      await deleteRepository(repoId);
      setRepos(prev => prev.filter(r => r.id !== repoId));
    } catch (err) {
      setError('Failed to delete repository');
    }
  };

  const handleConnectSuccess = () => {
    // Reload repos
    listRepositories().then(setRepos).catch(() => {});
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
              <a href="/dashboard/repositories" className="px-3 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium">Repositories</a>
              <a href="/dashboard/settings" className="px-3 py-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-white/5 text-sm font-medium transition-colors">Settings</a>
            </nav>
          </div>
        </div>
      </header>

      <main className="pt-20 sm:pt-16 pb-16 content-wrapper relative z-10 animate-fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-10 sm:mb-14">
          <div>
            <h1 className="text-3xl sm:text-4xl font-medium tracking-tight text-foreground mb-2">Repositories</h1>
            <p className="text-foreground-muted font-light text-[15px]">Manage connected GitHub repositories and code indexing.</p>
          </div>
          <button
            onClick={() => setShowConnect(true)}
            className="px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium text-sm hover:bg-primary/90 transition-colors flex items-center gap-2 self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            Connect Repository
          </button>
        </div>

        {error && (
          <div className="mb-8 p-4 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="glass-panel rounded-2xl p-6 border animate-pulse">
                <div className="h-6 bg-surface-card rounded w-3/4 mb-4" />
                <div className="h-4 bg-surface-card rounded w-1/2 mb-4" />
                <div className="grid grid-cols-4 gap-4">
                  {[1, 2, 3, 4].map(j => (
                    <div key={j} className="h-16 bg-surface-card rounded" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : repos.length === 0 ? (
          <div className="glass-panel rounded-2xl p-12 border text-center">
            <FolderGit2 className="w-16 h-16 mx-auto text-foreground-muted/30 mb-6" />
            <h2 className="text-xl font-medium text-foreground mb-2">No repositories connected</h2>
            <p className="text-foreground-muted mb-6 max-w-md mx-auto">
              Connect a GitHub repository to enable automatic PR reviews, code graph analysis, and repository-aware security scanning.
            </p>
            <button
              onClick={() => setShowConnect(true)}
              className="px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium text-sm hover:bg-primary/90 transition-colors flex items-center gap-2 mx-auto"
            >
              <Plus className="w-4 h-4" />
              Connect Your First Repository
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {repos.map(repo => (
              <RepositoryCard
                key={repo.id}
                repo={repo}
                onRefresh={() => handleRefresh(repo.id)}
                onDelete={handleDelete}
                indexing={indexing}
              />
            ))}
          </div>
        )}

        {/* Info Panel */}
        <div className="mt-12 glass-panel rounded-2xl p-6 border">
          <h2 className="text-lg font-medium tracking-tight mb-4 flex items-center gap-2">
            <Database className="w-5 h-5 text-accent" />
            How Repository Indexing Works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-foreground-muted">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                  <FileText className="w-4 h-4 text-primary" />
                </div>
                <span className="font-medium text-foreground">Code Chunking</span>
              </div>
              <p>Repository files are split into overlapping chunks (60 lines, 8 overlap) for semantic search.</p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Zap className="w-4 h-4 text-accent" />
                </div>
                <span className="font-medium text-foreground">Embeddings</span>
              </div>
              <p>Chunks are embedded and stored in pgvector (PostgreSQL) for fast similarity search. Falls back to TF-IDF if unavailable.</p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-purple/10 flex items-center justify-center">
                  <Settings className="w-4 h-4 text-purple" />
                </div>
                <span className="font-medium text-foreground">Code Graph</span>
              </div>
              <p>AST-based symbol extraction builds a call/import graph for context-aware agent reviews.</p>
            </div>
          </div>
        </div>
      </main>

      {showConnect && (
        <ConnectRepositoryForm onClose={() => setShowConnect(false)} onSuccess={handleConnectSuccess} />
      )}
    </div>
  );
}