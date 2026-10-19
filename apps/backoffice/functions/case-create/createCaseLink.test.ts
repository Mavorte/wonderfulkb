import assert from "node:assert/strict";
import { test } from "node:test";
import createCaseLink from "./createCaseLink.ts";

function createContext(data: { client_id?: string; case_id?: string }) {
  const records: Record<string, unknown>[] = [];
  let status = 200;
  return {
    data, records, getStatus: () => status,
    response: { setStatus(value: number) { status = value; } },
    tables: {
      async filter(table: string, filters: { column: string; operator: string; value: string }[], limit: number, offset: number) {
        assert.equal(table, "client_intake.intake_links");
        assert.equal(limit, 1);
        assert.equal(offset, 0);
        return { rows: records.filter((r) => filters.every((f) => r[f.column] === f.value)).map((item) => ({ data: item })) };
      },
      async insert(table: string, item: Record<string, unknown>) {
        assert.equal(table, "client_intake.intake_links");
        records.push(item);
      },
    },
  };
}

test("links the supplied backend case and reuses its hash on retry", async () => {
  const context = createContext({ client_id: "firm-id", case_id: "case-ocr-stable" });
  const first = await createCaseLink(context);
  const second = await createCaseLink(context);
  assert.equal(first.case_id, "case-ocr-stable");
  assert.equal(first.client_id, "firm-id");
  assert.match(first.hash!, /^[A-Za-z0-9_-]{22}$/);
  assert.deepEqual(first, second);
  assert.equal(context.records.length, 1);
});

test("preserves standalone mocked case creation when case_id is absent", async () => {
  const context = createContext({ client_id: "firm-id" });
  const result = await createCaseLink(context);
  assert.match(result.case_id!, /^\d{8}-\d{2}$/);
  assert.match(result.hash!, /^[A-Za-z0-9_-]{22}$/);
  assert.equal(context.records.length, 1);
});

test("rejects missing clients and malformed IDs without inserting a link", async () => {
  for (const data of [{}, { client_id: "firm-id", case_id: "../case" }, { client_id: "firm-id", case_id: "" }]) {
    const context = createContext(data);
    const result = await createCaseLink(context);
    assert.ok(result.error);
    assert.equal(context.getStatus(), 400);
    assert.equal(context.records.length, 0);
  }
});
