// Shared by the evaluation functions: reads and deletes a case's rows in the
// case-evaluator's tables, owned by the agent-functions app and linked to this one.
// Results reference evaluations with on_delete cascade, but both are deleted
// explicitly so orphaned results go too.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, type UpstreamResult } from "./upstream";

export const EVALUATIONS_TABLE = "agent_functions.case_evaluations";
export const RESULTS_TABLE = "agent_functions.case_evaluation_results";

const PAGE_SIZE = 100;
const MAX_PAGES = 20;

export type TableRow = { id: string; data: Record<string, unknown> };

function byColumn(column: string, value: string) {
  return [{ column, operator: "eq", value }];
}

export async function listRowsBy(
  context: FunctionContext,
  table: string,
  column: string,
  value: string,
  orderBy: Array<{ column: string; direction?: "asc" | "desc" }>,
): Promise<TableRow[]> {
  const rows: TableRow[] = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const result = await context.tables.filter(table, byColumn(column, value), PAGE_SIZE, page * PAGE_SIZE, orderBy);
    rows.push(...result.rows);
    if (result.rows.length < PAGE_SIZE) break;
  }
  return rows;
}

export function listCaseRows(
  context: FunctionContext,
  table: string,
  caseId: string,
  orderBy: Array<{ column: string; direction?: "asc" | "desc" }>,
): Promise<TableRow[]> {
  return listRowsBy(context, table, "case_id", caseId, orderBy);
}

// Deletes page by page from offset 0 until nothing matches; returns the count.
// Without a case ID it deletes every row of the table.
export async function deleteCaseRows(context: FunctionContext, table: string, caseId?: string): Promise<number> {
  let deleted = 0;
  const filters = caseId ? byColumn("case_id", caseId) : [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const { rows } = await context.tables.filter(table, filters, PAGE_SIZE, 0);
    if (!rows.length) break;
    await Promise.all(rows.map((row) => context.tables.deleteRow(table, row.id)));
    deleted += rows.length;
  }
  return deleted;
}

// Same shape as the upstream calls, with the table names as the "URL".
export async function tableResult(run: () => Promise<unknown>): Promise<UpstreamResult> {
  const url = `${EVALUATIONS_TABLE}, ${RESULTS_TABLE}`;
  try {
    return { url, status: 200, ok: true, body: await run() };
  } catch (error) {
    return { url, status: 500, ok: false, body: null, error: getErrorMessage(error) };
  }
}
