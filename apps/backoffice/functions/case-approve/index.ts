// Approve disbursement (body: case_id). The case moves to approved; the legacy
// write that would then move it to completed does not exist yet.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage } from "../lib/awsApi.ts";
import { isAwaitingDecision, setCaseStatus } from "../lib/caseStatus.ts";

const CASE_FUNCTION = "agent-functions/eval-case-get";

export type CaseApproveResponse =
  | { case_id: string; status: "approved" }
  | { error: "bad_request" | "case_not_found" | "not_awaiting_decision" | "upstream"; message?: string };

export async function userFunction(context: FunctionContext): Promise<CaseApproveResponse> {
  const caseId = typeof context.data?.case_id === "string" ? context.data.case_id.trim().slice(0, 200) : "";
  if (!caseId) {
    context.response.setStatus(400);
    return { error: "bad_request" };
  }

  let evalCase: { case?: { status?: string }; error?: string };
  try {
    const { result } = await context.functions.run({ slug: CASE_FUNCTION, params: { case_id: caseId } });
    evalCase = (result as typeof evalCase | null) ?? { error: "empty response" };
  } catch (error) {
    evalCase = { error: getErrorMessage(error) };
  }
  if (evalCase.error) {
    context.response.setStatus(evalCase.error === "case_not_found" ? 404 : 502);
    return { error: evalCase.error === "case_not_found" ? "case_not_found" : "upstream", message: evalCase.error };
  }
  if (!isAwaitingDecision(evalCase.case?.status)) {
    context.response.setStatus(409);
    return { error: "not_awaiting_decision", message: `The case is ${evalCase.case?.status ?? "without a status"}, not awaiting_decision.` };
  }

  const statusError = await setCaseStatus(context, caseId, "approved");
  if (statusError) {
    console.log(`case ${caseId} status update failed: ${statusError}`);
    context.response.setStatus(502);
    return { error: "upstream", message: statusError };
  }
  return { case_id: caseId, status: "approved" };
}
