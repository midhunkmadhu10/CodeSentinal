const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'codesentinal_token';

export function getToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/api/auth/login') && !path.startsWith('/api/auth/token') && !path.startsWith('/api/auth/register')) {
      clearToken();
      if (typeof window !== 'undefined') {
        window.location.assign('/');
      }
    }
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with status ${res.status}`);
  }

  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────

export async function register(email: string, password: string, name: string = ''): Promise<{ access_token: string; token_type: string; user: User }> {
  const data = await apiRequest<{ access_token: string; token_type: string; user: User }>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  });
  return data;
}

export async function login(username: string, password: string): Promise<string> {
  const data = await apiRequest<{ token: string }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  return data.token;
}

export async function loginWithEmail(email: string, password: string): Promise<{ access_token: string; token_type: string; user: User }> {
  const data = await apiRequest<{ access_token: string; token_type: string; user: User }>('/api/auth/token', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  return data;
}

export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
}

export async function getMe(): Promise<User> {
  return apiRequest<User>('/api/auth/me');
}

// ── Health / Settings ────────────────────────────────────────────────────

export async function fetchHealth(): Promise<{ status: string; service: string; version: string }> {
  return apiRequest('/api/health');
}

export interface SettingsStatus {
  llm_configured: boolean;
  llm_endpoint: string;
  llm_model: string;
  embeddings_configured: boolean;
  database: string;
  pgvector_enabled: boolean;
  worker_running: boolean;
  routing: {
    fast: { model: string; cost_per_1m_in: number; cost_per_1m_out: number };
    deep: { model: string; cost_per_1m_in: number; cost_per_1m_out: number };
    threshold: number;
  };
}

export async function fetchSettingsStatus(): Promise<SettingsStatus> {
  return apiRequest<SettingsStatus>('/api/settings/status');
}

// ── Demo ──────────────────────────────────────────────────────────────────

export async function fetchDemoDiff(): Promise<string> {
  const data = await apiRequest<{ diff: string }>('/api/demo/diff');
  return data.diff;
}

export async function fetchDemoRules(): Promise<string> {
  const data = await apiRequest<{ rules: string }>('/api/demo/rules');
  return data.rules;
}

// ── Legacy Analyze ────────────────────────────────────────────────────────

export interface AnalyzeParams {
  diff: string;
  rules: string;
}

export interface AnalyzeResult {
  findings: {
    severity: string;
    file_line: string;
    risk: string;
    rule_violation: string;
    safer_code: string;
    source_chunk: string;
  }[];
  screening_suggestions: { priority: string; title: string; action: string }[];
  error: string | null;
}

export async function analyze(params: AnalyzeParams): Promise<AnalyzeResult> {
  return apiRequest<AnalyzeResult>('/api/analyze', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ── Legacy GitHub Import ──────────────────────────────────────────────────

export interface GitHubImportParams {
  repository: string;
  pull_number?: number;
  access_token?: string;
}

export interface GitHubImportResult {
  repository: string;
  diff: string;
  policy: string | null;
  policy_path: string | null;
  error: string | null;
}

export async function importGitHubRepository(params: GitHubImportParams): Promise<GitHubImportResult> {
  return apiRequest<GitHubImportResult>('/api/github/import', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ── SaaS: Repositories ────────────────────────────────────────────────────

export interface Repository {
  id: number;
  owner: string;
  name: string;
  full_name: string;
  default_branch: string;
  is_private: boolean;
  index_status: string;
  indexed_at: string | null;
  chunk_count: number;
  symbol_count: number;
  file_count: number;
  graph_nodes: number;
  graph_edges: number;
  last_error: string | null;
  created_at: string | null;
}

export async function listRepositories(): Promise<Repository[]> {
  return apiRequest<Repository[]>('/api/repos');
}

export interface RepositoryCreateParams {
  repository: string;
  access_token?: string;
}

export async function connectRepository(params: RepositoryCreateParams): Promise<Repository> {
  return apiRequest<Repository>('/api/repos', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getRepository(repoId: number): Promise<Repository> {
  return apiRequest<Repository>(`/api/repos/${repoId}`);
}

export async function deleteRepository(repoId: number): Promise<void> {
  await apiRequest<void>(`/api/repos/${repoId}`, { method: 'DELETE' });
}

export async function triggerRepositoryIndex(repoId: number): Promise<Repository> {
  return apiRequest<Repository>(`/api/repos/${repoId}/index`, { method: 'POST' });
}

// ── SaaS: Reviews ────────────────────────────────────────────────────────

export interface ReviewFinding {
  id: number;
  source: string;
  agent: string | null;
  scanner: string | null;
  category: string;
  severity: string;
  file: string;
  line: number | null;
  file_line: string;
  title: string;
  description: string;
  rule: string;
  cwe: string;
  snippet: string;
  fix_code: string;
  tests: string[];
  confidence: number | null;
  corroborated: boolean;
}

export interface Review {
  id: number;
  user_id: number;
  repo_id: number | null;
  trigger: string;
  repository: string;
  title: string;
  pr_number: number | null;
  status: string;
  summary: string;
  counts: Record<string, number>;
  metrics: Record<string, any>;
  created_at: string | null;
  finished_at: string | null;
  findings: ReviewFinding[];
}

export interface ReviewCreateParams {
  diff: string;
  rules?: string;
  repository?: string;
  title?: string;
  repo_id?: number;
  depth?: 'standard' | 'deep';
}

export async function listReviews(params?: { limit?: number; offset?: number; repository?: string }): Promise<Review[]> {
  const query = new URLSearchParams();
  if (params?.limit) query.set('limit', params.limit.toString());
  if (params?.offset) query.set('offset', params.offset.toString());
  if (params?.repository) query.set('repository', params.repository);
  const qs = query.toString() ? `?${query.toString()}` : '';
  return apiRequest<Review[]>(`/api/reviews${qs}`);
}

export async function createReview(params: ReviewCreateParams): Promise<Review> {
  return apiRequest<Review>('/api/reviews', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getReview(reviewId: number): Promise<Review> {
  return apiRequest<Review>(`/api/reviews/${reviewId}`);
}

// ── SaaS: Jobs ────────────────────────────────────────────────────────────

export interface Job {
  id: number;
  type: string;
  status: string;
  payload: Record<string, any>;
  result: Record<string, any> | null;
  error: string | null;
  attempts: number;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export async function listJobs(limit: number = 50): Promise<Job[]> {
  return apiRequest<Job[]>(`/api/jobs?limit=${limit}`);
}

export async function getJob(jobId: number): Promise<Job> {
  return apiRequest<Job>(`/api/jobs/${jobId}`);
}

// ── SaaS: Metrics ────────────────────────────────────────────────────────

export interface MetricsSnapshot {
  counters: Record<string, number>;
  histograms: Record<string, { count: number; sum: number; min: number; max: number; buckets: Record<string, number> }>;
  usage: {
    total_reviews: number;
    total_findings: number;
    high_findings: number;
    estimated_cost_usd: number;
    avg_review_latency_seconds: number;
  };
}

export async function fetchMetricsSnapshot(): Promise<MetricsSnapshot> {
  return apiRequest<MetricsSnapshot>('/api/metrics/snapshot');
}

export async function fetchPrometheusMetrics(): Promise<string> {
  const res = await fetch(`${API_URL}/api/metrics`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return res.text();
}

// ── SaaS: Evaluations ────────────────────────────────────────────────────

export interface EvalRun {
  id: number;
  created_at: string | null;
  scores: Record<string, any>;
  details: Record<string, any>;
  notes: string;
}

export async function listEvals(limit: number = 20): Promise<EvalRun[]> {
  return apiRequest<EvalRun[]>(`/api/evals?limit=${limit}`);
}

export async function triggerEval(useLlm: boolean = true, notes: string = ''): Promise<EvalRun> {
  const query = new URLSearchParams();
  query.set('use_llm', useLlm.toString());
  if (notes) query.set('notes', notes);
  return apiRequest<EvalRun>(`/api/evals/run?${query.toString()}`, { method: 'POST' });
}