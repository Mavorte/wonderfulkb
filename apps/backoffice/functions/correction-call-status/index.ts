// Returns the latest Request correction call of a case (body: case_id) so the
// case screen can show how far the correction-caller agent got. The surname on
// file and the findings stay in the table.

import type { FunctionContext } from "@wonderful/types";

const CALLS_TABLE = "backoffice.correction_calls";

export type CorrectionCall = { request_id: string; status: string; requested_at: string; requested_by: string | null };

export async function userFunction(context: FunctionContext): Promise<{ call: CorrectionCall | null } | { error: "bad_request" }> {
  const caseId = typeof context.data?.case_id === "string" ? context.data.case_id.trim() : "";
  if (!caseId) {
    context.response.setStatus(400);
    return { error: "bad_request" };
  }
  const { rows } = await context.tables.filter(CALLS_TABLE, [{ column: "case_id", operator: "eq", value: caseId }], 1, 0, [
    { column: "requested_at", direction: "desc" },
  ]);
  const row = rows[0]?.data;
  if (!row) return { call: null };
  return {
    call: {
      request_id: String(row.request_id),
      status: String(row.status),
      requested_at: String(row.requested_at),
      requested_by: row.requested_by ? String(row.requested_by) : null,
    },
  };
}
