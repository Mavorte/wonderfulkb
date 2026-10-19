import { test } from "node:test";
import assert from "node:assert/strict";
import { createClientDirectory } from "./directory.ts";

const client = { client_id: "c1", ico: "98007106", name: "Agroluh Vřesava s.r.o.", status: "active" };

test("createClientDirectory joins cases to their client, newest first, and keeps clients without cases", () => {
  const [result] = createClientDirectory(
    [client],
    [
      { case_id: "old", client_id: "c1", status: "completed", created_at: "2026-01-01T00:00:00Z" },
      { case_id: "new", client_id: "c1", status: "awaiting_decision", created_at: "2026-02-01T00:00:00Z" },
      { case_id: "other", client_id: "c2", status: "open", created_at: "2026-03-01T00:00:00Z" },
    ],
  );
  assert.deepEqual(
    result.cases.map((c) => [c.case_id, c.status]),
    [
      ["new", "awaiting_decision"],
      ["old", "completed"],
    ],
  );
  assert.deepEqual(createClientDirectory([client], [])[0].cases, []);
});

test("createClientDirectory flattens KYC, first signatory and email, sorted by name", () => {
  const result = createClientDirectory(
    [
      { ...client, client_id: "z", name: "Zrnovia s.r.o." },
      {
        ...client,
        kyc: { status: "ok", checked_at: "2026-02-16" },
        signatories: [{ name: "Irena Březanová", function: "jednatelka" }],
        contacts: [{}, { email: "kancelar@agroluh.example" }],
      },
    ],
    [],
  );
  assert.deepEqual(
    result.map((c) => c.name),
    ["Agroluh Vřesava s.r.o.", "Zrnovia s.r.o."],
  );
  assert.equal(result[0].kyc_status, "ok");
  assert.equal(result[0].kyc_checked_at, "2026-02-16");
  assert.deepEqual(result[0].signatory, { name: "Irena Březanová", function: "jednatelka" });
  assert.equal(result[0].email, "kancelar@agroluh.example");
  assert.equal(result[1].signatory, null);
});

test("createClientDirectory orders mixed Z and +00:00 timestamps by instant", () => {
  const [result] = createClientDirectory(
    [client],
    [
      { case_id: "a", client_id: "c1", status: "open", created_at: "2026-10-19T14:25:16+00:00" },
      { case_id: "b", client_id: "c1", status: "open", created_at: "2026-10-19T14:25:16.483+00:00" },
      { case_id: "c", client_id: "c1", status: "open", created_at: "2026-10-19T15:00:00Z" },
      { case_id: "d", client_id: "c1", status: "open", created_at: "not a date" },
    ],
  );
  assert.deepEqual(
    result.cases.map((c) => c.case_id),
    ["c", "b", "a", "d"],
  );
});
