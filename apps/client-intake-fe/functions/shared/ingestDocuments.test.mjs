// Run with `node --test functions/shared/ingestDocuments.test.mjs` (node built-in runner; Node 22.6+ strips the TS types).
import assert from "node:assert/strict";
import { test } from "node:test";
import { toClientDocuments } from "./ingestDocuments.ts";

const fromIngest = {
  document_id: "6f1c2e0d-7a11-5d3f-9b36-0a524a8b7c1e",
  filename: "0_Form_Smlouva.pdf",
  received_at: "2026-10-19T12:00:00Z",
  content_type: "application/pdf",
  size_bytes: 1234,
  duplicate: false,
  also_in: [{ case_id: "other-case", document_id: "11111111-2222-5333-8444-555555555555" }],
};

test("keeps only whitelisted fields, drops also_in", () => {
  const [doc] = toClientDocuments([fromIngest]);
  assert.deepEqual(doc, {
    document_id: fromIngest.document_id,
    filename: fromIngest.filename,
    received_at: fromIngest.received_at,
    content_type: "application/pdf",
    size_bytes: 1234,
  });
  assert.ok(!JSON.stringify(doc).includes("other-case"));
});

test("non-array input gives an empty list", () => {
  assert.deepEqual(toClientDocuments(undefined), []);
  assert.deepEqual(toClientDocuments({ documents: [] }), []);
});
