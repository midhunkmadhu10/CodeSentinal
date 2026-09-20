'use client';

import React, { useState } from 'react';
import { GitPullRequest, Github, KeyRound, X } from 'lucide-react';
import { importGitHubRepository } from '@/lib/api';

interface GitHubImportModalProps {
  open: boolean;
  onClose: () => void;
  onImported: (result: { repository: string; diff: string; policy: string | null; policy_path: string | null }) => void;
}

export default function GitHubImportModal({ open, onClose, onImported }: GitHubImportModalProps) {
  const [repository, setRepository] = useState('');
  const [pullNumber, setPullNumber] = useState('');
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleImport = async () => {
    if (!repository.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await importGitHubRepository({
        repository,
        pull_number: pullNumber ? Number(pullNumber) : undefined,
        access_token: token || undefined,
      });
      if (result.error) {
        setError(result.error);
        return;
      }
      setRepository('');
      setPullNumber('');
      setToken('');
      onImported(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not import this GitHub repository.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-fade-in" onMouseDown={onClose}>
      <div className="glass-card w-full max-w-md max-h-[calc(100vh-2rem)] overflow-y-auto rounded-3xl p-5 sm:p-8 border border-border shadow-premium" onMouseDown={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-surface-card border border-border flex items-center justify-center"><Github className="w-5 h-5" /></div>
            <div><h3 className="text-xl font-medium tracking-tight">Import from GitHub</h3><p className="text-[12px] text-foreground-muted">Load a diff and repository security policy.</p></div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-surface-card flex items-center justify-center hover:bg-white/10 transition-colors" aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-4">
          <label className="block text-[13px] font-medium text-foreground-muted">Repository
            <input value={repository} onChange={e => setRepository(e.target.value)} placeholder="owner/repository or github.com/owner/repository" className="mt-2 w-full bg-surface-card border border-border rounded-xl px-4 py-3 text-[13px] focus:outline-none focus:border-primary" />
          </label>
          <label className="block text-[13px] font-medium text-foreground-muted">Pull request number <span className="font-normal">(optional)</span>
            <div className="relative mt-2"><GitPullRequest className="absolute left-3 top-3.5 w-4 h-4 text-foreground-muted" /><input inputMode="numeric" value={pullNumber} onChange={e => setPullNumber(e.target.value.replace(/\D/g, ''))} placeholder="Latest commit comparison when empty" className="w-full bg-surface-card border border-border rounded-xl pl-10 pr-4 py-3 text-[13px] focus:outline-none focus:border-primary" /></div>
          </label>
          <label className="block text-[13px] font-medium text-foreground-muted">GitHub access token <span className="font-normal">(only for private repositories)</span>
            <div className="relative mt-2"><KeyRound className="absolute left-3 top-3.5 w-4 h-4 text-foreground-muted" /><input type="password" value={token} onChange={e => setToken(e.target.value)} placeholder="Fine-grained token with repository read access" className="w-full bg-surface-card border border-border rounded-xl pl-10 pr-4 py-3 text-[13px] focus:outline-none focus:border-primary" /></div>
          </label>
          <p className="text-[12px] leading-relaxed text-foreground-muted">Tokens are used only for this import and are not stored. The importer looks for <code>SECURITY.md</code>, <code>.github/SECURITY.md</code>, or <code>SECURITY_POLICY.md</code>.</p>
          {error && (
            <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-[13px] text-danger">{error}</div>
          )}
          <button onClick={handleImport} disabled={!repository.trim() || loading} className="w-full bg-foreground text-background py-3 rounded-xl font-medium text-[14px] hover:bg-white transition-all disabled:opacity-50 flex items-center justify-center gap-2">
            {loading ? <span className="w-4 h-4 border-2 border-background/30 border-t-background rounded-full animate-spin" /> : <Github className="w-4 h-4" />}{loading ? 'Importing…' : 'Import repository'}
          </button>
        </div>
      </div>
    </div>
  );
}
