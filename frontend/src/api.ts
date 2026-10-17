export type Ticket = {
  id: string;
  source_key: string;
  source: string;
  summary: string;
  description: string;
  comments: string;
  status: string;
  priority: string;
  assignee: string;
  component: string;
  source_url: string;
  analyzed?: boolean;
};

export type DocumentLink = {
  title: string;
  url: string;
  snippet: string;
  source: string;
};

export type Analysis = {
  quick_summary: string;
  problem_statement: string;
  expected_outcome: string;
  actual_vs_expected: string;
  impact: string;
  category: string;
  affected_product: string;
  error_evidence: string[];
  actions_attempted: string[];
  missing_information: string[];
  confirmed_facts: string[];
  inferences: string[];
  recommended_next_steps: string[];
  analysis_method: string;
};

export type AnalysisBundle = {
  analysis: Analysis;
  documents: DocumentLink[];
  documents_error: string;
  analyzed_at: string;
};

export type AppConfig = {
  api_key_required: boolean;
  jira_configured: boolean;
  hpe_search_configured: boolean;
  mode: "jira" | "demo";
  last_sync_at: string;
  sync_interval_minutes: number;
};

export type SyncRun = {
  id: number;
  started_at: string;
  finished_at: string;
  status: "running" | "succeeded" | "failed";
  synced_count: number;
  error: string;
};

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const key = sessionStorage.getItem("request-lens-api-key");
  if (key) headers.set("X-API-Key", key);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(path, { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload as T;
}