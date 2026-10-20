// Reveals the readable original of one case document (body: case_id,
// document_id) on a reviewer's explicit action. The AWS API audits the call
// under this app's API key, so this Function adds an audit line naming the
// signed-in user by the id and email the platform puts on context.user. The
// link is presigned for 60 s and is never logged.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, requestAwsApi } from "../lib/awsApi.ts";
import { parseRequest } from "../document-pages/pages.ts";

/** Body of GET /cases/{case_id}/documents/{document_id}/original (be-document-processing/contracts/openapi-validator-agent.yaml). */
type UpstreamDocumentOriginal = { filename: string; content_type: string; url: string; expires_in: number };

type Outcome = "revealed" | "not_found" | "error";

type DocumentOriginalResponse =
  | { filename: string; contentType: string; url: string; expiresIn: number }
  | { error: "bad_request" | "unauthenticated" | "not_found" | "upstream" };

function audit(context: FunctionContext, caseId: string, documentId: string, outcome: Outcome) {
  const record = { event: "document_reveal", user_id: context.user?.id, user_email: context.user?.email, case_id: caseId, document_id: documentId, outcome };
  console.log(JSON.stringify(record));
}

export async function userFunction(context: FunctionContext): Promise<DocumentOriginalResponse> {
  const body = (context.data ?? {}) as { case_id?: unknown; document_id?: unknown };
  const request = parseRequest({ case_id: body.case_id, document_ids: [body.document_id] });
  if (!request || body.document_id === undefined) {
    context.response.setStatus(400);
    return { error: "bad_request" };
  }
  // Only a person may reveal an original; the audit has to name them.
  if (!context.user?.id) {
    context.response.setStatus(401);
    return { error: "unauthenticated" };
  }

  const [documentId] = request.documentIds;
  const path = `/cases/${encodeURIComponent(request.caseId)}/documents/${encodeURIComponent(documentId)}/original`;
  let outcome: Outcome = "error";
  try {
    const response = await requestAwsApi<UpstreamDocumentOriginal>(context, path);
    if (response.ok && response.body?.url) {
      outcome = "revealed";
      const { filename, content_type, url, expires_in } = response.body;
      return { filename, contentType: content_type, url, expiresIn: expires_in };
    }
    if (response.status === 404) {
      outcome = "not_found";
      context.response.setStatus(404);
      return { error: "not_found" };
    }
    console.log(`${path} returned ${response.status}${response.ok ? " without a link" : ""}`);
  } catch (error) {
    console.log(`${path} request failed: ${getErrorMessage(error)}`);
  } finally {
    audit(context, request.caseId, documentId, outcome);
  }
  context.response.setStatus(502);
  return { error: "upstream" };
}
