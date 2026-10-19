import { test } from "node:test";
import assert from "node:assert/strict";
import { toCaseSummary } from "./awsApi.ts";

const awsCase = { case_id: "17026014-25", client_id: "c1", status: "open", created_at: "2026-10-19T09:00:00Z" };

test("toCaseSummary takes the client from the case metadata", () => {
  assert.deepEqual(toCaseSummary({ ...awsCase, metadata: { client_name: "Solom Rec s.r.o.", ico: "04606812" } }), {
    ...awsCase,
    client_name: "Solom Rec s.r.o.",
    client_ico: "04606812",
  });
});

test("toCaseSummary leaves the client empty for cases without metadata", () => {
  assert.deepEqual(toCaseSummary({ ...awsCase, metadata: { ico: 4606812 } }), {
    ...awsCase,
    client_name: null,
    client_ico: null,
  });
});
