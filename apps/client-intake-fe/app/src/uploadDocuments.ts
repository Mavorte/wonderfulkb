import type { useWonderful } from "@wonderful/app-sdk";
import type { UploadedDocument } from "./types";

type WonderfulApi = ReturnType<typeof useWonderful>["api"];

type UploadResult =
  | { ok: true; documents: UploadedDocument[] }
  | { ok: false; message: string; failedFile?: File };

// `staging` reports the file being stored now; `submitting` the hand-off of all
// staged files to ingest.
export type UploadProgress = { phase: "staging"; index: number } | { phase: "submitting" };

type StageResponse = { key?: string; error?: string };

type SubmitResponse = { documents?: UploadedDocument[]; error?: string; message?: string };

// Mirrors the direct Custom Storage upload limit enforced by intake-stage.
export const MAX_FILE_BYTES = 10 * 1024 * 1024;

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).slice(String(reader.result).indexOf(",") + 1));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

// Sends the files to the AWS ingest service. On a share link the app can only
// invoke Functions, so each file is staged in Custom Storage by intake-stage,
// then intake-submit forwards them all to ingest with the API key attached
// server-side.
export default async function uploadDocuments(
  api: WonderfulApi,
  hash: string,
  files: File[],
  uploadedBy: string | null | undefined,
  onProgress: (progress: UploadProgress) => void,
): Promise<UploadResult> {
  const staged: Array<{ key: string; name: string }> = [];
  for (const [index, file] of files.entries()) {
    onProgress({ phase: "staging", index });
    try {
      const result = await api.invokeFunction<StageResponse>("client-intake/intake-stage", {
        method: "POST",
        params: { hash, name: file.name, content_base64: await readBase64(file) },
      });
      if (!result?.key) {
        const reason = result?.error === "invalid_file" ? "is not a valid PDF" : "could not be uploaded";
        return { ok: false, message: `${file.name} ${reason}.`, failedFile: file };
      }
      staged.push({ key: result.key, name: file.name });
    } catch {
      return { ok: false, message: `${file.name} could not be sent. Please try again.`, failedFile: file };
    }
  }

  onProgress({ phase: "submitting" });
  try {
    const result = await api.invokeFunction<SubmitResponse>("client-intake/intake-submit", {
      method: "POST",
      params: { hash, files: staged, uploaded_by: uploadedBy ?? undefined },
    });
    if (result?.error) {
      return {
        ok: false,
        message:
          result.error === "rejected" && result.message
            ? result.message
            : "The document service did not accept the files. Please try again later.",
      };
    }
    return { ok: true, documents: result?.documents ?? [] };
  } catch {
    return { ok: false, message: "The documents could not be sent to KB. Please try again." };
  }
}
