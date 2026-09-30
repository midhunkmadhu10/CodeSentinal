export interface Finding {
  severity: 'High' | 'Medium' | 'Low';
  file_line: string;
  risk: string;
  rule_violation: string;
  safer_code: string;
  source_chunk: string;
  // SaaS fields (optional for backward compatibility)
  source?: string;
  agent?: string | null;
  scanner?: string | null;
  category?: string;
  title?: string;
  description?: string;
  rule?: string;
  cwe?: string;
  snippet?: string;
  fix_code?: string;
  tests?: string[];
  confidence?: number | null;
  corroborated?: boolean;
}

export interface AnalyzeResponse {
  findings: Finding[];
  error: string | null;
  // Legacy fields
  screening_suggestions?: { priority: string; title: string; action: string }[];
}

export interface LoginResponse {
  token: string;
}

export interface DemoDiffResponse {
  diff: string;
}

export interface DemoRulesResponse {
  rules: string;
}

// ── SaaS Types ──────────────────────────────────────────────────────────────

export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
}

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
  database?: string;
  pgvector_enabled?: boolean;
  worker_running?: boolean;
  llm_configured?: boolean;
  routing?: {
    fast: { model: string; cost_per_1m_in: number; cost_per_1m_out: number };
    deep: { model: string; cost_per_1m_in: number; cost_per_1m_out: number };
    threshold: number;
  };
}

export interface EvalRun {
  id: number;
  created_at: string | null;
  scores: Record<string, any>;
  details: Record<string, any>;
  notes: string;
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