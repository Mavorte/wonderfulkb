// Shared by the intake functions: resolves an intake link hash to its case and
// reads the tenant configuration for the AWS services.

import type { FunctionContext } from "@wonderful/types";

const LINKS_TABLE = "client_intake.intake_links";

// Secret name (type "API Key", header x-api-key), shared by the case/client API and ingest.
export const INGEST_SECRET = "kb-aws-ingest-api-key";

export async function getCaseIdForHash(context: FunctionContext, hash: string): Promise<string | null> {
  const { rows } = await context.tables.filter(
    LINKS_TABLE,
    [{ column: "hash", operator: "eq", value: hash }],
    1,
    0,
  );
  const caseId: unknown = rows[0]?.data?.case_id;
  return typeof caseId === "string" && caseId ? caseId : null;
}

// Missing globals throw at runtime instead of returning null.
export function getGlobalUrl(context: FunctionContext, name: string): string {
  try {
    return String(context.globals.get(name) ?? "").replace(/\/+$/, "");
  } catch {
    return "";
  }
}

// Storage folder for a case's uploads; intake-submit only accepts keys inside it.
export function getUploadPrefix(caseId: string): string {
  return `client-intake/${caseId}/`;
}

// Random hex id from `crypto.getRandomValues`, which the function runtime provides.
export function getRandomId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
