// State and helpers shared by the intake tools. The conversation's progress
// (the accepted loan agreement, the documents it requires and which upload
// covers each one) lives in KV, so each tool picks up where the last one left off.

export type RequiredDocument = {
  key: string;
  name: string;
  // Uploads accepted for this requirement; empty while it is outstanding.
  attachment_ids: string[];
};

export type CheckedFile = {
  name: string;
  outcome: "loan_agreement" | "accepted" | "rejected";
  document_kind: string;
  requirement?: string;
};

export type IntakeState = {
  loan_agreement?: { attachment_id: string; name: string; contract_number: string | null };
  required_documents: RequiredDocument[];
  required_documents_source?: "agreement" | "default";
  checked: Record<string, CheckedFile>;
  submitted?: { case_id: string; document_count: number };
};

export type FileInfo = { id: string; name: string; mimeType: string; size: number };

type KvContext = {
  kv: { get(key: string): any; set(key: string, value: any): any; exists(key: string): boolean };
};

const STATE_KEY = "intake";

// Used when the loan agreement has no list of documents to submit before disbursement.
export const DEFAULT_REQUIRED_DOCUMENTS = [
  "Daňový doklad (faktura) od dodavatele",
  "Kupní smlouva nebo objednávka potvrzená dodavatelem",
  "Předávací protokol podepsaný dodavatelem i vámi",
  "Doklad o zaplacení (např. výpis z účtu)",
];

export function getState(ctx: KvContext): IntakeState {
  return ctx.kv.exists(STATE_KEY) ? (ctx.kv.get(STATE_KEY) as IntakeState) : { required_documents: [], checked: {} };
}

export function saveState(ctx: KvContext, state: IntakeState) {
  ctx.kv.set(STATE_KEY, state);
}

export function toRequiredDocuments(names: string[]): RequiredDocument[] {
  const unique = [...new Set(names.map((name) => name.trim()).filter(Boolean))];
  return unique.map((name, index) => ({ key: `doc_${index + 1}`, name, attachment_ids: [] }));
}

export function getOutstanding(state: IntakeState): string[] {
  return state.required_documents.filter((doc) => doc.attachment_ids.length === 0).map((doc) => doc.name);
}

// Files uploaded to the conversation that no tool has checked yet, oldest first.
export function getNewFiles(state: IntakeState, files: FileInfo[]): FileInfo[] {
  return files.filter((file) => !state.checked[file.id]);
}

// Ingest takes PDFs only, the same as the Client Intake app.
export function isPdf(file: FileInfo): boolean {
  return file.mimeType === "application/pdf" || /\.pdf$/i.test(file.name);
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}
