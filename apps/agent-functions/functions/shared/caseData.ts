// Handlers behind the eval-case-get, eval-documents-list, eval-document-get,
// eval-document-signatures, eval-document-regions and case-status-set functions. They take a minimal context so tests can pass a fake one.

import { type AwsApi, type UpstreamCase, type UpstreamClient, type UpstreamDocument, type UpstreamRegion, type UpstreamSignature, getAwsApi } from "./aws.ts";
import { type GlobalsContext, getErrorMessage } from "./config.ts";

export type HandlerContext = GlobalsContext & {
  data?: Record<string, unknown>;
  response: { setStatus(status: number): void };
};

type ErrorCode = "missing_parameter" | "invalid_status" | "case_not_found" | "document_not_found" | "upstream";
export type ErrorResult = { error: ErrorCode; message?: string };

// Client fields the agent compares against the documents.
export type EvalClient = Pick<UpstreamClient, "client_id" | "name" | "ico" | "dic" | "legal_form" | "address" | "status" | "signatories" | "kyc">;

export type EvalCase = { case_id: string; is_mock: boolean; case: UpstreamCase; client: EvalClient | null };

export type EvalDocumentSummary = { document_id: string; title: string; label: string; processing_status: string; page_count: number };

export type EvalDocument = EvalDocumentSummary & {
  case_id: string;
  is_mock: boolean;
  confidence: number | null;
  pages_failed: number[];
  // Page texts, 1-based page numbers, so findings can cite a page.
  pages: Array<{ page: number; text: string }>;
};

// A detected signature: who it is for, on which page, and the text it was matched by.
export type EvalSignature = { page: number; role: string; evidence: string; copy_suspicion: string };

export type EvalSignatures = { case_id: string; document_id: string; is_mock: boolean; signatures: EvalSignature[] };

// A labelled paragraph or table row with its position, so a finding can point
// at the exact place in the document. `lines` is kept only when the region has
// more than one line: a single line adds nothing to `bbox`.
export type EvalRegion = {
  region_id: string;
  page: number;
  label: string | null;
  party: string | null;
  refers_to: string[];
  text: string;
  bbox: number[] | null;
  lines?: Array<{ bbox: number[]; start: number; end: number }>;
};

// `regions` is empty unless `status` is completed. not_run, failed and
// not_ready (still ingesting) say nothing about the document's content.
export type EvalRegions = { case_id: string; document_id: string; is_mock: boolean; status: string; regions: EvalRegion[] };

// The seven case statuses of wonderfulkb architecture/case-statuses.md, in lifecycle order.
export const CASE_STATUSES = [
  "open",
  "intake_in_progress",
  "evaluating",
  "awaiting_decision",
  "awaiting_clarification",
  "approved",
  "completed",
] as const;

export type SetCaseStatusResult = { case_id: string; is_mock: boolean; case: UpstreamCase };

function getParam(context: HandlerContext, name: string): string {
  return String(context.data?.[name] ?? "").trim();
}

function fail(context: HandlerContext, status: number, error: ErrorCode, message?: string): ErrorResult {
  context.response.setStatus(status);
  return message ? { error, message } : { error };
}

function failUpstream(context: HandlerContext, what: string, status: number): ErrorResult {
  console.log(`${what} returned ${status}`);
  return fail(context, 502, "upstream", `${what} returned ${status}`);
}

export function toEvalClient(client: UpstreamClient): EvalClient {
  const { client_id, name, ico, dic, legal_form, address, status, signatories, kyc } = client;
  return { client_id, name, ico, dic, legal_form, address, status, signatories, kyc };
}

export function toEvalDocument(document: UpstreamDocument, caseId: string, isMock: boolean): EvalDocument {
  const { document_id, title, label, processing_status, page_count } = document;
  return {
    case_id: caseId,
    is_mock: isMock,
    document_id, title, label, processing_status, page_count,
    confidence: document.confidence ?? null,
    pages_failed: document.pages_failed ?? [],
    pages: (document.text ?? "").split("\f").map((text, index) => ({ page: index + 1, text: text.trim() })),
  };
}

export function toEvalSignature(signature: UpstreamSignature): EvalSignature {
  return {
    page: signature.page,
    role: signature.role,
    evidence: signature.role_evidence ?? "",
    copy_suspicion: signature.copy_suspicion?.level ?? "none",
  };
}

export function toEvalRegion(region: UpstreamRegion): EvalRegion {
  const lines = region.lines ?? [];
  return {
    region_id: region.region_id,
    page: region.page,
    label: region.label ?? null,
    party: region.party ?? null,
    refers_to: region.refers_to ?? [],
    text: region.text ?? "",
    bbox: region.bbox ?? null,
    ...(lines.length > 1 && { lines }),
  };
}

// GET /clients/{client_id} is not deployed, so page through the client list.
async function findClient(api: AwsApi, clientId: string): Promise<UpstreamClient | null> {
  let nextToken: string | null | undefined;
  do {
    const list = await api.listClients(nextToken);
    if (list.status !== 200 || !list.body) return null;
    const client = list.body.clients.find((c) => c.client_id === clientId);
    if (client) return client;
    nextToken = list.body.next_token;
  } while (nextToken);
  return null;
}

export async function getCase(context: HandlerContext): Promise<EvalCase | ErrorResult> {
  const caseId = getParam(context, "case_id");
  if (!caseId) return fail(context, 400, "missing_parameter", "case_id is required");
  const api = getAwsApi(context, caseId);
  try {
    const caseResponse = await api.getCase(caseId);
    if (caseResponse.status === 404) return fail(context, 404, "case_not_found");
    if (caseResponse.status !== 200 || !caseResponse.body) return failUpstream(context, "case API", caseResponse.status);
    const client = await findClient(api, caseResponse.body.client_id);
    return { case_id: caseId, is_mock: api.isMock, case: caseResponse.body, client: client && toEvalClient(client) };
  } catch (error) {
    console.log(`case API request failed: ${getErrorMessage(error)}`);
    return fail(context, 502, "upstream", getErrorMessage(error));
  }
}

export async function listDocuments(context: HandlerContext): Promise<{ case_id: string; is_mock: boolean; documents: EvalDocumentSummary[] } | ErrorResult> {
  const caseId = getParam(context, "case_id");
  if (!caseId) return fail(context, 400, "missing_parameter", "case_id is required");
  const api = getAwsApi(context, caseId);
  try {
    const documents: EvalDocumentSummary[] = [];
    let nextToken: string | null | undefined;
    do {
      const page = await api.listDocuments(caseId, nextToken);
      if (page.status === 404) return fail(context, 404, "case_not_found");
      if (page.status !== 200 || !page.body) return failUpstream(context, "documents API", page.status);
      for (const { document_id, title, label, processing_status, page_count } of page.body.documents) {
        documents.push({ document_id, title, label, processing_status, page_count });
      }
      nextToken = page.body.next_token;
    } while (nextToken);
    return { case_id: caseId, is_mock: api.isMock, documents };
  } catch (error) {
    console.log(`documents API request failed: ${getErrorMessage(error)}`);
    return fail(context, 502, "upstream", getErrorMessage(error));
  }
}

export async function getDocument(context: HandlerContext): Promise<EvalDocument | ErrorResult> {
  const caseId = getParam(context, "case_id");
  const documentId = getParam(context, "document_id");
  if (!caseId || !documentId) return fail(context, 400, "missing_parameter", "case_id and document_id are required");
  const api = getAwsApi(context, caseId);
  try {
    const response = await api.getDocument(caseId, documentId);
    if (response.status === 404) return fail(context, 404, "document_not_found");
    if (response.status !== 200 || !response.body) return failUpstream(context, "documents API", response.status);
    return toEvalDocument(response.body, caseId, api.isMock);
  } catch (error) {
    console.log(`documents API request failed: ${getErrorMessage(error)}`);
    return fail(context, 502, "upstream", getErrorMessage(error));
  }
}

export async function getSignatures(context: HandlerContext): Promise<EvalSignatures | ErrorResult> {
  const caseId = getParam(context, "case_id");
  const documentId = getParam(context, "document_id");
  if (!caseId || !documentId) return fail(context, 400, "missing_parameter", "case_id and document_id are required");
  const api = getAwsApi(context, caseId);
  try {
    const response = await api.getSignatures(caseId, documentId);
    if (response.status === 404) return fail(context, 404, "document_not_found");
    if (response.status !== 200 || !response.body) return failUpstream(context, "documents API signatures", response.status);
    return { case_id: caseId, document_id: documentId, is_mock: api.isMock, signatures: (response.body.signatures ?? []).map(toEvalSignature) };
  } catch (error) {
    console.log(`documents API signatures request failed: ${getErrorMessage(error)}`);
    return fail(context, 502, "upstream", getErrorMessage(error));
  }
}

export async function getRegions(context: HandlerContext): Promise<EvalRegions | ErrorResult> {
  const caseId = getParam(context, "case_id");
  const documentId = getParam(context, "document_id");
  if (!caseId || !documentId) return fail(context, 400, "missing_parameter", "case_id and document_id are required");
  const api = getAwsApi(context, caseId);
  const empty = (status: string): EvalRegions => ({ case_id: caseId, document_id: documentId, is_mock: api.isMock, status, regions: [] });
  try {
    const response = await api.getRegions(caseId, documentId);
    if (response.status === 404) return fail(context, 404, "document_not_found");
    // 409: the document is still being ingested.
    if (response.status === 409) return empty("not_ready");
    if (response.status !== 200 || !response.body) return failUpstream(context, "documents API regions", response.status);
    const status = response.body.status ?? "not_run";
    if (status !== "completed") return empty(status);
    return { ...empty(status), regions: (response.body.regions ?? []).map(toEvalRegion) };
  } catch (error) {
    console.log(`documents API regions request failed: ${getErrorMessage(error)}`);
    return fail(context, 502, "upstream", getErrorMessage(error));
  }
}

// The AWS API does not check transitions: any status can be set from any other.
export async function setCaseStatus(context: HandlerContext): Promise<SetCaseStatusResult | ErrorResult> {
  const caseId = getParam(context, "case_id");
  const status = getParam(context, "status");
  if (!caseId || !status) return fail(context, 400, "missing_parameter", "case_id and status are required");
  if (!(CASE_STATUSES as readonly string[]).includes(status)) {
    return fail(context, 400, "invalid_status", `status must be one of: ${CASE_STATUSES.join(", ")}`);
  }
  const api = getAwsApi(context, caseId);
  try {
    const response = await api.setCaseStatus(caseId, status);
    if (response.status === 404) return fail(context, 404, "case_not_found");
    if (response.status !== 200 || !response.body) return failUpstream(context, "case API status", response.status);
    return { case_id: caseId, is_mock: api.isMock, case: response.body };
  } catch (error) {
    console.log(`case API status request failed: ${getErrorMessage(error)}`);
    return fail(context, 502, "upstream", getErrorMessage(error));
  }
}
