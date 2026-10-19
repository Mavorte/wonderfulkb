import { test } from "node:test";
import assert from "node:assert/strict";
import type { FunctionContext } from "@wonderful/types";
import { userFunction } from "./index.ts";

type Row = Record<string, unknown>;
type Filter = { column: string; operator: string; value: unknown };
type Order = { column: string; direction: "asc" | "desc" };

// In-memory stand-in for context.tables that honours eq filters, order and limit.
function createContext(tables: Record<string, Row[]>, data: Row) {
  let status = 200;
  const context = {
    data,
    response: { setStatus: (code: number) => (status = code) },
    tables: {
      filter: async (table: string, filters: Filter[], limit: number, _offset: number, order: Order[] = []) => {
        let rows = (tables[table] ?? []).filter((row) => filters.every((f) => row[f.column] === f.value));
        for (const { column, direction } of [...order].reverse()) {
          rows = [...rows].sort((a, b) => String(a[column]).localeCompare(String(b[column])) * (direction === "desc" ? -1 : 1));
        }
        return { rows: rows.slice(0, limit).map((row) => ({ data: row })) };
      },
    },
  };
  // The function only touches data, response.setStatus and tables.filter.
  return { context: context as unknown as FunctionContext, status: () => status };
}

const run = (case_id: string, evaluation_id: string, started_at: string) => ({ case_id, evaluation_id, started_at });

const tables = {
  "agent_functions.case_evaluations": [
    run("A", "a-old", "2026-10-01T00:00:00Z"),
    run("B", "b-1", "2026-10-02T00:00:00Z"),
    run("A", "a-new", "2026-10-03T00:00:00Z"),
  ],
  "agent_functions.case_evaluation_results": [
    { evaluation_id: "a-new", rule_id: "r1", recorded_at: "2026-10-03T00:01:00Z" },
    { evaluation_id: "b-1", rule_id: "r1", recorded_at: "2026-10-02T00:01:00Z" },
  ],
};

async function call(data: Row) {
  const { context, status } = createContext(tables, data);
  const body = (await userFunction(context)) as { evaluation?: Row; results?: Row[]; error?: string };
  return { status: status(), evaluationId: body.evaluation?.evaluation_id, results: body.results?.length, error: body.error };
}

test("evaluation-get returns the latest run overall, of a case, or the requested run", async () => {
  assert.deepEqual(await call({}), { status: 200, evaluationId: "a-new", results: 1, error: undefined });
  assert.deepEqual(await call({ case_id: "B" }), { status: 200, evaluationId: "b-1", results: 1, error: undefined });
  assert.equal((await call({ case_id: "A" })).evaluationId, "a-new");
  assert.equal((await call({ evaluation_id: "a-old", case_id: "B" })).evaluationId, "a-old");
});

test("evaluation-get answers 404 for an unknown case or run", async () => {
  assert.equal((await call({ case_id: "missing" })).status, 404);
  assert.equal((await call({ evaluation_id: "missing" })).error, "evaluation_not_found");
});
