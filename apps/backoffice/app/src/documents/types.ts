export type Evidence = { page_number: number; block_id: string; quote: string; bbox: number[] | null };
export type DocumentRecord = {
  document_id: string; filename: string;
  processing_status: "awaiting_upload" | "queued" | "processing" | "completed" | "partial" | "failed";
  document_type?: string | null; page_count?: number | null; error?: string | null;
  errors?: { code: string; page_number: number | null }[];
};
export type ExtractedField = {
  field_id: string; key: string; role: string | null; raw_value: string | null;
  normalized_value: string | null; currency?: string | null; status: string; evidence: Evidence[];
};
export type DocumentResult = {
  document_id: string; run_id: string; page_count: number; processing_status: string;
  extraction: { document_type: string; fields: ExtractedField[]; warnings: string[] };
  ocr: { pages: { page_number: number; text: string; method: "native" | "vision"; model: string | null; warnings: string[]; status: string }[] };
  errors: { code: string; page_number: number | null }[];
  corrections: { correction_id: string; field_id: string; previous_value: string | null; normalized_value: string | null; reason: string; created_at: string }[];
};
export type CaseValidation = {
  status: string; completeness_profile: string;
  findings: { code: string; message: string; severity: string; sources: { document_id?: string; evidence?: Evidence[] }[] }[];
};
