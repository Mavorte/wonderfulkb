// State of the current evaluation run (in KV) and its rows in the
// agent_functions tables, which the backoffice app polls.

import type { Region } from "./regions";
import { type DocumentType, RULE_IDS, type RuleId, type Status, type Verdict } from "./rules";

export const EVALUATIONS_TABLE = "agent_functions.case_evaluations";
export const RESULTS_TABLE = "agent_functions.case_evaluation_results";
const RUN_KEY = "case_eval_run";

type Row = { id: string; data: Record<string, any> };

export type RunContext = {
  kv: { get(key: string): any; set(key: string, value: unknown): void };
  tables: {
    insert(table: string, data: Record<string, unknown>): Promise<{ id: string }>;
    update(table: string, id: string, data: Record<string, unknown>): Promise<unknown>;
    filter(table: string, filters: Array<{ column: string; operator: string; value?: unknown }>, limit?: number, offset?: number): Promise<{ rows: Row[] }>;
  };
};

// ref: the short name the agent uses for the document (D1, D2, ...), so its
// tool calls don't repeat 36-character IDs.
export type RunDocument = { document_id: string; ref?: string; title: string; label: string };

export type Client = {
  name: string;
  ico: string;
  dic?: string;
  address?: string;
  status: string;
  // The live client API has no authorized flag; a signatory without one counts as authorized.
  signatories?: Array<{ name: string; function?: string; authorized?: boolean }>;
  kyc?: { status: string; checked_at?: string };
};

// What the case record says about the loan, for the consistency rules to compare against.
export type CaseMetadata = { loan_number?: string; asset?: string; serial_number?: string };

export type Run = {
  evaluation_id: string;
  // Row id returned by insert; equals evaluation_id on real tables, not in eval fixtures.
  row_id: string;
  case_id: string;
  is_mock: boolean;
  client: Client | null;
  case_metadata: CaseMetadata;
  documents: RunDocument[];
};

// Where to look for a source's region: the value it shows, and the region
// labels, parties or required document types that fit it. See lib/regions.ts.
export type Locate = { value?: string; labels?: string[]; parties?: string[]; refers_to?: string[] };

// A place in a document that a result rests on. The region fields follow the
// evidence contract of wonderfulkb be-validator-agent/docs/regiony-dokumentu-navrh.md;
// they are filled in from the document's regions when the result is recorded,
// never by the agent.
export type Source = {
  document_id: string;
  title: string;
  page?: number;
  region_id?: string;
  // [x0, y0, x1, y1], 0-1 of the page, origin top left; narrowed to the value's lines when it can be.
  bbox?: number[];
  // The document's own text at that place.
  quote?: string;
  // evidence, compare_a / compare_b / ... (the sides of a conflict), declaration
  // (where a document requires something), missing_value (where something should be).
  role?: string;
  // The field or attribute whose value is at this place, as the rule's tool names
  // it, e.g. creditor (a *_contents field), ico (a consistency attribute), signatory.
  field?: string;
  // The issue this place shows, e.g. "IČO" or "faktura (daňový doklad)".
  issue?: string;
  // region (the value is in the region), lines (narrowed to its lines), page_only (no region found).
  anchor?: "region" | "lines" | "page_only";
  // Lookup hint for anchorSources; never saved.
  locate?: Locate;
};

export type RuleResult = {
  rule_id: RuleId;
  status: Status;
  expected: string;
  found: string;
  sources: Source[];
  details?: unknown;
  reasoning: string;
};

export function getRun(ctx: RunContext): Run | null {
  return getKey<Run>(ctx, RUN_KEY);
}

// Starts with the case ID, so a run's rows can be told apart by case.
function newEvaluationId(caseId: string): string {
  const random = Math.random().toString(36).slice(2, 6);
  return `ev-${caseId}-${Date.now().toString(36)}-${random}`;
}

export async function startRun(ctx: RunContext, run: Omit<Run, "evaluation_id" | "row_id">): Promise<Run> {
  const evaluationId = newEvaluationId(run.case_id);
  const row = await ctx.tables.insert(EVALUATIONS_TABLE, {
    evaluation_id: evaluationId,
    case_id: run.case_id,
    status: "running",
    rules_total: RULE_IDS.length,
    is_mock: run.is_mock,
    started_at: new Date().toISOString(),
  });
  const started: Run = { evaluation_id: evaluationId, row_id: row.id, ...run };
  ctx.kv.set(RUN_KEY, started);
  return started;
}

// By document_id or by ref (D1, D2, ...).
export function findDocument(run: Run, documentId: string | undefined): RunDocument | undefined {
  const id = documentId?.trim();
  if (!id) return undefined;
  return run.documents.find((d) => d.document_id === id) ?? run.documents.find((d) => d.ref?.toUpperCase() === id.toUpperCase());
}

// The document_id behind a ref, or the input as given when no document has it.
export function resolveDocumentId(run: Run, documentId: string): string {
  return findDocument(run, documentId)?.document_id ?? documentId.trim();
}

// What get_document saw in a document, for the *_contents rules to check the
// agent's input against. Kept under its own key per document, so parallel
// get_document calls don't overwrite each other.
export type DocumentRead = {
  page_count: number;
  // Pages with no text: blank, unless also in pages_failed.
  empty_pages: number[];
  pages_failed: number[];
  confidence: number | null;
  // null when the signatures could not be loaded.
  signatures: Array<{ role: string; page: number }> | null;
};

// Which document provides each typed requirement, as last recorded by
// required_documents_present.
export type TypedRequirement = { type: DocumentType; document_id: string | null };

const readKey = (run: Run, documentId: string) => `case_eval_read:${run.evaluation_id}:${documentId}`;
const requirementsKey = (run: Run) => `case_eval_requirements:${run.evaluation_id}`;
const regionsKey = (run: Run, documentId: string) => `case_eval_regions:${run.evaluation_id}:${documentId}`;

function getKey<T>(ctx: RunContext, key: string): T | null {
  try {
    return (ctx.kv.get(key) as T | null) ?? null;
  } catch {
    // kv.get throws for a missing key.
    return null;
  }
}

export function saveDocumentRead(ctx: RunContext, run: Run, documentId: string, read: DocumentRead): void {
  ctx.kv.set(readKey(run, documentId), read);
}

export function getDocumentRead(ctx: RunContext, run: Run, documentId: string | undefined): DocumentRead | null {
  return documentId ? getKey<DocumentRead>(ctx, readKey(run, resolveDocumentId(run, documentId))) : null;
}

// A document's regions, loaded by get_document, for anchoring sources. If a
// large document's regions don't fit in KV, they are kept without their lines,
// and failing that not at all; its sources then fall back to the page.
export function saveDocumentRegions(ctx: RunContext, run: Run, documentId: string, regions: Region[]): void {
  try {
    ctx.kv.set(regionsKey(run, documentId), regions);
  } catch {
    try {
      ctx.kv.set(regionsKey(run, documentId), regions.map((r) => ({ ...r, lines: [] })));
    } catch (error) {
      console.log(`regions of ${documentId} not cached: ${error}`);
    }
  }
}

export function getDocumentRegions(ctx: RunContext, run: Run, documentId: string): Region[] | null {
  return getKey<Region[]>(ctx, regionsKey(run, documentId));
}

export function saveRequirements(ctx: RunContext, run: Run, requirements: TypedRequirement[]): void {
  ctx.kv.set(requirementsKey(run), requirements);
}

export function getRequirements(ctx: RunContext, run: Run): TypedRequirement[] | null {
  return getKey<TypedRequirement[]>(ctx, requirementsKey(run));
}

// One row per rule per run; recording a rule again replaces its row.
export async function saveResult(ctx: RunContext, run: Run, result: RuleResult): Promise<void> {
  const data = {
    evaluation_id: run.evaluation_id,
    rule_id: result.rule_id,
    case_id: run.case_id,
    status: result.status,
    expected: result.expected,
    found: result.found,
    sources: JSON.stringify(result.sources.map(({ locate: _, ...source }) => source)),
    details: result.details === undefined ? null : JSON.stringify(result.details),
    reasoning: result.reasoning,
    recorded_at: new Date().toISOString(),
  };
  const { rows } = await ctx.tables.filter(RESULTS_TABLE, [
    { column: "evaluation_id", operator: "eq", value: run.evaluation_id },
    { column: "rule_id", operator: "eq", value: result.rule_id },
  ], 1, 0);
  if (rows[0]) await ctx.tables.update(RESULTS_TABLE, rows[0].id, data);
  else await ctx.tables.insert(RESULTS_TABLE, data);
}

export async function getStatuses(ctx: RunContext, run: Run): Promise<Partial<Record<RuleId, string>>> {
  const { rows } = await ctx.tables.filter(RESULTS_TABLE, [
    { column: "evaluation_id", operator: "eq", value: run.evaluation_id },
  ], 100, 0);
  return Object.fromEntries(rows.map((r) => [r.data.rule_id, r.data.status]));
}

export async function finishRun(ctx: RunContext, run: Run, status: "completed" | "failed", summary: string, verdict?: Verdict): Promise<void> {
  await ctx.tables.update(EVALUATIONS_TABLE, run.row_id, {
    status,
    verdict: verdict ?? null,
    summary,
    finished_at: new Date().toISOString(),
  });
}
