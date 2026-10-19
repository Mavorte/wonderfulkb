import type { UploadedDocument } from "../../app/src/types";

// Ingest also returns internal fields for trusted callers (e.g. `also_in`, the
// IDs of OTHER cases holding the same file). The anonymous client must only see
// its own documents, so the response is rebuilt from a whitelist.
export function toClientDocuments(raw: unknown): UploadedDocument[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((doc) => ({
    document_id: String(doc?.document_id ?? ""),
    filename: String(doc?.filename ?? ""),
    received_at: String(doc?.received_at ?? ""),
    content_type: String(doc?.content_type ?? ""),
    size_bytes: Number(doc?.size_bytes ?? 0),
  }));
}
