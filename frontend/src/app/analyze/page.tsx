'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertCircle, Activity, ArrowRight, BookOpen, Check, Command, Copy,
  FileCode2, FileText, Layers, LogOut, Plus, Settings, ShieldAlert,
  Github, GitPullRequest, KeyRound, ShieldCheck, Sparkles, Terminal, Upload, X, Zap
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { analyze, fetchDemoDiff, fetchDemoRules, fetchHealth, fetchSettingsStatus, importGitHubRepository } from '@/lib/api';
import { getSettings, saveSettings, hasApiKey, type AppSettings } from '@/lib/settings';
import type { Finding } from '@/types';

const starterDiff = `diff --git a/src/api/auth.ts b/src/api/auth.ts
index e9f6d1a..0c5bb21 100644
--- a/src/api/auth.ts
+++ b/src/api/auth.ts
@@ -24,7 +24,8 @@ export async function login(req: Request) {
   const { email, password } = await req.json();
-  const user = await db.users.findFirst({ where: { email } });
+  const query = "SELECT * FROM users WHERE email = '" + email + "'";
+  const user = await db.raw(query);
   return createSession(user);
 }`;

const nav: [React.ElementType, string][] = [
  [Terminal, 'Analyze'],
  [BookOpen, 'Knowledge'],
  [Settings, 'Settings'],
];

function computeScore(findings: Finding[]): number {
  if (!findings.length) return 100;
  const weights = { High: 15, Medium: 8, Low: 3 };
  const penalty = findings.reduce((sum, f) => sum + (weights[f.severity] ?? 3), 0);
  return Math.max(0, 100 - penalty);
}

export default function AnalyzePage() {
  const { isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const rulesRef = useRef<HTMLInputElement>(null);
  const [diff, setDiff] = useState('');
  const [rules, setRules] = useState('');
  const [rulesFileName, setRulesFileName] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [screeningSuggestions, setScreeningSuggestions] = useState<{ priority: string; title: string; action: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [activeNav, setActiveNav] = useState('Analyze');
  const [sourceOpen, setSourceOpen] = useState(false);
  const [settings, setSettings] = useState<AppSettings>(getSettings);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [backendHasKey, setBackendHasKey] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [githubOpen, setGithubOpen] = useState(false);
  const [githubRepository, setGithubRepository] = useState('');
  const [githubPullNumber, setGithubPullNumber] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [githubLoading, setGithubLoading] = useState(false);

  useEffect(() => { if (!isAuthenticated) router.replace('/'); }, [isAuthenticated, router]);
  useEffect(() => { if (toast) { const id = setTimeout(() => setToast(null), 2400); return () => clearTimeout(id); } }, [toast]);

  useEffect(() => {
    fetchHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    fetchSettingsStatus()
      .then(status => {
        setBackendHasKey(status.backend_api_key_configured);
        setSettings(prev => ({
          ...prev,
          llmEndpoint: prev.llmEndpoint || status.llm_endpoint,
          llmModel: prev.llmModel || status.llm_model,
        }));
      })
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

  const upload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setDiff(String(reader.result)); setToast(`${file.name} ready to review`); };
    reader.readAsText(file);
  };

  const uploadRules = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setRules(String(reader.result));
      setRulesFileName(file.name);
      setSourceOpen(false);
      setToast(`${file.name} added to context`);
    };
    reader.readAsText(file);
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setDiff(String(reader.result)); setToast(`${file.name} ready to review`); };
    reader.readAsText(file);
  };

  const handleAnalyze = async () => {
    if (!diff.trim()) { setError('Please provide a pull request diff.'); return; }
    if (!rules.trim()) { setError('Context rules missing. Upload rules to proceed.'); return; }
    if (!hasApiKey(settings) && !backendHasKey) {
      setError('API key required. Configure it in Settings.');
      setActiveNav('Settings');
      return;
    }

    setLoading(true);
    setError(null);
    setFindings([]);
    try {
      const result = await analyze({
        diff,
        rules,
        llm_endpoint: settings.llmEndpoint || undefined,
        llm_model: settings.llmModel || undefined,
        llm_api_key: settings.llmApiKey || undefined,
      });
      if (result.error) setError(result.error);
      else {
        setFindings(result.findings.map(f => ({ ...f, severity: f.severity as 'High' | 'Medium' | 'Low' })));
        setScreeningSuggestions(result.screening_suggestions || []);
      }
    } catch (err: any) {
      setError(err.message || 'Analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const importFromGitHub = async () => {
    if (!githubRepository.trim()) return;
    setGithubLoading(true);
    setError(null);
    try {
      const result = await importGitHubRepository({
        repository: githubRepository,
        pull_number: githubPullNumber ? Number(githubPullNumber) : undefined,
        access_token: githubToken || undefined,
      });
      if (result.error) {
        setError(result.error);
        return;
      }
      setDiff(result.diff);
      if (result.policy) {
        setRules(result.policy);
        setRulesFileName(result.policy_path || 'SECURITY.md');
      }
      setFindings([]);
      setScreeningSuggestions([]);
      setGithubOpen(false);
      setGithubToken('');
      setToast(`${result.repository} imported${result.policy ? ' with security policy' : ''}`);
    } catch (err: any) {
      setError(err.message || 'Could not import this GitHub repository.');
    } finally {
      setGithubLoading(false);
    }
  };

  const saveSettingsForm = () => {
    saveSettings(settings);
    setToast('Configuration updated');
  };

  const handleLogout = () => {
    logout();
    router.replace('/');
  };

  const copy = (text: string, i: number) => {
    navigator.clipboard.writeText(text);
    setCopied(i);
    setTimeout(() => setCopied(null), 1500);
  };

  if (!isAuthenticated) return null;

  const keyConfigured = hasApiKey(settings) || backendHasKey;
  const score = computeScore(findings);

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden selection:bg-primary/30 selection:text-primary">
      {/* Dynamic Backgrounds */}
      <div className="ambient-glow bg-primary w-[800px] h-[800px] -top-[400px] -right-[200px]"></div>
      
      {/* Floating Navigation */}
      <nav className="fixed top-3 sm:top-6 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-1rem)] sm:w-[calc(100%-3rem)] max-w-5xl">
        <div className="glass-panel rounded-2xl sm:rounded-full px-3 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 sm:flex-nowrap">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-foreground flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-background" strokeWidth={2} />
            </div>
            <span className="hidden sm:inline font-semibold tracking-tight text-[15px]">CodeSentinal</span>
          </div>
          
          <div className="order-3 flex w-full items-center justify-center gap-1 sm:order-none sm:w-auto sm:gap-2">
            {nav.map(([Icon, name]) => (
              <button 
                key={name}
                onClick={() => setActiveNav(name)}
                className={`flex items-center gap-1.5 px-3 sm:px-4 py-2 rounded-full text-[12px] sm:text-[13px] font-medium transition-all duration-300 ${activeNav === name ? 'bg-white/10 text-foreground' : 'text-foreground-muted hover:text-foreground hover:bg-white/5'}`}
              >
                {activeNav === name && <Icon className="w-4 h-4" />}
                {name}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <div className="flex items-center gap-2 text-[11px] sm:text-[12px] text-foreground-muted whitespace-nowrap">
              <span className={`w-2 h-2 rounded-full ${apiOnline ? 'bg-success shadow-[0_0_10px_rgba(34,197,94,0.5)]' : 'bg-danger'}`}></span>
              {apiOnline ? 'System Online' : 'Offline'}
            </div>
            <div className="w-px h-4 bg-border"></div>
            <button onClick={handleLogout} className="text-foreground-muted hover:text-foreground transition-colors">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </nav>

      <main className="pt-40 sm:pt-32 pb-16 sm:pb-24 content-wrapper relative z-10">
        
        {activeNav === 'Settings' ? (
          <div className="max-w-2xl mx-auto animate-fade-in">
            <div className="mb-10">
              <h2 className="text-3xl font-medium tracking-tight mb-3">Configuration</h2>
              <p className="text-foreground-muted font-light">Manage your LLM provider and API access. Keys are stored locally.</p>
            </div>
            
            <div className="glass-card rounded-2xl p-5 sm:p-8 space-y-6">
              <div className="space-y-5">
                <div>
                  <label className="block text-[13px] font-medium text-foreground-muted mb-2">API Key</label>
                  <div className="flex gap-3">
                    <input
                      type={showApiKey ? 'text' : 'password'}
                      value={settings.llmApiKey}
                      onChange={e => setSettings(s => ({ ...s, llmApiKey: e.target.value }))}
                      className="flex-1 bg-surface-card border border-border rounded-xl px-4 py-3 text-[14px] focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/50 transition-all font-mono"
                      placeholder="sk-..."
                    />
                    <button 
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="px-4 py-2 rounded-xl border border-border bg-surface-card hover:bg-white/5 transition-colors text-[13px]"
                    >
                      {showApiKey ? 'Hide' : 'Show'}
                    </button>
                  </div>
                </div>
                
                <div>
                  <label className="block text-[13px] font-medium text-foreground-muted mb-2">Endpoint URL</label>
                  <input
                    type="url"
                    value={settings.llmEndpoint}
                    onChange={e => setSettings(s => ({ ...s, llmEndpoint: e.target.value }))}
                    className="w-full bg-surface-card border border-border rounded-xl px-4 py-3 text-[14px] focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/50 transition-all font-mono"
                    placeholder="https://api.openai.com/v1"
                  />
                </div>
                
                <div>
                  <label className="block text-[13px] font-medium text-foreground-muted mb-2">Model</label>
                  <input
                    type="text"
                    value={settings.llmModel}
                    onChange={e => setSettings(s => ({ ...s, llmModel: e.target.value }))}
                    className="w-full bg-surface-card border border-border rounded-xl px-4 py-3 text-[14px] focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/50 transition-all font-mono"
                    placeholder="gpt-4o"
                  />
                </div>
              </div>
              
              <div className="pt-4 border-t border-border flex justify-end">
                <button 
                  onClick={saveSettingsForm}
                  className="bg-foreground text-background px-6 py-2.5 rounded-xl font-medium text-[14px] hover:bg-white transition-all shadow-premium hover:shadow-premium-hover active:scale-[0.98]"
                >
                  Save Configuration
                </button>
              </div>
            </div>
          </div>
        ) : activeNav === 'Knowledge' ? (
          <div className="max-w-4xl mx-auto animate-fade-in">
             <div className="flex items-end justify-between mb-10">
              <div>
                <h2 className="text-3xl font-medium tracking-tight mb-3">Knowledge Base</h2>
                <p className="text-foreground-muted font-light">Provide context, security rules, and code standards for the AI.</p>
              </div>
              <button 
                onClick={() => setSourceOpen(true)}
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
                    onClick={() => { setRules(''); setRulesFileName(null); setToast('Context cleared'); }}
                    className="text-foreground-muted hover:text-danger transition-colors p-2"
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
                  Upload your organization's security guidelines, OWASP rules, or coding standards.
                </p>
                <button 
                  onClick={() => setSourceOpen(true)}
                  className="bg-foreground text-background px-6 py-2.5 rounded-xl font-medium text-[14px] hover:bg-white transition-all shadow-premium hover:shadow-premium-hover inline-flex items-center gap-2"
                >
                  <Upload className="w-4 h-4" /> Upload Document
                </button>
              </div>
            )}
          </div>
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
                
                {/* Code Editor Side */}
                <div className="flex-1 flex flex-col border-b lg:border-b-0 lg:border-r border-border min-h-[400px]">
                  <div className="bg-surface border-b border-border px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <button className="text-[12px] font-medium text-foreground border-b border-foreground pb-1">Editor</button>
                    </div>
                    <button onClick={() => fileRef.current?.click()} className="text-[12px] text-foreground-muted hover:text-foreground flex items-center gap-1.5 transition-colors">
                      <Upload className="w-3.5 h-3.5" /> Upload .diff
                    </button>
                  </div>
                  
                  <div className="flex-1 min-h-[340px] flex relative bg-[#0D0D0F]">
                    <div className="w-12 bg-surface flex flex-col items-center py-4 text-[11px] font-mono text-foreground-muted/40 border-r border-border select-none">
                      {Array.from({ length: 20 }, (_, i) => <span key={i} className="leading-6">{i + 1}</span>)}
                    </div>
                    <textarea 
                      value={diff} 
                      onChange={e => setDiff(e.target.value)} 
                      placeholder={starterDiff}
                      spellCheck={false}
                      className="min-w-0 flex-1 bg-transparent p-4 text-[13px] font-mono text-foreground/80 focus:outline-none resize-none leading-6 placeholder:text-foreground-muted/30"
                    />
                    
                    {!diff && (
                      <div 
                        onDragOver={e => e.preventDefault()}
                        onDrop={handleDrop}
                        className="absolute inset-0 m-4 sm:m-8 border-2 border-dashed border-border rounded-xl flex flex-col items-center justify-center bg-surface/50 backdrop-blur-sm"
                      >
                        <FileCode2 className="w-8 h-8 text-foreground-muted mb-3" />
                        <span className="text-[14px] font-medium">Paste diff or drag file</span>
                      </div>
                    )}
                  </div>
                  
                  <input ref={fileRef} className="hidden" type="file" accept=".diff,.patch,.txt" onChange={upload} />
                  <input ref={rulesRef} className="hidden" type="file" accept=".md,.txt" onChange={uploadRules} />
                </div>

                {/* Info Panel Side */}
                <div className="w-full lg:w-80 bg-surface/30 p-6 flex flex-col">
                  <div className="flex-1 space-y-6">
                    <div>
                      <div className="text-[11px] font-medium text-foreground-muted uppercase tracking-wider mb-3">Security Policy</div>
                      {rules ? (
                         <div className="p-3 rounded-xl bg-surface-card border border-border flex items-start gap-3">
                           <Check className="w-4 h-4 text-success mt-0.5" />
                           <div>
                            <div className="text-[13px] font-medium">{rulesFileName || 'Active Policy'}</div>
                            <div className="text-[11px] text-foreground-muted">{rules.split('\n').length} policy lines</div>
                           </div>
                         </div>
                      ) : (
                        <div className="p-3 rounded-xl border border-dashed border-border text-center">
                          <p className="text-[12px] text-foreground-muted mb-3">No policy loaded</p>
                          <button onClick={() => setSourceOpen(true)} className="text-[12px] font-medium text-foreground hover:text-primary transition-colors">
                            Add Rules
                          </button>
                        </div>
                      )}
                    </div>

                    <div>
                      <div className="text-[11px] font-medium text-foreground-muted uppercase tracking-wider mb-3">Configuration</div>
                      <div className="space-y-2 text-[12px]">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-foreground-muted">Model</span>
                          <span className="min-w-0 max-w-[11rem] truncate text-right font-mono" title={settings.llmModel || 'Default'}>{settings.llmModel || 'Default'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-foreground-muted">Key</span>
                          <span>{keyConfigured ? 'Set' : 'Missing'}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <button 
                    onClick={handleAnalyze} 
                    disabled={loading || !diff.trim()}
                    className="w-full bg-foreground text-background py-3.5 rounded-xl font-medium text-[14px] hover:bg-white transition-all shadow-premium hover:shadow-premium-hover active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-6"
                  >
                    {loading ? <span className="w-4 h-4 border-2 border-background/30 border-t-background rounded-full animate-spin" /> : <Zap className="w-4 h-4" />}
                    {loading ? 'Analyzing...' : 'Run Analysis'}
                  </button>
                </div>
              </div>
            </section>

            {/* Results Section */}
            {(findings.length > 0 || loading || error) && (
              <section className="scroll-mt-32 animate-slide-up" id="results">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
                  <div>
                    <h2 className="text-2xl font-medium tracking-tight mb-2">Report</h2>
                    <p className="text-foreground-muted font-light text-[14px]">
                      {loading ? 'AI is processing the diff...' : `Found ${findings.length} actionable items.`}
                    </p>
                  </div>
                  {!loading && findings.length > 0 && (
                     <div className="flex items-center gap-4 bg-surface-card border border-border px-4 py-2 rounded-2xl">
                       <div className="text-right">
                         <div className="text-[10px] text-foreground-muted uppercase tracking-wider">Score</div>
                         <div className="text-xl font-medium">{score}<span className="text-[12px] text-foreground-muted">/100</span></div>
                       </div>
                       <div className="w-10 h-10 rounded-full border-4 flex items-center justify-center" style={{ borderColor: score > 80 ? '#22c55e' : score > 50 ? '#f59e0b' : '#ef4444' }}>
                         <ShieldAlert className="w-4 h-4" style={{ color: score > 80 ? '#22c55e' : score > 50 ? '#f59e0b' : '#ef4444' }} />
                       </div>
                     </div>
                  )}
                </div>

                {loading ? (
                  <div className="glass-card rounded-2xl p-12 text-center border border-border">
                    <div className="w-12 h-12 rounded-full border-2 border-border border-t-primary animate-spin mx-auto mb-6"></div>
                    <h3 className="text-[16px] font-medium mb-2">Analyzing Architecture</h3>
                    <p className="text-[14px] text-foreground-muted font-light">Cross-referencing diff against security context...</p>
                  </div>
                ) : error ? (
                  <div className="glass-card rounded-2xl p-8 border border-danger/30 bg-danger/5 flex items-start gap-4">
                     <AlertCircle className="w-6 h-6 text-danger shrink-0" />
                     <div>
                       <h3 className="text-[15px] font-medium text-danger mb-1">Analysis Failed</h3>
                       <p className="text-[14px] text-danger/80 mb-4">{error}</p>
                       <button onClick={() => setError(null)} className="text-[12px] px-3 py-1.5 rounded-lg border border-danger/30 hover:bg-danger/10 transition-colors">Dismiss</button>
                     </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {findings.map((f, i) => (
                      <div key={i} className="glass-card rounded-2xl border border-border overflow-hidden animate-slide-up" style={{ animationDelay: `${i * 0.1}s` }}>
                        <div className="p-6 border-b border-border flex flex-col md:flex-row md:items-start justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-3 mb-2">
                              <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                                f.severity === 'High' ? 'bg-danger/10 text-danger border border-danger/20' : 
                                f.severity === 'Medium' ? 'bg-warning/10 text-warning border border-warning/20' : 
                                'bg-success/10 text-success border border-success/20'
                              }`}>
                                {f.severity}
                              </span>
                              <h3 className="text-[16px] font-medium">{f.risk}</h3>
                            </div>
                            <p className="text-[14px] text-foreground-muted leading-relaxed max-w-3xl">{f.rule_violation}</p>
                          </div>
                          <div className="bg-surface rounded-lg px-3 py-1.5 border border-border text-[12px] font-mono text-foreground-muted shrink-0 flex items-center gap-2">
                            <FileCode2 className="w-3.5 h-3.5" /> {f.file_line}
                          </div>
                        </div>
                        
                        <div className="bg-surface/50 p-6 relative group">
                          <div className="flex items-center justify-between gap-3 mb-3">
                            <div className="flex items-center gap-2 text-[12px] font-medium text-primary">
                              <Sparkles className="w-3.5 h-3.5" /> Suggested Fix
                            </div>
                            <button 
                              onClick={() => copy(f.safer_code, i)}
                              className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity bg-surface-card border border-border px-3 py-1.5 rounded-lg text-[11px] flex items-center gap-1.5 hover:bg-white/10"
                            >
                              {copied === i ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                              {copied === i ? 'Copied' : 'Copy'}
                            </button>
                          </div>
                          <pre className="text-[13px] font-mono text-foreground/90 overflow-x-auto p-4 rounded-xl bg-[#09090B] border border-border/50 shadow-inner">
                            {f.safer_code}
                          </pre>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}

            {screeningSuggestions.length > 0 && !loading && !error && (
              <section className="scroll-mt-32 animate-slide-up" id="screening">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-9 h-9 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
                    <ShieldCheck className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-xl font-medium tracking-tight">Screening checklist</h2>
                    <p className="text-[13px] text-foreground-muted">Model-guided checks to complete before merging.</p>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {screeningSuggestions.map((suggestion, index) => (
                    <div key={index} className="glass-card rounded-2xl border border-border p-5">
                      <div className="flex items-center gap-2 mb-3">
                        <span className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                          suggestion.priority === 'High' ? 'bg-danger/10 text-danger' : suggestion.priority === 'Medium' ? 'bg-warning/10 text-warning' : 'bg-success/10 text-success'
                        }`}>{suggestion.priority}</span>
                        <h3 className="text-[13px] font-medium">{suggestion.title}</h3>
                      </div>
                      <p className="text-[13px] leading-relaxed text-foreground-muted">{suggestion.action}</p>
                    </div>
                  ))}
                </div>
              </section>
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
      {sourceOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-fade-in" onMouseDown={() => setSourceOpen(false)}>
          <div className="glass-card w-full max-w-md max-h-[calc(100vh-2rem)] overflow-y-auto rounded-3xl p-5 sm:p-8 border border-border shadow-premium" onMouseDown={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-medium tracking-tight">Add Context</h3>
              <button onClick={() => setSourceOpen(false)} className="w-8 h-8 rounded-full bg-surface-card flex items-center justify-center hover:bg-white/10 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <p className="text-[14px] text-foreground-muted mb-8 font-light">
              Upload a Markdown (.md) or Text (.txt) file containing your organization's security guidelines, OWASP standards, or custom AI instructions.
            </p>
            
            <button 
              onClick={() => rulesRef.current?.click()}
              className="w-full bg-surface border border-border border-dashed hover:border-primary/50 hover:bg-primary/5 transition-all p-8 rounded-2xl flex flex-col items-center justify-center gap-3 group"
            >
              <div className="w-12 h-12 rounded-full bg-surface-card flex items-center justify-center group-hover:scale-110 transition-transform">
                <Upload className="w-5 h-5 text-foreground-muted group-hover:text-primary transition-colors" />
              </div>
              <div>
                <div className="text-[14px] font-medium mb-1">Click to upload rules</div>
                <div className="text-[12px] text-foreground-muted">.md or .txt files only</div>
              </div>
            </button>
          </div>
        </div>
      )}

      {githubOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-fade-in" onMouseDown={() => setGithubOpen(false)}>
          <div className="glass-card w-full max-w-md max-h-[calc(100vh-2rem)] overflow-y-auto rounded-3xl p-5 sm:p-8 border border-border shadow-premium" onMouseDown={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-surface-card border border-border flex items-center justify-center"><Github className="w-5 h-5" /></div>
                <div><h3 className="text-xl font-medium tracking-tight">Import from GitHub</h3><p className="text-[12px] text-foreground-muted">Load a diff and repository security policy.</p></div>
              </div>
              <button onClick={() => setGithubOpen(false)} className="w-8 h-8 rounded-full bg-surface-card flex items-center justify-center hover:bg-white/10 transition-colors"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-4">
              <label className="block text-[13px] font-medium text-foreground-muted">Repository
                <input value={githubRepository} onChange={e => setGithubRepository(e.target.value)} placeholder="owner/repository or github.com/owner/repository" className="mt-2 w-full bg-surface-card border border-border rounded-xl px-4 py-3 text-[13px] focus:outline-none focus:border-primary" />
              </label>
              <label className="block text-[13px] font-medium text-foreground-muted">Pull request number <span className="font-normal">(optional)</span>
                <div className="relative mt-2"><GitPullRequest className="absolute left-3 top-3.5 w-4 h-4 text-foreground-muted" /><input inputMode="numeric" value={githubPullNumber} onChange={e => setGithubPullNumber(e.target.value.replace(/\D/g, ''))} placeholder="Latest commit comparison when empty" className="w-full bg-surface-card border border-border rounded-xl pl-10 pr-4 py-3 text-[13px] focus:outline-none focus:border-primary" /></div>
              </label>
              <label className="block text-[13px] font-medium text-foreground-muted">GitHub access token <span className="font-normal">(only for private repositories)</span>
                <div className="relative mt-2"><KeyRound className="absolute left-3 top-3.5 w-4 h-4 text-foreground-muted" /><input type="password" value={githubToken} onChange={e => setGithubToken(e.target.value)} placeholder="Fine-grained token with repository read access" className="w-full bg-surface-card border border-border rounded-xl pl-10 pr-4 py-3 text-[13px] focus:outline-none focus:border-primary" /></div>
              </label>
              <p className="text-[12px] leading-relaxed text-foreground-muted">Tokens are used only for this import and are not stored. The importer looks for <code>SECURITY.md</code>, <code>.github/SECURITY.md</code>, or <code>SECURITY_POLICY.md</code>.</p>
              <button onClick={importFromGitHub} disabled={!githubRepository.trim() || githubLoading} className="w-full bg-foreground text-background py-3 rounded-xl font-medium text-[14px] hover:bg-white transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                {githubLoading ? <span className="w-4 h-4 border-2 border-background/30 border-t-background rounded-full animate-spin" /> : <Github className="w-4 h-4" />}{githubLoading ? 'Importing…' : 'Import repository'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
