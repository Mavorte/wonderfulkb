// What every explorer Function returns: the upstream call and its answer, unchanged.
export type UpstreamResult<T = unknown> = {
  url: string;
  status: number;
  ok: boolean;
  body: T | null;
  secret?: string;
  error?: string;
};

// openapi-case-client.yaml `Client`.
export type Client = {
  client_id: string;
  ico: string;
  dic?: string;
  name: string;
  legal_form?: string;
  address?: string;
  status: string;
  contacts?: Array<{ name?: string; role?: string; email?: string; phone?: string }>;
  signatories?: Array<{ name?: string; function?: string; authorized?: boolean }>;
  kyc?: { status?: string; checked_at?: string };
};

// openapi-case-client.yaml `Case`.
export type Case = {
  case_id: string;
  client_id: string;
  status: string;
  created_at: string;
  metadata?: Record<string, unknown>;
};

// documents API `listCaseDocuments` item.
export type DocumentSummary = {
  document_id: string;
  title: string;
  label?: string;
  label_status?: string;
  processing_status?: string;
  page_count?: number;
};

export type DocumentView = "validation" | "vectors" | "signatures";

// Argument of a ui-base `Table` column `cell` renderer (TanStack's CellContext, narrowed to what we use).
export type CellProps<T> = { row: { original: T } };

// agent_functions.case_evaluations row (repos/agent-functions/tables).
export type Evaluation = {
  evaluation_id: string;
  case_id: string;
  status: string;
  verdict?: string | null;
  summary?: string | null;
  rules_total?: number | null;
  is_mock?: boolean | null;
  started_at?: string | null;
  finished_at?: string | null;
};

// agent_functions.case_evaluation_results row; sources and details are JSON strings.
export type EvaluationResult = {
  evaluation_id: string;
  rule_id: string;
  case_id: string;
  status: string;
  expected?: string | null;
  found?: string | null;
  sources?: string | null;
  details?: string | null;
  reasoning: string;
  recorded_at?: string | null;
};
