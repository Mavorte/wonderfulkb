// Looks up one case in the AWS case/client API and adds the hash of its
// Client Intake link from client_intake.intake_links.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, requestAwsApi, toCaseSummary, type AwsCase, type CaseSummary } from "../lib/awsApi";

const LINKS_TABLE = "client_intake.intake_links";
const CASE_ID_PATTERN = /^[A-Za-z0-9._-]{1,128}$/;

type CaseGetResponse =
  | { case: CaseSummary & { metadata: Record<string, unknown> }; hash: string | null }
  | { error: "invalid_case_id" | "case_not_found" | "upstream" };

async function userFunction(context: FunctionContext): Promise<CaseGetResponse> {
  const caseId = String(context.data?.case_id ?? "").trim();
  if (!CASE_ID_PATTERN.test(caseId)) {
    context.response.setStatus(400);
    return { error: "invalid_case_id" };
  }

  try {
    const response = await requestAwsApi<AwsCase>(context, `/cases/${encodeURIComponent(caseId)}`);
    if (response.status === 404) {
      context.response.setStatus(404);
      return { error: "case_not_found" };
    }
    if (response.ok && response.body) {
      const { rows } = await context.tables.filter(
        LINKS_TABLE,
        [{ column: "case_id", operator: "eq", value: caseId }],
        1,
        0,
      );
      const hash: unknown = rows[0]?.data?.hash;
      return {
        case: { ...toCaseSummary(response.body), metadata: response.body.metadata ?? {} },
        hash: typeof hash === "string" && hash ? hash : null,
      };
    }
  } catch (error) {
    console.log(`case lookup failed: ${getErrorMessage(error)}`);
  }
  context.response.setStatus(502);
  return { error: "upstream" };
}
