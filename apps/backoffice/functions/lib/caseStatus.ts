// Moves a case along its lifecycle (wonderfulkb architecture/case-statuses.md)
// after a worker's decision, through the agent-functions case-status-set Function.
// The AWS API does not check transitions, so callers check isAwaitingDecision first.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage } from "./awsApi.ts";

const STATUS_FUNCTION = "agent-functions/case-status-set";

// The case-evaluator moves a case to awaiting_decision when it finishes; only then may the worker decide.
export function isAwaitingDecision(status: string | null | undefined): boolean {
  return status === "awaiting_decision";
}

/** Sets the case's status; returns the error, or null once it is set. */
export async function setCaseStatus(context: FunctionContext, caseId: string, status: "approved" | "awaiting_clarification"): Promise<string | null> {
  try {
    const { result } = await context.functions.run({ slug: STATUS_FUNCTION, params: { case_id: caseId, status } });
    const error = (result as { error?: string } | null)?.error;
    return error ? String(error) : null;
  } catch (error) {
    return getErrorMessage(error);
  }
}
