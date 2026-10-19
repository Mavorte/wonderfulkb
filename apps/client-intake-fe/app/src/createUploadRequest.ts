import type { UploadedDocument } from "./types";

type UploadResult =
  | { ok: true; documents: UploadedDocument[] }
  | { ok: false; message: string };

// Sends all files in one multipart request to the AWS ingest endpoint
// (POST /cases/{case_id}/documents). Called from the browser because Wonderful
// Functions cannot carry PDF bodies.
export default async function createUploadRequest(
  upload: { url: string; api_key: string },
  files: File[],
  uploadedBy: string | null | undefined,
): Promise<UploadResult> {
  const body = new FormData();
  for (const file of files) body.append("files", file, file.name);
  if (uploadedBy) body.append("uploaded_by", uploadedBy);

  try {
    const response = await fetch(upload.url, {
      method: "POST",
      headers: { "x-api-key": upload.api_key },
      body,
    });
    const json = await response.json().catch(() => null);
    if (!response.ok) {
      const message = json?.error?.message ?? `Upload failed (HTTP ${response.status}).`;
      return { ok: false, message };
    }
    return { ok: true, documents: json?.documents ?? [] };
  } catch {
    return { ok: false, message: "Upload failed: the document service could not be reached." };
  }
}
