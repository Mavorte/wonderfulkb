import { test } from "node:test";
import assert from "node:assert/strict";
import type { FunctionContext } from "@wonderful/types";
import { userFunction } from "./index.ts";

type Row = Record<string, unknown>;
type Filter = { column: string; value: unknown };
type Order = { column: string; direction: "asc" | "desc" };

const ROWS: Row[] = [
  { request_id: "r1", case_id: "C1", status: "call_failed", requested_at: "2026-10-20T09:00:00Z", contact_last_name: "Křemeník" },
  { request_id: "r2", case_id: "C1", status: "email_sent", requested_at: "2026-10-20T10:00:00Z", requested_by: "reviewer@kb.example", contact_last_name: "Křemeník" },
  { request_id: "r3", case_id: "C2", status: "pending", requested_at: "2026-10-20T11:00:00Z", contact_last_name: "Novák" },
];

function createContext(data: Row) {
  let status = 200;
  const context = {
    data,
    response: { setStatus: (code: number) => (status = code) },
    tables: {
      filter: async (_table: string, filters: Filter[], limit: number, _offset: number, [order]: Order[]) => {
        const rows = ROWS.filter((row) => filters.every((f) => row[f.column] === f.value)).sort(
          (a, b) => String(a[order.column]).localeCompare(String(b[order.column])) * (order.direction === "desc" ? -1 : 1),
        );
        return { rows: rows.slice(0, limit).map((row) => ({ data: row })) };
      },
    },
  };
  return { context: context as unknown as FunctionContext, status: () => status };
}

test("correction-call-status returns the latest call of the case without the surname", async () => {
  const { context } = createContext({ case_id: "C1" });
  assert.deepEqual(await userFunction(context), {
    call: { request_id: "r2", status: "email_sent", requested_at: "2026-10-20T10:00:00Z", requested_by: "reviewer@kb.example" },
  });
});

test("correction-call-status answers null for a case without calls and 400 without a case", async () => {
  assert.deepEqual(await userFunction(createContext({ case_id: "C9" }).context), { call: null });
  const missing = createContext({});
  assert.deepEqual(await userFunction(missing.context), { error: "bad_request" });
  assert.equal(missing.status(), 400);
});
