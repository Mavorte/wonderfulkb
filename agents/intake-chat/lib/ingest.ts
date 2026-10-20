// Sends the accepted uploads to the AWS ingest service, the same way the Client
// Intake app's intake-submit Function does: one multipart POST of PDFs to
// `{kb_aws_ingest_url}/cases/{case_id}/documents` with the ingest key.
//
// The case comes from the intake link: the chat page passes the link's `h`
// value as the session metadata `intake_hash`, and the Client Intake app's
// intake-get Function resolves it to the case.

import { getErrorMessage } from "./intake";

// Secret name (type "API Key", header x-api-key), shared with the Client Intake app.
const INGEST_SECRET = "kb-aws-ingest-api-key";
const TIMEOUT_MS = 110_000;

export type UploadedDocument = {
  document_id: string;
  filename: string;
  received_at: string;
  content_type: string;
  size_bytes: number;
};

export type IntakeCase = { case_id: string; client_email: string | null };

type IngestContext = {
  metadata: { communication: { metadata: Record<string, any> } };
  globals: { get(name: string): any };
  functions: { run(options: { slug: string; params?: Record<string, unknown> }): { result: Record<string, any> } };
};

export type IngestError = { error: string; message: string };

export function getIntakeHash(ctx: IngestContext): string {
  return String(ctx.metadata.communication.metadata?.intake_hash ?? "").trim();
}

export function resolveCase(ctx: IngestContext): IntakeCase | IngestError {
  const hash = getIntakeHash(ctx);
  if (!hash) {
    return { error: "no_intake_link", message: "This conversation was not opened from an intake link, so it has no case." };
  }
  let result: Record<string, any>;
  try {
    result = ctx.functions.run({ slug: "client-intake/intake-get", params: { hash } }).result;
  } catch (error) {
    return { error: "case_lookup_failed", message: getErrorMessage(error) };
  }
  if (result?.error || !result?.case_id) {
    return { error: "case_lookup_failed", message: String(result?.error ?? "no case for this link") };
  }
  return { case_id: String(result.case_id), client_email: result.client?.email ?? null };
}

function concat(parts: Uint8Array[]): Uint8Array<ArrayBuffer> {
  const out = new Uint8Array(parts.reduce((sum, p) => sum + p.length, 0));
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export function buildMultipart(boundary: string, files: Array<{ name: string; data: Uint8Array }>, uploadedBy: string) {
  const encoder = new TextEncoder();
  const parts: Uint8Array[] = [];
  const quote = (value: string) => value.replace(/["\r\n\\]/g, "_");
  for (const file of files) {
    parts.push(
      encoder.encode(
        `--${boundary}\r\nContent-Disposition: form-data; name="files"; filename="${quote(file.name)}"\r\n` +
          "Content-Type: application/pdf\r\n\r\n",
      ),
      file.data,
      encoder.encode("\r\n"),
    );
  }
  if (uploadedBy) {
    parts.push(
      encoder.encode(`--${boundary}\r\nContent-Disposition: form-data; name="uploaded_by"\r\n\r\n${uploadedBy}\r\n`),
    );
  }
  parts.push(encoder.encode(`--${boundary}--\r\n`));
  return concat(parts);
}

function getIngestUrl(ctx: IngestContext): string {
  try {
    return String(ctx.globals.get("kb_aws_ingest_url") ?? "").replace(/\/+$/, "");
  } catch {
    return "";
  }
}

function getBoundary(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return `----kb-intake-chat-${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

export async function sendToIngest(
  ctx: IngestContext,
  intakeCase: IntakeCase,
  files: Array<{ name: string; data: Uint8Array }>,
): Promise<{ documents: UploadedDocument[] } | IngestError> {
  const ingestUrl = getIngestUrl(ctx);
  if (!ingestUrl) return { error: "not_configured", message: "The global kb_aws_ingest_url is not set." };

  const boundary = getBoundary();
  const response = await fetch(`${ingestUrl}/cases/${encodeURIComponent(intakeCase.case_id)}/documents`, {
    method: "POST",
    headers: { "content-type": `multipart/form-data; boundary=${boundary}`, accept: "application/json" },
    body: buildMultipart(boundary, files, intakeCase.client_email ?? ""),
    secretName: INGEST_SECRET,
    timeoutMs: TIMEOUT_MS,
  });
  const text = await response.text();
  let body: { documents?: UploadedDocument[]; error?: string } | null = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!response.ok) {
    return { error: "ingest_rejected", message: `ingest returned ${response.status}: ${body?.error ?? text.slice(0, 200)}` };
  }
  return { documents: body?.documents ?? [] };
}
