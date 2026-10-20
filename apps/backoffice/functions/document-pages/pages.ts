/** Body of GET /cases/{case_id}/documents/{document_id}/pages (be-document-processing/contracts/openapi-validator-agent.yaml). */
export type UpstreamDocumentPages = {
  document_id: string;
  page_count: number;
  redacted: boolean;
  preview_pdf_url: string | null;
  pages: { page: number; preview_url: string | null }[];
  original_available: boolean;
};

/**
 * One document as the case detail shows it. `pages[i]` is page i + 1; a page
 * without a masked preview is null. `processing`, `not_found` and `error` carry no pages.
 */
export type DocumentPreview =
  | {
      documentId: string;
      status: "ready";
      redacted: boolean;
      pdfUrl: string | null;
      pages: (string | null)[];
      originalAvailable: boolean;
    }
  | { documentId: string; status: "processing" | "not_found" | "error" };

export const MAX_DOCUMENTS = 40;
// Same shape the API accepts for case_id; document ids are UUIDs but stay opaque here.
const ID_PATTERN = /^[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}$/;

/** The request's case id and unique document ids, or null when any of them is malformed. */
export function parseRequest(data: unknown): { caseId: string; documentIds: string[] } | null {
  const body = (data ?? {}) as { case_id?: unknown; document_ids?: unknown };
  const caseId = String(body.case_id ?? "").trim();
  if (!ID_PATTERN.test(caseId) || !Array.isArray(body.document_ids)) return null;
  const documentIds = [...new Set(body.document_ids.map((id) => String(id).trim()))];
  if (documentIds.length > MAX_DOCUMENTS || !documentIds.every((id) => ID_PATTERN.test(id))) return null;
  return { caseId, documentIds };
}

export function toDocumentPreview(documentId: string, body: UpstreamDocumentPages): DocumentPreview {
  const byNumber = new Map(body.pages.map((p) => [p.page, p.preview_url]));
  const count = Math.max(body.page_count, ...body.pages.map((p) => p.page), 0);
  return {
    documentId,
    status: "ready",
    redacted: body.redacted,
    pdfUrl: body.preview_pdf_url,
    pages: Array.from({ length: count }, (_, i) => byNumber.get(i + 1) ?? null),
    originalAvailable: body.original_available,
  };
}
