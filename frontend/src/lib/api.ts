const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('codesentinal_token');
  }
  return null;
}

async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with status ${res.status}`);
  }

  return res.json();
}

export async function login(username: string, password: string): Promise<string> {
  const data = await apiRequest<{ token: string }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  return data.token;
}

export async function fetchDemoDiff(): Promise<string> {
  const data = await apiRequest<{ diff: string }>('/api/demo/diff');
  return data.diff;
}

export async function fetchDemoRules(): Promise<string> {
  const data = await apiRequest<{ rules: string }>('/api/demo/rules');
  return data.rules;
}

export interface AnalyzeParams {
  diff: string;
  rules: string;
  llm_endpoint?: string;
  llm_model?: string;
  llm_api_key?: string;
}

export async function analyze(params: AnalyzeParams) {
  return apiRequest<{
    findings: { severity: string; file_line: string; risk: string; rule_violation: string; safer_code: string; source_chunk: string }[];
    screening_suggestions: { priority: string; title: string; action: string }[];
    error: string | null;
  }>('/api/analyze', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function fetchHealth(): Promise<{ status: string; service: string }> {
  return apiRequest('/api/health');
}

export async function fetchSettingsStatus(): Promise<{
  backend_api_key_configured: boolean;
  llm_endpoint: string;
  llm_model: string;
}> {
  return apiRequest('/api/settings/status');
}

export async function importGitHubRepository(params: { repository: string; pull_number?: number; access_token?: string }) {
  return apiRequest<{
    repository: string;
    diff: string;
    policy: string | null;
    policy_path: string | null;
    error: string | null;
  }>('/api/github/import', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}
