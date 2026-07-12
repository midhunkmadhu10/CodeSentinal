export interface Finding {
  severity: 'High' | 'Medium' | 'Low';
  file_line: string;
  risk: string;
  rule_violation: string;
  safer_code: string;
  source_chunk: string;
}

export interface AnalyzeResponse {
  findings: Finding[];
  error: string | null;
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