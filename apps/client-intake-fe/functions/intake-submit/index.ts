// Sends the client's PDFs to the AWS ingest service (POST /cases/{case_id}/documents).
//
// The browser cannot call ingest itself: its API key must stay server-side and
// the service has no CORS. So the browser first uploads each file to Custom
// Storage under `client-intake/<case_id>/`, then calls this function with the
// link hash, the storage keys and the original file names. The function
// downloads the files, posts them in one multipart request with the ingest key
// (secret `kb-aws-ingest-api-key`), and deletes them from storage once ingest
// has accepted them.

import type { FunctionContext } from "@wonderful/types";
import type { UploadedDocument } from "../../app/src/types";
import { toClientDocuments } from "../shared/ingestDocuments";
import { getCaseIdForHash, getErrorMessage, getGlobalUrl, getRandomId, getUploadPrefix, INGEST_SECRET } from "../shared/intakeLinks";

const MAX_FILES = 20;
const TIMEOUT_MS = 110_000;

type SubmitResult = { documents: UploadedDocument[] };

type SubmitError = {
  error: "missing_hash" | "invalid_link" | "invalid_files" | "not_configured" | "rejected" | "upstream";
  message?: string;
};

function concat(parts: Uint8Array[]): Uint8Array<ArrayBuffer> {
  const out = new Uint8Array(parts.reduce((sum, p) => sum + p.length, 0));
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

type SubmittedFile = { key: string; name: string };

// Storage keys only allow `[A-Za-z0-9/_.-]`, so the browser sends the original
// file name (with diacritics) next to each key.
function getSubmittedFiles(raw: unknown): SubmittedFile[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => ({
    key: String(item?.key ?? ""),
    name: String(item?.name ?? "").trim().slice(0, 255) || "document.pdf",
  }));
}

function buildMultipart(boundary: string, files: Array<{ name: string; data: Uint8Array }>, uploadedBy: string) {
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

async function userFunction(context: FunctionContext): Promise<SubmitResult | SubmitError> {
  const hash = String(context.data?.hash || "").trim();
  if (!hash) {
    context.response.setStatus(400);
    return { error: "missing_hash" };
  }

  const caseId = await getCaseIdForHash(context, hash);
  if (!caseId) {
    context.response.setStatus(404);
    return { error: "invalid_link" };
  }

  // Only keys inside this case's folder are accepted, so a link cannot submit
  // other files from the workspace storage.
  const prefix = getUploadPrefix(caseId);
  const submitted = getSubmittedFiles(context.data?.files);
  if (
    submitted.length === 0 ||
    submitted.length > MAX_FILES ||
    submitted.some(({ key }) => !key.startsWith(prefix) || key.includes(".."))
  ) {
    context.response.setStatus(400);
    return { error: "invalid_files" };
  }

  const ingestUrl = getGlobalUrl(context, "kb_aws_ingest_url");
  if (!ingestUrl) {
    context.response.setStatus(503);
    return { error: "not_configured" };
  }

  const uploadedBy = String(context.data?.uploaded_by || "").trim().slice(0, 255);

  try {
    const files = [];
    for (const file of submitted) {
      const { data } = await context.storage.download(file.key);
      files.push({ name: file.name, data });
    }

    const boundary = `----kb-intake-${getRandomId()}`;
    const response = await fetch(`${ingestUrl}/cases/${encodeURIComponent(caseId)}/documents`, {
      method: "POST",
      headers: { "content-type": `multipart/form-data; boundary=${boundary}`, accept: "application/json" },
      body: buildMultipart(boundary, files, uploadedBy),
      secretName: INGEST_SECRET,
      timeoutMs: TIMEOUT_MS,
    });
    const text = await response.text();
    let body: { documents?: unknown; error?: string } | null = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }

    if (!response.ok) {
      console.log(`ingest returned ${response.status}: ${body?.error ?? text.slice(0, 200)}`);
      // 4xx are about the files (not a PDF, too large, …) and worth showing; 5xx are not.
      if (response.status >= 400 && response.status < 500 && response.status !== 401 && response.status !== 403) {
        context.response.setStatus(response.status);
        return { error: "rejected", message: body?.error };
      }
      context.response.setStatus(502);
      return { error: "upstream" };
    }

    // Ingest now owns the files; the storage copies were only for the hand-off.
    for (const { key } of submitted) {
      try {
        await context.storage.delete(key);
      } catch (error) {
        console.log(`could not delete ${key}: ${getErrorMessage(error)}`);
      }
    }
    // Whitelist: internal fields such as `also_in` (other cases) must not reach the anonymous client.
    return { documents: toClientDocuments(body?.documents) };
  } catch (error) {
    console.log(`intake submit failed: ${getErrorMessage(error)}`);
    context.response.setStatus(502);
    return { error: "upstream" };
  }
}
