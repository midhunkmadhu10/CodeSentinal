'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Activity, ArrowRight, Check, Command, FileText, Github, X,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  analyze, fetchDemoDiff, fetchDemoRules, fetchHealth,
  fetchSettingsStatus, type SettingsStatus,
} from '@/lib/api';
import { loadUpload } from '@/lib/upload';
import type { Finding } from '@/types';
import AnalyzeHeader, { type NavSection } from '@/components/analyze/AnalyzeHeader';
import DiffEditor, { starterDiff } from '@/components/analyze/DiffEditor';
import PolicyPanel from '@/components/analyze/PolicyPanel';
import AnalysisResults from '@/components/analyze/AnalysisResults';
import ScreeningChecklist from '@/components/analyze/ScreeningChecklist';
import SettingsPanel from '@/components/analyze/SettingsPanel';
import KnowledgeBase from '@/components/analyze/KnowledgeBase';
import GitHubImportModal from '@/components/analyze/GitHubImportModal';

export default function AnalyzePage() {
  const { isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const rulesRef = useRef<HTMLInputElement>(null);
  const [diff, setDiff] = useState('');
  const [rules, setRules] = useState('');
  const [rulesFileName, setRulesFileName] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [screeningSuggestions, setScreeningSuggestions] = useState<{ priority: string; title: string; action: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [activeNav, setActiveNav] = useState<NavSection>('Analyze');
  const [addContextOpen, setAddContextOpen] = useState(false);
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [githubOpen, setGithubOpen] = useState(false);

  useEffect(() => { if (!isAuthenticated) router.replace('/'); }, [isAuthenticated, router]);
  useEffect(() => { if (toast) { const id = setTimeout(() => setToast(null), 2400); return () => clearTimeout(id); } }, [toast]);

  useEffect(() => {
    fetchHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    fetchSettingsStatus()
      .then(setStatus)
      .catch(() => {});
  }, []);

  const demo = async () => {
    try {
      const [d, r] = await Promise.all([fetchDemoDiff(), fetchDemoRules()]);
      setDiff(d);
      setRules(r);
      setRulesFileName('sample_rules.md');
      setFindings([]);
      setScreeningSuggestions([]);
      setToast('Demo pull request loaded');
    } catch {
      setDiff(starterDiff);
      setToast('Example pull request loaded');
    }
  };

  const uploadRules = async (file: File | undefined | null) => {
    if (!file) return;
    const result = await loadUpload(file, 'rules');
    if ('error' in result) {
      setError(result.error);
      return;
    }
    setRules(result.content);
    setRulesFileName(file.name);
    setAddContextOpen(false);
    setToast(`${file.name} added to context`);
  };

  const handleAnalyze = async () => {
    if (!diff.trim()) { setError('Please provide a pull request diff.'); return; }
    if (!rules.trim()) { setError('Context rules missing. Upload rules to proceed.'); return; }

    setLoading(true);
    setError(null);
    setFindings([]);
    try {
      const result = await analyze({ diff, rules });
      if (result.error) setError(result.error);
      else {
        setFindings(result.findings.map(f => ({ ...f, severity: f.severity as Finding['severity'] })));
        setScreeningSuggestions(result.screening_suggestions || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    router.replace('/');
  };

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden selection:bg-primary/30 selection:text-primary">
      {/* Dynamic Backgrounds */}
      <div className="ambient-glow bg-primary w-[800px] h-[800px] -top-[400px] -right-[200px]"></div>

      <AnalyzeHeader
        activeNav={activeNav}
        onNavChange={setActiveNav}
        apiOnline={apiOnline}
        onLogout={handleLogout}
      />

      <main className="pt-40 sm:pt-32 pb-16 sm:pb-24 content-wrapper relative z-10">

        {activeNav === 'Settings' ? (
          <SettingsPanel status={status} />
        ) : activeNav === 'Knowledge' ? (
          <KnowledgeBase
            rules={rules}
            rulesFileName={rulesFileName}
            onClear={() => { setRules(''); setRulesFileName(null); setToast('Context cleared'); }}
            onAddContext={() => setAddContextOpen(true)}
          />
        ) : (
          <div className="space-y-16 sm:space-y-24 animate-fade-in">
            {/* Cinematic Hero */}
            <section className="flex flex-col lg:flex-row items-center gap-10 lg:gap-16 py-6 sm:py-12">
              <div className="flex-1 space-y-8 z-10">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/30 bg-primary/10 text-primary text-[11px] font-medium tracking-wide uppercase">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                  Engine v2.4 Active
                </div>
                <h1 className="text-4xl sm:text-5xl lg:text-7xl font-medium tracking-tighter leading-[1.1]">
                  Precision <br/>
                  <span className="text-foreground-muted">Security Review.</span>
                </h1>
                <p className="text-lg text-foreground-muted font-light max-w-md leading-relaxed">
                  Automate your pull request reviews with autonomous AI intelligence. Detect vulnerabilities before they merge.
                </p>

                <div className="flex flex-wrap items-center gap-3 sm:gap-4 pt-2 sm:pt-4">
                  <button
                    onClick={() => {
                      const el = document.getElementById('analyzer');
                      el?.scrollIntoView({ behavior: 'smooth' });
                    }}
                    className="bg-foreground text-background px-7 py-3.5 rounded-xl font-medium text-[15px] hover:bg-white transition-all shadow-premium hover:shadow-premium-hover active:scale-[0.98] flex items-center gap-2"
                  >
                    Start Analysis <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={demo}
                    className="bg-surface-card border border-border hover:bg-white/10 px-7 py-3.5 rounded-xl font-medium text-[15px] transition-all flex items-center gap-2"
                  >
                    <Command className="w-4 h-4" /> Load Demo
                  </button>
                  <button
                    onClick={() => setGithubOpen(true)}
                    className="bg-surface-card border border-border hover:bg-white/10 px-7 py-3.5 rounded-xl font-medium text-[15px] transition-all flex items-center gap-2"
                  >
                    <Github className="w-4 h-4" /> Import GitHub
                  </button>
                </div>
              </div>

              {/* Abstract AI Visual */}
              <div className="flex-1 relative h-[500px] w-full max-w-lg hidden lg:block">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-[300px] h-[300px] rounded-full border border-border border-dashed animate-[spin_60s_linear_infinite]"></div>
                  <div className="absolute w-[400px] h-[400px] rounded-full border border-border opacity-50 animate-[spin_40s_linear_infinite_reverse]"></div>

                  <div className="absolute w-[200px] h-[200px] bg-primary/5 rounded-full blur-2xl"></div>

                  <div className="glass-panel absolute p-6 rounded-2xl w-64 backdrop-blur-3xl border border-white/10 shadow-2xl -translate-x-12 -translate-y-12">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                        <Activity className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <div className="text-[10px] text-foreground-muted uppercase tracking-wider">Status</div>
                        <div className="text-[13px] font-medium">Scanning Diff</div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="h-1.5 w-full bg-surface-card rounded-full overflow-hidden">
                        <div className="h-full bg-primary w-2/3 rounded-full"></div>
                      </div>
                      <div className="h-1.5 w-4/5 bg-surface-card rounded-full overflow-hidden">
                        <div className="h-full bg-accent w-1/2 rounded-full"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Dashboard / Editor section */}
            <section id="analyzer" className="scroll-mt-32">
              <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-6 sm:mb-8">
                <div>
                  <h2 className="text-2xl font-medium tracking-tight mb-2">Analysis Engine</h2>
                  <p className="text-foreground-muted font-light text-[14px]">Provide your diff below to run the security check.</p>
                </div>
                <button
                  onClick={() => setGithubOpen(true)}
                  className="self-start sm:self-auto text-[13px] text-foreground-muted hover:text-foreground flex items-center gap-2 transition-colors"
                >
                  <Github className="w-4 h-4" /> Connect repository
                </button>
              </div>

              <div className="glass-card rounded-2xl overflow-hidden border border-border flex flex-col lg:flex-row">
                <DiffEditor
                  diff={diff}
                  onChange={setDiff}
                  onToast={setToast}
                  onError={setError}
                />

                <PolicyPanel
                  rules={rules}
                  rulesFileName={rulesFileName}
                  llmConfigured={status === null ? null : status.llm_configured}
                  llmModel={status?.llm_model || ''}
                  loading={loading}
                  canAnalyze={!!diff.trim()}
                  onAnalyze={handleAnalyze}
                  onAddContext={() => setAddContextOpen(true)}
                />
              </div>
            </section>

            <AnalysisResults
              findings={findings}
              loading={loading}
              error={error}
              onDismissError={() => setError(null)}
            />

            {!loading && !error && (
              <ScreeningChecklist suggestions={screeningSuggestions} />
            )}

          </div>
        )}
      </main>

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-4 left-4 right-4 sm:left-auto sm:bottom-8 sm:right-8 z-50 animate-slide-up">
          <div className="glass-panel px-5 py-3 rounded-xl flex items-center gap-3 border border-border/50 shadow-premium">
            <Check className="w-4 h-4 text-success" />
            <span className="text-[13px] font-medium">{toast}</span>
          </div>
        </div>
      )}

      {/* Rules Upload Modal */}
      {addContextOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-fade-in" onMouseDown={() => setAddContextOpen(false)}>
          <div className="glass-card w-full max-w-md max-h-[calc(100vh-2rem)] overflow-y-auto rounded-3xl p-5 sm:p-8 border border-border shadow-premium" onMouseDown={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-medium tracking-tight">Add Context</h3>
              <button onClick={() => setAddContextOpen(false)} className="w-8 h-8 rounded-full bg-surface-card flex items-center justify-center hover:bg-white/10 transition-colors" aria-label="Close">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-[14px] text-foreground-muted mb-8 font-light">
              Upload a Markdown (.md) or Text (.txt) file containing your organization&apos;s security guidelines, OWASP standards, or custom AI instructions.
            </p>

            <button
              onClick={() => rulesRef.current?.click()}
              className="w-full bg-surface border border-border border-dashed hover:border-primary/50 hover:bg-primary/5 transition-all p-8 rounded-2xl flex flex-col items-center justify-center gap-3 group"
            >
              <div className="w-12 h-12 rounded-full bg-surface-card flex items-center justify-center group-hover:scale-110 transition-transform">
                <FileText className="w-5 h-5 text-foreground-muted group-hover:text-primary transition-colors" />
              </div>
              <div>
                <div className="text-[14px] font-medium mb-1">Click to upload rules</div>
                <div className="text-[12px] text-foreground-muted">.md or .txt files only, up to 1 MB</div>
              </div>
            </button>
          </div>
        </div>
      )}

      <input
        ref={rulesRef}
        className="hidden"
        type="file"
        accept=".md,.txt"
        onChange={e => {
          uploadRules(e.target.files?.[0]);
          e.target.value = '';
        }}
      />

      <GitHubImportModal
        open={githubOpen}
        onClose={() => setGithubOpen(false)}
        onImported={result => {
          setDiff(result.diff);
          if (result.policy) {
            setRules(result.policy);
            setRulesFileName(result.policy_path || 'SECURITY.md');
          }
          setFindings([]);
          setScreeningSuggestions([]);
          setGithubOpen(false);
          setToast(`${result.repository} imported${result.policy ? ' with security policy' : ''}`);
        }}
      />
    </div>
  );
}
