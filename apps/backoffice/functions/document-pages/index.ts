// Returns the masked page previews of the requested documents of one case
// (body: case_id, document_ids) for the case detail. The AWS API presigns the
// links for 300 s; the readable original is never requested here. A document
// the API fails on is marked `error`, so the others still show.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, requestAwsApi } from "../lib/awsApi.ts";
import { parseRequest, toDocumentPreview, type DocumentPreview, type UpstreamDocumentPages } from "./pages.ts";

const CONCURRENCY = 4;

type DocumentPagesResponse = { documents: DocumentPreview[] } | { error: "bad_request" };

async function readPreview(context: FunctionContext, caseId: string, documentId: string): Promise<DocumentPreview> {
  const path = `/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(documentId)}/pages`;
  try {
    const response = await requestAwsApi<UpstreamDocumentPages>(context, path);
    if (response.ok && response.body) return toDocumentPreview(documentId, response.body);
    if (response.status === 404) return { documentId, status: "not_found" };
    if (response.status === 409) return { documentId, status: "processing" };
    console.log(`${path} returned ${response.status}`);
  } catch (error) {
    console.log(`${path} request failed: ${getErrorMessage(error)}`);
  }
  return { documentId, status: "error" };
}

export async function userFunction(context: FunctionContext): Promise<DocumentPagesResponse> {
  const request = parseRequest(context.data);
  if (!request) {
    context.response.setStatus(400);
    return { error: "bad_request" };
  }

  const queue = [...request.documentIds];
  const byId = new Map<string, DocumentPreview>();
  await Promise.all(
    Array.from({ length: CONCURRENCY }, async () => {
      for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
        byId.set(id, await readPreview(context, request.caseId, id));
      }
    }),
  );
  return { documents: request.documentIds.map((id) => byId.get(id) as DocumentPreview) };
}
