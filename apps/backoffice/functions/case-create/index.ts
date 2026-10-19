// Creates a case for a client in the AWS case/client API and registers its
// intake link, so the Client Intake app can resolve `?h=<hash>` to the case.
//
// The response carries the client's intake link, built from the global
// `public_access_base_url` (the Client Intake public URL) as `<base>?h=<hash>`.
//
// The API assigns the case id and returns it. The client's name and IČO go
// into the case metadata so the case list can show them.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, requestAwsApi, type AwsCase } from "../lib/awsApi";
import { buildIntakeLink, generateHash } from "./ids";

const LINKS_TABLE = "client_intake.intake_links";
const BASE_URL_GLOBAL = "public_access_base_url";

type CaseCreateResponse =
  | { case_id: string; client_id: string; hash: string | null; link: string | null; created_at: string }
  | { error: "missing_client_id" | "client_not_found" | "client_not_active" | "upstream" };

async function userFunction(context: FunctionContext): Promise<CaseCreateResponse> {
  const clientId = String(context.data?.client_id || "").trim();
  if (!clientId) {
    context.response.setStatus(400);
    return { error: "missing_client_id" };
  }

  let created: AwsCase;
  try {
    const response = await requestAwsApi<AwsCase>(context, "/cases", {
      method: "POST",
      body: {
        client_id: clientId,
        metadata: { client_name: String(context.data?.client_name ?? ""), ico: String(context.data?.ico ?? "") },
      },
    });
    if (response.status === 404 || response.status === 409) {
      context.response.setStatus(response.status);
      return { error: response.status === 404 ? "client_not_found" : "client_not_active" };
    }
    if (!response.ok || !response.body?.case_id) {
      context.response.setStatus(502);
      return { error: "upstream" };
    }
    created = response.body;
  } catch (error) {
    console.log(`case create request failed: ${getErrorMessage(error)}`);
    context.response.setStatus(502);
    return { error: "upstream" };
  }

  // The case already exists upstream, so a failed link still reports the case
  // (with no hash) instead of inviting a retry that would create a second one.
  let hash: string | null = generateHash();
  try {
    await context.tables.insert(LINKS_TABLE, { hash, case_id: created.case_id, inserted_at: Date.now() });
  } catch (error) {
    console.log(`intake link for case ${created.case_id} failed: ${getErrorMessage(error)}`);
    hash = null;
  }

  const link = buildIntakeLink(String(context.globals.get(BASE_URL_GLOBAL) ?? ""), hash);
  if (hash && !link) console.log(`global ${BASE_URL_GLOBAL} is not set; case ${created.case_id} has no intake link`);

  return { case_id: created.case_id, client_id: clientId, hash, link, created_at: created.created_at };
}
