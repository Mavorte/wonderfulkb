// Stores one PDF from the intake page in Custom Storage, under the case's
// folder, and returns its storage key for intake-submit.
//
// The intake page runs on an anonymous share link, where apps can only invoke
// Functions (no Custom Storage API), so the browser sends each file here as
// base64, one call per file.

import type { FunctionContext } from "@wonderful/types";
import { getCaseIdForHash, getErrorMessage, getRandomId, getUploadPrefix } from "../shared/intakeLinks";

// Direct `context.storage.upload` limit.
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

type StageResult = { key: string; size: number };

type StageError = { error: "missing_hash" | "invalid_link" | "invalid_file" | "too_large" | "storage" };

function decodeBase64(input: string): Uint8Array | null {
  const clean = input.replace(/\s+/g, "").replace(/=+$/, "");
  const lookup = new Map(Array.from(BASE64_ALPHABET, (c, i) => [c, i]));
  const out = new Uint8Array(Math.floor((clean.length * 3) / 4));
  let buffer = 0;
  let bits = 0;
  let offset = 0;
  for (const char of clean) {
    const value = lookup.get(char);
    if (value === undefined) return null;
    buffer = (buffer << 6) | value;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out[offset++] = (buffer >> bits) & 0xff;
    }
  }
  return out.subarray(0, offset);
}

function isPdf(data: Uint8Array): boolean {
  return data.length > 5 && String.fromCharCode(...data.subarray(0, 5)) === "%PDF-";
}

// Storage keys allow only `[A-Za-z0-9/_.-]`; the original name travels separately.
function getSafeName(name: string): string {
  const safe = name.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[^A-Za-z0-9]+/, "");
  return (safe || "document").slice(0, 120);
}

async function userFunction(context: FunctionContext): Promise<StageResult | StageError> {
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

  const content = String(context.data?.content_base64 || "");
  if (content.length > Math.ceil((MAX_FILE_BYTES * 4) / 3) + 4) {
    context.response.setStatus(413);
    return { error: "too_large" };
  }
  const data = decodeBase64(content);
  if (!data || !isPdf(data)) {
    context.response.setStatus(415);
    return { error: "invalid_file" };
  }

  const key = `${getUploadPrefix(caseId)}${getRandomId()}/${getSafeName(String(context.data?.name || ""))}`;
  try {
    const info = await context.storage.upload(key, data, "application/pdf");
    return { key: info.key, size: info.size };
  } catch (error) {
    console.log(`storage upload failed: ${getErrorMessage(error)}`);
    context.response.setStatus(502);
    return { error: "storage" };
  }
}
